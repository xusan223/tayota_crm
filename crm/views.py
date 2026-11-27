from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import PurePosixPath

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from .invoices import build_invoice_pdf, invoice_number
from .models import (
    Car,
    Customer,
    Deal,
    Document,
    Note,
    StaffProfile,
    Task,
    get_staff_role,
)

DEAL_RELATED = ("customer", "customer__interested_car", "manager")


# --------------------------------------------------------------------------
# Access rules: employees work only with their own deals and customers;
# directors and administrators see everything.
# --------------------------------------------------------------------------

def can_manage_all(user):
    return get_staff_role(user) in {
        StaffProfile.Role.DIRECTOR,
        StaffProfile.Role.ADMINISTRATOR,
    }


def visible_deals(user):
    deals = Deal.objects.select_related(*DEAL_RELATED)
    return deals if can_manage_all(user) else deals.filter(manager=user)


def visible_customers(user):
    customers = Customer.objects.select_related("interested_car")
    if can_manage_all(user):
        return customers
    return customers.filter(deals__manager=user).distinct()


def visible_tasks(user):
    tasks = Task.objects.select_related("customer", "assignee")
    return tasks if can_manage_all(user) else tasks.filter(assignee=user)


def active_users():
    return get_user_model().objects.filter(is_active=True).order_by(
        "first_name", "username"
    )


def redirect_back(request, default):
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(target)
    return redirect(default)


def base_context(request):
    """Context used by every page built on crm/base.html."""
    role = get_staff_role(request.user)
    manage_all = can_manage_all(request.user)
    return {
        "role": role,
        "role_label": StaffProfile.Role(role).label,
        "can_assign_deals": manage_all,
        "can_manage_all": manage_all,
        "is_administrator": role == StaffProfile.Role.ADMINISTRATOR,
        "cars": Car.objects.all(),
        "managers": active_users() if manage_all else [request.user],
        "open_task_count": visible_tasks(request.user).filter(is_done=False).count(),
        "task_kinds": Task.Kind.choices,
    }


def bar_rows(items, value_key):
    """Add a 0-100 ``pct`` to each item relative to the largest value."""
    largest = max((item[value_key] for item in items), default=0)
    for item in items:
        item["pct"] = round(item[value_key] * 100 / largest) if largest else 0
    return items


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------

def create_lead(request, can_assign):
    name = request.POST.get("name", "").strip()
    phone = request.POST.get("phone", "").strip()
    car_id = request.POST.get("interested_car", "").strip()
    manager_id = request.POST.get("manager", "").strip()

    if not name or not phone:
        messages.error(request, "Mijozning ismi va telefoni kiritilishi shart.")
        return

    try:
        car = Car.objects.get(pk=car_id) if car_id else None
        if can_assign:
            manager = get_user_model().objects.get(pk=manager_id, is_active=True)
        else:
            manager = request.user
        total_price = Decimal(request.POST.get("total_price", "").strip())
        if total_price < 0:
            raise InvalidOperation
    except (Car.DoesNotExist, get_user_model().DoesNotExist, InvalidOperation, ValueError):
        messages.error(
            request,
            "Avtomobil, faol menejer va to‘g‘ri bitim summasini tanlang.",
        )
        return

    with transaction.atomic():
        customer = Customer.objects.create(name=name, phone=phone, interested_car=car)
        Deal.objects.create(
            customer=customer,
            manager=manager,
            stage=Deal.Stage.NEW,
            total_price=total_price,
        )
    messages.success(request, "Yangi mijoz va lid muvaffaqiyatli qo‘shildi.")


def director_kpi(stages):
    sold_deals = Deal.objects.filter(stage=Deal.Stage.SOLD)
    total_deals = Deal.objects.count()
    total_sales = sold_deals.count()
    total_revenue = sold_deals.aggregate(total=Sum("total_price"))["total"] or Decimal("0")
    staff_kpis = (
        StaffProfile.objects.filter(user__is_active=True)
        .exclude(role=StaffProfile.Role.ADMINISTRATOR)
        .select_related("user")
        .annotate(
            lead_count=Count("user__deals", distinct=True),
            sales_count=Count(
                "user__deals",
                filter=Q(user__deals__stage=Deal.Stage.SOLD),
                distinct=True,
            ),
            revenue=Sum(
                "user__deals__total_price",
                filter=Q(user__deals__stage=Deal.Stage.SOLD),
            ),
        )
        .order_by("-sales_count", "user__last_name", "user__first_name")
    )

    stage_counts = {
        row["stage"]: row["count"]
        for row in Deal.objects.values("stage").annotate(count=Count("pk")).order_by()
    }
    stage_chart = bar_rows(
        [{"label": label, "count": stage_counts.get(value, 0)} for value, label in stages],
        "count",
    )
    model_chart = bar_rows(
        [
            {"label": row["customer__interested_car__model_name"] or "Tanlanmagan",
             "count": row["count"], "revenue": row["revenue"]}
            for row in sold_deals.values("customer__interested_car__model_name")
            .annotate(count=Count("pk"), revenue=Sum("total_price"))
            .order_by("-revenue")
        ],
        "revenue",
    )
    staff = [
        {
            "profile": profile,
            "lead_count": profile.lead_count,
            "sales_count": profile.sales_count,
            "conversion_rate": (
                round(profile.sales_count * 100 / profile.lead_count, 1)
                if profile.lead_count
                else 0
            ),
            "revenue": profile.revenue or Decimal("0"),
        }
        for profile in staff_kpis
    ]
    return {
        "lead_count": total_deals,
        "sales_count": total_sales,
        "active_deals": total_deals - total_sales,
        "conversion_rate": round(total_sales * 100 / total_deals, 1) if total_deals else 0,
        "revenue": total_revenue,
        "average_sale": total_revenue / total_sales if total_sales else Decimal("0"),
        "staff": staff,
        "stage_chart": stage_chart,
        "model_chart": model_chart,
        "staff_chart": bar_rows(
            [{"label": item["profile"].user.get_full_name() or item["profile"].user.username,
              "count": item["sales_count"]} for item in staff],
            "count",
        ),
    }


@require_http_methods(["GET", "POST"])
@login_required
def dashboard(request):
    context = base_context(request)

    if request.method == "POST":
        create_lead(request, context["can_assign_deals"])
        return redirect("dashboard")

    deals = list(visible_deals(request.user))
    stages = Deal.Stage.choices
    query = request.GET.get("q", "").strip()
    customers = visible_customers(request.user)
    if query:
        customers = customers.filter(Q(name__icontains=query) | Q(phone__icontains=query))
    open_tasks = visible_tasks(request.user).filter(is_done=False)

    context.update(
        {
            "customers": customers,
            "query": query,
            "deals": deals,
            "stage_columns": [
                {
                    "value": stage_value,
                    "label": stage_label,
                    "deals": [deal for deal in deals if deal.stage == stage_value],
                }
                for stage_value, stage_label in stages
            ],
            "stages": stages,
            "car_statuses": Car.Status.choices,
            "total_leads": len(deals),
            "total_sales": sum(deal.stage == Deal.Stage.SOLD for deal in deals),
            "cars_in_stock": Car.objects.filter(status=Car.Status.IN_STOCK).count(),
            "sales_revenue": sum(
                (deal.total_price for deal in deals if deal.stage == Deal.Stage.SOLD),
                Decimal("0"),
            ),
            "tasks": open_tasks,
            "upcoming_tasks": open_tasks[:4],
            "done_tasks": visible_tasks(request.user).filter(is_done=True).order_by("-due_at")[:10],
            "now": timezone.now(),
        }
    )
    if context["role"] == StaffProfile.Role.DIRECTOR:
        context["kpi"] = director_kpi(stages)
    return render(request, "crm/index.html", context)


# --------------------------------------------------------------------------
# Deals
# --------------------------------------------------------------------------

@require_POST
@login_required
def change_deal_stage(request, pk):
    deal = get_object_or_404(visible_deals(request.user), pk=pk)
    stage = request.POST.get("stage", "")
    if stage not in Deal.Stage.values:
        messages.error(request, "Bunday bosqich mavjud emas.")
    elif stage != deal.stage:
        deal.stage = stage
        deal.save(update_fields=["stage"])
        messages.success(
            request,
            f"“{deal.customer.name}” bitimi “{deal.get_stage_display()}” bosqichiga o‘tkazildi.",
        )
    return redirect_back(request, reverse("dashboard") + "#kanban")


@require_POST
@login_required
def create_invoice(request, pk):
    deal = get_object_or_404(visible_deals(request.user), pk=pk)
    if not deal.can_have_invoice:
        messages.error(request, "Invoice faqat “Shartnoma” yoki “Sotildi” bosqichidagi bitim uchun yaratiladi.")
        return redirect_back(request, reverse("customer-detail", args=[deal.customer_id]))

    pdf = build_invoice_pdf(deal, request.user)
    number = invoice_number(deal)
    filename = f"invoice-{number}-{timezone.localtime():%Y%m%d%H%M%S}.pdf"
    document = Document(
        deal=deal,
        kind=Document.Kind.INVOICE,
        title=f"Invoice #{number} — {deal.customer.name}",
        size=len(pdf),
        created_by=request.user,
    )
    document.file.save(filename, ContentFile(pdf), save=False)
    document.save()
    messages.success(request, f"Invoice #{number} yaratildi va saqlandi.")
    return redirect_back(request, reverse("customer-detail", args=[deal.customer_id]))


@require_GET
@login_required
def download_document(request, pk):
    document = get_object_or_404(
        Document.objects.filter(deal__in=visible_deals(request.user)), pk=pk
    )
    return FileResponse(
        document.file.open("rb"),
        as_attachment=True,
        filename=PurePosixPath(document.file.name).name,
        content_type="application/pdf",
    )


# --------------------------------------------------------------------------
# Customers, notes and tasks
# --------------------------------------------------------------------------

@require_GET
@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(visible_customers(request.user), pk=pk)
    context = base_context(request)
    context.update(
        {
            "customer": customer,
            "customer_deals": visible_deals(request.user)
            .filter(customer=customer)
            .prefetch_related("documents"),
            "notes": customer.notes.select_related("author"),
            "customer_tasks": customer.tasks.select_related("assignee"),
            "stages": Deal.Stage.choices,
            "now": timezone.now(),
        }
    )
    return render(request, "crm/customer_detail.html", context)


@require_POST
@login_required
def add_note(request, pk):
    customer = get_object_or_404(visible_customers(request.user), pk=pk)
    text = request.POST.get("text", "").strip()
    if not text:
        messages.error(request, "Izoh matni bo‘sh bo‘lmasligi kerak.")
    elif len(text) > 2000:
        messages.error(request, "Izoh 2000 belgidan oshmasligi kerak.")
    else:
        Note.objects.create(customer=customer, author=request.user, text=text)
        messages.success(request, "Izoh qo‘shildi.")
    return redirect("customer-detail", pk=customer.pk)


def parse_due(value):
    try:
        due = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if timezone.is_naive(due):
        due = timezone.make_aware(due)
    return due


@require_POST
@login_required
def add_task(request, pk):
    customer = get_object_or_404(visible_customers(request.user), pk=pk)
    title = request.POST.get("title", "").strip()
    kind = request.POST.get("kind", "")
    due_at = parse_due(request.POST.get("due_at", ""))
    assignee = request.user
    if can_manage_all(request.user) and request.POST.get("assignee"):
        assignee = active_users().filter(pk=request.POST["assignee"]).first()

    if not title or len(title) > 200 or kind not in Task.Kind.values or not due_at or not assignee:
        messages.error(request, "Vazifa nomi, turi, muddati va mas’ul xodimni to‘g‘ri kiriting.")
    else:
        Task.objects.create(
            customer=customer, assignee=assignee, kind=kind, title=title, due_at=due_at
        )
        messages.success(request, "Vazifa qo‘shildi.")
    return redirect("customer-detail", pk=customer.pk)


@require_POST
@login_required
def toggle_task(request, pk):
    task = get_object_or_404(visible_tasks(request.user), pk=pk)
    task.is_done = not task.is_done
    task.save(update_fields=["is_done"])
    messages.success(
        request,
        "Vazifa bajarildi deb belgilandi." if task.is_done else "Vazifa qayta ochildi.",
    )
    return redirect_back(request, reverse("dashboard") + "#tasks")


# --------------------------------------------------------------------------
# Inventory
# --------------------------------------------------------------------------

def parse_price(value):
    try:
        price = Decimal(value.strip())
    except (AttributeError, InvalidOperation):
        return None
    return price if price >= 0 else None


@require_POST
@login_required
def add_car(request):
    if not can_manage_all(request.user):
        raise PermissionDenied
    model_name = request.POST.get("model_name", "").strip()
    color = request.POST.get("color", "").strip()
    price = parse_price(request.POST.get("price", ""))
    status = request.POST.get("status", Car.Status.IN_STOCK)
    if not model_name or not color or price is None or status not in Car.Status.values:
        messages.error(request, "Model, rang, narx va holatni to‘g‘ri kiriting.")
    else:
        Car.objects.create(model_name=model_name, color=color, price=price, status=status)
        messages.success(request, f"{model_name} — {color} omborga qo‘shildi.")
    return redirect(reverse("dashboard") + "#inventory")


@require_POST
@login_required
def update_car(request, pk):
    if not can_manage_all(request.user):
        raise PermissionDenied
    car = get_object_or_404(Car, pk=pk)
    status = request.POST.get("status", "")
    price = parse_price(request.POST.get("price", ""))
    if status not in Car.Status.values or price is None:
        messages.error(request, "Holat va narxni to‘g‘ri kiriting.")
    else:
        car.status = status
        car.price = price
        car.save(update_fields=["status", "price"])
        messages.success(request, f"{car} yangilandi.")
    return redirect(reverse("dashboard") + "#inventory")


# --------------------------------------------------------------------------
# Excel export
# --------------------------------------------------------------------------

def write_sheet(sheet, headers, rows):
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="EB0A1E")
    for row in rows:
        sheet.append(row)
    for column in sheet.columns:
        width = max(len(str(cell.value or "")) for cell in column)
        sheet.column_dimensions[column[0].column_letter].width = min(max(width + 2, 10), 50)
    sheet.freeze_panes = "A2"


@require_GET
@login_required
def export_excel(request):
    workbook = Workbook()
    deals_sheet = workbook.active
    deals_sheet.title = "Bitimlar"
    write_sheet(
        deals_sheet,
        ["№", "Mijoz", "Telefon", "Avtomobil", "Bosqich", "Menejer", "Summa (so‘m)", "Sana"],
        [
            [
                deal.pk,
                deal.customer.name,
                deal.customer.phone,
                str(deal.customer.interested_car or ""),
                deal.get_stage_display(),
                deal.manager.get_full_name() or deal.manager.username,
                float(deal.total_price),
                timezone.localtime(deal.created_at).strftime("%d.%m.%Y %H:%M"),
            ]
            for deal in visible_deals(request.user).order_by("pk")
        ],
    )
    write_sheet(
        workbook.create_sheet("Mijozlar"),
        ["№", "Mijoz", "Telefon", "Qiziqqan avtomobil", "Qo‘shilgan sana"],
        [
            [
                customer.pk,
                customer.name,
                customer.phone,
                str(customer.interested_car or ""),
                timezone.localtime(customer.created_at).strftime("%d.%m.%Y %H:%M"),
            ]
            for customer in visible_customers(request.user).order_by("pk")
        ],
    )
    buffer = BytesIO()
    workbook.save(buffer)
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="toyota-crm-{timezone.localdate():%Y-%m-%d}.xlsx"'
    )
    return response
