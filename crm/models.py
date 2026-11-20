from django.conf import settings
from django.db import models


class StaffProfile(models.Model):
    class Role(models.TextChoices):
        EMPLOYEE = "employee", "Xodim"
        DIRECTOR = "director", "Direktor"
        ADMINISTRATOR = "administrator", "Administrator"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name="Xodim",
        on_delete=models.CASCADE,
        related_name="staff_profile",
    )
    role = models.CharField(
        "Lavozimi",
        max_length=20,
        choices=Role.choices,
        default=Role.EMPLOYEE,
    )

    class Meta:
        verbose_name = "Xodim roli"
        verbose_name_plural = "Xodim rollari"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        is_staff = self.role == self.Role.ADMINISTRATOR or self.user.is_superuser
        if self.user.is_staff != is_staff:
            self.user.is_staff = is_staff
            self.user.save(update_fields=["is_staff"])

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} — {self.get_role_display()}"


def get_staff_role(user):
    if user.is_superuser:
        return StaffProfile.Role.ADMINISTRATOR
    try:
        return user.staff_profile.role
    except StaffProfile.DoesNotExist:
        return StaffProfile.Role.EMPLOYEE


class Car(models.Model):
    class Status(models.TextChoices):
        IN_STOCK = "Omborda", "Omborda"
        RESERVED = "Band qilingan", "Band qilingan"
        SOLD = "Sotilgan", "Sotilgan"

    model_name = models.CharField("Model", max_length=100)
    color = models.CharField("Rang", max_length=60)
    price = models.DecimalField("Narxi", max_digits=14, decimal_places=2)
    status = models.CharField(
        "Holati", max_length=20, choices=Status.choices, default=Status.IN_STOCK
    )

    class Meta:
        ordering = ["model_name", "color"]
        verbose_name = "Avtomobil"
        verbose_name_plural = "Avtomobillar"

    def __str__(self):
        return f"{self.model_name} — {self.color}"


class Customer(models.Model):
    name = models.CharField("Ism-familiya", max_length=150)
    phone = models.CharField("Telefon", max_length=30)
    interested_car = models.ForeignKey(
        Car,
        verbose_name="Qiziqqan avtomobili",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customers",
    )
    created_at = models.DateTimeField("Yaratilgan vaqt", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Mijoz"
        verbose_name_plural = "Mijozlar"

    def __str__(self):
        return self.name


class Deal(models.Model):
    class Stage(models.TextChoices):
        NEW = "Yangi Lid", "Yangi Lid"
        CONTACTED = "Muloqot qilindi", "Muloqot qilindi"
        TEST_DRIVE = "Test-Drayv", "Test-Drayv"
        CONTRACT = "Shartnoma", "Shartnoma"
        SOLD = "Sotildi", "Sotildi"

    customer = models.ForeignKey(
        Customer, verbose_name="Mijoz", on_delete=models.CASCADE, related_name="deals"
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Menejer",
        on_delete=models.PROTECT,
        related_name="deals",
    )
    stage = models.CharField(
        "Bosqich", max_length=30, choices=Stage.choices, default=Stage.NEW
    )
    total_price = models.DecimalField("Bitim summasi", max_digits=14, decimal_places=2)

    class Meta:
        ordering = ["-pk"]
        verbose_name = "Bitim"
        verbose_name_plural = "Bitimlar"

    def __str__(self):
        return f"{self.customer.name} — {self.get_stage_display()}"
