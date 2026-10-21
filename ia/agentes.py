"""Cadastro dos agentes e a versão que guarda prompt, parâmetros e modelo."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction

from .models import Agente, Modelo, Provedor, VersaoAgente


def slug_chatbot(persona_id: str) -> str:
    return "chatbot-" + persona_id.replace("_", "-")


def garantir_chatbots() -> list[Agente]:
    from portfolio.chatbot import PERSONAS

    return [garantir_chatbot(persona_id) for persona_id in PERSONAS]


def garantir_chatbot(persona_id: str) -> Agente:
    """Garante o agente da persona. Na primeira versão, copia o prompt atual do site."""
    slug = slug_chatbot(persona_id)
    agente = Agente.objects.filter(slug=slug).first()
    if agente is not None:
        versao = agente.versao_ativa
        if versao is not None and versao.modelo_id:
            return agente
        if versao is not None and versao.numero == 1 and not versao.modelo_id:
            modelo = modelo_gemini_configurado()
            if modelo is not None:
                VersaoAgente.objects.filter(pk=versao.pk, modelo__isnull=True).update(modelo=modelo)
        if versao is not None:
            return agente

    from portfolio.chatbot import PERSONAS, build_system_instruction

    persona = PERSONAS[persona_id]
    with transaction.atomic():
        agente, _criado = Agente.objects.get_or_create(
            slug=slug,
            defaults={
                "nome": persona["title"],
                "responsabilidade": persona.get("subtitle") or "Chatbot público do site.",
                "sistema": True,
                "ativo": True,
            },
        )
        if not agente.versoes.exists():
            try:
                VersaoAgente.objects.create(
                    agente=agente,
                    numero=1,
                    prompt=build_system_instruction(persona),
                    temperatura=Decimal("0.55"),
                    max_tokens=700,
                    modelo=modelo_gemini_configurado(),
                    ativa=True,
                )
            except IntegrityError:
                pass
    return agente


def modelo_gemini_configurado() -> Modelo | None:
    bruto = (getattr(settings, "GEMINI_MODEL", "") or "").strip()
    if not bruto:
        return None
    candidatos = {bruto, bruto.removeprefix("models/"), bruto.split("/")[-1]}
    candidatos.discard("")
    return (
        Modelo.objects.filter(provedor=Provedor.GOOGLE, model_id__in=candidatos)
        .order_by("-habilitado", "model_id")
        .first()
    )


@transaction.atomic
def salvar_agente(dados: dict, agente: Agente | None = None) -> Agente:
    if agente is None:
        agente = Agente(slug=dados["slug"], sistema=False)
    else:
        agente = Agente.objects.select_for_update().get(pk=agente.pk)
    agente.nome = dados["nome"]
    agente.responsabilidade = dados["responsabilidade"]
    agente.ativo = dados["ativo"]
    agente.save()

    modelo = dados.get("modelo")
    reserva = dados.get("modelo_reserva")
    atual = agente.versao_ativa
    mudou = (
        atual is None
        or atual.prompt != dados["prompt"]
        or atual.temperatura != dados["temperatura"]
        or atual.max_tokens != dados["max_tokens"]
        or atual.modelo_id != (modelo.pk if modelo else None)
        or atual.modelo_reserva_id != (reserva.pk if reserva else None)
    )
    if not mudou:
        return agente
    if atual is not None:
        atual.ativa = False
        atual.save(update_fields=["ativa"])
    VersaoAgente.objects.create(
        agente=agente,
        numero=(atual.numero + 1) if atual else 1,
        prompt=dados["prompt"],
        temperatura=dados["temperatura"],
        max_tokens=dados["max_tokens"],
        modelo=modelo,
        modelo_reserva=reserva,
        ativa=True,
    )
    return agente


@transaction.atomic
def restaurar_versao(versao: VersaoAgente) -> VersaoAgente:
    agente = Agente.objects.select_for_update().get(pk=versao.agente_id)
    atual = agente.versao_ativa
    if atual is not None and atual.pk == versao.pk:
        return versao
    if atual is not None:
        atual.ativa = False
        atual.save(update_fields=["ativa"])
    numero = agente.versoes.order_by("-numero").values_list("numero", flat=True).first() or 0
    return VersaoAgente.objects.create(
        agente=agente,
        numero=numero + 1,
        prompt=versao.prompt,
        temperatura=versao.temperatura,
        max_tokens=versao.max_tokens,
        modelo=versao.modelo,
        modelo_reserva=versao.modelo_reserva,
        ativa=True,
    )
