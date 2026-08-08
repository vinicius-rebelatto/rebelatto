from django.contrib import admin

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("nome", "email", "telefone", "origem", "status", "created_at")
    list_filter = ("status", "origem", "created_at")
    search_fields = ("nome", "email", "telefone", "mensagem")
    readonly_fields = ("created_at",)
