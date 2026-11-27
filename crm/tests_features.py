import shutil
import tempfile
from datetime import timedelta
from io import BytesIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from .models import Car, Customer, Deal, Document, Note, StaffProfile, Task


class CrmFeatureTestBase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.employee = User.objects.create_user(username="employee")
        self.other = User.objects.create_user(username="other")
        self.director = User.objects.create_user(username="director")
        self.director.staff_profile.role = StaffProfile.Role.DIRECTOR
        self.director.staff_profile.save()
        self.car = Car.objects.create(
            model_name="Camry", color="Oq", price="450000000", status=Car.Status.IN_STOCK
        )
        self.customer = Customer.objects.create(
            name="Own Customer", phone="+998900001001", interested_car=self.car
        )
        self.deal = Deal.objects.create(
            customer=self.customer,
            manager=self.employee,
            stage=Deal.Stage.NEW,
            total_price="450000000",
        )
        self.other_customer = Customer.objects.create(
            name="Foreign Customer", phone="+998900001002", interested_car=self.car
        )
        self.other_deal = Deal.objects.create(
            customer=self.other_customer,
            manager=self.other,
            stage=Deal.Stage.SOLD,
            total_price="450000000",
        )


class DealStageTests(CrmFeatureTestBase):
    def test_employee_moves_own_deal_to_next_stage(self):
        self.client.force_login(self.employee)

        response = self.client.post(
            reverse("deal-stage", args=[self.deal.pk]),
            {"stage": Deal.Stage.CONTACTED, "next": reverse("dashboard") + "#kanban"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("dashboard") + "#kanban")
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.stage, Deal.Stage.CONTACTED)

    def test_employee_cannot_move_someone_elses_deal(self):
        self.client.force_login(self.employee)

        response = self.client.post(
            reverse("deal-stage", args=[self.other_deal.pk]), {"stage": Deal.Stage.NEW}
        )

        self.assertEqual(response.status_code, 404)
        self.other_deal.refresh_from_db()
        self.assertEqual(self.other_deal.stage, Deal.Stage.SOLD)

    def test_unknown_stage_is_rejected(self):
        self.client.force_login(self.employee)

        self.client.post(reverse("deal-stage", args=[self.deal.pk]), {"stage": "Bogus"})

        self.deal.refresh_from_db()
        self.assertEqual(self.deal.stage, Deal.Stage.NEW)

    def test_redirect_ignores_external_next_url(self):
        self.client.force_login(self.employee)

        response = self.client.post(
            reverse("deal-stage", args=[self.deal.pk]),
            {"stage": Deal.Stage.CONTACTED, "next": "https://evil.example/"},
        )

        self.assertEqual(response["Location"], reverse("dashboard") + "#kanban")

    def test_stage_change_requires_post(self):
        self.client.force_login(self.employee)

        response = self.client.get(reverse("deal-stage", args=[self.deal.pk]))

        self.assertEqual(response.status_code, 405)

    def test_director_can_move_any_deal(self):
        self.client.force_login(self.director)

        self.client.post(
            reverse("deal-stage", args=[self.other_deal.pk]), {"stage": Deal.Stage.CONTRACT}
        )

        self.other_deal.refresh_from_db()
        self.assertEqual(self.other_deal.stage, Deal.Stage.CONTRACT)

    def test_next_and_previous_stage_helpers(self):
        self.assertEqual(self.deal.next_stage, Deal.Stage.CONTACTED)
        self.assertIsNone(self.deal.previous_stage)
        self.assertIsNone(self.other_deal.next_stage)
        self.assertEqual(self.other_deal.previous_stage, Deal.Stage.CONTRACT)

    def test_kanban_shows_stage_buttons(self):
        self.client.force_login(self.employee)

        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, reverse("deal-stage", args=[self.deal.pk]))
        self.assertContains(response, "Muloqot qilindi →")


class CustomerCardTests(CrmFeatureTestBase):
    def test_employee_opens_own_customer_card(self):
        self.client.force_login(self.employee)

        response = self.client.get(reverse("customer-detail", args=[self.customer.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "crm/customer_detail.html")
        self.assertContains(response, "Own Customer")
        self.assertContains(response, "Muloqot tarixi")

    def test_employee_cannot_open_foreign_customer_card(self):
        self.client.force_login(self.employee)

        response = self.client.get(reverse("customer-detail", args=[self.other_customer.pk]))

        self.assertEqual(response.status_code, 404)

    def test_director_opens_any_customer_card(self):
        self.client.force_login(self.director)

        response = self.client.get(reverse("customer-detail", args=[self.other_customer.pk]))

        self.assertEqual(response.status_code, 200)

    def test_add_note_records_author(self):
        self.client.force_login(self.employee)

        self.client.post(
            reverse("customer-add-note", args=[self.customer.pk]),
            {"text": "Qo‘ng‘iroq qilindi"},
        )

        note = Note.objects.get()
        self.assertEqual(note.customer, self.customer)
        self.assertEqual(note.author, self.employee)

    def test_empty_note_is_rejected(self):
        self.client.force_login(self.employee)

        self.client.post(reverse("customer-add-note", args=[self.customer.pk]), {"text": "  "})

        self.assertEqual(Note.objects.count(), 0)

    def test_note_on_foreign_customer_is_not_found(self):
        self.client.force_login(self.employee)

        response = self.client.post(
            reverse("customer-add-note", args=[self.other_customer.pk]), {"text": "x"}
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Note.objects.count(), 0)

    def test_search_filters_customers_by_name_or_phone(self):
        self.client.force_login(self.director)

        by_name = self.client.get(reverse("dashboard"), {"q": "foreign"})
        by_phone = self.client.get(reverse("dashboard"), {"q": "1001"})

        self.assertEqual([c.name for c in by_name.context["customers"]], ["Foreign Customer"])
        self.assertEqual([c.name for c in by_phone.context["customers"]], ["Own Customer"])

    def test_employee_search_stays_within_own_customers(self):
        self.client.force_login(self.employee)

        response = self.client.get(reverse("dashboard"), {"q": "Customer"})

        self.assertEqual([c.name for c in response.context["customers"]], ["Own Customer"])


class TaskTests(CrmFeatureTestBase):
    def test_employee_adds_task_assigned_to_self(self):
        self.client.force_login(self.employee)

        self.client.post(
            reverse("customer-add-task", args=[self.customer.pk]),
            {
                "title": "Test-drayvga taklif",
                "kind": Task.Kind.TEST_DRIVE,
                "due_at": "2030-01-15T10:30",
                "assignee": self.other.pk,
            },
        )

        task = Task.objects.get()
        self.assertEqual(task.assignee, self.employee)
        self.assertEqual(task.kind, Task.Kind.TEST_DRIVE)
        self.assertEqual(timezone.localtime(task.due_at).hour, 10)

    def test_director_assigns_task_to_employee(self):
        self.client.force_login(self.director)

        self.client.post(
            reverse("customer-add-task", args=[self.customer.pk]),
            {
                "title": "Qo‘ng‘iroq",
                "kind": Task.Kind.CALL,
                "due_at": "2030-01-15T10:30",
                "assignee": self.employee.pk,
            },
        )

        self.assertEqual(Task.objects.get().assignee, self.employee)

    def test_task_without_valid_due_date_is_rejected(self):
        self.client.force_login(self.employee)

        self.client.post(
            reverse("customer-add-task", args=[self.customer.pk]),
            {"title": "Qo‘ng‘iroq", "kind": Task.Kind.CALL, "due_at": "not-a-date"},
        )

        self.assertEqual(Task.objects.count(), 0)

    def test_toggle_own_task_and_overdue_flag(self):
        task = Task.objects.create(
            customer=self.customer,
            assignee=self.employee,
            title="Eski",
            due_at=timezone.now() - timedelta(days=1),
        )
        self.assertTrue(task.is_overdue)
        self.client.force_login(self.employee)

        self.client.post(reverse("task-toggle", args=[task.pk]))

        task.refresh_from_db()
        self.assertTrue(task.is_done)
        self.assertFalse(task.is_overdue)

    def test_employee_cannot_toggle_someone_elses_task(self):
        task = Task.objects.create(
            customer=self.other_customer,
            assignee=self.other,
            title="Begona",
            due_at=timezone.now(),
        )
        self.client.force_login(self.employee)

        response = self.client.post(reverse("task-toggle", args=[task.pk]))

        self.assertEqual(response.status_code, 404)
        task.refresh_from_db()
        self.assertFalse(task.is_done)

    def test_dashboard_lists_only_own_open_tasks_for_employee(self):
        Task.objects.create(
            customer=self.customer, assignee=self.employee,
            title="Mening vazifam", due_at=timezone.now(),
        )
        Task.objects.create(
            customer=self.other_customer, assignee=self.other,
            title="Boshqaning vazifasi", due_at=timezone.now(),
        )
        self.client.force_login(self.employee)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual([t.title for t in response.context["tasks"]], ["Mening vazifam"])
        self.assertEqual(response.context["open_task_count"], 1)


class InventoryTests(CrmFeatureTestBase):
    def new_car(self):
        return {
            "model_name": "Supra",
            "color": "Qizil",
            "price": "900000000",
            "status": Car.Status.IN_STOCK,
        }

    def test_employee_cannot_add_car(self):
        self.client.force_login(self.employee)

        response = self.client.post(reverse("car-add"), self.new_car())

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Car.objects.filter(model_name="Supra").exists())

    def test_director_adds_and_updates_car(self):
        self.client.force_login(self.director)

        self.client.post(reverse("car-add"), self.new_car())
        supra = Car.objects.get(model_name="Supra")
        self.client.post(
            reverse("car-update", args=[supra.pk]),
            {"price": "880000000", "status": Car.Status.RESERVED},
        )

        supra.refresh_from_db()
        self.assertEqual(supra.status, Car.Status.RESERVED)
        self.assertEqual(supra.price, 880000000)

    def test_price_input_is_not_localized(self):
        # A number input rejects "450000000,00"; the browser would show it empty
        # and saving the row would then fail.
        self.client.force_login(self.director)

        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, 'value="450000000.00"')

    def test_negative_price_is_rejected(self):
        self.client.force_login(self.director)

        self.client.post(
            reverse("car-update", args=[self.car.pk]),
            {"price": "-1", "status": Car.Status.SOLD},
        )

        self.car.refresh_from_db()
        self.assertEqual(self.car.status, Car.Status.IN_STOCK)


class DirectorChartTests(CrmFeatureTestBase):
    def test_kpi_contains_chart_rows(self):
        self.client.force_login(self.director)

        response = self.client.get(reverse("dashboard"))
        kpi = response.context["kpi"]

        stage_rows = {row["label"]: row for row in kpi["stage_chart"]}
        self.assertEqual(stage_rows["Yangi Lid"]["count"], 1)
        self.assertEqual(stage_rows["Sotildi"]["pct"], 100)
        self.assertEqual(kpi["model_chart"][0]["label"], "Camry")
        self.assertEqual(kpi["model_chart"][0]["revenue"], 450000000)
        self.assertContains(response, "Bitimlar bosqichlar bo‘yicha")


TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="crm-test-media-")


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class InvoiceTests(CrmFeatureTestBase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def test_invoice_is_created_for_contract_deal_and_downloadable(self):
        self.deal.stage = Deal.Stage.CONTRACT
        self.deal.save()
        self.client.force_login(self.employee)

        self.client.post(reverse("deal-invoice", args=[self.deal.pk]))

        document = Document.objects.get()
        self.assertEqual(document.deal, self.deal)
        self.assertEqual(document.created_by, self.employee)
        self.assertTrue(document.file.name.startswith("documents/"))
        self.assertGreater(document.size, 1000)
        response = self.client.get(reverse("document-download", args=[document.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF"))

    def test_invoice_refused_for_new_lead(self):
        self.client.force_login(self.employee)

        self.client.post(reverse("deal-invoice", args=[self.deal.pk]))

        self.assertEqual(Document.objects.count(), 0)

    def test_employee_cannot_download_foreign_document(self):
        self.client.force_login(self.director)
        self.client.post(reverse("deal-invoice", args=[self.other_deal.pk]))
        document = Document.objects.get()
        self.client.force_login(self.employee)

        response = self.client.get(reverse("document-download", args=[document.pk]))

        self.assertEqual(response.status_code, 404)

    def test_media_root_is_isolated(self):
        self.assertEqual(settings.MEDIA_ROOT, TEST_MEDIA_ROOT)


class ExcelExportTests(CrmFeatureTestBase):
    def test_employee_export_contains_only_own_deals(self):
        self.client.force_login(self.employee)

        response = self.client.get(reverse("export-excel"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response["Content-Disposition"])
        workbook = load_workbook(BytesIO(response.content))
        deal_rows = list(workbook["Bitimlar"].iter_rows(min_row=2, values_only=True))
        self.assertEqual([row[1] for row in deal_rows], ["Own Customer"])
        customer_rows = list(workbook["Mijozlar"].iter_rows(min_row=2, values_only=True))
        self.assertEqual([row[1] for row in customer_rows], ["Own Customer"])

    def test_director_export_contains_all_deals(self):
        self.client.force_login(self.director)

        response = self.client.get(reverse("export-excel"))
        workbook = load_workbook(BytesIO(response.content))

        self.assertEqual(workbook["Bitimlar"].max_row, 3)


class DataMigrationTests(CrmFeatureTestBase):
    """The move between servers is dumpdata on the old one, loaddata on the new."""

    def test_dump_and_load_keeps_users_roles_and_deals(self):
        Note.objects.create(customer=self.customer, author=self.employee, text="Izoh")
        with tempfile.TemporaryDirectory(prefix="crm-dump-") as folder:
            dump_path = f"{folder}/data.json"
            call_command(
                "dumpdata",
                "--natural-foreign",
                "--natural-primary",
                "--exclude", "contenttypes",
                "--exclude", "auth.permission",
                "--exclude", "sessions",
                "--exclude", "admin.logentry",
                output=dump_path,
                verbosity=0,
            )
            Deal.objects.all().delete()
            Customer.objects.all().delete()
            Car.objects.all().delete()
            get_user_model().objects.all().delete()

            call_command("loaddata", dump_path, verbosity=0)

        director = get_user_model().objects.get(username="director")
        self.assertEqual(director.staff_profile.role, StaffProfile.Role.DIRECTOR)
        self.assertEqual(StaffProfile.objects.count(), 3)
        self.assertEqual(Deal.objects.count(), 2)
        self.assertEqual(Note.objects.get().author.username, "employee")


class SeedActivityTests(TestCase):
    def test_seed_adds_sample_notes_and_tasks_once(self):
        call_command("seed_demo_data", verbosity=0)
        call_command("seed_demo_data", verbosity=0)

        self.assertEqual(Note.objects.count(), 4)
        self.assertEqual(Task.objects.count(), 4)
