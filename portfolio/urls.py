from django.urls import path

from . import views

app_name = "portfolio"

urlpatterns = [
    path("", views.home, name="home"),
    path("leads/", views.create_lead, name="create_lead"),
    path("mockup/<slug:slug>/", views.mockup_public, name="mockup_public"),
]
