"""Única porta de saída para os provedores de IA.

Os outros módulos chamam ``executar``. O gateway escolhe o modelo, aplica o
teto, fala com o provedor pelo LiteLLM, calcula o custo pela tabela do banco
e grava a execução.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from decimal import Decimal

from .crypto import CryptoError
from .models import Agente, Credencial, Execucao, Modelo, VersaoAgente
from .orcamento import atualizar_alertas, orcamentos_estourados

logger = logging.getLogger(__name__)

MILHAO = Decimal("1_000_000")
PREFIXOS_LITELLM = {
    "anthropic": "anthropic/",
    "google": "gemini/",
    "xai": "xai/",
    "openai": "openai/",
}
PAPEIS = {"system": "system", "user": "user", "assistant": "assistant", "model": "assistant"}


class GatewayError(Exception):
    def __init__(self, message: str, execucao: Execucao | None = None):
        super().__init__(message)
        self.execucao = execucao


@dataclass
class Resultado:
    texto: str
    execucao: Execucao
    usou_reserva: bool


@dataclass
class _Uso:
    texto: str
    entrada: int
    saida: int
    cache_leitura: int
    cache_escrita: int


def calcular_custo(
    modelo: Modelo,
    entrada: int,
    saida: int,
    cache_leitura: int = 0,
    cache_escrita: int = 0,
) -> Decimal:
    """Custo em dólar, congelado com o preço do modelo no momento da chamada.

    Tokens de cache sem preço próprio entram como tokens de entrada, para o
    histórico não subestimar o gasto.
    """

    def parte(tokens: int, preco: Decimal | None) -> Decimal:
        if not tokens or preco is None:
            return Decimal("0")
        return Decimal(tokens) * Decimal(preco) / MILHAO

    entrada_cobrada = entrada
    if cache_leitura and modelo.preco_cache_leitura is None:
        entrada_cobrada += cache_leitura
        cache_leitura = 0
    if cache_escrita and modelo.preco_cache_escrita is None:
        entrada_cobrada += cache_escrita
        cache_escrita = 0
    total = (
        parte(entrada_cobrada, modelo.preco_entrada)
        + parte(saida, modelo.preco_saida)
        + parte(cache_leitura, modelo.preco_cache_leitura)
        + parte(cache_escrita, modelo.preco_cache_escrita)
    )
    return total.quantize(Decimal("0.000001"))


def limpar_erro(exc: Exception, chave: str = "") -> str:
    texto = " ".join((str(exc) or exc.__class__.__name__).split())
    if chave:
        texto = texto.replace(chave, "••••")
    return texto[:1500] or "Falha ao chamar o modelo."


def nome_litellm(modelo: Modelo) -> str:
    prefixo = PREFIXOS_LITELLM[modelo.provedor]
    if modelo.model_id.startswith(prefixo):
        return modelo.model_id
    return prefixo + modelo.model_id


def executar(
    agente: str | Agente,
    mensagens: list[dict],
    *,
    referencia: tuple[str, str] | None = None,
    origem: str = Execucao.Origem.PRODUCAO,
    modelo: Modelo | None = None,
    usar_prompt_da_versao: bool = True,
    fallback_erro: bool = True,
    respeitar_orcamento: bool = True,
    permitir_inativo: bool = False,
) -> Resultado:
    """Chama o modelo do agente e grava a execução.

    ``modelo`` troca o modelo só nesta chamada (o playground). Com o teto
    estourado, a chamada desce para o modelo reserva e um alerta é gravado.
    Se o provedor falhar, o reserva também é tentado, salvo quando
    ``fallback_erro`` é falso.
    """
    registro = _resolver_agente(agente)
    if not registro.ativo and not permitir_inativo:
        raise GatewayError(f"O agente {registro.nome} está desativado.")
    versao = registro.versao_ativa
    if versao is None:
        raise GatewayError(f"O agente {registro.nome} não tem uma versão ativa.")

    principal = modelo or versao.modelo
    if principal is None:
        raise GatewayError(f"Escolha um modelo principal para {registro.nome}.")
    reserva = None if modelo is not None else versao.modelo_reserva
    if reserva is not None and reserva.pk == principal.pk:
        reserva = None

    enviadas = _normalizar(mensagens)
    if usar_prompt_da_versao and versao.prompt.strip() and not any(item["role"] == "system" for item in enviadas):
        enviadas = [{"role": "system", "content": versao.prompt}, *enviadas]

    referencia_tipo, referencia_id = _referencia(referencia)
    usou_reserva = False
    escolhido = principal

    if respeitar_orcamento:
        estourados = orcamentos_estourados(registro, principal)
        if estourados:
            atualizar_alertas(registro, principal)
            if reserva is not None:
                escolhido = reserva
                usou_reserva = True
            else:
                execucao = _gravar(
                    registro, versao, principal, None, origem, Execucao.Status.ERRO,
                    _Uso("", 0, 0, 0, 0), Decimal("0"), 0,
                    "Orçamento do mês estourou e este agente não tem modelo reserva.",
                    False, referencia_tipo, referencia_id, enviadas,
                )
                raise GatewayError(
                    "Orçamento do mês estourou e este agente não tem modelo reserva.",
                    execucao,
                )

    try:
        resultado = _tentar(
            registro, versao, escolhido, enviadas, origem, usou_reserva,
            referencia_tipo, referencia_id, versao.temperatura, versao.max_tokens,
        )
    except GatewayError:
        if not (fallback_erro and reserva is not None and reserva.pk != escolhido.pk):
            atualizar_alertas(registro, escolhido)
            raise
        try:
            resultado = _tentar(
                registro, versao, reserva, enviadas, origem, True,
                referencia_tipo, referencia_id, versao.temperatura, versao.max_tokens,
            )
        except GatewayError:
            atualizar_alertas(registro, reserva)
            raise

    atualizar_alertas(registro, resultado.execucao.modelo or escolhido)
    return resultado


def _resolver_agente(agente: str | Agente) -> Agente:
    if isinstance(agente, Agente):
        return agente
    try:
        return Agente.objects.get(slug=agente)
    except Agente.DoesNotExist as exc:
        raise GatewayError(f"Agente “{agente}” não existe.") from exc


def _normalizar(mensagens: list[dict]) -> list[dict]:
    if not isinstance(mensagens, list) or not mensagens:
        raise GatewayError("Nenhuma mensagem para enviar.")
    saida = []
    for item in mensagens:
        if not isinstance(item, dict):
            raise GatewayError("Cada mensagem precisa ter papel e conteúdo.")
        papel = PAPEIS.get(str(item.get("role") or ""))
        if papel is None:
            raise GatewayError("Papel de mensagem inválido.")
        conteudo = item.get("content")
        if not isinstance(conteudo, str) or not conteudo.strip():
            raise GatewayError("Mensagem sem conteúdo.")
        saida.append({"role": papel, "content": conteudo})
    return saida


def _referencia(referencia: tuple[str, str] | None) -> tuple[str, str]:
    if not referencia:
        return "", ""
    return str(referencia[0])[:40], str(referencia[1])[:64]


def _tentar(
    agente: Agente,
    versao: VersaoAgente,
    modelo: Modelo,
    mensagens: list[dict],
    origem: str,
    usou_reserva: bool,
    referencia_tipo: str,
    referencia_id: str,
    temperatura: Decimal,
    max_tokens: int,
) -> Resultado:
    inicio = time.perf_counter()
    try:
        uso = _chamar(modelo, mensagens, temperatura, max_tokens)
    except GatewayError as exc:
        latencia = _latencia(inicio)
        execucao = _gravar(
            agente, versao, modelo, _credencial_ou_nada(modelo), origem, Execucao.Status.ERRO,
            _Uso("", 0, 0, 0, 0), Decimal("0"), latencia, str(exc), usou_reserva,
            referencia_tipo, referencia_id, mensagens,
        )
        raise GatewayError(str(exc), execucao) from exc

    latencia = _latencia(inicio)
    custo = calcular_custo(modelo, uso.entrada, uso.saida, uso.cache_leitura, uso.cache_escrita)
    if not modelo.tem_preco:
        logger.warning("Modelo %s sem preço; a execução foi custeada como zero.", modelo.model_id)
    if not uso.texto:
        execucao = _gravar(
            agente, versao, modelo, _credencial_ou_nada(modelo), origem, Execucao.Status.ERRO,
            uso, custo, latencia, "O modelo devolveu uma resposta vazia.", usou_reserva,
            referencia_tipo, referencia_id, mensagens,
        )
        raise GatewayError("O modelo devolveu uma resposta vazia.", execucao)
    execucao = _gravar(
        agente, versao, modelo, _credencial_ou_nada(modelo), origem, Execucao.Status.SUCESSO,
        uso, custo, latencia, "", usou_reserva, referencia_tipo, referencia_id, mensagens,
    )
    return Resultado(uso.texto, execucao, usou_reserva)


def _latencia(inicio: float) -> int:
    return max(0, int((time.perf_counter() - inicio) * 1000))


def _credencial_ou_nada(modelo: Modelo) -> Credencial | None:
    try:
        return _credencial(modelo)
    except GatewayError:
        return None


def _credencial(modelo: Modelo) -> Credencial:
    credencial = (
        modelo.credenciais.filter(ativa=True, status=Credencial.Status.VALIDA)
        .order_by("-updated_at")
        .first()
    )
    if credencial is None:
        raise GatewayError(f"Nenhuma chave ativa vinculada a {modelo}.")
    return credencial


def _chamar(modelo: Modelo, mensagens: list[dict], temperatura: Decimal, max_tokens: int) -> _Uso:
    try:
        import litellm
    except ImportError as exc:
        raise GatewayError("A biblioteca LiteLLM não está instalada.") from exc

    credencial = _credencial(modelo)
    try:
        chave = credencial.chave
    except CryptoError as exc:
        raise GatewayError(str(exc)) from exc

    litellm.suppress_debug_info = True
    try:
        resposta = litellm.completion(
            model=nome_litellm(modelo),
            messages=mensagens,
            api_key=chave,
            temperature=float(temperatura),
            max_tokens=max_tokens,
            timeout=45,
            num_retries=0,
            drop_params=True,
        )
    except Exception as exc:
        mensagem = limpar_erro(exc, chave)
        logger.warning("Falha ao chamar %s: %s", modelo.model_id, mensagem)
        raise GatewayError(mensagem) from exc
    return _uso(resposta)


def _uso(resposta) -> _Uso:
    usage = getattr(resposta, "usage", None)

    def ler(obj, chave: str, padrao: int = 0) -> int:
        if obj is None:
            return padrao
        if isinstance(obj, dict):
            valor = obj.get(chave)
        else:
            valor = getattr(obj, chave, None)
        try:
            return int(valor or 0)
        except (TypeError, ValueError):
            return padrao

    prompt = ler(usage, "prompt_tokens")
    saida = ler(usage, "completion_tokens")
    detalhes = usage.get("prompt_tokens_details") if isinstance(usage, dict) else getattr(usage, "prompt_tokens_details", None)
    cache_leitura = ler(detalhes, "cached_tokens")
    cache_escrita = ler(usage, "cache_creation_input_tokens")
    entrada = max(prompt - cache_leitura - cache_escrita, 0)
    return _Uso(_texto(resposta), entrada, saida, cache_leitura, cache_escrita)


def _texto(resposta) -> str:
    choices = getattr(resposta, "choices", None) or []
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", "") if message is not None else ""
    if isinstance(content, list):
        partes = []
        for parte in content:
            if isinstance(parte, dict):
                partes.append(parte.get("text") or "")
            else:
                partes.append(getattr(parte, "text", "") or "")
        return "\n".join(parte for parte in partes if parte).strip()
    return (content or "").strip()


def _gravar(
    agente: Agente,
    versao: VersaoAgente | None,
    modelo: Modelo | None,
    credencial: Credencial | None,
    origem: str,
    status: str,
    uso: _Uso,
    custo: Decimal,
    latencia: int,
    erro: str,
    usou_reserva: bool,
    referencia_tipo: str,
    referencia_id: str,
    mensagens: list[dict],
) -> Execucao:
    return Execucao.objects.create(
        agente=agente,
        versao=versao,
        modelo=modelo,
        credencial=credencial,
        origem=origem,
        status=status,
        tokens_entrada=uso.entrada,
        tokens_saida=uso.saida,
        tokens_cache_leitura=uso.cache_leitura,
        tokens_cache_escrita=uso.cache_escrita,
        custo_usd=custo,
        latencia_ms=latencia,
        erro=erro,
        usou_reserva=usou_reserva,
        referencia_tipo=referencia_tipo,
        referencia_id=referencia_id,
        entrada=json.dumps(mensagens, ensure_ascii=False),
        saida=uso.texto,
    )
