# Extend Project with cliente, status, publicado, updated_at

import django.db.models.deletion
from django.db import migrations, models


def copy_destaque_to_publicado(apps, schema_editor):
    Project = apps.get_model("portfolio", "Project")
    for project in Project.objects.all():
        project.publicado = bool(project.destaque)
        if project.publicado:
            project.status = "concluido"
        project.save(update_fields=["publicado", "status"])


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0003_migrate_leads_remove"),
        ("portfolio", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="cliente",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="projetos",
                to="crm.cliente",
                verbose_name="Cliente",
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="status",
            field=models.CharField(
                choices=[
                    ("rascunho", "Rascunho"),
                    ("em_andamento", "Em andamento"),
                    ("concluido", "Concluído"),
                    ("pausado", "Pausado"),
                    ("rejeitado", "Rejeitado"),
                ],
                default="rascunho",
                max_length=32,
                verbose_name="Status",
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="publicado",
            field=models.BooleanField(
                default=False,
                help_text="Exibe na seção de trabalhos quando o status for em andamento ou concluído.",
                verbose_name="Publicado na landing",
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name="project",
            name="destaque",
            field=models.BooleanField(
                default=True,
                help_text="Legado — preferir o campo Publicado.",
                verbose_name="Destaque na landing",
            ),
        ),
        migrations.RunPython(copy_destaque_to_publicado, migrations.RunPython.noop),
    ]
