from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from crm import apify, buscas
from crm.models import BuscaLeads, Cliente
from crm.presenca import Presenca

ITENS = [
    {
        "title": "Clínica Aurora Estética",
        "categoryName": "Clínica de estética",
        "categories": ["Clínica de estética", "Spa"],
        "phone": "(47) 99999-1111",
        "phoneUnformatted": "+5547999991111",
        "website": None,
        "url": "https://www.google.com/maps/place/?q=place_id:aurora",
        "placeId": "ChIJaurora",
        "street": "Rua Hercílio Luz, 100",
        "neighborhood": "Centro",
        "city": "Itajaí",
        "postalCode": "88301-000",
        "state": "Santa Catarina",
        "countryCode": "BR",
        "location": {"lat": -26.9077712, "lng": -48.6619301},
        "totalScore": 4.8,
        "reviewsCount": 86,
        "imagesCount": 3,
        "claimThisBusiness": True,
        "permanentlyClosed": False,
        "temporarilyClosed": False,
        "description": "Estética facial e corporal.",
        "price": "$$",
        "openingHours": [{"day": "segunda-feira", "hours": "09:00 a 18:00"}],
        "isAdvertisement": False,
        "reviewsDistribution": {"oneStar": 1, "fiveStar": 70},
    },
    {
        "title": "Studio Rede",
        "categoryName": "Harmonização facial",
        "phone": "(47) 99999-2222",
        "website": "https://instagram.com/studiorede",
        "placeId": "ChIJrede",
        "city": "Itajaí",
        "state": "Santa Catarina",
        "totalScore": 4.9,
        "reviewsCount": 40,
        "imagesCount": 12,
        "claimThisBusiness": False,
    },
    # Mesmo lugar repetido por outro termo de busca.
    {"title": "Clínica Aurora Estética", "placeId": "ChIJaurora", "phone": "(47) 99999-1111", "city": "Itajaí"},
    {"title": "", "placeId": "sem-nome"},
]


def visitas_falsas(urls):
    return {url: Presenca("site_fraco", "pouco conteúdo", True) for url in urls}


@override_settings(APIFY_TOKEN="tok-teste")
class BuscaApifyTests(TestCase):
    def setUp(self):
        self.busca = BuscaLeads.objects.create(
            nome="Teste Itajaí", termos="clínica de estética\nharmonização facial\n", local="Itajaí, SC, Brasil", max_por_termo=10
        )

    def test_entrada_do_actor(self):
        entrada = self.busca.entrada()
        self.assertEqual(entrada["searchStringsArray"], ["clínica de estética", "harmonização facial"])
        self.assertEqual(entrada["locationQuery"], "Itajaí, SC, Brasil")
        self.assertEqual(entrada["maxCrawledPlacesPerSearch"], 10)
        self.assertFalse(entrada["scrapeContacts"])
        self.assertEqual(self.busca.limite_lugares, 20)

    def test_iniciar_guarda_execucao(self):
        with patch("crm.apify.iniciar", return_value={"id": "run1", "defaultDatasetId": "ds1", "status": "READY"}) as ini:
            buscas.iniciar(self.busca)
        ini.assert_called_once()
        self.busca.refresh_from_db()
        self.assertEqual(self.busca.status, BuscaLeads.Status.RODANDO)
        self.assertEqual((self.busca.run_id, self.busca.dataset_id), ("run1", "ds1"))

    def test_concluida_importa_qualifica_e_guarda_todas_as_colunas(self):
        self.busca.status = BuscaLeads.Status.RODANDO
        self.busca.run_id, self.busca.dataset_id = "run1", "ds1"
        self.busca.save()
        execucao = {"status": "SUCCEEDED", "defaultDatasetId": "ds1", "usageTotalUsd": 0.0123}
        with patch("crm.apify.consultar", return_value=execucao), patch(
            "crm.apify.itens", return_value=ITENS
        ), patch("crm.importacao.visitar_varios", side_effect=visitas_falsas):
            busca = buscas.atualizar(self.busca.pk)
        self.assertEqual(busca.status, BuscaLeads.Status.CONCLUIDA)
        self.assertEqual((busca.lugares, busca.novos, busca.duplicados, busca.na_leva), (4, 2, 1, 2))
        self.assertEqual(str(busca.custo_usd), "0.0123")
        aurora = Cliente.objects.get(place_id="ChIJaurora")
        self.assertEqual(aurora.origem, Cliente.Origem.APIFY)
        self.assertEqual(aurora.status, Cliente.Status.IMPORTADO)
        self.assertEqual(aurora.busca, busca)
        self.assertEqual(aurora.categoria_lead, "sem_site")
        self.assertGreater(aurora.nota, 0)
        self.assertEqual(aurora.bairro, "Centro")
        self.assertEqual(aurora.cep, "88301-000")
        self.assertEqual(str(aurora.latitude), "-26.907771")
        self.assertEqual(aurora.horarios[0]["day"], "segunda-feira")
        self.assertEqual(aurora.dados_maps["reviewsDistribution"]["fiveStar"], 70)
        self.assertTrue(aurora.nao_reivindicado)
        rede = Cliente.objects.get(place_id="ChIJrede")
        self.assertEqual(rede.categoria_lead, "rede_social")
        self.assertEqual(rede.instagram, "https://instagram.com/studiorede")

    def test_segunda_importacao_nao_duplica(self):
        with patch("crm.importacao.visitar_varios", side_effect=visitas_falsas):
            buscas.importar(self.busca, ITENS)
            outra = BuscaLeads.objects.create(nome="De novo", termos="x", local="Itajaí")
            resumo = buscas.importar(outra, ITENS)
        self.assertEqual(resumo["novos"], 0)
        self.assertEqual(Cliente.objects.filter(place_id="ChIJaurora").count(), 1)

    def test_falha_no_apify_vira_erro(self):
        self.busca.status = BuscaLeads.Status.RODANDO
        self.busca.run_id = "run1"
        self.busca.save()
        with patch("crm.apify.consultar", return_value={"status": "FAILED", "statusMessage": "Sem créditos"}):
            busca = buscas.atualizar(self.busca.pk)
        self.assertEqual(busca.status, BuscaLeads.Status.ERRO)
        self.assertIn("Sem créditos", busca.erro)

    def test_ainda_rodando_nao_importa(self):
        self.busca.status = BuscaLeads.Status.RODANDO
        self.busca.run_id = "run1"
        self.busca.save()
        with patch("crm.apify.consultar", return_value={"status": "RUNNING"}), patch("crm.apify.itens") as itens:
            busca = buscas.atualizar(self.busca.pk)
        itens.assert_not_called()
        self.assertEqual(busca.status, BuscaLeads.Status.RODANDO)

    @override_settings(APIFY_TOKEN="")
    def test_sem_token_explica_o_que_fazer(self):
        with self.assertRaisesMessage(apify.ApifyError, "APIFY_TOKEN"):
            apify.iniciar({})

    def test_erro_http_nao_vaza_token(self):
        class Resposta:
            status_code = 400
            text = ""

            def json(self):
                return {"error": {"message": "input inválido tok-teste"}}

        with patch("httpx.Client.request", return_value=Resposta()):
            with self.assertRaises(apify.ApifyError) as ctx:
                apify.consultar("run1")
        self.assertNotIn("tok-teste", str(ctx.exception))
        self.assertIn("***", str(ctx.exception))


@override_settings(APIFY_TOKEN="tok-teste")
class BuscaTelasTests(TestCase):
    def setUp(self):
        usuario = get_user_model().objects.create_user("staff", password="x", is_staff=True)
        self.client.force_login(usuario)

    def test_criar_e_iniciar_pela_tela(self):
        dados = {"nome": "Itajaí estética", "termos": "clínica de estética", "local": "Itajaí, SC, Brasil", "max_por_termo": 20, "pular_fechados": "on", "iniciar": "1"}
        with patch("crm.apify.iniciar", return_value={"id": "run9", "defaultDatasetId": "ds9", "status": "READY"}):
            resposta = self.client.post(reverse("erp:cliente_busca_create"), dados)
        busca = BuscaLeads.objects.get()
        self.assertRedirects(resposta, reverse("erp:cliente_busca_detail", args=[busca.pk]), fetch_redirect_response=False)
        self.assertEqual(busca.status, BuscaLeads.Status.RODANDO)
        self.assertEqual(busca.entrada_extra, {})

    def test_limite_de_lugares_por_busca(self):
        dados = {"nome": "Grande", "termos": "a\nb\nc", "local": "SC", "max_por_termo": 200}
        resposta = self.client.post(reverse("erp:cliente_busca_create"), dados)
        self.assertContains(resposta, "Até 500 lugares por busca")
        self.assertFalse(BuscaLeads.objects.exists())

    def test_detalhe_rodando_consulta_o_apify(self):
        busca = BuscaLeads.objects.create(nome="B", termos="x", local="Itajaí", status=BuscaLeads.Status.RODANDO, run_id="r1")
        with patch("crm.apify.consultar", return_value={"status": "RUNNING"}) as consultar:
            resposta = self.client.get(reverse("erp:cliente_busca_detail", args=[busca.pk]))
        consultar.assert_called_once_with("r1")
        self.assertContains(resposta, 'http-equiv="refresh"')

    def test_lista_e_aviso_sem_token(self):
        with self.settings(APIFY_TOKEN=""):
            resposta = self.client.get(reverse("erp:cliente_busca_list"))
        self.assertContains(resposta, "APIFY_TOKEN")
