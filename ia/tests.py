from decimal import Decimal
from unittest import mock

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from . import crypto, pricing
from .forms import CredencialCreateForm
from .models import Credencial, Modelo, Provedor
from .providers import ModeloRemoto, ProviderError
from .services import sincronizar_modelos
from .templatetags.ia_extras import tokens, usd

REMOTOS = [
    ModeloRemoto("claude-haiku-5-5", "Claude Haiku 5.5"),
    ModeloRemoto("claude-sonnet-5-5", "Claude Sonnet 5.5"),
]

TABELA = {
    "claude-haiku-5-5": {
        "input_cost_per_token": 1e-07,
        "output_cost_per_token": 5e-07,
        "cache_read_input_token_cost": 1e-08,
        "max_input_tokens": 1_000_000,
        "supports_vision": True,
        "supports_function_calling": True,
    },
    "gemini/gemini-3.8-flash": {"input_cost_per_token": 7.5e-07, "output_cost_per_token": 3.75e-06},
}


class CryptoTests(TestCase):
    @override_settings(IA_ENCRYPTION_KEY="")
    def test_round_trip_with_derived_key(self):
        self.assertEqual(crypto.decifrar(crypto.cifrar("sk-ant-api-123")), "sk-ant-api-123")

    def test_values_saved_before_explicit_key_stay_readable(self):
        with override_settings(IA_ENCRYPTION_KEY=""):
            token = crypto.cifrar("segredo")
        with override_settings(IA_ENCRYPTION_KEY=Fernet.generate_key().decode()):
            self.assertEqual(crypto.decifrar(token), "segredo")

    def test_invalid_token_raises_crypto_error(self):
        with self.assertRaises(crypto.CryptoError):
            crypto.decifrar("lixo")


class FilterTests(TestCase):
    def test_usd(self):
        self.assertEqual(usd(Decimal("0.1000")), "$0,10")
        self.assertEqual(usd(Decimal("0.0050")), "$0,005")
        self.assertEqual(usd(Decimal("15.0000")), "$15,00")
        self.assertEqual(usd(None), "—")

    def test_tokens(self):
        self.assertEqual(tokens(1_000_000), "1M")
        self.assertEqual(tokens(200_000), "200k")
        self.assertEqual(tokens(None), "—")


class PricingTests(TestCase):
    def test_matches_provider_prefix_and_converts_per_million(self):
        modelo = Modelo(provedor=Provedor.GOOGLE, model_id="gemini-3.8-flash")
        pricing.aplicar(modelo, pricing.encontrar(TABELA, modelo.provedor, modelo.model_id))
        self.assertEqual(modelo.preco_entrada, Decimal("0.7500"))
        self.assertEqual(modelo.preco_saida, Decimal("3.7500"))
        self.assertEqual(modelo.faixa, Modelo.Faixa.ECONOMICO)

    def test_manual_prices_are_kept(self):
        modelo = Modelo.objects.create(
            provedor=Provedor.ANTHROPIC,
            model_id="claude-haiku-5-5",
            preco_entrada=Decimal("9"),
            preco_saida=Decimal("9"),
            fonte_preco=Modelo.FontePreco.MANUAL,
        )
        atualizados, _ = pricing.atualizar_precos([modelo], TABELA)
        modelo.refresh_from_db()
        self.assertEqual(atualizados, 0)
        self.assertEqual(modelo.preco_entrada, Decimal("9.0000"))


@mock.patch("ia.pricing.carregar_tabela", return_value=TABELA)
class CredencialTests(TestCase):
    def _form(self, **data):
        return CredencialCreateForm(
            data={"provedor": Provedor.ANTHROPIC, "apelido": "Produção", "chave": "sk-ant-api-abcd", **data}
        )

    @mock.patch("ia.forms.listar_modelos", side_effect=ProviderError("Chave inválida."))
    def test_invalid_key_is_not_saved(self, _listar, _tabela):
        form = self._form()
        self.assertFalse(form.is_valid())
        self.assertIn("chave", form.errors)
        self.assertEqual(Credencial.objects.count(), 0)

    @mock.patch("ia.forms.listar_modelos", return_value=REMOTOS)
    def test_valid_key_is_encrypted_and_models_synced(self, _listar, _tabela):
        form = self._form()
        self.assertTrue(form.is_valid(), form.errors)
        credencial = form.save()
        sincronizar_modelos(credencial, form.remotos)

        self.assertNotIn("sk-ant-api-abcd", credencial.chave_cifrada)
        self.assertEqual(credencial.chave, "sk-ant-api-abcd")
        self.assertEqual(credencial.chave_sufixo, "abcd")
        self.assertEqual(credencial.modelos.count(), 2)
        haiku = Modelo.objects.get(model_id="claude-haiku-5-5")
        self.assertEqual(haiku.preco_saida, Decimal("0.5000"))
        self.assertFalse(haiku.habilitado)

    @mock.patch("ia.forms.listar_modelos", return_value=REMOTOS)
    def test_admin_key_rejected_for_provider_without_admin(self, _listar, _tabela):
        form = CredencialCreateForm(
            data={"provedor": Provedor.GOOGLE, "apelido": "G", "chave": "AIza-1", "chave_admin": "x"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("chave_admin", form.errors)

    def test_sync_unlinks_models_no_longer_listed(self, _tabela):
        credencial = Credencial(provedor=Provedor.ANTHROPIC, apelido="A")
        credencial.definir_chave("sk-ant-api-1")
        credencial.save()
        sincronizar_modelos(credencial, REMOTOS)
        sincronizar_modelos(credencial, REMOTOS[:1])
        self.assertEqual(list(credencial.modelos.values_list("model_id", flat=True)), ["claude-haiku-5-5"])
        self.assertTrue(Modelo.objects.filter(model_id="claude-sonnet-5-5").exists())


@mock.patch("ia.pricing.carregar_tabela", return_value=TABELA)
class ViewTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("staff", password="x", is_staff=True)
        self.client.force_login(user)
        self.credencial = Credencial(provedor=Provedor.ANTHROPIC, apelido="Produção")
        self.credencial.definir_chave("sk-ant-api-wxyz")
        self.credencial.save()
        sincronizar_modelos(self.credencial, REMOTOS)

    def test_pages_render_without_exposing_key(self, _tabela):
        for url in [
            reverse("ia:credencial_list"),
            reverse("ia:credencial_create"),
            reverse("ia:credencial_detail", args=[self.credencial.pk]),
            reverse("ia:modelo_list"),
            reverse("ia:modelo_edit", args=[Modelo.objects.first().pk]),
        ]:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, url)
            self.assertNotContains(resp, "sk-ant-api-wxyz")

    def test_toggle_model(self, _tabela):
        modelo = Modelo.objects.get(model_id="claude-haiku-5-5")
        self.client.post(reverse("ia:modelo_toggle", args=[modelo.pk]))
        modelo.refresh_from_db()
        self.assertTrue(modelo.habilitado)

    def test_failed_test_marks_key_invalid(self, _tabela):
        with mock.patch("ia.services.listar_modelos", side_effect=ProviderError("Chave inválida.")):
            self.client.post(reverse("ia:credencial_test", args=[self.credencial.pk]))
        self.credencial.refresh_from_db()
        self.assertEqual(self.credencial.status, Credencial.Status.INVALIDA)

    def test_manual_price_edit_sets_source(self, _tabela):
        modelo = Modelo.objects.get(model_id="claude-haiku-5-5")
        self.client.post(
            reverse("ia:modelo_edit", args=[modelo.pk]),
            {"nome": modelo.nome, "faixa": "economico", "preco_entrada": "0.2", "preco_saida": "0.5"},
        )
        modelo.refresh_from_db()
        self.assertEqual(modelo.fonte_preco, Modelo.FontePreco.MANUAL)
        self.assertEqual(modelo.preco_entrada, Decimal("0.2000"))

    def test_staff_required(self, _tabela):
        self.client.logout()
        resp = self.client.get(reverse("ia:credencial_list"))
        self.assertEqual(resp.status_code, 302)
