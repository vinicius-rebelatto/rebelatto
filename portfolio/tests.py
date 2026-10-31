from django.test import TestCase


class ConsultorioTemplateTests(TestCase):
    def test_pagina_abre_com_a_identidade_da_alva(self):
        response = self.client.get("/mockups/consultorio/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alva")
        self.assertContains(response, "com calma")
        self.assertContains(response, "mockups/consultorio.css")
        self.assertNotContains(response, "Protótipo Rebel Tech")
        self.assertNotContains(response, "chatbot.js")


class LuxoTemplateTests(TestCase):
    def test_pagina_abre_com_a_identidade_do_onix(self):
        response = self.client.get("/mockups/luxo/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ónix")
        self.assertContains(response, "Muito critério")
        self.assertContains(response, "mockups/luxo.css")
        self.assertNotContains(response, "Protótipo Rebel Tech")
        self.assertNotContains(response, "chatbot.js")
        self.assertNotContains(response, "Fraunces")


class HarmonizacaoTemplateTests(TestCase):
    def test_pagina_abre_com_a_identidade_da_nara(self):
        response = self.client.get("/mockups/harmonizacao/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nara")
        self.assertContains(response, "Harmonização")
        self.assertContains(response, "mockups/harmonizacao.css")
        self.assertNotContains(response, "Protótipo Rebel Tech")
        self.assertNotContains(response, "chatbot.js")
        self.assertNotContains(response, "Fraunces")
        self.assertNotContains(response, "Cormorant")


class PaginaDoLeadTests(TestCase):
    def setUp(self):
        from crm.models import Cliente

        self.cliente = Cliente.objects.create(
            empresa="Clínica Bella Pele",
            cidade="Blumenau",
            estado="SC",
            rua="Rua XV de Novembro, 900",
            telefone="(47) 99123-4567",
            categoria_lead=Cliente.CategoriaLead.SEM_SITE,
            status=Cliente.Status.A_PROSPECTAR,
        )

    def test_link_abre_o_primeiro_template_com_os_dados_do_lead(self):
        response = self.client.get(f"/p/{self.cliente.slug}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "mockups/consultorio.css")
        self.assertContains(response, "Clínica Bella Pele")
        self.assertContains(response, "Blumenau")
        self.assertContains(response, "Rua XV de Novembro, 900")
        self.assertContains(response, "Texto de exemplo")
        self.assertContains(response, "Quero esta página")
        self.assertNotContains(response, "Itajaí")
        self.assertNotContains(response, "Alva")
        self.assertNotContains(response, "mark__seal")
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_trocar_template_mantem_o_lead_e_registra_o_ultimo(self):
        for slug, demo in (("luxo", "Ónix"), ("harmonizacao", "Nara")):
            response = self.client.get(f"/p/{self.cliente.slug}/{slug}/")
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, f"mockups/{slug}.css")
            self.assertContains(response, "Clínica Bella Pele")
            self.assertNotContains(response, demo)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.ultimo_template, "harmonizacao")
        self.assertEqual(self.cliente.mockup_visitas, 2)
        self.assertIsNotNone(self.cliente.mockup_visto_em)

    def test_odontologia_fica_fora_da_biblioteca_de_estetica(self):
        response = self.client.get(f"/p/{self.cliente.slug}/odontologia/")
        self.assertEqual(response.status_code, 404)

    def test_site_proprio_e_rejeitado_nao_recebem_pagina(self):
        from crm.models import Cliente

        self.cliente.categoria_lead = Cliente.CategoriaLead.SITE_PROPRIO
        self.cliente.save()
        self.assertEqual(self.client.get(f"/p/{self.cliente.slug}/").status_code, 404)
        self.cliente.categoria_lead = Cliente.CategoriaLead.REDE_SOCIAL
        self.cliente.reject(motivo="teste")
        self.assertEqual(self.client.get(f"/p/{self.cliente.slug}/").status_code, 404)

    def test_robo_de_preview_nao_conta_visita(self):
        self.client.get(f"/p/{self.cliente.slug}/", HTTP_USER_AGENT="WhatsApp/2.23")
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.mockup_visitas, 0)

    def test_cor_do_cliente_entra_so_no_botao_e_no_detalhe(self):
        self.cliente.cor_destaque = "#f5d0e0"
        self.cliente.save()
        response = self.client.get(f"/p/{self.cliente.slug}/")
        html = response.content.decode()
        self.assertIn("body[data-lead] .btn", html)
        self.assertNotIn("background: #f5d0e0", html)

    def test_demo_continua_igual(self):
        response = self.client.get("/mockups/consultorio/")
        self.assertContains(response, "Alva")
        self.assertContains(response, "Itajaí")
        self.assertNotContains(response, "Quero esta página")
        self.assertNotContains(response, "Texto de exemplo")


class PaletaTests(TestCase):
    def test_cor_clara_escurece_o_botao_no_tema_claro(self):
        from portfolio.marca import contraste, paleta

        cores = paleta("#f5d0e0", tema="light", fundo="#f3eee6")
        self.assertGreaterEqual(contraste(cores["botao"], cores["tinta"]), 4.5)
        self.assertGreaterEqual(contraste(cores["detalhe"], "#f3eee6"), 3)

    def test_cor_escura_clareia_no_tema_escuro(self):
        from portfolio.marca import contraste, paleta

        cores = paleta("#1a1a40", tema="dark", fundo="#100e0c")
        self.assertGreaterEqual(contraste(cores["botao"], "#100e0c"), 3)
        self.assertGreaterEqual(contraste(cores["botao"], cores["tinta"]), 4.5)
        self.assertGreaterEqual(contraste(cores["detalhe"], "#100e0c"), 4.5)

    def test_cor_boa_nao_muda(self):
        from portfolio.marca import paleta

        self.assertEqual(paleta("#8d4554", tema="light", fundo="#f3ece8")["botao"], "#8d4554")


class BibliotecaEsteticaTests(TestCase):
    ORDEM = [
        "consultorio", "luxo", "harmonizacao", "agenda", "cartao",
        "revista", "retrato", "minima", "acolhedora", "clinica",
    ]

    def setUp(self):
        from crm.models import Cliente

        self.cliente = Cliente.objects.create(
            empresa="Espaço Teste Pele",
            cidade="Lages",
            estado="SC",
            rua="Rua Teste, 10",
            telefone="(49) 99876-5432",
            cor_destaque="#2b6cb0",
            categoria_lead=Cliente.CategoriaLead.REDE_SOCIAL,
        )

    def test_biblioteca_tem_os_dez_templates_na_ordem(self):
        from portfolio.mockup_landings import biblioteca_do_nicho

        self.assertEqual([t["slug"] for t in biblioteca_do_nicho("estetica")], self.ORDEM)

    def test_cada_demo_abre_com_os_dados_ficticios(self):
        from portfolio.mockup_landings import LANDINGS

        for slug in self.ORDEM:
            with self.subTest(slug=slug):
                response = self.client.get(f"/mockups/{slug}/")
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, LANDINGS[slug]["demo"]["nome"])
                self.assertContains(response, f"mockups/{slug}.css")
                self.assertContains(response, "Página de demonstração" if slug != "minima" else "Demonstração")
                self.assertNotContains(response, "Quero esta página")
                self.assertNotContains(response, "Texto de exemplo")

    def test_cada_template_veste_o_lead(self):
        from portfolio.mockup_landings import LANDINGS

        for slug in self.ORDEM:
            with self.subTest(slug=slug):
                response = self.client.get(f"/p/{self.cliente.slug}/{slug}/")
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Espaço Teste Pele")
                self.assertContains(response, "Lages")
                self.assertContains(response, "(49) 99876-5432")
                self.assertContains(response, "Quero esta página")
                self.assertContains(response, "exemplo")
                self.assertContains(response, "body[data-lead] .btn")
                demo = LANDINGS[slug]["demo"]
                self.assertNotContains(response, demo["telefone"])
                self.assertNotContains(response, demo["endereco"])

    def test_lead_sem_endereco_nem_telefone_nao_mostra_campos_vazios(self):
        from crm.models import Cliente

        vazio = Cliente.objects.create(empresa="Studio Vazio", categoria_lead=Cliente.CategoriaLead.SEM_SITE)
        for slug in self.ORDEM:
            with self.subTest(slug=slug):
                response = self.client.get(f"/p/{vazio.slug}/{slug}/")
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "<dt>Endereço</dt>")
                self.assertNotContains(response, "<dt>Telefone</dt>")

    def test_setas_da_barra_dao_a_volta_na_biblioteca(self):
        response = self.client.get(f"/p/{self.cliente.slug}/clinica/")
        self.assertContains(response, f"/p/{self.cliente.slug}/consultorio/")
        self.assertContains(response, "10/10")
