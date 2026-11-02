from django.urls import path

from . import views

app_name = "captacao"

urlpatterns = [
    path("", views.painel, name="painel"),
    path("numeros/novo/", views.numero_create, name="numero_create"),
    path("numeros/<int:pk>/", views.numero_detail, name="numero_detail"),
    path("numeros/<int:pk>/conectar/", views.numero_conectar, name="numero_conectar"),
    path("numeros/<int:pk>/desconectar/", views.numero_desconectar, name="numero_desconectar"),
    path("numeros/<int:pk>/status/", views.numero_status, name="numero_status"),
    path("experimentos/novo/", views.experimento_form, name="experimento_create"),
    path("experimentos/<int:pk>/", views.experimento_form, name="experimento_edit"),
    path("experimentos/<int:pk>/fila/", views.experimento_fila, name="experimento_fila"),
    path("conversas/", views.conversa_list, name="conversa_list"),
    path("conversas/<int:pk>/", views.conversa_detail, name="conversa_detail"),
    path("webhook/<str:token>/", views.webhook_evolution, name="webhook"),
]
