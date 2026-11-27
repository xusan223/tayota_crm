"""Invoice PDF generation for deals."""

from decimal import Decimal
from io import BytesIO

from django.utils import timezone
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

TOYOTA_RED = HexColor("#EB0A1E")
INK = HexColor("#111111")
MUTED = HexColor("#64748B")
RULE = HexColor("#E2E8F0")


def format_sum(amount):
    value = int(Decimal(amount).quantize(Decimal("1")))
    return f"{value:,}".replace(",", " ") + " so‘m"


def invoice_number(deal):
    return f"{deal.pk:05d}"


def build_invoice_pdf(deal, issued_by):
    """Return the invoice for ``deal`` as PDF bytes."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    left, right = 56, width - 56
    issued_at = timezone.localtime()
    number = invoice_number(deal)

    pdf.setTitle(f"Invoice #{number} — {deal.customer.name}")
    pdf.setAuthor("Toyota CRM")

    # Header band
    pdf.setFillColor(INK)
    pdf.rect(0, height - 120, width, 120, stroke=0, fill=1)
    pdf.setFillColor(TOYOTA_RED)
    pdf.roundRect(left, height - 88, 40, 40, 8, stroke=0, fill=1)
    pdf.setFillColor(HexColor("#FFFFFF"))
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawCentredString(left + 20, height - 76, "T")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(left + 56, height - 66, "TOYOTA")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(left + 56, height - 82, "Dilerlik markazi · CRM")
    pdf.setFont("Helvetica-Bold", 26)
    pdf.drawRightString(right, height - 70, "INVOICE")
    pdf.setFont("Helvetica", 11)
    pdf.drawRightString(right, height - 88, f"#{number}")

    # Parties
    y = height - 170
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(left, y, "MIJOZ")
    pdf.drawString(width / 2, y, "HUJJAT")
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(left, y - 20, deal.customer.name)
    pdf.setFont("Helvetica", 11)
    pdf.drawString(left, y - 38, deal.customer.phone)
    manager = deal.manager.get_full_name() or deal.manager.username
    pdf.drawString(width / 2, y - 20, f"Sana: {issued_at:%d.%m.%Y %H:%M}")
    pdf.drawString(width / 2, y - 38, f"Menejer: {manager}")
    pdf.drawString(width / 2, y - 56, f"Bitim bosqichi: {deal.get_stage_display()}")

    # Line items
    y -= 110
    pdf.setFillColor(HexColor("#F1F5F9"))
    pdf.rect(left, y - 8, right - left, 28, stroke=0, fill=1)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(left + 12, y + 2, "AVTOMOBIL")
    pdf.drawString(left + 260, y + 2, "RANG")
    pdf.drawRightString(right - 12, y + 2, "SUMMA")

    car = deal.customer.interested_car
    y -= 34
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica", 11)
    pdf.drawString(left + 12, y, f"Toyota {car.model_name}" if car else "Avtomobil tanlanmagan")
    pdf.drawString(left + 260, y, car.color if car else "—")
    pdf.drawRightString(right - 12, y, format_sum(deal.total_price))
    pdf.setStrokeColor(RULE)
    pdf.line(left, y - 14, right, y - 14)

    y -= 50
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(left + 260, y, "Jami to‘lov:")
    pdf.setFillColor(TOYOTA_RED)
    pdf.drawRightString(right - 12, y, format_sum(deal.total_price))

    # Footer
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 9)
    issuer = issued_by.get_full_name() or issued_by.username
    pdf.drawString(left, 72, f"Hujjat Toyota CRM tizimida yaratildi · {issuer}")
    pdf.drawString(left, 58, "Ushbu invoice bitim summasini tasdiqlaydi va to‘lov uchun asos hisoblanadi.")

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
