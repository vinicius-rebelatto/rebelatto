from django import forms
from django.utils import timezone

from .models import Credencial, Modelo
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
