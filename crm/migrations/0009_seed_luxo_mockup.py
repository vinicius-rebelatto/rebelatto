from django.db import migrations


def seed_luxo(apps, schema_editor):
    Mockup = apps.get_model("crm", "Mockup")
    Mockup.objects.update_or_create(
        slug="luxo",
        defaults={
            "titulo": "Luxo",
            "categoria": "geral",
            "tipo": "landing",
            "status": "publicado",
            "cliente": None,
            "descricao": (
                "Template escuro, com margem larga, para clínicas de estética. "
                "Demonstração Ónix, com paleta e textura próprias."
            ),
            "preview_url": "",
            "notas_internas": "Segundo template da biblioteca de estética.",
        },
    )


def unseed_luxo(apps, schema_editor):
    Mockup = apps.get_model("crm", "Mockup")
    Mockup.objects.filter(slug="luxo", tipo="landing").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0008_seed_consultorio_mockup"),
    ]

    operations = [
        migrations.RunPython(seed_luxo, unseed_luxo),
    ]
