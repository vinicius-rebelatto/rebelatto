from django import forms
from django.forms import inlineformset_factory

from crm.models import BuscaLeads, Cliente, Mockup, MockupImagem, PerfilNicho
from crm.qualificacao import termos as termos_do_nicho
from portfolio.models import Project

from .models import Tarefa


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
            "logo",
            "cor_destaque",
        ]
        widgets = {
            "cor_destaque": forms.TextInput(attrs={"placeholder": "#8d4554"}),
            "mensagem": forms.Textarea(attrs={"rows": 3}),
            "motivo_rejeicao": forms.Textarea(attrs={"rows": 2}),
            "notas": forms.Textarea(attrs={"rows": 3}),
        }


    def clean_cor_destaque(self):
        cor = (self.cleaned_data.get("cor_destaque") or "").strip().lower()
        if not cor:
            return ""
        import re

        if not re.fullmatch(r"#[0-9a-f]{6}", cor):
            raise forms.ValidationError("Use o formato #rrggbb.")
        return cor


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


class TarefaForm(forms.ModelForm):
    class Meta:
        model = Tarefa
        fields = ["titulo", "descricao", "status", "prioridade", "frente", "prazo"]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "prazo": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }


class TarefaRapidaForm(forms.ModelForm):
    class Meta:
        model = Tarefa
        fields = ["titulo", "frente", "prioridade", "prazo"]
        widgets = {
            "titulo": forms.TextInput(
                attrs={"placeholder": "Nova tarefa…", "autocomplete": "off", "class": "erp-search"}
            ),
            "prazo": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }


class JSONOpcional(forms.JSONField):
    def prepare_value(self, value):
        if value in (None, "", {}):
            return ""
        return super().prepare_value(value)


class BuscaLeadsForm(forms.ModelForm):
    LIMITE_TOTAL = 500

    entrada_extra = JSONOpcional(
        label="Opções extras do actor",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": '{"scrapeContacts": true}'}),
        help_text="Opcional. JSON somado à entrada do Apify. Alguns extras são cobrados à parte.",
    )

    class Meta:
        model = BuscaLeads
        fields = ["nome", "termos", "local", "max_por_termo", "pular_fechados", "entrada_extra"]
        widgets = {
            "termos": forms.Textarea(attrs={"rows": 4, "placeholder": "clínica de estética\nharmonização facial"}),
            "local": forms.TextInput(attrs={"placeholder": "Itajaí, SC, Brasil"}),
        }

    def clean_max_por_termo(self):
        valor = self.cleaned_data["max_por_termo"]
        if valor < 1 or valor > 200:
            raise forms.ValidationError("Use de 1 a 200 lugares por termo.")
        return valor

    def clean_entrada_extra(self):
        valor = self.cleaned_data.get("entrada_extra")
        if valor in (None, ""):
            return {}
        if not isinstance(valor, dict):
            raise forms.ValidationError("Use um objeto JSON, como {\"scrapeContacts\": true}.")
        return valor

    def clean(self):
        dados = super().clean()
        termos = [t.strip() for t in (dados.get("termos") or "").splitlines() if t.strip()]
        if "termos" in dados and not termos:
            self.add_error("termos", "Informe pelo menos um termo.")
        maximo = dados.get("max_por_termo")
        if termos and maximo and len(termos) * maximo > self.LIMITE_TOTAL:
            self.add_error(
                "max_por_termo",
                f"Até {self.LIMITE_TOTAL} lugares por busca: {len(termos)} termo(s) × {maximo} passa disso.",
            )
        return dados
