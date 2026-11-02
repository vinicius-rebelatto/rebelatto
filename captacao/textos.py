"""Telefones brasileiros e montagem do texto dos scripts."""

from __future__ import annotations

import random
import re
import unicodedata

from django.conf import settings

CAMPOS = ("empresa", "cidade", "bairro", "nota_maps", "avaliacoes", "mockup")
_CAMPO = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")
_VARIACAO = re.compile(r"\{([^{}]*\|[^{}]*)\}")


def so_digitos(valor: str) -> str:
    return re.sub(r"\D+", "", valor or "")


def telefone_whatsapp(valor: str) -> str:
    """Devolve 55 + DDD + número, ou vazio se não parecer um telefone brasileiro."""
    digitos = so_digitos(valor).lstrip("0")
    if digitos.startswith("55") and len(digitos) in (12, 13):
        return digitos
    if len(digitos) in (10, 11):
        return "55" + digitos
    return ""


def chave_telefone(valor: str) -> str:
    """DDD + últimos 8 dígitos. Casa números com e sem o nono dígito."""
    digitos = so_digitos(valor)
    if digitos.startswith("55") and len(digitos) in (12, 13):
        digitos = digitos[2:]
    if len(digitos) < 10:
        return digitos[-8:]
    return digitos[:2] + digitos[-8:]


def telefone_do_jid(jid: str) -> str:
    if not jid or "@" not in jid:
        return ""
    usuario, dominio = jid.split("@", 1)
    if dominio not in ("s.whatsapp.net", "c.us"):
        return ""
    return so_digitos(usuario.split(":", 1)[0])


def campos_do_cliente(cliente) -> dict[str, str]:
    nota = f"{cliente.nota_maps}".replace(".", ",") if cliente.nota_maps is not None else ""
    return {
        "empresa": (cliente.empresa or cliente.nome or "").strip(),
        "cidade": (cliente.cidade or "").strip(),
        "bairro": (cliente.bairro or "").strip(),
        "nota_maps": nota,
        "avaliacoes": str(cliente.avaliacoes or ""),
        "mockup": f"{settings.SITE_URL}{cliente.mockup_path}" if cliente.slug else "",
    }


def campos_desconhecidos(texto: str) -> list[str]:
    return sorted({nome for nome in _CAMPO.findall(texto or "") if nome not in CAMPOS})


def montar(texto: str, cliente, semente: int | None = None) -> str:
    """Troca os campos pelos dados do lead e sorteia uma opção de cada {a|b|c}."""
    sorteio = random.Random(semente)
    valores = campos_do_cliente(cliente)
    resultado = _CAMPO.sub(lambda m: valores.get(m.group(1), ""), texto or "")
    while True:
        novo = _VARIACAO.sub(lambda m: sorteio.choice(m.group(1).split("|")), resultado)
        if novo == resultado:
            break
        resultado = novo
    resultado = re.sub(r"[ \t]{2,}", " ", resultado)
    return resultado.strip()


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


_SAIR = re.compile(
    r"^(sair|pare|parar|stop|remover|remova|descadastrar|cancelar)\b"
    r"|\b(nao (me )?(mande|envie|mandem|envia|manda)|me (tira|tire|remova|remove)|nao quero (mais )?receber)\b"
)


def pediu_para_sair(texto: str) -> bool:
    return bool(_SAIR.search(normalizar(texto)))
