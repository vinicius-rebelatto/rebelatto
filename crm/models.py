from django.db import models
from django.utils.text import slugify


class Cliente(models.Model):
    class Status(models.TextChoices):
        IMPORTADO = "importado", "Importado"
        A_PROSPECTAR = "a_prospectar", "A prospectar"
        EM_PROSPECCAO = "em_prospeccao", "Em prospecção"
        CONVERTIDO = "convertido", "Convertido"
        REJEITADO = "rejeitado", "Rejeitado"

    class Origem(models.TextChoices):
        CONTATO = "contato", "Seção Contato"
        CSV = "csv", "Importação CSV"
        MANUAL = "manual", "Manual"

    class EtapaRejeicao(models.TextChoices):
        FILTRAGEM = "filtragem", "Filtragem"
        PROSPECCAO = "prospeccao", "Prospecção"
        ORCAMENTO = "orcamento", "Orçamento"

    nome = models.CharField("Nome", max_length=160, blank=True)
    empresa = models.CharField("Empresa", max_length=200, blank=True)
    slug = models.SlugField("Slug", max_length=220, unique=True)

    email = models.EmailField("E-mail", blank=True)
    telefone = models.CharField("Telefone", max_length=40, blank=True)
    website = models.CharField("Website", max_length=300, blank=True)
    mensagem = models.TextField("Mensagem", blank=True)

    maps_url = models.CharField("URL Maps", blank=True, max_length=500)
    categoria = models.CharField("Categoria", max_length=160, blank=True)
    rua = models.CharField("Rua", max_length=255, blank=True)
    cidade = models.CharField("Cidade", max_length=120, blank=True)
    estado = models.CharField("Estado", max_length=80, blank=True)

    origem = models.CharField(
        "Origem",
        max_length=32,
        choices=Origem.choices,
        default=Origem.MANUAL,
    )
    status = models.CharField(
        "Status",
        max_length=32,
        choices=Status.choices,
        default=Status.A_PROSPECTAR,
    )
    etapa_rejeicao = models.CharField(
        "Etapa da rejeição",
        max_length=32,
        choices=EtapaRejeicao.choices,
        blank=True,
        null=True,
    )
    motivo_rejeicao = models.TextField("Motivo da rejeição", blank=True)
    notas = models.TextField("Notas", blank=True)

    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

    def __str__(self) -> str:
        return self.display_name

    @property
    def display_name(self) -> str:
        return self.empresa or self.nome or self.email or f"Cliente #{self.pk}"

    @classmethod
    def infer_etapa_rejeicao(cls, previous_status: str | None) -> str:
        if previous_status == cls.Status.IMPORTADO:
            return cls.EtapaRejeicao.FILTRAGEM
        return cls.EtapaRejeicao.PROSPECCAO

    def reject(
        self,
        *,
        etapa: str | None = None,
        motivo: str = "",
        save: bool = True,
    ) -> None:
        previous = self.status
        self.status = self.Status.REJEITADO
        self.etapa_rejeicao = etapa or self.infer_etapa_rejeicao(previous)
        if motivo:
            self.motivo_rejeicao = motivo.strip()
        if save:
            self.save(
                update_fields=[
                    "status",
                    "etapa_rejeicao",
                    "motivo_rejeicao",
                    "updated_at",
                ]
            )

    def clear_rejection(self, *, new_status: str, save: bool = True) -> None:
        self.status = new_status
        self.etapa_rejeicao = None
        self.motivo_rejeicao = ""
        if save:
            self.save(
                update_fields=[
                    "status",
                    "etapa_rejeicao",
                    "motivo_rejeicao",
                    "updated_at",
                ]
            )

    def ensure_slug(self) -> None:
        if self.slug:
            return
        base = slugify(self.empresa or self.nome or "cliente")[:180] or "cliente"
        candidate = base
        index = 2
        while Cliente.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
            candidate = f"{base}-{index}"
            index += 1
        self.slug = candidate

    def save(self, *args, **kwargs):
        if not self.slug:
            self.ensure_slug()
        if self.status != self.Status.REJEITADO:
            self.etapa_rejeicao = None
        super().save(*args, **kwargs)


class Mockup(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        PUBLICADO = "publicado", "Publicado"
        ARQUIVADO = "arquivado", "Arquivado"

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="mockups",
        verbose_name="Cliente",
    )
    titulo = models.CharField("Título", max_length=160)
    slug = models.SlugField("Slug", max_length=220, unique=True)
    status = models.CharField(
        "Status",
        max_length=32,
        choices=Status.choices,
        default=Status.RASCUNHO,
    )
    capa = models.ImageField("Capa", upload_to="mockups/", blank=True)
    descricao = models.TextField("Descrição", blank=True)
    preview_url = models.URLField("URL de preview", blank=True)
    notas_internas = models.TextField("Notas internas", blank=True)
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Mockup"
        verbose_name_plural = "Mockups"

    def __str__(self) -> str:
        return self.titulo

    def ensure_slug(self) -> None:
        if self.slug:
            return
        base_source = self.cliente.empresa or self.cliente.nome or self.titulo
        base = slugify(base_source)[:180] or "mockup"
        candidate = base
        index = 2
        while Mockup.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
            candidate = f"{base}-{index}"
            index += 1
        self.slug = candidate

    def save(self, *args, **kwargs):
        if not self.slug:
            self.ensure_slug()
        was_new = self.pk is None
        previous_status = None
        if not was_new:
            previous_status = (
                Mockup.objects.filter(pk=self.pk)
                .values_list("status", flat=True)
                .first()
            )
        super().save(*args, **kwargs)
        if self.status == self.Status.PUBLICADO and (
            was_new or previous_status != self.Status.PUBLICADO
        ):
            if self.cliente.status == Cliente.Status.A_PROSPECTAR:
                self.cliente.status = Cliente.Status.EM_PROSPECCAO
                self.cliente.save(update_fields=["status", "updated_at"])


class MockupImagem(models.Model):
    mockup = models.ForeignKey(
        Mockup,
        on_delete=models.CASCADE,
        related_name="imagens",
        verbose_name="Mockup",
    )
    imagem = models.ImageField("Imagem", upload_to="mockups/gallery/")
    legenda = models.CharField("Legenda", max_length=200, blank=True)
    ordem = models.PositiveIntegerField("Ordem", default=0)

    class Meta:
        ordering = ["ordem", "id"]
        verbose_name = "Imagem do mockup"
        verbose_name_plural = "Imagens do mockup"

    def __str__(self) -> str:
        return self.legenda or f"Imagem #{self.pk}"
