from django.db import migrations, models


def criar_perfil(apps, schema_editor):
    Perfil = apps.get_model("crm", "PerfilNicho")
    if Perfil.objects.exists():
        return
    Perfil.objects.create(
        nome="Clínicas de estética",
        termos_nicho="estética\nharmonização\nesteticista\nspa",
        termos_vizinhos="dermatolog\nmicropigment\nsobrancelha\nbiomedicina",
    )


def apagar_perfil(apps, schema_editor):
    Perfil = apps.get_model("crm", "PerfilNicho")
    Perfil.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0006_seed_odontologia_mockup"),
    ]

    operations = [
        migrations.CreateModel(
            name="PerfilNicho",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(default="Clínicas de estética", max_length=120, verbose_name="Nome")),
                (
                    "termos_nicho",
                    models.TextField(
                        default="estética\nharmonização\nesteticista\nspa",
                        help_text="Um termo por linha. A categoria do Maps precisa conter um deles.",
                        verbose_name="Termos do nicho",
                    ),
                ),
                (
                    "termos_vizinhos",
                    models.TextField(
                        blank=True,
                        default="dermatolog\nmicropigment\nsobrancelha\nbiomedicina",
                        help_text="Entram na leva, com menos pontos. Um termo por linha.",
                        verbose_name="Termos vizinhos",
                    ),
                ),
                (
                    "pontos_nicho",
                    models.PositiveSmallIntegerField(
                        default=25,
                        help_text="Soma quando a categoria do Maps bate com o nicho.",
                        verbose_name="Pontos do nicho",
                    ),
                ),
                (
                    "pontos_vizinho",
                    models.PositiveSmallIntegerField(
                        default=10,
                        help_text="Soma quando a categoria só bate com um termo vizinho.",
                        verbose_name="Pontos da categoria vizinha",
                    ),
                ),
                (
                    "pontos_avaliacoes_ideais",
                    models.PositiveSmallIntegerField(
                        default=35,
                        help_text="Clínica real, ainda local.",
                        verbose_name="Avaliações de 20 a 400",
                    ),
                ),
                (
                    "pontos_avaliacoes_poucas",
                    models.PositiveSmallIntegerField(default=15, verbose_name="Avaliações de 5 a 19"),
                ),
                (
                    "pontos_avaliacoes_muitas",
                    models.PositiveSmallIntegerField(
                        default=10,
                        help_text="Operação grande, ciclo de venda mais longo.",
                        verbose_name="Mais de 400 avaliações",
                    ),
                ),
                (
                    "pontos_nota_volume",
                    models.PositiveSmallIntegerField(
                        default=15,
                        help_text="Soma quando a nota é 4,2 ou mais e há pelo menos 15 avaliações.",
                        verbose_name="Nota do Maps com volume",
                    ),
                ),
                (
                    "pontos_nao_reivindicado",
                    models.PositiveSmallIntegerField(default=8, verbose_name="Perfil do Google não reivindicado"),
                ),
                (
                    "pontos_poucas_imagens",
                    models.PositiveSmallIntegerField(default=7, verbose_name="Menos de 5 fotos"),
                ),
                (
                    "pontos_agendamento",
                    models.PositiveSmallIntegerField(
                        default=10,
                        help_text="Este valor é descontado da nota.",
                        verbose_name="Já tem link de agendamento",
                    ),
                ),
                (
                    "fator_temporario",
                    models.PositiveSmallIntegerField(
                        default=20,
                        help_text="Percentual da nota que permanece. 20 deixa o lead no fim da categoria.",
                        verbose_name="Fechado temporariamente",
                    ),
                ),
            ],
            options={
                "verbose_name": "Perfil de nicho",
                "verbose_name_plural": "Perfis de nicho",
            },
        ),
        migrations.AddField(
            model_name="cliente",
            name="nota_maps",
            field=models.DecimalField(
                blank=True,
                decimal_places=1,
                max_digits=3,
                null=True,
                verbose_name="Nota no Maps",
            ),
        ),
        migrations.AddField(
            model_name="cliente",
            name="avaliacoes",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Avaliações"),
        ),
        migrations.AddField(
            model_name="cliente",
            name="imagens",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Fotos"),
        ),
        migrations.AddField(
            model_name="cliente",
            name="fechado_permanente",
            field=models.BooleanField(default=False, verbose_name="Fechado em definitivo"),
        ),
        migrations.AddField(
            model_name="cliente",
            name="fechado_temporario",
            field=models.BooleanField(default=False, verbose_name="Fechado temporariamente"),
        ),
        migrations.AddField(
            model_name="cliente",
            name="nao_reivindicado",
            field=models.BooleanField(default=False, verbose_name="Perfil não reivindicado"),
        ),
        migrations.AddField(
            model_name="cliente",
            name="link_agendamento",
            field=models.CharField(blank=True, max_length=300, verbose_name="Link de agendamento"),
        ),
        migrations.AddField(
            model_name="cliente",
            name="presenca",
            field=models.CharField(blank=True, max_length=32, verbose_name="Presença digital"),
        ),
        migrations.AddField(
            model_name="cliente",
            name="presenca_detalhe",
            field=models.CharField(blank=True, max_length=160, verbose_name="Detalhe da presença"),
        ),
        migrations.AddField(
            model_name="cliente",
            name="categoria_lead",
            field=models.CharField(
                blank=True,
                choices=[
                    ("sem_site", "Sem site"),
                    ("rede_social", "Rede social"),
                    ("site_fraco", "Site fraco"),
                    ("site_proprio", "Site próprio"),
                    ("fora_nicho", "Fora do nicho"),
                    ("fechado", "Fechado"),
                    ("sem_telefone", "Sem telefone"),
                ],
                db_index=True,
                max_length=32,
                verbose_name="Categoria do lead",
            ),
        ),
        migrations.AddField(
            model_name="cliente",
            name="nota",
            field=models.PositiveSmallIntegerField(default=0, verbose_name="Nota"),
        ),
        migrations.AddField(
            model_name="cliente",
            name="motivo_nota",
            field=models.CharField(blank=True, max_length=300, verbose_name="Motivo da nota"),
        ),
        migrations.AddField(
            model_name="cliente",
            name="dossie",
            field=models.TextField(blank=True, verbose_name="Dossiê"),
        ),
        migrations.AddField(
            model_name="cliente",
            name="ordem_fila",
            field=models.PositiveSmallIntegerField(default=9, verbose_name="Ordem na fila"),
        ),
        migrations.RunPython(criar_perfil, apagar_perfil),
    ]
