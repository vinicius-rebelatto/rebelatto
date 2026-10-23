from decimal import Decimal

from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify

from .preco import pontos

WHATSAPP = "(47) 99786-7428"
SITE = "rebelatto.tech"

ETAPAS = (
    ("01", "Alinhamento", "O objetivo e o que entra nesta entrega ficam combinados antes de produzir."),
    ("02", "Produção", "O combinado é produzido e mostrado para revisão antes de ir ao ar."),
    ("03", "Entrega", "Publicação ou ativação do que esta proposta descreve."),
)


class PdfIndisponivel(Exception):
    pass


def numero(proposta) -> str:
    return f"RT-{proposta.pk:04d}"


def nome_arquivo(proposta) -> str:
    cliente = slugify(proposta.cliente_nome) or "cliente"
    return f"Proposta-Rebel-Tech-{cliente}-{numero(proposta)}.pdf"


def _pct(valor) -> str:
    if not valor:
        return ""
    texto = f"{pontos(valor):f}".replace(".", ",").rstrip("0").rstrip(",")
    return f"{texto}%"


def contexto(proposta) -> dict:
    itens = list(proposta.itens.all())
    pacote = next((item for item in itens if item.tipo == "pacote"), None)
    escopo = [item for item in itens if item.tipo == "escopo"]
    avulsos = [item for item in itens if item.tipo == "avulso"]
    linhas = []
    if pacote is not None:
        linhas.append(_linha(pacote, proposta.piso))
    linhas.extend(_linha(item, False) for item in avulsos)

    grupos = []
    for chave, rotulo, sufixo in (
        ("unico", "Único", ""),
        ("mensal", "Mensal", "/mês"),
        ("anual", "Anual", "/ano"),
    ):
        preco = getattr(proposta, f"preco_{chave}")
        total = getattr(proposta, f"total_{chave}")
        if not preco and not total:
            continue
        economia = preco - total if total < preco else Decimal("0")
        grupos.append(
            {
                "rotulo": rotulo,
                "sufixo": sufixo,
                "preco": preco,
                "total": total,
                "pct": _pct(getattr(proposta, f"desconto_{chave}")),
                "economia": economia,
                "piso": proposta.piso and chave == "unico",
            }
        )
    economia = [grupo for grupo in grupos if grupo["economia"]]
    return {
        "proposta": proposta,
        "numero": numero(proposta),
        "resumo": proposta.pacote.resumo if proposta.pacote_id else "",
        "escopo": escopo,
        "avulsos": avulsos,
        "linhas": linhas,
        "grupos": grupos,
        "economia": economia,
        "etapas": ETAPAS,
        "whatsapp": WHATSAPP,
        "site": SITE,
        "ano": timezone.localtime(proposta.created_at).year,
    }


def _linha(item, piso: bool) -> dict:
    negociado = item.preco_negociado or item.preco
    return {
        "nome": item.nome,
        "cobranca": item.get_cobranca_display(),
        "tabela": item.preco,
        "final": item.valor_final,
        "pct": _pct(item.desconto),
        "riscado": negociado != item.preco or bool(item.desconto),
        "piso": piso,
    }


def render_html(proposta) -> str:
    return render_to_string("catalogo/proposta_pdf.html", contexto(proposta))


def gerar_pdf(proposta) -> bytes:
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as exc:
        raise PdfIndisponivel("O gerador de PDF não está disponível neste ambiente.") from exc
    return HTML(string=render_html(proposta), base_url="/").write_pdf()
