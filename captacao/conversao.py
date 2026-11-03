"""Agente de conversão: responde quem respondeu ao script, com um objetivo só, marcar a reunião."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from ia.gateway import GatewayError, executar
from ia.models import Agente, Modelo, VersaoAgente

from . import evolution, operacao, textos
from .models import Abordagem, Experimento, Mensagem, RespostaPadrao

SLUG = "captacao-conversao"
ESPERA_SEGUNDOS = 45  # o lead costuma mandar várias mensagens seguidas
MAX_RESPOSTAS_IA = 4
PASSAR = "[VOCE]"

PROMPT = """Você é o assistente comercial do Vinícius, da Rebel Tech, conversando pelo WhatsApp com clínicas de estética.

Contexto: a Rebel Tech faz sites, landing pages e sistemas para clínicas. Antes de escrever, montamos de graça uma prévia do site da clínica (o link do mockup está nos dados do lead). A primeira mensagem já foi enviada; agora o lead respondeu.

Seu único objetivo: marcar uma conversa de 20 minutos por vídeo (Google Meet) com o Vinícius, para ele mostrar a prévia e entender o que a clínica precisa.

Regras:
- Escreva como uma pessoa no WhatsApp: 1 a 3 frases curtas, sem listas, sem formalidade excessiva, no máximo um emoji quando fizer sentido.
- Responda primeiro o que o lead perguntou, depois conduza para a conversa.
- Quando o lead topar, pergunte o melhor dia e período (manhã ou tarde). Não confirme horário exato: diga que o Vinícius confirma em seguida.
- Nunca fale preço nem prazo. Se perguntarem, diga que depende do que a clínica precisa e que o Vinícius explica na conversa.
- Não invente fatos sobre a clínica nem sobre a Rebel Tech. Use só os dados do lead abaixo.
- Se perguntarem se é robô ou pessoa, diga que é o assistente do Vinícius e que ele entra na conversa para a reunião.
- Se o lead não tiver interesse, agradeça em uma frase e encerre, sem insistir.
- Se o lead estiver irritado, pedir para falar com uma pessoa, fizer uma pergunta que você não sabe responder com os dados abaixo, ou já tiver dito um dia e horário, responda exatamente [VOCE] e mais nada.

Responda só com o texto da mensagem."""


def garantir_agente() -> Agente:
    agente, _ = Agente.objects.get_or_create(
        slug=SLUG,
        defaults={
            "nome": "Captação: conversão em reunião",
            "responsabilidade": "Responde os leads que responderam ao script e tenta marcar a reunião.",
            "sistema": True,
            "ativo": True,
        },
    )
    if not agente.versoes.exists():
        VersaoAgente.objects.create(
            agente=agente,
            numero=1,
            prompt=PROMPT,
            temperatura=Decimal("0.60"),
            max_tokens=300,
            modelo=_modelo_padrao(),
            ativa=True,
        )
    return agente


def _modelo_padrao() -> Modelo | None:
    habilitados = Modelo.objects.filter(habilitado=True)
    return (
        habilitados.filter(faixa=Modelo.Faixa.EQUILIBRADO).order_by("provedor", "model_id").first()
        or habilitados.filter(faixa=Modelo.Faixa.ECONOMICO).order_by("provedor", "model_id").first()
        or habilitados.order_by("provedor", "model_id").first()
    )


def contexto_do_lead(abordagem: Abordagem) -> str:
    cliente = abordagem.cliente
    campos = textos.campos_do_cliente(cliente)
    linhas = [
        f"Clínica: {campos['empresa']}",
        f"Cidade: {campos['cidade']}" + (f", bairro {campos['bairro']}" if campos["bairro"] else ""),
        f"Categoria: {cliente.get_categoria_lead_display() or '—'} ({cliente.presenca_detalhe or 'sem detalhe'})",
        f"Google: nota {campos['nota_maps'] or '—'}, {campos['avaliacoes'] or '0'} avaliações",
        f"Prévia do site (mockup): {campos['mockup']}",
        f"Site atual: {cliente.website or 'não tem'}",
    ]
    if cliente.dossie:
        linhas.append(f"Dossiê: {cliente.dossie[:800]}")
    linhas.append(f"Primeira mensagem enviada (script {abordagem.variante.letra}): {abordagem.texto_enviado}")
    return "\n".join(linhas)


def historico(abordagem: Abordagem) -> list[dict]:
    mensagens = []
    for item in abordagem.mensagens.order_by("created_at", "id"):
        if not item.texto:
            continue
        papel = "user" if item.direcao == Mensagem.Direcao.ENTRADA else "assistant"
        if mensagens and mensagens[-1]["role"] == papel:
            mensagens[-1]["content"] += "\n" + item.texto
        else:
            mensagens.append({"role": papel, "content": item.texto})
    # A primeira mensagem do script já vai no contexto; a conversa começa no lead.
    while mensagens and mensagens[0]["role"] == "assistant":
        mensagens.pop(0)
    return mensagens


def pendentes(agora=None):
    """Última mensagem recebida de cada conversa que ainda espera resposta da IA."""
    agora = agora or timezone.now()
    candidatas = (
        Mensagem.objects.select_related("abordagem", "abordagem__variante__experimento", "abordagem__cliente")
        .filter(
            direcao=Mensagem.Direcao.ENTRADA,
            sugestao_status="",
            abordagem__isnull=False,
            abordagem__ia_pausada=False,
            abordagem__opt_out_em__isnull=True,
            abordagem__reuniao_marcada_em__isnull=True,
            created_at__gte=agora - timedelta(days=2),
            created_at__lte=agora - timedelta(seconds=ESPERA_SEGUNDOS),
        )
        .exclude(abordagem__variante__experimento__modo_ia=Experimento.ModoIA.DESLIGADO)
        .order_by("created_at")
    )
    vistas: set[int] = set()
    for mensagem in candidatas:
        if mensagem.abordagem_id in vistas:
            continue
        ultima = mensagem.abordagem.mensagens.order_by("-created_at", "-id").first()
        if ultima is None or ultima.pk != mensagem.pk:
            # Chegou outra mensagem ou alguém já respondeu: esta entra junto com a próxima.
            Mensagem.objects.filter(pk=mensagem.pk).update(sugestao_status="agrupada")
            continue
        vistas.add(mensagem.abordagem_id)
        yield mensagem


def respostas_padrao() -> str:
    itens = list(RespostaPadrao.objects.filter(ativa=True).order_by("pergunta")[:40])
    if not itens:
        return ""
    linhas = ["Respostas aprovadas pelo Vinícius para perguntas frequentes (use o conteúdo, adaptando ao tom da conversa):"]
    for item in itens:
        linhas.append(f"- Pergunta: {item.pergunta}\n  Resposta: {item.resposta}")
    return "\n".join(linhas)


def sugerir(mensagem: Mensagem) -> Mensagem:
    abordagem = mensagem.abordagem
    agente = garantir_agente()
    versao = agente.versao_ativa
    sistema = f"{versao.prompt if versao else PROMPT}\n\nDados do lead:\n{contexto_do_lead(abordagem)}"
    padroes = respostas_padrao()
    if padroes:
        sistema += f"\n\n{padroes}"
    try:
        resultado = executar(
            agente,
            [{"role": "system", "content": sistema}, *historico(abordagem)],
            referencia=("abordagem", str(abordagem.pk)),
            usar_prompt_da_versao=False,
        )
    except GatewayError as exc:
        mensagem.sugestao = f"Não consegui gerar a resposta: {exc}"
        mensagem.sugestao_status = "erro"
        mensagem.save(update_fields=["sugestao", "sugestao_status"])
        return mensagem

    texto = (resultado.texto or "").strip()
    respostas_ia = abordagem.mensagens.filter(autor=Mensagem.Autor.IA).count()
    if not texto or PASSAR in texto or respostas_ia >= MAX_RESPOSTAS_IA:
        mensagem.sugestao = "" if PASSAR in texto or not texto else texto
        mensagem.sugestao_status = "passar"
        mensagem.save(update_fields=["sugestao", "sugestao_status"])
        return mensagem

    mensagem.sugestao = texto
    modo = abordagem.variante.experimento.modo_ia
    if modo == Experimento.ModoIA.AUTOMATICO:
        try:
            operacao.enviar_resposta(abordagem, texto, autor=Mensagem.Autor.IA)
            mensagem.sugestao_status = "enviada"
        except evolution.EvolutionError as exc:
            mensagem.sugestao_status = "erro"
            mensagem.sugestao = f"{texto}\n\n(Não enviou: {exc})"
    else:
        mensagem.sugestao_status = "pendente"
    mensagem.save(update_fields=["sugestao", "sugestao_status"])
    return mensagem


def processar_pendentes(limite: int = 5) -> int:
    feitas = 0
    for mensagem in pendentes():
        with transaction.atomic():
            travada = Mensagem.objects.select_for_update().get(pk=mensagem.pk)
            if travada.sugestao_status:
                continue
            travada.sugestao_status = "gerando"
            travada.save(update_fields=["sugestao_status"])
        travada.sugestao_status = ""
        sugerir(travada)
        feitas += 1
        if feitas >= limite:
            break
    return feitas
