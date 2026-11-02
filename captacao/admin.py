from django.contrib import admin

from .models import Abordagem, Experimento, Mensagem, NumeroWhatsApp, OptOut, Variante


class VarianteInline(admin.StackedInline):
    model = Variante
    extra = 0


@admin.register(Experimento)
class ExperimentoAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo", "leads_por_variante", "modo_ia", "created_at")
    inlines = [VarianteInline]


@admin.register(NumeroWhatsApp)
class NumeroAdmin(admin.ModelAdmin):
    list_display = ("apelido", "telefone", "instancia", "conexao", "envios_ativos", "inicio_aquecimento")
    exclude = ("qr_code",)


@admin.register(Abordagem)
class AbordagemAdmin(admin.ModelAdmin):
    list_display = ("cliente", "variante", "envio", "enviada_em", "respondeu_em", "reuniao_marcada_em", "resultado")
    list_filter = ("envio", "variante__experimento", "variante__letra", "resultado")
    search_fields = ("cliente__empresa", "telefone")
    raw_id_fields = ("cliente",)


@admin.register(Mensagem)
class MensagemAdmin(admin.ModelAdmin):
    list_display = ("abordagem", "direcao", "autor", "texto", "status", "created_at")
    list_filter = ("direcao", "autor")
    raw_id_fields = ("abordagem",)


@admin.register(OptOut)
class OptOutAdmin(admin.ModelAdmin):
    list_display = ("telefone", "motivo", "created_at")
