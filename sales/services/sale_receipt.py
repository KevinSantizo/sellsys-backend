from decimal import Decimal
from io import BytesIO
from urllib.request import urlopen

from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from sales.models import Sale


BACKGROUND_COLOR = colors.HexColor("#EEEEEE")
CARD_COLOR = colors.HexColor("#FFFFFF")
TEXT_COLOR = colors.HexColor("#171717")
SECONDARY_TEXT_COLOR = colors.HexColor("#777777")
BORDER_COLOR = colors.HexColor("#D5D5D5")
SUMMARY_COLOR = colors.HexColor("#F7F7F7")


def format_money(value):
    value = Decimal(value or "0.00")

    return f"Q{value:,.2f}"


def format_quantity(value):
    value = Decimal(value or "0")

    if value == value.to_integral_value():
        return str(int(value))

    return format(
        value.normalize(),
        "f",
    )


def get_payment_method_label(method):
    methods = {
        "CASH": "Efectivo",
        "CARD": "Tarjeta",
        "TRANSFER": "Transferencia",
    }

    return methods.get(
        method,
        method,
    )


def get_sale_payment_method(sale):
    payments = list(
        sale.payments.all()
    )

    if not payments:
        return "Sin pago"

    if len(payments) > 1:
        return "Pago mixto"

    return get_payment_method_label(
        payments[0].method
    )


def draw_notches_and_separator(
    pdf,
    card_x,
    card_width,
    y,
):
    notch_radius = 4 * mm

    pdf.setFillColor(
        BACKGROUND_COLOR
    )

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


def draw_logo(
    pdf,
    image_url,
    center_x,
    top_y,
    width=28 * mm,
):
    if not image_url:
        print(
            "[RECEIPT] No existe company.logo_url"
        )

        return False

    try:
        print(
            f"[RECEIPT] Descargando logo: {image_url}"
        )

        response = urlopen(
            image_url,
            timeout=10,
        )

        image_data = response.read()

        image_bytes = BytesIO(
            image_data
        )

        image = ImageReader(
            image_bytes
        )

        image_width, image_height = (
            image.getSize()
        )

        aspect_ratio = (
            image_height
            / image_width
        )

        height = (
            width
            * aspect_ratio
        )

        draw_x = (
            center_x
            - width / 2
        )

        draw_y = (
            top_y
            - height
        )

        pdf.drawImage(
            image,
            draw_x,
            draw_y,
            width=width,
            height=height,
            preserveAspectRatio=True,
            mask="auto",
        )

        print(
            "[RECEIPT] Logo dibujado correctamente"
        )

        return height

    except Exception as exc:
        print(
            "[RECEIPT] ERROR cargando logo:",
            repr(exc),
        )

        return False


def build_sale_receipt_pdf(
    sale: Sale,
):
    items = list(
        sale.items.all()
    )

    company = sale.company
    branch = sale.branch

    # =========================
    # DATOS DE EMPRESA
    # =========================

    company_name = (
        company.name
        or "Tienda"
    )

    company_legal_name = (
        company.legal_name
        or ""
    )

    company_tax_identifier = (
        company.tax_identifier
        or ""
    )

    company_logo_url = (
        company.logo_url
        or ""
    )

    branch_name = (
        branch.name
        or ""
    )

    branch_code = (
        branch.code
        or ""
    )

    branch_address = (
        branch.address
        or ""
    )

    branch_phone = (
        branch.phone
        or ""
    )

    # =========================
    # DIMENSIONES
    # =========================

    page_width = (
        105 * mm
    )

    # Más alto para darle aire
    # al logo y al encabezado.
    base_height = (
        180 * mm
    )

    item_height = (
        15 * mm
    )

    extra_items_height = (
        max(
            len(items) - 1,
            0,
        )
        * item_height
    )

    page_height = (
        base_height
        + extra_items_height
    )

    buffer = BytesIO()

    pdf = canvas.Canvas(
        buffer,
        pagesize=(
            page_width,
            page_height,
        ),
    )

    pdf.setTitle(
        f"Comprobante {sale.sale_number}"
    )

    pdf.setAuthor(
        "SellSys"
    )

    # =========================
    # FONDO
    # =========================

    pdf.setFillColor(
        BACKGROUND_COLOR
    )

    pdf.rect(
        0,
        0,
        page_width,
        page_height,
        fill=1,
        stroke=0,
    )

    # =========================
    # TARJETA
    # =========================

    margin = (
        5 * mm
    )

    card_x = (
        margin
    )

    card_y = (
        margin
    )

    card_width = (
        page_width
        - margin * 2
    )

    card_height = (
        page_height
        - margin * 2
    )

    pdf.setFillColor(
        CARD_COLOR
    )

    pdf.roundRect(
        card_x,
        card_y,
        card_width,
        card_height,
        5 * mm,
        fill=1,
        stroke=0,
    )

    left = (
        card_x
        + 10 * mm
    )

    right = (
        card_x
        + card_width
        - 10 * mm
    )

    # =========================
    # LOGO
    # =========================

    logo_top_y = (
            page_height
            - 10 * mm
    )

    logo_height = draw_logo(
        pdf,
        company_logo_url,
        page_width / 2,
        logo_top_y,
        width=24 * mm,
    )
    if logo_height:
        y = (
                logo_top_y
                - logo_height
                - 6 * mm
        )
    else:
        y = (
                page_height
                - 16 * mm
        )

    # =========================
    # HEADER
    # =========================

    pdf.setFillColor(
        TEXT_COLOR
    )

    pdf.setFont(
        "Helvetica-Bold",
        11,
    )

    pdf.drawString(
        left,
        y,
        company_name,
    )

    pdf.setFillColor(
        SECONDARY_TEXT_COLOR
    )

    pdf.setFont(
        "Helvetica",
        6.8,
    )

    pdf.drawRightString(
        right,
        y + 1,
        "Recibo",
    )

    pdf.setFont(
        "Helvetica-Bold",
        6.2,
    )

    pdf.drawRightString(
        right,
        y - 3 * mm,
        sale.sale_number,
    )

    completed_at = (
        sale.completed_at
        or sale.created_at
    )

    if completed_at:
        completed_at = (
            timezone.localtime(
                completed_at
            )
        )

        date_text = (
            completed_at.strftime(
                "%d/%m/%Y %H:%M"
            )
        )

    else:
        date_text = ""

    pdf.setFont(
        "Helvetica",
        6.8,
    )

    pdf.setFillColor(
        SECONDARY_TEXT_COLOR
    )

    pdf.drawRightString(
        right,
        y - 6 * mm,
        date_text,
    )

    y -= (
        6 * mm
    )

    # =========================
    # RAZÓN SOCIAL
    # =========================

    if company_legal_name:
        pdf.setFont(
            "Helvetica",
            7.2,
        )

        pdf.setFillColor(
            SECONDARY_TEXT_COLOR
        )

        pdf.drawString(
            left,
            y,
            company_legal_name,
        )

        y -= (
            3.8 * mm
        )

    # =========================
    # SUCURSAL
    # =========================

    if branch_name:
        branch_label = (
            f"Sucursal: {branch_name}"
        )

        if branch.is_main:
            branch_label += (
                " · Principal"
            )

        pdf.setFont(
            "Helvetica",
            7.2,
        )

        pdf.setFillColor(
            SECONDARY_TEXT_COLOR
        )

        pdf.drawString(
            left,
            y,
            branch_label,
        )

        y -= (
            3.8 * mm
        )

    # =========================
    # CÓDIGO
    # =========================

    if branch_code:
        pdf.drawString(
            left,
            y,
            f"Código: {branch_code}",
        )

        y -= (
            3.8 * mm
        )

    # =========================
    # DIRECCIÓN
    # =========================

    if branch_address:
        address = str(
            branch_address
        )

        if len(address) > 58:
            address = (
                address[:55]
                + "..."
            )

        pdf.drawString(
            left,
            y,
            address,
        )

        y -= (
            3.8 * mm
        )

    # =========================
    # NIT / TELÉFONO
    # =========================

    store_info = []

    if company_tax_identifier:
        store_info.append(
            f"NIT: {company_tax_identifier}"
        )

    if branch_phone:
        store_info.append(
            f"Tel: {branch_phone}"
        )

    if store_info:
        pdf.drawString(
            left,
            y,
            " · ".join(
                store_info
            ),
        )

        y -= (
            7 * mm
        )

    else:
        y -= (
            3 * mm
        )

    # =========================
    # MENSAJE
    # =========================

    pdf.setFillColor(
        TEXT_COLOR
    )

    pdf.setFont(
        "Helvetica-Bold",
        12,
    )

    pdf.drawString(
        left,
        y,
        "¡Gracias por su compra!",
    )

    y -= (
        6.5 * mm
    )

    # =========================
    # CLIENTE
    # =========================

    pdf.setFont(
        "Helvetica",
        8,
    )

    pdf.setFillColor(
        SECONDARY_TEXT_COLOR
    )

    customer_name = (
        sale.customer_name
        or "Consumidor final"
    )

    pdf.drawString(
        left,
        y,
        f"Cliente: {customer_name}",
    )

    y -= (
        4.2 * mm
    )

    customer_tax_id = (
        sale.customer_tax_id
        or "CF"
    )

    pdf.drawString(
        left,
        y,
        f"NIT: {customer_tax_id}",
    )

    y -= (
        7 * mm
    )

    # =========================
    # SEPARADOR
    # =========================

    draw_notches_and_separator(
        pdf,
        card_x,
        card_width,
        y,
    )

    y -= (
        9 * mm
    )

    # =========================
    # CABECERA ITEMS
    # =========================

    number_x = (
        card_x
        + 10 * mm
    )

    item_x = (
        card_x
        + 20 * mm
    )

    price_x = (
        card_x
        + card_width
        - 10 * mm
    )

    pdf.setFillColor(
        TEXT_COLOR
    )

    pdf.setFont(
        "Helvetica-Bold",
        8,
    )

    pdf.drawString(
        number_x,
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
        "Total",
    )

    y -= (
        7.5 * mm
    )

    # =========================
    # PRODUCTOS
    # =========================

    for index, item in enumerate(
        items,
        start=1,
    ):
        pdf.setFillColor(
            TEXT_COLOR
        )

        pdf.setFont(
            "Helvetica",
            8,
        )

        pdf.drawString(
            number_x,
            y,
            str(index),
        )

        product_name = (
            item.product_name
            or ""
        )

        if len(product_name) > 30:
            product_name = (
                product_name[:27]
                + "..."
            )

        pdf.setFont(
            "Helvetica-Bold",
            8.3,
        )

        pdf.drawString(
            item_x,
            y,
            product_name,
        )

        pdf.drawRightString(
            price_x,
            y,
            format_money(
                item.line_total
            ),
        )

        y -= (
            4.5 * mm
        )

        # =========================
        # SKU
        # =========================

        if item.product_sku:
            pdf.setFont(
                "Helvetica",
                7,
            )

            pdf.setFillColor(
                SECONDARY_TEXT_COLOR
            )

            pdf.drawString(
                item_x,
                y,
                f"SKU: {item.product_sku}",
            )

            y -= (
                4.5 * mm
            )

        detail_text = (
            f"{format_quantity(item.quantity)} x "
            f"{format_money(item.unit_price)}"
        )

        discount_amount = Decimal(
            item.discount_amount
            or "0.00"
        )

        if (
            discount_amount
            > Decimal("0.00")
        ):
            detail_text += (
                f" · Desc. "
                f"{format_quantity(item.discount_percent)}%"
            )

        pdf.setFont(
            "Helvetica",
            7.3,
        )

        pdf.setFillColor(
            SECONDARY_TEXT_COLOR
        )

        pdf.drawString(
            item_x,
            y,
            detail_text,
        )

        y -= (
            8.5 * mm
        )

    # =========================
    # RESUMEN
    # =========================

    y += (
        1 * mm
    )

    summary_height = (
        37 * mm
    )

    summary_x = (
        card_x
        + 8 * mm
    )

    summary_width = (
        card_width
        - 16 * mm
    )

    summary_y = (
        y
        - summary_height
        + 5 * mm
    )

    pdf.setFillColor(
        SUMMARY_COLOR
    )

    pdf.roundRect(
        summary_x,
        summary_y,
        summary_width,
        summary_height,
        3 * mm,
        fill=1,
        stroke=0,
    )

    summary_left = (
        summary_x
        + 6 * mm
    )

    summary_right = (
        summary_x
        + summary_width
        - 6 * mm
    )

    summary_top = (
        summary_y
        + summary_height
        - 8 * mm
    )

    # =========================
    # TOTAL
    # =========================

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

    pdf.drawRightString(
        summary_right,
        summary_top,
        format_money(
            sale.total
        ),
    )

    row_y = (
        summary_top
        - 8.5 * mm
    )

    pdf.setFillColor(
        SECONDARY_TEXT_COLOR
    )

    pdf.setFont(
        "Helvetica",
        8,
    )

    # =========================
    # MÉTODO DE PAGO
    # =========================

    pdf.drawString(
        summary_left,
        row_y,
        "Método de pago",
    )

    pdf.drawRightString(
        summary_right,
        row_y,
        get_sale_payment_method(
            sale
        ),
    )

    row_y -= (
        6 * mm
    )

    # =========================
    # SUBTOTAL
    # =========================

    pdf.drawString(
        summary_left,
        row_y,
        "Subtotal",
    )

    pdf.drawRightString(
        summary_right,
        row_y,
        format_money(
            sale.subtotal
        ),
    )

    row_y -= (
        6 * mm
    )

    # =========================
    # DESCUENTO
    # =========================

    pdf.drawString(
        summary_left,
        row_y,
        "Descuento",
    )

    pdf.drawRightString(
        summary_right,
        row_y,
        format_money(
            sale.discount_total
        ),
    )

    row_y -= (
        6 * mm
    )

    # =========================
    # CAMBIO
    # =========================

    pdf.drawString(
        summary_left,
        row_y,
        "Cambio",
    )

    pdf.drawRightString(
        summary_right,
        row_y,
        format_money(
            sale.change_amount
        ),
    )

    # =========================
    # FOOTER
    # =========================

    y = (
        summary_y
        - 5 * mm
    )

    pdf.setStrokeColor(
        BORDER_COLOR
    )

    pdf.setLineWidth(
        0.6
    )

    pdf.line(
        left,
        y,
        right,
        y,
    )

    y -= (
        6 * mm
    )

    pdf.setFillColor(
        TEXT_COLOR
    )

    pdf.setFont(
        "Helvetica-Bold",
        7.2,
    )

    pdf.drawString(
        left,
        y,
        company_name,
    )

    pdf.setFillColor(
        SECONDARY_TEXT_COLOR
    )

    pdf.setFont(
        "Helvetica",
        6.5,
    )

    pdf.drawRightString(
        right,
        y,
        "Gracias por su compra",
    )

    y -= (
        3.8 * mm
    )

    if company_tax_identifier:
        pdf.drawString(
            left,
            y,
            f"NIT: {company_tax_identifier}",
        )

    if branch_phone:
        pdf.drawRightString(
            right,
            y,
            f"Tel: {branch_phone}",
        )

    # =========================
    # FINAL
    # =========================

    pdf.save()

    pdf_bytes = (
        buffer.getvalue()
    )

    buffer.close()

    return pdf_bytes