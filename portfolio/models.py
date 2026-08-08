from django.db import models


class Project(models.Model):
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
    destaque = models.BooleanField("Destaque na landing", default=True)
    ordem = models.PositiveIntegerField("Ordem", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

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
