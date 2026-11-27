# Toyota CRM

Toyota avtosaloni uchun mijozlar va sotuvlarni boshqarish tizimi (CRM).
Django 5.2 asosida yozilgan o'quv loyihasi, Oracle Cloud'da ishlaydi.

Jonli tizim: https://92-6-237-206.sslip.io

## Imkoniyatlar

- **Mijozlar va lidlar** — yangi mijoz qiziqqan avtomobili va bitim summasi
  bilan birga "Yangi Lid" bitimi sifatida qo'shiladi.
- **Sotuv voronkasi (Kanban)** — bitimni tugma bilan keyingi yoki oldingi
  bosqichga o'tkazish: Yangi Lid → Muloqot qilindi → Test-Drayv → Shartnoma →
  Sotildi.
- **Mijoz kartochkasi** — mijozning bitimlari, muloqot tarixi (izohlar),
  vazifalari va hujjatlari bitta sahifada.
- **Vazifalar** — qo'ng'iroq, test-drayv, uchrashuv; muddati o'tganlari
  ajratib ko'rsatiladi.
- **Invoice PDF** — "Shartnoma" va "Sotildi" bosqichidagi bitim uchun PDF
  yaratiladi va saqlanadi; yuklab olish faqat ruxsati borlarga.
- **Qidiruv** — mijozni ism yoki telefon bo'yicha topish.
- **Excel eksport** — bitimlar va mijozlar `.xlsx` faylga.
- **Avtomobillar ombori** — model, rang, narx, holat; direktor va
  administrator tahrirlaydi.
- **Direktor KPI va grafiklar** — bosqichlar bo'yicha bitimlar, modellar
  bo'yicha tushum, xodimlar bo'yicha sotuvlar, konversiya.
- **Rollar**:
  - *Xodim* — faqat o'z mijozlari, bitimlari va vazifalari bilan ishlaydi;
  - *Direktor* — hamma bitimlarni ko'radi, lidlarni taqsimlaydi, KPI;
  - *Administrator* — `/admin/` panelida foydalanuvchi va rollarni boshqaradi.

## Texnologiyalar

| Qism | Texnologiya |
| --- | --- |
| Backend | Python 3.12, Django 5.2 |
| Baza | SQLite (lokal), PostgreSQL (production) |
| Hujjatlar | ReportLab (PDF), openpyxl (Excel) |
| Server | nginx, Gunicorn, WhiteNoise |
| Bulut | Oracle Cloud Always Free: Compute, VCN, Object Storage |

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

So'ng http://127.0.0.1:8000/ (CRM) va http://127.0.0.1:8000/admin/ ni oching.
Superuser avtomatik *Administrator* rolini oladi; boshqa foydalanuvchilarga
admin panelning "Xodim rollari" bo'limida rol bering.

## Testlar

```powershell
python manage.py test
```

## Loyiha tuzilishi

```
tayota_crm/            Django sozlamalari, URL'lar, /health/ endpoint
crm/
  models.py            Car, Customer, Deal, Note, Task, Document, StaffProfile
  views.py             Sahifalar va rollarga qarab ruxsatlar
  invoices.py          Invoice PDF yaratish
  signals.py           Yangi foydalanuvchiga avtomatik rol berish
  templates/, static/  Interfeys (HTML, CSS, JS)
  tests.py, tests_features.py
deploy/oracle/         Server sozlash, HTTPS, zaxira va yangilash skriptlari
```

## Muhit o'zgaruvchilari (production)

| O'zgaruvchi | Vazifasi |
| --- | --- |
| `DJANGO_SECRET_KEY` | Maxfiy kalit (production'da majburiy) |
| `DATABASE_URL` | PostgreSQL manzili |
| `DJANGO_DEBUG` | `False` production uchun |
| `DJANGO_ALLOWED_HOSTS` | Ruxsat etilgan domenlar, vergul bilan |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | CSRF uchun ishonchli manzillar |
| `DJANGO_SERVE_HTTPS` | HTTPS yo'q bo'lsa `False` (aks holda login ishlamaydi) |
| `DJANGO_SECURE_SSL_REDIRECT` | HTTP'ni HTTPS'ga yo'naltirish |
| `DJANGO_MEDIA_ROOT` | Invoice fayllari papkasi |
| `DJANGO_S3_DOCUMENTS_BUCKET` | Ixtiyoriy: hujjatlarni S3 bucket'da saqlash |

`DJANGO_DEBUG` o'rnatilmagan bo'lsa loyiha lokal rejimda (SQLite, DEBUG=True)
ishlaydi.

## Deploy

Oracle Cloud'ga joylashtirish va yangilash: [DEPLOYMENT.md](DEPLOYMENT.md).
