"""Busca de leads no Google Maps pelo Apify: inicia, acompanha e importa.

Cada lugar passa pela mesma qualificação da importação por CSV e entra como
lead importado, com o JSON completo do Apify guardado em ``dados_maps``.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from . import apify
from .importacao import (
    dados_novos,
    duplicatas_no_lote,
    e_duplicata,
    linha_apify,
    qualificar_linhas,
    unique_cliente_slug,
)
from .models import BuscaLeads, Cliente, PerfilNicho
from .qualificacao import LEVA

INTERVALO_VERIFICACAO = 10  # segundos entre consultas ao Apify pela tela


def iniciar(busca: BuscaLeads) -> BuscaLeads:
    if not busca.pode_iniciar:
        return busca
    if not busca.termos_lista or not busca.local.strip():
        raise apify.ApifyError("Preencha pelo menos um termo e o local da busca.")
    execucao = apify.iniciar(busca.entrada())
    busca.run_id = str(execucao.get("id") or "")
    busca.dataset_id = str(execucao.get("defaultDatasetId") or "")
    if not busca.run_id:
        raise apify.ApifyError("O Apify não devolveu o ID da execução.")
    busca.status = BuscaLeads.Status.RODANDO
    busca.status_apify = str(execucao.get("status") or "")
    busca.iniciada_em = timezone.now()
    busca.verificada_em = timezone.now()
    busca.concluida_em = None
    busca.erro = ""
    busca.lugares = busca.novos = busca.duplicados = busca.na_leva = 0
    busca.custo_usd = None
    busca.save()
    return busca


def precisa_verificar(busca: BuscaLeads) -> bool:
    if busca.status != BuscaLeads.Status.RODANDO:
        return False
    if busca.verificada_em is None:
        return True
    return (timezone.now() - busca.verificada_em).total_seconds() >= INTERVALO_VERIFICACAO


def atualizar(busca_id: int) -> BuscaLeads:
    """Consulta a execução. Se terminou, importa os lugares uma única vez."""
    with transaction.atomic():
        busca = BuscaLeads.objects.select_for_update().get(pk=busca_id)
        if busca.status != BuscaLeads.Status.RODANDO:
            return busca
        execucao = apify.consultar(busca.run_id)
        busca.status_apify = str(execucao.get("status") or "")
        busca.verificada_em = timezone.now()
        busca.custo_usd = _decimal(execucao.get("usageTotalUsd"), "0.0001") or busca.custo_usd
        busca.dataset_id = str(execucao.get("defaultDatasetId") or busca.dataset_id)
        if busca.status_apify == apify.SUCESSO:
            importar(busca, apify.itens(busca.dataset_id))
            busca.status = BuscaLeads.Status.CONCLUIDA
            busca.concluida_em = timezone.now()
        elif busca.status_apify in apify.FALHAS:
            busca.status = BuscaLeads.Status.ERRO
            busca.erro = str(execucao.get("statusMessage") or f"Execução terminou como {busca.status_apify}.")
            busca.concluida_em = timezone.now()
        busca.save()
        return busca


def importar(busca: BuscaLeads, itens: list[dict]) -> dict:
    linhas: list[dict] = []
    for item in itens:
        linha = linha_apify(_como_linha(item))
        if linha is None:
            continue
        extras = extras_do_item(item)
        linha["extras"] = extras
        linha["duplicate"] = e_duplicata(
            linha["empresa"], linha["telefone"], linha["cidade"], extras["place_id"]
        )
        linhas.append(linha)
    _duplicados_por_lugar(linhas)
    duplicatas_no_lote(linhas)
    linhas, _ = qualificar_linhas(linhas, PerfilNicho.atual())

    novos = na_leva = duplicados = 0
    for linha in linhas:
        if linha.get("duplicate"):
            duplicados += 1
            continue
        Cliente.objects.create(
            slug=unique_cliente_slug(linha.get("empresa") or "cliente"),
            origem=Cliente.Origem.APIFY,
            status=Cliente.Status.IMPORTADO,
            busca=busca,
            **dados_novos(linha),
            **linha["extras"],
        )
        novos += 1
        if linha.get("categoria_lead") in LEVA:
            na_leva += 1

    busca.lugares = len(itens)
    busca.novos = novos
    busca.duplicados = duplicados
    busca.na_leva = na_leva
    return {"lugares": len(itens), "novos": novos, "duplicados": duplicados, "na_leva": na_leva}


def extras_do_item(item: dict) -> dict:
    local = item.get("location") if isinstance(item.get("location"), dict) else {}
    website = str(item.get("website") or "")
    horarios = item.get("openingHours")
    return {
        "place_id": str(item.get("placeId") or "")[:128],
        "bairro": str(item.get("neighborhood") or "")[:120],
        "cep": str(item.get("postalCode") or "")[:20],
        "latitude": _decimal(local.get("lat"), "0.000001"),
        "longitude": _decimal(local.get("lng"), "0.000001"),
        "descricao_maps": str(item.get("description") or ""),
        "faixa_preco": str(item.get("price") or "")[:40],
        "horarios": horarios if isinstance(horarios, list) else [],
        "instagram": _rede(item.get("instagrams"), website, "instagram.com"),
        "facebook": _rede(item.get("facebooks"), website, "facebook.com"),
        "anuncio": bool(item.get("isAdvertisement")),
        "dados_maps": item,
    }


def _como_linha(item: dict) -> dict:
    """Converte o item JSON no formato de texto que o CSV do Apify usa."""
    linha: dict[str, str] = {}
    for chave, valor in item.items():
        if valor is None:
            linha[chave] = ""
        elif isinstance(valor, bool):
            linha[chave] = "true" if valor else "false"
        elif isinstance(valor, (list, dict)):
            linha[chave] = json.dumps(valor, ensure_ascii=False)
        else:
            linha[chave] = str(valor)
    return linha


def _duplicados_por_lugar(linhas: list[dict]) -> None:
    vistos: set[str] = set()
    for linha in linhas:
        place_id = linha["extras"]["place_id"]
        if not place_id or linha.get("duplicate"):
            continue
        if place_id in vistos:
            linha["duplicate"] = True
        vistos.add(place_id)


def _rede(lista, website: str, dominio: str) -> str:
    if isinstance(lista, list):
        for url in lista:
            if isinstance(url, str) and url.strip():
                return url.strip()[:300]
    if dominio in website.lower():
        return website[:300]
    return ""


def _decimal(valor, casas: str) -> Decimal | None:
    if valor in (None, ""):
        return None
    try:
        return Decimal(str(valor)).quantize(Decimal(casas))
    except (InvalidOperation, ValueError):
        return None
