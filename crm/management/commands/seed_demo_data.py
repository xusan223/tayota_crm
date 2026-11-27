from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from crm.models import Car, Customer, Deal, Note, Task


class Command(BaseCommand):
    help = "Toyota CRM uchun kamida 100 ta takrorlanmaydigan namunaviy mijoz yaratadi."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        manager, manager_created = User.objects.get_or_create(
            username="demo_manager",
            defaults={
                "first_name": "Demo",
                "last_name": "Menejer",
                "email": "demo.manager@example.com",
                "is_active": True,
            },
        )
        if manager_created:
            manager.set_unusable_password()
            manager.save(update_fields=["password"])

        car_specs = [
            ("Camry", "Oq", "450000000", Car.Status.IN_STOCK),
            ("RAV4", "Qora", "520000000", Car.Status.IN_STOCK),
            ("Land Cruiser Prado", "Kulrang", "850000000", Car.Status.RESERVED),
            ("Corolla Cross", "Kumush", "390000000", Car.Status.IN_STOCK),
            ("Hilux", "Ko‘k", "610000000", Car.Status.SOLD),
        ]
        cars = {}
        for model_name, color, price, status in car_specs:
            car, _ = Car.objects.get_or_create(
                model_name=model_name,
                color=color,
                defaults={"price": Decimal(price), "status": status},
            )
            cars[model_name] = car

        sample_deals = [
            ("Azizbek Karimov", "+998900000101", "Camry", Deal.Stage.NEW, "450000000"),
            ("Madina Rasulova", "+998900000102", "RAV4", Deal.Stage.CONTACTED, "520000000"),
            ("Jasur Tursunov", "+998900000103", "Land Cruiser Prado", Deal.Stage.TEST_DRIVE, "850000000"),
            ("Dilnoza Abdullayeva", "+998900000104", "Corolla Cross", Deal.Stage.CONTRACT, "390000000"),
            ("Bekzod Ismoilov", "+998900000105", "Hilux", Deal.Stage.SOLD, "610000000"),
        ]
        for name, phone, car_name, stage, total_price in sample_deals:
            customer, _ = Customer.objects.get_or_create(
                phone=phone,
                defaults={"name": name, "interested_car": cars[car_name]},
            )
            Deal.objects.get_or_create(
                customer=customer,
                manager=manager,
                defaults={"stage": stage, "total_price": Decimal(total_price)},
            )

        first_names = [
            "Aziz",
            "Madina",
            "Jasur",
            "Dilnoza",
            "Bekzod",
            "Sevara",
            "Sardor",
            "Mohira",
            "Diyor",
            "Nilufar",
        ]
        last_names = [
            "Karimov",
            "Rasulova",
            "Tursunov",
            "Abdullayeva",
            "Ismoilov",
            "Ergasheva",
            "Yusupov",
            "Qodirova",
            "Nazarov",
            "Saidova",
        ]
        car_names = list(cars)
        stages = [stage for stage, _ in Deal.Stage.choices]
        customer_count = Customer.objects.count()
        sequence = 1
        while customer_count < 100:
            first_name = first_names[(sequence - 1) % len(first_names)]
            last_name = last_names[
                ((sequence - 1) // len(first_names)) % len(last_names)
            ]
            car = cars[car_names[(sequence - 1) % len(car_names)]]
            phone = f"+99890{2000000 + sequence:07d}"
            customer, created = Customer.objects.get_or_create(
                phone=phone,
                defaults={
                    "name": f"{first_name} {last_name}",
                    "interested_car": car,
                },
            )
            Deal.objects.get_or_create(
                customer=customer,
                manager=manager,
                defaults={
                    "stage": stages[(sequence - 1) % len(stages)],
                    "total_price": car.price,
                },
            )
            if created:
                customer_count += 1
            sequence += 1

        now = timezone.now()
        sample_activity = [
            ("+998900000101", "Camry bo‘yicha narx so‘radi, katalog yuborildi.",
             Task.Kind.CALL, "Kreditsiz to‘lov variantini aytib qayta qo‘ng‘iroq qilish", 1),
            ("+998900000102", "Qo‘ng‘iroq qilindi: RAV4 qora rangda qiziqtiradi.",
             Task.Kind.TEST_DRIVE, "RAV4 test-drayviga taklif qilish", 2),
            ("+998900000103", "Test-drayv o‘tkazildi, mijoz mamnun.",
             Task.Kind.MEETING, "Shartnoma shartlarini kelishish uchun uchrashuv", 3),
            ("+998900000104", "Shartnoma imzolandi, to‘lov kutilmoqda.",
             Task.Kind.CALL, "To‘lov holatini tekshirish", -1),
        ]
        for phone, note_text, kind, title, days in sample_activity:
            customer = Customer.objects.filter(phone=phone).first()
            if customer is None:
                continue
            Note.objects.get_or_create(
                customer=customer, text=note_text, defaults={"author": manager}
            )
            Task.objects.get_or_create(
                customer=customer,
                title=title,
                defaults={
                    "assignee": manager,
                    "kind": kind,
                    "due_at": now + timedelta(days=days),
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Namunaviy ma'lumotlar tayyor: jami {customer_count} ta mijoz."
            )
        )
