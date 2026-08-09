# Generated manually for Cliente / Mockup models

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Cliente",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(blank=True, max_length=160, verbose_name="Nome")),
                ("empresa", models.CharField(blank=True, max_length=200, verbose_name="Empresa")),
                ("slug", models.SlugField(max_length=220, unique=True, verbose_name="Slug")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="E-mail")),
                ("telefone", models.CharField(blank=True, max_length=40, verbose_name="Telefone")),
                ("website", models.URLField(blank=True, verbose_name="Website")),
                ("mensagem", models.TextField(blank=True, verbose_name="Mensagem")),
                ("maps_url", models.URLField(blank=True, max_length=500, verbose_name="URL Maps")),
                ("categoria", models.CharField(blank=True, max_length=160, verbose_name="Categoria")),
                ("rua", models.CharField(blank=True, max_length=255, verbose_name="Rua")),
                ("cidade", models.CharField(blank=True, max_length=120, verbose_name="Cidade")),
                ("estado", models.CharField(blank=True, max_length=80, verbose_name="Estado")),
                (
                    "origem",
                    models.CharField(
                        choices=[("contato", "Seção Contato"), ("csv", "Importação CSV"), ("manual", "Manual")],
                        default="manual",
                        max_length=32,
                        verbose_name="Origem",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("importado", "Importado"),
                            ("a_prospectar", "A prospectar"),
                            ("em_prospeccao", "Em prospecção"),
                            ("convertido", "Convertido"),
                            ("rejeitado", "Rejeitado"),
                        ],
                        default="a_prospectar",
                        max_length=32,
                        verbose_name="Status",
                    ),
                ),
                (
                    "etapa_rejeicao",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("filtragem", "Filtragem"),
                            ("prospeccao", "Prospecção"),
                            ("orcamento", "Orçamento"),
                        ],
                        max_length=32,
                        null=True,
                        verbose_name="Etapa da rejeição",
                    ),
                ),
                ("motivo_rejeicao", models.TextField(blank=True, verbose_name="Motivo da rejeição")),
                ("notas", models.TextField(blank=True, verbose_name="Notas")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
            ],
            options={
                "verbose_name": "Cliente",
                "verbose_name_plural": "Clientes",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="Mockup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=160, verbose_name="Título")),
                ("slug", models.SlugField(max_length=220, unique=True, verbose_name="Slug")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("rascunho", "Rascunho"),
                            ("publicado", "Publicado"),
                            ("arquivado", "Arquivado"),
                        ],
                        default="rascunho",
                        max_length=32,
                        verbose_name="Status",
                    ),
                ),
                ("capa", models.ImageField(blank=True, upload_to="mockups/", verbose_name="Capa")),
                ("descricao", models.TextField(blank=True, verbose_name="Descrição")),
                ("preview_url", models.URLField(blank=True, verbose_name="URL de preview")),
                ("notas_internas", models.TextField(blank=True, verbose_name="Notas internas")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
                (
                    "cliente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mockups",
                        to="crm.cliente",
                        verbose_name="Cliente",
                    ),
                ),
            ],
            options={
                "verbose_name": "Mockup",
                "verbose_name_plural": "Mockups",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="MockupImagem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("imagem", models.ImageField(upload_to="mockups/gallery/", verbose_name="Imagem")),
                ("legenda", models.CharField(blank=True, max_length=200, verbose_name="Legenda")),
                ("ordem", models.PositiveIntegerField(default=0, verbose_name="Ordem")),
                (
                    "mockup",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="imagens",
                        to="crm.mockup",
                        verbose_name="Mockup",
                    ),
                ),
            ],
            options={
                "verbose_name": "Imagem do mockup",
                "verbose_name_plural": "Imagens do mockup",
                "ordering": ["ordem", "id"],
            },
        ),
    ]
