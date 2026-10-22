from decimal import Decimal
from io import BytesIO

from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from sales.models import Sale


BACKGROUND_COLOR = colors.HexColor("#EEEEEE")
CARD_COLOR = colors.HexColor("#FFFFFF")
TEXT_COLOR = colors.HexColor("#171717")
SECONDARY_TEXT_COLOR = colors.HexColor("#777777")
BORDER_COLOR = colors.HexColor("#D5D5D5")
SUMMARY_COLOR = colors.HexColor("#F7F7F7")
SUCCESS_COLOR = colors.HexColor("#63C623")
PRIMARY_COLOR = colors.HexColor("#064A57")


def format_money(value):
    value = Decimal(value or "0.00")
    return f"Q{value:,.2f}"


def format_quantity(value):
    value = Decimal(value or "0")

    if value == value.to_integral_value():
        return str(int(value))

    return format(value.normalize(), "f")


def get_payment_method_label(method):
    methods = {
        "CASH": "Efectivo",
        "CARD": "Tarjeta",
        "TRANSFER": "Transferencia",
    }

    return methods.get(method, method)


def get_sale_payment_method(sale):
    payments = list(sale.payments.all())

    if not payments:
        return "Sin pago"

    if len(payments) > 1:
        return "Pago mixto"

    return get_payment_method_label(payments[0].method)


def draw_centered_text(pdf, text, y, font="Helvetica", size=9, color=TEXT_COLOR):
    pdf.setFont(font, size)
    pdf.setFillColor(color)
    pdf.drawCentredString(PAGE_WIDTH / 2, y, text)


def draw_check_icon(pdf, center_x, center_y):
    radius = 8 * mm

    pdf.setFillColor(SUCCESS_COLOR)
    pdf.circle(center_x, center_y, radius, fill=1, stroke=0)

    pdf.setStrokeColor(colors.white)
    pdf.setLineWidth(2.2)

    pdf.line(
        center_x - 3.5 * mm,
        center_y,
        center_x - 0.8 * mm,
        center_y - 3 * mm,
    )

    pdf.line(
        center_x - 0.8 * mm,
        center_y - 3 * mm,
        center_x + 4.5 * mm,
        center_y + 3.2 * mm,
    )


def build_sale_receipt_pdf(sale):
    global PAGE_WIDTH

    items = list(sale.items.all())

    PAGE_WIDTH = 105 * mm

    base_height = 150 * mm
    item_height = 17 * mm
    extra_items_height = max(len(items) - 3, 0) * item_height
    page_height = base_height + extra_items_height

    buffer = BytesIO()

    pdf = canvas.Canvas(
        buffer,
        pagesize=(PAGE_WIDTH, page_height),
    )

    pdf.setTitle(f"Comprobante {sale.sale_number}")
    pdf.setAuthor("SellSys")

    pdf.setFillColor(BACKGROUND_COLOR)
    pdf.rect(
        0,
        0,
        PAGE_WIDTH,
        page_height,
        fill=1,
        stroke=0,
    )

    margin = 5 * mm
    card_x = margin
    card_y = margin
    card_width = PAGE_WIDTH - (margin * 2)
    card_height = page_height - (margin * 2)

    pdf.setFillColor(CARD_COLOR)

    pdf.roundRect(
        card_x,
        card_y,
        card_width,
        card_height,
        5 * mm,
        fill=1,
        stroke=0,
    )

    y = page_height - 16 * mm

    draw_check_icon(
        pdf,
        PAGE_WIDTH / 2,
        y,
    )

    y -= 17 * mm

    draw_centered_text(
        pdf,
        "Pago exitoso",
        y,
        font="Helvetica-Bold",
        size=15,
    )

    y -= 8 * mm

    pdf.setFont(
        "Helvetica",
        8.5,
    )

    pdf.setFillColor(
        SECONDARY_TEXT_COLOR
    )

    sale_label = "Venta N.º: "

    sale_label_width = pdf.stringWidth(
        sale_label,
        "Helvetica",
        8.5,
    )

    sale_number_width = pdf.stringWidth(
        sale.sale_number,
        "Helvetica-Bold",
        8.5,
    )

    total_width = sale_label_width + sale_number_width
    start_x = (PAGE_WIDTH - total_width) / 2

    pdf.drawString(
        start_x,
        y,
        sale_label,
    )

    pdf.setFont(
        "Helvetica-Bold",
        8.5,
    )

    pdf.setFillColor(
        PRIMARY_COLOR
    )

    pdf.drawString(
        start_x + sale_label_width,
        y,
        sale.sale_number,
    )

    y -= 6 * mm

    completed_at = sale.completed_at or sale.created_at

    if completed_at:
        completed_at = timezone.localtime(completed_at)
        date_text = completed_at.strftime("%d/%m/%Y %H:%M")
    else:
        date_text = ""

    draw_centered_text(
        pdf,
        f"Fecha: {date_text}",
        y,
        size=8.5,
        color=SECONDARY_TEXT_COLOR,
    )

    y -= 12 * mm

    notch_radius = 4 * mm

    pdf.setFillColor(BACKGROUND_COLOR)

    pdf.circle(
        card_x,
        y,
        notch_radius,
        fill=1,
        stroke=0,
    )

    pdf.circle(
        card_x + card_width,
        y,
        notch_radius,
        fill=1,
        stroke=0,
    )

    pdf.setStrokeColor(
        BORDER_COLOR
    )

    pdf.setLineWidth(
        0.7
    )

    pdf.setDash(
        4,
        5,
    )

    pdf.line(
        card_x + 6 * mm,
        y,
        card_x + card_width - 6 * mm,
        y,
    )

    pdf.setDash()

    y -= 12 * mm

    left = card_x + 13 * mm
    item_x = card_x + 25 * mm
    price_x = card_x + card_width - 13 * mm

    pdf.setFillColor(
        TEXT_COLOR
    )

    pdf.setFont(
        "Helvetica-Bold",
        8,
    )

    pdf.drawString(
        left,
        y,
        "N.º",
    )

    pdf.drawString(
        item_x,
        y,
        "Artículo",
    )

    pdf.drawRightString(
        price_x,
        y,
        "Precio",
    )

    y -= 10 * mm

    for index, item in enumerate(items, start=1):
        pdf.setFillColor(TEXT_COLOR)

        pdf.setFont(
            "Helvetica",
            8.5,
        )

        pdf.drawString(
            left,
            y,
            str(index),
        )

        product_name = item.product_name

        if len(product_name) > 34:
            product_name = f"{product_name[:31]}..."

        pdf.setFont(
            "Helvetica-Bold",
            8.5,
        )

        pdf.drawString(
            item_x,
            y,
            product_name,
        )

        pdf.drawRightString(
            price_x,
            y,
            format_money(item.line_total),
        )

        y -= 5.5 * mm

        detail_text = (
            f"{format_quantity(item.quantity)} x "
            f"{format_money(item.unit_price)}"
        )

        if Decimal(item.discount_amount or "0.00") > Decimal("0.00"):
            detail_text += f" · Desc. {item.discount_percent}%"

        pdf.setFillColor(
            colors.HexColor("#A0A0A0")
        )

        pdf.setFont(
            "Helvetica",
            7.5,
        )

        pdf.drawString(
            item_x,
            y,
            detail_text,
        )

        y -= 10 * mm

    y -= 2 * mm

    summary_height = 39 * mm
    summary_x = card_x + 9 * mm
    summary_width = card_width - 18 * mm
    summary_y = card_y + 9 * mm

    pdf.setFillColor(
        SUMMARY_COLOR
    )

    pdf.roundRect(
        summary_x,
        summary_y,
        summary_width,
        summary_height,
        4 * mm,
        fill=1,
        stroke=0,
    )

    summary_left = summary_x + 6 * mm
    summary_right = summary_x + summary_width - 6 * mm
    summary_top = summary_y + summary_height - 9 * mm

    pdf.setFillColor(
        TEXT_COLOR
    )

    pdf.setFont(
        "Helvetica-Bold",
        12,
    )

    pdf.drawString(
        summary_left,
        summary_top,
        "Total",
    )

    pdf.setFont(
        "Helvetica-Bold",
        12,
    )

    pdf.drawRightString(
        summary_right,
        summary_top,
        format_money(sale.total),
    )

    row_y = summary_top - 10 * mm

    pdf.setFillColor(
        SECONDARY_TEXT_COLOR
    )

    pdf.setFont(
        "Helvetica",
        8,
    )

    pdf.drawString(
        summary_left,
        row_y,
        "Método de pago",
    )

    pdf.drawRightString(
        summary_right,
        row_y,
        get_sale_payment_method(sale),
    )

    row_y -= 6.5 * mm

    pdf.drawString(
        summary_left,
        row_y,
        "Descuento",
    )

    pdf.drawRightString(
        summary_right,
        row_y,
        format_money(sale.discount_total),
    )

    row_y -= 6.5 * mm

    pdf.drawString(
        summary_left,
        row_y,
        "Cambio",
    )

    pdf.drawRightString(
        summary_right,
        row_y,
        format_money(sale.change_amount),
    )

    pdf.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes