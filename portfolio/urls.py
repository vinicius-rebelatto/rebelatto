from django.urls import path

from . import views

app_name = "portfolio"

urlpatterns = [
    path("", views.home, name="home"),
    path("leads/", views.create_lead, name="create_lead"),
    path("chat/", views.chat_message, name="chat"),
    path("robots.txt", views.robots_txt, name="robots"),
    path("sitemap.xml", views.sitemap_xml, name="sitemap"),
    path("mockups/<slug:slug>/", views.mockup_public, name="mockup_public"),
    path("p/<slug:slug>/", views.mockup_lead, name="mockup_lead"),
    path("mockups/<slug:slug>/servicos/<slug:servico>/", views.mockup_public, {"pagina": "servico"}, name="mockup_public_servico"),
    path("mockups/<slug:slug>/<slug:pagina>/", views.mockup_public, name="mockup_public_pagina"),
    path("p/<slug:slug>/<slug:template>/", views.mockup_lead, name="mockup_lead_template"),
    path("p/<slug:slug>/<slug:template>/servicos/<slug:servico>/", views.mockup_lead, {"pagina": "servico"}, name="mockup_lead_servico"),
    path("p/<slug:slug>/<slug:template>/<slug:pagina>/", views.mockup_lead, name="mockup_lead_pagina"),
    path("mockup/<slug:slug>/", views.mockup_public_legacy, name="mockup_public_legacy"),
]
