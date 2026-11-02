"""Fotos de exemplo (Unsplash) que ocupam os espaços de imagem dos templates.

As imagens são carregadas direto do images.unsplash.com, como pede a API do
Unsplash, com o tamanho e o recorte pedidos na URL. Cada foto guarda o autor
para o crédito. Trocar uma foto é trocar o ``id`` aqui; os templates não mudam.
"""

BASE = "https://images.unsplash.com/{id}?ixlib=rb-4.1.0&auto=format&fit=crop&q=72&w={w}"
LARGURAS = (480, 800, 1200, 1600)


def _foto(id, alt, autor, perfil, larguras=LARGURAS):
    return {
        "src": BASE.format(id=id, w=larguras[-2]),
        "srcset": ", ".join(f"{BASE.format(id=id, w=w)} {w}w" for w in larguras),
        "alt": alt,
        "autor": autor,
        "perfil": f"https://unsplash.com/@{perfil}?utm_source=rebel_tech&utm_medium=referral",
    }


SALA_CLARA = _foto(
    "photo-1691036562132-56a310d4b789",
    "Poltrona diante de uma janela em arco, com luz natural",
    "Bilal Mansuri", "itsbilalmn",
)
JANELA = _foto(
    "photo-1617326302376-c576dc5aa525",
    "Banco branco na sombra desenhada pela janela",
    "Deconovo", "deconovo",
)
SALA_ESCURA = _foto(
    "photo-1541194577687-8c63bf9e7ee3",
    "Sala escura com sofá e luz quente vinda da janela",
    "Christian Lambert", "_christianlambert",
)
CAPA = _foto(
    "photo-1772989665252-7cb41ae759cc",
    "Retrato de mulher com sardas, pele natural",
    "Alexander Aguero", "alexcrphoto",
)
RETRATO = _foto(
    "photo-1667053508464-eb11b394df83",
    "Retrato de mulher em fundo escuro",
    "Dmitry Ganin", "ganinph",
)
PELE = _foto(
    "photo-1651149586345-ba723f576e5d",
    "Mulher com a mão no rosto, em tons suaves",
    "Quỳnh Lê Mạnh", "quynhlmph14759",
)
RECEPCAO = _foto(
    "photo-1759262151080-e05ba1c6294f",
    "Recepção de consultório com poltrona e luz natural",
    "Caroline Badran", "___atmos",
)

# Espaço "sobre" (página Sobre) vale para todo template que tem essa página.
PADRAO = {"sobre": RECEPCAO}

POR_TEMPLATE = {
    "consultorio": {"hero": SALA_CLARA, "sala": JANELA},
    "luxo": {"sala": SALA_ESCURA, "sobre": SALA_ESCURA},
    "revista": {"capa": CAPA},
    "retrato": {"retrato": RETRATO},
    "acolhedora": {"hero": PELE},
}


def fotos_do_template(slug: str) -> dict:
    return {**PADRAO, **POR_TEMPLATE.get(slug, {})}
