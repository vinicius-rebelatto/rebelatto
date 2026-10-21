"""Telas do gateway: visão geral, agentes, execuções, orçamento e notas."""

from __future__ import annotations

import calendar
import json
import math
from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.db.models import Avg, Count, ProtectedError, Q, Sum
from django.db.models.functions import TruncDate
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from erp.mixins import ListingMixin
from erp.views import staff_required

from .agentes import garantir_chatbots, restaurar_versao, salvar_agente
from .forms import AgenteForm, OrcamentoForm, PlaygroundForm
from .gateway import GatewayError, executar
from .models import Agente, Alerta, Avaliacao, Execucao, Modelo, Orcamento, Provedor, VersaoAgente
from .orcamento import gasto_de, intervalo_mes, orcamentos_estourados, periodo_atual, sincronizar_todos

ORDEM_ALERTA = {
    Alerta.Nivel.ESTOURO: 0,
    Alerta.Nivel.P95: 1,
    Alerta.Nivel.P80: 2,
    Alerta.Nivel.PROJECAO: 3,
    Alerta.Nivel.P50: 4,
}


def _mes():
    inicio, fim = intervalo_mes()
    return inicio, fim, timezone.localdate()


def _inteiro(valor) -> int:
    return int(valor or 0)


def _decimal(valor) -> Decimal:
    return Decimal(valor or 0)


def _percentual(parte, total) -> int | None:
    if not total:
        return None
    return int((_decimal(parte) / _decimal(total) * Decimal("100")).quantize(Decimal("1")))


def _tom_percentual(percentual: int | None) -> str:
    if percentual is None:
        return ""
    if percentual >= 95:
        return "danger"
    if percentual >= 80:
        return "warning"
    return ""


def _modelos_playground(agente: Agente):
    ids = []
    versao = agente.versao_ativa
    if versao is not None:
        ids = [pk for pk in (versao.modelo_id, versao.modelo_reserva_id) if pk]
    return Modelo.objects.filter(Q(habilitado=True) | Q(pk__in=ids)).order_by("provedor", "model_id")


def _formulario_agente(request: HttpRequest, agente: Agente | None) -> AgenteForm:
    versao = agente.versao_ativa if agente else None
    initial = None
    incluir = []
    if agente is not None and versao is not None:
        incluir = [pk for pk in (versao.modelo_id, versao.modelo_reserva_id) if pk]
        if request.method == "GET":
            initial = {
                "nome": agente.nome,
                "responsabilidade": agente.responsabilidade,
                "ativo": agente.ativo,
                "prompt": versao.prompt,
                "temperatura": versao.temperatura,
                "max_tokens": versao.max_tokens,
                "modelo": versao.modelo_id,
                "modelo_reserva": versao.modelo_reserva_id,
            }
    elif agente is not None and request.method == "GET":
        initial = {
            "nome": agente.nome,
            "responsabilidade": agente.responsabilidade,
            "ativo": agente.ativo,
        }
    return AgenteForm(request.POST or None, initial=initial, agente=agente, incluir_ids=incluir)


# --- Visão geral ------------------------------------------------------------


@staff_required
def visao_geral(request: HttpRequest) -> HttpResponse:
    garantir_chatbots()
    sincronizar_todos()
    inicio, fim, hoje = _mes()
    execucoes = Execucao.objects.filter(created_at__gte=inicio, created_at__lt=fim)
    totais = execucoes.aggregate(
        custo=Sum("custo_usd"),
        chamadas=Count("id"),
        erros=Count("id", filter=Q(status=Execucao.Status.ERRO)),
        entrada=Sum("tokens_entrada"),
        saida=Sum("tokens_saida"),
        cache=Sum("tokens_cache_leitura"),
    )
    gasto = _decimal(totais["custo"])
    chamadas = _inteiro(totais["chamadas"])
    erros = _inteiro(totais["erros"])
    latencias = list(
        execucoes.filter(status=Execucao.Status.SUCESSO)
        .order_by("latencia_ms")
        .values_list("latencia_ms", flat=True)
    )
    latencia_media = int(sum(latencias) / len(latencias)) if latencias else None
    latencia_p95 = latencias[max(0, math.ceil(0.95 * len(latencias)) - 1)] if latencias else None

    dias_no_mes = calendar.monthrange(hoje.year, hoje.month)[1]
    projecao = (gasto / Decimal(hoje.day) * Decimal(dias_no_mes)) if gasto and hoje.day else None
    teto = Orcamento.objects.filter(escopo=Orcamento.Escopo.GLOBAL, ativo=True).first()
    percentual = _percentual(gasto, teto.teto_usd) if teto else None

    por_dia = {
        _como_data(linha["dia"]): _decimal(linha["custo"])
        for linha in execucoes.annotate(
            dia=TruncDate("created_at", tzinfo=timezone.get_current_timezone())
        )
        .values("dia")
        .annotate(custo=Sum("custo_usd"))
        if linha["dia"] is not None
    }
    maior = max(por_dia.values(), default=Decimal("0"))
    dias = []
    for numero in range(1, hoje.day + 1):
        custo = por_dia.get(hoje.replace(day=numero), Decimal("0"))
        altura = 0
        if custo and maior:
            altura = max(8, int(custo / maior * 100))
        dias.append({"rotulo": numero, "custo": custo, "altura": altura})

    alertas = sorted(
        Alerta.objects.filter(periodo=periodo_atual(), dispensado=False).select_related("orcamento"),
        key=lambda alerta: ORDEM_ALERTA.get(alerta.nivel, 9),
    )
    context = {
        "page_title": "Visão geral de IA",
        "alertas": alertas,
        "gasto": gasto,
        "teto": teto,
        "percentual": percentual,
        "tom_teto": _tom_percentual(percentual),
        "largura_teto": min(percentual or 0, 100),
        "projecao": projecao,
        "chamadas": chamadas,
        "erros": erros,
        "taxa_erro": _percentual(erros, chamadas),
        "latencia_media": latencia_media,
        "latencia_p95": latencia_p95,
        "tokens_entrada": _inteiro(totais["entrada"]),
        "tokens_saida": _inteiro(totais["saida"]),
        "tokens_cache": _inteiro(totais["cache"]),
        "dias": dias,
        "por_provedor": _por_provedor(execucoes),
        "por_modelo": _por_modelo(execucoes),
        "ranking": _ranking(inicio, fim),
    }
    return render(request, "ia/painel.html", context)


def _como_data(valor):
    if isinstance(valor, datetime):
        if timezone.is_aware(valor):
            return timezone.localtime(valor).date()
        return valor.date()
    return valor


def _por_provedor(execucoes):
    linhas = (
        execucoes.exclude(modelo__isnull=True)
        .values("modelo__provedor")
        .annotate(chamadas=Count("id"), custo=Sum("custo_usd"), erros=Count("id", filter=Q(status=Execucao.Status.ERRO)))
        .order_by("-custo")
    )
    rotulos = dict(Provedor.choices)
    return [
        {
            "nome": rotulos.get(linha["modelo__provedor"], linha["modelo__provedor"]),
            "chamadas": linha["chamadas"],
            "custo": _decimal(linha["custo"]),
            "erros": linha["erros"],
        }
        for linha in linhas
    ]


def _por_modelo(execucoes):
    linhas = (
        execucoes.exclude(modelo__isnull=True)
        .values("modelo_id", "modelo__nome", "modelo__model_id", "modelo__provedor")
        .annotate(
            chamadas=Count("id"),
            custo=Sum("custo_usd"),
            latencia=Avg("latencia_ms", filter=Q(status=Execucao.Status.SUCESSO)),
        )
        .order_by("-custo")
    )
    rotulos = dict(Provedor.choices)
    return [
        {
            "nome": linha["modelo__nome"] or linha["modelo__model_id"],
            "provedor": rotulos.get(linha["modelo__provedor"], ""),
            "chamadas": linha["chamadas"],
            "custo": _decimal(linha["custo"]),
            "latencia": int(linha["latencia"]) if linha["latencia"] is not None else None,
        }
        for linha in linhas
    ]


def _ranking(inicio, fim):
    filtro = Q(execucoes__created_at__gte=inicio, execucoes__created_at__lt=fim)
    linhas = Agente.objects.annotate(
        chamadas=Count("execucoes", filter=filtro),
        custo=Sum("execucoes__custo_usd", filter=filtro),
        erros=Count("execucoes", filter=filtro & Q(execucoes__status=Execucao.Status.ERRO)),
        positivas=Count(
            "execucoes__avaliacao",
            filter=filtro & Q(execucoes__avaliacao__nota=Avaliacao.Nota.POSITIVA),
        ),
        avaliadas=Count("execucoes__avaliacao", filter=filtro),
    ).order_by("-custo", "nome")
    ranking = []
    for agente in linhas:
        custo = _decimal(agente.custo)
        ranking.append(
            {
                "agente": agente,
                "chamadas": agente.chamadas,
                "custo": custo,
                "erros": agente.erros,
                "taxa_erro": _percentual(agente.erros, agente.chamadas),
                "positivas": agente.positivas,
                "avaliadas": agente.avaliadas,
                "custo_por_bom": (custo / agente.positivas) if agente.positivas else None,
            }
        )
    return ranking


@staff_required
@require_POST
def alerta_dispensar(request: HttpRequest, pk: int) -> HttpResponse:
    alerta = get_object_or_404(Alerta, pk=pk)
    alerta.dispensado = True
    alerta.save(update_fields=["dispensado"])
    return redirect("ia:painel")


# --- Agentes ----------------------------------------------------------------


@staff_required
def agente_list(request: HttpRequest) -> HttpResponse:
    garantir_chatbots()
    inicio, fim, _hoje = _mes()
    filtro = Q(execucoes__created_at__gte=inicio, execucoes__created_at__lt=fim)
    agentes = (
        Agente.objects.annotate(
            chamadas=Count("execucoes", filter=filtro),
            custo=Sum("execucoes__custo_usd", filter=filtro),
            erros=Count("execucoes", filter=filtro & Q(execucoes__status=Execucao.Status.ERRO)),
            positivas=Count(
                "execucoes__avaliacao",
                filter=filtro & Q(execucoes__avaliacao__nota=Avaliacao.Nota.POSITIVA),
            ),
        )
        .prefetch_related("versoes__modelo")
        .order_by("nome")
    )
    return render(
        request,
        "ia/agentes/list.html",
        {"page_title": "Agentes", "agentes": agentes},
    )


@staff_required
@require_http_methods(["GET", "POST"])
def agente_create(request: HttpRequest) -> HttpResponse:
    form = _formulario_agente(request, None)
    if request.method == "POST" and form.is_valid():
        agente = salvar_agente(form.cleaned_data)
        messages.success(request, f"Agente {agente.nome} criado.")
        return redirect("ia:agente_detail", pk=agente.pk)
    return render(request, "ia/agentes/form.html", {"page_title": "Novo agente", "form": form})


@staff_required
@require_http_methods(["GET", "POST"])
def agente_detail(request: HttpRequest, pk: int) -> HttpResponse:
    agente = get_object_or_404(Agente, pk=pk)
    form = _formulario_agente(request, agente)
    if request.method == "POST" and form.is_valid():
        salvar_agente(form.cleaned_data, agente)
        messages.success(request, "Agente atualizado.")
        return redirect("ia:agente_detail", pk=agente.pk)

    versao = agente.versao_ativa
    chave = f"ia_playground_{agente.pk}"
    resultados = request.session.pop(chave, None)
    if resultados is not None:
        request.session.modified = True
    estouro = bool(versao and versao.modelo_id and orcamentos_estourados(agente, versao.modelo))
    context = {
        "page_title": agente.nome,
        "agente": agente,
        "versao": versao,
        "form": form,
        "playground_form": PlaygroundForm(queryset=_modelos_playground(agente)),
        "resultados": resultados or [],
        "versoes": agente.versoes.select_related("modelo", "modelo_reserva"),
        "comparativo": _comparativo(agente),
        "recentes": agente.execucoes.select_related("modelo", "avaliacao")[:8],
        "estouro": estouro,
    }
    return render(request, "ia/agentes/detail.html", context)


def _comparativo(agente: Agente) -> list[dict]:
    linhas = (
        Execucao.objects.filter(agente=agente)
        .values("modelo_id", "modelo__nome", "modelo__model_id", "modelo__provedor")
        .annotate(
            chamadas=Count("id"),
            sucessos=Count("id", filter=Q(status=Execucao.Status.SUCESSO)),
            custo=Sum("custo_usd"),
            latencia=Avg("latencia_ms", filter=Q(status=Execucao.Status.SUCESSO)),
            positivas=Count("avaliacao", filter=Q(avaliacao__nota=Avaliacao.Nota.POSITIVA)),
            avaliadas=Count("avaliacao"),
        )
        .order_by("-chamadas")
    )
    rotulos = dict(Provedor.choices)
    comparativo = []
    for linha in linhas:
        custo = _decimal(linha["custo"])
        comparativo.append(
            {
                "nome": linha["modelo__nome"] or linha["modelo__model_id"] or "Modelo removido",
                "provedor": rotulos.get(linha["modelo__provedor"], ""),
                "chamadas": linha["chamadas"],
                "sucessos": linha["sucessos"],
                "custo": custo,
                "latencia": int(linha["latencia"]) if linha["latencia"] is not None else None,
                "positivas": linha["positivas"],
                "avaliadas": linha["avaliadas"],
                "custo_por_bom": (custo / linha["positivas"]) if linha["positivas"] else None,
            }
        )
    return comparativo


@staff_required
@require_POST
def agente_playground(request: HttpRequest, pk: int) -> HttpResponse:
    agente = get_object_or_404(Agente, pk=pk)
    form = PlaygroundForm(request.POST, queryset=_modelos_playground(agente))
    if not form.is_valid():
        messages.error(request, "Não deu para rodar o playground. " + " ".join(form.errors.get("modelos", [])))
        if form.errors.get("entrada"):
            messages.error(request, " ".join(form.errors["entrada"]))
        return redirect("ia:agente_detail", pk=agente.pk)
    if agente.versao_ativa is None:
        messages.error(request, "Este agente ainda não tem uma versão ativa.")
        return redirect("ia:agente_detail", pk=agente.pk)

    resultados = []
    for modelo in form.cleaned_data["modelos"]:
        try:
            resultado = executar(
                agente,
                [{"role": "user", "content": form.cleaned_data["entrada"]}],
                origem=Execucao.Origem.PLAYGROUND,
                modelo=modelo,
                fallback_erro=False,
                permitir_inativo=True,
            )
            execucao = resultado.execucao
            resultados.append(
                {
                    "pedido": str(modelo),
                    "usado": str(execucao.modelo or modelo),
                    "usou_reserva": resultado.usou_reserva,
                    "texto": resultado.texto,
                    "erro": "",
                    "custo": str(execucao.custo_usd),
                    "latencia": execucao.latencia_ms,
                    "execucao_id": execucao.pk,
                }
            )
        except GatewayError as exc:
            execucao = exc.execucao
            resultados.append(
                {
                    "pedido": str(modelo),
                    "usado": str(execucao.modelo) if execucao and execucao.modelo_id else str(modelo),
                    "usou_reserva": bool(execucao and execucao.usou_reserva),
                    "texto": "",
                    "erro": str(exc),
                    "custo": str(execucao.custo_usd) if execucao else "0",
                    "latencia": execucao.latencia_ms if execucao else 0,
                    "execucao_id": execucao.pk if execucao else None,
                }
            )
    request.session[f"ia_playground_{agente.pk}"] = resultados
    return redirect("ia:agente_detail", pk=agente.pk)


@staff_required
@require_POST
def agente_restaurar(request: HttpRequest, pk: int, versao_pk: int) -> HttpResponse:
    versao = get_object_or_404(VersaoAgente, pk=versao_pk, agente_id=pk)
    nova = restaurar_versao(versao)
    messages.success(request, f"Versão {versao.numero} restaurada como versão {nova.numero}.")
    return redirect("ia:agente_detail", pk=pk)


@staff_required
@require_POST
def agente_delete(request: HttpRequest, pk: int) -> HttpResponse:
    agente = get_object_or_404(Agente, pk=pk)
    if agente.sistema:
        messages.error(request, "Este agente faz parte do site e não pode ser excluído. Você pode desativá-lo.")
        return redirect("ia:agente_detail", pk=pk)
    try:
        agente.delete()
    except ProtectedError:
        messages.error(request, "Este agente já tem execuções e não pode ser excluído.")
        return redirect("ia:agente_detail", pk=pk)
    messages.success(request, f"Agente {agente.nome} excluído.")
    return redirect("ia:agente_list")


# --- Execuções --------------------------------------------------------------


class ExecucaoListing(ListingMixin):
    paginate_by = 30
    search_fields = ["saida", "erro", "referencia_id", "agente__nome"]
    filter_fields = ["agente", "status", "origem", "modelo"]
    sort_fields = {"created_at": "created_at", "custo_usd": "custo_usd", "latencia_ms": "latencia_ms"}
    default_sort = "-created_at"


@staff_required
def execucao_list(request: HttpRequest) -> HttpResponse:
    queryset = Execucao.objects.select_related("agente", "modelo", "avaliacao")
    context = {
        "page_title": "Execuções",
        "agentes": Agente.objects.order_by("nome"),
        "modelos": Modelo.objects.filter(Q(habilitado=True) | Q(execucoes__isnull=False)).distinct().order_by("provedor", "model_id"),
        "status_choices": Execucao.Status.choices,
        "origem_choices": Execucao.Origem.choices,
        **ExecucaoListing().get_listing_queryset(request, queryset),
    }
    return render(request, "ia/execucoes/list.html", context)


@staff_required
def execucao_detail(request: HttpRequest, pk: int) -> HttpResponse:
    execucao = get_object_or_404(
        Execucao.objects.select_related("agente", "modelo", "credencial", "versao", "avaliacao"),
        pk=pk,
    )
    return render(
        request,
        "ia/execucoes/detail.html",
        {
            "page_title": f"Execução {execucao.pk}",
            "execucao": execucao,
            "entrada": _entrada_legivel(execucao.entrada),
            "feedback": execucao.feedback,
        },
    )


def _entrada_legivel(entrada: str) -> str:
    if not entrada:
        return ""
    try:
        return json.dumps(json.loads(entrada), ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        return entrada


@staff_required
@require_POST
def execucao_avaliar(request: HttpRequest, pk: int) -> HttpResponse:
    execucao = get_object_or_404(Execucao, pk=pk)
    nota = (request.POST.get("nota") or "").strip()
    if nota not in Avaliacao.Nota.values:
        messages.error(request, "Escolha se a resposta foi boa ou ruim.")
        return redirect("ia:execucao_detail", pk=pk)
    comentario = (request.POST.get("comentario") or "").strip()[:2000]
    avaliacao, _criada = Avaliacao.objects.get_or_create(
        execucao=execucao,
        defaults={"nota": nota, "comentario": comentario if "comentario" in request.POST else ""},
    )
    avaliacao.nota = nota
    if "comentario" in request.POST:
        avaliacao.comentario = comentario
    avaliacao.save()
    messages.success(request, "Nota registrada.")
    proximo = request.POST.get("next")
    if proximo:
        from django.utils.http import url_has_allowed_host_and_scheme

        if url_has_allowed_host_and_scheme(proximo, allowed_hosts={request.get_host()}):
            return redirect(proximo)
    return redirect("ia:execucao_detail", pk=pk)


# --- Orçamento --------------------------------------------------------------


@staff_required
def orcamento_list(request: HttpRequest) -> HttpResponse:
    sincronizar_todos()
    linhas = []
    for orcamento in Orcamento.objects.select_related("agente"):
        gasto = gasto_de(orcamento)
        percentual = _percentual(gasto, orcamento.teto_usd)
        linhas.append(
            {
                "orcamento": orcamento,
                "gasto": gasto,
                "percentual": percentual,
                "tom": _tom_percentual(percentual),
                "largura": min(percentual or 0, 100),
            }
        )
    return render(
        request,
        "ia/orcamento/list.html",
        {
            "page_title": "Orçamento",
            "linhas": linhas,
            "tem_global": any(linha["orcamento"].escopo == Orcamento.Escopo.GLOBAL and linha["orcamento"].ativo for linha in linhas),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def orcamento_create(request: HttpRequest) -> HttpResponse:
    form = OrcamentoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Teto salvo. Os alertas passam a valer nas próximas chamadas.")
        return redirect("ia:orcamento_list")
    return render(request, "ia/orcamento/form.html", {"page_title": "Novo teto", "form": form})


@staff_required
@require_http_methods(["GET", "POST"])
def orcamento_edit(request: HttpRequest, pk: int) -> HttpResponse:
    orcamento = get_object_or_404(Orcamento, pk=pk)
    form = OrcamentoForm(request.POST or None, instance=orcamento)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Teto atualizado.")
        return redirect("ia:orcamento_list")
    return render(
        request,
        "ia/orcamento/form.html",
        {"page_title": str(orcamento), "form": form, "orcamento": orcamento},
    )


@staff_required
@require_POST
def orcamento_delete(request: HttpRequest, pk: int) -> HttpResponse:
    orcamento = get_object_or_404(Orcamento, pk=pk)
    orcamento.delete()
    messages.success(request, "Teto removido.")
    return redirect("ia:orcamento_list")
