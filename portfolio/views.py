import csv
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from crm.models import Cliente, Mockup
from portfolio.models import Project


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


def mockup_public(request, slug):
    mockup = get_object_or_404(
        Mockup.objects.select_related("cliente").prefetch_related("imagens"),
        slug=slug,
        status=Mockup.Status.PUBLICADO,
    )
    return render(
        request,
        "portfolio/mockup_public.html",
        {"mockup": mockup, "site": SITE},
    )
