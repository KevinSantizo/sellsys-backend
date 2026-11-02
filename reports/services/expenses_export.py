from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def build_expenses_excel(
    *,
    expenses,
    date_from,
    date_to,
    company_name,
    branch_name,
):
    workbook = Workbook()

    sheet = workbook.active
    sheet.title = "Gastos"

    sheet["A1"] = "SellSys - Reporte de Gastos"
    sheet["A1"].font = Font(
        bold=True,
        size=16,
    )

    sheet.merge_cells("A1:F1")

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
        "Fecha",
        "Descripción",
        "Proveedor",
        "Método de pago",
        "Referencia",
        "Monto",
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
            vertical="center",
        )

    current_row = header_row + 1

    total_expenses = Decimal(
        "0.00",
    )

    for expense in expenses:
        supplier_name = (
            expense.supplier.name
            if expense.supplier
            else ""
        )

        values = [
            expense.expense_date.strftime(
                "%d/%m/%Y",
            ),
            expense.description,
            supplier_name,
            expense.get_payment_method_display(),
            expense.reference or "",
            float(expense.amount),
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

        total_expenses += expense.amount

        current_row += 1

    current_row += 1

    sheet.cell(
        row=current_row,
        column=5,
        value="TOTAL",
    ).font = Font(
        bold=True,
    )

    total_cell = sheet.cell(
        row=current_row,
        column=6,
        value=float(
            total_expenses,
        ),
    )

    total_cell.font = Font(
        bold=True,
    )

    for row in range(
        header_row + 1,
        current_row + 1,
    ):
        sheet.cell(
            row=row,
            column=6,
        ).number_format = (
            '"Q"#,##0.00'
        )

    widths = {
        1: 15,
        2: 40,
        3: 30,
        4: 22,
        5: 25,
        6: 16,
    }

    for column, width in widths.items():
        sheet.column_dimensions[
            get_column_letter(column)
        ].width = width

    sheet.freeze_panes = "A7"

    output = BytesIO()

    workbook.save(
        output,
    )

    output.seek(0)

    return output


def build_expenses_pdf(
    *,
    expenses,
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
            "SellSys - Reporte de Gastos",
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
            "Fecha",
            "Descripción",
            "Proveedor",
            "Método",
            "Referencia",
            "Monto",
        ]
    ]

    total_expenses = Decimal(
        "0.00",
    )

    for expense in expenses:
        supplier_name = (
            expense.supplier.name
            if expense.supplier
            else ""
        )

        data.append(
            [
                expense.expense_date.strftime(
                    "%d/%m/%Y",
                ),
                Paragraph(
                    expense.description or "",
                    styles["BodyText"],
                ),
                Paragraph(
                    supplier_name,
                    styles["BodyText"],
                ),
                expense.get_payment_method_display(),
                expense.reference or "",
                f"Q{expense.amount:,.2f}",
            ]
        )

        total_expenses += expense.amount

    data.append(
        [
            "",
            "",
            "",
            "",
            "TOTAL",
            f"Q{total_expenses:,.2f}",
        ]
    )

    table = Table(
        data,
        repeatRows=1,
        colWidths=[
            24 * mm,
            65 * mm,
            50 * mm,
            35 * mm,
            45 * mm,
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
                    (-1, 1),
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