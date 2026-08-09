from django.contrib import admin

from .models import Cliente, Mockup, MockupImagem


class MockupImagemInline(admin.TabularInline):
    model = MockupImagem
    extra = 1


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "email",
        "telefone",
        "origem",
        "status",
        "etapa_rejeicao",
        "updated_at",
    )
    list_filter = ("status", "origem", "etapa_rejeicao", "cidade", "estado")
    search_fields = ("nome", "empresa", "email", "telefone", "cidade", "mensagem")
    prepopulated_fields = {"slug": ("empresa", "nome")}
    readonly_fields = ("created_at", "updated_at")


@admin.register(Mockup)
class MockupAdmin(admin.ModelAdmin):
    list_display = ("titulo", "cliente", "status", "slug", "updated_at")
    list_filter = ("status",)
    search_fields = ("titulo", "slug", "cliente__empresa", "cliente__nome")
    prepopulated_fields = {"slug": ("titulo",)}
    inlines = [MockupImagemInline]
    readonly_fields = ("created_at", "updated_at")
