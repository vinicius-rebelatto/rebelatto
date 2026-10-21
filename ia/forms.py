from decimal import Decimal

from django import forms
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from .models import Agente, Credencial, Modelo, Orcamento
from .providers import PROVEDORES_COM_ADMIN, ProviderError, listar_modelos, validar_chave_admin


def _campo_secreto(label: str, required: bool, help_text: str = "") -> forms.CharField:
    return forms.CharField(
        label=label,
        required=required,
        strip=True,
        help_text=help_text,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "off"}),
    )


class _ValidacaoChaveMixin:
    """Validates keys against the provider before anything is saved."""

    remotos: list = []

    def _validar_chave(self, provedor: str, campo: str) -> None:
        chave = self.cleaned_data.get(campo)
        if not chave:
            return
        try:
            self.remotos = listar_modelos(provedor, chave)
        except ProviderError as exc:
            self.add_error(campo, str(exc))

    def _validar_admin(self, provedor: str, campo: str) -> None:
        chave = self.cleaned_data.get(campo)
        if not chave:
            return
        if provedor not in PROVEDORES_COM_ADMIN:
            self.add_error(campo, "Este provedor não usa chave de admin.")
            return
        try:
            validar_chave_admin(provedor, chave)
        except ProviderError as exc:
            self.add_error(campo, str(exc))


class CredencialCreateForm(_ValidacaoChaveMixin, forms.ModelForm):
    chave = _campo_secreto("Chave de API", required=True)
    chave_admin = _campo_secreto(
        "Chave de admin",
        required=False,
        help_text="Opcional. Só Anthropic e OpenAI; permite conferir o gasto oficial.",
    )

    class Meta:
        model = Credencial
        fields = ["provedor", "apelido"]

    def clean(self):
        cleaned = super().clean()
        provedor = cleaned.get("provedor")
        if provedor and not self.errors:
            self._validar_chave(provedor, "chave")
            self._validar_admin(provedor, "chave_admin")
        return cleaned

    def save(self, commit: bool = True) -> Credencial:
        credencial = super().save(commit=False)
        credencial.definir_chave(self.cleaned_data["chave"])
        credencial.definir_chave_admin(self.cleaned_data.get("chave_admin") or "")
        credencial.status = Credencial.Status.VALIDA
        if commit:
            credencial.save()
        return credencial


class CredencialEditForm(_ValidacaoChaveMixin, forms.ModelForm):
    nova_chave = _campo_secreto(
        "Nova chave de API",
        required=False,
        help_text="Deixe em branco para manter a atual.",
    )
    nova_chave_admin = _campo_secreto(
        "Nova chave de admin",
        required=False,
        help_text="Deixe em branco para manter a atual.",
    )
    remover_admin = forms.BooleanField(label="Remover chave de admin", required=False)

    class Meta:
        model = Credencial
        fields = ["apelido", "ativa"]

    def clean(self):
        cleaned = super().clean()
        if not self.errors:
            self._validar_chave(self.instance.provedor, "nova_chave")
            self._validar_admin(self.instance.provedor, "nova_chave_admin")
        return cleaned

    def save(self, commit: bool = True) -> Credencial:
        credencial = super().save(commit=False)
        if self.cleaned_data.get("nova_chave"):
            credencial.definir_chave(self.cleaned_data["nova_chave"])
            credencial.status = Credencial.Status.VALIDA
            credencial.ultimo_erro = ""
        if self.cleaned_data.get("nova_chave_admin"):
            credencial.definir_chave_admin(self.cleaned_data["nova_chave_admin"])
        elif self.cleaned_data.get("remover_admin"):
            credencial.definir_chave_admin("")
        if commit:
            credencial.save()
        return credencial


class ModeloForm(forms.ModelForm):
    PRICE_FIELDS = ("preco_entrada", "preco_saida", "preco_cache_leitura", "preco_cache_escrita")

    class Meta:
        model = Modelo
        fields = [
            "nome",
            "habilitado",
            "faixa",
            "preco_entrada",
            "preco_saida",
            "preco_cache_leitura",
            "preco_cache_escrita",
            "contexto_max",
            "saida_max",
            "suporta_visao",
            "suporta_ferramentas",
        ]

    def save(self, commit: bool = True) -> Modelo:
        modelo = super().save(commit=False)
        if any(field in self.changed_data for field in self.PRICE_FIELDS):
            modelo.fonte_preco = Modelo.FontePreco.MANUAL
            modelo.preco_atualizado_em = timezone.now()
        if commit:
            modelo.save()
        return modelo


def _rotulo_modelo(modelo: Modelo) -> str:
    if modelo.preco_saida is None:
        preco = "sem preço"
    else:
        preco = f"saída ${modelo.preco_saida}"
    estado = "" if modelo.habilitado else " · desabilitado"
    return f"{modelo.get_provedor_display()} — {modelo} · {preco}{estado}"


class AgenteForm(forms.Form):
    nome = forms.CharField(label="Nome", max_length=120)
    slug = forms.SlugField(
        label="Identificador",
        max_length=80,
        required=False,
        help_text="Deixe em branco para gerar a partir do nome. Não muda depois de criado.",
    )
    responsabilidade = forms.CharField(
        label="Responsabilidade",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    ativo = forms.BooleanField(label="Ativo", required=False, initial=True)
    prompt = forms.CharField(
        label="Prompt de sistema",
        required=False,
        widget=forms.Textarea(attrs={"rows": 14}),
        help_text="Cada alteração de prompt, modelo ou parâmetro grava uma versão nova.",
    )
    temperatura = forms.DecimalField(
        label="Temperatura",
        min_value=Decimal("0"),
        max_value=Decimal("2"),
        decimal_places=2,
        max_digits=3,
        initial=Decimal("0.70"),
    )
    max_tokens = forms.IntegerField(
        label="Limite de tokens na resposta",
        min_value=1,
        max_value=100_000,
        initial=1024,
    )
    modelo = forms.ModelChoiceField(label="Modelo principal", queryset=Modelo.objects.none(), required=False)
    modelo_reserva = forms.ModelChoiceField(
        label="Modelo reserva",
        queryset=Modelo.objects.none(),
        required=False,
        help_text="Usado quando o principal falha ou quando o teto do mês estoura.",
    )

    def __init__(self, *args, agente: Agente | None = None, incluir_ids: list[int] | None = None, **kwargs):
        self.agente = agente
        super().__init__(*args, **kwargs)
        if agente is not None:
            self.fields.pop("slug")
        ids = incluir_ids or []
        queryset = Modelo.objects.filter(Q(habilitado=True) | Q(pk__in=ids)).order_by("provedor", "model_id")
        for nome in ("modelo", "modelo_reserva"):
            self.fields[nome].queryset = queryset
            self.fields[nome].label_from_instance = _rotulo_modelo
            self.fields[nome].empty_label = "Nenhum"

    def clean(self):
        cleaned = super().clean()
        if self.agente is None and "slug" not in self.errors:
            slug = (cleaned.get("slug") or "").strip() or slugify(cleaned.get("nome") or "")
            if not slug:
                self.add_error("nome", "Informe um nome.")
            elif Agente.objects.filter(slug=slug).exists():
                self.add_error("slug", "Já existe um agente com este identificador.")
            else:
                cleaned["slug"] = slug
        modelo = cleaned.get("modelo")
        reserva = cleaned.get("modelo_reserva")
        if modelo is not None and reserva is not None and modelo.pk == reserva.pk:
            self.add_error("modelo_reserva", "O reserva precisa ser um modelo diferente do principal.")
        return cleaned


class OrcamentoForm(forms.ModelForm):
    class Meta:
        model = Orcamento
        fields = ["escopo", "provedor", "agente", "teto_usd", "ativo"]
        help_texts = {
            "provedor": "Preencha só quando o escopo for um provedor.",
            "agente": "Preencha só quando o escopo for um agente.",
            "teto_usd": "No 100%, as chamadas passam a usar o modelo reserva e um alerta é aberto.",
        }

    def clean(self):
        cleaned = super().clean()
        escopo = cleaned.get("escopo")
        provedor = cleaned.get("provedor") or ""
        agente = cleaned.get("agente")
        teto = cleaned.get("teto_usd")
        if teto is not None and teto <= 0:
            self.add_error("teto_usd", "O teto precisa ser maior que zero.")
        if escopo == Orcamento.Escopo.GLOBAL:
            cleaned["provedor"] = ""
            cleaned["agente"] = None
            consulta = Orcamento.objects.filter(escopo=Orcamento.Escopo.GLOBAL)
        elif escopo == Orcamento.Escopo.PROVEDOR:
            if not provedor:
                self.add_error("provedor", "Escolha o provedor.")
            cleaned["agente"] = None
            consulta = Orcamento.objects.filter(escopo=Orcamento.Escopo.PROVEDOR, provedor=provedor)
        elif escopo == Orcamento.Escopo.AGENTE:
            if agente is None:
                self.add_error("agente", "Escolha o agente.")
            cleaned["provedor"] = ""
            consulta = Orcamento.objects.filter(escopo=Orcamento.Escopo.AGENTE, agente=agente)
        else:
            return cleaned
        if self.instance.pk:
            consulta = consulta.exclude(pk=self.instance.pk)
        if not self.errors and consulta.exists():
            self.add_error("escopo", "Já existe um teto para este escopo.")
        return cleaned


class PlaygroundForm(forms.Form):
    entrada = forms.CharField(
        label="Mensagem de teste",
        max_length=8000,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Usa o prompt e os parâmetros da versão ativa. Cada modelo escolhido consome crédito.",
    )
    modelos = forms.ModelMultipleChoiceField(label="Modelos", queryset=Modelo.objects.none())

    def __init__(self, *args, queryset, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["modelos"].queryset = queryset
        self.fields["modelos"].label_from_instance = _rotulo_modelo
        self.fields["modelos"].widget.attrs["size"] = 6

    def clean_modelos(self):
        modelos = self.cleaned_data["modelos"]
        if len(modelos) > 3:
            raise forms.ValidationError("Escolha no máximo 3 modelos.")
        return modelos
