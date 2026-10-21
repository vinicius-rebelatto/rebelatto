from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from erp.mixins import ListingMixin
from erp.views import staff_required

from . import pricing
from .crypto import CryptoError, usando_chave_derivada
from .forms import CredencialCreateForm, CredencialEditForm, ModeloForm
from .models import Credencial, Modelo, Provedor
from .providers import INFO_PROVEDORES, PROVEDORES_COM_ADMIN
from .services import sincronizar_modelos, testar_credencial


def _base_context(**extra) -> dict:
    return {"chave_derivada": usando_chave_derivada(), **extra}


def _redirect_next(request: HttpRequest, fallback: str, **kwargs) -> HttpResponse:
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect(fallback, **kwargs)


# --- Credenciais ------------------------------------------------------------


@staff_required
def index(request: HttpRequest) -> HttpResponse:
    return redirect("ia:credencial_list")


@staff_required
def credencial_list(request: HttpRequest) -> HttpResponse:
    credenciais = Credencial.objects.annotate(
        total_modelos=Count("modelos", distinct=True),
        modelos_habilitados=Count("modelos", filter=Q(modelos__habilitado=True), distinct=True),
    )
    por_provedor = {value: [] for value, _ in Provedor.choices}
    for credencial in credenciais:
        por_provedor[credencial.provedor].append(credencial)

    provedores = [
        {
            "value": value,
            "label": label,
            "info": INFO_PROVEDORES[value],
            "suporta_admin": value in PROVEDORES_COM_ADMIN,
            "credenciais": por_provedor[value],
        }
        for value, label in Provedor.choices
    ]
    context = _base_context(
        page_title="Chaves de IA",
        provedores=provedores,
        total_chaves=len(credenciais),
        total_validas=sum(1 for c in credenciais if c.status == Credencial.Status.VALIDA and c.ativa),
        total_modelos=Modelo.objects.count(),
        total_habilitados=Modelo.objects.filter(habilitado=True).count(),
    )
    return render(request, "ia/credenciais/list.html", context)


@staff_required
@require_http_methods(["GET", "POST"])
def credencial_create(request: HttpRequest) -> HttpResponse:
    initial = {}
    if request.GET.get("provedor") in Provedor.values:
        initial["provedor"] = request.GET["provedor"]
    form = CredencialCreateForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        credencial = form.save(commit=False)
        credencial.ultimo_teste_em = timezone.now()
        credencial.save()
        novos = sincronizar_modelos(credencial, form.remotos)
        messages.success(
            request,
            f"Chave validada e salva: {len(form.remotos)} modelos disponíveis ({novos} novos). "
            "Habilite os que quiser usar.",
        )
        return redirect("ia:credencial_detail", pk=credencial.pk)
    context = _base_context(
        page_title="Nova chave de IA",
        form=form,
        info_provedores=[(label, INFO_PROVEDORES[value]) for value, label in Provedor.choices],
    )
    return render(request, "ia/credenciais/form.html", context)


@staff_required
@require_http_methods(["GET", "POST"])
def credencial_detail(request: HttpRequest, pk: int) -> HttpResponse:
    credencial = get_object_or_404(Credencial, pk=pk)
    form = CredencialEditForm(request.POST or None, instance=credencial)
    if request.method == "POST" and form.is_valid():
        nova_chave = bool(form.cleaned_data.get("nova_chave"))
        credencial = form.save(commit=False)
        if nova_chave:
            credencial.ultimo_teste_em = timezone.now()
        credencial.save()
        if nova_chave:
            sincronizar_modelos(credencial, form.remotos)
        messages.success(request, "Chave atualizada.")
        return redirect("ia:credencial_detail", pk=credencial.pk)

    erro_cripto = ""
    try:
        credencial.chave  # noqa: B018 - surfaces undecryptable keys in the UI
    except CryptoError as exc:
        erro_cripto = str(exc)

    context = _base_context(
        page_title=credencial.apelido,
        credencial=credencial,
        form=form,
        modelos=credencial.modelos.order_by("-habilitado", "model_id"),
        info=INFO_PROVEDORES[credencial.provedor],
        suporta_admin=credencial.provedor in PROVEDORES_COM_ADMIN,
        erro_cripto=erro_cripto,
    )
    return render(request, "ia/credenciais/detail.html", context)


@staff_required
@require_POST
def credencial_test(request: HttpRequest, pk: int) -> HttpResponse:
    credencial = get_object_or_404(Credencial, pk=pk)
    try:
        ok, mensagem = testar_credencial(credencial)
    except CryptoError as exc:
        ok, mensagem = False, str(exc)
    (messages.success if ok else messages.error)(request, mensagem)
    return _redirect_next(request, "ia:credencial_detail", pk=pk)


@staff_required
@require_POST
def credencial_delete(request: HttpRequest, pk: int) -> HttpResponse:
    credencial = get_object_or_404(Credencial, pk=pk)
    nome = str(credencial)
    credencial.delete()
    messages.success(request, f"Chave “{nome}” removida.")
    return redirect("ia:credencial_list")


# --- Modelos ----------------------------------------------------------------


class ModeloListing(ListingMixin):
    paginate_by = 50
    search_fields = ["model_id", "nome"]
    filter_fields = ["provedor", "habilitado", "faixa"]
    boolean_filters = {"habilitado"}
    sort_fields = {
        "model_id": "model_id",
        "provedor": "provedor",
        "preco_entrada": "preco_entrada",
        "preco_saida": "preco_saida",
        "contexto_max": "contexto_max",
    }
    default_sort = "provedor"


@staff_required
def modelo_list(request: HttpRequest) -> HttpResponse:
    queryset = Modelo.objects.annotate(total_chaves=Count("credenciais"))
    context = _base_context(
        page_title="Modelos de IA",
        provedor_choices=Provedor.choices,
        faixa_choices=Modelo.Faixa.choices,
        **ModeloListing().get_listing_queryset(request, queryset),
    )
    return render(request, "ia/modelos/list.html", context)


@staff_required
@require_http_methods(["GET", "POST"])
def modelo_edit(request: HttpRequest, pk: int) -> HttpResponse:
    modelo = get_object_or_404(Modelo, pk=pk)
    form = ModeloForm(request.POST or None, instance=modelo)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Modelo atualizado.")
        return redirect("ia:modelo_list")
    context = _base_context(
        page_title=str(modelo),
        modelo=modelo,
        form=form,
        credenciais=modelo.credenciais.all(),
    )
    return render(request, "ia/modelos/form.html", context)


@staff_required
@require_POST
def modelo_toggle(request: HttpRequest, pk: int) -> HttpResponse:
    modelo = get_object_or_404(Modelo, pk=pk)
    modelo.habilitado = not modelo.habilitado
    modelo.save(update_fields=["habilitado", "updated_at"])
    return _redirect_next(request, "ia:modelo_list")


@staff_required
@require_POST
def modelo_reset_preco(request: HttpRequest, pk: int) -> HttpResponse:
    modelo = get_object_or_404(Modelo, pk=pk)
    modelo.fonte_preco = ""
    try:
        atualizados, _ = pricing.atualizar_precos([modelo], pricing.carregar_tabela(force=True))
    except pricing.PricingError as exc:
        messages.error(request, str(exc))
        return redirect("ia:modelo_edit", pk=pk)
    if atualizados:
        messages.success(request, "Preço restaurado a partir do LiteLLM.")
    else:
        modelo.save(update_fields=["fonte_preco", "updated_at"])
        messages.warning(request, "O LiteLLM não tem preço para este modelo; cadastre manualmente.")
    return redirect("ia:modelo_edit", pk=pk)


@staff_required
@require_POST
def modelos_atualizar_precos(request: HttpRequest) -> HttpResponse:
    try:
        tabela = pricing.carregar_tabela(force=True)
    except pricing.PricingError as exc:
        messages.error(request, str(exc))
        return redirect("ia:modelo_list")
    atualizados, sem_preco = pricing.atualizar_precos(Modelo.objects.all(), tabela)
    manuais = Modelo.objects.filter(fonte_preco=Modelo.FontePreco.MANUAL).count()
    partes = [f"{atualizados} modelos atualizados"]
    if sem_preco:
        partes.append(f"{sem_preco} sem preço no LiteLLM")
    if manuais:
        partes.append(f"{manuais} com preço manual mantido")
    messages.success(request, "Preços atualizados: " + ", ".join(partes) + ".")
    return redirect("ia:modelo_list")
