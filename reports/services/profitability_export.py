from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

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


def _decimal(value):
    if value is None:
        return None
    return Decimal(str(value))


def _money_text(value, currency):
    amount = _decimal(value)
    if amount is None:
        return "No disponible"
    return f"{currency} {amount:,.2f}"


def _percentage_text(value):
    if value is None:
        return "—"
    return f"{Decimal(str(value)):,.2f}%"


def _excel_money(value, currency):
    amount = _decimal(value)
    if amount is None:
        return "No disponible"
    return float(amount)


def _summary_rows(summary):
    return [
        ("Ventas netas", "revenue", "money"),
        ("Costo de ventas", "cost_of_sales", "money"),
        ("Utilidad bruta", "gross_profit", "money"),
        ("Gastos", "expenses", "money"),
        ("Resultado operativo", "operating_result", "money"),
        ("Margen bruto", "gross_margin", "percent"),
        (
            "Líneas sin costo histórico",
            "missing_cost_items",
            "count",
        ),
    ]


def build_profitability_excel(
    *,
    summary,
    products,
    date_from,
    date_to,
    company_name,
    branch_name,
    currency,
):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Rentabilidad"

    sheet["A1"] = "SellSys - Reporte de Rentabilidad"
    sheet["A1"].font = Font(bold=True, size=16)
    sheet.merge_cells("A1:H1")

    sheet["A3"] = "Empresa"
    sheet["B3"] = company_name
    sheet["D3"] = "Sucursal"
    sheet["E3"] = branch_name
    sheet["A4"] = "Desde"
    sheet["B4"] = date_from.strftime("%d/%m/%Y")
    sheet["D4"] = "Hasta"
    sheet["E4"] = date_to.strftime("%d/%m/%Y")

    sheet["A6"] = "RESUMEN"
    sheet["A6"].font = Font(bold=True, size=12)

    row = 7
    for label, key, value_type in _summary_rows(summary):
        sheet.cell(row=row, column=1, value=label).font = Font(bold=True)
        value = summary.get(key)

        if value_type == "money":
            cell_value = _excel_money(value, currency)
        elif value_type == "percent":
            cell_value = _percentage_text(value)
        else:
            cell_value = int(value or 0)

        cell = sheet.cell(row=row, column=2, value=cell_value)
        if value_type == "money" and value is not None:
            cell.number_format = f'"{currency}" #,##0.00'
        row += 1

    if not summary.get("cost_coverage_complete", True):
        sheet.cell(
            row=row,
            column=1,
            value="Aviso",
        ).font = Font(bold=True, color="C2410C")
        sheet.cell(
            row=row,
            column=2,
            value=(
                "La rentabilidad no es completa porque hay líneas "
                "sin costo histórico."
            ),
        )
        row += 2
    else:
        row += 1

    header_row = row
    headers = [
        "Producto",
        "SKU",
        "Cantidad vendida",
        "Ventas",
        "Costo de ventas",
        "Utilidad bruta",
        "Margen bruto",
        "Costo completo",
    ]

    for column, header in enumerate(headers, start=1):
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

    current_row = header_row + 1
    for product in products:
        values = [
            product["product_name"],
            product["product_sku"] or "",
            float(Decimal(str(product["quantity_sold"]))),
            _excel_money(product["revenue"], currency),
            _excel_money(product["cost_of_sales"], currency),
            _excel_money(product["gross_profit"], currency),
            _percentage_text(product["gross_margin"]),
            "Sí" if product["cost_coverage_complete"] else "No",
        ]

        for column, value in enumerate(values, start=1):
            sheet.cell(
                row=current_row,
                column=column,
                value=value,
            )

        current_row += 1

    if not products:
        sheet.cell(
            row=current_row,
            column=1,
            value="No existen ventas completadas para el período seleccionado.",
        )
        sheet.merge_cells(
            start_row=current_row,
            start_column=1,
            end_row=current_row,
            end_column=len(headers),
        )

    for data_row in range(header_row + 1, current_row):
        sheet.cell(row=data_row, column=3).number_format = "#,##0.000"
        for column in (4, 5, 6):
            sheet.cell(
                row=data_row,
                column=column,
            ).number_format = f'"{currency}" #,##0.00'

    widths = {
        1: 34,
        2: 20,
        3: 19,
        4: 18,
        5: 20,
        6: 18,
        7: 17,
        8: 18,
    }
    for column, width in widths.items():
        sheet.column_dimensions[get_column_letter(column)].width = width

    sheet.freeze_panes = f"A{header_row + 1}"

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def build_profitability_pdf(
    *,
    summary,
    products,
    date_from,
    date_to,
    company_name,
    branch_name,
    currency,
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
            "SellSys - Reporte de Rentabilidad",
            styles["Title"],
        ),
        Spacer(1, 5 * mm),
        Paragraph(
            (
                f"<b>Empresa:</b> {escape(str(company_name))}<br/>"
                f"<b>Sucursal:</b> {escape(str(branch_name))}<br/>"
                f"<b>Período:</b> {date_from.strftime('%d/%m/%Y')} "
                f"al {date_to.strftime('%d/%m/%Y')}"
            ),
            styles["Normal"],
        ),
        Spacer(1, 5 * mm),
    ]

    summary_data = [["Indicador", "Resultado"]]
    for label, key, value_type in _summary_rows(summary):
        value = summary.get(key)
        if value_type == "money":
            formatted_value = _money_text(value, currency)
        elif value_type == "percent":
            formatted_value = _percentage_text(value)
        else:
            formatted_value = str(value or 0)
        summary_data.append([label, formatted_value])

    summary_table = Table(
        summary_data,
        colWidths=[65 * mm, 55 * mm],
        hAlign="LEFT",
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(summary_table)

    if not summary.get("cost_coverage_complete", True):
        elements.extend(
            [
                Spacer(1, 3 * mm),
                Paragraph(
                    (
                        "Aviso: la rentabilidad del período no es completa "
                        "porque existen líneas de venta sin costo histórico."
                    ),
                    styles["BodyText"],
                ),
            ]
        )

    elements.extend(
        [
            Spacer(1, 7 * mm),
            Paragraph(
                "Rentabilidad por producto",
                styles["Heading2"],
            ),
            Spacer(1, 2 * mm),
        ]
    )

    table_data = [[
        "Producto",
        "SKU",
        "Cantidad",
        "Ventas",
        "Costo",
        "Utilidad bruta",
        "Margen",
        "Costo completo",
    ]]

    for product in products:
        table_data.append(
            [
                Paragraph(
                    escape(str(product["product_name"] or "")),
                    styles["BodyText"],
                ),
                Paragraph(
                    escape(str(product["product_sku"] or "")),
                    styles["BodyText"],
                ),
                f'{Decimal(str(product["quantity_sold"])):,.3f}',
                _money_text(product["revenue"], currency),
                _money_text(product["cost_of_sales"], currency),
                _money_text(product["gross_profit"], currency),
                _percentage_text(product["gross_margin"]),
                "Sí" if product["cost_coverage_complete"] else "No",
            ]
        )

    if not products:
        table_data.append(
            [
                Paragraph(
                    "No existen ventas completadas para el período seleccionado.",
                    styles["BodyText"],
                ),
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ]
        )

    product_table = Table(
        table_data,
        repeatRows=1,
        colWidths=[
            47 * mm,
            22 * mm,
            22 * mm,
            35 * mm,
            35 * mm,
            35 * mm,
            24 * mm,
            27 * mm,
        ],
    )
    product_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (2, 1), (-2, -1), "RIGHT"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(product_table)

    document.build(elements)
    output.seek(0)
    return output
