from __future__ import annotations

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

from . import evolution, metricas, operacao, webhook
from .forms import ExperimentoForm, NumeroConfigForm, NumeroForm, RespostaForm, ResultadoForm, VarianteForm
from .models import Abordagem, Experimento, Mensagem, NumeroWhatsApp

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
                variante = vform.save(commit=False)
                variante.experimento = experimento
                variante.letra = letra
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
    try:
        with transaction.atomic():
            resultado = webhook.processar(payload)
    except Exception:  # o webhook não pode derrubar a Evolution com reenvios infinitos
        logger.exception("Falha ao processar webhook da Evolution")
        return JsonResponse({"ok": False}, status=200)
    return JsonResponse({"ok": True, "resultado": resultado})
