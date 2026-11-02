from django.core.management.base import BaseCommand

from crm import buscas
from crm.apify import ApifyError
from crm.models import BuscaLeads


class Command(BaseCommand):
    help = "Consulta as buscas do Apify em andamento e importa as que terminaram."

    def handle(self, *args, **options):
        pendentes = BuscaLeads.objects.filter(status=BuscaLeads.Status.RODANDO).values_list("pk", flat=True)
        for pk in list(pendentes):
            try:
                busca = buscas.atualizar(pk)
            except ApifyError as exc:
                self.stderr.write(f"Busca {pk}: {exc}")
                continue
            self.stdout.write(f"Busca {pk} ({busca.nome}): {busca.get_status_display()}, {busca.novos} novo(s).")
