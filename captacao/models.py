"""Captação pelo WhatsApp: números, scripts em teste, abordagens e conversas."""

from __future__ import annotations

from datetime import time

from django.db import models
from django.utils import timezone

# Mensagens frias por dia em cada dia de aquecimento. Depois do último dia, fica no teto.
CURVA_AQUECIMENTO = [20, 20, 25, 35, 40, 45, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 185, 200]
TETO_DIARIO = 200


class NumeroWhatsApp(models.Model):
    """Um chip com WhatsApp Business ligado a uma instância da Evolution API."""

    class Conexao(models.TextChoices):
        PENDENTE = "pendente", "Aguardando QR"
        CONECTANDO = "conectando", "Conectando"
        CONECTADO = "conectado", "Conectado"
        DESCONECTADO = "desconectado", "Desconectado"

    apelido = models.CharField("Apelido", max_length=60, help_text="Ex.: TIM principal")
    telefone = models.CharField("Número", max_length=20, help_text="Com DDD. Ex.: (47) 99999-1111")
    instancia = models.SlugField("Instância na Evolution", max_length=60, unique=True)
    conexao = models.CharField("Conexão", max_length=20, choices=Conexao.choices, default=Conexao.PENDENTE)
    qr_code = models.TextField("Último QR code", blank=True)
    codigo_pareamento = models.CharField("Código de pareamento", max_length=20, blank=True)
    qr_atualizado_em = models.DateTimeField(null=True, blank=True)
    conectado_em = models.DateTimeField(null=True, blank=True)

    envios_ativos = models.BooleanField(
        "Envios ativos",
        default=False,
        help_text="Liga o disparo automático da fila por este número.",
    )
    inicio_aquecimento = models.DateField(
        "Início da automação",
        null=True,
        blank=True,
        help_text="Dia 1 da curva de aquecimento. Preenchido ao ativar os envios.",
    )
    limite_manual = models.PositiveSmallIntegerField(
        "Limite diário fixo",
        null=True,
        blank=True,
        help_text="Opcional. Substitui a curva de aquecimento.",
    )
    hora_inicio = models.TimeField("Começa às", default=time(9, 0))
    hora_fim = models.TimeField("Para às", default=time(18, 0))
    envia_sabado = models.BooleanField("Envia aos sábados", default=False)
    intervalo_min = models.PositiveSmallIntegerField("Intervalo mínimo (s)", default=60)
    intervalo_max = models.PositiveSmallIntegerField("Intervalo máximo (s)", default=150)
    pausa_a_cada = models.PositiveSmallIntegerField("Pausa a cada (mensagens)", default=10)
    pausa_minutos = models.PositiveSmallIntegerField("Duração da pausa (min)", default=10)
    proximo_envio_em = models.DateTimeField(null=True, blank=True)
    ultimo_envio_em = models.DateTimeField(null=True, blank=True)
    ultimo_erro = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["apelido"]
        verbose_name = "Número de WhatsApp"
        verbose_name_plural = "Números de WhatsApp"

    def __str__(self) -> str:
        return f"{self.apelido} ({self.telefone})"

    def dia_em(self, data) -> int:
        if self.inicio_aquecimento is None:
            return 0
        return (data - self.inicio_aquecimento).days + 1

    def limite_em(self, data) -> int:
        dia = self.dia_em(data)
        if dia <= 0:
            return 0
        if dia > len(CURVA_AQUECIMENTO):
            return TETO_DIARIO
        return CURVA_AQUECIMENTO[dia - 1]

    @property
    def dia_aquecimento(self) -> int:
        return self.dia_em(timezone.localdate())

    @property
    def limite_curva(self) -> int:
        return self.limite_em(timezone.localdate())


class Experimento(models.Model):
    """Um teste A/B/C de scripts da primeira mensagem."""

    class ModoIA(models.TextChoices):
        DESLIGADO = "desligado", "Desligado: só você responde"
        COPILOTO = "copiloto", "Copiloto: a IA sugere, você aprova"
        AUTOMATICO = "automatico", "Automático: a IA responde sozinha"

    nome = models.CharField("Nome", max_length=120)
    ativo = models.BooleanField(
        "Ativo",
        default=True,
        help_text="Só a fila de experimentos ativos é enviada.",
    )
    leads_por_variante = models.PositiveSmallIntegerField("Leads por script", default=100)
    categorias = models.CharField(
        "Categorias de lead",
        max_length=200,
        default="sem_site,rede_social",
        help_text="Separadas por vírgula: sem_site, rede_social, site_fraco.",
    )
    nota_minima = models.PositiveSmallIntegerField("Nota mínima do lead", default=0)
    previa_do_link = models.BooleanField("Mostrar prévia do link", default=True)
    modo_ia = models.CharField(
        "Respostas com IA", max_length=20, choices=ModoIA.choices, default=ModoIA.COPILOTO
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Experimento"
        verbose_name_plural = "Experimentos"

    def __str__(self) -> str:
        return self.nome

    @property
    def categorias_lista(self) -> list[str]:
        return [c.strip() for c in self.categorias.split(",") if c.strip()]


class Variante(models.Model):
    experimento = models.ForeignKey(Experimento, on_delete=models.CASCADE, related_name="variantes")
    letra = models.CharField("Letra", max_length=2)
    nome = models.CharField("O que este script testa", max_length=120, blank=True)
    texto = models.TextField(
        "Primeira mensagem",
        help_text="Campos: {{empresa}}, {{cidade}}, {{bairro}}, {{nota_maps}}, {{avaliacoes}}, {{mockup}}. "
        "Variações: {Oi|Olá|Bom dia}.",
    )

    class Meta:
        ordering = ["experimento", "letra"]
        constraints = [
            models.UniqueConstraint(fields=["experimento", "letra"], name="captacao_variante_letra_unica"),
        ]

    def __str__(self) -> str:
        return f"{self.experimento} · {self.letra}"


class Abordagem(models.Model):
    """Um lead dentro de um script: da fila até o resultado da reunião."""

    class Envio(models.TextChoices):
        NA_FILA = "na_fila", "Na fila"
        ENVIADA = "enviada", "Enviada"
        FALHOU = "falhou", "Falhou"
        CANCELADA = "cancelada", "Cancelada"

    class Resultado(models.TextChoices):
        FECHOU = "fechou", "Fechou"
        EM_VALIDACAO = "em_validacao", "Em validação"
        PERDIDO = "perdido", "Perdido"

    cliente = models.OneToOneField("crm.Cliente", on_delete=models.CASCADE, related_name="abordagem")
    variante = models.ForeignKey(Variante, on_delete=models.PROTECT, related_name="abordagens")
    numero = models.ForeignKey(
        NumeroWhatsApp, null=True, blank=True, on_delete=models.SET_NULL, related_name="abordagens"
    )
    telefone = models.CharField("Telefone de destino", max_length=20, db_index=True)
    chave_telefone = models.CharField(max_length=12, db_index=True)
    jid = models.CharField(max_length=80, blank=True, db_index=True)
    envio = models.CharField(max_length=20, choices=Envio.choices, default=Envio.NA_FILA, db_index=True)
    ordem = models.PositiveIntegerField(default=0)
    texto_enviado = models.TextField(blank=True)
    erro = models.TextField(blank=True)

    enviada_em = models.DateTimeField(null=True, blank=True, db_index=True)
    entregue_em = models.DateTimeField(null=True, blank=True)
    lida_em = models.DateTimeField(null=True, blank=True)
    respondeu_em = models.DateTimeField(null=True, blank=True)
    opt_out_em = models.DateTimeField(null=True, blank=True)
    reuniao_marcada_em = models.DateTimeField("Reunião marcada em", null=True, blank=True)
    reuniao_para = models.DateTimeField("Data da reunião", null=True, blank=True)
    compareceu = models.BooleanField("Compareceu", null=True, blank=True)
    resultado = models.CharField(max_length=20, choices=Resultado.choices, blank=True)
    retorno_em = models.DateField("Retomar contato em", null=True, blank=True)
    motivo_perda = models.CharField("Motivo", max_length=200, blank=True)
    notas = models.TextField("Notas da reunião", blank=True)
    ia_pausada = models.BooleanField("IA pausada nesta conversa", default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordem", "id"]
        verbose_name = "Abordagem"
        verbose_name_plural = "Abordagens"

    def __str__(self) -> str:
        return f"{self.cliente} · {self.variante.letra}"

    @property
    def etapa(self) -> str:
        if self.opt_out_em:
            return "Pediu para sair"
        if self.resultado:
            return self.get_resultado_display()
        if self.compareceu is False:
            return "Faltou"
        if self.compareceu:
            return "Compareceu"
        if self.reuniao_marcada_em:
            return "Reunião marcada"
        if self.respondeu_em:
            return "Respondeu"
        if self.lida_em:
            return "Lida"
        if self.entregue_em:
            return "Entregue"
        return self.get_envio_display()


class Mensagem(models.Model):
    class Direcao(models.TextChoices):
        ENTRADA = "entrada", "Recebida"
        SAIDA = "saida", "Enviada"

    class Autor(models.TextChoices):
        LEAD = "lead", "Lead"
        SCRIPT = "script", "Script"
        IA = "ia", "IA"
        VOCE = "voce", "Você"
        CELULAR = "celular", "Pelo celular"

    abordagem = models.ForeignKey(
        Abordagem, null=True, blank=True, on_delete=models.CASCADE, related_name="mensagens"
    )
    numero = models.ForeignKey(NumeroWhatsApp, null=True, blank=True, on_delete=models.SET_NULL)
    direcao = models.CharField(max_length=10, choices=Direcao.choices)
    autor = models.CharField(max_length=10, choices=Autor.choices)
    texto = models.TextField(blank=True)
    tipo = models.CharField(max_length=40, blank=True)
    whatsapp_id = models.CharField(max_length=120, blank=True, db_index=True)
    jid = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=30, blank=True)
    sugestao = models.TextField("Resposta sugerida pela IA", blank=True)
    sugestao_status = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "Mensagem"
        verbose_name_plural = "Mensagens"

    def __str__(self) -> str:
        return f"{self.get_direcao_display()}: {self.texto[:40]}"


class OptOut(models.Model):
    chave_telefone = models.CharField(max_length=12, unique=True)
    telefone = models.CharField(max_length=20)
    motivo = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Opt-out"
        verbose_name_plural = "Opt-outs"

    def __str__(self) -> str:
        return self.telefone
