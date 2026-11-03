"""Classifica o que os leads escrevem (intenção, temas, pergunta, objeção) e resume para análise."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from ia.gateway import GatewayError, executar
from ia.models import Agente, Modelo, VersaoAgente

from .models import Mensagem

SLUG = "captacao-triagem"
INTENCOES = {
    "interessado": "Interessado",
    "quer_reuniao": "Quer marcar a conversa",
    "pergunta": "Fez uma pergunta",
    "objecao": "Levantou uma objeção",
    "sem_interesse": "Sem interesse",
    "pediu_para_sair": "Pediu para sair",
    "ja_tem_fornecedor": "Já tem quem faça",
    "outro": "Outro",
}
TEMAS_SUGERIDOS = [
    "preco", "portfolio", "prazo", "como_funciona", "quem_e_voce", "ja_tem_site", "instagram_basta",
    "sem_tempo", "sem_dinheiro", "agendamento_online", "confianca", "mockup", "dono_decide", "outro",
]

PROMPT = f"""Você classifica mensagens de clínicas de estética que receberam uma abordagem comercial da Rebel Tech (sites e sistemas) pelo WhatsApp.

Responda só com um JSON, sem texto antes ou depois, neste formato:
{{"intencao": "...", "temas": ["..."], "pergunta": "...", "objecao": "..."}}

- intencao: uma destas: {", ".join(INTENCOES)}.
- temas: de 1 a 3 temas curtos em snake_case. Prefira estes: {", ".join(TEMAS_SUGERIDOS)}. Crie outro só se nenhum servir.
- pergunta: se o lead perguntou algo, reescreva a pergunta de forma curta e genérica, sem nomes (ex.: "Quanto custa um site?", "Vocês têm outros trabalhos para mostrar?"). Senão, "".
- objecao: se o lead deu um motivo para não seguir, resuma em poucas palavras (ex.: "Já tem site", "Sem orçamento agora"). Senão, ""."""


def garantir_agente() -> Agente:
    agente, _ = Agente.objects.get_or_create(
        slug=SLUG,
        defaults={
            "nome": "Captação: triagem de respostas",
            "responsabilidade": "Classifica intenção, temas, perguntas e objeções das mensagens dos leads.",
            "sistema": True,
            "ativo": True,
        },
    )
    if not agente.versoes.exists():
        habilitados = Modelo.objects.filter(habilitado=True)
        modelo = (
            habilitados.filter(faixa=Modelo.Faixa.ECONOMICO).order_by("provedor", "model_id").first()
            or habilitados.order_by("provedor", "model_id").first()
        )
        VersaoAgente.objects.create(
            agente=agente, numero=1, prompt=PROMPT, temperatura=Decimal("0.10"), max_tokens=250, modelo=modelo, ativa=True
        )
    return agente


def _ler_json(texto: str) -> dict:
    achado = re.search(r"\{.*\}", texto or "", re.S)
    if not achado:
        return {}
    try:
        dados = json.loads(achado.group(0))
    except ValueError:
        return {}
    return dados if isinstance(dados, dict) else {}


def _tema(valor) -> str:
    sem_acento = unicodedata.normalize("NFKD", str(valor or "")).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^a-z0-9_]+", "_", sem_acento.strip().lower()).strip("_")
    return texto[:40]


def classificar(mensagem: Mensagem) -> Mensagem:
    agente = garantir_agente()
    anteriores = list(
        mensagem.abordagem.mensagens.filter(created_at__lte=mensagem.created_at).exclude(pk=mensagem.pk).order_by("-created_at")[:4]
    ) if mensagem.abordagem_id else []
    contexto = "\n".join(
        f"{'Lead' if m.direcao == Mensagem.Direcao.ENTRADA else 'Rebel Tech'}: {m.texto}" for m in reversed(anteriores)
    )
    conteudo = (f"Conversa até aqui:\n{contexto}\n\n" if contexto else "") + f"Mensagem do lead para classificar:\n{mensagem.texto}"
    try:
        resultado = executar(agente, [{"role": "user", "content": conteudo}], referencia=("mensagem", str(mensagem.pk)))
    except GatewayError:
        mensagem.intencao = "erro"
        mensagem.classificada_em = timezone.now()
        mensagem.save(update_fields=["intencao", "classificada_em"])
        return mensagem
    dados = _ler_json(resultado.texto)
    intencao = str(dados.get("intencao") or "outro")
    mensagem.intencao = intencao if intencao in INTENCOES else "outro"
    temas = dados.get("temas") if isinstance(dados.get("temas"), list) else []
    mensagem.temas = [t for t in (_tema(t) for t in temas[:3]) if t]
    mensagem.pergunta = str(dados.get("pergunta") or "").strip()[:300]
    mensagem.objecao = str(dados.get("objecao") or "").strip()[:300]
    mensagem.classificada_em = timezone.now()
    mensagem.save(update_fields=["intencao", "temas", "pergunta", "objecao", "classificada_em"])
    return mensagem


def classificar_pendentes(limite: int = 10) -> int:
    pendentes = Mensagem.objects.filter(
        direcao=Mensagem.Direcao.ENTRADA,
        classificada_em__isnull=True,
        created_at__gte=timezone.now() - timedelta(days=30),
    ).exclude(texto="").order_by("created_at")[:limite]
    feitas = 0
    for mensagem in pendentes:
        classificar(mensagem)
        feitas += 1
    return feitas


def _normalizar(texto: str) -> str:
    return re.sub(r"[^\w\s]", "", (texto or "").lower()).strip()


def resumo(qs=None) -> dict:
    """Contagens para a tela de insights: intenções, temas, perguntas e objeções mais comuns."""
    qs = qs if qs is not None else Mensagem.objects.all()
    mensagens = list(
        qs.filter(direcao=Mensagem.Direcao.ENTRADA, classificada_em__isnull=False)
        .exclude(intencao="erro")
        .select_related("abordagem__variante")
    )
    intencoes = Counter(m.intencao for m in mensagens)
    temas = Counter(t for m in mensagens for t in (m.temas or []))
    temas_por_script: dict[str, Counter] = {}
    for m in mensagens:
        letra = m.abordagem.variante.letra if m.abordagem_id else "?"
        temas_por_script.setdefault(letra, Counter()).update(m.temas or [])

    def agrupar(campo: str):
        grupos: dict[str, dict] = {}
        for m in mensagens:
            valor = getattr(m, campo)
            if not valor:
                continue
            chave = _normalizar(valor)
            grupo = grupos.setdefault(chave, {"texto": valor, "total": 0, "exemplos": []})
            grupo["total"] += 1
            if len(grupo["exemplos"]) < 3:
                grupo["exemplos"].append(m)
        return sorted(grupos.values(), key=lambda g: -g["total"])

    return {
        "total": len(mensagens),
        "intencoes": [(INTENCOES.get(k, k), v) for k, v in intencoes.most_common()],
        "temas": temas.most_common(20),
        "temas_por_script": {k: dict(v) for k, v in sorted(temas_por_script.items())},
        "perguntas": agrupar("pergunta")[:30],
        "objecoes": agrupar("objecao")[:30],
    }
