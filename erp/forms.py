from django import forms
from django.forms import inlineformset_factory

from crm.models import Cliente, Mockup, MockupImagem
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


class MockupForm(forms.ModelForm):
    class Meta:
        model = Mockup
        fields = [
            "cliente",
            "titulo",
            "slug",
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
