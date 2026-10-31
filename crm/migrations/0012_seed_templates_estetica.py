from django.db import migrations

TEMPLATES = [
    ("agenda", "Agenda", "Página curta com o WhatsApp na frente. Demonstração Lis."),
    ("cartao", "Cartão", "Quase um cartão de visita, frente e verso. Demonstração Íris."),
    ("revista", "Revista", "Grelha editorial de duas colunas. Demonstração Aurea."),
    ("retrato", "Retrato", "Pensada primeiro para o celular, em tom escuro. Demonstração Vela."),
    ("minima", "Mínima", "Nome, uma frase e um botão. Demonstração Lume."),
    ("acolhedora", "Acolhedora", "Formas arredondadas e tom quente. Demonstração Brisa."),
    ("clinica", "Clínica", "Seções objetivas: sobre, procedimentos e contato. Demonstração Vértice."),
]


def seed(apps, schema_editor):
    Mockup = apps.get_model("crm", "Mockup")
    for ordem, (slug, titulo, descricao) in enumerate(TEMPLATES, start=4):
        Mockup.objects.update_or_create(
            slug=slug,
            defaults={
                "titulo": titulo,
                "categoria": "geral",
                "tipo": "landing",
                "status": "publicado",
                "cliente": None,
                "descricao": descricao,
                "preview_url": "",
                "notas_internas": f"Template {ordem} da biblioteca de estética.",
            },
        )


def unseed(apps, schema_editor):
    Mockup = apps.get_model("crm", "Mockup")
    Mockup.objects.filter(slug__in=[t[0] for t in TEMPLATES], tipo="landing").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0011_identidade_mockup_lead"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
