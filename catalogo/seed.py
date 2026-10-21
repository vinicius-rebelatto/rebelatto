"""Catálogo inicial da Rebelatto. Preço de tabela; o desconto mora na proposta."""

from decimal import Decimal

from django.db import transaction

# nome, descricao, preco, cobranca, complemento
SERVICOS = [
    ("Página", "Página única do pacote.", "0", "unico", False),
    ("WhatsApp", "Botão com mensagem pronta.", "0", "unico", False),
    ("SEO básico", "Título, descrição e compartilhamento.", "0", "unico", False),
    ("Publicação", "Página no ar, com SSL.", "0", "unico", False),
    ("Formulário de contato", "Formulário ligado ao e-mail da clínica.", "0", "unico", False),
    ("Copy da página", "Texto da página.", "0", "unico", False),
    ("Página de obrigado", "Página depois do envio.", "0", "unico", False),
    ("Pixel e analytics", "Pixel da Meta e conversões no Google.", "0", "unico", False),
    ("Política de privacidade e LGPD", "Aviso de privacidade e cookies.", "0", "unico", False),
    ("Inscrição e contagem", "Formulário de inscrição do evento.", "0", "unico", False),
    ("Checkout", "Pagamento na própria página.", "0", "unico", False),
    ("Página de links", "Página de links do Instagram.", "0", "unico", False),
    ("Análise da página", "Leitura do que já está no ar.", "0", "unico", False),
    ("Nova interface", "Visual novo da página.", "0", "unico", False),
    ("Implementação", "Colocar o visual novo no ar.", "0", "unico", False),
    ("Arquitetura do site", "Mapa de até 5 páginas.", "0", "unico", False),
    ("Layout das páginas", "Visual das páginas do site.", "0", "unico", False),
    ("Desenvolvimento do site", "Site de até 5 páginas.", "0", "unico", False),
    ("Layout da loja", "Visual da loja.", "0", "unico", False),
    ("Configuração da plataforma", "Loja configurada na plataforma escolhida.", "0", "unico", False),
    ("Pagamento e frete", "Meios de pagamento e frete.", "0", "unico", False),
    ("Cadastro de até 30 produtos", "Carga inicial do catálogo.", "0", "unico", False),
    ("Levantamento", "Conversa curta de escopo.", "0", "unico", False),
    ("Fluxo de atendimento", "Roteiro automático do WhatsApp.", "0", "unico", False),
    ("Protótipo", "Telas de referência.", "0", "unico", False),
    ("Portal com acesso restrito", "Área logada.", "0", "unico", False),
    ("Funil de leads", "Cadastro de leads e etapas.", "0", "unico", False),
    ("Treinamento", "Uma sessão com quem vai usar.", "0", "unico", False),
    ("Reunião de escopo", "Reunião para fechar o que entra no sistema.", "0", "unico", False),
    ("Hospedagem, SSL e backup", "Site no ar, com certificado e cópia.", "0", "mensal", False),
    ("Ajuste de até 1 hora", "Pequenos ajustes no mês.", "0", "mensal", False),
    ("Logo", "Marca e versões de uso.", "0", "unico", False),
    ("Identidade visual", "Cores, tipo e aplicações principais.", "0", "unico", False),
    ("Agendamento online", "A cliente marca pelo site.", "200", "unico", True),
    ("Antes e depois", "Seção de resultados.", "200", "unico", True),
    ("Chatbot", "Respostas no site, fora da landing de entrada.", "390", "unico", True),
    ("Manual de marca", "PDF com as regras de uso da marca.", "250", "unico", True),
    ("Domínio", "Registro anual no nome do cliente.", "70", "anual", True),
    ("E-mail profissional", "Até 5 caixas.", "30", "mensal", True),
]

# nome, resumo, preco, cobranca, piso, [(servico, incluso)]
PACOTES = [
    (
        "Landing Express",
        "Página, WhatsApp, SEO básico e publicação.",
        "490",
        "unico",
        False,
        [("Página", True), ("WhatsApp", True), ("SEO básico", True), ("Publicação", True)],
    ),
    (
        "Landing page",
        "A Express, mais formulário, texto e página de obrigado.",
        "790",
        "unico",
        False,
        [
            ("Página", True),
            ("WhatsApp", True),
            ("SEO básico", True),
            ("Publicação", True),
            ("Formulário de contato", True),
            ("Copy da página", True),
            ("Página de obrigado", True),
        ],
    ),
    (
        "Landing de captação",
        "Página, formulário, obrigado, WhatsApp, SEO, pixel, analytics e LGPD.",
        "990",
        "unico",
        False,
        [
            ("Página", True),
            ("Formulário de contato", True),
            ("Página de obrigado", True),
            ("WhatsApp", True),
            ("SEO básico", True),
            ("Pixel e analytics", True),
            ("Política de privacidade e LGPD", True),
        ],
    ),
    (
        "Landing de evento",
        "Página, inscrição, obrigado e WhatsApp.",
        "690",
        "unico",
        False,
        [
            ("Página", True),
            ("Inscrição e contagem", True),
            ("Página de obrigado", True),
            ("WhatsApp", True),
        ],
    ),
    (
        "Landing de venda",
        "Página, texto, checkout, antes e depois e WhatsApp.",
        "1290",
        "unico",
        False,
        [
            ("Página", True),
            ("Copy da página", True),
            ("Checkout", True),
            ("Antes e depois", True),
            ("WhatsApp", True),
        ],
    ),
    (
        "Link na bio",
        "Página de links e WhatsApp.",
        "190",
        "unico",
        False,
        [("Página de links", True), ("WhatsApp", True)],
    ),
    (
        "Redesign",
        "Análise, visual novo, implementação e SEO.",
        "790",
        "unico",
        False,
        [
            ("Análise da página", True),
            ("Nova interface", True),
            ("Implementação", True),
            ("SEO básico", True),
        ],
    ),
    (
        "Site institucional",
        "Até 5 páginas, layout, formulário, WhatsApp e SEO.",
        "1190",
        "unico",
        False,
        [
            ("Arquitetura do site", True),
            ("Layout das páginas", True),
            ("Desenvolvimento do site", True),
            ("Formulário de contato", True),
            ("WhatsApp", True),
            ("SEO básico", True),
        ],
    ),
    (
        "Loja virtual",
        "Layout, plataforma, pagamento, frete e até 30 produtos. Com reunião antes.",
        "3900",
        "unico",
        False,
        [
            ("Layout da loja", True),
            ("Configuração da plataforma", True),
            ("Pagamento e frete", True),
            ("Cadastro de até 30 produtos", True),
        ],
    ),
    (
        "Branding",
        "Logo e identidade. O manual entra à parte.",
        "890",
        "unico",
        False,
        [("Logo", True), ("Identidade visual", True), ("Manual de marca", False)],
    ),
    (
        "Automação de WhatsApp",
        "Levantamento curto e fluxo de atendimento. A API fica no cliente.",
        "1490",
        "unico",
        False,
        [("Levantamento", True), ("Fluxo de atendimento", True)],
    ),
    (
        "Área de membros",
        "Protótipo e portal com acesso restrito. Com reunião antes.",
        "2900",
        "unico",
        False,
        [("Protótipo", True), ("Portal com acesso restrito", True)],
    ),
    (
        "CRM",
        "Funil, cadastro de leads e treinamento. Escopo estreito, com reunião antes.",
        "8900",
        "unico",
        False,
        [
            ("Levantamento", True),
            ("Protótipo", True),
            ("Funil de leads", True),
            ("Treinamento", True),
        ],
    ),
    (
        "ERP",
        "Piso depois da reunião de escopo. Não é um ERP completo.",
        "8000",
        "unico",
        True,
        [("Reunião de escopo", True)],
    ),
    (
        "Hospedagem e manutenção",
        "SSL, backup e até 1 hora de ajuste no mês.",
        "97",
        "mensal",
        False,
        [("Hospedagem, SSL e backup", True), ("Ajuste de até 1 hora", True)],
    ),
]


def aplicar(Servico, Pacote, ItemPacote, FaixaDesconto) -> None:
    servicos = {}
    for ordem, (nome, descricao, preco, cobranca, complemento) in enumerate(SERVICOS, start=1):
        servico, _ = Servico.objects.get_or_create(
            nome=nome,
            defaults={
                "descricao": descricao,
                "preco": Decimal(preco),
                "cobranca": cobranca,
                "complemento": complemento,
                "ordem": ordem,
            },
        )
        servicos[nome] = servico

    for ordem, (nome, resumo, preco, cobranca, piso, itens) in enumerate(PACOTES, start=1):
        pacote, _ = Pacote.objects.get_or_create(
            nome=nome,
            defaults={
                "resumo": resumo,
                "preco": Decimal(preco),
                "cobranca": cobranca,
                "piso": piso,
                "ordem": ordem,
            },
        )
        for item_ordem, (servico_nome, incluso) in enumerate(itens, start=1):
            ItemPacote.objects.get_or_create(
                pacote=pacote,
                servico=servicos[servico_nome],
                defaults={"incluso": incluso, "ordem": item_ordem},
            )

    FaixaDesconto.objects.get_or_create(
        valor_ate=Decimal("2000"),
        defaults={"percentual": Decimal("0.05"), "ordem": 1},
    )
    FaixaDesconto.objects.get_or_create(
        valor_ate=None,
        defaults={"percentual": Decimal("0.10"), "ordem": 2},
    )


def garantir_catalogo() -> None:
    from .models import FaixaDesconto, ItemPacote, Pacote, Servico

    with transaction.atomic():
        aplicar(Servico, Pacote, ItemPacote, FaixaDesconto)
