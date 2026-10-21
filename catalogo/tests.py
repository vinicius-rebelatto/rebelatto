from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from crm.models import Cliente

from .models import Pacote, Proposta, Servico
from .preco import com_desconto, gravar, percentual_sugerido


class FaixaTests(TestCase):
    def test_ticket_baixo_fica_em_cinco(self):
        self.assertEqual(percentual_sugerido(Decimal("490")), Decimal("0.05"))
        self.assertEqual(percentual_sugerido(Decimal("2000")), Decimal("0.05"))

    def test_ticket_alto_sobe_para_dez(self):
        self.assertEqual(percentual_sugerido(Decimal("2000.01")), Decimal("0.10"))
        self.assertEqual(percentual_sugerido(Decimal("8900")), Decimal("0.10"))


class PropostaTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(empresa="Clínica Aurora")
        self.express = Pacote.objects.get(nome="Landing Express")
        self.venda = Pacote.objects.get(nome="Landing de venda")
        self.crm = Pacote.objects.get(nome="CRM")
        self.chatbot = Servico.objects.get(nome="Chatbot")

    def test_express_sai_com_cinco_por_cento(self):
        proposta = gravar(Proposta(), self.express, [], False, {}, self.cliente, "", None)
        self.assertEqual(proposta.preco_unico, Decimal("490.00"))
        self.assertEqual(proposta.total_unico, Decimal("465.50"))
        self.assertEqual(proposta.desconto_unico, Decimal("0.05"))

    def test_crm_sai_com_dez_por_cento(self):
        proposta = gravar(Proposta(), self.crm, [], False, {}, self.cliente, "", None)
        self.assertEqual(proposta.total_unico, com_desconto(Decimal("8900"), Decimal("0.10")))
        self.assertEqual(proposta.piso, False)

    def test_escopo_incluso_nao_soma_de_novo(self):
        antes = Servico.objects.get(nome="Antes e depois")
        proposta = gravar(Proposta(), self.venda, [antes], False, {}, self.cliente, "", None)
        self.assertEqual(proposta.preco_unico, Decimal("1290.00"))
        self.assertFalse(proposta.itens.filter(tipo="avulso", nome="Antes e depois").exists())
        self.assertTrue(proposta.itens.filter(tipo="escopo", nome="Antes e depois").exists())

    def test_avulso_entra_no_subtotal(self):
        proposta = gravar(Proposta(), self.express, [self.chatbot], False, {}, self.cliente, "", None)
        self.assertEqual(proposta.preco_unico, Decimal("880.00"))
        self.assertEqual(proposta.total_unico, com_desconto(Decimal("880"), Decimal("0.05")))

    def test_desconto_informado_nao_segue_a_faixa(self):
        from catalogo.models import Cobranca

        proposta = gravar(
            Proposta(),
            self.express,
            [],
            True,
            {Cobranca.UNICO: Decimal("0.20"), Cobranca.MENSAL: Decimal("0"), Cobranca.ANUAL: Decimal("0")},
            self.cliente,
            "",
            None,
        )
        self.assertEqual(proposta.total_unico, Decimal("392.00"))

    def test_proposta_fechada_nao_muda_quando_a_tabela_muda(self):
        proposta = gravar(Proposta(), self.express, [], False, {}, self.cliente, "", None)
        proposta.status = Proposta.Status.FECHADA
        proposta.save(update_fields=["status"])
        self.express.preco = Decimal("999")
        self.express.save(update_fields=["preco"])
        proposta.refresh_from_db()
        self.assertEqual(proposta.total_unico, Decimal("465.50"))

    def test_rascunho_le_o_preco_novo(self):
        proposta = gravar(Proposta(), self.express, [], False, {}, self.cliente, "", None)
        self.express.preco = Decimal("1000")
        self.express.save(update_fields=["preco"])
        gravar(proposta, self.express, [], False, {}, self.cliente, "", None)
        self.assertEqual(proposta.preco_unico, Decimal("1000.00"))
        self.assertEqual(proposta.total_unico, Decimal("950.00"))


class PaginaTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("staff", password="x", is_staff=True)
        self.client = Client()
        self.client.force_login(user)
        self.cliente = Cliente.objects.create(empresa="Clínica Aurora")

    def test_tabela_e_propostas_abrem(self):
        tabela = self.client.get("/erp/catalogo/")
        self.assertEqual(tabela.status_code, 200)
        self.assertContains(tabela, "Landing Express")
        self.assertContains(tabela, "R$ 465,50")
        self.assertContains(tabela, "R$ 8.010,00")
        self.assertEqual(self.client.get("/erp/catalogo/servicos/").status_code, 200)
        self.assertEqual(self.client.get("/erp/catalogo/descontos/").status_code, 200)
        self.assertEqual(self.client.get("/erp/catalogo/propostas/").status_code, 200)
        nova = self.client.get(f"/erp/catalogo/propostas/nova/?cliente={self.cliente.pk}")
        self.assertEqual(nova.status_code, 200)
        self.assertContains(nova, "Landing Express")
        self.assertContains(nova, "R$ 465,50")

    def test_criar_proposta_pela_tela(self):
        pacote = Pacote.objects.get(nome="Landing Express")
        resposta = self.client.post(
            "/erp/catalogo/propostas/nova/",
            {
                "cliente": self.cliente.pk,
                "pacote": pacote.pk,
                "observacao": "Primeira clínica",
                "desconto_unico": "5",
                "desconto_mensal": "5",
                "desconto_anual": "5",
            },
        )
        proposta = Proposta.objects.get()
        self.assertRedirects(resposta, f"/erp/catalogo/propostas/{proposta.pk}/")
        detalhe = self.client.get(f"/erp/catalogo/propostas/{proposta.pk}/")
        self.assertContains(detalhe, "R$ 465,50")
        self.assertContains(detalhe, "Clínica Aurora")
        self.assertContains(detalhe, "Página")
