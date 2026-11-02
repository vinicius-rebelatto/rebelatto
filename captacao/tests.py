from datetime import datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from captacao import conversao, evolution, operacao, textos
from captacao.models import Abordagem, Experimento, Mensagem, NumeroWhatsApp, OptOut, Variante
from crm.models import Cliente

FUSO = timezone.get_current_timezone()


def quarta(hora=10, minuto=0):
    return timezone.make_aware(datetime(2026, 11, 4, hora, minuto), FUSO)


def cliente(nome, telefone, categoria="sem_site", nota=80, status=Cliente.Status.A_PROSPECTAR):
    return Cliente.objects.create(
        empresa=nome, telefone=telefone, cidade="Itajaí", categoria_lead=categoria, nota=nota, status=status
    )


def experimento(por_variante=2, modo=Experimento.ModoIA.COPILOTO):
    exp = Experimento.objects.create(nome="Teste", leads_por_variante=por_variante, modo_ia=modo)
    for letra in "ABC":
        Variante.objects.create(experimento=exp, letra=letra, texto=f"{{Oi|Olá}}, {{{{empresa}}}}! Script {letra}")
    return exp


def numero(**extra):
    dados = dict(
        apelido="TIM",
        telefone="5547999990000",
        instancia="rebel-tim",
        conexao=NumeroWhatsApp.Conexao.CONECTADO,
        envios_ativos=True,
        inicio_aquecimento=quarta().date(),
    )
    dados.update(extra)
    return NumeroWhatsApp.objects.create(**dados)


class TextosTests(TestCase):
    def test_telefones(self):
        self.assertEqual(textos.telefone_whatsapp("(47) 99999-1111"), "5547999991111")
        self.assertEqual(textos.telefone_whatsapp("+55 47 3333-1111"), "554733331111")
        self.assertEqual(textos.telefone_whatsapp("1234"), "")
        self.assertEqual(textos.chave_telefone("5547999991111"), textos.chave_telefone("554799991111"))
        self.assertEqual(textos.telefone_do_jid("554799991111@s.whatsapp.net"), "554799991111")
        self.assertEqual(textos.telefone_do_jid("12345@lid"), "")

    def test_montar_troca_campos_e_sorteia_variacoes(self):
        lead = cliente("Clínica Aurora", "47999991111")
        lead.nota_maps = "4.8"
        lead.avaliacoes = 86
        texto = textos.montar("{Oi|Olá}, {{empresa}}! Nota {{nota_maps}} ({{avaliacoes}}). {{mockup}}", lead, semente=1)
        self.assertRegex(texto, r"^(Oi|Olá), Clínica Aurora! Nota 4,8 \(86\)\. https://.+/p/clinica-aurora/$")
        self.assertEqual(textos.montar("{a|b}", lead, semente=7), textos.montar("{a|b}", lead, semente=7))
        self.assertEqual(textos.campos_desconhecidos("{{empresa}} {{preco}}"), ["preco"])

    def test_pedido_para_sair(self):
        for texto in ["SAIR", "Pare por favor", "não me mande mais isso", "me tira dessa lista"]:
            self.assertTrue(textos.pediu_para_sair(texto), texto)
        for texto in ["Quanto custa?", "pode parar aqui na clínica amanhã", "Sim, quero ver"]:
            self.assertFalse(textos.pediu_para_sair(texto), texto)


class FilaTests(TestCase):
    def test_distribui_entre_scripts_e_respeita_filtros(self):
        exp = experimento(por_variante=2)
        for i in range(8):
            cliente(f"Lead {i}", f"4799999{i:04d}", categoria="sem_site" if i % 2 else "rede_social")
        cliente("Com site", "47988880001", categoria="site_proprio")
        cliente("Sem telefone", "", categoria="sem_site")
        cliente("Importado", "47988880002", status=Cliente.Status.IMPORTADO)
        bloqueado = cliente("Bloqueado", "47988880003")
        OptOut.objects.create(chave_telefone=textos.chave_telefone("47988880003"), telefone="x")
        criadas = operacao.montar_fila(exp)
        self.assertEqual(criadas, {"A": 2, "B": 2, "C": 2})
        self.assertFalse(Abordagem.objects.filter(cliente=bloqueado).exists())
        self.assertFalse(Abordagem.objects.filter(cliente__empresa__in=["Com site", "Importado"]).exists())
        self.assertEqual(operacao.montar_fila(exp), {"A": 0, "B": 0, "C": 0})


class GuardiaoTests(TestCase):
    def setUp(self):
        self.numero = numero()

    def test_curva_horario_e_dias(self):
        self.assertEqual(self.numero.limite_em(quarta().date()), 20)
        self.assertEqual(self.numero.limite_em(quarta().date() + timedelta(days=11)), 100)
        self.assertEqual(self.numero.limite_em(quarta().date() + timedelta(days=60)), 200)
        self.assertTrue(operacao.situacao(self.numero, quarta(10)).pode_enviar)
        self.assertEqual(operacao.situacao(self.numero, quarta(8)).motivo, "Fora do horário de envio")
        domingo = quarta(10) + timedelta(days=4)
        self.assertEqual(operacao.situacao(self.numero, domingo).motivo, "Fora dos dias de envio")

    def test_limite_do_dia(self):
        exp = experimento(por_variante=30)
        self.numero.limite_manual = 2
        self.numero.save()
        for i in range(3):
            lead = cliente(f"L{i}", f"4799998{i:04d}")
            Abordagem.objects.create(
                cliente=lead, variante=exp.variantes.first(), numero=self.numero, telefone="x",
                chave_telefone=f"k{i}", envio=Abordagem.Envio.ENVIADA, enviada_em=quarta(9, i),
            )
        self.assertEqual(operacao.situacao(self.numero, quarta(10)).motivo, "Limite do dia atingido")

    def test_freia_com_resposta_baixa(self):
        exp = experimento(por_variante=50)
        for i in range(40):
            lead = cliente(f"F{i}", f"4799997{i:04d}")
            Abordagem.objects.create(
                cliente=lead, variante=exp.variantes.first(), numero=self.numero, telefone="x",
                chave_telefone=f"f{i}", envio=Abordagem.Envio.ENVIADA,
                enviada_em=quarta(10) - timedelta(days=2), respondeu_em=quarta(10) if i < 2 else None,
            )
        limite, freado, taxa = operacao.limite_hoje(self.numero, quarta(10))
        self.assertTrue(freado)
        self.assertEqual(round(taxa, 2), 0.05)
        self.assertEqual(limite, 20)

    def test_intervalo_com_pausa(self):
        self.numero.intervalo_min, self.numero.intervalo_max = 60, 60
        self.assertEqual(operacao.proximo_intervalo(self.numero, 3).total_seconds(), 60)
        self.assertGreater(operacao.proximo_intervalo(self.numero, 10).total_seconds(), 60 + 7 * 60)


class DisparoTests(TestCase):
    def setUp(self):
        self.numero = numero()
        self.exp = experimento()
        self.lead = cliente("Clínica Aurora", "(47) 99999-1111")
        operacao.montar_fila(self.exp)

    def test_envia_registra_e_agenda_o_proximo(self):
        resposta = {"key": {"id": "MSG1", "remoteJid": "554799991111@s.whatsapp.net", "fromMe": True}, "status": "PENDING"}
        with patch("captacao.evolution.enviar_texto", return_value=resposta) as enviar:
            abordagem = operacao.disparar(self.numero, quarta(10))
        enviar.assert_called_once()
        self.assertEqual(enviar.call_args.args[:2], ("rebel-tim", "5547999991111"))
        self.assertIn("Clínica Aurora", enviar.call_args.args[2])
        self.assertEqual(abordagem.envio, Abordagem.Envio.ENVIADA)
        self.assertEqual(abordagem.jid, "554799991111@s.whatsapp.net")
        self.assertEqual(Mensagem.objects.get(whatsapp_id="MSG1").autor, Mensagem.Autor.SCRIPT)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, Cliente.Status.EM_PROSPECCAO)
        self.numero.refresh_from_db()
        self.assertGreater(self.numero.proximo_envio_em, quarta(10) + timedelta(seconds=59))
        with patch("captacao.evolution.enviar_texto") as enviar:
            self.assertIsNone(operacao.disparar(self.numero, quarta(10, 0)))
            enviar.assert_not_called()

    def test_numero_sem_whatsapp_falha_e_segue(self):
        erro = evolution.EvolutionError("400", 400, {"response": {"message": [{"exists": False, "number": "x"}]}})
        with patch("captacao.evolution.enviar_texto", side_effect=erro):
            abordagem = operacao.disparar(self.numero, quarta(10))
        self.assertEqual(abordagem.envio, Abordagem.Envio.FALHOU)
        self.assertEqual(abordagem.erro, "Número sem WhatsApp.")

    def test_desligado_nao_envia(self):
        self.numero.envios_ativos = False
        self.numero.save()
        with patch("captacao.evolution.enviar_texto") as enviar:
            self.assertIsNone(operacao.disparar(self.numero, quarta(10)))
        enviar.assert_not_called()


@override_settings(EVOLUTION_API_KEY="chave", EVOLUTION_URL="http://evolution:8080")
class WebhookTests(TestCase):
    def setUp(self):
        self.numero = numero()
        exp = experimento()
        self.lead = cliente("Clínica Aurora", "(47) 99999-1111")
        operacao.montar_fila(exp)
        self.abordagem = Abordagem.objects.get()
        self.abordagem.envio = Abordagem.Envio.ENVIADA
        self.abordagem.numero = self.numero
        self.abordagem.enviada_em = timezone.now()
        self.abordagem.save()
        Mensagem.objects.create(
            abordagem=self.abordagem, numero=self.numero, direcao="saida", autor="script", texto="Oi", whatsapp_id="MSG1"
        )
        self.url = reverse("captacao:webhook", kwargs={"token": evolution.token_webhook()})

    def post(self, payload):
        return self.client.post(self.url, payload, content_type="application/json")

    def test_token_errado(self):
        resposta = self.client.post(reverse("captacao:webhook", kwargs={"token": "x"}), {}, content_type="application/json")
        self.assertEqual(resposta.status_code, 403)

    def test_resposta_do_lead_com_nono_digito_diferente(self):
        self.post({
            "event": "messages.upsert", "instance": "rebel-tim",
            "data": {"key": {"remoteJid": "554799991111@s.whatsapp.net", "fromMe": False, "id": "IN1"},
                     "message": {"conversation": "Oi! Quanto custa?"}},
        })
        self.abordagem.refresh_from_db()
        self.assertIsNotNone(self.abordagem.respondeu_em)
        self.assertEqual(self.abordagem.mensagens.filter(direcao="entrada").get().texto, "Oi! Quanto custa?")
        self.post({"event": "messages.upsert", "instance": "rebel-tim",
                   "data": {"key": {"remoteJid": "554799991111@s.whatsapp.net", "fromMe": False, "id": "IN1"},
                            "message": {"conversation": "Oi! Quanto custa?"}}})
        self.assertEqual(self.abordagem.mensagens.filter(direcao="entrada").count(), 1)

    def test_lid_com_sender_pn(self):
        self.post({
            "event": "messages.upsert", "instance": "rebel-tim",
            "data": {"key": {"remoteJid": "1234567@lid", "senderPn": "5547999991111@s.whatsapp.net", "fromMe": False, "id": "IN2"},
                     "message": {"extendedTextMessage": {"text": "Tenho interesse"}}},
        })
        self.abordagem.refresh_from_db()
        self.assertIsNotNone(self.abordagem.respondeu_em)

    def test_pedido_para_sair(self):
        self.post({"event": "messages.upsert", "instance": "rebel-tim",
                   "data": {"key": {"remoteJid": "5547999991111@s.whatsapp.net", "fromMe": False, "id": "IN3"},
                            "message": {"conversation": "SAIR"}}})
        self.abordagem.refresh_from_db()
        self.assertIsNotNone(self.abordagem.opt_out_em)
        self.assertTrue(OptOut.objects.filter(chave_telefone=self.abordagem.chave_telefone).exists())

    def test_tiques_de_entregue_e_lida(self):
        self.post({"event": "messages.update", "instance": "rebel-tim", "data": {"keyId": "MSG1", "status": "DELIVERY_ACK"}})
        self.abordagem.refresh_from_db()
        self.assertIsNotNone(self.abordagem.entregue_em)
        self.assertIsNone(self.abordagem.lida_em)
        self.post({"event": "messages.update", "instance": "rebel-tim", "data": {"keyId": "MSG1", "status": "READ"}})
        self.abordagem.refresh_from_db()
        self.assertIsNotNone(self.abordagem.lida_em)

    def test_conexao_e_qrcode(self):
        self.numero.conexao = NumeroWhatsApp.Conexao.PENDENTE
        self.numero.save()
        self.post({"event": "qrcode.updated", "instance": "rebel-tim", "data": {"qrcode": {"base64": "data:image/png;base64,AAA", "pairingCode": "ABCD1234"}}})
        self.numero.refresh_from_db()
        self.assertEqual(self.numero.codigo_pareamento, "ABCD1234")
        self.post({"event": "connection.update", "instance": "rebel-tim", "data": {"state": "open"}})
        self.numero.refresh_from_db()
        self.assertEqual(self.numero.conexao, NumeroWhatsApp.Conexao.CONECTADO)
        self.assertEqual(self.numero.qr_code, "")

    def test_mensagem_de_quem_nao_e_lead_e_ignorada(self):
        self.post({"event": "messages.upsert", "instance": "rebel-tim",
                   "data": {"key": {"remoteJid": "5511988887777@s.whatsapp.net", "fromMe": False, "id": "X"},
                            "message": {"conversation": "oi mãe"}}})
        self.assertFalse(Mensagem.objects.filter(whatsapp_id="X").exists())


class ConversaoTests(TestCase):
    def setUp(self):
        self.numero = numero()
        self.exp = experimento()
        cliente("Clínica Aurora", "(47) 99999-1111")
        operacao.montar_fila(self.exp)
        self.abordagem = Abordagem.objects.get()
        self.abordagem.numero = self.numero
        self.abordagem.envio = Abordagem.Envio.ENVIADA
        self.abordagem.texto_enviado = "Oi, Clínica Aurora!"
        self.abordagem.save()
        script = Mensagem.objects.create(abordagem=self.abordagem, direcao="saida", autor="script", texto="Oi, Clínica Aurora!")
        Mensagem.objects.filter(pk=script.pk).update(created_at=timezone.now() - timedelta(minutes=10))
        self.entrada = Mensagem.objects.create(abordagem=self.abordagem, direcao="entrada", autor="lead", texto="Quanto custa?")
        Mensagem.objects.filter(pk=self.entrada.pk).update(created_at=timezone.now() - timedelta(minutes=2))

    def test_copiloto_guarda_sugestao(self):
        with patch("captacao.conversao.executar", return_value=SimpleNamespace(texto="Depende do que vocês precisam! Topa 20 min amanhã?")) as ex:
            self.assertEqual(conversao.processar_pendentes(), 1)
        mensagens = ex.call_args.args[1]
        self.assertEqual(mensagens[0]["role"], "system")
        self.assertIn("Clínica Aurora", mensagens[0]["content"])
        self.assertEqual(mensagens[1], {"role": "user", "content": "Quanto custa?"})
        self.entrada.refresh_from_db()
        self.assertEqual(self.entrada.sugestao_status, "pendente")
        self.assertIn("20 min", self.entrada.sugestao)
        self.assertEqual(conversao.processar_pendentes(), 0)

    def test_automatico_envia_e_passa_para_voce_quando_pede(self):
        self.exp.modo_ia = Experimento.ModoIA.AUTOMATICO
        self.exp.save()
        with patch("captacao.conversao.executar", return_value=SimpleNamespace(texto="Bora marcar?")), patch(
            "captacao.evolution.enviar_texto", return_value={"key": {"id": "OUT1"}}
        ) as enviar:
            conversao.processar_pendentes()
        enviar.assert_called_once()
        self.assertEqual(Mensagem.objects.get(whatsapp_id="OUT1").autor, Mensagem.Autor.IA)
        Mensagem.objects.filter(whatsapp_id="OUT1").update(created_at=timezone.now() - timedelta(minutes=90 / 60))
        novo = Mensagem.objects.create(abordagem=self.abordagem, direcao="entrada", autor="lead", texto="Quero falar com uma pessoa")
        Mensagem.objects.filter(pk=novo.pk).update(created_at=timezone.now() - timedelta(minutes=1))
        with patch("captacao.conversao.executar", return_value=SimpleNamespace(texto="[VOCE]")), patch(
            "captacao.evolution.enviar_texto"
        ) as enviar:
            conversao.processar_pendentes()
        enviar.assert_not_called()
        novo.refresh_from_db()
        self.assertEqual(novo.sugestao_status, "passar")

    def test_agente_criado_com_prompt(self):
        agente = conversao.garantir_agente()
        self.assertIn("marcar uma conversa", agente.versao_ativa.prompt)


@override_settings(EVOLUTION_API_KEY="chave", EVOLUTION_URL="http://evolution:8080")
class TelasTests(TestCase):
    def setUp(self):
        usuario = get_user_model().objects.create_user("staff", password="x", is_staff=True)
        self.client.force_login(usuario)

    def test_conectar_numero_gera_qr(self):
        resposta_evo = {"instance": {"instanceName": "rebel-tim"}, "qrcode": {"base64": "data:image/png;base64,QQ", "pairingCode": "WZYEH1YY"}}
        with patch("captacao.evolution.criar_instancia", return_value=resposta_evo) as criar, patch(
            "captacao.evolution.estado", return_value="connecting"
        ):
            resposta = self.client.post(reverse("captacao:numero_create"), {"apelido": "TIM", "telefone": "(47) 99999-0000"}, follow=True)
        criar.assert_called_once_with("rebel-tim", "5547999990000")
        self.assertContains(resposta, "data:image/png;base64,QQ")
        self.assertContains(resposta, "WZYEH1YY")

    def test_ativar_envios_comeca_aquecimento(self):
        n = numero(envios_ativos=False, inicio_aquecimento=None)
        dados = {"envios_ativos": "on", "hora_inicio": "09:00", "hora_fim": "18:00", "intervalo_min": 60,
                 "intervalo_max": 150, "pausa_a_cada": 10, "pausa_minutos": 10}
        self.client.post(reverse("captacao:numero_detail", args=[n.pk]), dados)
        n.refresh_from_db()
        self.assertTrue(n.envios_ativos)
        self.assertEqual(n.inicio_aquecimento, timezone.localdate())

    def test_experimento_painel_e_conversa(self):
        dados = {"nome": "Primeiro teste", "ativo": "on", "leads_por_variante": 100, "nota_minima": 0,
                 "modo_ia": "copiloto", "previa_do_link": "on", "categorias_escolhidas": ["sem_site", "rede_social"]}
        for letra in "abc":
            dados[f"{letra}-nome"] = f"gancho {letra}"
            dados[f"{letra}-texto"] = "Oi {{empresa}}"
        resposta = self.client.post(reverse("captacao:experimento_create"), dados, follow=True)
        exp = Experimento.objects.get()
        self.assertEqual(exp.variantes.count(), 3)
        self.assertContains(resposta, "Script C")
        cliente("Lead X", "47999991234")
        self.client.post(reverse("captacao:experimento_fila", args=[exp.pk]))
        abordagem = Abordagem.objects.get()
        resposta = self.client.get(reverse("captacao:conversa_detail", args=[abordagem.pk]))
        self.assertContains(resposta, "Reunião e resultado")
        self.client.post(reverse("captacao:conversa_detail", args=[abordagem.pk]),
                         {"acao": "resultado", "reuniao_para": "2026-11-10T14:00", "compareceu": "", "resultado": ""})
        abordagem.refresh_from_db()
        self.assertIsNotNone(abordagem.reuniao_marcada_em)
        self.assertEqual(self.client.get(reverse("captacao:painel")).status_code, 200)
        self.assertEqual(self.client.get(reverse("captacao:conversa_list") + "?f=todas").status_code, 200)

    def test_campo_desconhecido_no_script(self):
        dados = {"nome": "X", "leads_por_variante": 100, "nota_minima": 0, "modo_ia": "copiloto",
                 "categorias_escolhidas": ["sem_site"]}
        for letra in "abc":
            dados[f"{letra}-texto"] = "Oi {{preco}}"
        resposta = self.client.post(reverse("captacao:experimento_create"), dados)
        self.assertContains(resposta, "Campo desconhecido")


class WorkerTests(TestCase):
    def test_uma_volta(self):
        numero(envios_ativos=True)
        with patch("captacao.operacao.disparar", return_value=None) as disparar, patch(
            "captacao.conversao.processar_pendentes", return_value=0
        ):
            call_command("rodar_captacao", "--uma-vez", stdout=open("/dev/null", "w"))
        disparar.assert_called_once()


class HoraTests(TestCase):
    def test_janela_padrao(self):
        n = numero()
        self.assertEqual((n.hora_inicio, n.hora_fim), (time(9), time(18)))
