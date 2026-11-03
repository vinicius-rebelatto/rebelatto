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
        APIFY = "apify", "Busca no Apify"
        MANUAL = "manual", "Manual"

    class EtapaRejeicao(models.TextChoices):
        FILTRAGEM = "filtragem", "Filtragem"
        PROSPECCAO = "prospeccao", "Prospecção"
        ORCAMENTO = "orcamento", "Orçamento"

    class CategoriaLead(models.TextChoices):
        SEM_SITE = "sem_site", "Sem site"
        REDE_SOCIAL = "rede_social", "Rede social"
        SITE_FRACO = "site_fraco", "Site fraco"
        SITE_PROPRIO = "site_proprio", "Site próprio"
        FORA_NICHO = "fora_nicho", "Fora do nicho"
        FECHADO = "fechado", "Fechado"
        SEM_TELEFONE = "sem_telefone", "Sem telefone"

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

    nota_maps = models.DecimalField(
        "Nota no Maps",
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
    )
    avaliacoes = models.PositiveIntegerField("Avaliações", null=True, blank=True)
    imagens = models.PositiveIntegerField("Fotos", null=True, blank=True)
    fechado_permanente = models.BooleanField("Fechado em definitivo", default=False)
    fechado_temporario = models.BooleanField("Fechado temporariamente", default=False)
    nao_reivindicado = models.BooleanField("Perfil não reivindicado", default=False)
    link_agendamento = models.CharField("Link de agendamento", max_length=300, blank=True)
    presenca = models.CharField("Presença digital", max_length=32, blank=True)
    presenca_detalhe = models.CharField("Detalhe da presença", max_length=160, blank=True)
    categoria_lead = models.CharField(
        "Categoria do lead",
        max_length=32,
        choices=CategoriaLead.choices,
        blank=True,
        db_index=True,
    )
    nota = models.PositiveSmallIntegerField("Nota", default=0)
    motivo_nota = models.CharField("Motivo da nota", max_length=300, blank=True)
    dossie = models.TextField("Dossiê", blank=True)
    ordem_fila = models.PositiveSmallIntegerField("Ordem na fila", default=9)

    logo = models.ImageField("Logo", upload_to="clientes/logos/", blank=True)
    cor_destaque = models.CharField(
        "Cor de destaque",
        max_length=7,
        blank=True,
        help_text="Hex, ex.: #8d4554. Entra no botão e num detalhe do mockup.",
    )
    ultimo_template = models.CharField("Último template aberto", max_length=40, blank=True)
    mockup_visto_em = models.DateTimeField("Mockup visto em", null=True, blank=True)
    mockup_visitas = models.PositiveIntegerField("Visitas ao mockup", default=0)

    busca = models.ForeignKey(
        "BuscaLeads",
        verbose_name="Busca de origem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leads",
    )
    place_id = models.CharField("ID do lugar no Google", max_length=128, blank=True, db_index=True)
    bairro = models.CharField("Bairro", max_length=120, blank=True)
    cep = models.CharField("CEP", max_length=20, blank=True)
    latitude = models.DecimalField("Latitude", max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField("Longitude", max_digits=9, decimal_places=6, null=True, blank=True)
    descricao_maps = models.TextField("Descrição no Maps", blank=True)
    faixa_preco = models.CharField("Faixa de preço", max_length=40, blank=True)
    horarios = models.JSONField("Horário de funcionamento", default=list, blank=True)
    instagram = models.CharField("Instagram", max_length=300, blank=True)
    facebook = models.CharField("Facebook", max_length=300, blank=True)
    anuncio = models.BooleanField("Apareceu como anúncio", default=False)
    dados_maps = models.JSONField(
        "Dados completos do Maps",
        default=dict,
        blank=True,
        help_text="Tudo o que o Apify devolveu para este lugar.",
    )

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

    CATEGORIAS_MOCKUP = ("sem_site", "rede_social", "site_fraco")

    @property
    def recebe_mockup(self) -> bool:
        """Sem site, site em rede ou site fraco. Site próprio fica fora."""
        return (
            self.categoria_lead in self.CATEGORIAS_MOCKUP
            and self.status != self.Status.REJEITADO
        )

    @property
    def mockup_path(self) -> str:
        from django.urls import reverse

        return reverse("portfolio:mockup_lead", kwargs={"slug": self.slug})

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


class BuscaLeads(models.Model):
    """Uma busca no Google Maps pelo Apify. Os lugares viram leads importados."""

    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        RODANDO = "rodando", "Rodando"
        CONCLUIDA = "concluida", "Concluída"
        ERRO = "erro", "Erro"

    nome = models.CharField("Nome", max_length=120)
    termos = models.TextField(
        "Termos de busca",
        help_text="Um termo por linha, como você digitaria no Google Maps.",
    )
    local = models.CharField(
        "Local",
        max_length=200,
        help_text="Cidade, estado e país. Ex.: Itajaí, SC, Brasil",
    )
    max_por_termo = models.PositiveSmallIntegerField(
        "Máximo de lugares por termo",
        default=20,
        help_text="Cada lugar custa. No plano grátis, conte cerca de US$ 4 por mil lugares.",
    )
    idioma = models.CharField("Idioma", max_length=10, default="pt-BR")
    pular_fechados = models.BooleanField(
        "Pular lugares fechados",
        default=True,
        help_text="Economiza créditos. Lugares fechados não viram leads.",
    )
    entrada_extra = models.JSONField(
        "Opções extras do actor",
        default=dict,
        blank=True,
        help_text='JSON somado à entrada do Apify. Ex.: {"scrapeContacts": true}. Alguns extras são cobrados à parte.',
    )

    status = models.CharField(
        "Status", max_length=20, choices=Status.choices, default=Status.RASCUNHO
    )
    status_apify = models.CharField("Status no Apify", max_length=30, blank=True)
    run_id = models.CharField("ID da execução", max_length=40, blank=True)
    dataset_id = models.CharField("ID do dataset", max_length=40, blank=True)
    iniciada_em = models.DateTimeField("Iniciada em", null=True, blank=True)
    verificada_em = models.DateTimeField("Verificada em", null=True, blank=True)
    concluida_em = models.DateTimeField("Concluída em", null=True, blank=True)
    lugares = models.PositiveIntegerField("Lugares encontrados", default=0)
    novos = models.PositiveIntegerField("Leads novos", default=0)
    duplicados = models.PositiveIntegerField("Duplicados", default=0)
    na_leva = models.PositiveIntegerField("Na primeira leva", default=0)
    custo_usd = models.DecimalField(
        "Custo (US$)", max_digits=10, decimal_places=4, null=True, blank=True
    )
    erro = models.TextField("Erro", blank=True)
    created_at = models.DateTimeField("Criada em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizada em", auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Busca de leads"
        verbose_name_plural = "Buscas de leads"

    def __str__(self) -> str:
        return self.nome

    @property
    def termos_lista(self) -> list[str]:
        vistos: list[str] = []
        for linha in self.termos.splitlines():
            termo = linha.strip()
            if termo and termo not in vistos:
                vistos.append(termo)
        return vistos

    @property
    def limite_lugares(self) -> int:
        return len(self.termos_lista) * self.max_por_termo

    @property
    def pode_iniciar(self) -> bool:
        return self.status in {self.Status.RASCUNHO, self.Status.ERRO}

    def entrada(self) -> dict:
        dados = {
            "searchStringsArray": self.termos_lista,
            "locationQuery": self.local.strip(),
            "maxCrawledPlacesPerSearch": self.max_por_termo,
            "language": self.idioma or "pt-BR",
            "skipClosedPlaces": self.pular_fechados,
            "maxImages": 0,
            "maxReviews": 0,
            "scrapeContacts": False,
            "scrapeReviewsPersonalData": False,
        }
        if isinstance(self.entrada_extra, dict):
            dados.update(self.entrada_extra)
        return dados


class PerfilNicho(models.Model):
    """Perfil de cliente ideal. A nota usa estes pesos; a categoria escolhe a abordagem."""

    nome = models.CharField("Nome", max_length=120, default="Clínicas de estética")
    termos_nicho = models.TextField(
        "Termos do nicho",
        default="estética\nharmonização\nesteticista\nspa",
        help_text="Um termo por linha. A categoria do Maps precisa conter um deles.",
    )
    termos_vizinhos = models.TextField(
        "Termos vizinhos",
        blank=True,
        default="dermatolog\nmicropigment\nsobrancelha\nbiomedicina",
        help_text="Entram na leva, com menos pontos. Um termo por linha.",
    )
    pontos_nicho = models.PositiveSmallIntegerField(
        "Pontos do nicho",
        default=25,
        help_text="Soma quando a categoria do Maps bate com o nicho.",
    )
    pontos_vizinho = models.PositiveSmallIntegerField(
        "Pontos da categoria vizinha",
        default=10,
        help_text="Soma quando a categoria só bate com um termo vizinho.",
    )
    pontos_avaliacoes_ideais = models.PositiveSmallIntegerField(
        "Avaliações de 20 a 400",
        default=35,
        help_text="Clínica real, ainda local.",
    )
    pontos_avaliacoes_poucas = models.PositiveSmallIntegerField(
        "Avaliações de 5 a 19",
        default=15,
    )
    pontos_avaliacoes_muitas = models.PositiveSmallIntegerField(
        "Mais de 400 avaliações",
        default=10,
        help_text="Operação grande, ciclo de venda mais longo.",
    )
    pontos_nota_volume = models.PositiveSmallIntegerField(
        "Nota do Maps com volume",
        default=15,
        help_text="Soma quando a nota é 4,2 ou mais e há pelo menos 15 avaliações.",
    )
    pontos_nao_reivindicado = models.PositiveSmallIntegerField(
        "Perfil do Google não reivindicado",
        default=8,
    )
    pontos_poucas_imagens = models.PositiveSmallIntegerField(
        "Menos de 5 fotos",
        default=7,
    )
    pontos_agendamento = models.PositiveSmallIntegerField(
        "Já tem link de agendamento",
        default=10,
        help_text="Este valor é descontado da nota.",
    )
    fator_temporario = models.PositiveSmallIntegerField(
        "Fechado temporariamente",
        default=20,
        help_text="Percentual da nota que permanece. 20 deixa o lead no fim da categoria.",
    )

    class Meta:
        verbose_name = "Perfil de nicho"
        verbose_name_plural = "Perfis de nicho"

    def __str__(self) -> str:
        return self.nome

    @classmethod
    def atual(cls) -> "PerfilNicho":
        perfil = cls.objects.order_by("id").first()
        if perfil is not None:
            return perfil
        return cls.objects.create(nome="Clínicas de estética")


class Mockup(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        PUBLICADO = "publicado", "Publicado"
        ARQUIVADO = "arquivado", "Arquivado"

    class Categoria(models.TextChoices):
        ODONTOLOGIA = "odontologia", "Odontologia"
        GERAL = "geral", "Geral"

    class Tipo(models.TextChoices):
        GALERIA = "galeria", "Galeria"
        LANDING = "landing", "Landing"

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mockups",
        verbose_name="Cliente",
    )
    titulo = models.CharField("Título", max_length=160)
    slug = models.SlugField("Slug", max_length=220, unique=True)
    categoria = models.CharField(
        "Categoria",
        max_length=32,
        choices=Categoria.choices,
        default=Categoria.GERAL,
    )
    tipo = models.CharField(
        "Tipo",
        max_length=32,
        choices=Tipo.choices,
        default=Tipo.GALERIA,
    )
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
        if self.cliente_id:
            base_source = self.cliente.empresa or self.cliente.nome or self.titulo
        else:
            base_source = self.titulo
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
            if self.cliente_id and self.cliente.status == Cliente.Status.A_PROSPECTAR:
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


class VisitaMockup(models.Model):
    """Uma abertura da prévia do site pelo lead (robôs e equipe ficam de fora)."""

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="visitas_mockup")
    template = models.CharField("Template", max_length=40, blank=True)
    pagina = models.CharField("Página", max_length=60, blank=True)
    celular = models.BooleanField("Pelo celular", default=False)
    created_at = models.DateTimeField("Quando", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Visita ao mockup"
        verbose_name_plural = "Visitas ao mockup"

    def __str__(self) -> str:
        return f"{self.cliente} · {self.created_at:%d/%m %H:%M}"
