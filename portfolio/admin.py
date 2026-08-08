from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("titulo", "destaque", "ordem", "created_at")
    list_filter = ("destaque",)
    search_fields = ("titulo", "resumo", "stack")
    list_editable = ("destaque", "ordem")
