from django.db import migrations


def seed_harmonizacao(apps, schema_editor):
    Mockup = apps.get_model("crm", "Mockup")
    Mockup.objects.update_or_create(
        slug="harmonizacao",
        defaults={
            "titulo": "Harmonização",
            "categoria": "geral",
            "tipo": "landing",
            "status": "publicado",
            "cliente": None,
            "descricao": (
                "Template com o procedimento em destaque, para clínicas de estética. "
                "Demonstração Nara, com paleta e textura próprias."
            ),
            "preview_url": "",
            "notas_internas": "Terceiro template da biblioteca de estética.",
        },
    )


def unseed_harmonizacao(apps, schema_editor):
    Mockup = apps.get_model("crm", "Mockup")
    Mockup.objects.filter(slug="harmonizacao", tipo="landing").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0009_seed_luxo_mockup"),
    ]

    operations = [
        migrations.RunPython(seed_harmonizacao, unseed_harmonizacao),
    ]
