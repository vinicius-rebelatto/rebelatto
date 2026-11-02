"""Cliente da Evolution API (v2.3) que roda ao lado do Django no docker-compose."""

from __future__ import annotations

import hashlib
import hmac

import httpx
from django.conf import settings

TIMEOUT = httpx.Timeout(40.0, connect=10.0)
EVENTOS = ["QRCODE_UPDATED", "CONNECTION_UPDATE", "MESSAGES_UPSERT", "MESSAGES_UPDATE", "SEND_MESSAGE"]


class EvolutionError(Exception):
    def __init__(self, mensagem: str, status: int | None = None, resposta=None):
        super().__init__(mensagem)
        self.status = status
        self.resposta = resposta

    @property
    def sem_whatsapp(self) -> bool:
        return _tem_exists_falso(self.resposta)


def _tem_exists_falso(dados) -> bool:
    if isinstance(dados, dict):
        if dados.get("exists") is False:
            return True
        return any(_tem_exists_falso(v) for v in dados.values())
    if isinstance(dados, list):
        return any(_tem_exists_falso(v) for v in dados)
    return False


def configurada() -> bool:
    return bool(settings.EVOLUTION_API_KEY and settings.EVOLUTION_URL)


def token_webhook() -> str:
    return hmac.new(settings.SECRET_KEY.encode(), b"captacao-webhook", hashlib.sha256).hexdigest()[:40]


def url_webhook() -> str:
    from django.urls import reverse

    caminho = reverse("captacao:webhook", kwargs={"token": token_webhook()})
    return f"{settings.EVOLUTION_WEBHOOK_BASE.rstrip('/')}{caminho}"


def _requisitar(metodo: str, caminho: str, **kwargs):
    if not configurada():
        raise EvolutionError("Configure EVOLUTION_API_KEY no .env do servidor.")
    chave = settings.EVOLUTION_API_KEY
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resposta = client.request(
                metodo,
                f"{settings.EVOLUTION_URL.rstrip('/')}{caminho}",
                headers={"apikey": chave},
                **kwargs,
            )
    except httpx.HTTPError as exc:
        raise EvolutionError(f"Não consegui falar com a Evolution API: {exc}".replace(chave, "***")) from None
    try:
        dados = resposta.json()
    except ValueError:
        dados = resposta.text
    if resposta.status_code >= 400:
        detalhe = dados
        if isinstance(dados, dict):
            detalhe = (dados.get("response") or {}).get("message") if isinstance(dados.get("response"), dict) else None
            detalhe = detalhe or dados.get("message") or dados.get("error") or dados
        texto = str(detalhe).replace(chave, "***")[:400]
        raise EvolutionError(f"Evolution respondeu {resposta.status_code}: {texto}", resposta.status_code, dados)
    return dados


def criar_instancia(instancia: str, telefone: str) -> dict:
    return _requisitar(
        "POST",
        "/instance/create",
        json={
            "instanceName": instancia,
            "integration": "WHATSAPP-BAILEYS",
            "qrcode": True,
            "number": telefone,
            "rejectCall": True,
            "msgCall": "Oi! Aqui é só por mensagem. Pode escrever que eu respondo.",
            "groupsIgnore": True,
            "alwaysOnline": False,
            "readMessages": False,
            "syncFullHistory": False,
            "webhook": {
                "url": url_webhook(),
                "byEvents": False,
                "base64": False,
                "events": EVENTOS,
            },
        },
    )


def configurar_webhook(instancia: str) -> dict:
    return _requisitar(
        "POST",
        f"/webhook/set/{instancia}",
        json={
            "webhook": {
                "enabled": True,
                "url": url_webhook(),
                "webhookByEvents": False,
                "webhookBase64": False,
                "events": EVENTOS,
            }
        },
    )


def conectar(instancia: str) -> dict:
    """Pede um QR code novo (e o código de pareamento)."""
    return _requisitar("GET", f"/instance/connect/{instancia}")


def estado(instancia: str) -> str:
    dados = _requisitar("GET", f"/instance/connectionState/{instancia}")
    if isinstance(dados, dict):
        info = dados.get("instance") or dados
        return str(info.get("state") or "")
    return ""


def desconectar(instancia: str) -> None:
    _requisitar("DELETE", f"/instance/logout/{instancia}")


def excluir(instancia: str) -> None:
    _requisitar("DELETE", f"/instance/delete/{instancia}")


def enviar_texto(instancia: str, telefone: str, texto: str, *, digitando_ms: int = 2500, previa: bool = True) -> dict:
    return _requisitar(
        "POST",
        f"/message/sendText/{instancia}",
        json={"number": telefone, "text": texto, "delay": digitando_ms, "linkPreview": previa},
    )
