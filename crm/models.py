from django.db import models


class Lead(models.Model):
    class Status(models.TextChoices):
        NOVO = "novo", "Novo"
        CONTATADO = "contatado", "Contatado"
        QUALIFICADO = "qualificado", "Qualificado"
        ARQUIVADO = "arquivado", "Arquivado"

    class Origem(models.TextChoices):
        HIRE_MODAL = "hire_modal", "Modal Contratar"
        CONTATO = "contato", "Seção Contato"
        OUTRO = "outro", "Outro"

    nome = models.CharField("Nome", max_length=120)
    email = models.EmailField("E-mail")
    telefone = models.CharField("Telefone", max_length=30, blank=True)
    mensagem = models.TextField("Mensagem")
    origem = models.CharField(
        "Origem",
        max_length=32,
        choices=Origem.choices,
        default=Origem.CONTATO,
    )
    status = models.CharField(
        "Status",
        max_length=32,
        choices=Status.choices,
        default=Status.NOVO,
    )
    created_at = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Lead"
        verbose_name_plural = "Leads"

    def __str__(self) -> str:
        return f"{self.nome} <{self.email}>"
