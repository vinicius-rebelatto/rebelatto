from django.urls import path

from . import painel, views

app_name = "ia"

urlpatterns = [
    path("", painel.visao_geral, name="painel"),
    path("chaves/", views.credencial_list, name="credencial_list"),
    path("chaves/nova/", views.credencial_create, name="credencial_create"),
    path("chaves/<int:pk>/", views.credencial_detail, name="credencial_detail"),
    path("chaves/<int:pk>/testar/", views.credencial_test, name="credencial_test"),
    path("chaves/<int:pk>/excluir/", views.credencial_delete, name="credencial_delete"),
    path("modelos/", views.modelo_list, name="modelo_list"),
    path("modelos/atualizar-precos/", views.modelos_atualizar_precos, name="modelos_atualizar_precos"),
    path("modelos/<int:pk>/", views.modelo_edit, name="modelo_edit"),
    path("modelos/<int:pk>/alternar/", views.modelo_toggle, name="modelo_toggle"),
    path("modelos/<int:pk>/restaurar-preco/", views.modelo_reset_preco, name="modelo_reset_preco"),
    path("agentes/", painel.agente_list, name="agente_list"),
    path("agentes/novo/", painel.agente_create, name="agente_create"),
    path("agentes/<int:pk>/", painel.agente_detail, name="agente_detail"),
    path("agentes/<int:pk>/playground/", painel.agente_playground, name="agente_playground"),
    path("agentes/<int:pk>/versoes/<int:versao_pk>/restaurar/", painel.agente_restaurar, name="agente_restaurar"),
    path("agentes/<int:pk>/excluir/", painel.agente_delete, name="agente_delete"),
    path("execucoes/", painel.execucao_list, name="execucao_list"),
    path("execucoes/<int:pk>/", painel.execucao_detail, name="execucao_detail"),
    path("execucoes/<int:pk>/avaliar/", painel.execucao_avaliar, name="execucao_avaliar"),
    path("orcamento/", painel.orcamento_list, name="orcamento_list"),
    path("orcamento/novo/", painel.orcamento_create, name="orcamento_create"),
    path("orcamento/<int:pk>/", painel.orcamento_edit, name="orcamento_edit"),
    path("orcamento/<int:pk>/excluir/", painel.orcamento_delete, name="orcamento_delete"),
    path("alertas/<int:pk>/dispensar/", painel.alerta_dispensar, name="alerta_dispensar"),
]
