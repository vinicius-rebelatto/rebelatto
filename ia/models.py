from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
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


class Agente(models.Model):
    """Uma responsabilidade. O modelo que a executa é só um campo da versão ativa."""

    slug = models.SlugField("Identificador", max_length=80, unique=True)
    nome = models.CharField("Nome", max_length=120)
    responsabilidade = models.TextField("Responsabilidade", blank=True)
    ativo = models.BooleanField("Ativo", default=True)
    sistema = models.BooleanField(
        "Do sistema",
        default=False,
        help_text="Agentes criados pelo sistema, como os chatbots do site, não podem ser excluídos.",
    )
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Agente"
        verbose_name_plural = "Agentes"

    def __str__(self) -> str:
        return self.nome

    @property
    def versao_ativa(self) -> "VersaoAgente | None":
        return self.versoes.filter(ativa=True).order_by("-numero").first()


class VersaoAgente(models.Model):
    agente = models.ForeignKey(Agente, on_delete=models.CASCADE, related_name="versoes")
    numero = models.PositiveIntegerField("Número")
    prompt = models.TextField("Prompt de sistema", blank=True)
    temperatura = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.70"))
    max_tokens = models.PositiveIntegerField("Limite de tokens na resposta", default=1024)
    modelo = models.ForeignKey(
        Modelo,
        verbose_name="Modelo principal",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="versoes_principais",
    )
    modelo_reserva = models.ForeignKey(
        Modelo,
        verbose_name="Modelo reserva",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="versoes_reserva",
    )
    ativa = models.BooleanField("Ativa", default=True)
    created_at = models.DateTimeField("Criada em", auto_now_add=True)

    class Meta:
        ordering = ["-numero"]
        verbose_name = "Versão de agente"
        verbose_name_plural = "Versões de agente"
        constraints = [
            models.UniqueConstraint(fields=["agente", "numero"], name="ia_versao_numero_unico"),
            models.UniqueConstraint(
                fields=["agente"],
                condition=models.Q(ativa=True),
                name="ia_versao_ativa_unica",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.agente} v{self.numero}"


class Execucao(models.Model):
    class Status(models.TextChoices):
        SUCESSO = "sucesso", "Sucesso"
        ERRO = "erro", "Erro"

    class Origem(models.TextChoices):
        PRODUCAO = "producao", "Produção"
        PLAYGROUND = "playground", "Playground"

    agente = models.ForeignKey(Agente, on_delete=models.PROTECT, related_name="execucoes")
    versao = models.ForeignKey(
        VersaoAgente, null=True, blank=True, on_delete=models.SET_NULL, related_name="execucoes"
    )
    modelo = models.ForeignKey(
        Modelo, null=True, blank=True, on_delete=models.SET_NULL, related_name="execucoes"
    )
    credencial = models.ForeignKey(
        Credencial, null=True, blank=True, on_delete=models.SET_NULL, related_name="execucoes"
    )
    origem = models.CharField(max_length=20, choices=Origem.choices, default=Origem.PRODUCAO)
    status = models.CharField(max_length=20, choices=Status.choices)
    tokens_entrada = models.PositiveIntegerField(default=0)
    tokens_saida = models.PositiveIntegerField(default=0)
    tokens_cache_leitura = models.PositiveIntegerField(default=0)
    tokens_cache_escrita = models.PositiveIntegerField(default=0)
    custo_usd = models.DecimalField(max_digits=14, decimal_places=6, default=Decimal("0"))
    latencia_ms = models.PositiveIntegerField(default=0)
    erro = models.TextField(blank=True)
    usou_reserva = models.BooleanField(default=False)
    referencia_tipo = models.CharField(max_length=40, blank=True)
    referencia_id = models.CharField(max_length=64, blank=True)
    entrada = models.TextField(blank=True)
    saida = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Execução"
        verbose_name_plural = "Execuções"
        indexes = [
            models.Index(fields=["-created_at"], name="ia_execucao_data"),
            models.Index(fields=["agente", "-created_at"], name="ia_execucao_agente_data"),
        ]

    def __str__(self) -> str:
        return f"Execução {self.pk} — {self.agente}"

    @property
    def feedback(self) -> "Avaliacao | None":
        try:
            return self.avaliacao
        except ObjectDoesNotExist:
            return None


class Avaliacao(models.Model):
    class Nota(models.TextChoices):
        POSITIVA = "positiva", "Boa"
        NEGATIVA = "negativa", "Ruim"

    execucao = models.OneToOneField(Execucao, on_delete=models.CASCADE, related_name="avaliacao")
    nota = models.CharField(max_length=20, choices=Nota.choices)
    comentario = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Avaliação"
        verbose_name_plural = "Avaliações"

    def __str__(self) -> str:
        return f"{self.get_nota_display()} em {self.execucao_id}"


class Orcamento(models.Model):
    class Escopo(models.TextChoices):
        GLOBAL = "global", "Global"
        PROVEDOR = "provedor", "Provedor"
        AGENTE = "agente", "Agente"

    escopo = models.CharField(max_length=20, choices=Escopo.choices)
    provedor = models.CharField(max_length=20, choices=Provedor.choices, blank=True)
    agente = models.ForeignKey(
        Agente, null=True, blank=True, on_delete=models.CASCADE, related_name="orcamentos"
    )
    teto_usd = models.DecimalField("Teto do mês (US$)", max_digits=10, decimal_places=2)
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["escopo", "provedor", "agente__nome"]
        verbose_name = "Orçamento"
        verbose_name_plural = "Orçamentos"
        constraints = [
            models.UniqueConstraint(
                fields=["escopo"],
                condition=models.Q(escopo="global"),
                name="ia_orcamento_global_unico",
            ),
            models.UniqueConstraint(
                fields=["provedor"],
                condition=models.Q(escopo="provedor"),
                name="ia_orcamento_provedor_unico",
            ),
            models.UniqueConstraint(
                fields=["agente"],
                condition=models.Q(escopo="agente"),
                name="ia_orcamento_agente_unico",
            ),
        ]

    def __str__(self) -> str:
        if self.escopo == self.Escopo.GLOBAL:
            return "Orçamento global"
        if self.escopo == self.Escopo.PROVEDOR:
            return f"Orçamento {self.get_provedor_display()}"
        return f"Orçamento de {self.agente}"


class Alerta(models.Model):
    class Nivel(models.TextChoices):
        P50 = "50", "50%"
        P80 = "80", "80%"
        P95 = "95", "95%"
        PROJECAO = "projecao", "Projeção"
        ESTOURO = "estouro", "Estouro"

    orcamento = models.ForeignKey(Orcamento, on_delete=models.CASCADE, related_name="alertas")
    nivel = models.CharField(max_length=20, choices=Nivel.choices)
    periodo = models.CharField(max_length=7)
    mensagem = models.TextField()
    dia_previsto = models.PositiveSmallIntegerField(null=True, blank=True)
    dispensado = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Alerta"
        verbose_name_plural = "Alertas"
        constraints = [
            models.UniqueConstraint(
                fields=["orcamento", "nivel", "periodo"],
                name="ia_alerta_unico_no_periodo",
            ),
        ]

    def __str__(self) -> str:
        return self.mensagem

    @property
    def tom(self) -> str:
        if self.nivel in {self.Nivel.P95, self.Nivel.ESTOURO}:
            return "danger"
        if self.nivel in {self.Nivel.P80, self.Nivel.PROJECAO}:
            return "warning"
        return ""
