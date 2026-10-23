from django.test import SimpleTestCase, TestCase

from crm.models import PerfilNicho
from crm.presenca import (
    Presenca,
    classificar_por_url,
    classificar_resposta,
    url_publica,
    visitar,
    visitar_varios,
)
from crm.qualificacao import calcular


def perfil(**valores):
    base = PerfilNicho(
        termos_nicho="estética\nharmonização\nesteticista\nspa",
        termos_vizinhos="dermatolog\nmicropigment\nsobrancelha\nbiomedicina",
    )
    for chave, valor in valores.items():
        setattr(base, chave, valor)
    return base


def qualificar(**valores):
    dados = {
        "telefone": "(47) 99999-0000",
        "categoria": "Clínica de estética",
        "presenca": "sem_site",
        "presenca_detalhe": "",
        "avaliacoes": 86,
        "nota_maps": 4.6,
        "imagens": 2,
        "fechado_permanente": False,
        "fechado_temporario": False,
        "nao_reivindicado": True,
        "tem_agendamento": False,
        "empresa": "Clínica Aurora",
        "cidade": "Itajaí",
        "estado": "SC",
    }
    dados.update(valores)
    return calcular(perfil(), **dados)


class PresencaUrlTests(SimpleTestCase):
    def test_vazio_e_sem_site(self):
        self.assertEqual(classificar_por_url("  ").categoria, "sem_site")

    def test_rede_social_sai_do_endereco(self):
        self.assertEqual(classificar_por_url("instagram.com/clinica").detalhe, "Instagram")
        self.assertEqual(classificar_por_url("https://www.facebook.com/clinica").detalhe, "Facebook")
        self.assertEqual(classificar_por_url("https://linktr.ee/clinica").detalhe, "Linktree")

    def test_construtor_sai_do_endereco(self):
        wix = classificar_por_url("https://clinica.wixsite.com/estetica")
        self.assertEqual(wix.categoria, "site_fraco")
        self.assertEqual(wix.detalhe, "Wix")
        wp = classificar_por_url("https://clinica.wordpress.com")
        self.assertEqual(wp.detalhe, "WordPress.com")

    def test_dominio_proprio_pede_visita(self):
        self.assertIsNone(classificar_por_url("https://aurora.example"))


class PresencaHtmlTests(SimpleTestCase):
    def test_dominio_a_venda_volta_para_a_primeira_leva(self):
        html = "<html><title>aurora.com</title><body>This domain is for sale</body></html>"
        resultado = classificar_resposta("https://aurora.example", 200, html)
        self.assertEqual(resultado.categoria, "sem_site")
        self.assertEqual(resultado.detalhe, "domínio à venda")

    def test_wordpress_fino_e_site_fraco(self):
        html = "<html><head><meta name='generator' content='WordPress 6'></head><body>wp-content Olá</body></html>"
        resultado = classificar_resposta("https://aurora.example", 200, html)
        self.assertEqual(resultado.categoria, "site_fraco")
        self.assertEqual(resultado.detalhe, "WordPress com pouco conteúdo")

    def test_wordpress_com_pagina_continua_site_proprio(self):
        html = "<html><body>wp-content " + ("harmonização facial e procedimentos. " * 40) + "</body></html>"
        resultado = classificar_resposta("https://aurora.example", 200, html)
        self.assertEqual(resultado.categoria, "site_proprio")
        self.assertEqual(resultado.detalhe, "WordPress")

    def test_pagina_no_ar_nao_vira_sem_site(self):
        html = "<html><title>Clínica Aurora</title><body>" + ("agenda de avaliação " * 30) + "</body></html>"
        resultado = classificar_resposta("https://aurora.example", 200, html)
        self.assertEqual(resultado.categoria, "site_proprio")
        self.assertEqual(resultado.detalhe, "página no ar")

    def test_falha_http_fica_como_site_proprio(self):
        resultado = classificar_resposta("https://aurora.example", 404, "")
        self.assertEqual(resultado.detalhe, "não abriu")


class VisitaSeguraTests(SimpleTestCase):
    def test_rede_local_nao_e_buscada(self):
        self.assertFalse(url_publica("http://127.0.0.1/admin"))
        self.assertFalse(url_publica("http://169.254.169.254/latest"))
        self.assertFalse(url_publica("http://localhost/"))
        self.assertFalse(url_publica("file:///etc/passwd"))

    def test_visitar_rede_local_nao_abre_cliente_http(self):
        from unittest.mock import patch

        with patch("httpx.Client", side_effect=AssertionError("não deveria conectar")):
            resultado = visitar("http://127.0.0.1/admin")
        self.assertEqual(resultado.categoria, "site_proprio")
        self.assertEqual(resultado.detalhe, "não abriu")

    def test_nao_segue_redirecionamento_para_rede_local(self):
        from unittest.mock import patch

        class Resposta:
            def __init__(self):
                self.status_code = 302
                self.headers = {"location": "http://127.0.0.1/latest"}
                self.url = "https://clinica.example"

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def iter_text(self):
                yield ""

        class ClienteHttp:
            def stream(self, metodo, url):
                return Resposta()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with patch("crm.presenca.url_publica", side_effect=lambda url: "127.0.0.1" not in url):
            resultado = visitar("https://clinica.example", cliente=ClienteHttp())
        self.assertEqual(resultado.detalhe, "não abriu")

    def test_visita_deduplica_e_respeita_o_limite(self):
        from unittest.mock import patch

        with patch("crm.presenca.MAX_VISITAS", 1), patch(
            "crm.presenca.visitar",
            return_value=Presenca("site_proprio", "página no ar", True),
        ) as visita:
            saida = visitar_varios(["https://a.example", "https://a.example", "https://b.example"])
        self.assertEqual(visita.call_count, 1)
        self.assertEqual(saida["https://b.example"].detalhe, "não verificado")


class NotaTests(SimpleTestCase):
    def test_lead_forte_sem_site_chega_a_90(self):
        resultado = qualificar()
        self.assertEqual(resultado.categoria, "sem_site")
        self.assertEqual(resultado.nota, 90)
        self.assertIn("Não há site no perfil do Google.", resultado.dossie)
        self.assertIn("Oferta: Landing", resultado.dossie)

    def test_acento_nao_tira_do_nicho(self):
        resultado = qualificar(categoria="Harmonização facial", avaliacoes=40, imagens=None, nao_reivindicado=False)
        self.assertEqual(resultado.categoria, "sem_site")
        self.assertEqual(resultado.nota, 75)

    def test_vizinho_entra_com_menos_pontos(self):
        resultado = qualificar(
            categoria="Dermatologista",
            avaliacoes=86,
            imagens=None,
            nao_reivindicado=False,
        )
        self.assertEqual(resultado.categoria, "sem_site")
        self.assertEqual(resultado.nota, 60)
        self.assertIn("Categoria vizinha do nicho.", resultado.dossie)

    def test_salao_fica_fora_do_nicho(self):
        resultado = qualificar(categoria="Salão de beleza")
        self.assertEqual(resultado.categoria, "fora_nicho")
        self.assertEqual(resultado.nota, 0)

    def test_sem_telefone_corta_antes_da_nota(self):
        resultado = qualificar(telefone="")
        self.assertEqual(resultado.categoria, "sem_telefone")
        self.assertEqual(resultado.nota, 0)

    def test_fechado_em_definitivo_sai_da_leva(self):
        resultado = qualificar(fechado_permanente=True)
        self.assertEqual(resultado.categoria, "fechado")

    def test_fechado_temporariamente_esmaga_a_nota(self):
        resultado = qualificar(fechado_temporario=True)
        self.assertEqual(resultado.categoria, "sem_site")
        self.assertEqual(resultado.nota, 18)
        self.assertIn("fechado temporariamente", resultado.motivo)

    def test_agendamento_desconta(self):
        resultado = qualificar(tem_agendamento=True)
        self.assertEqual(resultado.nota, 80)

    def test_nota_nao_passa_de_100_nem_fica_negativa(self):
        alto = qualificar()
        self.assertLessEqual(alto.nota, 100)
        baixo = calcular(
            perfil(pontos_agendamento=100, pontos_nicho=25),
            telefone="47999990000",
            categoria="Clínica de estética",
            presenca="sem_site",
            presenca_detalhe="",
            avaliacoes=0,
            nota_maps=None,
            imagens=None,
            fechado_permanente=False,
            fechado_temporario=False,
            nao_reivindicado=False,
            tem_agendamento=True,
            empresa="A",
            cidade="",
            estado="",
        )
        self.assertEqual(baixo.nota, 0)

    def test_rede_social_tem_oferta_propria(self):
        resultado = qualificar(presenca="rede_social", presenca_detalhe="Instagram")
        self.assertEqual(resultado.categoria, "rede_social")
        self.assertIn("O site apontado é Instagram.", resultado.dossie)

    def test_cidade_nao_muda_a_nota(self):
        itajai = qualificar(cidade="Itajaí")
        outro = qualificar(cidade="Manaus")
        self.assertEqual(itajai.nota, outro.nota)


class LeituraCsvTests(TestCase):
    def test_le_campos_do_maps_e_listas(self):
        from crm.importacao import linha_apify

        linha = linha_apify(
            {
                "title": "Clínica Aurora",
                "phone": "",
                "phoneUnformatted": "+5547999990000",
                "categoryName": "Clínica de estética",
                "categories": '["Clínica de estética", "Spa"]',
                "reviewsCount": "1.234",
                "totalScore": "4,6",
                "emails": '["ola@clinica.com"]',
                "claimThisBusiness": "true",
                "permanentlyClosed": "false",
            }
        )
        self.assertEqual(linha["telefone"], "+5547999990000")
        self.assertEqual(linha["avaliacoes"], 1234)
        self.assertEqual(linha["nota_maps"], 4.6)
        self.assertIn("Spa", linha["categoria"])
        self.assertEqual(linha["email"], "ola@clinica.com")
        self.assertTrue(linha["nao_reivindicado"])
        self.assertFalse(linha["fechado_permanente"])
