"""Teto mensal, alertas e a decisão de cair para o modelo reserva.

Os limiares avisam em 50%, 80% e 95%. A projeção avisa quando o ritmo do mês
estoura o teto antes do dia 30. Em 100%, o gateway troca para o reserva.
"""

from __future__ import annotations

import calendar
from datetime import datetime, time
from decimal import ROUND_CEILING, Decimal

from django.db.models import Q, Sum
from django.utils import timezone

from .models import Agente, Alerta, Execucao, Modelo, Orcamento

LIMIARES = (
    (Alerta.Nivel.P95, Decimal("95")),
    (Alerta.Nivel.P80, Decimal("80")),
    (Alerta.Nivel.P50, Decimal("50")),
)


def intervalo_mes(data=None) -> tuple[datetime, datetime]:
    data = data or timezone.localdate()
    inicio_dia = data.replace(day=1)
    if data.month == 12:
        proximo = data.replace(year=data.year + 1, month=1, day=1)
    else:
        proximo = data.replace(month=data.month + 1, day=1)
    tz = timezone.get_current_timezone()
    inicio = timezone.make_aware(datetime.combine(inicio_dia, time.min), tz)
    fim = timezone.make_aware(datetime.combine(proximo, time.min), tz)
    return inicio, fim


def periodo_atual(data=None) -> str:
    data = data or timezone.localdate()
    return f"{data.year:04d}-{data.month:02d}"


def gasto_de(orcamento: Orcamento, inicio: datetime | None = None, fim: datetime | None = None) -> Decimal:
    if inicio is None or fim is None:
        inicio, fim = intervalo_mes()
    consultas = Execucao.objects.filter(created_at__gte=inicio, created_at__lt=fim)
    if orcamento.escopo == Orcamento.Escopo.PROVEDOR:
        consultas = consultas.filter(modelo__provedor=orcamento.provedor)
    elif orcamento.escopo == Orcamento.Escopo.AGENTE:
        consultas = consultas.filter(agente=orcamento.agente)
    total = consultas.aggregate(total=Sum("custo_usd"))["total"] or Decimal("0")
    return Decimal(total)


def orcamentos_aplicaveis(agente: Agente, modelo: Modelo) -> list[Orcamento]:
    return list(
        Orcamento.objects.filter(ativo=True)
        .filter(
            Q(escopo=Orcamento.Escopo.GLOBAL)
            | Q(escopo=Orcamento.Escopo.PROVEDOR, provedor=modelo.provedor)
            | Q(escopo=Orcamento.Escopo.AGENTE, agente=agente)
        )
        .select_related("agente")
    )


def orcamentos_estourados(agente: Agente, modelo: Modelo) -> list[Orcamento]:
    estourados = []
    for orcamento in orcamentos_aplicaveis(agente, modelo):
        if orcamento.teto_usd > 0 and gasto_de(orcamento) >= orcamento.teto_usd:
            estourados.append(orcamento)
    return estourados


def atualizar_alertas(agente: Agente, modelo: Modelo | None = None) -> None:
    for orcamento in Orcamento.objects.filter(ativo=True).select_related("agente"):
        if orcamento.escopo == Orcamento.Escopo.PROVEDOR and (
            modelo is None or orcamento.provedor != modelo.provedor
        ):
            continue
        if orcamento.escopo == Orcamento.Escopo.AGENTE and orcamento.agente_id != agente.pk:
            continue
        sincronizar(orcamento)


def sincronizar_todos() -> None:
    for orcamento in Orcamento.objects.filter(ativo=True).select_related("agente"):
        sincronizar(orcamento)


def sincronizar(orcamento: Orcamento) -> None:
    """Cria ou atualiza os alertas do mês e dispensa os que deixaram de valer."""
    gasto = gasto_de(orcamento)
    teto = orcamento.teto_usd
    percentual = (gasto / teto * Decimal("100")) if teto else Decimal("0")
    periodo = periodo_atual()
    ativos: set[str] = set()
    nome = _nome(orcamento)

    if percentual >= 100:
        ativos.add(Alerta.Nivel.ESTOURO)
        _gravar(
            orcamento,
            Alerta.Nivel.ESTOURO,
            (
                f"O {nome} estourou: {_usd(gasto)} de {_usd(teto)}. "
                "As próximas chamadas usam o modelo reserva do agente, quando houver."
            ),
            periodo,
        )
    else:
        for nivel, limite in LIMIARES:
            if percentual >= limite:
                ativos.add(nivel)
                _gravar(
                    orcamento,
                    nivel,
                    f"O {nome} passou de {limite}% do teto: {_usd(gasto)} de {_usd(teto)}.",
                    periodo,
                )
        dia = _dia_da_projecao(gasto, teto)
        if dia is not None:
            ativos.add(Alerta.Nivel.PROJECAO)
            _gravar(
                orcamento,
                Alerta.Nivel.PROJECAO,
                f"No ritmo atual, o {nome} estoura no dia {dia}.",
                periodo,
                dia,
            )

    # Apaga o alerta que deixou de valer. O dispensado pelo usuário continua
    # oculto enquanto o mesmo limiar seguir valendo.
    Alerta.objects.filter(orcamento=orcamento, periodo=periodo).exclude(nivel__in=ativos).delete()


def _dia_da_projecao(gasto: Decimal, teto: Decimal) -> int | None:
    hoje = timezone.localdate()
    if gasto <= 0 or teto <= 0 or gasto >= teto:
        return None
    ritmo = gasto / Decimal(hoje.day)
    if ritmo <= 0:
        return None
    dia = int((teto / ritmo).to_integral_value(rounding=ROUND_CEILING))
    ultimo = calendar.monthrange(hoje.year, hoje.month)[1]
    if hoje.day < dia <= ultimo:
        return dia
    return None


def _gravar(
    orcamento: Orcamento,
    nivel: str,
    mensagem: str,
    periodo: str,
    dia: int | None = None,
) -> None:
    alerta, _criado = Alerta.objects.get_or_create(
        orcamento=orcamento,
        nivel=nivel,
        periodo=periodo,
        defaults={"mensagem": mensagem, "dia_previsto": dia},
    )
    if alerta.dispensado:
        return
    if alerta.mensagem != mensagem or alerta.dia_previsto != dia:
        alerta.mensagem = mensagem
        alerta.dia_previsto = dia
        alerta.save(update_fields=["mensagem", "dia_previsto"])


def _nome(orcamento: Orcamento) -> str:
    if orcamento.escopo == Orcamento.Escopo.GLOBAL:
        return "orçamento global"
    if orcamento.escopo == Orcamento.Escopo.PROVEDOR:
        return f"orçamento {orcamento.get_provedor_display()}"
    return f"orçamento do agente {orcamento.agente}"


def _usd(valor: Decimal) -> str:
    quantizado = (
        Decimal(valor).quantize(Decimal("0.01"))
        if abs(Decimal(valor)) >= Decimal("0.01")
        else Decimal(valor).quantize(Decimal("0.0001"))
    )
    return f"US$ {quantizado}".replace(".", ",")
