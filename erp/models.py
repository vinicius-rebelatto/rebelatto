from django.db import models
from django.utils import timezone


class Tarefa(models.Model):
    """Uma ação que precisa ser feita para a operação andar."""

    class Status(models.TextChoices):
        A_FAZER = "a_fazer", "A fazer"
        FAZENDO = "fazendo", "Fazendo"
        AGUARDANDO = "aguardando", "Aguardando"
        FEITA = "feita", "Feita"

    class Prioridade(models.IntegerChoices):
        ALTA = 1, "Alta"
        MEDIA = 2, "Média"
        BAIXA = 3, "Baixa"

    class Frente(models.TextChoices):
        CAPTACAO = "captacao", "Captação"
        OPERACAO = "operacao", "Operação"
        SISTEMA = "sistema", "Sistema"
        IA = "ia", "IA"
        COMERCIAL = "comercial", "Comercial"
        OUTRA = "outra", "Outra"

    titulo = models.CharField("Tarefa", max_length=200)
    descricao = models.TextField("Detalhes", blank=True)
    status = models.CharField("Status", max_length=20, choices=Status.choices, default=Status.A_FAZER)
    prioridade = models.PositiveSmallIntegerField(
        "Prioridade", choices=Prioridade.choices, default=Prioridade.MEDIA
    )
    frente = models.CharField("Frente", max_length=20, choices=Frente.choices, default=Frente.CAPTACAO)
    prazo = models.DateField("Prazo", null=True, blank=True)
    concluida_em = models.DateTimeField("Concluída em", null=True, blank=True)
    created_at = models.DateTimeField("Criada em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizada em", auto_now=True)

    class Meta:
        ordering = ["prioridade", models.F("prazo").asc(nulls_last=True), "created_at"]
        verbose_name = "Tarefa"
        verbose_name_plural = "Tarefas"

    def __str__(self) -> str:
        return self.titulo

    @property
    def aberta(self) -> bool:
        return self.status != self.Status.FEITA

    @property
    def atrasada(self) -> bool:
        return self.aberta and self.prazo is not None and self.prazo < timezone.localdate()

    @property
    def vence_hoje(self) -> bool:
        return self.aberta and self.prazo == timezone.localdate()

    def save(self, *args, **kwargs):
        if self.status == self.Status.FEITA:
            if self.concluida_em is None:
                self.concluida_em = timezone.now()
        else:
            self.concluida_em = None
        super().save(*args, **kwargs)
