from django.conf import settings
from django.db import models
from django.utils import timezone


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
    created_at = models.DateTimeField("Yaratilgan vaqt", default=timezone.now)

    class Meta:
        ordering = ["-pk"]
        verbose_name = "Bitim"
        verbose_name_plural = "Bitimlar"

    def __str__(self):
        return f"{self.customer.name} — {self.get_stage_display()}"

    @property
    def next_stage(self):
        values = self.Stage.values
        index = values.index(self.stage)
        return values[index + 1] if index + 1 < len(values) else None

    @property
    def previous_stage(self):
        values = self.Stage.values
        index = values.index(self.stage)
        return values[index - 1] if index > 0 else None

    @property
    def can_have_invoice(self):
        return self.stage in {self.Stage.CONTRACT, self.Stage.SOLD}


class Note(models.Model):
    customer = models.ForeignKey(
        Customer, verbose_name="Mijoz", on_delete=models.CASCADE, related_name="notes"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Muallif",
        on_delete=models.SET_NULL,
        null=True,
        related_name="crm_notes",
    )
    text = models.TextField("Izoh", max_length=2000)
    created_at = models.DateTimeField("Yozilgan vaqt", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "Izoh"
        verbose_name_plural = "Izohlar"

    def __str__(self):
        return f"{self.customer.name}: {self.text[:40]}"


class Task(models.Model):
    class Kind(models.TextChoices):
        CALL = "call", "Qo‘ng‘iroq"
        TEST_DRIVE = "test_drive", "Test-drayv"
        MEETING = "meeting", "Uchrashuv"
        OTHER = "other", "Boshqa"

    customer = models.ForeignKey(
        Customer, verbose_name="Mijoz", on_delete=models.CASCADE, related_name="tasks"
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Mas’ul",
        on_delete=models.CASCADE,
        related_name="crm_tasks",
    )
    kind = models.CharField("Turi", max_length=20, choices=Kind.choices, default=Kind.CALL)
    title = models.CharField("Vazifa", max_length=200)
    due_at = models.DateTimeField("Muddat")
    is_done = models.BooleanField("Bajarildi", default=False)
    created_at = models.DateTimeField("Yaratilgan vaqt", auto_now_add=True)

    class Meta:
        ordering = ["is_done", "due_at", "pk"]
        verbose_name = "Vazifa"
        verbose_name_plural = "Vazifalar"

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        return not self.is_done and self.due_at < timezone.now()


def document_upload_to(instance, filename):
    return f"documents/{timezone.now():%Y/%m}/{filename}"


class Document(models.Model):
    class Kind(models.TextChoices):
        INVOICE = "invoice", "Invoice"

    deal = models.ForeignKey(
        Deal, verbose_name="Bitim", on_delete=models.CASCADE, related_name="documents"
    )
    kind = models.CharField("Turi", max_length=20, choices=Kind.choices, default=Kind.INVOICE)
    title = models.CharField("Nomi", max_length=200)
    file = models.FileField("Fayl", upload_to=document_upload_to)
    size = models.PositiveIntegerField("Hajmi (bayt)", default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Yaratgan",
        on_delete=models.SET_NULL,
        null=True,
        related_name="crm_documents",
    )
    created_at = models.DateTimeField("Yaratilgan vaqt", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "Hujjat"
        verbose_name_plural = "Hujjatlar"

    def __str__(self):
        return self.title
