from django.urls import path

from . import views

app_name = "ia"

urlpatterns = [
    path("", views.index, name="index"),
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
]
