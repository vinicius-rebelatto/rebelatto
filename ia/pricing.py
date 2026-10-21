"""Model prices and limits imported from LiteLLM's public price map."""

from decimal import Decimal

import httpx
from django.core.cache import cache
from django.utils import timezone

from .models import Modelo, Provedor

LITELLM_PRICES_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
)
CACHE_KEY = "ia:litellm-prices"
CACHE_SECONDS = 6 * 60 * 60
MILHAO = Decimal(1_000_000)

_PREFIXOS = {
    Provedor.ANTHROPIC: ["", "anthropic/"],
    Provedor.GOOGLE: ["gemini/", ""],
    Provedor.XAI: ["xai/", ""],
    Provedor.OPENAI: ["", "openai/"],
}


class PricingError(Exception):
    pass


def carregar_tabela(force: bool = False) -> dict:
    if not force:
        tabela = cache.get(CACHE_KEY)
        if tabela is not None:
            return tabela
    try:
        resp = httpx.get(LITELLM_PRICES_URL, timeout=20.0)
        resp.raise_for_status()
        tabela = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise PricingError("Não foi possível baixar a tabela de preços do LiteLLM.") from exc
    cache.set(CACHE_KEY, tabela, CACHE_SECONDS)
    return tabela


def _por_milhao(valor) -> Decimal | None:
    if valor in (None, ""):
        return None
    return (Decimal(str(valor)) * MILHAO).quantize(Decimal("0.0001"))


def encontrar(tabela: dict, provedor: str, model_id: str) -> dict | None:
    for prefixo in _PREFIXOS.get(provedor, [""]):
        entrada = tabela.get(f"{prefixo}{model_id}")
        if isinstance(entrada, dict) and entrada.get("input_cost_per_token") is not None:
            return entrada
    return None


def aplicar(modelo: Modelo, entrada: dict) -> None:
    modelo.preco_entrada = _por_milhao(entrada.get("input_cost_per_token"))
    modelo.preco_saida = _por_milhao(entrada.get("output_cost_per_token"))
    modelo.preco_cache_leitura = _por_milhao(entrada.get("cache_read_input_token_cost"))
    modelo.preco_cache_escrita = _por_milhao(entrada.get("cache_creation_input_token_cost"))
    modelo.contexto_max = entrada.get("max_input_tokens") or modelo.contexto_max
    modelo.saida_max = entrada.get("max_output_tokens") or modelo.saida_max
    modelo.suporta_visao = bool(entrada.get("supports_vision"))
    modelo.suporta_ferramentas = bool(entrada.get("supports_function_calling"))
    modelo.faixa = Modelo.faixa_por_preco(modelo.preco_saida)
    modelo.fonte_preco = Modelo.FontePreco.LITELLM
    modelo.preco_atualizado_em = timezone.now()


def atualizar_precos(modelos, tabela: dict | None = None) -> tuple[int, int]:
    """Update models not priced manually. Returns (updated, without_price)."""
    tabela = tabela if tabela is not None else carregar_tabela()
    atualizados = sem_preco = 0
    for modelo in modelos:
        if modelo.fonte_preco == Modelo.FontePreco.MANUAL:
            continue
        entrada = encontrar(tabela, modelo.provedor, modelo.model_id)
        if entrada is None:
            sem_preco += 1
            continue
        aplicar(modelo, entrada)
        modelo.save()
        atualizados += 1
    return atualizados, sem_preco
