from django import template

register = template.Library()


@register.filter
def cap_opcoes(valor: str) -> list[tuple[str, str]]:
    """'a:A,b:B' vira [('a', 'A'), ('b', 'B')]."""
    pares = []
    for item in valor.split(","):
        chave, _, rotulo = item.partition(":")
        pares.append((chave, rotulo))
    return pares
