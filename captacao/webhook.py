"""Eventos que a Evolution API manda: conexão, QR code, mensagens e tiques."""

from __future__ import annotations

from django.utils import timezone

from . import operacao, textos
from .models import Abordagem, Mensagem, NumeroWhatsApp

STATUS_ENTREGUE = {"DELIVERY_ACK", "DELIVERED", "3"}
STATUS_LIDA = {"READ", "PLAYED", "4", "5"}


def processar(payload: dict) -> str:
    evento = str(payload.get("event") or "").lower().replace("_", ".")
    numero = NumeroWhatsApp.objects.filter(instancia=payload.get("instance") or "").first()
    if numero is None:
        return "instancia desconhecida"
    dados = payload.get("data")
    if evento == "connection.update":
        return _conexao(numero, dados or {})
    if evento == "qrcode.updated":
        return _qrcode(numero, dados or {})
    if evento in ("messages.upsert", "send.message"):
        itens = dados if isinstance(dados, list) else [dados or {}]
        for item in itens:
            if isinstance(item, dict):
                _mensagem(numero, item)
        return "mensagem"
    if evento == "messages.update":
        itens = dados if isinstance(dados, list) else [dados or {}]
        for item in itens:
            if isinstance(item, dict):
                _status(item)
        return "status"
    return "ignorado"


def _conexao(numero: NumeroWhatsApp, dados: dict) -> str:
    estado = str(dados.get("state") or "").lower()
    agora = timezone.now()
    if estado == "open":
        numero.conexao = NumeroWhatsApp.Conexao.CONECTADO
        numero.conectado_em = agora
        numero.qr_code = ""
        numero.codigo_pareamento = ""
    elif estado == "connecting":
        numero.conexao = NumeroWhatsApp.Conexao.CONECTANDO
    elif estado == "close":
        numero.conexao = NumeroWhatsApp.Conexao.DESCONECTADO
    numero.save()
    return estado


def _qrcode(numero: NumeroWhatsApp, dados: dict) -> str:
    qr = dados.get("qrcode") if isinstance(dados.get("qrcode"), dict) else dados
    numero.qr_code = str(qr.get("base64") or "")
    numero.codigo_pareamento = str(qr.get("pairingCode") or "")[:20]
    numero.qr_atualizado_em = timezone.now()
    if numero.conexao != NumeroWhatsApp.Conexao.CONECTADO:
        numero.conexao = NumeroWhatsApp.Conexao.PENDENTE
    numero.save()
    return "qrcode"


def texto_da_mensagem(mensagem: dict) -> tuple[str, str]:
    if not isinstance(mensagem, dict):
        return "", ""
    if mensagem.get("conversation"):
        return str(mensagem["conversation"]), "texto"
    extendido = mensagem.get("extendedTextMessage") or {}
    if extendido.get("text"):
        return str(extendido["text"]), "texto"
    for tipo, rotulo in (
        ("imageMessage", "imagem"),
        ("videoMessage", "vídeo"),
        ("documentMessage", "documento"),
    ):
        if tipo in mensagem:
            legenda = (mensagem[tipo] or {}).get("caption") or ""
            return (legenda or f"[{rotulo}]"), rotulo
    if "audioMessage" in mensagem:
        return "[áudio]", "audio"
    if "stickerMessage" in mensagem:
        return "[figurinha]", "figurinha"
    if "reactionMessage" in mensagem:
        return str((mensagem["reactionMessage"] or {}).get("text") or ""), "reacao"
    return "", "outro"


def _telefones_possiveis(chave: dict, dados: dict) -> list[str]:
    candidatos = [
        chave.get("remoteJid"),
        chave.get("senderPn"),
        chave.get("remoteJidAlt"),
        chave.get("participantAlt"),
        dados.get("senderPn"),
    ]
    telefones = []
    for jid in candidatos:
        if not jid:
            continue
        jid = str(jid)
        telefone = textos.telefone_do_jid(jid if "@" in jid else f"{jid}@s.whatsapp.net")
        if telefone:
            telefones.append(telefone)
    return telefones


def _achar_abordagem(numero: NumeroWhatsApp, chave: dict, dados: dict) -> Abordagem | None:
    jid = str(chave.get("remoteJid") or "")
    if jid:
        achada = Abordagem.objects.filter(jid=jid).order_by("-enviada_em").first()
        if achada:
            return achada
    for telefone in _telefones_possiveis(chave, dados):
        achada = (
            Abordagem.objects.filter(chave_telefone=textos.chave_telefone(telefone))
            .order_by("-enviada_em")
            .first()
        )
        if achada:
            if jid and not achada.jid:
                achada.jid = jid
                achada.save(update_fields=["jid", "updated_at"])
            return achada
    return None


def _mensagem(numero: NumeroWhatsApp, dados: dict) -> None:
    chave = dados.get("key") or {}
    jid = str(chave.get("remoteJid") or "")
    if not jid or jid.endswith("@g.us") or jid.startswith("status@") or jid.endswith("@newsletter"):
        return
    whatsapp_id = str(chave.get("id") or "")
    if whatsapp_id and Mensagem.objects.filter(whatsapp_id=whatsapp_id).exists():
        return
    texto, tipo = texto_da_mensagem(dados.get("message") or {})
    if not texto and tipo in ("outro", "reacao"):
        return
    abordagem = _achar_abordagem(numero, chave, dados)
    if abordagem is None:
        return  # conversa que não veio da captação: fica só no celular
    de_mim = bool(chave.get("fromMe"))
    Mensagem.objects.create(
        abordagem=abordagem,
        numero=numero,
        direcao=Mensagem.Direcao.SAIDA if de_mim else Mensagem.Direcao.ENTRADA,
        autor=Mensagem.Autor.CELULAR if de_mim else Mensagem.Autor.LEAD,
        texto=texto,
        tipo=tipo,
        whatsapp_id=whatsapp_id,
        jid=jid,
        status=str(dados.get("status") or ""),
    )
    if de_mim:
        return
    agora = timezone.now()
    campos = ["updated_at"]
    if abordagem.respondeu_em is None:
        abordagem.respondeu_em = agora
        campos.append("respondeu_em")
    if abordagem.entregue_em is None:
        abordagem.entregue_em = agora
        campos.append("entregue_em")
    if abordagem.lida_em is None:
        abordagem.lida_em = agora
        campos.append("lida_em")
    abordagem.save(update_fields=campos)
    if textos.pediu_para_sair(texto):
        operacao.registrar_opt_out(abordagem.telefone, motivo=texto)


def _status(dados: dict) -> None:
    whatsapp_id = str(dados.get("keyId") or dados.get("messageId") or (dados.get("key") or {}).get("id") or "")
    status = str(dados.get("status") or (dados.get("update") or {}).get("status") or "").upper()
    if not whatsapp_id or not status:
        return
    mensagem = Mensagem.objects.filter(whatsapp_id=whatsapp_id).select_related("abordagem").first()
    if mensagem is None:
        return
    mensagem.status = status
    mensagem.save(update_fields=["status"])
    abordagem = mensagem.abordagem
    if abordagem is None or mensagem.autor != Mensagem.Autor.SCRIPT:
        return
    agora = timezone.now()
    campos = []
    if status in STATUS_ENTREGUE | STATUS_LIDA and abordagem.entregue_em is None:
        abordagem.entregue_em = agora
        campos.append("entregue_em")
    if status in STATUS_LIDA and abordagem.lida_em is None:
        abordagem.lida_em = agora
        campos.append("lida_em")
    if campos:
        abordagem.save(update_fields=[*campos, "updated_at"])
