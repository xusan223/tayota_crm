from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Car, Customer, Deal, StaffProfile


class DashboardTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            username="manager", password="test-password"
        )
        self.client.force_login(self.manager)
        self.car = Car.objects.create(
            model_name="Camry",
            color="Oq",
            price="350000000",
            status=Car.Status.IN_STOCK,
        )

    def test_dashboard_renders_stats_and_sections(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "crm/index.html")
        self.assertContains(response, "Sotuv voronkasi")
        self.assertContains(response, "Camry")
        self.assertContains(response, "crm/css/app.css")
        self.assertContains(response, "crm/js/app.js?v=2")
        self.assertEqual(response.context["cars_in_stock"], 1)

    def test_dashboard_requires_login(self):
        self.client.logout()

        response = self.client.get(reverse("dashboard"))

        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('dashboard')}"
        )

    def test_employee_only_sees_and_owns_assigned_deals(self):
        other_employee = get_user_model().objects.create_user(username="other-employee")
        customer = Customer.objects.create(
            name="Other employee customer",
            phone="+998900000999",
            interested_car=self.car,
        )
        Deal.objects.create(
            customer=customer,
            manager=other_employee,
            stage=Deal.Stage.NEW,
            total_price="1000",
        )

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.context["total_leads"], 0)
        self.assertNotContains(response, "Other employee customer")
        self.assertNotIn("kpi", response.context)
        self.assertNotContains(response, "KPI ko‘rsatkichlari")

    def test_employee_cannot_assign_new_lead_to_another_employee(self):
        other_employee = get_user_model().objects.create_user(username="other-employee")

        self.client.post(
            reverse("dashboard"),
            {
                "name": "My lead",
                "phone": "+998900000998",
                "interested_car": self.car.pk,
                "manager": other_employee.pk,
                "total_price": "1000",
            },
        )

        self.assertEqual(Deal.objects.get().manager, self.manager)

    def test_demo_seed_command_is_safe_to_run_more_than_once(self):
        call_command("seed_demo_data", verbosity=0)
        call_command("seed_demo_data", verbosity=0)

        self.assertEqual(Car.objects.count(), 5)
        self.assertGreaterEqual(Customer.objects.count(), 100)
        self.assertGreaterEqual(Deal.objects.count(), 100)
        self.assertEqual(Customer.objects.values("phone").distinct().count(), 100)

    def test_post_creates_customer_and_new_deal(self):
        response = self.client.post(
            reverse("dashboard"),
            {
                "name": "Ali Valiyev",
                "phone": "+998901234567",
                "interested_car": self.car.pk,
                "manager": self.manager.pk,
                "total_price": "350000000",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        customer = Customer.objects.get(phone="+998901234567")
        deal = Deal.objects.get(customer=customer)
        self.assertEqual(customer.interested_car, self.car)
        self.assertEqual(deal.manager, self.manager)
        self.assertEqual(deal.stage, Deal.Stage.NEW)
        self.assertContains(self.client.get(reverse("dashboard")), "Ali Valiyev")

    def test_post_rejects_missing_customer_details(self):
        response = self.client.post(
            reverse("dashboard"),
            {
                "name": "",
                "phone": "",
                "manager": self.manager.pk,
                "total_price": "1000",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(Customer.objects.count(), 0)
        self.assertEqual(Deal.objects.count(), 0)


class AuthenticationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="login-user", password="safe-test-password"
        )

    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "crm/login.html")
        self.assertContains(response, "Tizimga kirish")

    def test_valid_credentials_open_dashboard(self):
        response = self.client.post(
            reverse("login"),
            {"username": "login-user", "password": "safe-test-password"},
        )

        self.assertRedirects(response, reverse("dashboard"))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_invalid_credentials_show_error(self):
        response = self.client.post(
            reverse("login"),
            {"username": "login-user", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())

    def test_logout_ends_session(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("login"))
        dashboard_response = self.client.get(reverse("dashboard"))
        self.assertRedirects(
            dashboard_response, f"{reverse('login')}?next={reverse('dashboard')}"
        )

    def test_health_check_reports_database_ready(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class StaffRoleTests(TestCase):
    def setUp(self):
        self.employee = get_user_model().objects.create_user(username="employee")
        self.director = get_user_model().objects.create_user(username="director")
        self.director.staff_profile.role = StaffProfile.Role.DIRECTOR
        self.director.staff_profile.save()
        self.car = Car.objects.create(
            model_name="RAV4",
            color="Qora",
            price="520000000",
            status=Car.Status.IN_STOCK,
        )
        customer = Customer.objects.create(
            name="Employee customer",
            phone="+998900000997",
            interested_car=self.car,
        )
        Deal.objects.create(
            customer=customer,
            manager=self.employee,
            stage=Deal.Stage.SOLD,
            total_price="520000000",
        )

    def test_director_sees_all_sales_and_can_assign_deals(self):
        self.client.force_login(self.director)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.context["role_label"], "Direktor")
        self.assertTrue(response.context["can_assign_deals"])
        self.assertEqual(response.context["total_leads"], 1)
        self.assertEqual(response.context["total_sales"], 1)
        self.assertEqual(response.context["kpi"]["lead_count"], 1)
        self.assertEqual(response.context["kpi"]["sales_count"], 1)
        self.assertEqual(response.context["kpi"]["active_deals"], 0)
        self.assertEqual(response.context["kpi"]["conversion_rate"], 100)
        self.assertEqual(response.context["kpi"]["revenue"], 520000000)
        self.assertEqual(response.context["kpi"]["staff"][0]["sales_count"], 1)
        self.assertContains(response, "KPI ko‘rsatkichlari")
        self.assertContains(response, "Xodimlar kesimida KPI")

    def test_director_kpi_handles_no_deals(self):
        Deal.objects.all().delete()
        self.client.force_login(self.director)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.context["kpi"]["conversion_rate"], 0)
        self.assertEqual(response.context["kpi"]["average_sale"], 0)
        self.assertEqual(response.context["kpi"]["revenue"], 0)

    def test_administrator_does_not_receive_director_kpi(self):
        administrator = get_user_model().objects.create_user(
            username="administrator"
        )
        administrator.staff_profile.role = StaffProfile.Role.ADMINISTRATOR
        administrator.staff_profile.save()
        self.client.force_login(administrator)

        response = self.client.get(reverse("dashboard"))

        self.assertNotIn("kpi", response.context)
        self.assertNotContains(response, "KPI ko‘rsatkichlari")

    def test_administrator_role_enables_admin_site(self):
        administrator = get_user_model().objects.create_user(
            username="administrator"
        )
        administrator.staff_profile.role = StaffProfile.Role.ADMINISTRATOR
        administrator.staff_profile.save()
        self.client.force_login(administrator)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
