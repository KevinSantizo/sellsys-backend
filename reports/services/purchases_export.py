from io import BytesIO
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def build_purchases_excel(
    *,
    purchases,
    date_from,
    date_to,
    company_name,
    branch_name,
):
    workbook = Workbook()

    sheet = workbook.active
    sheet.title = "Compras"

    sheet["A1"] = "SellSys - Reporte de Compras"
    sheet["A1"].font = Font(
        bold=True,
        size=16,
    )

    sheet.merge_cells("A1:I1")

    sheet["A3"] = "Empresa"
    sheet["B3"] = company_name

    sheet["D3"] = "Sucursal"
    sheet["E3"] = branch_name

    sheet["A4"] = "Desde"
    sheet["B4"] = date_from.strftime(
        "%d/%m/%Y",
    )

    sheet["D4"] = "Hasta"
    sheet["E4"] = date_to.strftime(
        "%d/%m/%Y",
    )

    headers = [
        "Compra",
        "Fecha",
        "Proveedor",
        "Factura proveedor",
        "Método de pago",
        "Subtotal",
        "Descuento",
        "Impuesto",
        "Total",
    ]

    header_row = 6

    for column, header in enumerate(
        headers,
        start=1,
    ):
        cell = sheet.cell(
            row=header_row,
            column=column,
            value=header,
        )

        cell.font = Font(
            bold=True,
        )

        cell.alignment = Alignment(
            horizontal="center",
        )

    current_row = header_row + 1

    total_purchases = Decimal(
        "0.00",
    )

    for purchase in purchases:
        values = [
            purchase.purchase_number,
            purchase.purchase_date.strftime(
                "%d/%m/%Y",
            ),
            purchase.supplier.name,
            (
                purchase.supplier_invoice_number
                or ""
            ),
            purchase.get_payment_method_display(),
            float(purchase.subtotal),
            float(purchase.discount_total),
            float(purchase.tax_total),
            float(purchase.total),
        ]

        for column, value in enumerate(
            values,
            start=1,
        ):
            sheet.cell(
                row=current_row,
                column=column,
                value=value,
            )

        total_purchases += (
            purchase.total
        )

        current_row += 1

    current_row += 1

    sheet.cell(
        row=current_row,
        column=8,
        value="TOTAL",
    ).font = Font(
        bold=True,
    )

    total_cell = sheet.cell(
        row=current_row,
        column=9,
        value=float(
            total_purchases,
        ),
    )

    total_cell.font = Font(
        bold=True,
    )

    currency_columns = [
        6,
        7,
        8,
        9,
    ]

    for row in range(
        header_row + 1,
        current_row + 1,
    ):
        for column in currency_columns:
            sheet.cell(
                row=row,
                column=column,
            ).number_format = (
                '"Q"#,##0.00'
            )

    widths = {
        1: 18,
        2: 14,
        3: 30,
        4: 22,
        5: 20,
        6: 15,
        7: 15,
        8: 15,
        9: 15,
    }

    for column, width in (
        widths.items()
    ):
        sheet.column_dimensions[
            get_column_letter(column)
        ].width = width

    sheet.freeze_panes = "A7"

    output = BytesIO()

    workbook.save(output)

    output.seek(0)

    return output


def build_purchases_pdf(
    *,
    purchases,
    date_from,
    date_to,
    company_name,
    branch_name,
):
    output = BytesIO()

    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    styles = getSampleStyleSheet()

    elements = []

    elements.append(
        Paragraph(
            "SellSys - Reporte de Compras",
            styles["Title"],
        )
    )

    elements.append(
        Spacer(
            1,
            6 * mm,
        )
    )

    elements.append(
        Paragraph(
            (
                f"<b>Empresa:</b> "
                f"{company_name}<br/>"
                f"<b>Sucursal:</b> "
                f"{branch_name}<br/>"
                f"<b>Período:</b> "
                f"{date_from.strftime('%d/%m/%Y')} "
                f"al "
                f"{date_to.strftime('%d/%m/%Y')}"
            ),
            styles["Normal"],
        )
    )

    elements.append(
        Spacer(
            1,
            6 * mm,
        )
    )

    data = [
        [
            "Compra",
            "Fecha",
            "Proveedor",
            "Factura",
            "Método",
            "Subtotal",
            "Descuento",
            "Impuesto",
            "Total",
        ]
    ]

    total_purchases = Decimal(
        "0.00",
    )

    for purchase in purchases:
        data.append(
            [
                purchase.purchase_number,
                purchase.purchase_date.strftime(
                    "%d/%m/%Y",
                ),
                purchase.supplier.name,
                (
                    purchase.supplier_invoice_number
                    or ""
                ),
                purchase.get_payment_method_display(),
                f"Q{purchase.subtotal:,.2f}",
                f"Q{purchase.discount_total:,.2f}",
                f"Q{purchase.tax_total:,.2f}",
                f"Q{purchase.total:,.2f}",
            ]
        )

        total_purchases += (
            purchase.total
        )

    data.append(
        [
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "TOTAL",
            f"Q{total_purchases:,.2f}",
        ]
    )

    table = Table(
        data,
        repeatRows=1,
        colWidths=[
            24 * mm,
            22 * mm,
            38 * mm,
            30 * mm,
            28 * mm,
            24 * mm,
            24 * mm,
            24 * mm,
            26 * mm,
        ],
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor(
                        "#F1F5F9",
                    ),
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold",
                ),
                (
                    "FONTNAME",
                    (-2, -1),
                    (-1, -1),
                    "Helvetica-Bold",
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -2),
                    0.25,
                    colors.HexColor(
                        "#CBD5E1",
                    ),
                ),
                (
                    "ALIGN",
                    (5, 1),
                    (-1, -1),
                    "RIGHT",
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    7.5,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    elements.append(
        table,
    )

    document.build(
        elements,
    )

    output.seek(0)

    return output