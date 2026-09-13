from django.db import migrations


def seed_odontologia_mockup(apps, schema_editor):
    Mockup = apps.get_model("crm", "Mockup")
    Mockup.objects.update_or_create(
        slug="odontologia",
        defaults={
            "titulo": "Odontologia",
            "categoria": "odontologia",
            "tipo": "landing",
            "status": "publicado",
            "cliente": None,
            "descricao": (
                "Landing demonstrativa para clínicas odontológicas — "
                "Aurora Odontologia (protótipo Rebel Tech)."
            ),
            "preview_url": "",
            "notas_internas": "Seed da biblioteca de mockups (landing interativa).",
        },
    )


def unseed_odontologia_mockup(apps, schema_editor):
    Mockup = apps.get_model("crm", "Mockup")
    Mockup.objects.filter(slug="odontologia", tipo="landing").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0005_mockup_decouple_categoria_tipo"),
    ]

    operations = [
        migrations.RunPython(seed_odontologia_mockup, unseed_odontologia_mockup),
    ]
