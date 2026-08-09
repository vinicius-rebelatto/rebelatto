# Data migration: Lead -> Cliente, then drop Lead

from django.db import migrations
from django.utils.text import slugify


STATUS_MAP = {
    "novo": "a_prospectar",
    "contatado": "em_prospeccao",
    "qualificado": "convertido",
    "arquivado": "rejeitado",
}

ORIGEM_MAP = {
    "hire_modal": "contato",
    "contato": "contato",
    "outro": "manual",
}


def forwards(apps, schema_editor):
    Lead = apps.get_model("crm", "Lead")
    Cliente = apps.get_model("crm", "Cliente")
    used_slugs: set[str] = set()

    for lead in Lead.objects.all().order_by("id"):
        base = slugify(lead.nome)[:180] or f"lead-{lead.pk}"
        slug = base
        index = 2
        while slug in used_slugs or Cliente.objects.filter(slug=slug).exists():
            slug = f"{base}-{index}"
            index += 1
        used_slugs.add(slug)

        status = STATUS_MAP.get(lead.status, "a_prospectar")
        etapa = "prospeccao" if status == "rejeitado" else None

        cliente = Cliente(
            nome=lead.nome,
            empresa=lead.nome,
            slug=slug,
            email=lead.email,
            telefone=lead.telefone or "",
            mensagem=lead.mensagem or "",
            origem=ORIGEM_MAP.get(lead.origem, "contato"),
            status=status,
            etapa_rejeicao=etapa,
        )
        cliente.save()
        Cliente.objects.filter(pk=cliente.pk).update(created_at=lead.created_at)


def backwards(apps, schema_editor):
    Lead = apps.get_model("crm", "Lead")
    Cliente = apps.get_model("crm", "Cliente")
    for cliente in Cliente.objects.filter(origem="contato"):
        if not cliente.email:
            continue
        Lead.objects.create(
            nome=cliente.nome or cliente.empresa or "Lead",
            email=cliente.email,
            telefone=cliente.telefone,
            mensagem=cliente.mensagem or "-",
            origem="contato",
            status="novo",
        )


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0002_cliente_mockup"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.DeleteModel(name="Lead"),
    ]
