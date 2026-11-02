from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from erp.models import Tarefa


class TarefaTests(TestCase):
    def setUp(self):
        usuario = get_user_model().objects.create_user("staff", password="x", is_staff=True)
        self.client.force_login(usuario)

    def test_tarefas_iniciais_da_operacao(self):
        self.assertTrue(Tarefa.objects.filter(titulo__icontains="chips pré-pagos da TIM").exists())
        self.assertTrue(Tarefa.objects.filter(status=Tarefa.Status.FAZENDO).exists())

    def test_quadro_mostra_colunas_e_atrasadas(self):
        Tarefa.objects.all().delete()
        Tarefa.objects.create(titulo="Ligar para a TIM", prazo=timezone.localdate() - timedelta(days=1))
        Tarefa.objects.create(titulo="Feita ontem", status=Tarefa.Status.FEITA)
        resposta = self.client.get(reverse("erp:tarefa_list"))
        self.assertContains(resposta, "Ligar para a TIM")
        self.assertContains(resposta, "Feita ontem")
        self.assertContains(resposta, "is-late")
        self.assertEqual(resposta.context["atrasadas"], 1)

    def test_adicionar_rapido(self):
        resposta = self.client.post(
            reverse("erp:tarefa_list"), {"titulo": "Comprar celular", "frente": "operacao", "prioridade": 1}
        )
        self.assertEqual(resposta.status_code, 302)
        tarefa = Tarefa.objects.get(titulo="Comprar celular")
        self.assertEqual(tarefa.status, Tarefa.Status.A_FAZER)

    def test_concluir_marca_data_e_reabrir_limpa(self):
        tarefa = Tarefa.objects.create(titulo="X")
        self.client.post(reverse("erp:tarefa_status", args=[tarefa.pk]), {"status": "feita"})
        tarefa.refresh_from_db()
        self.assertIsNotNone(tarefa.concluida_em)
        self.assertFalse(tarefa.atrasada)
        self.client.post(reverse("erp:tarefa_status", args=[tarefa.pk]), {"status": "a_fazer", "next": "//evil.com"})
        tarefa.refresh_from_db()
        self.assertIsNone(tarefa.concluida_em)

    def test_filtro_por_frente(self):
        Tarefa.objects.all().delete()
        Tarefa.objects.create(titulo="Sistema 1", frente="sistema")
        Tarefa.objects.create(titulo="Operação 1", frente="operacao")
        resposta = self.client.get(reverse("erp:tarefa_list"), {"frente": "sistema"})
        self.assertContains(resposta, "Sistema 1")
        self.assertNotContains(resposta, "Operação 1")

    def test_editar_e_excluir(self):
        tarefa = Tarefa.objects.create(titulo="Antes")
        self.client.post(
            reverse("erp:tarefa_edit", args=[tarefa.pk]),
            {"titulo": "Depois", "status": "fazendo", "prioridade": 2, "frente": "ia", "descricao": "", "prazo": ""},
        )
        tarefa.refresh_from_db()
        self.assertEqual((tarefa.titulo, tarefa.status), ("Depois", "fazendo"))
        self.client.post(reverse("erp:tarefa_delete", args=[tarefa.pk]))
        self.assertFalse(Tarefa.objects.filter(pk=tarefa.pk).exists())

    def test_dashboard_mostra_proximas(self):
        resposta = self.client.get(reverse("erp:dashboard"))
        self.assertContains(resposta, "Próximas tarefas")
