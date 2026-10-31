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
    path("p/<slug:slug>/<slug:template>/", views.mockup_lead, name="mockup_lead_template"),
    path("mockup/<slug:slug>/", views.mockup_public_legacy, name="mockup_public_legacy"),
]
