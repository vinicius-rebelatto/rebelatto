"""Fila de abordagens, guardião de aquecimento e disparo pela Evolution API."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from crm.models import Cliente

from . import evolution, textos
from .models import Abordagem, Experimento, Mensagem, NumeroWhatsApp, OptOut

MIN_ENVIOS_PARA_FREAR = 30
TAXA_FREIO = 0.15


# --- Fila -------------------------------------------------------------------


def leads_elegiveis(experimento: Experimento):
    bloqueados = set(OptOut.objects.values_list("chave_telefone", flat=True))
    qs = (
        Cliente.objects.filter(
            status=Cliente.Status.A_PROSPECTAR,
            categoria_lead__in=experimento.categorias_lista,
            nota__gte=experimento.nota_minima,
            abordagem__isnull=True,
        )
        .exclude(telefone="")
        .order_by("ordem_fila", "-nota", "id")
    )
    for cliente in qs.iterator():
        telefone = textos.telefone_whatsapp(cliente.telefone)
        if not telefone:
            continue
        chave = textos.chave_telefone(telefone)
        if chave in bloqueados:
            continue
        yield cliente, telefone, chave


@transaction.atomic
def montar_fila(experimento: Experimento) -> dict[str, int]:
    """Sorteia os leads entre os scripts, equilibrando por categoria, até a meta de cada um."""
    variantes = list(experimento.variantes.order_by("letra"))
    if not variantes:
        return {}
    vagas = {
        v.pk: max(0, experimento.leads_por_variante - v.abordagens.count())
        for v in variantes
    }
    ordem = (Abordagem.objects.order_by("-ordem").values_list("ordem", flat=True).first() or 0) + 1
    por_categoria: dict[str, int] = {}
    chaves_usadas = set(Abordagem.objects.values_list("chave_telefone", flat=True))
    criadas = {v.letra: 0 for v in variantes}
    for cliente, telefone, chave in leads_elegiveis(experimento):
        if not any(vagas.values()):
            break
        if chave in chaves_usadas:
            continue
        indice = por_categoria.get(cliente.categoria_lead, random.randrange(len(variantes)))
        escolhida = None
        for passo in range(len(variantes)):
            candidata = variantes[(indice + passo) % len(variantes)]
            if vagas[candidata.pk] > 0:
                escolhida = candidata
                por_categoria[cliente.categoria_lead] = (indice + passo + 1) % len(variantes)
                break
        if escolhida is None:
            break
        Abordagem.objects.create(
            cliente=cliente,
            variante=escolhida,
            telefone=telefone,
            chave_telefone=chave,
            ordem=ordem,
        )
        ordem += 1
        vagas[escolhida.pk] -= 1
        chaves_usadas.add(chave)
        criadas[escolhida.letra] += 1
    return criadas


# --- Guardião ---------------------------------------------------------------


@dataclass
class Situacao:
    pode_enviar: bool
    motivo: str
    enviados_hoje: int
    limite_hoje: int
    taxa_resposta: float | None
    freado: bool


def inicio_do_dia(agora: datetime) -> datetime:
    local = timezone.localtime(agora)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def taxa_resposta_recente(numero: NumeroWhatsApp, agora: datetime | None = None) -> tuple[float | None, int]:
    """Respostas das mensagens enviadas entre 4 dias e 12 horas atrás."""
    agora = agora or timezone.now()
    janela = Abordagem.objects.filter(
        numero=numero,
        enviada_em__gte=agora - timedelta(days=4),
        enviada_em__lte=agora - timedelta(hours=12),
    )
    total = janela.count()
    if not total:
        return None, 0
    return janela.filter(respondeu_em__isnull=False).count() / total, total


def limite_hoje(numero: NumeroWhatsApp, agora: datetime | None = None) -> tuple[int, bool, float | None]:
    agora = agora or timezone.now()
    curva = numero.limite_em(timezone.localtime(agora).date())
    limite = numero.limite_manual if numero.limite_manual is not None else curva
    taxa, total = taxa_resposta_recente(numero, agora)
    freado = False
    if numero.limite_manual is None and taxa is not None and total >= MIN_ENVIOS_PARA_FREAR and taxa < TAXA_FREIO:
        limite = max(20, limite // 2)
        freado = True
    return limite, freado, taxa


def enviados_hoje(numero: NumeroWhatsApp, agora: datetime | None = None) -> int:
    agora = agora or timezone.now()
    return Abordagem.objects.filter(numero=numero, enviada_em__gte=inicio_do_dia(agora)).count()


def situacao(numero: NumeroWhatsApp, agora: datetime | None = None) -> Situacao:
    agora = agora or timezone.now()
    limite, freado, taxa = limite_hoje(numero, agora)
    feitos = enviados_hoje(numero, agora)

    def nao(motivo: str) -> Situacao:
        return Situacao(False, motivo, feitos, limite, taxa, freado)

    local = timezone.localtime(agora)
    if not numero.envios_ativos:
        return nao("Envios desligados")
    if numero.conexao != NumeroWhatsApp.Conexao.CONECTADO:
        return nao("WhatsApp desconectado")
    if local.weekday() == 6 or (local.weekday() == 5 and not numero.envia_sabado):
        return nao("Fora dos dias de envio")
    if not (numero.hora_inicio <= local.time() < numero.hora_fim):
        return nao("Fora do horário de envio")
    if feitos >= limite:
        return nao("Limite do dia atingido")
    if numero.proximo_envio_em and agora < numero.proximo_envio_em:
        return nao("Aguardando o intervalo")
    return Situacao(True, "Pronto para enviar", feitos, limite, taxa, freado)


def proximo_intervalo(numero: NumeroWhatsApp, enviados: int) -> timedelta:
    minimo = min(numero.intervalo_min, numero.intervalo_max)
    maximo = max(numero.intervalo_min, numero.intervalo_max)
    segundos = random.uniform(minimo, maximo)
    if numero.pausa_a_cada and enviados and enviados % numero.pausa_a_cada == 0:
        segundos += numero.pausa_minutos * 60 * random.uniform(0.8, 1.25)
    return timedelta(seconds=segundos)


# --- Disparo ----------------------------------------------------------------


def proxima_da_fila():
    bloqueados = OptOut.objects.values_list("chave_telefone", flat=True)
    return (
        Abordagem.objects.select_related("cliente", "variante", "variante__experimento")
        .filter(envio=Abordagem.Envio.NA_FILA, variante__experimento__ativo=True)
        .exclude(chave_telefone__in=bloqueados)
        .order_by("ordem", "id")
        .first()
    )


def disparar(numero: NumeroWhatsApp, agora: datetime | None = None) -> Abordagem | None:
    """Envia a próxima mensagem da fila por este número, se o guardião deixar."""
    agora = agora or timezone.now()
    with transaction.atomic():
        numero = NumeroWhatsApp.objects.select_for_update().get(pk=numero.pk)
        estado = situacao(numero, agora)
        if not estado.pode_enviar:
            return None
        abordagem = proxima_da_fila()
        if abordagem is None:
            return None
        abordagem = Abordagem.objects.select_for_update().get(pk=abordagem.pk)
        if abordagem.envio != Abordagem.Envio.NA_FILA:
            return None

        texto = textos.montar(abordagem.variante.texto, abordagem.cliente, semente=abordagem.pk)
        abordagem.numero = numero
        abordagem.texto_enviado = texto
        abordagem.versao_script = abordagem.variante.versao
        abordagem.texto_script = abordagem.variante.texto
        abordagem.lead_no_envio = foto_do_lead(abordagem.cliente, numero, agora)
        try:
            resposta = evolution.enviar_texto(
                numero.instancia,
                abordagem.telefone,
                texto,
                digitando_ms=random.randint(1800, 4200),
                previa=abordagem.variante.experimento.previa_do_link,
            )
        except evolution.EvolutionError as exc:
            abordagem.envio = Abordagem.Envio.FALHOU
            abordagem.erro = "Número sem WhatsApp." if exc.sem_whatsapp else str(exc)
            abordagem.save()
            numero.ultimo_erro = "" if exc.sem_whatsapp else str(exc)
            numero.proximo_envio_em = agora + timedelta(seconds=20 if exc.sem_whatsapp else 300)
            numero.save(update_fields=["ultimo_erro", "proximo_envio_em", "updated_at"])
            return abordagem

        chave = (resposta or {}).get("key") or {}
        abordagem.envio = Abordagem.Envio.ENVIADA
        abordagem.enviada_em = agora
        abordagem.jid = str(chave.get("remoteJid") or "")
        abordagem.erro = ""
        abordagem.save()
        registrar_saida(abordagem, numero, Mensagem.Autor.SCRIPT, texto, resposta)
        Cliente.objects.filter(pk=abordagem.cliente_id).update(
            status=Cliente.Status.EM_PROSPECCAO, updated_at=agora
        )
        numero.ultimo_envio_em = agora
        numero.ultimo_erro = ""
        numero.proximo_envio_em = agora + proximo_intervalo(numero, estado.enviados_hoje + 1)
        numero.save(update_fields=["ultimo_envio_em", "ultimo_erro", "proximo_envio_em", "updated_at"])
        return abordagem


def foto_do_lead(cliente: Cliente, numero: NumeroWhatsApp, agora: datetime) -> dict:
    """Como o lead e o número estavam no momento do envio, para análise depois."""
    local = timezone.localtime(agora)
    return {
        "categoria_lead": cliente.categoria_lead,
        "nota": cliente.nota,
        "motivo_nota": cliente.motivo_nota,
        "presenca": cliente.presenca,
        "presenca_detalhe": cliente.presenca_detalhe,
        "nota_maps": str(cliente.nota_maps) if cliente.nota_maps is not None else None,
        "avaliacoes": cliente.avaliacoes,
        "imagens": cliente.imagens,
        "nao_reivindicado": cliente.nao_reivindicado,
        "tem_agendamento": bool(cliente.link_agendamento),
        "tem_instagram": bool(cliente.instagram),
        "categoria_maps": cliente.categoria,
        "cidade": cliente.cidade,
        "bairro": cliente.bairro,
        "estado": cliente.estado,
        "busca_id": cliente.busca_id,
        "mockup_visitas_antes": cliente.mockup_visitas,
        "dia_aquecimento": numero.dia_em(local.date()),
        "dia_semana": local.weekday(),
        "hora": local.hour,
    }


def enviar_resposta(abordagem: Abordagem, texto: str, autor: str = Mensagem.Autor.VOCE) -> Mensagem:
    numero = abordagem.numero
    if numero is None:
        raise evolution.EvolutionError("Esta conversa ainda não tem um número de WhatsApp.")
    resposta = evolution.enviar_texto(
        numero.instancia, abordagem.telefone, texto, digitando_ms=random.randint(1200, 3000), previa=False
    )
    return registrar_saida(abordagem, numero, autor, texto, resposta)


def registrar_saida(abordagem: Abordagem, numero: NumeroWhatsApp, autor: str, texto: str, resposta) -> Mensagem:
    """Grava a mensagem enviada. Se o webhook chegou antes, só corrige o autor."""
    chave = (resposta or {}).get("key") or {}
    whatsapp_id = str(chave.get("id") or "")
    dados = {
        "abordagem": abordagem,
        "numero": numero,
        "direcao": Mensagem.Direcao.SAIDA,
        "autor": autor,
        "texto": texto,
        "jid": str(chave.get("remoteJid") or ""),
        "status": str((resposta or {}).get("status") or ""),
    }
    if not whatsapp_id:
        return Mensagem.objects.create(**dados)
    mensagem, _ = Mensagem.objects.update_or_create(whatsapp_id=whatsapp_id, defaults=dados)
    return mensagem


def registrar_opt_out(telefone: str, motivo: str = "") -> None:
    chave = textos.chave_telefone(telefone)
    if not chave:
        return
    OptOut.objects.get_or_create(chave_telefone=chave, defaults={"telefone": telefone, "motivo": motivo[:200]})
    agora = timezone.now()
    Abordagem.objects.filter(chave_telefone=chave, opt_out_em__isnull=True).update(
        opt_out_em=agora, ia_pausada=True
    )
    Abordagem.objects.filter(chave_telefone=chave, envio=Abordagem.Envio.NA_FILA).update(
        envio=Abordagem.Envio.CANCELADA
    )
