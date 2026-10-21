from django.conf import settings
from django.db import models


class Cobranca(models.TextChoices):
    UNICO = "unico", "Único"
    MENSAL = "mensal", "Mensal"
    ANUAL = "anual", "Anual"


class Servico(models.Model):
    nome = models.CharField("nome", max_length=160, unique=True)
    descricao = models.TextField("descrição", blank=True)
    preco = models.DecimalField("preço", max_digits=10, decimal_places=2, default=0)
    cobranca = models.CharField(
        "cobrança",
        max_length=10,
        choices=Cobranca.choices,
        default=Cobranca.UNICO,
    )
    complemento = models.BooleanField(
        "avulso",
        default=False,
        help_text="Pode entrar em qualquer proposta, além do pacote.",
    )
    ativo = models.BooleanField("ativo", default=True)
    ordem = models.PositiveIntegerField("ordem", default=0)

    class Meta:
        verbose_name = "serviço"
        verbose_name_plural = "serviços"
        ordering = ["ordem", "nome"]

    def __str__(self) -> str:
        return self.nome


class Pacote(models.Model):
    nome = models.CharField("nome", max_length=160, unique=True)
    resumo = models.TextField("resumo", blank=True)
    preco = models.DecimalField("preço de tabela", max_digits=10, decimal_places=2, default=0)
    cobranca = models.CharField(
        "cobrança",
        max_length=10,
        choices=Cobranca.choices,
        default=Cobranca.UNICO,
    )
    piso = models.BooleanField(
        "preço mínimo",
        default=False,
        help_text="O valor é um piso. A proposta diz “a partir de”.",
    )
    ativo = models.BooleanField("ativo", default=True)
    ordem = models.PositiveIntegerField("ordem", default=0)

    class Meta:
        verbose_name = "pacote"
        verbose_name_plural = "pacotes"
        ordering = ["ordem", "nome"]

    def __str__(self) -> str:
        return self.nome


class ItemPacote(models.Model):
    pacote = models.ForeignKey(Pacote, related_name="itens", on_delete=models.CASCADE)
    servico = models.ForeignKey(Servico, related_name="pacotes", on_delete=models.PROTECT)
    incluso = models.BooleanField("incluso no preço", default=True)
    ordem = models.PositiveIntegerField("ordem", default=0)

    class Meta:
        verbose_name = "item do pacote"
        verbose_name_plural = "itens do pacote"
        ordering = ["ordem", "id"]
        constraints = [
            models.UniqueConstraint(fields=["pacote", "servico"], name="catalogo_servico_unico_no_pacote"),
        ]

    def __str__(self) -> str:
        return f"{self.pacote} · {self.servico}"


class FaixaDesconto(models.Model):
    valor_ate = models.DecimalField(
        "até",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Vazio significa “acima da faixa anterior”.",
    )
    percentual = models.DecimalField("percentual", max_digits=5, decimal_places=4, default=0)
    ordem = models.PositiveIntegerField("ordem", default=0)

    class Meta:
        verbose_name = "faixa de desconto"
        verbose_name_plural = "faixas de desconto"
        ordering = ["ordem", "id"]

    def __str__(self) -> str:
        return f"{self.percentual} até {self.valor_ate or 'o fim'}"


class Proposta(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        FECHADA = "fechada", "Fechada"

    cliente = models.ForeignKey(
        "crm.Cliente",
        related_name="propostas",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    cliente_nome = models.CharField("cliente", max_length=200, blank=True)
    pacote = models.ForeignKey(
        Pacote,
        related_name="propostas",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    pacote_nome = models.CharField("pacote", max_length=160, blank=True)
    piso = models.BooleanField(default=False)
    observacao = models.TextField("observação", blank=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.RASCUNHO,
    )
    desconto_fixo = models.BooleanField("desconto informado à mão", default=False)
    preco_unico = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    desconto_unico = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    total_unico = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    preco_mensal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    desconto_mensal = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    total_mensal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    preco_anual = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    desconto_anual = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    total_anual = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="propostas_criadas",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "proposta"
        verbose_name_plural = "propostas"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.pacote_nome or 'Proposta'} · {self.cliente_nome}"

    @property
    def fechada(self) -> bool:
        return self.status == self.Status.FECHADA


class ItemProposta(models.Model):
    class Tipo(models.TextChoices):
        PACOTE = "pacote", "Pacote"
        ESCOPO = "escopo", "Escopo"
        AVULSO = "avulso", "Avulso"

    proposta = models.ForeignKey(Proposta, related_name="itens", on_delete=models.CASCADE)
    nome = models.CharField(max_length=160)
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.ESCOPO)
    cobranca = models.CharField(max_length=10, choices=Cobranca.choices, default=Cobranca.UNICO)
    preco = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordem", "id"]

    def __str__(self) -> str:
        return self.nome
