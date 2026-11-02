"""Identidade do lead aplicada em cima de um template da biblioteca.

Código, sem modelo. A página só diz o que já está no lead: nome, cidade,
endereço e telefone vêm do Maps; logo e cor vêm do cadastro. A cor entra no
botão, no link e num detalhe. Ela nunca pinta o fundo.
"""

from __future__ import annotations

import re
from urllib.parse import quote

TINTA_CLARA = "#ffffff"
TINTA_ESCURA = "#14110f"


def _rgb(cor: str) -> tuple[float, float, float]:
    cor = cor.lstrip("#")
    return tuple(int(cor[i : i + 2], 16) / 255 for i in (0, 2, 4))


def _hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(max(0, min(1, c)) * 255):02x}" for c in rgb)


def _luminancia(cor: str) -> float:
    def canal(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (canal(c) for c in _rgb(cor))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a: str, b: str) -> float:
    la, lb = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _misturar(cor: str, alvo: str, passo: float) -> str:
    return _hex(tuple(c + (t - c) * passo for c, t in zip(_rgb(cor), _rgb(alvo))))


def ajustar(cor: str, contra: str, minimo: float) -> str:
    """Escurece ou clareia ``cor`` até ter ``minimo`` de contraste com ``contra``."""
    if contraste(cor, contra) >= minimo:
        return cor
    alvo = "#000000" if _luminancia(contra) > 0.18 else "#ffffff"
    for i in range(1, 21):
        tentativa = _misturar(cor, alvo, i / 20)
        if contraste(tentativa, contra) >= minimo:
            return tentativa
    return alvo


def cor_valida(cor: str) -> bool:
    return bool(re.fullmatch(r"#[0-9a-fA-F]{6}", cor or ""))


def paleta(cor: str, *, tema: str, fundo: str) -> dict:
    """Cores do botão e do detalhe a partir da cor do cliente.

    Claro: botão com texto branco, escurecido se a cor for clara demais.
    Escuro: botão com a tinta de maior contraste, clareado se sumir no fundo.
    """
    cor = cor.lower()
    if tema == "dark":
        botao = ajustar(cor, fundo, 3)
        tinta = (
            TINTA_ESCURA
            if contraste(botao, TINTA_ESCURA) >= contraste(botao, TINTA_CLARA)
            else TINTA_CLARA
        )
        detalhe = ajustar(cor, fundo, 4.5)
    else:
        botao = ajustar(cor, TINTA_CLARA, 4.5)
        tinta = TINTA_CLARA
        detalhe = ajustar(cor, fundo, 3)
    alvo_hover = "#000000" if tinta == TINTA_CLARA else "#ffffff"
    return {
        "botao": botao,
        "tinta": tinta,
        "hover": _misturar(botao, alvo_hover, 0.15),
        "detalhe": detalhe,
    }


def whatsapp_digitos(telefone: str) -> str:
    digitos = re.sub(r"\D", "", telefone or "")
    if not digitos:
        return ""
    if len(digitos) in (10, 11):
        digitos = "55" + digitos
    return digitos


def _uf(estado: str) -> str:
    estado = (estado or "").strip()
    return estado if len(estado) <= 3 else ""


def mapa_do_endereco(endereco: str, bairro: str, cidade: str, uf: str) -> dict | None:
    """Mapa do Google para o endereço do site: embed, rota e o texto do cartão.

    O complemento depois do travessão ("— sala 3") fica no cartão, mas sai da
    busca, que só precisa de rua, bairro e cidade.
    """
    endereco = (endereco or "").strip()
    cidade = (cidade or "").strip()
    if not endereco and not cidade:
        return None
    rua = endereco.split("—")[0].strip(" ,")
    local = f"{cidade} - {uf}" if cidade and uf else cidade
    busca = ", ".join(p for p in (rua, (bairro or "").strip(), local, "Brasil") if p)
    texto = ", ".join(p for p in (endereco, (bairro or "").strip()) if p)
    zoom = 16 if rua else 13
    return {
        "busca": busca,
        "texto": texto or local,
        "local": local,
        "embed": f"https://maps.google.com/maps?q={quote(busca)}&z={zoom}&hl=pt-BR&output=embed",
        "rota": f"https://www.google.com/maps/dir/?api=1&destination={quote(busca)}",
    }


def marca_demo(landing: dict) -> dict:
    demo = landing.get("demo") or {}
    return {
        "lead": False,
        "nome": demo.get("nome", ""),
        "cidade": demo.get("cidade", ""),
        "uf": demo.get("uf", ""),
        "endereco": demo.get("endereco", ""),
        "bairro": demo.get("bairro", ""),
        "telefone": demo.get("telefone", ""),
        "whatsapp_url": f"https://wa.me/{demo.get('whatsapp', '')}",
        "logo_url": "",
        "cores": None,
        "mapa": mapa_do_endereco(
            demo.get("endereco", ""), demo.get("bairro", ""), demo.get("cidade", ""), demo.get("uf", "")
        ),
    }


def marca_do_lead(cliente, landing: dict) -> dict:
    cores = None
    if cor_valida(cliente.cor_destaque):
        cores = paleta(
            cliente.cor_destaque,
            tema=landing.get("theme", "light"),
            fundo=landing.get("fundo", "#ffffff"),
        )
    digitos = whatsapp_digitos(cliente.telefone)
    return {
        "lead": True,
        "nome": cliente.display_name,
        "cidade": (cliente.cidade or "").strip(),
        "uf": _uf(cliente.estado),
        "endereco": (cliente.rua or "").strip(),
        "bairro": "",
        "telefone": (cliente.telefone or "").strip(),
        "whatsapp_url": f"https://wa.me/{digitos}" if digitos else "#visita",
        "logo_url": cliente.logo.url if cliente.logo else "",
        "cores": cores,
        "mapa": mapa_do_endereco(cliente.rua, "", cliente.cidade, _uf(cliente.estado)),
    }


def link_rebel_tech(site: dict, nome: str) -> str:
    texto = f"Olá! Vi a página de exemplo da {nome} e quero conversar sobre ela."
    return f"https://wa.me/{site['whatsapp']}?text={quote(texto)}"
