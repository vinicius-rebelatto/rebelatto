from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from crm.models import Cliente, PerfilNicho
from crm.presenca import Presenca
from erp.forms import PerfilNichoForm

CSV = """title,phone,website,categoryName,city,state,totalScore,reviewsCount,imagesCount,claimThisBusiness,permanentlyClosed,temporarilyClosed
Clinica Aurora,(47) 99999-1111,,Clínica de estética,Itajaí,SC,4.6,86,2,true,false,false
Clinica Rede,(47) 99999-2222,https://instagram.com/clinicarede,Harmonização facial,Blumenau,SC,4.8,40,,,false,false,false
Clinica WP,(47) 99999-3333,https://aurora.example,Clínica de estética,Joinville,SC,4.5,30,10,false,false,false
Sem Fone,,https://instagram.com/semfone,Clínica de estética,Itajaí,SC,4.9,10,,,false,false,false
Salao Bella,(47) 99999-4444,,Salão de beleza,Itajaí,SC,4.9,50,1,true,false,false
Clinica Fechada,(47) 99999-5555,,Clínica de estética,Itajaí,SC,4.2,22,3,false,true,false
Clinica Aurora,(47) 99999-1111,,Clínica de estética,Itajaí,SC,4.6,86,2,true,false,false
Clinica Sul,(47) 99999-6666,,Clínica de estética,Itajaí,SC,4.4,25,8,false,false,false
Clinica Sul,(47) 99999-7777,,Clínica de estética,Itajaí,SC,4.4,25,8,false,false,false
"""


def visitas_falsas(urls):
    return {url: Presenca("site_fraco", "WordPress com pouco conteúdo", True) for url in urls}


class ImportacaoTests(TestCase):
    def setUp(self):
        usuario = get_user_model().objects.create_user("staff", password="x", is_staff=True)
        self.client.force_login(usuario)

    def test_importa_classifica_e_ordena_a_fila(self):
        arquivo = SimpleUploadedFile("leads.csv", CSV.encode("utf-8"), content_type="text/csv")
        with patch("crm.importacao.visitar_varios", side_effect=visitas_falsas) as visitas:
            previa = self.client.post(reverse("erp:cliente_import"), {"arquivo": arquivo})
            visitas.assert_called_once_with(["https://aurora.example"])
            self.assertContains(previa, "Clinica Aurora")
            self.assertContains(previa, "Duplicata")
            self.assertContains(previa, "2 unidades com este nome")
            confirmacao = self.client.post(reverse("erp:cliente_import"), {"confirm": "1"}, follow=True)
            visitas.assert_called_once()
        self.assertContains(confirmacao, "8 novo(s), 5 na primeira leva, 1 duplicata")
        self.assertEqual(Cliente.objects.filter(empresa="Clinica Aurora").count(), 1)
        self.assertEqual(Cliente.objects.filter(empresa="Clinica Sul").count(), 2)
        aurora = Cliente.objects.get(empresa="Clinica Aurora")
        self.assertEqual(aurora.categoria_lead, "sem_site")
        self.assertEqual(aurora.nota, 90)
        self.assertEqual(aurora.avaliacoes, 86)
        self.assertIn("Não há site no perfil do Google.", aurora.dossie)
        self.assertEqual(Cliente.objects.get(empresa="Clinica Rede").categoria_lead, "rede_social")
        self.assertEqual(Cliente.objects.get(empresa="Clinica WP").categoria_lead, "site_fraco")
        self.assertEqual(Cliente.objects.get(empresa="Sem Fone").categoria_lead, "sem_telefone")
        self.assertEqual(Cliente.objects.get(empresa="Salao Bella").categoria_lead, "fora_nicho")
        self.assertEqual(Cliente.objects.get(empresa="Clinica Fechada").categoria_lead, "fechado")
        html = confirmacao.content.decode()
        self.assertLess(html.index("Clinica Aurora"), html.index("Clinica Rede"))
        self.assertLess(html.index("Clinica Rede"), html.index("Clinica WP"))
        self.assertNotContains(confirmacao, "Salao Bella")

        fora = self.client.get(reverse("erp:cliente_filtragem") + "?fila=fora")
        self.assertContains(fora, "Salao Bella")
        self.assertContains(fora, "Sem Fone")
        self.assertContains(fora, "Clinica Fechada")
        self.assertNotContains(fora, "Clinica Aurora")

        self.client.post(reverse("erp:cliente_accept", args=[aurora.pk]))
        aurora.refresh_from_db()
        self.assertEqual(aurora.status, Cliente.Status.A_PROSPECTAR)
        self.assertEqual(aurora.nota, 90)

    def test_salvar_nicho_recalcula_sem_visitar_de_novo(self):
        Cliente.objects.create(
            empresa="Clinica Aurora",
            slug="clinica-aurora",
            telefone="(47) 99999-1111",
            website="https://aurora.example",
            categoria="Clínica de estética",
            cidade="Itajaí",
            estado="SC",
            presenca="sem_site",
            nota_maps="4.6",
            avaliacoes=86,
            imagens=2,
            nao_reivindicado=True,
            origem=Cliente.Origem.CSV,
            status=Cliente.Status.IMPORTADO,
        )
        with patch("crm.importacao.visitar_varios") as visitas:
            perfil = PerfilNicho.atual()
            dados = {nome: getattr(perfil, nome) for nome in PerfilNichoForm.Meta.fields}
            self.client.post(reverse("erp:cliente_nicho"), dados)
            visitas.assert_not_called()
            self.assertEqual(Cliente.objects.get(slug="clinica-aurora").nota, 90)
            dados["pontos_nicho"] = 0
            self.client.post(reverse("erp:cliente_nicho"), dados)
            visitas.assert_not_called()
        self.assertEqual(Cliente.objects.get(slug="clinica-aurora").nota, 65)

    def test_recalcular_so_visita_dominio_proprio(self):
        from crm.importacao import recalcular_importados

        Cliente.objects.create(
            empresa="Rede",
            slug="rede",
            telefone="47999992222",
            website="https://instagram.com/rede",
            categoria="Clínica de estética",
            status=Cliente.Status.IMPORTADO,
            origem=Cliente.Origem.CSV,
        )
        Cliente.objects.create(
            empresa="Proprio",
            slug="proprio",
            telefone="47999993333",
            website="https://proprio.example",
            categoria="Clínica de estética",
            status=Cliente.Status.IMPORTADO,
            origem=Cliente.Origem.CSV,
        )
        with patch("crm.importacao.visitar_varios", side_effect=visitas_falsas) as visitas:
            total, visitados = recalcular_importados(PerfilNicho.atual())
        self.assertEqual((total, visitados), (2, 1))
        visitas.assert_called_once_with(["https://proprio.example"])
        self.assertEqual(Cliente.objects.get(slug="rede").categoria_lead, "rede_social")
        self.assertEqual(Cliente.objects.get(slug="proprio").categoria_lead, "site_fraco")
