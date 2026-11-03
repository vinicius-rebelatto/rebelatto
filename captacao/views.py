from __future__ import annotations

import csv
import json
import logging

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from erp.views import staff_required

from . import analise, evolution, metricas, operacao, webhook
from .forms import (
    ExperimentoForm,
    NumeroConfigForm,
    NumeroForm,
    RespostaForm,
    RespostaPadraoForm,
    ResultadoForm,
    VarianteForm,
)
from .models import Abordagem, EventoWhatsApp, Experimento, Mensagem, NumeroWhatsApp, RespostaPadrao, Variante

logger = logging.getLogger(__name__)

LETRAS = ["A", "B", "C"]
TEXTOS_EXEMPLO = {
    "A": "{Oi|Olá}, tudo bem? Vi a {{empresa}} no Google e montei uma prévia de como poderia ficar o site de vocês: {{mockup}}\nPosso te mostrar em 20 minutos como isso traria mais agendamentos?",
    "B": "{Oi|Olá}! A {{empresa}} tem nota {{nota_maps}} com {{avaliacoes}} avaliações no Google, mas quem procura vocês não encontra um site para agendar. Fiz uma prévia aqui: {{mockup}}\nFaz sentido conversarmos?",
    "C": "{Oi|Olá}, tudo bem? Quem cuida dos agendamentos online aí na {{empresa}}?",
}


# --- Painel -----------------------------------------------------------------


@staff_required
def painel(request: HttpRequest) -> HttpResponse:
    experimentos = list(Experimento.objects.all())
    atual = None
    if request.GET.get("experimento"):
        atual = next((e for e in experimentos if str(e.pk) == request.GET["experimento"]), None)
    atual = atual or next((e for e in experimentos if e.ativo), None) or (experimentos[0] if experimentos else None)
    numeros = []
    for numero in NumeroWhatsApp.objects.all():
        numeros.append({"numero": numero, "situacao": operacao.situacao(numero)})
    aguardando = (
        Abordagem.objects.filter(mensagens__sugestao_status__in=["pendente", "passar", "erro"])
        .distinct()
        .count()
    )
    return render(
        request,
        "captacao/painel.html",
        {
            "page_title": "Captação",
            "experimentos": experimentos,
            "experimento": atual,
            "tabela": metricas.tabela(metricas.funil(atual)) if atual else None,
            "numeros": numeros,
            "aguardando": aguardando,
            "na_fila": Abordagem.objects.filter(envio=Abordagem.Envio.NA_FILA).count(),
            "evolution_ok": evolution.configurada(),
        },
    )


# --- Números ----------------------------------------------------------------


@staff_required
@require_http_methods(["GET", "POST"])
def numero_create(request: HttpRequest) -> HttpResponse:
    form = NumeroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        numero = form.save()
        _conectar(request, numero, criar=True)
        return redirect("captacao:numero_detail", pk=numero.pk)
    return render(
        request,
        "captacao/numero_form.html",
        {"page_title": "Conectar número", "form": form, "evolution_ok": evolution.configurada()},
    )


def _conectar(request: HttpRequest, numero: NumeroWhatsApp, criar: bool = False) -> None:
    try:
        if criar:
            dados = evolution.criar_instancia(numero.instancia, numero.telefone)
            qr = dados.get("qrcode") if isinstance(dados, dict) else None
        else:
            evolution.configurar_webhook(numero.instancia)
            qr = evolution.conectar(numero.instancia)
    except evolution.EvolutionError as exc:
        numero.ultimo_erro = str(exc)
        numero.save(update_fields=["ultimo_erro", "updated_at"])
        messages.error(request, f"A Evolution API não respondeu como esperado: {exc}")
        return
    if isinstance(qr, dict):
        numero.qr_code = str(qr.get("base64") or numero.qr_code)
        numero.codigo_pareamento = str(qr.get("pairingCode") or "")[:20]
        numero.qr_atualizado_em = timezone.now()
    numero.ultimo_erro = ""
    if numero.conexao != NumeroWhatsApp.Conexao.CONECTADO:
        numero.conexao = NumeroWhatsApp.Conexao.PENDENTE
    numero.save()
    messages.success(request, "QR code gerado. Escaneie pelo WhatsApp Business do chip.")


@staff_required
@require_http_methods(["GET", "POST"])
def numero_detail(request: HttpRequest, pk: int) -> HttpResponse:
    numero = get_object_or_404(NumeroWhatsApp, pk=pk)
    if request.method == "POST":
        form = NumeroConfigForm(request.POST, instance=numero)
        if form.is_valid():
            numero = form.save(commit=False)
            if numero.envios_ativos and numero.inicio_aquecimento is None:
                numero.inicio_aquecimento = timezone.localdate()
            numero.save()
            messages.success(request, "Configuração salva.")
            return redirect("captacao:numero_detail", pk=numero.pk)
    else:
        form = NumeroConfigForm(instance=numero)
        if numero.conexao != NumeroWhatsApp.Conexao.CONECTADO and evolution.configurada():
            try:
                estado = evolution.estado(numero.instancia)
            except evolution.EvolutionError:
                estado = ""
            if estado == "open":
                numero.conexao = NumeroWhatsApp.Conexao.CONECTADO
                numero.conectado_em = timezone.now()
                numero.qr_code = ""
                numero.save()
    return render(
        request,
        "captacao/numero_detail.html",
        {
            "page_title": numero.apelido,
            "numero": numero,
            "form": form,
            "situacao": operacao.situacao(numero),
            "curva": _curva(numero),
        },
    )


def _curva(numero: NumeroWhatsApp) -> list[dict]:
    from .models import CURVA_AQUECIMENTO

    dia = numero.dia_aquecimento
    return [{"dia": i + 1, "limite": v, "hoje": i + 1 == dia} for i, v in enumerate(CURVA_AQUECIMENTO)]


@staff_required
@require_POST
def numero_conectar(request: HttpRequest, pk: int) -> HttpResponse:
    numero = get_object_or_404(NumeroWhatsApp, pk=pk)
    _conectar(request, numero, criar=False)
    return redirect("captacao:numero_detail", pk=numero.pk)


@staff_required
@require_POST
def numero_desconectar(request: HttpRequest, pk: int) -> HttpResponse:
    numero = get_object_or_404(NumeroWhatsApp, pk=pk)
    try:
        evolution.desconectar(numero.instancia)
    except evolution.EvolutionError as exc:
        messages.error(request, str(exc))
    numero.conexao = NumeroWhatsApp.Conexao.DESCONECTADO
    numero.envios_ativos = False
    numero.save()
    messages.success(request, "Número desconectado e envios desligados.")
    return redirect("captacao:numero_detail", pk=numero.pk)


@staff_required
def numero_status(request: HttpRequest, pk: int) -> JsonResponse:
    numero = get_object_or_404(NumeroWhatsApp, pk=pk)
    return JsonResponse(
        {
            "conexao": numero.conexao,
            "qr": numero.qr_code,
            "codigo": numero.codigo_pareamento,
        }
    )


# --- Experimentos -------------------------------------------------------------


def _form_variantes(request: HttpRequest, experimento: Experimento | None):
    formularios = []
    for letra in LETRAS:
        instancia = experimento.variantes.filter(letra=letra).first() if experimento else None
        inicial = {} if instancia else {"texto": TEXTOS_EXEMPLO[letra]}
        formularios.append(
            (letra, VarianteForm(request.POST or None, instance=instancia, prefix=letra.lower(), initial=inicial))
        )
    return formularios


@staff_required
@require_http_methods(["GET", "POST"])
def experimento_form(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    experimento = get_object_or_404(Experimento, pk=pk) if pk else None
    form = ExperimentoForm(request.POST or None, instance=experimento)
    variantes = _form_variantes(request, experimento)
    if request.method == "POST" and form.is_valid() and all(f.is_valid() for _, f in variantes):
        with transaction.atomic():
            experimento = form.save()
            for letra, vform in variantes:
                anterior = None
                if vform.instance.pk:
                    anterior = Variante.objects.filter(pk=vform.instance.pk).values("texto", "nome", "versao").first()
                variante = vform.save(commit=False)
                variante.experimento = experimento
                variante.letra = letra
                if anterior and anterior["texto"] != variante.texto:
                    variante.historico = [
                        *(variante.historico or []),
                        {**anterior, "trocado_em": timezone.now().isoformat()},
                    ]
                    variante.versao = anterior["versao"] + 1
                variante.save()
        messages.success(request, "Experimento salvo.")
        return redirect(f"{_url_painel()}?experimento={experimento.pk}")
    return render(
        request,
        "captacao/experimento_form.html",
        {
            "page_title": "Editar experimento" if experimento else "Novo experimento",
            "form": form,
            "variantes": variantes,
            "experimento": experimento,
        },
    )


def _url_painel() -> str:
    from django.urls import reverse

    return reverse("captacao:painel")


@staff_required
@require_POST
def experimento_fila(request: HttpRequest, pk: int) -> HttpResponse:
    experimento = get_object_or_404(Experimento, pk=pk)
    criadas = operacao.montar_fila(experimento)
    total = sum(criadas.values())
    if total:
        detalhe = ", ".join(f"{letra}: {n}" for letra, n in criadas.items())
        messages.success(request, f"{total} lead(s) entraram na fila ({detalhe}).")
    else:
        messages.warning(
            request,
            "Nenhum lead novo entrou. A fila puxa só leads em \"A prospectar\" das categorias escolhidas, "
            "com telefone, que ainda não foram abordados. Aceite leads na Filtragem primeiro.",
        )
    return redirect(f"{_url_painel()}?experimento={experimento.pk}")


# --- Conversas ----------------------------------------------------------------


@staff_required
def conversa_list(request: HttpRequest) -> HttpResponse:
    filtro = request.GET.get("f") or "responderam"
    qs = (
        Abordagem.objects.select_related("cliente", "variante", "numero")
        .annotate(ultima=Max("mensagens__created_at"), recebidas=Count("mensagens", filter=Q(mensagens__direcao="entrada")))
    )
    if filtro == "responderam":
        qs = qs.filter(respondeu_em__isnull=False)
    elif filtro == "aguardando":
        qs = qs.filter(mensagens__sugestao_status__in=["pendente", "passar", "erro"]).distinct()
    elif filtro == "reunioes":
        qs = qs.filter(reuniao_marcada_em__isnull=False)
    elif filtro == "fila":
        qs = qs.filter(envio=Abordagem.Envio.NA_FILA)
    elif filtro == "falhas":
        qs = qs.filter(envio=Abordagem.Envio.FALHOU)
    else:
        filtro = "todas"
    qs = qs.order_by("-ultima", "ordem")[:300]
    return render(
        request,
        "captacao/conversas.html",
        {"page_title": "Conversas", "abordagens": qs, "filtro": filtro},
    )


@staff_required
@require_http_methods(["GET", "POST"])
def conversa_detail(request: HttpRequest, pk: int) -> HttpResponse:
    abordagem = get_object_or_404(
        Abordagem.objects.select_related("cliente", "variante", "variante__experimento", "numero"), pk=pk
    )
    resultado_form = ResultadoForm(instance=abordagem)
    resposta_form = RespostaForm()
    if request.method == "POST":
        acao = request.POST.get("acao")
        if acao == "resultado":
            resultado_form = ResultadoForm(request.POST, instance=abordagem)
            if resultado_form.is_valid():
                abordagem = resultado_form.save(commit=False)
                if abordagem.reuniao_para and abordagem.reuniao_marcada_em is None:
                    abordagem.reuniao_marcada_em = timezone.now()
                if "resultado" in resultado_form.changed_data:
                    abordagem.resultado_em = timezone.now() if abordagem.resultado else None
                abordagem.save()
                messages.success(request, "Resultado salvo.")
                return redirect("captacao:conversa_detail", pk=abordagem.pk)
        elif acao in ("responder", "aprovar"):
            resposta_form = RespostaForm(request.POST)
            if resposta_form.is_valid():
                autor = Mensagem.Autor.IA if acao == "aprovar" else Mensagem.Autor.VOCE
                try:
                    operacao.enviar_resposta(abordagem, resposta_form.cleaned_data["texto"], autor=autor)
                except evolution.EvolutionError as exc:
                    messages.error(request, f"Não enviou: {exc}")
                else:
                    abordagem.mensagens.filter(sugestao_status__in=["pendente", "passar", "erro"]).update(
                        sugestao_status="respondida"
                    )
                    messages.success(request, "Mensagem enviada.")
                return redirect("captacao:conversa_detail", pk=abordagem.pk)
        elif acao == "descartar":
            abordagem.mensagens.filter(sugestao_status__in=["pendente", "passar", "erro"]).update(
                sugestao_status="descartada"
            )
            return redirect("captacao:conversa_detail", pk=abordagem.pk)
        elif acao == "opt_out":
            operacao.registrar_opt_out(abordagem.telefone, motivo="Marcado manualmente")
            messages.success(request, "Este número não recebe mais mensagens.")
            return redirect("captacao:conversa_detail", pk=abordagem.pk)
    sugestao = abordagem.mensagens.filter(sugestao_status__in=["pendente", "passar", "erro"]).order_by("-id").first()
    return render(
        request,
        "captacao/conversa.html",
        {
            "page_title": abordagem.cliente.display_name,
            "abordagem": abordagem,
            "mensagens": abordagem.mensagens.all(),
            "resultado_form": resultado_form,
            "resposta_form": resposta_form,
            "sugestao": sugestao,
            "visitas": abordagem.cliente.visitas_mockup.order_by("-created_at")[:20],
            "intencoes": analise.INTENCOES,
        },
    )


# --- Webhook da Evolution ---------------------------------------------------


@csrf_exempt
@require_POST
def webhook_evolution(request: HttpRequest, token: str) -> HttpResponse:
    if not constant_time_compare(token, evolution.token_webhook()):
        return HttpResponseForbidden("token inválido")
    try:
        payload = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"ok": False, "erro": "json inválido"}, status=400)
    evento = EventoWhatsApp.objects.create(
        instancia=str(payload.get("instance") or "")[:60] if isinstance(payload, dict) else "",
        evento=str(payload.get("event") or "")[:60] if isinstance(payload, dict) else "",
        payload=payload if isinstance(payload, (dict, list)) else {},
    )
    try:
        with transaction.atomic():
            resultado = webhook.processar(payload)
    except Exception:  # o webhook não pode derrubar a Evolution com reenvios infinitos
        logger.exception("Falha ao processar webhook da Evolution")
        EventoWhatsApp.objects.filter(pk=evento.pk).update(resultado="erro")
        return JsonResponse({"ok": False}, status=200)
    EventoWhatsApp.objects.filter(pk=evento.pk).update(resultado=str(resultado)[:60])
    return JsonResponse({"ok": True, "resultado": resultado})


# --- Insights, respostas padrão e exportação -------------------------------


@staff_required
def insights(request: HttpRequest) -> HttpResponse:
    experimento = None
    qs = Mensagem.objects.all()
    if request.GET.get("experimento"):
        experimento = Experimento.objects.filter(pk=request.GET["experimento"]).first()
        if experimento:
            qs = qs.filter(abordagem__variante__experimento=experimento)
    dados = analise.resumo(qs)
    letras = list(dados["temas_por_script"].keys())
    temas = [
        {"tema": tema, "total": total, "por_script": [dados["temas_por_script"][l].get(tema, 0) for l in letras]}
        for tema, total in dados["temas"]
    ]
    return render(
        request,
        "captacao/insights.html",
        {
            "page_title": "Perguntas e objeções",
            "dados": dados,
            "letras": letras,
            "temas": temas,
            "experimentos": Experimento.objects.all(),
            "experimento": experimento,
            "pendentes": Mensagem.objects.filter(direcao="entrada", classificada_em__isnull=True).exclude(texto="").count(),
            "padroes": RespostaPadrao.objects.all(),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def resposta_padrao_form(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    item = get_object_or_404(RespostaPadrao, pk=pk) if pk else None
    inicial = {"pergunta": request.GET.get("pergunta", "")} if item is None else None
    form = RespostaPadraoForm(request.POST or None, instance=item, initial=inicial)
    if request.method == "POST":
        if request.POST.get("excluir") and item:
            item.delete()
            messages.success(request, "Resposta padrão excluída.")
            return redirect("captacao:insights")
        if form.is_valid():
            form.save()
            messages.success(request, "Resposta padrão salva. O agente já usa nas próximas conversas.")
            return redirect("captacao:insights")
    return render(
        request,
        "captacao/resposta_padrao_form.html",
        {"page_title": "Resposta padrão", "form": form, "item": item},
    )


def _csv(nome: str, cabecalho: list[str], linhas) -> HttpResponse:
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = f'attachment; filename="{nome}"'
    resposta.write("\ufeff")
    escritor = csv.writer(resposta, delimiter=";")
    escritor.writerow(cabecalho)
    for linha in linhas:
        escritor.writerow(["" if v is None else v for v in linha])
    return resposta


def _data(valor):
    return timezone.localtime(valor).strftime("%Y-%m-%d %H:%M:%S") if valor else ""


@staff_required
def exportar_abordagens(request: HttpRequest) -> HttpResponse:
    cabecalho = [
        "abordagem_id", "experimento", "script", "versao_script", "lead_id", "empresa", "cidade", "bairro",
        "categoria_no_envio", "nota_no_envio", "nota_maps", "avaliacoes", "numero", "envio", "erro",
        "enviada_em", "entregue_em", "lida_em", "respondeu_em", "opt_out_em", "reuniao_marcada_em",
        "reuniao_para", "compareceu", "resultado", "resultado_em", "produto", "valor_fechado", "motivo_perda",
        "mensagens_do_lead", "visitas_mockup", "primeira_visita_mockup", "texto_enviado", "lead_no_envio_json",
    ]
    qs = (
        Abordagem.objects.select_related("variante__experimento", "cliente", "numero")
        .annotate(recebidas=Count("mensagens", filter=Q(mensagens__direcao="entrada")))
        .order_by("id")
    )

    def linhas():
        for a in qs.iterator():
            foto = a.lead_no_envio or {}
            visitas = a.cliente.visitas_mockup.order_by("created_at")
            primeira = visitas.first()
            yield [
                a.pk, a.variante.experimento.nome, a.variante.letra, a.versao_script, a.cliente_id,
                a.cliente.display_name, a.cliente.cidade, a.cliente.bairro,
                foto.get("categoria_lead", a.cliente.categoria_lead), foto.get("nota", a.cliente.nota),
                foto.get("nota_maps"), foto.get("avaliacoes"), a.numero.apelido if a.numero else "",
                a.envio, a.erro, _data(a.enviada_em), _data(a.entregue_em), _data(a.lida_em), _data(a.respondeu_em),
                _data(a.opt_out_em), _data(a.reuniao_marcada_em), _data(a.reuniao_para),
                "" if a.compareceu is None else ("sim" if a.compareceu else "nao"), a.resultado, _data(a.resultado_em),
                a.produto, a.valor_fechado, a.motivo_perda, a.recebidas, visitas.count(),
                _data(primeira.created_at) if primeira else "", a.texto_enviado,
                json.dumps(foto, ensure_ascii=False),
            ]

    return _csv("abordagens.csv", cabecalho, linhas())


@staff_required
def exportar_mensagens(request: HttpRequest) -> HttpResponse:
    cabecalho = [
        "mensagem_id", "abordagem_id", "empresa", "script", "direcao", "autor", "quando", "texto", "tipo", "status",
        "intencao", "temas", "pergunta", "objecao", "sugestao_ia", "sugestao_status",
    ]
    qs = Mensagem.objects.select_related("abordagem__cliente", "abordagem__variante").order_by("abordagem_id", "created_at", "id")

    def linhas():
        for m in qs.iterator():
            a = m.abordagem
            yield [
                m.pk, m.abordagem_id, a.cliente.display_name if a else "", a.variante.letra if a else "",
                m.direcao, m.autor, _data(m.created_at), m.texto, m.tipo, m.status, m.intencao,
                ",".join(m.temas or []), m.pergunta, m.objecao, m.sugestao, m.sugestao_status,
            ]

    return _csv("mensagens.csv", cabecalho, linhas())
