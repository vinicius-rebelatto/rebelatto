from django.contrib import admin

from .models import FaixaDesconto, ItemPacote, Pacote, Proposta, Servico


class ItemInline(admin.TabularInline):
    model = ItemPacote
    extra = 0


@admin.register(Servico)
class ServicoAdmin(admin.ModelAdmin):
    list_display = ("nome", "preco", "cobranca", "complemento", "ativo")
    list_filter = ("cobranca", "complemento", "ativo")
    search_fields = ("nome",)


@admin.register(Pacote)
class PacoteAdmin(admin.ModelAdmin):
    list_display = ("nome", "preco", "cobranca", "piso", "ativo")
    inlines = [ItemInline]


@admin.register(FaixaDesconto)
class FaixaAdmin(admin.ModelAdmin):
    list_display = ("valor_ate", "percentual", "ordem")


@admin.register(Proposta)
class PropostaAdmin(admin.ModelAdmin):
    list_display = ("pacote_nome", "cliente_nome", "status", "total_unico", "created_at")
    list_filter = ("status",)
