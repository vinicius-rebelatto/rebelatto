from datetime import date

from django.db import migrations

# (título, detalhes, frente, prioridade, prazo, status)
TAREFAS = [
    ("Comprar 2 chips pré-pagos da TIM (principal e reserva)",
     "Ativar no CPF. O principal vai para o WhatsApp Business da captação; o reserva fica guardado para trocar se o número for restrito.",
     "operacao", 1, date(2026, 11, 4), "a_fazer"),
    ("Separar um celular Android para o número de captação",
     "Fica ligado no Wi-Fi com o WhatsApp Business aberto. A Evolution API entra como aparelho conectado.",
     "operacao", 1, date(2026, 11, 4), "a_fazer"),
    ("Instalar o WhatsApp Business e completar o perfil",
     "Nome Rebel Tech, logo, site, descrição e horário de atendimento.",
     "operacao", 1, date(2026, 11, 5), "a_fazer"),
    ("Usar o número novo em conversas reais por 5 a 7 dias",
     "Aquecimento antes da automação: conversar com conhecidos, entrar em grupos, responder mensagens.",
     "operacao", 2, date(2026, 11, 12), "a_fazer"),
    ("Colocar o APIFY_TOKEN no .env da VPS",
     "Nunca no código. Se preferir, gerar um token novo no painel do Apify antes.",
     "sistema", 1, date(2026, 11, 3), "a_fazer"),
    ("Rodar a primeira busca de teste no Apify",
     "Um termo, uma cidade, uns 20 a 50 lugares. Sobram US$ 4,60 de crédito grátis neste mês.",
     "captacao", 1, date(2026, 11, 4), "a_fazer"),
    ("Revisar os pesos do Nicho com os leads da busca de teste",
     "Ver se a primeira leva faz sentido e ajustar a nota em Clientes > Nicho.",
     "captacao", 2, date(2026, 11, 6), "a_fazer"),
    ("Escrever e aprovar os 3 scripts da primeira mensagem (A, B e C)",
     "Mudar uma coisa por vez entre eles e terminar com uma pergunta fácil de responder.",
     "captacao", 1, date(2026, 11, 7), "a_fazer"),
    ("Subir Evolution API e Redis na VPS",
     "Conectar o WhatsApp Business do número novo por QR code e configurar o webhook para o Django.",
     "sistema", 1, date(2026, 11, 9), "a_fazer"),
    ("Criar a fila de tarefas em segundo plano",
     "Para envios, follow-ups e buscas rodarem sozinhos.",
     "sistema", 2, date(2026, 11, 9), "a_fazer"),
    ("Tabelas de experimento, interação e reunião + painel do funil",
     "Abordados → responderam → reunião → compareceu → fechou / em validação / perdido, por script.",
     "sistema", 1, date(2026, 11, 11), "a_fazer"),
    ("Agente de conversão no módulo de IA (modo copiloto)",
     "Objetivo único: marcar a reunião. Nos primeiros dias, ele escreve e você aprova.",
     "ia", 1, date(2026, 11, 12), "a_fazer"),
    ("Conectar o Google Calendar (vinirbt@gmail.com)",
     "Para o agendador oferecer horários livres e mandar os lembretes.",
     "sistema", 2, date(2026, 11, 12), "a_fazer"),
    ("Definir o teto mensal de IA no Orçamento",
     "Por exemplo US$ 30 por mês para a captação, enquanto estiver em teste.",
     "ia", 2, date(2026, 11, 6), "a_fazer"),
    ("Conferir a regra do 0303 e do Não Me Perturbe",
     "Só antes de colocar ligações com IA. Não bloqueia o WhatsApp.",
     "operacao", 3, None, "a_fazer"),
    ("Colocar a operação de captação no ar",
     "Meta: primeiros envios reais com o número aquecido e o funil medindo.",
     "captacao", 1, date(2026, 11, 16), "a_fazer"),
    ("Integrar o Apify ao CRM",
     "Buscas pelo ERP, todas as colunas salvas no lead e qualificação automática.",
     "sistema", 1, date(2026, 11, 3), "fazendo"),
]


def criar(apps, schema_editor):
    Tarefa = apps.get_model("erp", "Tarefa")
    if Tarefa.objects.exists():
        return
    Tarefa.objects.bulk_create(
        Tarefa(titulo=t, descricao=d, frente=f, prioridade=p, prazo=prazo, status=s)
        for t, d, f, p, prazo, s in TAREFAS
    )


def remover(apps, schema_editor):
    Tarefa = apps.get_model("erp", "Tarefa")
    Tarefa.objects.filter(titulo__in=[t[0] for t in TAREFAS]).delete()


class Migration(migrations.Migration):
    dependencies = [("erp", "0001_initial")]

    operations = [migrations.RunPython(criar, remover)]
