"""Cliente mínimo da API do Apify para o Google Maps Scraper.

O token vem de ``settings.APIFY_TOKEN`` e vai no cabeçalho, nunca na URL.
"""

from __future__ import annotations

import httpx
from django.conf import settings

BASE = "https://api.apify.com/v2"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)
PAGINA = 1000

SUCESSO = "SUCCEEDED"
FALHAS = {"FAILED", "ABORTED", "TIMED-OUT", "TIMED_OUT"}


class ApifyError(Exception):
    pass


def configurado() -> bool:
    return bool(getattr(settings, "APIFY_TOKEN", ""))


def _token() -> str:
    token = getattr(settings, "APIFY_TOKEN", "")
    if not token:
        raise ApifyError("Configure APIFY_TOKEN no .env do servidor para buscar leads no Apify.")
    return token


def _actor() -> str:
    return getattr(settings, "APIFY_ACTOR", "") or "compass~crawler-google-places"


def _limpar(texto: str, token: str) -> str:
    texto = str(texto or "")
    if token:
        texto = texto.replace(token, "***")
    return texto[:500]


def _requisitar(metodo: str, caminho: str, **kwargs):
    token = _token()
    headers = {"Authorization": f"Bearer {token}"}
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resposta = client.request(metodo, f"{BASE}{caminho}", headers=headers, **kwargs)
    except httpx.HTTPError as exc:
        raise ApifyError(_limpar(f"Falha ao falar com o Apify: {exc}", token)) from None
    if resposta.status_code >= 400:
        mensagem = ""
        try:
            mensagem = (resposta.json().get("error") or {}).get("message", "")
        except ValueError:
            mensagem = resposta.text
        if resposta.status_code == 401:
            mensagem = "Token do Apify inválido ou revogado."
        raise ApifyError(_limpar(f"Apify respondeu {resposta.status_code}: {mensagem}", token))
    try:
        return resposta.json()
    except ValueError:
        raise ApifyError("O Apify devolveu uma resposta que não é JSON.") from None


def iniciar(entrada: dict) -> dict:
    """Começa uma execução do actor e devolve os dados da execução."""
    dados = _requisitar("POST", f"/acts/{_actor()}/runs", json=entrada)
    return dados.get("data") or {}


def consultar(run_id: str) -> dict:
    dados = _requisitar("GET", f"/actor-runs/{run_id}")
    return dados.get("data") or {}


def itens(dataset_id: str) -> list[dict]:
    resultado: list[dict] = []
    offset = 0
    while True:
        pagina = _requisitar(
            "GET",
            f"/datasets/{dataset_id}/items",
            params={"clean": "true", "format": "json", "offset": offset, "limit": PAGINA},
        )
        if not isinstance(pagina, list):
            raise ApifyError("O dataset do Apify não veio como lista.")
        resultado.extend(item for item in pagina if isinstance(item, dict))
        if len(pagina) < PAGINA:
            return resultado
        offset += PAGINA
