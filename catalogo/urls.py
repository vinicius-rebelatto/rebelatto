from django.urls import path

from . import views

app_name = "catalogo"

urlpatterns = [
    path("", views.pacote_list, name="pacote_list"),
    path("pacotes/novo/", views.pacote_create, name="pacote_create"),
    path("pacotes/<int:pk>/", views.pacote_edit, name="pacote_edit"),
    path("pacotes/<int:pk>/excluir/", views.pacote_delete, name="pacote_delete"),
    path("servicos/", views.servico_list, name="servico_list"),
    path("servicos/novo/", views.servico_create, name="servico_create"),
    path("servicos/<int:pk>/", views.servico_edit, name="servico_edit"),
    path("servicos/<int:pk>/excluir/", views.servico_delete, name="servico_delete"),
    path("descontos/", views.desconto_list, name="desconto_list"),
    path("propostas/", views.proposta_list, name="proposta_list"),
    path("propostas/nova/", views.proposta_create, name="proposta_create"),
    path("propostas/<int:pk>/", views.proposta_detail, name="proposta_detail"),
    path("propostas/<int:pk>/documento/", views.proposta_documento, name="proposta_documento"),
    path("propostas/<int:pk>/pdf/", views.proposta_pdf, name="proposta_pdf"),
    path("propostas/<int:pk>/editar/", views.proposta_edit, name="proposta_edit"),
    path("propostas/<int:pk>/fechar/", views.proposta_fechar, name="proposta_fechar"),
    path("propostas/<int:pk>/excluir/", views.proposta_excluir, name="proposta_excluir"),
]
