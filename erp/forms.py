from django import forms
from django.forms import inlineformset_factory

from crm.models import Cliente, Mockup, MockupImagem, PerfilNicho
from crm.qualificacao import termos as termos_do_nicho
from portfolio.models import Project


class ClienteForm(forms.ModelForm):
    website = forms.CharField(label="Website", required=False, max_length=200)
    maps_url = forms.CharField(label="URL Maps", required=False, max_length=500)

    class Meta:
        model = Cliente
        fields = [
            "nome",
            "empresa",
            "slug",
            "email",
            "telefone",
            "website",
            "mensagem",
            "maps_url",
            "categoria",
            "rua",
            "cidade",
            "estado",
            "origem",
            "status",
            "motivo_rejeicao",
            "notas",
        ]
        widgets = {
            "mensagem": forms.Textarea(attrs={"rows": 3}),
            "motivo_rejeicao": forms.Textarea(attrs={"rows": 2}),
            "notas": forms.Textarea(attrs={"rows": 3}),
        }


class RejectForm(forms.Form):
    motivo_rejeicao = forms.CharField(
        label="Motivo da rejeição",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Opcional"}),
    )


class CsvImportForm(forms.Form):
    arquivo = forms.FileField(label="Arquivo CSV")


class PerfilNichoForm(forms.ModelForm):
    class Meta:
        model = PerfilNicho
        fields = [
            "nome",
            "termos_nicho",
            "termos_vizinhos",
            "pontos_nicho",
            "pontos_vizinho",
            "pontos_avaliacoes_ideais",
            "pontos_avaliacoes_poucas",
            "pontos_avaliacoes_muitas",
            "pontos_nota_volume",
            "pontos_nao_reivindicado",
            "pontos_poucas_imagens",
            "pontos_agendamento",
            "fator_temporario",
        ]
        widgets = {
            "termos_nicho": forms.Textarea(attrs={"rows": 8}),
            "termos_vizinhos": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nome in (
            "pontos_nicho",
            "pontos_vizinho",
            "pontos_avaliacoes_ideais",
            "pontos_avaliacoes_poucas",
            "pontos_avaliacoes_muitas",
            "pontos_nota_volume",
            "pontos_nao_reivindicado",
            "pontos_poucas_imagens",
            "pontos_agendamento",
            "fator_temporario",
        ):
            self.fields[nome].widget.attrs.update({"min": 0, "max": 100})

    def clean_termos_nicho(self):
        texto = self.cleaned_data.get("termos_nicho", "")
        if not termos_do_nicho(texto):
            raise forms.ValidationError("Informe ao menos um termo do nicho.")
        return texto

    def clean(self):
        cleaned = super().clean()
        for nome in self.fields:
            valor = cleaned.get(nome)
            if isinstance(valor, int) and valor > 100:
                self.add_error(nome, "O máximo é 100.")
        return cleaned


class MockupForm(forms.ModelForm):
    class Meta:
        model = Mockup
        fields = [
            "cliente",
            "titulo",
            "slug",
            "categoria",
            "tipo",
            "status",
            "capa",
            "descricao",
            "preview_url",
            "notas_internas",
        ]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 3}),
            "notas_internas": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cliente"].required = False
        self.fields["cliente"].empty_label = "— Sem cliente (biblioteca) —"


MockupImagemFormSet = inlineformset_factory(
    Mockup,
    MockupImagem,
    fields=["imagem", "legenda", "ordem"],
    extra=2,
    can_delete=True,
)


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = [
            "titulo",
            "resumo",
            "stack",
            "url",
            "capa",
            "cliente",
            "status",
            "publicado",
            "ordem",
        ]
        widgets = {
            "resumo": forms.Textarea(attrs={"rows": 3}),
        }
