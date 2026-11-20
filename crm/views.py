from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .models import Car, Customer, Deal, StaffProfile, get_staff_role


@require_http_methods(["GET", "POST"])
@login_required
def dashboard(request):
    role = get_staff_role(request.user)
    can_assign_deals = role in {
        StaffProfile.Role.DIRECTOR,
        StaffProfile.Role.ADMINISTRATOR,
    }

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        phone = request.POST.get("phone", "").strip()
        car_id = request.POST.get("interested_car", "").strip()
        manager_id = request.POST.get("manager", "").strip()

        if not name or not phone:
            messages.error(request, "Mijozning ismi va telefoni kiritilishi shart.")
            return redirect("dashboard")

        try:
            car = Car.objects.get(pk=car_id) if car_id else None
            if can_assign_deals:
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
            return redirect("dashboard")

        with transaction.atomic():
            customer = Customer.objects.create(
                name=name, phone=phone, interested_car=car
            )
            Deal.objects.create(
                customer=customer,
                manager=manager,
                stage=Deal.Stage.NEW,
                total_price=total_price,
            )

        messages.success(request, "Yangi mijoz va lid muvaffaqiyatli qo‘shildi.")
        return redirect("dashboard")

    cars = Car.objects.all()
    deals_query = Deal.objects.select_related(
        "customer", "customer__interested_car", "manager"
    )
    if not can_assign_deals:
        deals_query = deals_query.filter(manager=request.user)
    deals = list(deals_query)
    customer_query = Customer.objects.select_related("interested_car")
    if not can_assign_deals:
        customer_query = customer_query.filter(deals__manager=request.user).distinct()
    stages = Deal.Stage.choices
    context = {
        "cars": cars,
        "customers": customer_query,
        "deals": deals,
        "stage_columns": [
            {
                "value": stage_value,
                "label": stage_label,
                "deals": [deal for deal in deals if deal.stage == stage_value],
            }
            for stage_value, stage_label in stages
        ],
        "managers": (
            get_user_model().objects.filter(is_active=True).order_by(
                "first_name", "username"
            )
            if can_assign_deals
            else [request.user]
        ),
        "stages": stages,
        "total_leads": len(deals),
        "total_sales": sum(deal.stage == Deal.Stage.SOLD for deal in deals),
        "cars_in_stock": Car.objects.filter(status=Car.Status.IN_STOCK).count(),
        "sales_revenue": sum(
            (deal.total_price for deal in deals if deal.stage == Deal.Stage.SOLD),
            Decimal("0"),
        ),
        "role": role,
        "role_label": StaffProfile.Role(role).label,
        "can_assign_deals": can_assign_deals,
        "is_administrator": role == StaffProfile.Role.ADMINISTRATOR,
    }

    if role == StaffProfile.Role.DIRECTOR:
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
        context["kpi"] = {
            "lead_count": total_deals,
            "sales_count": total_sales,
            "active_deals": total_deals - total_sales,
            "conversion_rate": (
                round(total_sales * 100 / total_deals, 1) if total_deals else 0
            ),
            "revenue": total_revenue,
            "average_sale": (
                total_revenue / total_sales if total_sales else Decimal("0")
            ),
            "staff": [
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
            ],
        }
    return render(request, "crm/index.html", context)
