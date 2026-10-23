"""Nota e categoria do lead. A categoria escolhe a abordagem; a nota só ordena dentro dela."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

LEVA = ("sem_site", "rede_social", "site_fraco")
FORA = ("fora_nicho", "fechado", "sem_telefone")

ROTULO = {
    "sem_site": "Sem site",
    "rede_social": "Rede social",
    "site_fraco": "Site fraco",
    "site_proprio": "Site próprio",
    "fora_nicho": "Fora do nicho",
    "fechado": "Fechado",
    "sem_telefone": "Sem telefone",
}

ORDEM = {
    "sem_site": 0,
    "rede_social": 1,
    "site_fraco": 2,
    "site_proprio": 3,
    "fora_nicho": 4,
    "fechado": 5,
    "sem_telefone": 6,
}

OFERTA = {
    "sem_site": "Landing",
    "rede_social": "Landing — o site do perfil é uma rede social",
    "site_fraco": "Redesign ou landing nova",
    "site_proprio": "Guardado. Baixa prioridade para vender site.",
    "fora_nicho": "Não abordar nesta leva.",
    "fechado": "Não abordar.",
    "sem_telefone": "Não abordar.",
}

FATOS = {
    "domínio à venda": "O domínio informado está à venda.",
    "página vazia": "A página do domínio está vazia.",
    "em construção": "O site está em construção.",
    "não abriu": "O domínio não abriu na verificação.",
    "não verificado": "O domínio não foi verificado nesta leva.",
}

CAMPOS_SALVAR = [
    "presenca",
    "presenca_detalhe",
    "categoria_lead",
    "nota",
    "motivo_nota",
    "dossie",
    "ordem_fila",
    "updated_at",
]


@dataclass(frozen=True)
class Qualificacao:
    categoria: str
    nota: int
    motivo: str
    dossie: str
    ordem: int


def _sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFKD", (texto or "").casefold())
    return "".join(caractere for caractere in base if not unicodedata.combining(caractere))


def termos(texto: str) -> list[str]:
    saida: list[str] = []
    for linha in (texto or "").replace(",", "\n").splitlines():
        termo = _sem_acento(linha).strip()
        if len(termo.replace(" ", "")) >= 3:
            saida.append(termo)
    return saida


def _casa(termo: str, blob: str, tokens: set[str]) -> bool:
    if " " in termo:
        return termo in blob
    if len(termo) <= 4:
        return termo in tokens
    return termo in blob


def encaixe_nicho(categoria: str, termos_nicho: str, termos_vizinhos: str) -> str:
    blob = _sem_acento(categoria)
    tokens = set(re.findall(r"[a-z0-9]+", blob))
    if any(_casa(termo, blob, tokens) for termo in termos(termos_nicho)):
        return "nicho"
    if any(_casa(termo, blob, tokens) for termo in termos(termos_vizinhos)):
        return "vizinho"
    return "fora"


def tem_telefone(telefone: str) -> bool:
    return len(re.sub(r"\D", "", telefone or "")) >= 8


def _fmt_nota(valor: float | None) -> str:
    if valor is None:
        return ""
    return f"{valor:.1f}".replace(".", ",")


def _lugar(empresa: str, cidade: str, estado: str, categoria: str) -> str:
    lugar = cidade or ""
    if estado:
        lugar = f"{lugar}/{estado}" if lugar else estado
    return " · ".join(parte for parte in (empresa, lugar, categoria) if parte)


def _fato(presenca: str, detalhe: str) -> str:
    if detalhe in FATOS:
        return FATOS[detalhe]
    if presenca == "sem_site":
        return "Não há site no perfil do Google."
    if presenca == "rede_social":
        return f"O site apontado é {detalhe}." if detalhe else "O site apontado é uma rede social."
    if presenca == "site_fraco":
        if detalhe:
            return f"O site está em {detalhe}."
        return "O site está num construtor ou com pouco conteúdo."
    if detalhe == "WordPress":
        return "Há um site próprio em WordPress."
    return "Há um site próprio."


def _corte(categoria: str, motivo: str, empresa: str, cidade: str, estado: str, categoria_google: str) -> Qualificacao:
    dossie = "\n".join(
        parte
        for parte in (
            f"Oferta: {OFERTA[categoria]}",
            motivo + ".",
            _lugar(empresa, cidade, estado, categoria_google),
        )
        if parte
    )
    return Qualificacao(categoria, 0, motivo[:300], dossie, ORDEM[categoria])


def pontuar(
    perfil,
    *,
    encaixe: str,
    avaliacoes: int | None,
    nota_maps: float | None,
    imagens: int | None,
    nao_reivindicado: bool,
    tem_agendamento: bool,
    fechado_temporario: bool,
) -> int:
    pontos = 0
    if encaixe == "nicho":
        pontos += perfil.pontos_nicho
    elif encaixe == "vizinho":
        pontos += perfil.pontos_vizinho
    quantidade = avaliacoes or 0
    if 20 <= quantidade <= 400:
        pontos += perfil.pontos_avaliacoes_ideais
    elif 5 <= quantidade <= 19:
        pontos += perfil.pontos_avaliacoes_poucas
    elif quantidade > 400:
        pontos += perfil.pontos_avaliacoes_muitas
    if nota_maps is not None and nota_maps >= 4.2 and quantidade >= 15:
        pontos += perfil.pontos_nota_volume
    if nao_reivindicado:
        pontos += perfil.pontos_nao_reivindicado
    if imagens is not None and imagens < 5:
        pontos += perfil.pontos_poucas_imagens
    if tem_agendamento:
        pontos -= perfil.pontos_agendamento
    pontos = min(100, max(0, pontos))
    if fechado_temporario:
        pontos = int(round(pontos * perfil.fator_temporario / 100))
    return pontos


def calcular(
    perfil,
    *,
    telefone: str,
    categoria: str,
    presenca: str,
    presenca_detalhe: str,
    avaliacoes: int | None,
    nota_maps: float | None,
    imagens: int | None,
    fechado_permanente: bool,
    fechado_temporario: bool,
    nao_reivindicado: bool,
    tem_agendamento: bool,
    empresa: str,
    cidade: str,
    estado: str,
) -> Qualificacao:
    if presenca not in {"sem_site", "rede_social", "site_fraco", "site_proprio"}:
        presenca = "site_proprio"
    encaixe = encaixe_nicho(categoria, perfil.termos_nicho, perfil.termos_vizinhos)
    if not tem_telefone(telefone):
        return _corte("sem_telefone", "Sem telefone", empresa, cidade, estado, categoria)
    if fechado_permanente:
        return _corte("fechado", "Fechado em definitivo", empresa, cidade, estado, categoria)
    if encaixe == "fora":
        if categoria:
            motivo = f"Fora do nicho · {categoria}"
        else:
            motivo = "Fora do nicho · sem categoria no Maps"
        return _corte("fora_nicho", motivo, empresa, cidade, estado, categoria)

    nota = pontuar(
        perfil,
        encaixe=encaixe,
        avaliacoes=avaliacoes,
        nota_maps=nota_maps,
        imagens=imagens,
        nao_reivindicado=nao_reivindicado,
        tem_agendamento=tem_agendamento,
        fechado_temporario=fechado_temporario,
    )
    partes = [ROTULO[presenca]]
    if presenca_detalhe:
        partes.append(presenca_detalhe)
    if avaliacoes:
        partes.append(f"{avaliacoes} avaliações")
    nota_txt = _fmt_nota(nota_maps)
    if nota_txt:
        partes.append(f"nota {nota_txt}")
    if categoria:
        partes.append(categoria)
    if fechado_temporario:
        partes.append("fechado temporariamente")
    if cidade:
        partes.append(cidade)

    linhas = [f"Oferta: {OFERTA[presenca]}", _fato(presenca, presenca_detalhe)]
    if encaixe == "vizinho":
        linhas.append("Categoria vizinha do nicho.")
    if fechado_temporario:
        linhas.append("Fechada temporariamente. Prioridade baixa.")
    lugar = _lugar(empresa, cidade, estado, categoria)
    if lugar:
        linhas.append(lugar)
    sinais = []
    if avaliacoes:
        sinais.append(f"{avaliacoes} avaliações")
    if nota_txt:
        sinais.append(f"nota {nota_txt} no Maps")
    if sinais:
        linhas.append(" · ".join(sinais))
    if tem_agendamento:
        linhas.append("Já existe link de agendamento.")
    return Qualificacao(presenca, nota, " · ".join(partes)[:300], "\n".join(linhas), ORDEM[presenca])


def aplicar(cliente, perfil) -> None:
    nota_maps = cliente.nota_maps
    if nota_maps is not None:
        nota_maps = float(nota_maps)
    resultado = calcular(
        perfil,
        telefone=cliente.telefone,
        categoria=cliente.categoria,
        presenca=cliente.presenca,
        presenca_detalhe=cliente.presenca_detalhe,
        avaliacoes=cliente.avaliacoes,
        nota_maps=nota_maps,
        imagens=cliente.imagens,
        fechado_permanente=cliente.fechado_permanente,
        fechado_temporario=cliente.fechado_temporario,
        nao_reivindicado=cliente.nao_reivindicado,
        tem_agendamento=bool(cliente.link_agendamento),
        empresa=cliente.empresa,
        cidade=cliente.cidade,
        estado=cliente.estado,
    )
    cliente.categoria_lead = resultado.categoria
    cliente.nota = resultado.nota
    cliente.motivo_nota = resultado.motivo
    cliente.dossie = resultado.dossie
    cliente.ordem_fila = resultado.ordem
