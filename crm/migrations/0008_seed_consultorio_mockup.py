from django.db import migrations


def seed_consultorio(apps, schema_editor):
    Mockup = apps.get_model("crm", "Mockup")
    Mockup.objects.update_or_create(
        slug="consultorio",
        defaults={
            "titulo": "Consultório",
            "categoria": "geral",
            "tipo": "landing",
            "status": "publicado",
            "cliente": None,
            "descricao": (
                "Template claro e calmo para clínicas de estética. "
                "Demonstração Alva, com paleta e textura próprias."
            ),
            "preview_url": "",
            "notas_internas": "Primeiro template da biblioteca de estética.",
        },
    )


def unseed_consultorio(apps, schema_editor):
    Mockup = apps.get_model("crm", "Mockup")
    Mockup.objects.filter(slug="consultorio", tipo="landing").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0007_qualificacao_leads"),
    ]

    operations = [
        migrations.RunPython(seed_consultorio, unseed_consultorio),
    ]
