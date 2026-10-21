from django.db import migrations


def seed(apps, schema_editor):
    from catalogo.seed import aplicar

    aplicar(
        apps.get_model("catalogo", "Servico"),
        apps.get_model("catalogo", "Pacote"),
        apps.get_model("catalogo", "ItemPacote"),
        apps.get_model("catalogo", "FaixaDesconto"),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("catalogo", "0001_inicial"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
