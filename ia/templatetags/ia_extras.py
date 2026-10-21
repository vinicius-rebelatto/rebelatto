from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def usd(value) -> str:
    """Price per 1M tokens: keeps at least 2 decimals, drops trailing zeros beyond that."""
    if value is None or value == "":
        return "—"
    texto = f"{Decimal(value).normalize():f}"
    inteiro, _, decimais = texto.partition(".")
    decimais = decimais.ljust(2, "0")
    return f"${inteiro},{decimais}"


@register.filter
def tokens(value) -> str:
    if not value:
        return "—"
    value = int(value)
    if value >= 1_000_000:
        return f"{value / 1_000_000:g}M".replace(".", ",")
    if value >= 1_000:
        return f"{value / 1_000:g}k".replace(".", ",")
    return str(value)
