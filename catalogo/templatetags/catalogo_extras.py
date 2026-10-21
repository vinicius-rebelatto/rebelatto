from django import template

from catalogo.preco import dinheiro, pontos

register = template.Library()


@register.filter
def brl(value) -> str:
    if value is None or value == "":
        return "—"
    numero = dinheiro(value)
    sinal = "-" if numero < 0 else ""
    texto = f"{abs(numero):.2f}"
    inteiro, decimais = texto.split(".")
    partes = []
    while inteiro:
        partes.append(inteiro[-3:])
        inteiro = inteiro[:-3]
    return f"{sinal}R$ {'.'.join(reversed(partes))},{decimais}"


@register.filter
def pontos_input(value) -> str:
    if value is None or value == "":
        return ""
    return f"{pontos(value):f}".replace(".", ",").rstrip("0").rstrip(",")


@register.filter
def pct(value) -> str:
    if value is None or value == "":
        return "—"
    texto = f"{pontos(value):f}".replace(".", ",").rstrip("0").rstrip(",")
    return f"{texto}%"
