from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "titulo",
        "cliente",
        "status",
        "publicado",
        "ordem",
        "created_at",
    )
    list_filter = ("status", "publicado", "destaque")
    search_fields = ("titulo", "resumo", "stack", "cliente__empresa", "cliente__nome")
    list_editable = ("publicado", "ordem", "status")
    autocomplete_fields = ("cliente",)
