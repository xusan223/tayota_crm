# Oracle Cloud'ga joylashtirish

Toyota CRM Oracle Cloud Infrastructure (OCI) **Always Free** resurslarida
ishlaydi: bitta server, uning ichida ilova va baza.

```
Brauzer ──HTTPS──▶ nginx ──▶ Gunicorn ──▶ Django ──▶ PostgreSQL (shu serverda)
                                              │
                                              └──▶ /var/lib/tayota-crm/media (invoice PDF)

Har kecha 02:00 (Toshkent): pg_dump + media arxivi ──▶ serverda 14 kun
                                                  └──▶ Object Storage, 30 kun
```

## Hozirgi joylashuv

| Qism | Qiymat |
| --- | --- |
| Region | Germany Central (Frankfurt), `eu-frankfurt-1` |
| Compartment | `tayota-crm` (akkauntdagi boshqa loyihalardan ajratilgan) |
| Server | `VM.Standard.E2.1.Micro` (Always Free), Ubuntu 24.04, 1 GB RAM + 2 GB swap |
| Manzil | https://92-6-237-206.sslip.io (public IP `92.6.237.206`) |
| Tarmoq | VCN `tayota-vcn` 10.20.0.0/16, public subnet, internet gateway |
| Firewall | Security list: 80 va 443 hamma uchun, 22 faqat admin IP'sidan; serverda iptables |
| HTTPS | Let's Encrypt (`certbot`, avtomatik yangilanadi), HSTS, secure cookie |
| Baza | PostgreSQL 16, faqat unix socket, peer autentifikatsiya (parolsiz) |
| Zaxira | `tayota-backup.timer` → serverda 14 kun + bucket `tayota-crm-backups`, 30 kun |

`sslip.io` IP manzilni nomga aylantiradi (`92-6-237-206.sslip.io` →
`92.6.237.206`), shuning uchun domen sotib olmasdan HTTPS sertifikat olinadi.

## Yangi server sozlash

Ubuntu 24.04 server yarating, SSH orqali kiring va:

```bash
git clone --depth 1 https://github.com/xusan223/tayota_crm.git /tmp/tayota-src
sudo bash /tmp/tayota-src/deploy/oracle/setup.sh <ip-chiziqcha-bilan>.sslip.io
sudo bash /srv/tayota_crm/deploy/oracle/enable-https.sh <ip-chiziqcha-bilan>.sslip.io
sudo tayota-manage createsuperuser
```

`setup.sh` paketlarni o'rnatadi, firewall'ni ochadi, bazani, `crm`
foydalanuvchisini, nginx va systemd servislarini sozlaydi. Uni qayta ishga
tushirish xavfsiz: sozlamalar va ma'lumotlar saqlanadi.

## O'z domenini ulash

Registrator panelida domen uchun A yozuvlarini server IP'siga yo'naltiring
(`@` va `www` → `92.6.237.206`). DNS tarqalgach:

```bash
sudo bash /srv/tayota_crm/deploy/oracle/set-domain.sh husanprogrammer.uz www.husanprogrammer.uz 92-6-237-206.sslip.io
```

Skript har bir nom shu serverga ko'rsatishini tekshiradi, Django va nginx
sozlamalarini yangilaydi va hamma nomlar uchun bitta Let's Encrypt
sertifikat oladi.

## Kodni yangilash

```bash
sudo bash /srv/tayota_crm/deploy/oracle/update.sh
```

GitHub'dan oxirgi kodni oladi, kutubxonalarni o'rnatadi, migratsiya va
`collectstatic` qiladi, servisni qayta ishga tushiradi.

## Foydali buyruqlar

```bash
sudo tayota-manage <buyruq>          # masalan: createsuperuser, shell
sudo journalctl -u tayota-crm -f     # ilova loglari
sudo systemctl status tayota-crm     # servis holati
sudo tayota-backup                   # zaxira nusxani hozir olish
curl https://<server>/health/        # {"status": "ok"}
```

## Zaxiradan tiklash

```bash
gunzip -c /var/lib/tayota-crm/backups/db-<sana>.sql.gz | sudo -u crm psql tayotacrm
sudo tar -xzf /var/lib/tayota-crm/backups/media-<sana>.tar.gz -C /var/lib/tayota-crm
```

## Sozlamalar

`/etc/tayota-crm.env` (root:crm, 0640): maxfiy kalit, baza manzili,
ruxsat etilgan host, HTTPS bayroqlari va Object Storage'ga yozish havolasi
(`BACKUP_PAR_URL`, 2027-11-27 gacha amal qiladi — keyin yangisini yarating).
