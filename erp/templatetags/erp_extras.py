from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def sort_link(context, field: str) -> str:
    request = context["request"]
    current = (request.GET.get("sort") or context.get("sort") or "").strip()
    query = request.GET.copy()
    if current == field:
        query["sort"] = f"-{field}"
    else:
        query["sort"] = field
    query.pop("page", None)
    encoded = query.urlencode()
    return f"?{encoded}" if encoded else f"?sort={field}"


@register.filter
def status_badge(value: str) -> str:
    return value or "default"
