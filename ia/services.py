from django.db import transaction
from django.utils import timezone

from . import pricing
from .models import Credencial, Modelo
from .providers import ModeloRemoto, ProviderError, listar_modelos


@transaction.atomic
def sincronizar_modelos(credencial: Credencial, remotos: list[ModeloRemoto]) -> int:
    """Link the credential to the models it can see. Returns how many models are new."""
    ids_remotos = {r.model_id for r in remotos}
    novos: list[Modelo] = []
    for remoto in remotos:
        modelo, criado = Modelo.objects.get_or_create(
            provedor=credencial.provedor,
            model_id=remoto.model_id,
            defaults={
                "nome": remoto.nome,
                "contexto_max": remoto.contexto_max,
                "saida_max": remoto.saida_max,
            },
        )
        if not criado and remoto.nome and not modelo.nome:
            modelo.nome = remoto.nome
            modelo.save(update_fields=["nome", "updated_at"])
        modelo.credenciais.add(credencial)
        if criado:
            novos.append(modelo)

    for modelo in credencial.modelos.exclude(model_id__in=ids_remotos):
        modelo.credenciais.remove(credencial)

    if novos:
        try:
            pricing.atualizar_precos(novos)
        except pricing.PricingError:
            pass
    return len(novos)


def testar_credencial(credencial: Credencial) -> tuple[bool, str]:
    credencial.ultimo_teste_em = timezone.now()
    try:
        remotos = listar_modelos(credencial.provedor, credencial.chave)
    except ProviderError as exc:
        credencial.status = Credencial.Status.INVALIDA
        credencial.ultimo_erro = str(exc)
        credencial.save(update_fields=["status", "ultimo_erro", "ultimo_teste_em", "updated_at"])
        return False, str(exc)

    credencial.status = Credencial.Status.VALIDA
    credencial.ultimo_erro = ""
    credencial.save(update_fields=["status", "ultimo_erro", "ultimo_teste_em", "updated_at"])
    novos = sincronizar_modelos(credencial, remotos)
    mensagem = f"Chave válida — {len(remotos)} modelos disponíveis"
    if novos:
        mensagem += f", {novos} novos"
    return True, mensagem + "."
