"""Processo que fica rodando ao lado do site: envia a fila, gera respostas e importa buscas.

No docker-compose ele é o serviço `worker`. Para rodar uma volta só (testes, cron):
    python manage.py rodar_captacao --uma-vez
"""

import logging
import signal
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from captacao import conversao, operacao
from captacao.models import NumeroWhatsApp
from crm import buscas
from crm.apify import ApifyError
from crm.models import BuscaLeads

logger = logging.getLogger(__name__)

PAUSA = 10  # segundos entre voltas
BUSCAS_A_CADA = 6  # voltas (1 minuto)


class Command(BaseCommand):
    help = "Dispara a fila de WhatsApp, gera respostas da IA e importa buscas do Apify."

    def add_arguments(self, parser):
        parser.add_argument("--uma-vez", action="store_true", help="Roda uma volta e sai.")

    def handle(self, *args, **options):
        self.parar = False
        signal.signal(signal.SIGTERM, self._sair)
        signal.signal(signal.SIGINT, self._sair)
        volta = 0
        self.stdout.write("Captação rodando.")
        while not self.parar:
            close_old_connections()
            self.volta(com_buscas=volta % BUSCAS_A_CADA == 0)
            close_old_connections()
            if options["uma_vez"]:
                break
            volta += 1
            for _ in range(PAUSA):
                if self.parar:
                    break
                time.sleep(1)

    def _sair(self, *args):
        self.parar = True

    def volta(self, com_buscas: bool) -> None:
        for numero in NumeroWhatsApp.objects.filter(envios_ativos=True):
            try:
                abordagem = operacao.disparar(numero)
            except Exception:
                logger.exception("Falha ao disparar pelo número %s", numero.pk)
                continue
            if abordagem is not None:
                self.stdout.write(f"{numero.apelido}: {abordagem.get_envio_display()} para {abordagem.cliente}")
        try:
            conversao.processar_pendentes()
        except Exception:
            logger.exception("Falha ao gerar respostas da IA")
        if com_buscas:
            for pk in BuscaLeads.objects.filter(status=BuscaLeads.Status.RODANDO).values_list("pk", flat=True):
                try:
                    buscas.atualizar(pk)
                except ApifyError as exc:
                    logger.warning("Busca %s: %s", pk, exc)
                except Exception:
                    logger.exception("Falha ao atualizar a busca %s", pk)
