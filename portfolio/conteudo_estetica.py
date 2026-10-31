"""Conteúdo demonstrativo da biblioteca de estética.

Tudo aqui é exemplo. Nas páginas do lead este texto sai marcado como
ilustrativo: não descreve a clínica, não promete resultado e não tem preço.
Um catálogo só, usado por todos os templates; cada template veste com o
visual dele.
"""

SERVICOS = [
    {
        "slug": "avaliacao-facial",
        "nome": "Avaliação facial",
        "categoria": "Primeira visita",
        "resumo": "Uma conversa com tempo para entender o que incomoda e o que faz sentido agora.",
        "descricao": [
            "A avaliação é o ponto de partida de qualquer tratamento. Olhamos o rosto em luz natural, de frente e de perfil, e ouvimos o que você gostaria de mudar — e o que prefere manter.",
            "Ao final, você recebe um plano por escrito: o que pode ser feito agora, o que pode esperar e o intervalo entre cada etapa. A avaliação não obriga a nenhum procedimento.",
        ],
        "indicado": [
            "Quem nunca fez um procedimento estético e quer entender as opções",
            "Quem já faz tratamentos e quer revisar o plano",
            "Quem tem uma queixa específica e quer saber se há indicação",
        ],
        "etapas": [
            ("Conversa", "Você conta seu histórico, expectativas e o que incomoda."),
            ("Análise", "Observação do rosto, da pele e das proporções em luz natural."),
            ("Plano", "Indicação por escrito, com ordem e intervalo de cada etapa."),
        ],
        "duracao": "Cerca de 50 minutos",
        "retorno": "Sem retorno obrigatório",
        "cuidados": [
            "Venha sem maquiagem, se possível",
            "Traga a lista de procedimentos que já fez e quando",
            "Informe medicamentos de uso contínuo",
        ],
        "duvidas": [
            ("A avaliação já inclui algum procedimento?", "Não. A primeira visita é só para conversar e avaliar. O procedimento, se fizer sentido, fica para outro dia."),
            ("Preciso já saber o que quero fazer?", "Não. A avaliação existe justamente para ajudar a decidir."),
        ],
    },
    {
        "slug": "harmonizacao-facial",
        "nome": "Harmonização facial",
        "categoria": "Rosto",
        "resumo": "Um conjunto de técnicas planejado em etapas para equilibrar as proporções do rosto.",
        "descricao": [
            "Harmonização facial não é um procedimento único, e sim um plano. Ele pode combinar diferentes técnicas para trabalhar contorno, proporção e qualidade da pele, sempre respeitando os traços de cada pessoa.",
            "O objetivo é um resultado discreto: parecer descansada, não diferente. Por isso o plano é feito em etapas, com intervalo para o rosto se acomodar entre uma e outra.",
        ],
        "indicado": [
            "Quem sente o rosto cansado ou desproporcional",
            "Quem quer tratar várias regiões de forma planejada",
            "Quem prefere mudanças graduais e naturais",
        ],
        "etapas": [
            ("Avaliação", "Mapa do rosto com as regiões a tratar e a ordem."),
            ("Primeira etapa", "As regiões prioritárias, definidas no plano."),
            ("Intervalo", "Tempo para o rosto se acomodar antes de seguir."),
            ("Revisão", "Retorno para avaliar e ajustar o necessário."),
        ],
        "duracao": "De 40 a 90 minutos por etapa",
        "retorno": "Revisão em cerca de 15 dias",
        "cuidados": [
            "Evitar atividade física intensa nas primeiras 24 horas",
            "Não massagear as regiões tratadas, salvo orientação",
            "Evitar sol forte e calor excessivo nos primeiros dias",
        ],
        "duvidas": [
            ("O resultado fica artificial?", "O plano é pensado para respeitar seus traços. Quantidade e regiões são definidas na avaliação, sem exagero."),
            ("Quantas sessões são necessárias?", "Depende do plano. Algumas pessoas fazem uma etapa; outras preferem dividir em duas ou três."),
        ],
    },
    {
        "slug": "toxina-botulinica",
        "nome": "Toxina botulínica",
        "categoria": "Rosto",
        "resumo": "Suaviza linhas de expressão preservando o movimento natural do rosto.",
        "descricao": [
            "A toxina botulínica relaxa temporariamente a musculatura responsável pelas linhas de expressão, como as da testa, entre as sobrancelhas e ao redor dos olhos.",
            "A aplicação é rápida, com agulhas finas, e o efeito aparece de forma gradual nos dias seguintes. A dose é ajustada para manter a expressão — o rosto continua se movendo.",
        ],
        "indicado": [
            "Linhas na testa e entre as sobrancelhas",
            "Pés de galinha",
            "Quem quer prevenir o aprofundamento das linhas",
        ],
        "etapas": [
            ("Avaliação", "Análise da expressão em movimento e em repouso."),
            ("Aplicação", "Pontos definidos no plano, com agulhas finas."),
            ("Revisão", "Retorno para conferir o resultado e ajustar se preciso."),
        ],
        "duracao": "Cerca de 30 minutos",
        "retorno": "Revisão em cerca de 15 dias",
        "cuidados": [
            "Não deitar nas quatro horas seguintes",
            "Evitar exercícios intensos no mesmo dia",
            "Não massagear a região tratada",
        ],
        "duvidas": [
            ("Quanto tempo dura o efeito?", "Varia de pessoa para pessoa. Em geral, alguns meses; o retorno é combinado na avaliação."),
            ("Vou perder a expressão?", "Não é esse o objetivo. A dose é ajustada para suavizar as linhas mantendo o movimento."),
        ],
    },
    {
        "slug": "preenchimento-labial",
        "nome": "Preenchimento labial",
        "categoria": "Rosto",
        "resumo": "Contorno e hidratação dos lábios, com volume apenas se fizer sentido.",
        "descricao": [
            "O preenchimento labial pode definir o contorno, corrigir assimetrias e devolver hidratação. Volume é uma escolha, não uma regra.",
            "O plano considera a proporção dos lábios com o restante do rosto. Muitas vezes, pouca quantidade bem posicionada é o que traz o resultado mais natural.",
        ],
        "indicado": [
            "Lábios com contorno pouco definido",
            "Assimetrias leves",
            "Lábios ressecados ou com linhas finas",
        ],
        "etapas": [
            ("Avaliação", "Proporção, simetria e expectativa."),
            ("Aplicação", "Com anestésico tópico para mais conforto."),
            ("Revisão", "Retorno para avaliar o resultado assentado."),
        ],
        "duracao": "Cerca de 45 minutos",
        "retorno": "Revisão em cerca de 15 dias",
        "cuidados": [
            "Inchaço leve é comum nos primeiros dias",
            "Evitar bebidas muito quentes no mesmo dia",
            "Não pressionar os lábios nas primeiras horas",
        ],
        "duvidas": [
            ("Dói?", "Usamos anestésico para deixar a aplicação mais confortável. A sensação varia de pessoa para pessoa."),
            ("O resultado é imediato?", "Parte sim, mas o resultado final aparece depois que o inchaço inicial passa."),
        ],
    },
    {
        "slug": "bioestimuladores",
        "nome": "Bioestimuladores de colágeno",
        "categoria": "Pele",
        "resumo": "Estimulam a produção de colágeno para mais firmeza, de forma gradual.",
        "descricao": [
            "Os bioestimuladores ajudam o próprio organismo a produzir colágeno. O resultado não é imediato: a firmeza vai aparecendo ao longo das semanas.",
            "É uma opção para quem nota a pele mais flácida e prefere uma melhora progressiva, sem mudança brusca na aparência.",
        ],
        "indicado": [
            "Flacidez leve a moderada",
            "Perda de firmeza no contorno do rosto",
            "Quem prefere resultados graduais",
        ],
        "etapas": [
            ("Avaliação", "Qualidade da pele e regiões a tratar."),
            ("Sessões", "Aplicações com intervalo definido no plano."),
            ("Acompanhamento", "Revisões para acompanhar a evolução."),
        ],
        "duracao": "Cerca de 50 minutos",
        "retorno": "Nova sessão conforme o plano",
        "cuidados": [
            "Seguir a orientação de massagem, quando indicada",
            "Evitar sol forte nos primeiros dias",
            "Manter a hidratação da pele",
        ],
        "duvidas": [
            ("Quando vejo resultado?", "A melhora é gradual e aparece ao longo das semanas seguintes."),
            ("Quantas sessões?", "Depende da pele de cada pessoa. O número é definido na avaliação."),
        ],
    },
    {
        "slug": "skinbooster",
        "nome": "Skinbooster",
        "categoria": "Pele",
        "resumo": "Hidratação profunda para devolver viço e textura à pele.",
        "descricao": [
            "O skinbooster leva hidratação para as camadas mais profundas da pele. O efeito é de uma pele mais viçosa, com textura uniforme e aspecto descansado.",
            "Pode ser feito no rosto, no pescoço e no colo, e combina bem com outros tratamentos do plano.",
        ],
        "indicado": [
            "Pele opaca ou desidratada",
            "Linhas finas de ressecamento",
            "Quem quer melhorar a textura sem mudar volume",
        ],
        "etapas": [
            ("Avaliação", "Análise da hidratação e da textura da pele."),
            ("Sessões", "Aplicações espaçadas, conforme o plano."),
            ("Manutenção", "Sessões periódicas para manter o resultado."),
        ],
        "duracao": "Cerca de 40 minutos",
        "retorno": "Nova sessão conforme o plano",
        "cuidados": [
            "Pequenas marcas podem aparecer e somem em poucos dias",
            "Evitar maquiagem nas primeiras horas",
            "Usar protetor solar diariamente",
        ],
        "duvidas": [
            ("Muda o formato do rosto?", "Não. O foco é a qualidade da pele, não o volume."),
            ("Posso fazer junto com outros tratamentos?", "Em muitos casos, sim. A combinação é definida na avaliação."),
        ],
    },
    {
        "slug": "limpeza-de-pele",
        "nome": "Limpeza de pele",
        "categoria": "Pele",
        "resumo": "Remove impurezas e prepara a pele para os outros cuidados.",
        "descricao": [
            "A limpeza de pele remove impurezas, cravos e excesso de oleosidade, deixando a pele mais uniforme e preparada para os outros tratamentos.",
            "O protocolo é ajustado ao tipo de pele, com produtos e etapas escolhidos para cada caso.",
        ],
        "indicado": [
            "Pele com cravos e poros obstruídos",
            "Oleosidade excessiva",
            "Manutenção periódica da saúde da pele",
        ],
        "etapas": [
            ("Higienização", "Limpeza e preparação da pele."),
            ("Extração", "Remoção cuidadosa de cravos e impurezas."),
            ("Finalização", "Máscara calmante, hidratação e proteção."),
        ],
        "duracao": "Cerca de 1 hora",
        "retorno": "Manutenção mensal, se indicada",
        "cuidados": [
            "Leve vermelhidão pode aparecer nas primeiras horas",
            "Evitar maquiagem no mesmo dia",
            "Usar protetor solar diariamente",
        ],
        "duvidas": [
            ("Com que frequência devo fazer?", "Depende do tipo de pele. Para muitas pessoas, uma vez por mês funciona bem."),
            ("Serve para pele sensível?", "Sim, com o protocolo ajustado. Por isso a pele é avaliada antes."),
        ],
    },
    {
        "slug": "peeling",
        "nome": "Peeling",
        "categoria": "Pele",
        "resumo": "Renovação da camada superficial para uniformizar tom e textura.",
        "descricao": [
            "O peeling acelera a renovação da pele, ajudando a uniformizar o tom, suavizar manchas leves e melhorar a textura.",
            "Existem diferentes tipos e intensidades. A escolha depende da pele, da época do ano e do resultado esperado.",
        ],
        "indicado": [
            "Manchas leves e tom irregular",
            "Textura áspera",
            "Marcas superficiais",
        ],
        "etapas": [
            ("Avaliação", "Escolha do tipo e da intensidade do peeling."),
            ("Preparo", "Cuidados em casa antes da sessão, quando indicados."),
            ("Sessão", "Aplicação e orientação para os dias seguintes."),
        ],
        "duracao": "Cerca de 40 minutos",
        "retorno": "Conforme o protocolo",
        "cuidados": [
            "A pele pode descamar nos dias seguintes",
            "Proteção solar rigorosa",
            "Não arrancar a pele que descama",
        ],
        "duvidas": [
            ("Preciso ficar em casa depois?", "Depende da intensidade. Os mais leves permitem seguir a rotina normalmente."),
            ("Posso fazer no verão?", "Alguns tipos, sim, com cuidados extras. A indicação é feita na avaliação."),
        ],
    },
]

SOBRE = [
    "{nome} é um espaço de estética dedicado ao cuidado da pele e do rosto, com atendimento individual e hora marcada.",
    "Acreditamos que todo tratamento começa por uma boa conversa. Por isso a primeira visita é sempre uma avaliação, sem compromisso com nenhum procedimento.",
    "Cada plano é feito por escrito, respeitando os traços, o tempo e as expectativas de cada pessoa.",
]

DIFERENCIAIS = [
    ("Avaliação antes de tudo", "Nenhum procedimento é indicado sem conversa e análise."),
    ("Plano por escrito", "Você sabe o que será feito, em que ordem e por quê."),
    ("Resultado natural", "O objetivo é realçar, não transformar."),
    ("Acompanhamento", "Retornos agendados para ajustar o necessário."),
]

PRIMEIRA_VISITA = [
    ("Agendamento", "Pelo WhatsApp, no horário que for melhor para você."),
    ("Conversa", "Você conta o que incomoda e o que espera."),
    ("Avaliação", "Análise do rosto e da pele em luz natural."),
    ("Plano", "Indicação por escrito, sem compromisso."),
]

DUVIDAS = [
    ("A avaliação tem algum compromisso?", "Não. Você recebe o plano e decide com calma se quer seguir."),
    ("Como faço para agendar?", "Pelo WhatsApp. Respondemos com os horários disponíveis da semana."),
    ("Atendem com hora marcada?", "Sim. Cada atendimento tem seu horário, sem espera."),
    ("Posso remarcar?", "Sim. Basta avisar pelo WhatsApp com antecedência."),
    ("Quais formas de pagamento?", "As condições são explicadas na avaliação, junto com o plano."),
]

POR_SLUG = {s["slug"]: s for s in SERVICOS}


def servico(slug: str) -> dict | None:
    return POR_SLUG.get(slug)


def contexto(nome: str) -> dict:
    return {
        "servicos": SERVICOS,
        "sobre": [p.format(nome=nome) for p in SOBRE],
        "diferenciais": DIFERENCIAIS,
        "primeira_visita": PRIMEIRA_VISITA,
        "duvidas_gerais": DUVIDAS,
    }
