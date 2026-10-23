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
