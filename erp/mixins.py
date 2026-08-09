from django.core.paginator import Paginator
from django.db.models import Q


class ListingMixin:
    """Search, filter, sort and paginate querysets for ERP list views."""

    paginate_by = 25
    search_fields: list[str] = []
    filter_fields: list[str] = []
    sort_fields: dict[str, str] = {}
    default_sort: str = "-id"
    boolean_filters: set[str] = set()

    def get_listing_queryset(self, request, queryset):
        q = (request.GET.get("q") or "").strip()
        if q and self.search_fields:
            query = Q()
            for field in self.search_fields:
                query |= Q(**{f"{field}__icontains": q})
            queryset = queryset.filter(query)

        active_filters: dict[str, str] = {}
        for field in self.filter_fields:
            value = (request.GET.get(field) or "").strip()
            if not value:
                continue
            if field in self.boolean_filters:
                if value.lower() in {"1", "true", "sim"}:
                    queryset = queryset.filter(**{field: True})
                    active_filters[field] = "1"
                elif value.lower() in {"0", "false", "nao", "não"}:
                    queryset = queryset.filter(**{field: False})
                    active_filters[field] = "0"
                continue
            queryset = queryset.filter(**{field: value})
            active_filters[field] = value

        sort = (request.GET.get("sort") or self.default_sort).strip()
        descending = sort.startswith("-")
        sort_key = sort.lstrip("-")
        if sort_key in self.sort_fields:
            order_field = self.sort_fields[sort_key]
            queryset = queryset.order_by(f"-{order_field}" if descending else order_field)
        else:
            sort = self.default_sort
            queryset = queryset.order_by(self.default_sort)

        page_number = request.GET.get("page") or 1
        paginator = Paginator(queryset, self.paginate_by)
        page_obj = paginator.get_page(page_number)

        querydict = request.GET.copy()
        querydict.pop("page", None)

        return {
            "object_list": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "q": q,
            "sort": sort,
            "active_filters": active_filters,
            "query_string": querydict.urlencode(),
        }

    def sort_url(self, request, field: str) -> str:
        query = request.GET.copy()
        current = (query.get("sort") or self.default_sort).strip()
        if current == field:
            query["sort"] = f"-{field}"
        else:
            query["sort"] = field
        query.pop("page", None)
        return f"?{query.urlencode()}"
