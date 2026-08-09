import csv
import io
import re
from functools import wraps

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods, require_POST

from crm.models import Cliente, Mockup
from portfolio.models import Project

from .forms import (
    ClienteForm,
    CsvImportForm,
    MockupForm,
    MockupImagemFormSet,
    ProjectForm,
    RejectForm,
)
from .mixins import ListingMixin


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
    mixin = ClienteListing()
    listing = _listing_context(mixin, request, Cliente.objects.all())
    listing.update(
        {
            "page_title": "Clientes",
            "status_choices": Cliente.Status.choices,
            "origem_choices": Cliente.Origem.choices,
            "etapa_choices": Cliente.EtapaRejeicao.choices,
            "cidades": Cliente.objects.exclude(cidade="")
            .order_by("cidade")
            .values_list("cidade", flat=True)
            .distinct(),
            "estados": Cliente.objects.exclude(estado="")
            .order_by("estado")
            .values_list("estado", flat=True)
            .distinct(),
        }
    )
    return render(request, "erp/clientes/list.html", listing)


@staff_required
@require_http_methods(["GET", "POST"])
def cliente_create(request: HttpRequest) -> HttpResponse:
    form = ClienteForm(request.POST or None, initial={"origem": Cliente.Origem.MANUAL})
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
    reject_form = RejectForm()
    return render(
        request,
        "erp/clientes/detail.html",
        {
            "page_title": cliente.display_name,
            "cliente": cliente,
            "reject_form": reject_form,
            "mockups": cliente.mockups.all(),
            "projetos": cliente.projetos.all(),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
def cliente_edit(request: HttpRequest, pk: int) -> HttpResponse:
    cliente = get_object_or_404(Cliente, pk=pk)
    previous_status = cliente.status
    form = ClienteForm(request.POST or None, instance=cliente)
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
    search_fields = ["empresa", "telefone", "cidade", "categoria", "website"]
    filter_fields = ["cidade", "estado", "categoria"]
    sort_fields = {
        "empresa": "empresa",
        "cidade": "cidade",
        "categoria": "categoria",
        "created_at": "created_at",
    }
    default_sort = "empresa"
    paginate_by = 50


@staff_required
def cliente_filtragem(request: HttpRequest) -> HttpResponse:
    mixin = FiltragemListing()
    qs = Cliente.objects.filter(status=Cliente.Status.IMPORTADO)
    listing = _listing_context(mixin, request, qs)
    listing.update(
        {
            "page_title": "Filtragem de leads",
            "reject_form": RejectForm(),
            "cidades": qs.exclude(cidade="").order_by("cidade").values_list("cidade", flat=True).distinct(),
            "estados": qs.exclude(estado="").order_by("estado").values_list("estado", flat=True).distinct(),
            "categorias": qs.exclude(categoria="")
            .order_by("categoria")
            .values_list("categoria", flat=True)
            .distinct(),
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


def _decode_csv(uploaded) -> str:
    raw = uploaded.read()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def _normalize_phone(phone: str) -> str:
    return re.sub(r"\D+", "", phone or "")


def _unique_cliente_slug(base: str) -> str:
    slug_base = slugify(base)[:180] or "cliente"
    candidate = slug_base
    index = 2
    while Cliente.objects.filter(slug=candidate).exists():
        candidate = f"{slug_base}-{index}"
        index += 1
    return candidate


@staff_required
@require_http_methods(["GET", "POST"])
def cliente_import_csv(request: HttpRequest) -> HttpResponse:
    form = CsvImportForm()
    preview_rows = request.session.get("csv_preview") or []

    if request.method == "POST":
        if request.POST.get("confirm") == "1":
            preview_rows = request.session.get("csv_preview") or []
            created = 0
            skipped = 0
            for item in preview_rows:
                if item.get("duplicate"):
                    skipped += 1
                    continue
                empresa = item["empresa"]
                phone_norm = _normalize_phone(item.get("telefone", ""))
                if phone_norm and len(phone_norm) >= 8:
                    if Cliente.objects.filter(telefone__icontains=phone_norm[-8:]).exists():
                        skipped += 1
                        continue
                if Cliente.objects.filter(
                    empresa__iexact=empresa, cidade__iexact=item.get("cidade", "")
                ).exists():
                    skipped += 1
                    continue
                Cliente.objects.create(
                    empresa=empresa,
                    slug=_unique_cliente_slug(empresa),
                    telefone=item.get("telefone", ""),
                    website=item.get("website", ""),
                    maps_url=item.get("maps_url", ""),
                    categoria=item.get("categoria", ""),
                    rua=item.get("rua", ""),
                    cidade=item.get("cidade", ""),
                    estado=item.get("estado", ""),
                    origem=Cliente.Origem.CSV,
                    status=Cliente.Status.IMPORTADO,
                )
                created += 1
            request.session.pop("csv_preview", None)
            messages.success(
                request,
                f"Importação concluída: {created} novo(s), {skipped} duplicata(s) ignorada(s).",
            )
            return redirect("erp:cliente_filtragem")

        form = CsvImportForm(request.POST, request.FILES)
        if form.is_valid():
            text = _decode_csv(form.cleaned_data["arquivo"])
            reader = csv.DictReader(io.StringIO(text), delimiter=";")
            if not reader.fieldnames:
                messages.error(request, "CSV inválido ou sem cabeçalho.")
                return redirect("erp:cliente_import")

            preview_rows = []
            duplicates = 0
            for row in reader:
                empresa = (row.get("title") or "").strip()
                if not empresa:
                    continue
                telefone = (row.get("phone") or "").strip()
                website = (row.get("website") or "").strip()
                maps_url = (row.get("url") or "").strip()
                categoria = (row.get("categoryName") or "").strip()
                rua = (row.get("street") or "").strip()
                cidade = (row.get("city") or "").strip()
                estado = (row.get("state") or "").strip()

                phone_norm = _normalize_phone(telefone)
                is_dup = False
                if phone_norm and len(phone_norm) >= 8:
                    if Cliente.objects.filter(telefone__icontains=phone_norm[-8:]).exists():
                        is_dup = True
                if not is_dup and Cliente.objects.filter(
                    empresa__iexact=empresa, cidade__iexact=cidade
                ).exists():
                    is_dup = True

                if is_dup:
                    duplicates += 1

                preview_rows.append(
                    {
                        "empresa": empresa,
                        "telefone": telefone,
                        "website": website,
                        "maps_url": maps_url,
                        "categoria": categoria,
                        "rua": rua,
                        "cidade": cidade,
                        "estado": estado,
                        "duplicate": is_dup,
                    }
                )

            request.session["csv_preview"] = preview_rows
            return render(
                request,
                "erp/clientes/import.html",
                {
                    "page_title": "Importar CSV",
                    "form": CsvImportForm(),
                    "preview_rows": preview_rows,
                    "duplicates": duplicates,
                    "show_preview": True,
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
        },
    )


# --- Mockups --------------------------------------------------------------


class MockupListing(ListingMixin):
    search_fields = ["titulo", "slug", "cliente__empresa", "cliente__nome", "descricao"]
    filter_fields = ["status", "cliente"]
    sort_fields = {
        "titulo": "titulo",
        "status": "status",
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
