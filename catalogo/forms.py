from django import forms
from django.db.models import Q

from crm.models import Cliente

from .models import Cobranca, Pacote, Servico


class ServicoForm(forms.ModelForm):
    class Meta:
        model = Servico
        fields = ["nome", "descricao", "preco", "cobranca", "complemento", "ativo", "ordem"]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 3})}
        labels = {"complemento": "Pode entrar avulso na proposta"}


class PacoteForm(forms.ModelForm):
    class Meta:
        model = Pacote
        fields = ["nome", "resumo", "preco", "cobranca", "piso", "ativo", "ordem"]
        widgets = {"resumo": forms.Textarea(attrs={"rows": 3})}
        labels = {"piso": "Este valor é um piso (a partir de)"}


class PropostaForm(forms.Form):
    cliente = forms.ModelChoiceField(
        label="Cliente",
        queryset=Cliente.objects.order_by("empresa", "nome"),
    )
    pacote = forms.ModelChoiceField(
        label="Pacote",
        queryset=Pacote.objects.filter(ativo=True).order_by("ordem", "nome"),
    )
    observacao = forms.CharField(
        label="Observação",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    desconto_fixo = forms.BooleanField(
        label="Manter o desconto que eu digitei",
        required=False,
        help_text="Sem esta marca, o percentual segue a faixa do valor.",
    )
    desconto_unico = forms.DecimalField(
        label="Desconto do valor único (%)",
        required=False,
        min_value=0,
        max_value=100,
        decimal_places=2,
    )
    desconto_mensal = forms.DecimalField(
        label="Desconto mensal (%)",
        required=False,
        min_value=0,
        max_value=100,
        decimal_places=2,
    )
    desconto_anual = forms.DecimalField(
        label="Desconto anual (%)",
        required=False,
        min_value=0,
        max_value=100,
        decimal_places=2,
    )

    def __init__(self, *args, proposta=None, **kwargs):
        super().__init__(*args, **kwargs)
        if proposta and proposta.pacote_id:
            self.fields["pacote"].queryset = Pacote.objects.filter(
                Q(ativo=True) | Q(pk=proposta.pacote_id)
            ).order_by("ordem", "nome")

    def percentuais(self) -> dict:
        from .preco import fracao

        dados = self.cleaned_data
        return {
            Cobranca.UNICO: fracao(dados.get("desconto_unico")),
            Cobranca.MENSAL: fracao(dados.get("desconto_mensal")),
            Cobranca.ANUAL: fracao(dados.get("desconto_anual")),
        }
