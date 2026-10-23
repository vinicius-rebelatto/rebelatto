"""Lê o CSV do Google Maps e grava categoria, nota e dossiê."""

from __future__ import annotations

import ast
import json
import re
from collections import Counter
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from crm.models import Cliente
from crm.presenca import classificar_por_url, visitar_varios
from crm.qualificacao import CAMPOS_SALVAR, ROTULO, aplicar


def _celula(row: dict, *chaves: str) -> str:
    for chave in chaves:
        valor = (row.get(chave) or "").strip()
        if valor:
            return valor
    return ""


def _inteiro(valor: str) -> int | None:
    texto = (valor or "").strip()
    if re.fullmatch(r"\d+", texto):
        return int(texto)
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", texto):
        return int(texto.replace(".", ""))
    if re.fullmatch(r"\d{1,3}(,\d{3})+", texto):
        return int(texto.replace(",", ""))
    return None


def _nota_maps(valor: str) -> float | None:
    texto = (valor or "").strip().replace(",", ".")
    if not texto:
        return None
    try:
        nota = float(texto)
    except ValueError:
        return None
    if nota < 0 or nota > 5:
        return None
    return round(nota, 1)


def _booleano(valor: str) -> bool:
    return (valor or "").strip().lower() in {"true", "1", "yes", "sim"}


def _lista(valor: str) -> list:
    bruto = (valor or "").strip()
    if not bruto.startswith("["):
        return []
    try:
        dados = ast.literal_eval(bruto)
    except (ValueError, SyntaxError):
        try:
            dados = json.loads(bruto)
        except json.JSONDecodeError:
            return []
    return dados if isinstance(dados, list) else []


def _categoria(row: dict) -> str:
    nomes: list[str] = []
    principal = _celula(row, "categoryName")
    if principal:
        nomes.append(principal)
    extra = _celula(row, "categories")
    for item in _lista(extra):
        texto = str(item).strip()
        if texto and texto not in nomes:
            nomes.append(texto)
    if extra and not extra.startswith("[") and extra not in nomes:
        nomes.append(extra)
    return " · ".join(nomes)[:160]


def _email(row: dict) -> str:
    bruto = _celula(row, "emails", "email")
    if not bruto:
        return ""
    candidatos = [str(item) for item in _lista(bruto)] or re.split(r"[,;\s]+", bruto)
    for item in candidatos:
        item = item.strip()
        if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", item):
            return item[:254]
    return ""


def linha_apify(row: dict) -> dict | None:
    empresa = _celula(row, "title")
    if not empresa:
        return None
    nota = _nota_maps(_celula(row, "totalScore"))
    return {
        "empresa": empresa,
        "telefone": _celula(row, "phone", "phoneUnformatted"),
        "website": _celula(row, "website"),
        "maps_url": _celula(row, "url"),
        "categoria": _categoria(row),
        "rua": _celula(row, "street"),
        "cidade": _celula(row, "city"),
        "estado": _celula(row, "state"),
        "email": _email(row),
        "nota_maps": nota,
        "avaliacoes": _inteiro(_celula(row, "reviewsCount")),
        "imagens": _inteiro(_celula(row, "imagesCount")),
        "fechado_permanente": _booleano(_celula(row, "permanentlyClosed")),
        "fechado_temporario": _booleano(_celula(row, "temporarilyClosed")),
        # No CSV da Apify, claimThisBusiness verdadeiro significa perfil não reivindicado.
        "nao_reivindicado": _booleano(_celula(row, "claimThisBusiness")),
        "link_agendamento": _celula(row, "servicesLink")[:300],
    }


def _cliente_da_linha(linha: dict) -> Cliente:
    nota = linha.get("nota_maps")
    return Cliente(
        empresa=linha.get("empresa") or "",
        telefone=linha.get("telefone") or "",
        website=linha.get("website") or "",
        categoria=linha.get("categoria") or "",
        cidade=linha.get("cidade") or "",
        estado=linha.get("estado") or "",
        presenca=linha.get("presenca") or "",
        presenca_detalhe=linha.get("presenca_detalhe") or "",
        nota_maps=Decimal(str(nota)) if nota not in (None, "") else None,
        avaliacoes=linha.get("avaliacoes"),
        imagens=linha.get("imagens"),
        fechado_permanente=bool(linha.get("fechado_permanente")),
        fechado_temporario=bool(linha.get("fechado_temporario")),
        nao_reivindicado=bool(linha.get("nao_reivindicado")),
        link_agendamento=linha.get("link_agendamento") or "",
    )


def _copiar_resultado(linha: dict, cliente: Cliente) -> None:
    linha["presenca"] = cliente.presenca
    linha["presenca_detalhe"] = cliente.presenca_detalhe
    linha["categoria_lead"] = cliente.categoria_lead
    linha["categoria_label"] = ROTULO.get(cliente.categoria_lead, "")
    linha["nota"] = cliente.nota
    linha["motivo_nota"] = cliente.motivo_nota
    linha["dossie"] = cliente.dossie
    linha["ordem_fila"] = cliente.ordem_fila
    nota = linha.get("nota_maps")
    if isinstance(nota, float):
        linha["nota_maps"] = f"{nota:.1f}"
    elif nota is None:
        linha["nota_maps"] = ""


def _marcar_unidades(linhas: list[dict]) -> None:
    no_arquivo = Counter(
        linha["empresa"].casefold()
        for linha in linhas
        if linha.get("empresa") and not linha.get("duplicate")
    )
    existentes = Counter(
        nome.casefold()
        for nome in Cliente.objects.exclude(empresa="").values_list("empresa", flat=True)
    )
    for linha in linhas:
        chave = (linha.get("empresa") or "").casefold()
        linha["unidades"] = (no_arquivo[chave] + existentes[chave]) if chave else 1


def qualificar_linhas(linhas: list[dict], perfil, *, visitar: bool = True) -> tuple[list[dict], int]:
    pendentes: list[str] = []
    vistos: set[str] = set()
    for linha in linhas:
        if linha.get("duplicate"):
            continue
        achado = classificar_por_url(linha.get("website") or "")
        if achado is None:
            website = linha.get("website") or ""
            if website and website not in vistos:
                vistos.add(website)
                pendentes.append(website)
        else:
            linha["presenca"] = achado.categoria
            linha["presenca_detalhe"] = achado.detalhe
    visitas = visitar_varios(pendentes) if visitar and pendentes else {}
    for linha in linhas:
        if linha.get("duplicate"):
            linha["presenca"] = ""
            linha["presenca_detalhe"] = ""
            linha["categoria_lead"] = ""
            linha["categoria_label"] = ""
            linha["nota"] = 0
            linha["motivo_nota"] = "Duplicata"
            linha["dossie"] = ""
            linha["ordem_fila"] = 9
            if isinstance(linha.get("nota_maps"), float):
                linha["nota_maps"] = f"{linha['nota_maps']:.1f}"
            elif linha.get("nota_maps") is None:
                linha["nota_maps"] = ""
            continue
        if not linha.get("presenca"):
            visita = visitas.get(linha.get("website") or "")
            if visita is None:
                linha["presenca"] = "site_proprio"
                linha["presenca_detalhe"] = "não verificado" if linha.get("website") else ""
            else:
                linha["presenca"] = visita.categoria
                linha["presenca_detalhe"] = visita.detalhe
        cliente = _cliente_da_linha(linha)
        aplicar(cliente, perfil)
        _copiar_resultado(linha, cliente)
    _marcar_unidades(linhas)
    return linhas, len(pendentes)


def dados_novos(item: dict) -> dict:
    def corta(valor, limite: int) -> str:
        return (valor or "")[:limite]

    nota = item.get("nota_maps") or ""
    return {
        "empresa": corta(item.get("empresa"), 200),
        "email": corta(item.get("email"), 254),
        "telefone": corta(item.get("telefone"), 40),
        "website": corta(item.get("website"), 300),
        "maps_url": corta(item.get("maps_url"), 500),
        "categoria": corta(item.get("categoria"), 160),
        "rua": corta(item.get("rua"), 255),
        "cidade": corta(item.get("cidade"), 120),
        "estado": corta(item.get("estado"), 80),
        "nota_maps": Decimal(str(nota)) if nota else None,
        "avaliacoes": item.get("avaliacoes"),
        "imagens": item.get("imagens"),
        "fechado_permanente": bool(item.get("fechado_permanente")),
        "fechado_temporario": bool(item.get("fechado_temporario")),
        "nao_reivindicado": bool(item.get("nao_reivindicado")),
        "link_agendamento": corta(item.get("link_agendamento"), 300),
        "presenca": corta(item.get("presenca"), 32),
        "presenca_detalhe": corta(item.get("presenca_detalhe"), 160),
        "categoria_lead": corta(item.get("categoria_lead"), 32),
        "nota": int(item.get("nota") or 0),
        "motivo_nota": corta(item.get("motivo_nota"), 300),
        "dossie": item.get("dossie") or "",
        "ordem_fila": int(item.get("ordem_fila") if item.get("ordem_fila") is not None else 9),
    }


def recalcular_importados(perfil) -> tuple[int, int]:
    leads = list(Cliente.objects.filter(status=Cliente.Status.IMPORTADO))
    pendentes: list[str] = []
    vistos: set[str] = set()
    for lead in leads:
        if lead.presenca:
            continue
        achado = classificar_por_url(lead.website)
        if achado is None:
            if lead.website and lead.website not in vistos:
                vistos.add(lead.website)
                pendentes.append(lead.website)
        else:
            lead.presenca = achado.categoria
            lead.presenca_detalhe = achado.detalhe
    visitas = visitar_varios(pendentes) if pendentes else {}
    for lead in leads:
        if not lead.presenca:
            visita = visitas.get(lead.website)
            if visita is None:
                lead.presenca = "site_proprio"
                lead.presenca_detalhe = "não verificado" if lead.website else ""
            else:
                lead.presenca = visita.categoria
                lead.presenca_detalhe = visita.detalhe
        aplicar(lead, perfil)
        lead.updated_at = timezone.now()
    if leads:
        with transaction.atomic():
            Cliente.objects.bulk_update(leads, CAMPOS_SALVAR, batch_size=100)
    return len(leads), len(pendentes)
