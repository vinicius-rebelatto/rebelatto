from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import F

from .models import Cobranca, FaixaDesconto, ItemProposta, Proposta

CENTAVO = Decimal("0.01")
GRUPOS = (Cobranca.UNICO, Cobranca.MENSAL, Cobranca.ANUAL)
CAMPO = {
    Cobranca.UNICO: "unico",
    Cobranca.MENSAL: "mensal",
    Cobranca.ANUAL: "anual",
}


def dinheiro(valor) -> Decimal:
    return Decimal(valor or 0).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def faixas():
    return list(FaixaDesconto.objects.order_by(F("valor_ate").asc(nulls_last=True), "ordem", "pk"))


def percentual_sugerido(valor) -> Decimal:
    valor = Decimal(valor or 0)
    lista = faixas()
    if not lista:
        return Decimal("0")
    for faixa in lista:
        if faixa.valor_ate is None or valor <= faixa.valor_ate:
            return faixa.percentual
    return lista[-1].percentual


def com_desconto(valor, percentual) -> Decimal:
    fator = Decimal("1") - Decimal(percentual or 0)
    return dinheiro(Decimal(valor or 0) * fator)


def pontos(percentual) -> Decimal:
    """0.05 → 5.00, para o campo da proposta."""
    return (Decimal(percentual or 0) * 100).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def fracao(pontos_percentuais) -> Decimal:
    if pontos_percentuais is None or pontos_percentuais == "":
        return Decimal("0")
    return (Decimal(pontos_percentuais) / 100).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def reais(valor) -> str:
    numero = dinheiro(valor)
    sinal = "-" if numero < 0 else ""
    inteiro, decimais = f"{abs(numero):.2f}".split(".")
    partes = []
    while inteiro:
        partes.append(inteiro[-3:])
        inteiro = inteiro[:-3]
    return f"{sinal}R$ {'.'.join(reversed(partes))},{decimais}"


def texto_faixas() -> str:
    lista = faixas()
    if not lista:
        return "Nenhuma faixa de desconto. A proposta sai pelo preço de tabela."
    partes = []
    for faixa in lista:
        pct = f"{pontos(faixa.percentual):f}".replace(".", ",").rstrip("0").rstrip(",")
        if faixa.valor_ate is None:
            partes.append(f"acima disso, {pct}%")
        else:
            partes.append(f"até {reais(faixa.valor_ate)}, {pct}%")
    return "Na proposta, " + "; ".join(partes) + ". Dá para trocar o percentual em cada proposta."


def montar(pacote, extras):
    """Escopo incluso, avulsos escolhidos e subtotais por cobrança."""
    incluso_ids = set()
    escopo = []
    for item in pacote.itens.select_related("servico").order_by("ordem", "id"):
        if item.incluso:
            incluso_ids.add(item.servico_id)
            escopo.append(item.servico)

    avulsos = []
    vistos = set()
    for extra in extras:
        if extra.id in incluso_ids or extra.id in vistos or not extra.ativo:
            continue
        vistos.add(extra.id)
        avulsos.append(extra)

    grupos = {cobranca: Decimal("0") for cobranca in GRUPOS}
    grupos[pacote.cobranca] += Decimal(pacote.preco)
    for extra in avulsos:
        grupos[extra.cobranca] += Decimal(extra.preco)
    return escopo, avulsos, grupos


def percentuais_de(grupos, fixo, informados) -> dict:
    saida = {}
    for cobranca, subtotal in grupos.items():
        if not subtotal:
            saida[cobranca] = Decimal("0")
            continue
        if fixo and informados.get(cobranca) is not None:
            saida[cobranca] = informados[cobranca]
        else:
            saida[cobranca] = percentual_sugerido(subtotal)
    return saida


def cotar(pacote, extras, fixo=False, informados=None):
    informados = informados or {}
    escopo, avulsos, grupos = montar(pacote, extras)
    descontos = percentuais_de(grupos, fixo, informados)
    totais = {
        cobranca: com_desconto(subtotal, descontos[cobranca])
        for cobranca, subtotal in grupos.items()
    }
    return {
        "escopo": escopo,
        "avulsos": avulsos,
        "grupos": grupos,
        "descontos": descontos,
        "totais": totais,
    }


@transaction.atomic
def gravar(proposta: Proposta, pacote, extras, fixo, informados, cliente, observacao, usuario) -> Proposta:
    conta = cotar(pacote, extras, fixo=fixo, informados=informados)
    proposta.cliente = cliente
    proposta.cliente_nome = cliente.display_name
    proposta.pacote = pacote
    proposta.pacote_nome = pacote.nome
    proposta.piso = pacote.piso
    proposta.observacao = observacao or ""
    proposta.desconto_fixo = bool(fixo)
    if usuario is not None and proposta.criado_por_id is None:
        proposta.criado_por = usuario
    for cobranca, nome in CAMPO.items():
        setattr(proposta, f"preco_{nome}", dinheiro(conta["grupos"][cobranca]))
        setattr(proposta, f"desconto_{nome}", conta["descontos"][cobranca])
        setattr(proposta, f"total_{nome}", conta["totais"][cobranca])
    proposta.save()

    proposta.itens.all().delete()
    ordem = 1
    ItemProposta.objects.create(
        proposta=proposta,
        nome=pacote.nome,
        tipo=ItemProposta.Tipo.PACOTE,
        cobranca=pacote.cobranca,
        preco=dinheiro(pacote.preco),
        preco_negociado=dinheiro(pacote.preco),
        desconto=conta["descontos"][pacote.cobranca],
        ordem=ordem,
    )
    for servico in conta["escopo"]:
        ordem += 1
        ItemProposta.objects.create(
            proposta=proposta,
            nome=servico.nome,
            tipo=ItemProposta.Tipo.ESCOPO,
            cobranca=servico.cobranca,
            preco=Decimal("0"),
            ordem=ordem,
        )
    for servico in conta["avulsos"]:
        ordem += 1
        ItemProposta.objects.create(
            proposta=proposta,
            nome=servico.nome,
            tipo=ItemProposta.Tipo.AVULSO,
            cobranca=servico.cobranca,
            preco=dinheiro(servico.preco),
            preco_negociado=dinheiro(servico.preco),
            desconto=conta["descontos"][servico.cobranca],
            ordem=ordem,
        )
    return proposta


def _pct_comum(valores) -> Decimal:
    if not valores:
        return Decimal("0")
    primeiro = valores[0]
    if all(valor == primeiro for valor in valores):
        return primeiro
    return Decimal("0")


@transaction.atomic
def gravar_linhas(proposta, pacote, escopo, linhas, cliente, observacao, usuario) -> Proposta:
    """Cada linha tem preço negociado e desconto próprios."""
    grupos = {cobranca: Decimal("0") for cobranca in GRUPOS}
    totais = {cobranca: Decimal("0") for cobranca in GRUPOS}
    percentuais = {cobranca: [] for cobranca in GRUPOS}
    for linha in linhas:
        cobranca = linha["cobranca"]
        grupos[cobranca] += Decimal(linha["tabela"])
        totais[cobranca] += com_desconto(linha["negociado"], linha["desconto"])
        percentuais[cobranca].append(linha["desconto"])

    proposta.cliente = cliente
    proposta.cliente_nome = cliente.display_name
    proposta.pacote = pacote
    proposta.pacote_nome = pacote.nome
    proposta.piso = pacote.piso
    proposta.observacao = observacao or ""
    proposta.desconto_fixo = any(
        linha["desconto"] != percentual_sugerido(linha["tabela"]) for linha in linhas
    )
    if usuario is not None and proposta.criado_por_id is None:
        proposta.criado_por = usuario
    for cobranca, nome in CAMPO.items():
        setattr(proposta, f"preco_{nome}", dinheiro(grupos[cobranca]))
        setattr(proposta, f"desconto_{nome}", _pct_comum(percentuais[cobranca]))
        setattr(proposta, f"total_{nome}", dinheiro(totais[cobranca]))
    proposta.save()

    proposta.itens.all().delete()
    ordem = 1
    for linha in linhas:
        if linha["tipo"] != ItemProposta.Tipo.PACOTE:
            continue
        ItemProposta.objects.create(
            proposta=proposta,
            nome=linha["nome"],
            tipo=ItemProposta.Tipo.PACOTE,
            cobranca=linha["cobranca"],
            preco=dinheiro(linha["tabela"]),
            preco_negociado=dinheiro(linha["negociado"]),
            desconto=linha["desconto"],
            ordem=ordem,
        )
        ordem += 1
        break
    for servico in escopo:
        ItemProposta.objects.create(
            proposta=proposta,
            nome=servico.nome,
            tipo=ItemProposta.Tipo.ESCOPO,
            cobranca=servico.cobranca,
            preco=Decimal("0"),
            ordem=ordem,
        )
        ordem += 1
    for linha in linhas:
        if linha["tipo"] == ItemProposta.Tipo.PACOTE:
            continue
        ItemProposta.objects.create(
            proposta=proposta,
            nome=linha["nome"],
            tipo=ItemProposta.Tipo.AVULSO,
            cobranca=linha["cobranca"],
            preco=dinheiro(linha["tabela"]),
            preco_negociado=dinheiro(linha["negociado"]),
            desconto=linha["desconto"],
            ordem=ordem,
        )
        ordem += 1
    return proposta
