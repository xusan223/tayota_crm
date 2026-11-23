# Toyota CRM

Toyota avtosaloni uchun mijozlar va sotuvlarni boshqarish tizimi (CRM).
Django 5.2 asosida yozilgan o'quv loyihasi.

## Imkoniyatlar

- **Mijozlar va lidlar** — yangi mijozni qo'shish, u qiziqqan avtomobil va
  bitim summasi bilan birga avtomatik "Yangi Lid" bitimi yaratiladi.
- **Bitim bosqichlari** — Yangi Lid → Muloqot qilindi → Test-Drayv →
  Shartnoma → Sotildi.
- **Avtomobillar ombori** — model, rang, narx va holat (Omborda, Band qilingan,
  Sotilgan).
- **Rollar**:
  - *Xodim* — o'z bitimlarini ko'radi va o'ziga lid qo'shadi;
  - *Direktor* — lidlarni menejerlarga taqsimlaydi va har bir xodimning KPI
    ko'rsatkichlarini (lidlar, sotuvlar, tushum) ko'radi;
  - *Administrator* — `/admin/` panelida foydalanuvchilar va rollarni
    boshqaradi.
- **Dashboard** — jami sotuvlar, tushum va ombordagi avtomobillar soni.
- **Namunaviy ma'lumotlar** — bitta buyruq bilan 100 ta mijoz va bitim.

## Texnologiyalar

| Qism | Texnologiya |
| --- | --- |
| Backend | Python 3.12, Django 5.2 |
| Baza | SQLite (lokal), PostgreSQL (production) |
| Server | Gunicorn, WhiteNoise (static fayllar) |
| Deploy | AWS Elastic Beanstalk + RDS PostgreSQL |

## Lokal ishga tushirish

```powershell
git clone https://github.com/xusan223/tayota_crm.git
cd tayota_crm

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo_data   # ixtiyoriy: 100 ta namunaviy mijoz
python manage.py runserver
```

So'ng brauzerda oching:

- http://127.0.0.1:8000/ — CRM (login sahifasi)
- http://127.0.0.1:8000/admin/ — administrator paneli

Superuser avtomatik ravishda *Administrator* rolini oladi. Boshqa
foydalanuvchilarni admin panelida yarating va "Xodim rollari" bo'limida
Direktor yoki Xodim rolini bering.

## Testlar

```powershell
python manage.py test
```

## Loyiha tuzilishi

```
tayota_crm/            Django sozlamalari, URL'lar, /health/ endpoint
crm/
  models.py            Car, Customer, Deal, StaffProfile
  views.py             Dashboard va rollarga qarab ruxsatlar
  signals.py           Yangi foydalanuvchiga avtomatik rol berish
  management/commands/ seed_demo_data buyrug'i
  templates/, static/  Interfeys (HTML, CSS, JS)
  tests.py             Testlar
.ebextensions/         AWS Elastic Beanstalk sozlamalari
Procfile               Gunicorn ishga tushirish buyrug'i
```

## Muhit o'zgaruvchilari (production)

| O'zgaruvchi | Vazifasi |
| --- | --- |
| `DJANGO_SECRET_KEY` | Maxfiy kalit (production'da majburiy) |
| `DATABASE_URL` | PostgreSQL manzili, masalan `postgresql://user:pass@host:5432/db` |
| `DJANGO_DEBUG` | `False` production uchun |
| `DJANGO_ALLOWED_HOSTS` | Ruxsat etilgan domenlar, vergul bilan |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | CSRF uchun ishonchli manzillar |
| `DJANGO_SERVE_HTTPS` | HTTPS bo'lmasa `False` (aks holda login ishlamaydi) |
| `DJANGO_SECURE_SSL_REDIRECT` | HTTP'ni HTTPS'ga yo'naltirish |

`DJANGO_DEBUG` o'rnatilmagan bo'lsa loyiha lokal rejimda (SQLite, DEBUG=True)
ishlaydi.

## AWS'ga deploy

Batafsil yo'riqnoma: [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md).
