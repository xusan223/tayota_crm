from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .models import Car, Customer, Deal, StaffProfile, get_staff_role


def is_crm_administrator(user):
    return user.is_active and (
        user.is_superuser
        or (
            user.is_staff
            and get_staff_role(user) == StaffProfile.Role.ADMINISTRATOR
        )
    )


class AdministratorOnlyAdmin:
    def has_module_permission(self, request):
        return is_crm_administrator(request.user)

    def has_view_permission(self, request, obj=None):
        return is_crm_administrator(request.user)

    def has_add_permission(self, request):
        return is_crm_administrator(request.user)

    def has_change_permission(self, request, obj=None):
        return is_crm_administrator(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_crm_administrator(request.user)


class StaffProfileInline(admin.StackedInline):
    model = StaffProfile
    can_delete = False
    extra = 0
    max_num = 1
    verbose_name = "CRM lavozimi"
    verbose_name_plural = "CRM lavozimi"
    fields = ("role",)


class CRMUserAdmin(AdministratorOnlyAdmin, UserAdmin):
    inlines = (StaffProfileInline,)

User = get_user_model()
admin.site.unregister(User)
admin.site.register(User, CRMUserAdmin)


@admin.register(Car)
class CarAdmin(AdministratorOnlyAdmin, admin.ModelAdmin):
    list_display = ("model_name", "color", "price", "status")
    list_filter = ("status", "model_name")
    search_fields = ("model_name", "color")


@admin.register(Customer)
class CustomerAdmin(AdministratorOnlyAdmin, admin.ModelAdmin):
    list_display = ("name", "phone", "interested_car", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name", "phone")
    date_hierarchy = "created_at"


@admin.register(Deal)
class DealAdmin(AdministratorOnlyAdmin, admin.ModelAdmin):
    list_display = ("customer", "manager", "stage", "total_price")
    list_filter = ("stage", "manager")
    search_fields = ("customer__name", "customer__phone", "manager__username")
