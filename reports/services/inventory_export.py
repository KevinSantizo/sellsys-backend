from base64 import b64decode
from decimal import Decimal
from io import BytesIO
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import (
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as PdfImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _decimal(value):
    return value or Decimal("0.00")


def _quantity(value):
    return value or Decimal("0.000")


def _product_image_bytes(product):
    """Obtiene la imagen remota sin interrumpir la generación del reporte."""
    image_url = getattr(product, "image_url", None)

    if not image_url:
        return None

    try:
        if image_url.startswith("data:"):
            _, encoded_data = image_url.split(",", 1)
            return b64decode(encoded_data)

        request = Request(
            image_url,
            headers={
                "User-Agent": "SellSys inventory report",
            },
        )

        with urlopen(request, timeout=8) as response:
            return response.read()
    except Exception:
        # Una imagen dañada o inaccesible no debe impedir descargar el reporte.
        return None


def _add_excel_product_image(sheet, row, product):
    image_bytes = _product_image_bytes(product)

    if not image_bytes:
        return

    try:
        image = ExcelImage(BytesIO(image_bytes))
        max_size = 48
        scale = min(
            max_size / image.width,
            max_size / image.height,
        )
        image.width = max(1, int(image.width * scale))
        image.height = max(1, int(image.height * scale))
        sheet.add_image(image, f"A{row}")
    except Exception:
        return


def _pdf_product_image(product):
    image_bytes = _product_image_bytes(product)

    if not image_bytes:
        return ""

    try:
        image_buffer = BytesIO(image_bytes)
        image_reader = ImageReader(image_buffer)
        image_width, image_height = image_reader.getSize()
        max_size = 12 * mm
        scale = min(
            max_size / image_width,
            max_size / image_height,
        )

        image = PdfImage(
            BytesIO(image_bytes),
            width=image_width * scale,
            height=image_height * scale,
        )
        image.hAlign = "CENTER"
        return image
    except Exception:
        return ""


def _pdf_text(value, style):
    return Paragraph(
        escape(str(value or "")),
        style,
    )


def _lot_details(stock):
    lots = getattr(
        stock.product,
        "export_inventory_lots",
        (),
    )

    if not lots:
        return "Sin lote", "Sin vencimiento"

    lot_numbers = "\n".join(
        lot.lot_number or "Sin lote"
        for lot in lots
    )
    expiration_dates = "\n".join(
        (
            lot.expiration_date.strftime("%d/%m/%Y")
            if lot.expiration_date
            else "Sin vencimiento"
        )
        for lot in lots
    )

    return lot_numbers, expiration_dates


def _pdf_lot_details(stock, body_style):
    lot_numbers, expiration_dates = _lot_details(stock)

    return (
        Paragraph(
            "<br/>".join(
                escape(value)
                for value in lot_numbers.split("\n")
            ),
            body_style,
        ),
        Paragraph(
            "<br/>".join(
                escape(value)
                for value in expiration_dates.split("\n")
            ),
            body_style,
        ),
    )


def build_inventory_excel(
    *,
    stocks,
    company_name,
    branch_name,
    currency,
):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Inventario"

    body_font = Font(
        name="Arial",
        size=8,
    )
    header_font = Font(
        name="Arial",
        bold=True,
        size=8,
    )

    sheet["A1"] = "SellSys - Reporte de Inventario"
    sheet["A1"].font = Font(
        bold=True,
        size=16,
    )
    sheet.merge_cells("A1:N1")

    sheet["A3"] = "Empresa"
    sheet["B3"] = company_name

    sheet["D3"] = "Sucursal"
    sheet["E3"] = branch_name

    sheet["G3"] = "Moneda"
    sheet["H3"] = currency

    headers = [
        "Foto",
        "Producto",
        "Código de barras",
        "Precio costo",
        "Precio venta",
        "Categoría",
        "Marca",
        "Unidad",
        "Lote",
        "Vencimiento",
        "Existencia",
        "Valor a costo",
        "Valor a venta",
        "Estado",
    ]

    header_row = 5

    for column, header in enumerate(
        headers,
        start=1,
    ):
        cell = sheet.cell(
            row=header_row,
            column=column,
            value=header,
        )
        cell.font = header_font
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True,
        )

    sheet.row_dimensions[header_row].height = 24

    total_units = Decimal("0.000")
    total_cost_value = Decimal("0.00")
    total_sale_value = Decimal("0.00")

    row = header_row + 1

    for stock in stocks:
        product = stock.product
        quantity = _quantity(stock.quantity)
        cost_price = _decimal(product.cost_price)
        sale_price = _decimal(product.sale_price)
        lot_numbers, expiration_dates = _lot_details(stock)
        cost_value = quantity * cost_price
        sale_value = quantity * sale_price

        total_units += quantity
        total_cost_value += cost_value
        total_sale_value += sale_value

        values = [
            "",
            product.name,
            product.barcode or "",
            float(cost_price),
            float(sale_price),
            product.category.name if product.category else "",
            product.brand.name if product.brand else "",
            product.base_unit.symbol if product.base_unit else "",
            lot_numbers,
            expiration_dates,
            float(quantity),
            float(cost_value),
            float(sale_value),
            "Activo" if product.is_active else "Inactivo",
        ]

        for column, value in enumerate(
            values,
            start=1,
        ):
            sheet.cell(
                row=row,
                column=column,
                value=value,
            )

        _add_excel_product_image(
            sheet,
            row,
            product,
        )
        sheet.row_dimensions[row].height = 42

        row += 1

    row += 1

    summary = [
        ("PRODUCTOS", len(stocks)),
        ("UNIDADES TOTALES", float(total_units)),
        ("VALOR TOTAL A COSTO", float(total_cost_value)),
        ("VALOR TOTAL A VENTA", float(total_sale_value)),
    ]

    for label, value in summary:
        sheet.cell(
            row=row,
            column=13,
            value=label,
        ).font = header_font

        cell = sheet.cell(
            row=row,
            column=14,
            value=value,
        )
        cell.font = header_font

        row += 1

    for current_row in range(
        header_row + 1,
        row,
    ):
        for column in range(1, 15):
            sheet.cell(
                row=current_row,
                column=column,
            ).font = body_font

        sheet.cell(
            row=current_row,
            column=11,
        ).number_format = "#,##0.000"

        for column in (4, 5, 12, 13):
            sheet.cell(
                row=current_row,
                column=column,
            ).number_format = "#,##0.00"

        for column in (2, 6, 7, 8, 9, 10, 14):
            sheet.cell(
                row=current_row,
                column=column,
            ).alignment = Alignment(
                vertical="center",
                wrap_text=True,
            )

        sheet.cell(
            row=current_row,
            column=1,
        ).alignment = Alignment(
            horizontal="center",
            vertical="center",
        )

    for summary_row in range(
        row - len(summary),
        row,
    ):
        sheet.cell(
            row=summary_row,
            column=13,
        ).font = header_font
        sheet.cell(
            row=summary_row,
            column=14,
        ).font = header_font

    widths = {
        1: 10,
        2: 34,
        3: 22,
        4: 15,
        5: 15,
        6: 20,
        7: 16,
        8: 12,
        9: 22,
        10: 18,
        11: 13,
        12: 18,
        13: 18,
        14: 12,
    }

    for column, width in widths.items():
        sheet.column_dimensions[
            get_column_letter(column)
        ].width = width

    sheet.freeze_panes = "A6"

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    return output


def build_inventory_pdf(
    *,
    stocks,
    company_name,
    branch_name,
    currency,
):
    output = BytesIO()

    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=7 * mm,
        leftMargin=7 * mm,
        topMargin=9 * mm,
        bottomMargin=9 * mm,
    )

    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        "InventoryBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7,
        leading=8,
        spaceBefore=0,
        spaceAfter=0,
    )

    elements = [
        Paragraph(
            "SellSys - Reporte de Inventario",
            styles["Title"],
        ),
        Spacer(1, 4 * mm),
        Paragraph(
            (
                f"<b>Empresa:</b> {company_name}<br/>"
                f"<b>Sucursal:</b> {branch_name}<br/>"
                f"<b>Moneda:</b> {currency}"
            ),
            styles["Normal"],
        ),
        Spacer(1, 5 * mm),
    ]

    data = [[
        "Foto",
        "Producto",
        "Código de barras",
        "Precio costo",
        "Precio venta",
        "Categoría",
        "Marca",
        "Unidad",
        "Lote",
        "Vencimiento",
        "Existencia",
        "V. costo",
        "V. venta",
        "Estado",
    ]]

    total_units = Decimal("0.000")
    total_cost_value = Decimal("0.00")
    total_sale_value = Decimal("0.00")

    for stock in stocks:
        product = stock.product
        quantity = _quantity(stock.quantity)
        cost_price = _decimal(product.cost_price)
        sale_price = _decimal(product.sale_price)
        lot_numbers, expiration_dates = _pdf_lot_details(
            stock,
            body_style,
        )
        cost_value = quantity * cost_price
        sale_value = quantity * sale_price

        total_units += quantity
        total_cost_value += cost_value
        total_sale_value += sale_value

        data.append([
            _pdf_product_image(product),
            _pdf_text(product.name, body_style),
            _pdf_text(product.barcode, body_style),
            _pdf_text(f"{cost_price:,.2f}", body_style),
            _pdf_text(f"{sale_price:,.2f}", body_style),
            _pdf_text(
                product.category.name
                if product.category
                else "",
                body_style,
            ),
            _pdf_text(
                product.brand.name
                if product.brand
                else "",
                body_style,
            ),
            _pdf_text(
                product.base_unit.symbol
                if product.base_unit
                else "",
                body_style,
            ),
            lot_numbers,
            expiration_dates,
            _pdf_text(f"{quantity:,.3f}", body_style),
            _pdf_text(f"{cost_value:,.2f}", body_style),
            _pdf_text(f"{sale_value:,.2f}", body_style),
            _pdf_text(
                "Activo" if product.is_active else "Inactivo",
                body_style,
            ),
        ])

    table = Table(
        data,
        repeatRows=1,
        colWidths=[
            14 * mm,
            34 * mm,
            23 * mm,
            17 * mm,
            17 * mm,
            21 * mm,
            17 * mm,
            13 * mm,
            25 * mm,
            21 * mm,
            15 * mm,
            19 * mm,
            19 * mm,
            14 * mm,
        ],
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#F1F5F9"),
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold",
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.25,
                    colors.HexColor("#CBD5E1"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "ALIGN",
                    (3, 1),
                    (4, -1),
                    "RIGHT",
                ),
                (
                    "ALIGN",
                    (10, 1),
                    (12, -1),
                    "RIGHT",
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    3,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    3,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    elements.append(table)
    elements.append(Spacer(1, 6 * mm))

    summary = Table(
        [
            [
                "Productos",
                str(len(stocks)),
            ],
            [
                "Unidades totales",
                f"{total_units:,.3f}",
            ],
            [
                "Valor total a costo",
                f"{currency} {total_cost_value:,.2f}",
            ],
            [
                "Valor total a venta",
                f"{currency} {total_sale_value:,.2f}",
            ],
        ],
        colWidths=[
            45 * mm,
            40 * mm,
        ],
        hAlign="RIGHT",
    )

    summary.setStyle(
        TableStyle(
            [
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, -1),
                    "Helvetica-Bold",
                ),
                (
                    "ALIGN",
                    (1, 0),
                    (1, -1),
                    "RIGHT",
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.25,
                    colors.HexColor("#CBD5E1"),
                ),
                (

                   "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#F8FAFC"),
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
            ]
        )
    )

    elements.append(summary)

    document.build(elements)
    output.seek(0)

    return output
