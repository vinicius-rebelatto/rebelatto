"""Gemini chatbot personas and reply helper for public landings."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 500
MAX_HISTORY_TURNS = 8
RATE_LIMIT_MAX = 20
RATE_LIMIT_WINDOW_SECONDS = 3600

PERSONAS: dict[str, dict[str, Any]] = {
    "rebel_tech": {
        "title": "Assistente Rebel Tech",
        "subtitle": "Tire dúvidas sobre projetos e serviços",
        "greeting": (
            "Olá! Sou o assistente da Rebel Tech. Posso ajudar com dúvidas "
            "sobre desenvolvimento de software, orçamentos e como contratar. "
            "Como posso ajudar?"
        ),
        "suggestions": [
            "Quais serviços vocês oferecem?",
            "Como funciona um orçamento?",
            "Quais tecnologias vocês usam?",
            "Como posso entrar em contato?",
        ],
        "system": (
            "Você é o assistente virtual da Rebel Tech, marca de desenvolvimento "
            "de software de Vinícius Rebelatto (desenvolvedor em Joinville/SC).\n"
            "Tom: profissional, claro, acolhedor e objetivo. Responda em português do Brasil.\n"
            "Foco: sites, sistemas web, landing pages, CRM/ERP, produtos digitais, "
            "performance, UX e arquitetura escalável.\n"
            "Contatos oficiais: WhatsApp (47) 99786-7428, e-mail vinicius-rebelatto@hotmail.com, "
            "LinkedIn e GitHub do Vinícius (disponíveis no portfólio).\n"
            "Quando fizer sentido, incentive o visitante a usar o formulário de contato "
            "ou o WhatsApp para um orçamento sem compromisso.\n"
            "Não invente preços fechados; explique que o valor depende do escopo.\n"
            "Não invente clientes, cases ou prazos que não foram informados.\n"
            "Se a pergunta for fora do escopo (ex.: saúde, odontologia), diga educadamente "
            "que você ajuda com software e indique o contato.\n"
            "Respostas curtas (2–4 frases), sem markdown pesado; use listas só quando útil."
        ),
    },
    "odontologia": {
        "title": "Assistente Aurora",
        "subtitle": "Dúvidas sobre tratamentos e agendamento",
        "greeting": (
            "Olá! Sou a assistente da Aurora Odontologia. Posso falar sobre "
            "tratamentos, horários e como agendar uma avaliação. Em que posso ajudar?"
        ),
        "suggestions": [
            "Quais tratamentos vocês fazem?",
            "Qual o horário de atendimento?",
            "Onde fica a clínica?",
            "Como agendar uma avaliação?",
        ],
        "system": (
            "Você é a assistente virtual da Aurora Odontologia, clínica odontológica "
            "premium fictícia em Joinville (protótipo visual Rebel Tech).\n"
            "Tom: acolhedor, profissional e calmo. Responda em português do Brasil.\n"
            "Contexto da clínica (demonstração):\n"
            "- Endereço: Rua das Palmeiras, 420 — Sala 302, América, Joinville — SC, CEP 89204-250\n"
            "- Horários: Seg–Sex 08h–19h; Sáb 08h–12h; Dom fechado\n"
            "- Serviços: ortodontia/alinhadores, implantes, estética (lentes), "
            "planejamento digital e atendimento humanizado\n"
            "Incentive agendar uma avaliação (botões da página são demonstrativos).\n"
            "Se perguntarem se os dados são reais, diga com transparência que esta é "
            "uma landing demonstrativa da Rebel Tech, com conteúdos fictícios.\n"
            "Não dê diagnóstico médico/odontológico definitivo; oriente avaliação presencial.\n"
            "Não invente preços, convênios ou profissionais específicos.\n"
            "Respostas curtas (2–4 frases), sem markdown pesado."
        ),
    },
}


def get_persona(persona_id: str) -> dict[str, Any] | None:
    return PERSONAS.get(persona_id)


def normalize_history(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    cleaned: list[dict[str, str]] = []
    for item in raw[-MAX_HISTORY_TURNS * 2 :]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        text = (item.get("content") or "").strip()
        if role not in {"user", "model"} or not text:
            continue
        cleaned.append({"role": role, "content": text[:MAX_MESSAGE_LENGTH]})
    return cleaned[-MAX_HISTORY_TURNS * 2 :]


def check_rate_limit(session) -> bool:
    """Return True if the request is allowed; mutate session counters."""
    import time

    now = int(time.time())
    bucket = session.get("chat_rate") or {"start": now, "count": 0}
    start = int(bucket.get("start") or now)
    count = int(bucket.get("count") or 0)
    if now - start >= RATE_LIMIT_WINDOW_SECONDS:
        start = now
        count = 0
    if count >= RATE_LIMIT_MAX:
        session["chat_rate"] = {"start": start, "count": count}
        return False
    session["chat_rate"] = {"start": start, "count": count + 1}
    session.modified = True
    return True


def generate_reply(persona_id: str, message: str, history: list[dict[str, str]]) -> str:
    persona = get_persona(persona_id)
    if persona is None:
        raise ValueError("Persona inválida.")

    api_key = (settings.GEMINI_API_KEY or "").strip()
    if not api_key:
        raise RuntimeError("Chat temporariamente indisponível.")

    from google import genai
    from google.genai import types
    from google.genai import errors as genai_errors

    contents: list[types.Content] = []
    for turn in history:
        role = "user" if turn["role"] == "user" else "model"
        contents.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=turn["content"])],
            )
        )
    contents.append(
        types.Content(role="user", parts=[types.Part.from_text(text=message)])
    )

    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=persona["system"],
                temperature=0.7,
                max_output_tokens=1024,
            ),
        )
    except genai_errors.ClientError as exc:
        status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        logger.warning("Gemini ClientError status=%s: %s", status, exc)
        if status in {429, 403}:
            raise RuntimeError("Chat temporariamente indisponível.") from exc
        raise RuntimeError("Falha ao gerar resposta.") from exc

    text = ""
    try:
        text = (response.text or "").strip()
    except Exception:
        text = ""

    if not text and response.candidates:
        parts = []
        for candidate in response.candidates:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", None) or []:
                part_text = getattr(part, "text", None)
                if part_text:
                    parts.append(part_text)
        text = "\n".join(parts).strip()

    if not text:
        raise RuntimeError("Resposta vazia do modelo.")
    return text
