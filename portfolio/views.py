import csv
import json
import logging
import re
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.db.models import F
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST

from crm.models import Cliente, Mockup
from portfolio import chatbot as chatbot_service
from portfolio.marca import link_rebel_tech, marca_demo, marca_do_lead
from portfolio import conteudo_estetica
from portfolio.fotos_mockup import fotos_do_template
from portfolio.mockup_landings import LANDINGS, biblioteca_do_nicho, biblioteca_publica, paginas_do_tipo
from portfolio.models import Project

logger = logging.getLogger(__name__)


def load_icon_list(filename, with_level=False):
    path = Path(settings.BASE_DIR) / "data" / filename
    items = []
    if not path.exists():
        return items
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            slug = row["slug"].strip()
            color = row["color"].strip()
            color_dark = row.get("color_dark", color).strip()
            icon_local = (row.get("icon") or "").strip()
            item = {
                "name": row["name"].strip(),
                "slug": slug,
                "icon_local": icon_local,
                "icon_light": f"https://cdn.simpleicons.org/{slug}/{color}",
                "icon_dark": f"https://cdn.simpleicons.org/{slug}/{color_dark}",
            }
            if with_level:
                item["level"] = int(row.get("level", 100) or 100)
            items.append(item)
    return items


def load_hero_tecnologias():
    return load_icon_list("tecnologias.csv")


def load_skills():
    return load_icon_list("skills.csv", with_level=True)


SITE = {
    "nome": "Vinícius Rebelatto",
    "nome_curto": "Vinícius",
    "cargo": "Desenvolvedor de software",
    "marca": "Rebel Tech",
    "hero_titulo": "Software que escala com o seu negócio.",
    "hero_titulo_destaque": "Software",
    "hero_titulo_resto": " que escala com o seu negócio.",
    "hero_texto": (
        "Transformando requisitos complexos em produtos digitais "
        "rápidos, seguros e focados na experiência do usuário."
    ),
    "sobre": (
        "Construo produtos digitais sólidos e eficientes. Através da Rebel Tech, "
        "entrego soluções completas com foco em performance, usabilidade e uma "
        "arquitetura técnica pronta para acompanhar o crescimento do seu negócio."
    ),
    "seo_title": "Rebel Tech | Desenvolvimento de Software — Vinícius Rebelatto",
    "seo_description": (
        "Desenvolvimento de sites, sistemas web, landing pages e produtos digitais. "
        "A Rebel Tech cria software moderno, rápido e focado em resultado."
    ),
    "seo_keywords": (
        "desenvolvimento de software, criar site, sistema web, landing page, "
        "CRM, ERP, produto digital, Rebel Tech, Vinícius Rebelatto, software sob medida"
    ),
    "og_image": "img/vinicius.png",
    "whatsapp": "5547997867428",
    "whatsapp_display": "(47) 99786-7428",
    "whatsapp_msg": "Olá! Vi o portfolio da Rebel Tech e gostaria de conversar.",
    "linkedin": "https://www.linkedin.com/in/vinicius-rebelatto-07001a232/",
    "github": "https://github.com/vinicius-rebelatto",
    "instagram": "https://www.instagram.com/rebelattovinicius/",
    "email": "vinicius-rebelatto@hotmail.com",
}


def home(request):
    projects = Project.landing_queryset()[:6]
    whatsapp_url = f"https://wa.me/{SITE['whatsapp']}?text={quote(SITE['whatsapp_msg'])}"
    return render(
        request,
        "portfolio/home.html",
        {
            "site": SITE,
            "projects": projects,
            "whatsapp_url": whatsapp_url,
            "hero_tecnologias": load_hero_tecnologias(),
            "skills": load_skills(),
            "vitrine": biblioteca_publica(),
        },
    )


@require_POST
def create_lead(request):
    # Honeypot: bots preenchem "website"
    if request.POST.get("website"):
        return JsonResponse({"ok": True})

    nome = (request.POST.get("nome") or "").strip()
    email = (request.POST.get("email") or "").strip()
    telefone = (request.POST.get("telefone") or "").strip()
    mensagem = (request.POST.get("mensagem") or "").strip()

    errors = {}
    if not nome:
        errors["nome"] = "Informe seu nome."
    if not email:
        errors["email"] = "Informe um e-mail válido."
    if not mensagem:
        errors["mensagem"] = "Escreva uma mensagem."

    if errors:
        return JsonResponse({"ok": False, "errors": errors}, status=400)

    base = slugify(nome)[:180] or "contato"
    slug = base
    index = 2
    while Cliente.objects.filter(slug=slug).exists():
        slug = f"{base}-{index}"
        index += 1

    Cliente.objects.create(
        nome=nome,
        empresa=nome,
        slug=slug,
        email=email,
        telefone=telefone,
        mensagem=mensagem,
        origem=Cliente.Origem.CONTATO,
        status=Cliente.Status.A_PROSPECTAR,
    )
    return JsonResponse({"ok": True, "message": "Recebi seu contato. Em breve retorno!"})


def _pagina_do_template(landing, pagina, servico_slug):
    """Escolhe o arquivo e o contexto da página pedida dentro do template.

    Landing tem uma página só. Site simples tem serviços e contato.
    Institucional tem ainda a página sobre. Página que o tipo não tem é 404.
    """
    if pagina is None:
        return landing["template"], {}
    if pagina not in paginas_do_tipo(landing.get("tipo")):
        raise Http404
    extra = {}
    if pagina == "servico":
        item = conteudo_estetica.servico(servico_slug or "")
        if item is None:
            raise Http404
        extra["servico"] = item
        extra["outros_servicos"] = [s for s in conteudo_estetica.SERVICOS if s["slug"] != item["slug"]][:4]
    return f"portfolio/mockups/_paginas/{pagina}.html", extra


def _contexto_mockup(landing, slug, marca, base_url, pagina, extra):
    return {
        "site": SITE,
        "landing": {"slug": slug, **landing},
        "marca": marca,
        "base_url": base_url,
        "base_template": landing.get("base", landing["template"]),
        "pagina": pagina or "inicio",
        "paginas": paginas_do_tipo(landing.get("tipo")),
        "fotos": fotos_do_template(slug),
        **conteudo_estetica.contexto(marca["nome"]),
        **extra,
    }


def _vitrine_vizinhos(slug, nicho):
    """Anterior e próximo da vitrine pública, para as setas do provador."""
    biblioteca = biblioteca_publica(nicho) if nicho else []
    atual = next((t for t in biblioteca if t["slug"] == slug), None)
    if atual is None or len(biblioteca) < 2:
        return {}
    posicao = biblioteca.index(atual)
    return {
        "vitrine": {
            "biblioteca": biblioteca,
            "posicao": posicao + 1,
            "anterior": biblioteca[posicao - 1],
            "proximo": biblioteca[(posicao + 1) % len(biblioteca)],
        }
    }


def mockup_public(request, slug, pagina=None, servico=None):
    mockup = get_object_or_404(
        Mockup.objects.select_related("cliente").prefetch_related("imagens"),
        slug=slug,
        status=Mockup.Status.PUBLICADO,
    )

    if mockup.tipo == Mockup.Tipo.LANDING:
        landing = LANDINGS.get(mockup.slug)
        if landing:
            arquivo, extra = _pagina_do_template(landing, pagina, servico)
            contexto = _contexto_mockup(
                landing,
                mockup.slug,
                marca_demo(landing),
                reverse("portfolio:mockup_public", kwargs={"slug": mockup.slug}),
                pagina,
                extra,
            )
            contexto["mockup"] = mockup
            contexto.update(_vitrine_vizinhos(mockup.slug, landing.get("nicho")))
            return render(request, arquivo, contexto)

    if pagina is not None:
        raise Http404
    return render(
        request,
        "portfolio/mockup_public.html",
        {"mockup": mockup, "site": SITE},
    )


ROBOS = re.compile(r"bot|crawl|spider|preview|facebookexternalhit|whatsapp|telegram|slack", re.I)


def _registrar_visita(request, cliente, template_slug):
    if request.user.is_authenticated and request.user.is_staff:
        return
    if ROBOS.search(request.META.get("HTTP_USER_AGENT", "")):
        return
    Cliente.objects.filter(pk=cliente.pk).update(
        mockup_visitas=F("mockup_visitas") + 1,
        mockup_visto_em=timezone.now(),
        ultimo_template=template_slug,
    )


def mockup_lead(request, slug, template=None, pagina=None, servico=None):
    """Página de exemplo do lead: template do nicho com a identidade dele.

    /p/<slug>/ abre sempre o primeiro template; /p/<slug>/<template>/ troca a
    pele; /p/<slug>/<template>/<pagina>/ abre as páginas internas. Não chama
    modelo. Staff vê qualquer lead; o público só vê lead da leva (sem site,
    rede social ou site fraco) que não foi rejeitado.
    """
    cliente = get_object_or_404(Cliente, slug=slug)
    staff = request.user.is_authenticated and request.user.is_staff
    if not cliente.recebe_mockup and not staff:
        raise Http404

    biblioteca = biblioteca_do_nicho()
    if not biblioteca:
        raise Http404
    if template is None:
        escolhido = biblioteca[0]
    else:
        escolhido = next((t for t in biblioteca if t["slug"] == template), None)
        if escolhido is None:
            raise Http404

    arquivo, extra = _pagina_do_template(escolhido, pagina, servico)
    posicao = biblioteca.index(escolhido)
    anterior = biblioteca[posicao - 1]
    proximo = biblioteca[(posicao + 1) % len(biblioteca)]

    _registrar_visita(request, cliente, escolhido["slug"])
    marca = marca_do_lead(cliente, escolhido)
    contexto = _contexto_mockup(
        escolhido,
        escolhido["slug"],
        marca,
        reverse("portfolio:mockup_lead_template", kwargs={"slug": cliente.slug, "template": escolhido["slug"]}),
        pagina,
        extra,
    )
    contexto.update(
        {
            "cliente": cliente,
            "biblioteca": biblioteca,
            "posicao": posicao + 1,
            "anterior": anterior,
            "proximo": proximo,
            "rebel_tech_url": link_rebel_tech(SITE, marca["nome"]),
        }
    )
    response = render(request, arquivo, contexto)
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


def mockup_public_legacy(request, slug):
    return redirect("portfolio:mockup_public", slug=slug, permanent=True)


@require_GET
def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /erp/",
        "Disallow: /admin/",
        "Disallow: /chat/",
        "Disallow: /leads/",
        "Disallow: /p/",
        f"Sitemap: {settings.SITE_URL}/sitemap.xml",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


@require_GET
def sitemap_xml(request):
    urls = [
        {
            "loc": f"{settings.SITE_URL}/",
            "changefreq": "weekly",
            "priority": "1.0",
        },
    ]
    body = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for item in urls:
        body.extend(
            [
                "  <url>",
                f"    <loc>{item['loc']}</loc>",
                f"    <changefreq>{item['changefreq']}</changefreq>",
                f"    <priority>{item['priority']}</priority>",
                "  </url>",
            ]
        )
    body.append("</urlset>")
    return HttpResponse("\n".join(body), content_type="application/xml; charset=utf-8")


@require_POST
def chat_message(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "JSON inválido."}, status=400)

    persona_id = (payload.get("persona") or "").strip()
    message = (payload.get("message") or "").strip()
    history = chatbot_service.normalize_history(payload.get("history"))

    if chatbot_service.get_persona(persona_id) is None:
        return JsonResponse({"ok": False, "error": "Assistente inválido."}, status=400)

    if not message:
        return JsonResponse({"ok": False, "error": "Escreva uma mensagem."}, status=400)

    if len(message) > chatbot_service.MAX_MESSAGE_LENGTH:
        return JsonResponse(
            {
                "ok": False,
                "error": f"Mensagem muito longa (máx. {chatbot_service.MAX_MESSAGE_LENGTH} caracteres).",
            },
            status=400,
        )

    if not chatbot_service.check_rate_limit(request.session):
        return JsonResponse(
            {
                "ok": False,
                "error": "Muitas mensagens neste momento. Tente novamente em alguns minutos.",
            },
            status=429,
        )

    try:
        reply = chatbot_service.generate_reply(persona_id, message, history)
    except chatbot_service.PromptInjectionError as exc:
        return JsonResponse({"ok": True, "reply": str(exc)})
    except RuntimeError as exc:
        logger.warning("Chat unavailable: %s", exc)
        return JsonResponse(
            {"ok": False, "error": "Chat temporariamente indisponível. Tente mais tarde."},
            status=503,
        )
    except Exception:
        logger.exception("Chat failed")
        return JsonResponse(
            {"ok": False, "error": "Não consegui responder agora. Tente de novo em instantes."},
            status=502,
        )

    return JsonResponse({"ok": True, "reply": reply})
