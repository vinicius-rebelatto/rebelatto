"""Registry of interactive landing mockups (template-driven demos).

Cada template pertence a um nicho. O lead só passeia na biblioteca do nicho
dele, na ordem de ``ordem``. A primeira posição é o template que o link
enviado abre.
"""

LANDINGS = {
    "odontologia": {
        "template": "portfolio/mockups/odontologia.html",
        "css": "css/mockups/odontologia.css",
        "js": "js/mockups/landing.js",
        "theme": "light",
        "nicho": "odontologia",
        "nome": "Odontologia",
        "ordem": 1,
    },
    "consultorio": {
        "template": "portfolio/mockups/consultorio/inicio.html",
        "base": "portfolio/mockups/consultorio/base.html",
        "tipo": "institucional",
        "css": "css/mockups/consultorio.css",
        "js": "js/mockups/consultorio.js",
        "theme": "light",
        "nicho": "estetica",
        "nome": "Consultório",
        "vitrine": "Calmo e editorial: sala, método e visita, sem pressa.",
        "ordem": 1,
        "fundo": "#f3eee6",
        "acento": "#3f4a3c",
        "demo": {
            "nome": "Alva",
            "cidade": "Itajaí",
            "uf": "SC",
            "endereco": "Rua Hercílio Luz, 240 — sala 3",
            "bairro": "Centro",
            "telefone": "(47) 3268-0140",
            "whatsapp": "554732680140",
        },
    },
    "luxo": {
        "template": "portfolio/mockups/luxo/inicio.html",
        "base": "portfolio/mockups/luxo/base.html",
        "tipo": "institucional",
        "css": "css/mockups/luxo.css",
        "js": "js/mockups/luxo.js",
        "theme": "dark",
        "nicho": "estetica",
        "nome": "Luxo",
        "vitrine": "Escuro e silencioso, para quem atende poucos e bem.",
        "ordem": 2,
        "fundo": "#100e0c",
        "acento": "#d4c4a8",
        "demo": {
            "nome": "Ónix",
            "cidade": "Balneário Camboriú",
            "uf": "SC",
            "endereco": "Avenida Atlântica, 1500 — sala 12",
            "bairro": "Centro",
            "telefone": "(47) 3363-0190",
            "whatsapp": "554733630190",
        },
    },
    "harmonizacao": {
        "template": "portfolio/mockups/harmonizacao.html",
        "tipo": "landing",
        "css": "css/mockups/harmonizacao.css",
        "js": "js/mockups/harmonizacao.js",
        "theme": "light",
        "nicho": "estetica",
        "nome": "Harmonização",
        "vitrine": "Um procedimento só, contado do mapa do rosto à aplicação.",
        "ordem": 3,
        "fundo": "#f3ece8",
        "acento": "#8d4554",
        "demo": {
            "nome": "Nara",
            "cidade": "Joinville",
            "uf": "SC",
            "endereco": "Rua Nove de Março, 140 — sala 5",
            "bairro": "Centro",
            "telefone": "(47) 3422-0188",
            "whatsapp": "554734220188",
        },
    },
    "agenda": {
        "template": "portfolio/mockups/agenda.html",
        "tipo": "landing",
        "css": "css/mockups/agenda.css",
        "js": "js/mockups/estetica.js",
        "theme": "light",
        "nicho": "estetica",
        "nome": "Agenda",
        "vitrine": "O WhatsApp na frente: a avaliação marcada em duas mensagens.",
        "ordem": 4,
        "fundo": "#f7f4ee",
        "acento": "#1f5c56",
        "demo": {
            "nome": "Lis",
            "cidade": "Florianópolis",
            "uf": "SC",
            "endereco": "Rua Bocaiúva, 2125 — sala 204",
            "bairro": "Centro",
            "telefone": "(48) 3024-7716",
            "whatsapp": "554830247716",
        },
    },
    "cartao": {
        "template": "portfolio/mockups/cartao.html",
        "tipo": "landing",
        "css": "css/mockups/cartao.css",
        "js": "js/mockups/estetica.js",
        "theme": "light",
        "nicho": "estetica",
        "nome": "Cartão",
        "vitrine": "Um cartão de visita, frente e verso, que cabe em uma tela.",
        "ordem": 5,
        "fundo": "#ddd3c6",
        "acento": "#6e3328",
        "demo": {
            "nome": "Íris",
            "cidade": "Brusque",
            "uf": "SC",
            "endereco": "Rua Felipe Schmidt, 310 — sala 2",
            "bairro": "Centro",
            "telefone": "(47) 3351-0427",
            "whatsapp": "554733510427",
        },
    },
    "revista": {
        "template": "portfolio/mockups/revista/inicio.html",
        "base": "portfolio/mockups/revista/base.html",
        "tipo": "institucional",
        "css": "css/mockups/revista.css",
        "js": "js/mockups/estetica.js",
        "theme": "light",
        "nicho": "estetica",
        "nome": "Revista",
        "vitrine": "Capa, matéria e índice, como uma edição de revista.",
        "ordem": 6,
        "fundo": "#f5f2ec",
        "acento": "#9b3426",
        "demo": {
            "nome": "Aurea",
            "cidade": "Chapecó",
            "uf": "SC",
            "endereco": "Avenida Getúlio Vargas, 860 — sala 31",
            "bairro": "Centro",
            "telefone": "(49) 3322-1840",
            "whatsapp": "554933221840",
        },
    },
    "retrato": {
        "template": "portfolio/mockups/retrato/inicio.html",
        "base": "portfolio/mockups/retrato/base.html",
        "tipo": "simples",
        "css": "css/mockups/retrato.css",
        "js": "js/mockups/estetica.js",
        "theme": "dark",
        "nicho": "estetica",
        "nome": "Retrato",
        "vitrine": "Pensado primeiro para o celular, em tom escuro e elegante.",
        "ordem": 7,
        "fundo": "#1b1416",
        "acento": "#e2b2a0",
        "demo": {
            "nome": "Vela",
            "cidade": "Criciúma",
            "uf": "SC",
            "endereco": "Rua Henrique Lage, 455 — sala 7",
            "bairro": "Centro",
            "telefone": "(48) 3433-2091",
            "whatsapp": "554834332091",
        },
    },
    "minima": {
        "template": "portfolio/mockups/minima/inicio.html",
        "base": "portfolio/mockups/minima/base.html",
        "tipo": "simples",
        "css": "css/mockups/minima.css",
        "js": "js/mockups/estetica.js",
        "theme": "light",
        "nicho": "estetica",
        "nome": "Mínima",
        "vitrine": "Nome, uma frase e um botão. O essencial e nada mais.",
        "ordem": 8,
        "fundo": "#f0eee9",
        "acento": "#141414",
        "demo": {
            "nome": "Lume",
            "cidade": "Jaraguá do Sul",
            "uf": "SC",
            "endereco": "Rua Reinoldo Rau, 210 — sala 4",
            "bairro": "Centro",
            "telefone": "(47) 3371-5530",
            "whatsapp": "554733715530",
        },
    },
    "acolhedora": {
        "template": "portfolio/mockups/acolhedora/inicio.html",
        "base": "portfolio/mockups/acolhedora/base.html",
        "tipo": "simples",
        "css": "css/mockups/acolhedora.css",
        "js": "js/mockups/estetica.js",
        "theme": "light",
        "nicho": "estetica",
        "nome": "Acolhedora",
        "vitrine": "Formas redondas e tom quente, para receber bem.",
        "ordem": 9,
        "fundo": "#fbf2ea",
        "acento": "#a24e3a",
        "demo": {
            "nome": "Brisa",
            "cidade": "Palhoça",
            "uf": "SC",
            "endereco": "Rua José Maria da Luz, 1180",
            "bairro": "Centro",
            "telefone": "(48) 3242-6618",
            "whatsapp": "554832426618",
        },
    },
    "clinica": {
        "template": "portfolio/mockups/clinica/inicio.html",
        "base": "portfolio/mockups/clinica/base.html",
        "tipo": "institucional",
        "css": "css/mockups/clinica.css",
        "js": "js/mockups/estetica.js",
        "theme": "light",
        "nicho": "estetica",
        "nome": "Clínica",
        "vitrine": "Objetivo e completo: sobre, serviços, comparativo e mapa.",
        "ordem": 10,
        "fundo": "#ffffff",
        "acento": "#0f6e7a",
        "demo": {
            "nome": "Clínica Vértice",
            "cidade": "São José",
            "uf": "SC",
            "endereco": "Rua Koesa, 430 — 3º andar",
            "bairro": "Kobrasol",
            "telefone": "(48) 3259-4402",
            "whatsapp": "554832594402",
        },
    },
}

NICHO_PADRAO = "estetica"

PAGINAS = {
    "institucional": ("sobre", "servicos", "servico", "contato"),
    "simples": ("servicos", "servico", "contato"),
    "landing": (),
}


def paginas_do_tipo(tipo: str | None) -> tuple:
    return PAGINAS.get(tipo or "landing", ())


TIPO_ROTULO = {
    "landing": "Página única",
    "simples": "Site enxuto",
    "institucional": "Site completo",
}


def biblioteca_do_nicho(nicho: str = NICHO_PADRAO) -> list[dict]:
    """Templates do nicho, em ordem, com o slug dentro de cada item."""
    itens = [
        {"slug": slug, **dados}
        for slug, dados in LANDINGS.items()
        if dados.get("nicho") == nicho
    ]
    return sorted(itens, key=lambda item: item["ordem"])


def biblioteca_publica(nicho: str = NICHO_PADRAO) -> list[dict]:
    """Templates do nicho que estão publicados, na ordem da vitrine.

    É a lista que o visitante percorre com as setas em /mockups/<slug>/ e a
    que aparece na seção Vitrine da home.
    """
    from crm.models import Mockup

    publicados = set(
        Mockup.objects.filter(
            tipo=Mockup.Tipo.LANDING, status=Mockup.Status.PUBLICADO
        ).values_list("slug", flat=True)
    )
    return [
        {**item, "tipo_rotulo": TIPO_ROTULO.get(item.get("tipo") or "landing", "")}
        for item in biblioteca_do_nicho(nicho)
        if item["slug"] in publicados
    ]
