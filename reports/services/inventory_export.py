from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _decimal(value):
    return value or Decimal("0.00")


def _quantity(value):
    return value or Decimal("0.000")


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

    sheet["A1"] = "SellSys - Reporte de Inventario"
    sheet["A1"].font = Font(
        bold=True,
        size=16,
    )
    sheet.merge_cells("A1:L1")

    sheet["A3"] = "Empresa"
    sheet["B3"] = company_name

    sheet["D3"] = "Sucursal"
    sheet["E3"] = branch_name

    sheet["G3"] = "Moneda"
    sheet["H3"] = currency

    headers = [
        "Producto",
        "SKU",
        "Código de barras",
        "Categoría",
        "Marca",
        "Unidad",
        "Existencia",
        "Costo unitario",
        "Precio de venta",
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
        cell.font = Font(bold=True)
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
        )

    total_units = Decimal("0.000")
    total_cost_value = Decimal("0.00")
    total_sale_value = Decimal("0.00")

    row = header_row + 1

    for stock in stocks:
        product = stock.product
        quantity = _quantity(stock.quantity)
        cost_price = _decimal(product.cost_price)
        sale_price = _decimal(product.sale_price)
        cost_value = quantity * cost_price
        sale_value = quantity * sale_price

        total_units += quantity
        total_cost_value += cost_value
        total_sale_value += sale_value

        values = [
            product.name,
            product.sku,
            product.barcode or "",
            product.category.name if product.category else "",
            product.brand.name if product.brand else "",
            product.base_unit.symbol if product.base_unit else "",
            float(quantity),
            float(cost_price),
            float(sale_price),
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
            column=10,
            value=label,
        ).font = Font(bold=True)

        cell = sheet.cell(
            row=row,
            column=11,
            value=value,
        )
        cell.font = Font(bold=True)

        row += 1

    for current_row in range(
        header_row + 1,
        row,
    ):
        sheet.cell(
            row=current_row,
            column=7,
        ).number_format = "#,##0.000"

        for column in (8, 9, 10, 11):
            sheet.cell(
                row=current_row,
                column=column,
            ).number_format = "#,##0.00"

    widths = {
        1: 30,
        2: 18,
        3: 20,
        4: 20,
        5: 18,
        6: 12,
        7: 14,
        8: 16,
        9: 16,
        10: 18,
        11: 18,
        12: 12,
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
        "Producto",
        "SKU",
        "Categoría",
        "Marca",
        "Unidad",
        "Exist.",
        "Costo",
        "Venta",
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
        cost_value = quantity * cost_price
        sale_value = quantity * sale_price

        total_units += quantity
        total_cost_value += cost_value
        total_sale_value += sale_value

        data.append([
            Paragraph(
                product.name,
                styles["BodyText"],
            ),
            product.sku,
            Paragraph(
                product.category.name if product.category else "",
                styles["BodyText"],
            ),
            Paragraph(
                product.brand.name if product.brand else "",
                styles["BodyText"],
            ),
            product.base_unit.symbol if product.base_unit else "",
            f"{quantity:,.3f}",
            f"{cost_price:,.2f}",
            f"{sale_price:,.2f}",
            f"{cost_value:,.2f}",
            f"{sale_value:,.2f}",
            "Activo" if product.is_active else "Inactivo",
        ])

    table = Table(
        data,
        repeatRows=1,
        colWidths=[
            37 * mm,
            23 * mm,
            27 * mm,
            23 * mm,
            15 * mm,
            18 * mm,
            20 * mm,
            20 * mm,
            23 * mm,
            23 * mm,
            17 * mm,
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
                    (5, 1),
                    (9, -1),
                    "RIGHT",
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    7,
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
                    8,
                ),
            ]
        )
    )

    elements.append(summary)

    document.build(elements)
    output.seek(0)

    return output
