from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalogo", "0002_seed"),
    ]

    operations = [
        migrations.AddField(
            model_name="itemproposta",
            name="preco_negociado",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="itemproposta",
            name="desconto",
            field=models.DecimalField(decimal_places=4, default=0, max_digits=5),
        ),
    ]
