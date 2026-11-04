from io import BytesIO

from django.utils import timezone
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


def build_sales_excel(
    *,
    sales,
    date_from,
    date_to,
    company_name,
    branch_name,
):
    workbook = Workbook()

    sheet = workbook.active
    sheet.title = "Ventas"

    sheet["A1"] = "SellSys - Reporte de Ventas"
    sheet["A1"].font = Font(
        bold=True,
        size=16,
    )

    sheet.merge_cells("A1:H1")

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
        "Venta",
        "Fecha",
        "Cliente",
        "Subtotal",
        "Descuento",
        "Impuestos",
        "Total",
        "Estado",
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

    total_sales = 0

    for sale in sales:
        completed_at = sale.completed_at

        if completed_at:
            completed_at = timezone.localtime(
                completed_at,
            )

        values = [
            sale.sale_number,
            (
                completed_at.strftime(
                    "%d/%m/%Y %H:%M",
                )
                if completed_at
                else ""
            ),
            sale.customer_name or "",
            float(sale.subtotal),
            float(sale.discount_total),
            float(sale.tax_total),
            float(sale.total),
            "Completada",
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

        total_sales += sale.total

        current_row += 1

    current_row += 1

    sheet.cell(
        row=current_row,
        column=6,
        value="TOTAL",
    ).font = Font(
        bold=True,
    )

    total_cell = sheet.cell(
        row=current_row,
        column=7,
        value=float(total_sales),
    )

    total_cell.font = Font(
        bold=True,
    )

    currency_columns = [
        4,
        5,
        6,
        7,
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
        2: 20,
        3: 28,
        4: 15,
        5: 15,
        6: 15,
        7: 15,
        8: 15,
    }

    for column, width in widths.items():
        sheet.column_dimensions[
            get_column_letter(column)
        ].width = width

    sheet.freeze_panes = "A7"

    output = BytesIO()

    workbook.save(output)

    output.seek(0)

    return output


def build_sales_pdf(
    *,
    sales,
    date_from,
    date_to,
    company_name,
    branch_name,
):
    output = BytesIO()

    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    styles = getSampleStyleSheet()

    elements = []

    elements.append(
        Paragraph(
            "SellSys - Reporte de Ventas",
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
            "Venta",
            "Fecha",
            "Cliente",
            "Subtotal",
            "Descuento",
            "Impuestos",
            "Total",
        ]
    ]

    total_sales = 0

    for sale in sales:
        completed_at = sale.completed_at

        if completed_at:
            completed_at = timezone.localtime(
                completed_at,
            )

        data.append(
            [
                sale.sale_number,
                (
                    completed_at.strftime(
                        "%d/%m/%Y %H:%M",
                    )
                    if completed_at
                    else ""
                ),
                sale.customer_name or "",
                f"Q{sale.subtotal:,.2f}",
                f"Q{sale.discount_total:,.2f}",
                f"Q{sale.tax_total:,.2f}",
                f"Q{sale.total:,.2f}",
            ]
        )

        total_sales += sale.total

    data.append(
        [
            "",
            "",
            "",
            "",
            "",
            "TOTAL",
            f"Q{total_sales:,.2f}",
        ]
    )

    table = Table(
        data,
        repeatRows=1,
        colWidths=[
            30 * mm,
            34 * mm,
            45 * mm,
            28 * mm,
            28 * mm,
            28 * mm,
            30 * mm,
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
                    (3, 1),
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
                    8,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    elements.append(table)
    document.build(elements)
    output.seek(0)

    return output

def _get_receivable_values(sale):
    paid_total = getattr(
        sale,
        "paid_total_export",
        None,
    )

    if paid_total is None:
        paid_total = (
            sale.amount_received
            or Decimal("0.00")
        )

    balance_due = getattr(
        sale,
        "balance_due_export",
        None,
    )

    if balance_due is None:
        balance_due = sale.total - paid_total

    payment_count = getattr(
        sale,
        "payment_count_export",
        0,
    ) or 0

    return (
        paid_total,
        balance_due,
        payment_count,
    )


def build_accounts_receivable_excel(
    *,
    sales,
    company_name,
    branch_name,
):
    workbook = Workbook()

    sheet = workbook.active
    sheet.title = "Cuentas por cobrar"

    sheet["A1"] = (
        "SellSys - Cuentas por cobrar"
    )
    sheet["A1"].font = Font(
        bold=True,
        size=16,
    )

    sheet.merge_cells("A1:G1")

    sheet["A3"] = "Empresa"
    sheet["B3"] = company_name

    sheet["D3"] = "Sucursal"
    sheet["E3"] = branch_name

    headers = [
        "Venta",
        "Fecha",
        "Cliente",
        "Total",
        "Pagado",
        "Saldo pendiente",
        "Pagos",
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

    total_sales = Decimal("0.00")
    total_paid = Decimal("0.00")
    total_due = Decimal("0.00")
    total_payments = 0

    for sale in sales:
        completed_at = sale.completed_at

        if completed_at:
            completed_at = timezone.localtime(
                completed_at,
            )

        (
            paid_total,
            balance_due,
            payment_count,
        ) = _get_receivable_values(sale)

        values = [
            sale.sale_number,
            (
                completed_at.strftime(
                    "%d/%m/%Y %H:%M",
                )
                if completed_at
                else ""
            ),
            sale.customer_name or "",
            float(sale.total),
            float(paid_total),
            float(balance_due),
            payment_count,
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

        total_sales += sale.total
        total_paid += paid_total
        total_due += balance_due
        total_payments += payment_count

        current_row += 1

    current_row += 1

    sheet.cell(
        row=current_row,
        column=3,
        value="TOTAL",
    ).font = Font(
        bold=True,
    )

    sheet.cell(
        row=current_row,
        column=4,
        value=float(total_sales),
    ).font = Font(
        bold=True,
    )

    sheet.cell(
        row=current_row,
        column=5,
        value=float(total_paid),
    ).font = Font(
        bold=True,
    )

    sheet.cell(
        row=current_row,
        column=6,
        value=float(total_due),
    ).font = Font(
        bold=True,
    )

    sheet.cell(
        row=current_row,
        column=7,
        value=total_payments,
    ).font = Font(
        bold=True,
    )

    for row in range(
        header_row + 1,
        current_row + 1,
    ):
        for column in (4, 5, 6):
            sheet.cell(
                row=row,
                column=column,
            ).number_format = '"Q"#,##0.00'

    widths = {
        1: 20,
        2: 20,
        3: 28,
        4: 15,
        5: 15,
        6: 18,
        7: 12,
    }

    for column, width in widths.items():
        sheet.column_dimensions[
            get_column_letter(column)
        ].width = width

    sheet.freeze_panes = "A7"

    output = BytesIO()

    workbook.save(output)
    output.seek(0)

    return output


def build_accounts_receivable_pdf(
    *,
    sales,
    company_name,
    branch_name,
):
    output = BytesIO()

    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    styles = getSampleStyleSheet()
    elements = []

    elements.append(
        Paragraph(
            "SellSys - Cuentas por cobrar",
            styles["Title"],
        )
    )

    elements.append(
        Spacer(
            1,
            6 * mm,
        )
    )

    generated_at = timezone.localtime()

    elements.append(
        Paragraph(
            (
                f"<b>Empresa:</b> "
                f"{company_name}<br/>"
                f"<b>Sucursal:</b> "
                f"{branch_name}<br/>"
                f"<b>Generado:</b> "
                f"{generated_at.strftime('%d/%m/%Y %H:%M')}"
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
            "Venta",
            "Fecha",
            "Cliente",
            "Total",
            "Pagado",
            "Saldo pendiente",
            "Pagos",
        ]
    ]

    total_sales = Decimal("0.00")
    total_paid = Decimal("0.00")
    total_due = Decimal("0.00")
    total_payments = 0

    for sale in sales:
        completed_at = sale.completed_at

        if completed_at:
            completed_at = timezone.localtime(
                completed_at,
            )

        (
            paid_total,
            balance_due,
            payment_count,
        ) = _get_receivable_values(sale)

        data.append(
            [
                sale.sale_number,
                (
                    completed_at.strftime(
                        "%d/%m/%Y %H:%M",
                    )
                    if completed_at
                    else ""
                ),
                sale.customer_name or "",
                f"Q{sale.total:,.2f}",
                f"Q{paid_total:,.2f}",
                f"Q{balance_due:,.2f}",
                payment_count,
            ]
        )

        total_sales += sale.total
        total_paid += paid_total
        total_due += balance_due
        total_payments += payment_count

    data.append(
        [
            "",
            "",
            "TOTAL",
            f"Q{total_sales:,.2f}",
            f"Q{total_paid:,.2f}",
            f"Q{total_due:,.2f}",
            total_payments,
        ]
    )

    table = Table(
        data,
        repeatRows=1,
        colWidths=[
            30 * mm,
            34 * mm,
            48 * mm,
            28 * mm,
            28 * mm,
            32 * mm,
            18 * mm,
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
                    "FONTNAME",
                    (0, -1),
                    (-1, -1),
                    "Helvetica-Bold",
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -2),
                    0.25,
                    colors.HexColor("#CBD5E1"),
                ),
                (
                    "ALIGN",
                    (3, 1),
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
                    8,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    elements.append(table)

    document.build(elements)

    output.seek(0)

    return output