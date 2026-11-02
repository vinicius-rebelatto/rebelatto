"""Funil por script: da fila ao fechamento."""

from __future__ import annotations

from django.db.models import Count, Q

from .models import Abordagem, Variante

ETAPAS = [
    ("na_fila", "Na fila", Q(envio=Abordagem.Envio.NA_FILA)),
    ("enviadas", "Enviadas", Q(envio=Abordagem.Envio.ENVIADA)),
    ("entregues", "Entregues", Q(entregue_em__isnull=False)),
    ("lidas", "Lidas", Q(lida_em__isnull=False)),
    ("responderam", "Responderam", Q(respondeu_em__isnull=False)),
    ("reunioes", "Reunião marcada", Q(reuniao_marcada_em__isnull=False)),
    ("compareceram", "Compareceram", Q(compareceu=True)),
    ("faltaram", "Faltaram", Q(compareceu=False)),
    ("fecharam", "Fecharam", Q(resultado=Abordagem.Resultado.FECHOU)),
    ("em_validacao", "Em validação", Q(resultado=Abordagem.Resultado.EM_VALIDACAO)),
    ("perdidos", "Perdidos", Q(resultado=Abordagem.Resultado.PERDIDO)),
    ("opt_out", "Pediram para sair", Q(opt_out_em__isnull=False)),
    ("falharam", "Falharam", Q(envio=Abordagem.Envio.FALHOU)),
]

TAXAS = [
    ("Resposta", "responderam", "enviadas"),
    ("Resposta → reunião", "reunioes", "responderam"),
    ("Comparecimento", "compareceram", "reunioes"),
    ("Fechamento", "fecharam", "compareceram"),
    ("Reunião por envio", "reunioes", "enviadas"),
]


def _pct(parte: int, total: int) -> float | None:
    return (parte / total) if total else None


def funil(experimento) -> list[dict]:
    agregados = {nome: Count("abordagens", filter=_prefixar(filtro)) for nome, _, filtro in ETAPAS}
    linhas = []
    for variante in Variante.objects.filter(experimento=experimento).order_by("letra").annotate(**agregados):
        valores = {nome: getattr(variante, nome) for nome, _, _ in ETAPAS}
        taxas = [
            {"rotulo": rotulo, "valor": _pct(valores[a], valores[b]), "parte": valores[a], "total": valores[b]}
            for rotulo, a, b in TAXAS
        ]
        linhas.append({"variante": variante, "valores": valores, "taxas": taxas})
    return linhas


def _prefixar(filtro: Q) -> Q:
    """Q(campo=x) vira Q(abordagens__campo=x) para contar a partir da variante."""
    novo = Q()
    novo.connector = filtro.connector
    novo.negated = filtro.negated
    for filho in filtro.children:
        if isinstance(filho, Q):
            novo.children.append(_prefixar(filho))
        else:
            chave, valor = filho
            novo.children.append((f"abordagens__{chave}", valor))
    return novo


def tabela(linhas: list[dict]) -> dict:
    """O funil virado: uma linha por etapa, uma coluna por script."""
    return {
        "scripts": [linha["variante"] for linha in linhas],
        "etapas": [
            {"rotulo": rotulo, "valores": [linha["valores"][nome] for linha in linhas]}
            for nome, rotulo, _ in ETAPAS
        ],
        "taxas": [
            {
                "rotulo": rotulo,
                "valores": [
                    round(linha["taxas"][i]["valor"] * 100) if linha["taxas"][i]["valor"] is not None else None
                    for linha in linhas
                ],
            }
            for i, (rotulo, _, _) in enumerate(TAXAS)
        ],
    }
