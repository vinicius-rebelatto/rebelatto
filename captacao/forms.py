from django import forms
from django.utils.text import slugify

from . import textos
from .models import Abordagem, Experimento, NumeroWhatsApp, RespostaPadrao, Variante

CATEGORIAS = [
    ("sem_site", "Sem site"),
    ("rede_social", "Só rede social"),
    ("site_fraco", "Site fraco"),
    ("site_proprio", "Site próprio"),
]


class NumeroForm(forms.ModelForm):
    class Meta:
        model = NumeroWhatsApp
        fields = ["apelido", "telefone"]

    def clean_telefone(self):
        valor = self.cleaned_data["telefone"]
        telefone = textos.telefone_whatsapp(valor)
        if not telefone:
            raise forms.ValidationError("Use DDD + número, como (47) 99999-1111.")
        existente = NumeroWhatsApp.objects.filter(telefone=telefone)
        if self.instance.pk:
            existente = existente.exclude(pk=self.instance.pk)
        if existente.exists():
            raise forms.ValidationError("Este número já está cadastrado.")
        return telefone

    def save(self, commit=True):
        numero = super().save(commit=False)
        if not numero.instancia:
            base = slugify(f"rebel-{numero.apelido}")[:40] or "rebel"
            instancia = base
            indice = 2
            while NumeroWhatsApp.objects.filter(instancia=instancia).exists():
                instancia = f"{base}-{indice}"
                indice += 1
            numero.instancia = instancia
        if commit:
            numero.save()
        return numero


class NumeroConfigForm(forms.ModelForm):
    class Meta:
        model = NumeroWhatsApp
        fields = [
            "envios_ativos",
            "inicio_aquecimento",
            "limite_manual",
            "hora_inicio",
            "hora_fim",
            "envia_sabado",
            "intervalo_min",
            "intervalo_max",
            "pausa_a_cada",
            "pausa_minutos",
        ]
        widgets = {
            "inicio_aquecimento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "hora_fim": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def clean(self):
        dados = super().clean()
        if dados.get("intervalo_min") and dados["intervalo_min"] < 30:
            self.add_error("intervalo_min", "Abaixo de 30 segundos o WhatsApp percebe a automação.")
        if dados.get("hora_inicio") and dados.get("hora_fim") and dados["hora_inicio"] >= dados["hora_fim"]:
            self.add_error("hora_fim", "Precisa ser depois do horário de início.")
        return dados


class ExperimentoForm(forms.ModelForm):
    categorias_escolhidas = forms.MultipleChoiceField(
        label="Categorias de lead",
        choices=CATEGORIAS,
        widget=forms.CheckboxSelectMultiple,
        initial=["sem_site", "rede_social"],
    )

    class Meta:
        model = Experimento
        fields = ["nome", "ativo", "leads_por_variante", "nota_minima", "modo_ia", "previa_do_link"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["categorias_escolhidas"].initial = self.instance.categorias_lista

    def save(self, commit=True):
        experimento = super().save(commit=False)
        experimento.categorias = ",".join(self.cleaned_data["categorias_escolhidas"])
        if commit:
            experimento.save()
        return experimento


class VarianteForm(forms.ModelForm):
    class Meta:
        model = Variante
        fields = ["nome", "texto"]
        widgets = {"texto": forms.Textarea(attrs={"rows": 5})}

    def clean_texto(self):
        texto = self.cleaned_data["texto"]
        desconhecidos = textos.campos_desconhecidos(texto)
        if desconhecidos:
            raise forms.ValidationError(
                "Campo desconhecido: " + ", ".join("{{" + c + "}}" for c in desconhecidos)
            )
        return texto


class ResultadoForm(forms.ModelForm):
    class Meta:
        model = Abordagem
        fields = [
            "reuniao_para",
            "compareceu",
            "resultado",
            "produto",
            "valor_fechado",
            "retorno_em",
            "motivo_perda",
            "notas",
            "ia_pausada",
        ]
        widgets = {
            "reuniao_para": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "retorno_em": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "compareceu": forms.Select(choices=[("", "Ainda não"), ("true", "Compareceu"), ("false", "Faltou")]),
            "notas": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {"compareceu": "Compareceu?", "resultado": "Resultado"}


class RespostaForm(forms.Form):
    texto = forms.CharField(label="Mensagem", widget=forms.Textarea(attrs={"rows": 3}), max_length=2000)


class RespostaPadraoForm(forms.ModelForm):
    class Meta:
        model = RespostaPadrao
        fields = ["pergunta", "resposta", "ativa"]
        widgets = {"resposta": forms.Textarea(attrs={"rows": 5})}
