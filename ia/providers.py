"""Minimal HTTP clients used to validate keys and list models per provider.

Listing models consumes no tokens, so it doubles as the key validation call.
"""

from dataclasses import dataclass

import httpx

from .models import Provedor

TIMEOUT = httpx.Timeout(15.0)
ANTHROPIC_VERSION = "2023-06-01"

PROVEDORES_COM_ADMIN = {Provedor.ANTHROPIC, Provedor.OPENAI}

INFO_PROVEDORES = {
    Provedor.ANTHROPIC: {
        "console_url": "https://console.anthropic.com/settings/keys",
        "chave_hint": "sk-ant-api…",
        "admin_hint": "sk-ant-admin… (opcional, exige conta de organização)",
    },
    Provedor.GOOGLE: {
        "console_url": "https://aistudio.google.com/apikey",
        "chave_hint": "Chave do Google AI Studio",
        "admin_hint": "",
    },
    Provedor.XAI: {
        "console_url": "https://console.x.ai",
        "chave_hint": "xai-…",
        "admin_hint": "",
    },
    Provedor.OPENAI: {
        "console_url": "https://platform.openai.com/api-keys",
        "chave_hint": "sk-proj-…",
        "admin_hint": "sk-admin… (opcional, criada pelo dono da organização)",
    },
}

_OPENAI_NAO_TEXTO = (
    "embedding",
    "tts",
    "whisper",
    "dall-e",
    "moderation",
    "image",
    "audio",
    "realtime",
    "transcribe",
    "davinci",
    "babbage",
    "sora",
)


class ProviderError(Exception):
    pass


@dataclass
class ModeloRemoto:
    model_id: str
    nome: str = ""
    contexto_max: int | None = None
    saida_max: int | None = None


def _erro_http(resp: httpx.Response) -> ProviderError:
    if resp.status_code in (401, 403):
        return ProviderError("Chave inválida ou sem permissão para este recurso.")
    if resp.status_code == 429:
        return ProviderError("Limite de requisições atingido no provedor. Tente novamente em instantes.")
    try:
        payload = resp.json()
        detalhe = (
            payload.get("error", {}).get("message")
            if isinstance(payload.get("error"), dict)
            else payload.get("error") or payload.get("message")
        )
    except ValueError:
        detalhe = resp.text[:200]
    detalhe = str(detalhe or "erro desconhecido").strip().rstrip(".")
    # Google and xAI answer 400 (not 401) for a bad key.
    if resp.status_code == 400 and "api key" in detalhe.lower():
        return ProviderError(f"Chave inválida ({detalhe}).")
    return ProviderError(f"O provedor respondeu {resp.status_code}: {detalhe}.")


def _get(client: httpx.Client, url: str, **kwargs) -> dict:
    try:
        resp = client.get(url, **kwargs)
    except httpx.RequestError as exc:
        raise ProviderError("Não foi possível conectar ao provedor. Verifique a rede da VPS.") from exc
    if resp.status_code != 200:
        raise _erro_http(resp)
    return resp.json()


def _anthropic(chave: str) -> list[ModeloRemoto]:
    headers = {"x-api-key": chave, "anthropic-version": ANTHROPIC_VERSION}
    modelos: list[ModeloRemoto] = []
    params: dict[str, str | int] = {"limit": 1000}
    with httpx.Client(timeout=TIMEOUT, headers=headers) as client:
        while True:
            data = _get(client, "https://api.anthropic.com/v1/models", params=params)
            for item in data.get("data", []):
                modelos.append(ModeloRemoto(item["id"], item.get("display_name", "")))
            if not data.get("has_more") or not data.get("last_id"):
                break
            params["after_id"] = data["last_id"]
    return modelos


def _google(chave: str) -> list[ModeloRemoto]:
    headers = {"x-goog-api-key": chave}
    modelos: list[ModeloRemoto] = []
    params: dict[str, str | int] = {"pageSize": 1000}
    with httpx.Client(timeout=TIMEOUT, headers=headers) as client:
        while True:
            data = _get(client, "https://generativelanguage.googleapis.com/v1beta/models", params=params)
            for item in data.get("models", []):
                if "generateContent" not in item.get("supportedGenerationMethods", []):
                    continue
                modelos.append(
                    ModeloRemoto(
                        model_id=item["name"].removeprefix("models/"),
                        nome=item.get("displayName", ""),
                        contexto_max=item.get("inputTokenLimit"),
                        saida_max=item.get("outputTokenLimit"),
                    )
                )
            token = data.get("nextPageToken")
            if not token:
                break
            params["pageToken"] = token
    return modelos


def _bearer_models(url: str, chave: str) -> list[dict]:
    with httpx.Client(timeout=TIMEOUT, headers={"Authorization": f"Bearer {chave}"}) as client:
        return _get(client, url).get("data", [])


def _xai(chave: str) -> list[ModeloRemoto]:
    return [ModeloRemoto(item["id"]) for item in _bearer_models("https://api.x.ai/v1/models", chave)]


def _openai(chave: str) -> list[ModeloRemoto]:
    return [
        ModeloRemoto(item["id"])
        for item in _bearer_models("https://api.openai.com/v1/models", chave)
        if not any(marca in item["id"] for marca in _OPENAI_NAO_TEXTO)
    ]


_LISTAGEM = {
    Provedor.ANTHROPIC: _anthropic,
    Provedor.GOOGLE: _google,
    Provedor.XAI: _xai,
    Provedor.OPENAI: _openai,
}


def listar_modelos(provedor: str, chave: str) -> list[ModeloRemoto]:
    if provedor not in _LISTAGEM:
        raise ProviderError("Provedor não suportado.")
    modelos = _LISTAGEM[provedor](chave.strip())
    if not modelos:
        raise ProviderError("A chave é válida, mas nenhum modelo de texto está disponível para ela.")
    return modelos


def validar_chave_admin(provedor: str, chave_admin: str) -> None:
    chave_admin = chave_admin.strip()
    if provedor == Provedor.ANTHROPIC:
        headers = {"x-api-key": chave_admin, "anthropic-version": ANTHROPIC_VERSION}
        url = "https://api.anthropic.com/v1/organizations/users"
    elif provedor == Provedor.OPENAI:
        headers = {"Authorization": f"Bearer {chave_admin}"}
        url = "https://api.openai.com/v1/organization/users"
    else:
        raise ProviderError("Este provedor não usa chave de admin.")
    with httpx.Client(timeout=TIMEOUT, headers=headers) as client:
        _get(client, url, params={"limit": 1})
