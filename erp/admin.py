from django.contrib import admin

from .models import Tarefa


@admin.register(Tarefa)
class TarefaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "status", "prioridade", "frente", "prazo", "concluida_em")
    list_filter = ("status", "prioridade", "frente")
    search_fields = ("titulo", "descricao")
