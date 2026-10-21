from decimal import Decimal

from django.db import models

from .crypto import cifrar, decifrar


class Provedor(models.TextChoices):
    ANTHROPIC = "anthropic", "Anthropic (Claude)"
    GOOGLE = "google", "Google (Gemini)"
    XAI = "xai", "xAI (Grok)"
    OPENAI = "openai", "OpenAI (GPT)"


def _sufixo(valor: str) -> str:
    return valor.strip()[-4:]


class Credencial(models.Model):
    class Status(models.TextChoices):
        VALIDA = "valida", "Válida"
        INVALIDA = "invalida", "Inválida"

    provedor = models.CharField("Provedor", max_length=20, choices=Provedor.choices)
    apelido = models.CharField("Apelido", max_length=80)
    chave_cifrada = models.TextField("Chave (cifrada)")
    chave_sufixo = models.CharField("Final da chave", max_length=8)
    admin_cifrada = models.TextField("Chave admin (cifrada)", blank=True)
    admin_sufixo = models.CharField("Final da chave admin", max_length=8, blank=True)
    ativa = models.BooleanField("Ativa", default=True)
    status = models.CharField(
        "Status",
        max_length=20,
        choices=Status.choices,
        default=Status.VALIDA,
    )
    ultimo_teste_em = models.DateTimeField("Último teste", null=True, blank=True)
    ultimo_erro = models.TextField("Último erro", blank=True)
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        ordering = ["provedor", "apelido"]
        verbose_name = "Credencial de IA"
        verbose_name_plural = "Credenciais de IA"
        constraints = [
            models.UniqueConstraint(fields=["provedor", "apelido"], name="ia_credencial_apelido_unico"),
        ]

    def __str__(self) -> str:
        return f"{self.get_provedor_display()} — {self.apelido}"

    @property
    def chave(self) -> str:
        return decifrar(self.chave_cifrada)

    @property
    def chave_admin(self) -> str:
        return decifrar(self.admin_cifrada) if self.admin_cifrada else ""

    @property
    def tem_admin(self) -> bool:
        return bool(self.admin_cifrada)

    def definir_chave(self, valor: str) -> None:
        self.chave_cifrada = cifrar(valor.strip())
        self.chave_sufixo = _sufixo(valor)

    def definir_chave_admin(self, valor: str) -> None:
        if valor.strip():
            self.admin_cifrada = cifrar(valor.strip())
            self.admin_sufixo = _sufixo(valor)
        else:
            self.admin_cifrada = ""
            self.admin_sufixo = ""


class Modelo(models.Model):
    class Faixa(models.TextChoices):
        ECONOMICO = "economico", "Econômico"
        EQUILIBRADO = "equilibrado", "Equilibrado"
        PREMIUM = "premium", "Premium"

    class FontePreco(models.TextChoices):
        LITELLM = "litellm", "LiteLLM"
        MANUAL = "manual", "Manual"

    provedor = models.CharField("Provedor", max_length=20, choices=Provedor.choices)
    model_id = models.CharField("ID do modelo", max_length=160)
    nome = models.CharField("Nome", max_length=160, blank=True)
    credenciais = models.ManyToManyField(
        Credencial,
        related_name="modelos",
        blank=True,
        verbose_name="Disponível nas chaves",
    )
    habilitado = models.BooleanField("Habilitado", default=False)

    preco_entrada = models.DecimalField(
        "Entrada (US$/1M tokens)", max_digits=12, decimal_places=4, null=True, blank=True
    )
    preco_saida = models.DecimalField(
        "Saída (US$/1M tokens)", max_digits=12, decimal_places=4, null=True, blank=True
    )
    preco_cache_leitura = models.DecimalField(
        "Leitura de cache (US$/1M tokens)", max_digits=12, decimal_places=4, null=True, blank=True
    )
    preco_cache_escrita = models.DecimalField(
        "Escrita de cache (US$/1M tokens)", max_digits=12, decimal_places=4, null=True, blank=True
    )
    fonte_preco = models.CharField(
        "Fonte do preço", max_length=20, choices=FontePreco.choices, blank=True
    )
    preco_atualizado_em = models.DateTimeField("Preço atualizado em", null=True, blank=True)

    contexto_max = models.PositiveIntegerField("Contexto máximo (tokens)", null=True, blank=True)
    saida_max = models.PositiveIntegerField("Saída máxima (tokens)", null=True, blank=True)
    suporta_visao = models.BooleanField("Lê imagens", default=False)
    suporta_ferramentas = models.BooleanField("Usa ferramentas", default=False)
    faixa = models.CharField("Faixa", max_length=20, choices=Faixa.choices, blank=True)

    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        ordering = ["provedor", "model_id"]
        verbose_name = "Modelo de IA"
        verbose_name_plural = "Modelos de IA"
        constraints = [
            models.UniqueConstraint(fields=["provedor", "model_id"], name="ia_modelo_unico"),
        ]

    def __str__(self) -> str:
        return self.nome or self.model_id

    @property
    def tem_preco(self) -> bool:
        return self.preco_entrada is not None and self.preco_saida is not None

    @staticmethod
    def faixa_por_preco(preco_saida: Decimal | None) -> str:
        if preco_saida is None:
            return ""
        if preco_saida < Decimal("5"):
            return Modelo.Faixa.ECONOMICO
        if preco_saida < Decimal("15"):
            return Modelo.Faixa.EQUILIBRADO
        return Modelo.Faixa.PREMIUM
