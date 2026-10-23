from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db.models import ProtectedError, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from crm.models import Cliente
from erp.views import staff_required

from .forms import PacoteForm, PropostaForm, ServicoForm
from .pdf import PdfIndisponivel, gerar_pdf, nome_arquivo, render_html
from .models import Cobranca, FaixaDesconto, ItemPacote, Pacote, Proposta, Servico
from .preco import (
    com_desconto,
    cotar,
    dinheiro,
    fracao,
    gravar,
    gravar_linhas,
    faixas,
    pontos,
    percentual_sugerido,
    texto_faixas,
)


def _extras_da_proposta(pacote, ids):
    if pacote is None:
        return []
    incluso = set(pacote.itens.filter(incluso=True).values_list("servico_id", flat=True))
    opcionais = pacote.itens.filter(incluso=False).values_list("servico_id", flat=True)
    return list(
        Servico.objects.filter(ativo=True)
        .filter(Q(complemento=True) | Q(pk__in=opcionais))
        .exclude(pk__in=incluso)
        .order_by("ordem", "nome")
        .distinct()
    )


def _ids_extras(request: HttpRequest) -> list[int]:
    origem = request.POST if request.method == "POST" else request.GET
    ids = []
    for valor in origem.getlist("extras"):
        if valor.isdigit():
            ids.append(int(valor))
    return ids


def _informados(form: PropostaForm) -> dict:
    return form.percentuais()


def _iniciais(proposta: Proposta | None, pacote, extras) -> dict:
    if proposta and proposta.pk:
        return {
            "cliente": proposta.cliente_id,
            "pacote": proposta.pacote_id,
            "observacao": proposta.observacao,
            "desconto_fixo": proposta.desconto_fixo,
            "desconto_unico": pontos(proposta.desconto_unico),
            "desconto_mensal": pontos(proposta.desconto_mensal),
            "desconto_anual": pontos(proposta.desconto_anual),
        }
    conta = cotar(pacote, extras) if pacote is not None else None
    return {
        "pacote": pacote.pk if pacote else None,
        "desconto_unico": pontos(conta["descontos"][Cobranca.UNICO]) if conta else Decimal("0"),
        "desconto_mensal": pontos(conta["descontos"][Cobranca.MENSAL]) if conta else Decimal("0"),
        "desconto_anual": pontos(conta["descontos"][Cobranca.ANUAL]) if conta else Decimal("0"),
    }


# --- Tabela -----------------------------------------------------------------


@staff_required
def pacote_list(request: HttpRequest) -> HttpResponse:
    linhas = []
    for pacote in Pacote.objects.prefetch_related("itens__servico"):
        pct = percentual_sugerido(pacote.preco)
        linhas.append(
            {
                "pacote": pacote,
                "desconto": pct,
                "na_proposta": com_desconto(pacote.preco, pct),
                "inclusos": [item.servico.nome for item in pacote.itens.all() if item.incluso],
                "opcionais": [item.servico.nome for item in pacote.itens.all() if not item.incluso],
            }
        )
    avulsos = []
    for servico in Servico.objects.filter(complemento=True, ativo=True):
        pct = percentual_sugerido(servico.preco)
        servico.desconto_sugerido = pct
        servico.na_proposta = com_desconto(servico.preco, pct)
        avulsos.append(servico)
    return render(
        request,
        "catalogo/pacotes.html",
        {
            "page_title": "Catálogo",
            "linhas": linhas,
            "avulsos": avulsos,
            "faixas": texto_faixas(),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def pacote_create(request: HttpRequest) -> HttpResponse:
    form = PacoteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        pacote = form.save()
        messages.success(request, f"Pacote “{pacote.nome}” criado. Agora marque o que entra nele.")
        return redirect("catalogo:pacote_edit", pk=pacote.pk)
    return render(request, "catalogo/pacote_form.html", {"page_title": "Novo pacote", "form": form})


@staff_required
@require_http_methods(["GET", "POST"])
def pacote_edit(request: HttpRequest, pk: int) -> HttpResponse:
    pacote = get_object_or_404(Pacote, pk=pk)
    form = PacoteForm(request.POST or None, instance=pacote)
    ligados = {item.servico_id: item for item in pacote.itens.all()}
    servicos = Servico.objects.filter(Q(ativo=True) | Q(pk__in=ligados)).order_by("ordem", "nome")
    if request.method == "POST" and form.is_valid():
        form.save()
        manter = []
        for servico in servicos:
            papel = request.POST.get(f"papel-{servico.pk}", "fora")
            if papel not in {"incluso", "opcional"}:
                continue
            item, _ = ItemPacote.objects.get_or_create(
                pacote=pacote,
                servico=servico,
                defaults={"incluso": papel == "incluso", "ordem": servico.ordem},
            )
            item.incluso = papel == "incluso"
            item.save(update_fields=["incluso"])
            manter.append(item.pk)
        pacote.itens.exclude(pk__in=manter).delete()
        messages.success(request, f"Pacote “{pacote.nome}” atualizado.")
        return redirect("catalogo:pacote_list")
    papeis = []
    for servico in servicos:
        item = ligados.get(servico.pk)
        if item and item.incluso:
            papel = "incluso"
        elif item:
            papel = "opcional"
        else:
            papel = "fora"
        papeis.append({"servico": servico, "papel": papel})
    return render(
        request,
        "catalogo/pacote_form.html",
        {
            "page_title": pacote.nome,
            "form": form,
            "pacote": pacote,
            "papeis": papeis,
        },
    )


@staff_required
@require_POST
def pacote_delete(request: HttpRequest, pk: int) -> HttpResponse:
    pacote = get_object_or_404(Pacote, pk=pk)
    nome = pacote.nome
    pacote.delete()
    messages.success(request, f"Pacote “{nome}” removido. Propostas já feitas continuam com o preço gravado.")
    return redirect("catalogo:pacote_list")


@staff_required
def servico_list(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "catalogo/servicos.html",
        {"page_title": "Serviços", "servicos": Servico.objects.all()},
    )


@staff_required
@require_http_methods(["GET", "POST"])
def servico_create(request: HttpRequest) -> HttpResponse:
    form = ServicoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        servico = form.save()
        messages.success(request, f"Serviço “{servico.nome}” criado.")
        return redirect("catalogo:servico_list")
    return render(request, "catalogo/servico_form.html", {"page_title": "Novo serviço", "form": form})


@staff_required
@require_http_methods(["GET", "POST"])
def servico_edit(request: HttpRequest, pk: int) -> HttpResponse:
    servico = get_object_or_404(Servico, pk=pk)
    form = ServicoForm(request.POST or None, instance=servico)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Serviço “{servico.nome}” atualizado.")
        return redirect("catalogo:servico_list")
    return render(
        request,
        "catalogo/servico_form.html",
        {"page_title": servico.nome, "form": form, "servico": servico},
    )


@staff_required
@require_POST
def servico_delete(request: HttpRequest, pk: int) -> HttpResponse:
    servico = get_object_or_404(Servico, pk=pk)
    nome = servico.nome
    try:
        servico.delete()
    except ProtectedError:
        messages.error(request, f"“{nome}” está num pacote. Tire ele do pacote antes de excluir.")
        return redirect("catalogo:servico_edit", pk=pk)
    messages.success(request, f"Serviço “{nome}” removido.")
    return redirect("catalogo:servico_list")


@staff_required
@require_http_methods(["GET", "POST"])
def desconto_list(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        acao = request.POST.get("acao")
        if acao == "excluir":
            faixa = get_object_or_404(FaixaDesconto, pk=request.POST.get("faixa"))
            if FaixaDesconto.objects.count() == 1:
                messages.error(request, "A tabela precisa de pelo menos uma faixa.")
            else:
                faixa.delete()
                messages.success(request, "Faixa removida.")
            return redirect("catalogo:desconto_list")
        if acao == "nova":
            _criar_faixa(request)
            return redirect("catalogo:desconto_list")
        _salvar_faixas(request)
        return redirect("catalogo:desconto_list")
    return render(
        request,
        "catalogo/descontos.html",
        {"page_title": "Descontos", "faixas": FaixaDesconto.objects.all(), "resumo": texto_faixas()},
    )


def _ler_percentual(texto: str):
    try:
        valor = Decimal((texto or "").replace(",", "."))
    except InvalidOperation:
        return None
    if valor < 0 or valor > 100:
        return None
    return fracao(valor)


def _ler_teto(texto: str):
    texto = (texto or "").strip().replace(",", ".")
    if texto == "":
        return None
    try:
        return Decimal(texto)
    except InvalidOperation:
        return "invalido"


def _salvar_faixas(request: HttpRequest) -> None:
    mudancas = []
    abertas = 0
    for faixa in FaixaDesconto.objects.all():
        teto = _ler_teto(request.POST.get(f"ate-{faixa.pk}", ""))
        percentual = _ler_percentual(request.POST.get(f"pct-{faixa.pk}", ""))
        if teto == "invalido" or percentual is None:
            messages.error(request, "Alguma faixa ficou com número inválido e não foi salva.")
            return
        if teto is None:
            abertas += 1
        mudancas.append((faixa, teto, percentual))
    if abertas > 1:
        messages.error(request, "Só uma faixa pode ficar sem teto.")
        return
    for faixa, teto, percentual in mudancas:
        faixa.valor_ate = teto
        faixa.percentual = percentual
        faixa.save(update_fields=["valor_ate", "percentual"])
    messages.success(request, "Faixas de desconto atualizadas.")


def _criar_faixa(request: HttpRequest) -> None:
    teto = _ler_teto(request.POST.get("ate-nova", ""))
    percentual = _ler_percentual(request.POST.get("pct-nova", ""))
    if teto == "invalido" or percentual is None:
        messages.error(request, "Informe um percentual de 0 a 100.")
        return
    if teto is None and FaixaDesconto.objects.filter(valor_ate__isnull=True).exists():
        messages.error(request, "Já existe a faixa sem teto. Edite ela, ou dê um limite para a nova.")
        return
    FaixaDesconto.objects.create(valor_ate=teto, percentual=percentual, ordem=FaixaDesconto.objects.count() + 1)
    messages.success(request, "Faixa criada.")


# --- Propostas --------------------------------------------------------------


def _pacote_escolhido(request: HttpRequest, proposta: Proposta | None):
    bruto = request.POST.get("pacote") if request.method == "POST" else request.GET.get("pacote")
    if bruto and str(bruto).isdigit():
        pacote = Pacote.objects.filter(pk=int(bruto)).first()
        if pacote:
            return pacote
    if proposta and proposta.pacote_id:
        return proposta.pacote
    return Pacote.objects.filter(ativo=True).order_by("ordem", "nome").first()


def _cliente_inicial(request: HttpRequest, proposta: Proposta | None):
    if proposta and proposta.cliente_id:
        return proposta.cliente_id
    bruto = request.GET.get("cliente")
    if bruto and bruto.isdigit() and Cliente.objects.filter(pk=int(bruto)).exists():
        return int(bruto)
    return None


@staff_required
def proposta_list(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "catalogo/propostas.html",
        {"page_title": "Propostas", "propostas": Proposta.objects.all()},
    )


@staff_required
@require_http_methods(["GET", "POST"])
def proposta_create(request: HttpRequest) -> HttpResponse:
    return _proposta_form(request, None)


@staff_required
@require_http_methods(["GET", "POST"])
def proposta_edit(request: HttpRequest, pk: int) -> HttpResponse:
    proposta = get_object_or_404(Proposta, pk=pk)
    if proposta.fechada:
        return redirect("catalogo:proposta_detail", pk=proposta.pk)
    return _proposta_form(request, proposta)


def _origem(request: HttpRequest):
    return request.POST if request.method == "POST" else request.GET


def _ler_dinheiro(texto, padrao):
    if texto is None or str(texto).strip() == "":
        return dinheiro(padrao)
    bruto = str(texto).strip().replace("R$", "").replace(" ", "")
    if "," in bruto:
        bruto = bruto.replace(".", "").replace(",", ".")
    try:
        return dinheiro(Decimal(bruto))
    except InvalidOperation:
        return dinheiro(padrao)


def _ler_pct(texto, padrao):
    if texto is None or str(texto).strip() == "":
        return padrao
    return fracao(str(texto).strip().replace(",", "."))


def _chip(percentual) -> str:
    texto = f"{pontos(percentual):f}".rstrip("0").rstrip(".")
    return texto if texto in {"0", "5", "10"} else ""


def _servicos_do_pacote(pacote):
    if pacote is None:
        return []
    return [item.servico for item in pacote.itens.select_related("servico").order_by("ordem", "id") if item.incluso]


def _montar_tela(request, proposta, pacote, extras):
    """Preço negociado e desconto de cada item, mais o escopo marcado."""
    origem = _origem(request)
    pacote_mudou = "pacote_base" in origem and origem.get("pacote_base") != str(pacote.pk if pacote else "")
    personalizado = "pacote_base" in origem and not pacote_mudou
    salvos = {}
    if proposta and proposta.pk and pacote and proposta.pacote_id == pacote.pk and not personalizado:
        for item in proposta.itens.all():
            salvos[item.nome] = item

    escopo_todos = _servicos_do_pacote(pacote)
    if personalizado:
        escolhidos = {int(valor) for valor in origem.getlist("escopo") if str(valor).isdigit()}
        escopo = [servico for servico in escopo_todos if servico.pk in escolhidos]
    elif salvos:
        nomes = {item.nome for item in salvos.values() if item.tipo == "escopo"}
        escopo = [servico for servico in escopo_todos if servico.nome in nomes]
    else:
        escopo = list(escopo_todos)

    linhas = []
    if pacote is not None:
        tabela = dinheiro(pacote.preco)
        salvo = salvos.get(pacote.nome)
        if personalizado:
            negociado = _ler_dinheiro(origem.get("preco_pacote"), tabela)
            desconto = _ler_pct(origem.get("pct_pacote"), percentual_sugerido(negociado))
        elif salvo and salvo.preco_negociado:
            negociado = dinheiro(salvo.preco_negociado)
            desconto = salvo.desconto
        else:
            negociado = tabela
            desconto = percentual_sugerido(tabela)
        linhas.append(_linha("pacote", pacote.nome, "pacote", pacote.cobranca, tabela, negociado, desconto, pacote.piso))

    for servico in extras:
        tabela = dinheiro(servico.preco)
        salvo = salvos.get(servico.nome)
        if personalizado and (f"preco_extra_{servico.pk}" in origem or f"pct_extra_{servico.pk}" in origem):
            negociado = _ler_dinheiro(origem.get(f"preco_extra_{servico.pk}"), tabela)
            desconto = _ler_pct(origem.get(f"pct_extra_{servico.pk}"), percentual_sugerido(negociado))
        elif salvo and salvo.tipo == "avulso" and salvo.preco_negociado:
            negociado = dinheiro(salvo.preco_negociado)
            desconto = salvo.desconto
        else:
            negociado = tabela
            desconto = percentual_sugerido(tabela)
        linhas.append(
            _linha(f"extra-{servico.pk}", servico.nome, "avulso", servico.cobranca, tabela, negociado, desconto, False, servico.pk)
        )
    return escopo, linhas


def _linha(chave, nome, tipo, cobranca, tabela, negociado, desconto, piso, servico_id=None):
    return {
        "chave": chave,
        "nome": nome,
        "tipo": tipo,
        "cobranca": cobranca,
        "cobranca_label": dict(Cobranca.choices).get(cobranca, cobranca),
        "tabela": dinheiro(tabela),
        "negociado": dinheiro(negociado),
        "desconto": desconto,
        "total": com_desconto(negociado, desconto),
        "pct": pontos(desconto),
        "pct_texto": f"{pontos(desconto):f}".rstrip("0").rstrip(".") or "0",
        "chip": _chip(desconto),
        "piso": piso,
        "servico_id": servico_id,
    }


def _proposta_form(request: HttpRequest, proposta: Proposta | None) -> HttpResponse:
    pacote = _pacote_escolhido(request, proposta)
    disponiveis = _extras_da_proposta(pacote, [])
    if request.method == "POST" or "pacote" in request.GET or "extras" in request.GET:
        marcados = set(_ids_extras(request))
    elif proposta and proposta.pk:
        nomes = set(proposta.itens.filter(tipo="avulso").values_list("nome", flat=True))
        marcados = {servico.pk for servico in disponiveis if servico.nome in nomes}
    else:
        marcados = set()
    extras = [servico for servico in disponiveis if servico.pk in marcados]
    escopo, linhas = _montar_tela(request, proposta, pacote, extras) if pacote is not None else ([], [])
    fixo = request.method == "GET" and bool(request.GET.get("desconto_fixo"))
    informados = {
        Cobranca.UNICO: fracao(request.GET.get("desconto_unico")),
        Cobranca.MENSAL: fracao(request.GET.get("desconto_mensal")),
        Cobranca.ANUAL: fracao(request.GET.get("desconto_anual")),
    }
    conta = cotar(pacote, extras, fixo=fixo, informados=informados) if pacote is not None else None

    iniciais = _iniciais(proposta, pacote, extras)
    if request.method == "GET":
        bruto = request.GET.get("cliente")
        if bruto and bruto.isdigit():
            iniciais["cliente"] = int(bruto)
        if "observacao" in request.GET:
            iniciais["observacao"] = request.GET.get("observacao", "")
    if request.method == "GET" and request.GET.get("pacote") and pacote is not None and conta is not None:
        iniciais["pacote"] = pacote.pk
        iniciais["desconto_fixo"] = fixo
        iniciais["desconto_unico"] = pontos(conta["descontos"][Cobranca.UNICO])
        iniciais["desconto_mensal"] = pontos(conta["descontos"][Cobranca.MENSAL])
        iniciais["desconto_anual"] = pontos(conta["descontos"][Cobranca.ANUAL])
    cliente_id = _cliente_inicial(request, proposta)
    if cliente_id and "cliente" not in iniciais:
        iniciais["cliente"] = cliente_id
    form = PropostaForm(request.POST or None, initial=None if request.method == "POST" else iniciais, proposta=proposta)

    if request.method == "POST" and form.is_valid():
        if proposta is None:
            proposta = Proposta(status=Proposta.Status.RASCUNHO)
        if "preco_pacote" in request.POST:
            gravar_linhas(
                proposta,
                form.cleaned_data["pacote"],
                escopo,
                linhas,
                form.cleaned_data["cliente"],
                form.cleaned_data["observacao"],
                request.user,
            )
        else:
            gravar(
                proposta,
                form.cleaned_data["pacote"],
                extras,
                form.cleaned_data["desconto_fixo"],
                _informados(form),
                form.cleaned_data["cliente"],
                form.cleaned_data["observacao"],
                request.user,
            )
        messages.success(request, "Proposta salva. Feche quando o preço puder ficar congelado.")
        return redirect("catalogo:proposta_detail", pk=proposta.pk)

    return render(
        request,
        "catalogo/proposta_form.html",
        {
            "page_title": "Nova proposta" if proposta is None or not proposta.pk else f"Proposta {proposta.pk}",
            "form": form,
            "proposta": proposta,
            "pacote": pacote,
            "disponiveis": disponiveis,
            "marcados": marcados,
            "conta": conta,
            "escopo": escopo,
            "linhas": linhas,
            "faixas": texto_faixas(),
            "candidatos": _candidatos_extras(),
            "disponiveis_ids": {servico.pk for servico in disponiveis},
            "catalogo": _catalogo_interativo(form.fields["pacote"].queryset),
        },
    )


def _candidatos_extras():
    opcionais = ItemPacote.objects.filter(incluso=False).values("servico_id")
    return Servico.objects.filter(ativo=True).filter(Q(complemento=True) | Q(pk__in=opcionais)).order_by("ordem", "nome")


def _catalogo_interativo(pacotes_qs):
    pacotes = []
    for pacote in pacotes_qs.prefetch_related("itens__servico"):
        escopo = []
        opcionais = []
        for item in pacote.itens.all():
            if item.incluso:
                escopo.append({"id": item.servico_id, "nome": item.servico.nome})
            else:
                opcionais.append(item.servico_id)
        pacotes.append(
            {
                "id": pacote.pk,
                "nome": pacote.nome,
                "preco": str(dinheiro(pacote.preco)),
                "cobranca_label": pacote.get_cobranca_display(),
                "piso": pacote.piso,
                "escopo": escopo,
                "opcionais": opcionais,
            }
        )
    servicos = [
        {
            "id": servico.pk,
            "nome": servico.nome,
            "preco": str(dinheiro(servico.preco)),
            "cobranca_label": servico.get_cobranca_display(),
            "complemento": servico.complemento,
        }
        for servico in _candidatos_extras()
    ]
    return {
        "pacotes": pacotes,
        "servicos": servicos,
        "faixas": [
            {"ate": None if faixa.valor_ate is None else str(dinheiro(faixa.valor_ate)), "pct": str(faixa.percentual)}
            for faixa in faixas()
        ],
    }


@staff_required
def proposta_documento(request: HttpRequest, pk: int) -> HttpResponse:
    proposta = get_object_or_404(Proposta.objects.prefetch_related("itens"), pk=pk)
    return HttpResponse(render_html(proposta))


@staff_required
def proposta_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    proposta = get_object_or_404(Proposta.objects.prefetch_related("itens"), pk=pk)
    try:
        dados = gerar_pdf(proposta)
    except PdfIndisponivel as exc:
        messages.error(request, str(exc))
        return redirect("catalogo:proposta_detail", pk=proposta.pk)
    resposta = HttpResponse(dados, content_type="application/pdf")
    resposta["Content-Disposition"] = f'attachment; filename="{nome_arquivo(proposta)}"'
    return resposta


@staff_required
def proposta_detail(request: HttpRequest, pk: int) -> HttpResponse:
    proposta = get_object_or_404(Proposta.objects.prefetch_related("itens"), pk=pk)
    return render(
        request,
        "catalogo/proposta_detail.html",
        {"page_title": f"Proposta {proposta.pk}", "proposta": proposta},
    )


@staff_required
@require_POST
def proposta_fechar(request: HttpRequest, pk: int) -> HttpResponse:
    proposta = get_object_or_404(Proposta, pk=pk)
    proposta.status = Proposta.Status.FECHADA
    proposta.save(update_fields=["status", "updated_at"])
    messages.success(request, "Proposta fechada. Mudar a tabela não altera este preço.")
    return redirect("catalogo:proposta_detail", pk=proposta.pk)


@staff_required
@require_POST
def proposta_excluir(request: HttpRequest, pk: int) -> HttpResponse:
    proposta = get_object_or_404(Proposta, pk=pk)
    proposta.delete()
    messages.success(request, "Proposta excluída.")
    return redirect("catalogo:proposta_list")
