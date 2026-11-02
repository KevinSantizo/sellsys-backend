from decimal import Decimal
from io import BytesIO

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _cash_register_name(movement):
    if movement.cash_session_id and movement.cash_session:
        return movement.cash_session.cash_register.name
    return ""


def _format_datetime(value):
    if not value:
        return ""

    local_value = timezone.localtime(value)

    return local_value.strftime("%d/%m/%Y %H:%M")


def build_cash_excel(
    *,
    movements,
    date_from,
    date_to,
    company_name,
    branch_name,
):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Movimientos de caja"

    sheet["A1"] = "SellSys - Reporte de Movimientos de Caja"
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
    sheet["B4"] = date_from.strftime("%d/%m/%Y")

    sheet["D4"] = "Hasta"
    sheet["E4"] = date_to.strftime("%d/%m/%Y")

    headers = [
        "Fecha / hora",
        "Caja",
        "Dirección",
        "Tipo",
        "Origen",
        "Referencia",
        "Notas",
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

    total_in = Decimal("0.00")
    total_out = Decimal("0.00")

    for movement in movements:
        if movement.direction == "IN":
            total_in += movement.amount
        elif movement.direction == "OUT":
            total_out += movement.amount

        values = [
            _format_datetime(
                movement.created_at,
            ),
            _cash_register_name(
                movement,
            ),
            movement.get_direction_display(),
            movement.get_movement_type_display(),
            movement.source_type or "",
            movement.reference or "",
            movement.notes or "",
            float(movement.amount),
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

        current_row += 1

    current_row += 1

    summary_rows = [
        ("TOTAL ENTRADAS", total_in),
        ("TOTAL SALIDAS", total_out),
        ("FLUJO NETO", total_in - total_out),
    ]

    for label, amount in summary_rows:
        sheet.cell(
            row=current_row,
            column=7,
            value=label,
        ).font = Font(
            bold=True,
        )

        cell = sheet.cell(
            row=current_row,
            column=8,
            value=float(amount),
        )
        cell.font = Font(
            bold=True,
        )
        cell.number_format = '"Q"#,##0.00'

        current_row += 1

    for row in range(
        header_row + 1,
        current_row,
    ):
        sheet.cell(
            row=row,
            column=8,
        ).number_format = '"Q"#,##0.00'

    widths = {
        1: 20,
        2: 25,
        3: 16,
        4: 25,
        5: 18,
        6: 28,
        7: 45,
        8: 16,
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


def build_cash_pdf(
    *,
    movements,
    date_from,
    date_to,
    company_name,
    branch_name,
):
    output = BytesIO()

    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=8 * mm,
        leftMargin=8 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )

    styles = getSampleStyleSheet()

    elements = [
        Paragraph(
            "SellSys - Reporte de Movimientos de Caja",
            styles["Title"],
        ),
        Spacer(
            1,
            5 * mm,
        ),
        Paragraph(
            (
                f"<b>Empresa:</b> {company_name}<br/>"
                f"<b>Sucursal:</b> {branch_name}<br/>"
                f"<b>Período:</b> "
                f"{date_from.strftime('%d/%m/%Y')} "
                f"al {date_to.strftime('%d/%m/%Y')}"
            ),
            styles["Normal"],
        ),
        Spacer(
            1,
            5 * mm,
        ),
    ]

    data = [[
        "Fecha / hora",
        "Caja",
        "Dirección",
        "Tipo",
        "Origen",
        "Referencia",
        "Notas",
        "Monto",
    ]]

    total_in = Decimal("0.00")
    total_out = Decimal("0.00")

    for movement in movements:
        if movement.direction == "IN":
            total_in += movement.amount
        elif movement.direction == "OUT":
            total_out += movement.amount

        data.append([
            _format_datetime(
                movement.created_at,
            ),
            Paragraph(
                _cash_register_name(
                    movement,
                ),
                styles["BodyText"],
            ),
            movement.get_direction_display(),
            Paragraph(
                movement.get_movement_type_display(),
                styles["BodyText"],
            ),
            movement.source_type or "",
            Paragraph(
                movement.reference or "",
                styles["BodyText"],
            ),
            Paragraph(
                movement.notes or "",
                styles["BodyText"],
            ),
            f"Q{movement.amount:,.2f}",
        ])

    table = Table(
        data,
        repeatRows=1,
        colWidths=[
            26 * mm,
            30 * mm,
            22 * mm,
            36 * mm,
            22 * mm,
            35 * mm,
            55 * mm,
            24 * mm,
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
                    (-1, 1),
                    (-1, -1),
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
    elements.append(
        Spacer(
            1,
            6 * mm,
        )
    )

    summary_data = [
        [
            "Total entradas",
            f"Q{total_in:,.2f}",
        ],
        [
            "Total salidas",
            f"Q{total_out:,.2f}",
        ],
        [
            "Flujo neto",
            f"Q{(total_in - total_out):,.2f}",
        ],
    ]

    summary_table = Table(
        summary_data,
        colWidths=[
            45 * mm,
            35 * mm,
        ],
        hAlign="RIGHT",
    )

    summary_table.setStyle(
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

    elements.append(summary_table)

    document.build(elements)

    output.seek(0)

    return output
