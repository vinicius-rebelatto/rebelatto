from django.urls import path

from . import views

app_name = "erp"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.dashboard, name="dashboard"),
    # Clientes
    path("clientes/", views.cliente_list, name="cliente_list"),
    path("clientes/novo/", views.cliente_create, name="cliente_create"),
    path("clientes/importar/", views.cliente_import_csv, name="cliente_import"),
    path("clientes/filtragem/", views.cliente_filtragem, name="cliente_filtragem"),
    path("clientes/filtragem/lote/", views.cliente_filtragem_bulk, name="cliente_filtragem_bulk"),
    path("clientes/<int:pk>/", views.cliente_detail, name="cliente_detail"),
    path("clientes/<int:pk>/editar/", views.cliente_edit, name="cliente_edit"),
    path("clientes/<int:pk>/rejeitar/", views.cliente_reject, name="cliente_reject"),
    path("clientes/<int:pk>/aceitar/", views.cliente_accept_filter, name="cliente_accept"),
    path("clientes/<int:pk>/excluir/", views.cliente_delete, name="cliente_delete"),
    # Mockups
    path("mockups/", views.mockup_list, name="mockup_list"),
    path("mockups/novo/", views.mockup_create, name="mockup_create"),
    path("mockups/<int:pk>/", views.mockup_edit, name="mockup_edit"),
    path("mockups/<int:pk>/excluir/", views.mockup_delete, name="mockup_delete"),
    path("mockups/<int:pk>/publicar/", views.mockup_publish_toggle, name="mockup_publish"),
    # Projetos
    path("projetos/", views.project_list, name="project_list"),
    path("projetos/novo/", views.project_create, name="project_create"),
    path("projetos/reordenar/", views.project_reorder, name="project_reorder"),
    path("projetos/<int:pk>/", views.project_edit, name="project_edit"),
    path("projetos/<int:pk>/excluir/", views.project_delete, name="project_delete"),
]
