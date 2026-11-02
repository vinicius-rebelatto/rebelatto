import csv
import io
import json
from collections import Counter
from functools import wraps

from django.contrib import messages
from django.db import transaction
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from crm.importacao import (
    dados_novos,
    duplicatas_no_lote as _duplicatas_no_arquivo,
    e_duplicata as _e_duplicata,
    linha_apify,
    qualificar_linhas,
    recalcular_importados,
    unique_cliente_slug as _unique_cliente_slug,
)
from crm import apify, buscas
from crm.models import BuscaLeads, Cliente, Mockup, PerfilNicho
from crm.qualificacao import FORA, LEVA
from portfolio.mockup_landings import biblioteca_do_nicho
from portfolio.models import Project

from .forms import (
    BuscaLeadsForm,
    ClienteForm,
    CsvImportForm,
    MockupForm,
    PerfilNichoForm,
    MockupImagemFormSet,
    ProjectForm,
    RejectForm,
    TarefaForm,
    TarefaRapidaForm,
)
from .mixins import ListingMixin
from .models import Tarefa


def staff_required(view_func):
    @wraps(view_func)
    @login_required(login_url="erp:login")
    def _wrapped(request: HttpRequest, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, "Acesso restrito à equipe.")
            return redirect("erp:login")
        return view_func(request, *args, **kwargs)

    return _wrapped


def _listing_context(mixin: ListingMixin, request: HttpRequest, queryset):
    return mixin.get_listing_queryset(request, queryset)


# --- Auth -----------------------------------------------------------------


@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("erp:dashboard")

    error = ""
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_staff:
            login(request, user)
            next_url = request.GET.get("next") or reverse("erp:dashboard")
            return redirect(next_url)
        error = "Credenciais inválidas ou usuário sem permissão."

    return render(request, "erp/login.html", {"error": error})


@require_POST
@login_required(login_url="erp:login")
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("erp:login")


# --- Dashboard ------------------------------------------------------------


@staff_required
def dashboard(request: HttpRequest) -> HttpResponse:
    status_counts = {
        row["status"]: row["total"]
        for row in Cliente.objects.values("status").annotate(total=Count("id"))
    }
    context = {
        "page_title": "Dashboard",
        "cliente_total": Cliente.objects.count(),
        "status_counts": status_counts,
        "mockups_publicados": Mockup.objects.filter(status=Mockup.Status.PUBLICADO).count(),
        "mockups_total": Mockup.objects.count(),
        "projetos_publicados": Project.landing_queryset().count(),
        "projetos_total": Project.objects.count(),
        "importados": status_counts.get(Cliente.Status.IMPORTADO, 0),
        "a_prospectar": status_counts.get(Cliente.Status.A_PROSPECTAR, 0),
        "em_prospeccao": status_counts.get(Cliente.Status.EM_PROSPECCAO, 0),
        "convertidos": status_counts.get(Cliente.Status.CONVERTIDO, 0),
        "rejeitados": status_counts.get(Cliente.Status.REJEITADO, 0),
        "tarefas_proximas": list(Tarefa.objects.exclude(status=Tarefa.Status.FEITA)[:6]),
        "tarefas_abertas": Tarefa.objects.exclude(status=Tarefa.Status.FEITA).count(),
    }
    return render(request, "erp/dashboard.html", context)


# --- Clientes -------------------------------------------------------------


class ClienteListing(ListingMixin):
    search_fields = ["nome", "empresa", "email", "telefone", "cidade", "mensagem"]
    filter_fields = ["status", "origem", "etapa_rejeicao", "cidade", "estado"]
    sort_fields = {
        "empresa": "empresa",
        "nome": "nome",
        "status": "status",
        "origem": "origem",
        "cidade": "cidade",
        "updated_at": "updated_at",
        "created_at": "created_at",
    }
    default_sort = "-updated_at"


@staff_required
def cliente_list(request: HttpRequest) -> HttpResponse:
    status = (request.GET.get("status") or "").strip()
    etapa = (request.GET.get("etapa_rejeicao") or "").strip()
    origem = (request.GET.get("origem") or "").strip()
    clientes = Cliente.objects.all()
    if status != Cliente.Status.REJEITADO and not etapa:
        clientes = clientes.exclude(status=Cliente.Status.REJEITADO)
    if origem != Cliente.Origem.CONTATO:
        clientes = clientes.exclude(origem=Cliente.Origem.CONTATO)
    mixin = ClienteListing()
    listing = _listing_context(mixin, request, clientes)
    listing.update(
        {
            "page_title": "Clientes",
            "status_choices": Cliente.Status.choices,
            "origem_choices": Cliente.Origem.choices,
            "etapa_choices": Cliente.EtapaRejeicao.choices,
            "cidades": clientes.exclude(cidade="")
            .order_by("cidade")
            .values_list("cidade", flat=True)
            .distinct(),
            "estados": clientes.exclude(estado="")
            .order_by("estado")
            .values_list("estado", flat=True)
            .distinct(),
        }
    )
    return render(request, "erp/clientes/list.html", listing)


@staff_required
@require_http_methods(["GET", "POST"])
def cliente_create(request: HttpRequest) -> HttpResponse:
    form = ClienteForm(request.POST or None, request.FILES or None, initial={"origem": Cliente.Origem.MANUAL})
    if request.method == "POST" and form.is_valid():
        cliente = form.save(commit=False)
        if cliente.status == Cliente.Status.REJEITADO:
            cliente.etapa_rejeicao = Cliente.EtapaRejeicao.PROSPECCAO
        cliente.ensure_slug()
        cliente.save()
        messages.success(request, "Cliente criado.")
        return redirect("erp:cliente_detail", pk=cliente.pk)
    return render(
        request,
        "erp/clientes/form.html",
        {"page_title": "Novo cliente", "form": form, "cliente": None},
    )


@staff_required
def cliente_detail(request: HttpRequest, pk: int) -> HttpResponse:
    cliente = get_object_or_404(Cliente, pk=pk)
    unidades = 1
    if cliente.empresa:
        unidades = Cliente.objects.filter(empresa__iexact=cliente.empresa).count()
    return render(
        request,
        "erp/clientes/detail.html",
        {
            "page_title": cliente.display_name,
            "cliente": cliente,
            "reject_form": RejectForm(),
            "mockups": cliente.mockups.all(),
            "templates_lead": biblioteca_do_nicho("estetica"),
            "projetos": cliente.projetos.all(),
            "unidades": unidades,
            "dados_maps_json": json.dumps(cliente.dados_maps, ensure_ascii=False, indent=2)
            if cliente.dados_maps
            else "",
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def cliente_edit(request: HttpRequest, pk: int) -> HttpResponse:
    cliente = get_object_or_404(Cliente, pk=pk)
    previous_status = cliente.status
    form = ClienteForm(request.POST or None, request.FILES or None, instance=cliente)
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        if (
            updated.status == Cliente.Status.REJEITADO
            and previous_status != Cliente.Status.REJEITADO
        ):
            updated.etapa_rejeicao = Cliente.infer_etapa_rejeicao(previous_status)
        elif updated.status != Cliente.Status.REJEITADO:
            updated.etapa_rejeicao = None
            if previous_status == Cliente.Status.REJEITADO and not form.cleaned_data.get(
                "motivo_rejeicao"
            ):
                updated.motivo_rejeicao = ""
        updated.save()
        messages.success(request, "Cliente atualizado.")
        return redirect("erp:cliente_detail", pk=cliente.pk)
    return render(
        request,
        "erp/clientes/form.html",
        {"page_title": f"Editar — {cliente.display_name}", "form": form, "cliente": cliente},
    )


@staff_required
@require_POST
def cliente_reject(request: HttpRequest, pk: int) -> HttpResponse:
    cliente = get_object_or_404(Cliente, pk=pk)
    form = RejectForm(request.POST)
    if form.is_valid():
        etapa = request.POST.get("etapa") or Cliente.infer_etapa_rejeicao(cliente.status)
        cliente.reject(etapa=etapa, motivo=form.cleaned_data.get("motivo_rejeicao") or "")
        messages.success(request, "Cliente marcado como rejeitado.")
    return redirect(request.POST.get("next") or reverse("erp:cliente_detail", args=[pk]))


@staff_required
@require_POST
def cliente_accept_filter(request: HttpRequest, pk: int) -> HttpResponse:
    cliente = get_object_or_404(Cliente, pk=pk, status=Cliente.Status.IMPORTADO)
    cliente.clear_rejection(new_status=Cliente.Status.A_PROSPECTAR)
    messages.success(request, f"{cliente.display_name} movido para a prospectar.")
    return redirect(request.POST.get("next") or reverse("erp:cliente_filtragem"))


@staff_required
@require_POST
def cliente_delete(request: HttpRequest, pk: int) -> HttpResponse:
    cliente = get_object_or_404(Cliente, pk=pk)
    nome = cliente.display_name
    cliente.delete()
    messages.success(request, f"Cliente “{nome}” removido.")
    return redirect("erp:cliente_list")


# --- Filtragem / CSV ------------------------------------------------------


class FiltragemListing(ListingMixin):
    search_fields = ["empresa", "telefone", "cidade", "categoria", "website", "motivo_nota"]
    filter_fields = []
    sort_fields = {
        "empresa": "empresa",
        "nota": "nota",
        "categoria": "categoria_lead",
    }
    default_sort = "-nota"
    default_order = ("ordem_fila", "-nota", "empresa")
    paginate_by = 50


FILAS_QUALIFICACAO = (
    ("leva", "Primeira leva", LEVA),
    ("sem_site", "Sem site", ("sem_site",)),
    ("rede_social", "Rede social", ("rede_social",)),
    ("site_fraco", "Site fraco", ("site_fraco",)),
    ("site_proprio", "Site próprio", ("site_proprio",)),
    ("fora", "Fora", FORA),
)


@staff_required
def cliente_filtragem(request: HttpRequest) -> HttpResponse:
    fila = request.GET.get("fila") or "leva"
    if fila not in {item[0] for item in FILAS_QUALIFICACAO}:
        fila = "leva"
    base = Cliente.objects.filter(status=Cliente.Status.IMPORTADO)
    contagem = {
        row["categoria_lead"]: row["total"]
        for row in base.values("categoria_lead").annotate(total=Count("id"))
    }
    abas = []
    for chave, rotulo, categorias in FILAS_QUALIFICACAO:
        query = request.GET.copy()
        query["fila"] = chave
        query.pop("page", None)
        query.pop("sort", None)
        abas.append(
            {
                "chave": chave,
                "rotulo": rotulo,
                "total": sum(contagem.get(item, 0) for item in categorias),
                "url": "?" + query.urlencode(),
            }
        )
    categorias = next(item[2] for item in FILAS_QUALIFICACAO if item[0] == fila)
    mixin = FiltragemListing()
    listing = _listing_context(mixin, request, base.filter(categoria_lead__in=categorias))
    repetidos = Counter(
        nome.casefold()
        for nome in base.exclude(empresa="").values_list("empresa", flat=True)
    )
    for cliente in listing["object_list"]:
        cliente.unidades = repetidos.get(cliente.empresa.casefold(), 1) if cliente.empresa else 1
    listing.update(
        {
            "page_title": "Qualificação de leads",
            "fila": fila,
            "abas": abas,
            "sem_classificar": contagem.get("", 0),
        }
    )
    return render(request, "erp/clientes/filtragem.html", listing)


@staff_required
@require_POST
def cliente_filtragem_bulk(request: HttpRequest) -> HttpResponse:
    ids = request.POST.getlist("ids")
    action = request.POST.get("action")
    motivo = (request.POST.get("motivo_rejeicao") or "").strip()
    clientes = Cliente.objects.filter(pk__in=ids, status=Cliente.Status.IMPORTADO)
    count = 0
    for cliente in clientes:
        if action == "accept":
            cliente.clear_rejection(new_status=Cliente.Status.A_PROSPECTAR)
            count += 1
        elif action == "reject":
            cliente.reject(etapa=Cliente.EtapaRejeicao.FILTRAGEM, motivo=motivo)
            count += 1
    if action == "accept":
        messages.success(request, f"{count} cliente(s) aceito(s).")
    elif action == "reject":
        messages.success(request, f"{count} cliente(s) rejeitado(s).")
    return redirect("erp:cliente_filtragem")


@staff_required
@require_http_methods(["GET", "POST"])
def cliente_nicho(request: HttpRequest) -> HttpResponse:
    perfil = PerfilNicho.atual()
    form = PerfilNichoForm(request.POST or None, instance=perfil)
    if request.method == "POST" and form.is_valid():
        perfil = form.save()
        total, visitados = recalcular_importados(perfil)
        texto = "Perfil salvo."
        if total:
            texto = f"Perfil salvo. {total} lead(s) da filtragem recalculado(s)."
            if visitados:
                texto += f" {visitados} site(s) verificado(s)."
        messages.success(request, texto)
        return redirect("erp:cliente_nicho")
    return render(
        request,
        "erp/clientes/nicho.html",
        {"page_title": "Nicho", "form": form, "perfil": perfil},
    )


def _decode_csv(uploaded) -> str:
    raw = uploaded.read()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def _detect_csv_delimiter(text: str) -> str:
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,|\t")
        if dialect.delimiter in {";", ",", "|", "\t"}:
            return dialect.delimiter
    except csv.Error:
        pass
    first_line = sample.splitlines()[0] if sample else ""
    if first_line.count(";") >= first_line.count(","):
        return ";"
    return ","


@staff_required
@require_http_methods(["GET", "POST"])
def cliente_import_csv(request: HttpRequest) -> HttpResponse:
    form = CsvImportForm()
    preview_rows = request.session.get("csv_preview") or []

    if request.method == "POST":
        if request.POST.get("confirm") == "1":
            preview_rows = request.session.get("csv_preview") or []
            if preview_rows and "categoria_lead" not in preview_rows[0]:
                preview_rows, _ = qualificar_linhas(preview_rows, PerfilNicho.atual())
            created = 0
            skipped = 0
            na_leva = 0
            with transaction.atomic():
                for item in preview_rows:
                    if item.get("duplicate"):
                        skipped += 1
                        continue
                    if _e_duplicata(
                        item.get("empresa", ""),
                        item.get("telefone", ""),
                        item.get("cidade", ""),
                    ):
                        skipped += 1
                        continue
                    Cliente.objects.create(
                        slug=_unique_cliente_slug(item.get("empresa") or "cliente"),
                        origem=Cliente.Origem.CSV,
                        status=Cliente.Status.IMPORTADO,
                        **dados_novos(item),
                    )
                    created += 1
                    if item.get("categoria_lead") in LEVA:
                        na_leva += 1
            request.session.pop("csv_preview", None)
            messages.success(
                request,
                "Importação concluída: "
                f"{created} novo(s), {na_leva} na primeira leva, "
                f"{skipped} duplicata(s) ignorada(s).",
            )
            return redirect("erp:cliente_filtragem")

        form = CsvImportForm(request.POST, request.FILES)
        if form.is_valid():
            text = _decode_csv(form.cleaned_data["arquivo"])
            delimiter = _detect_csv_delimiter(text)
            reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
            if not reader.fieldnames:
                messages.error(request, "CSV inválido ou sem cabeçalho.")
                return redirect("erp:cliente_import")

            fieldnames = [((name or "").lstrip("\ufeff").strip()) for name in reader.fieldnames]
            preview_rows = []
            duplicates = 0
            for raw_row in reader:
                row = {
                    (key or "").lstrip("\ufeff").strip(): (value or "")
                    for key, value in raw_row.items()
                }
                linha = linha_apify(row)
                if linha is None:
                    continue
                linha["duplicate"] = _e_duplicata(
                    linha["empresa"], linha["telefone"], linha["cidade"]
                )
                if linha["duplicate"]:
                    duplicates += 1
                preview_rows.append(linha)
            duplicates += _duplicatas_no_arquivo(preview_rows)

            if not preview_rows:
                messages.error(
                    request,
                    "Nenhuma linha válida encontrada. Use CSV com a coluna title "
                    f"(delimitador detectado: “{delimiter}”).",
                )
                return redirect("erp:cliente_import")

            preview_rows, sitios = qualificar_linhas(preview_rows, PerfilNicho.atual())
            request.session["csv_preview"] = preview_rows
            return render(
                request,
                "erp/clientes/import.html",
                {
                    "page_title": "Importar CSV",
                    "form": CsvImportForm(),
                    "preview_rows": preview_rows,
                    "duplicates": duplicates,
                    "sitios": sitios,
                    "show_preview": True,
                    "delimiter": delimiter,
                    "fieldnames": fieldnames,
                },
            )

    return render(
        request,
        "erp/clientes/import.html",
        {
            "page_title": "Importar CSV",
            "form": form,
            "preview_rows": preview_rows,
            "show_preview": bool(preview_rows),
            "duplicates": sum(1 for r in preview_rows if r.get("duplicate")),
            "sitios": 0,
        },
    )


# --- Mockups --------------------------------------------------------------


class MockupListing(ListingMixin):
    search_fields = ["titulo", "slug", "cliente__empresa", "cliente__nome", "descricao"]
    filter_fields = ["status", "cliente", "categoria", "tipo"]
    sort_fields = {
        "titulo": "titulo",
        "status": "status",
        "categoria": "categoria",
        "tipo": "tipo",
        "updated_at": "updated_at",
        "cliente": "cliente__empresa",
    }
    default_sort = "-updated_at"


@staff_required
def mockup_list(request: HttpRequest) -> HttpResponse:
    mixin = MockupListing()
    listing = _listing_context(mixin, request, Mockup.objects.select_related("cliente"))
    listing.update(
        {
            "page_title": "Mockups",
            "status_choices": Mockup.Status.choices,
            "categoria_choices": Mockup.Categoria.choices,
            "tipo_choices": Mockup.Tipo.choices,
            "clientes": Cliente.objects.order_by("empresa", "nome"),
        }
    )
    return render(request, "erp/mockups/list.html", listing)


@staff_required
@require_http_methods(["GET", "POST"])
def mockup_create(request: HttpRequest) -> HttpResponse:
    initial = {}
    cliente_id = request.GET.get("cliente")
    if cliente_id:
        initial["cliente"] = cliente_id
    form = MockupForm(request.POST or None, request.FILES or None, initial=initial)
    formset = MockupImagemFormSet(
        request.POST or None, request.FILES or None, instance=Mockup()
    )
    if request.method == "POST" and form.is_valid():
        mockup = form.save(commit=False)
        mockup.ensure_slug()
        mockup.save()
        formset = MockupImagemFormSet(request.POST, request.FILES, instance=mockup)
        if formset.is_valid():
            formset.save()
            messages.success(request, "Mockup criado.")
            return redirect("erp:mockup_edit", pk=mockup.pk)
        messages.error(request, "Mockup salvo, mas há erros na galeria.")
        return redirect("erp:mockup_edit", pk=mockup.pk)
    return render(
        request,
        "erp/mockups/form.html",
        {"page_title": "Novo mockup", "form": form, "formset": formset, "mockup": None},
    )


@staff_required
@require_http_methods(["GET", "POST"])
def mockup_edit(request: HttpRequest, pk: int) -> HttpResponse:
    mockup = get_object_or_404(Mockup.objects.select_related("cliente"), pk=pk)
    form = MockupForm(request.POST or None, request.FILES or None, instance=mockup)
    formset = MockupImagemFormSet(
        request.POST or None, request.FILES or None, instance=mockup
    )
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        form.save()
        formset.save()
        messages.success(request, "Mockup atualizado.")
        return redirect("erp:mockup_edit", pk=mockup.pk)
    return render(
        request,
        "erp/mockups/form.html",
        {
            "page_title": f"Editar — {mockup.titulo}",
            "form": form,
            "formset": formset,
            "mockup": mockup,
        },
    )


@staff_required
@require_POST
def mockup_delete(request: HttpRequest, pk: int) -> HttpResponse:
    mockup = get_object_or_404(Mockup, pk=pk)
    titulo = mockup.titulo
    mockup.delete()
    messages.success(request, f"Mockup “{titulo}” removido.")
    return redirect("erp:mockup_list")


@staff_required
@require_POST
def mockup_publish_toggle(request: HttpRequest, pk: int) -> HttpResponse:
    mockup = get_object_or_404(Mockup, pk=pk)
    if mockup.status == Mockup.Status.PUBLICADO:
        mockup.status = Mockup.Status.RASCUNHO
        mockup.save(update_fields=["status", "updated_at"])
        messages.info(request, "Mockup despublicado.")
    else:
        mockup.status = Mockup.Status.PUBLICADO
        mockup.save()
        messages.success(request, "Mockup publicado.")
    return redirect(request.POST.get("next") or reverse("erp:mockup_edit", args=[pk]))


# --- Projetos -------------------------------------------------------------


class ProjectListing(ListingMixin):
    search_fields = ["titulo", "resumo", "stack", "cliente__empresa", "cliente__nome"]
    filter_fields = ["status", "publicado", "cliente"]
    boolean_filters = {"publicado"}
    sort_fields = {
        "titulo": "titulo",
        "status": "status",
        "ordem": "ordem",
        "publicado": "publicado",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }
    default_sort = "ordem"


@staff_required
def project_list(request: HttpRequest) -> HttpResponse:
    mixin = ProjectListing()
    qs = Project.objects.select_related("cliente")
    listing = _listing_context(mixin, request, qs)
    listing.update(
        {
            "page_title": "Projetos",
            "status_choices": Project.Status.choices,
            "clientes": Cliente.objects.order_by("empresa", "nome"),
        }
    )
    return render(request, "erp/projetos/list.html", listing)


@staff_required
@require_http_methods(["GET", "POST"])
def project_create(request: HttpRequest) -> HttpResponse:
    initial = {}
    cliente_id = request.GET.get("cliente")
    if cliente_id:
        cliente = Cliente.objects.filter(pk=cliente_id).first()
        if cliente:
            initial["cliente"] = cliente.pk
            initial["titulo"] = cliente.empresa or cliente.nome
            initial["status"] = Project.Status.EM_ANDAMENTO
    form = ProjectForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        project = form.save()
        messages.success(request, "Projeto criado.")
        return redirect("erp:project_edit", pk=project.pk)
    return render(
        request,
        "erp/projetos/form.html",
        {"page_title": "Novo projeto", "form": form, "project": None},
    )


@staff_required
@require_http_methods(["GET", "POST"])
def project_edit(request: HttpRequest, pk: int) -> HttpResponse:
    project = get_object_or_404(Project.objects.select_related("cliente"), pk=pk)
    form = ProjectForm(request.POST or None, request.FILES or None, instance=project)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Projeto atualizado.")
        return redirect("erp:project_edit", pk=project.pk)
    return render(
        request,
        "erp/projetos/form.html",
        {"page_title": f"Editar — {project.titulo}", "form": form, "project": project},
    )


@staff_required
@require_POST
def project_delete(request: HttpRequest, pk: int) -> HttpResponse:
    project = get_object_or_404(Project, pk=pk)
    titulo = project.titulo
    project.delete()
    messages.success(request, f"Projeto “{titulo}” removido.")
    return redirect("erp:project_list")


@staff_required
@require_POST
def project_reorder(request: HttpRequest) -> HttpResponse:
    """Expects POST field order as list of project ids in desired ordem."""
    ids = request.POST.getlist("order")
    for index, pk in enumerate(ids):
        Project.objects.filter(pk=pk).update(ordem=index)

    wants_json = (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or "application/json" in (request.headers.get("accept") or "")
    )
    if wants_json:
        return JsonResponse({"ok": True, "count": len(ids)})

    messages.success(request, "Ordem da vitrine atualizada.")
    return redirect("erp:project_list")


# --- Buscas no Apify -------------------------------------------------------


@staff_required
def cliente_busca_list(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "erp/clientes/buscas.html",
        {
            "page_title": "Buscas de leads",
            "buscas": BuscaLeads.objects.all()[:100],
            "apify_configurado": apify.configurado(),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def cliente_busca_create(request: HttpRequest) -> HttpResponse:
    origem = None
    if request.GET.get("copiar"):
        origem = BuscaLeads.objects.filter(pk=request.GET["copiar"]).first()
    if request.method == "POST":
        form = BuscaLeadsForm(request.POST)
        if form.is_valid():
            busca = form.save()
            if request.POST.get("iniciar") == "1":
                return _iniciar_busca(request, busca)
            messages.success(request, "Busca salva. Confira e clique em Iniciar.")
            return redirect("erp:cliente_busca_detail", pk=busca.pk)
    else:
        inicial = {}
        if origem is not None:
            inicial = {
                "nome": f"{origem.nome} (cópia)",
                "termos": origem.termos,
                "local": origem.local,
                "max_por_termo": origem.max_por_termo,
                "pular_fechados": origem.pular_fechados,
                "entrada_extra": origem.entrada_extra or None,
            }
        form = BuscaLeadsForm(initial=inicial)
    return render(
        request,
        "erp/clientes/busca_form.html",
        {
            "page_title": "Nova busca de leads",
            "form": form,
            "apify_configurado": apify.configurado(),
        },
    )


def _iniciar_busca(request: HttpRequest, busca: BuscaLeads) -> HttpResponse:
    try:
        buscas.iniciar(busca)
    except apify.ApifyError as exc:
        busca.status = BuscaLeads.Status.ERRO
        busca.erro = str(exc)
        busca.save(update_fields=["status", "erro", "updated_at"])
        messages.error(request, f"Não foi possível iniciar: {exc}")
    else:
        messages.success(request, "Busca iniciada no Apify. Esta página se atualiza sozinha até terminar.")
    return redirect("erp:cliente_busca_detail", pk=busca.pk)


@staff_required
def cliente_busca_detail(request: HttpRequest, pk: int) -> HttpResponse:
    busca = get_object_or_404(BuscaLeads, pk=pk)
    if buscas.precisa_verificar(busca):
        try:
            busca = buscas.atualizar(busca.pk)
        except apify.ApifyError as exc:
            messages.error(request, f"Não consegui consultar o Apify agora: {exc}")
    leads = busca.leads.order_by("ordem_fila", "-nota", "empresa")
    categorias = (
        leads.values("categoria_lead").annotate(total=Count("id")).order_by("-total")
    )
    rotulos = dict(Cliente.CategoriaLead.choices)
    return render(
        request,
        "erp/clientes/busca_detail.html",
        {
            "page_title": busca.nome,
            "busca": busca,
            "leads": leads[:300],
            "categorias": [
                {"valor": c["categoria_lead"], "rotulo": rotulos.get(c["categoria_lead"], "Sem categoria"), "total": c["total"]}
                for c in categorias
            ],
            "entrada": json.dumps(busca.entrada(), ensure_ascii=False, indent=2),
        },
    )


@staff_required
@require_POST
def cliente_busca_iniciar(request: HttpRequest, pk: int) -> HttpResponse:
    busca = get_object_or_404(BuscaLeads, pk=pk)
    if not busca.pode_iniciar:
        messages.warning(request, "Esta busca já foi iniciada.")
        return redirect("erp:cliente_busca_detail", pk=busca.pk)
    return _iniciar_busca(request, busca)


@staff_required
@require_POST
def cliente_busca_delete(request: HttpRequest, pk: int) -> HttpResponse:
    busca = get_object_or_404(BuscaLeads, pk=pk)
    if busca.status == BuscaLeads.Status.RODANDO:
        messages.error(request, "Espere a busca terminar antes de excluir.")
        return redirect("erp:cliente_busca_detail", pk=busca.pk)
    busca.delete()
    messages.success(request, "Busca excluída. Os leads importados continuam em Clientes.")
    return redirect("erp:cliente_busca_list")


# --- Tarefas ----------------------------------------------------------------


def _filtrar_tarefas(request: HttpRequest, queryset):
    filtros = {}
    q = (request.GET.get("q") or "").strip()
    if q:
        queryset = queryset.filter(Q(titulo__icontains=q) | Q(descricao__icontains=q))
    frente = request.GET.get("frente") or ""
    if frente in Tarefa.Frente.values:
        queryset = queryset.filter(frente=frente)
        filtros["frente"] = frente
    prioridade = request.GET.get("prioridade") or ""
    if prioridade.isdigit() and int(prioridade) in Tarefa.Prioridade.values:
        queryset = queryset.filter(prioridade=int(prioridade))
        filtros["prioridade"] = prioridade
    return queryset, q, filtros


@staff_required
@require_http_methods(["GET", "POST"])
def tarefa_list(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        rapida = TarefaRapidaForm(request.POST)
        if rapida.is_valid():
            rapida.save()
            messages.success(request, "Tarefa criada.")
            return redirect(request.get_full_path())
    else:
        rapida = TarefaRapidaForm()
    tarefas, q, filtros = _filtrar_tarefas(request, Tarefa.objects.all())
    abertas = tarefas.exclude(status=Tarefa.Status.FEITA)
    feitas = tarefas.filter(status=Tarefa.Status.FEITA).order_by("-concluida_em")
    colunas = [
        {"status": valor, "rotulo": rotulo, "tarefas": [t for t in abertas if t.status == valor]}
        for valor, rotulo in Tarefa.Status.choices
        if valor != Tarefa.Status.FEITA
    ]
    colunas.append(
        {"status": Tarefa.Status.FEITA, "rotulo": "Feitas", "tarefas": list(feitas[:20]), "total": feitas.count()}
    )
    hoje = timezone.localdate()
    return render(
        request,
        "erp/tarefas/list.html",
        {
            "page_title": "Tarefas",
            "colunas": colunas,
            "rapida": rapida,
            "q": q,
            "filtros": filtros,
            "frentes": Tarefa.Frente.choices,
            "prioridades": Tarefa.Prioridade.choices,
            "atrasadas": abertas.filter(prazo__lt=hoje).count(),
            "hoje": abertas.filter(prazo=hoje).count(),
            "total_abertas": abertas.count(),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def tarefa_create(request: HttpRequest) -> HttpResponse:
    form = TarefaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tarefa criada.")
        return redirect("erp:tarefa_list")
    return render(request, "erp/tarefas/form.html", {"page_title": "Nova tarefa", "form": form})


@staff_required
@require_http_methods(["GET", "POST"])
def tarefa_edit(request: HttpRequest, pk: int) -> HttpResponse:
    tarefa = get_object_or_404(Tarefa, pk=pk)
    form = TarefaForm(request.POST or None, instance=tarefa)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tarefa salva.")
        return redirect("erp:tarefa_list")
    return render(
        request,
        "erp/tarefas/form.html",
        {"page_title": "Editar tarefa", "form": form, "tarefa": tarefa},
    )


@staff_required
@require_POST
def tarefa_status(request: HttpRequest, pk: int) -> HttpResponse:
    tarefa = get_object_or_404(Tarefa, pk=pk)
    status = request.POST.get("status") or ""
    if status in Tarefa.Status.values:
        tarefa.status = status
        tarefa.save()
    destino = request.POST.get("next") or ""
    if destino.startswith("/") and not destino.startswith("//"):
        return redirect(destino)
    return redirect("erp:tarefa_list")


@staff_required
@require_POST
def tarefa_delete(request: HttpRequest, pk: int) -> HttpResponse:
    tarefa = get_object_or_404(Tarefa, pk=pk)
    tarefa.delete()
    messages.success(request, "Tarefa excluída.")
    return redirect("erp:tarefa_list")
