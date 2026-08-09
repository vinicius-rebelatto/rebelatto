from django.db import models


class Project(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        EM_ANDAMENTO = "em_andamento", "Em andamento"
        CONCLUIDO = "concluido", "Concluído"
        PAUSADO = "pausado", "Pausado"
        REJEITADO = "rejeitado", "Rejeitado"

    titulo = models.CharField("Título", max_length=160)
    resumo = models.TextField("Resumo", blank=True)
    stack = models.CharField(
        "Stack",
        max_length=255,
        blank=True,
        help_text="Tecnologias separadas por vírgula",
    )
    url = models.URLField("URL do projeto", blank=True)
    capa = models.ImageField("Capa", upload_to="projects/", blank=True)
    cliente = models.ForeignKey(
        "crm.Cliente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projetos",
        verbose_name="Cliente",
    )
    status = models.CharField(
        "Status",
        max_length=32,
        choices=Status.choices,
        default=Status.RASCUNHO,
    )
    publicado = models.BooleanField(
        "Publicado na landing",
        default=False,
        help_text="Exibe na seção de trabalhos quando o status for em andamento ou concluído.",
    )
    destaque = models.BooleanField(
        "Destaque na landing",
        default=True,
        help_text="Legado — preferir o campo Publicado.",
    )
    ordem = models.PositiveIntegerField("Ordem", default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordem", "-created_at"]
        verbose_name = "Projeto"
        verbose_name_plural = "Projetos"

    def __str__(self) -> str:
        return self.titulo

    def stack_list(self) -> list[str]:
        if not self.stack:
            return []
        return [item.strip() for item in self.stack.split(",") if item.strip()]

    @classmethod
    def landing_queryset(cls):
        return cls.objects.filter(
            publicado=True,
            status__in=[cls.Status.EM_ANDAMENTO, cls.Status.CONCLUIDO],
        )
