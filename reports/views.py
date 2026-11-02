from datetime import datetime, time, timedelta
from decimal import Decimal
from django.db.models import (
    Avg,
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Q,
    Sum,
)
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import (
    OpenApiTypes,
    extend_schema,
)
from cash.models import (
    CashMovement,
    CashMovementDirection,
)
from common.access import validate_company_branch_access
from expenses.models import (
    Expense,
    ExpenseStatus,
)
from inventory.models import ProductStock
from purchases.models import (
    Purchase,
    PurchaseStatus,
)
from sales.models import (
    Sale,
    SaleItem,
    SaleStatus,
)
from .serializers import (
    InventoryReportQuerySerializer,
    ReportSummaryQuerySerializer,
)
from django.http import HttpResponse
from branches.models import Branch
from .services.sales_export import (
    build_sales_excel,
    build_sales_pdf,
)

from .services.purchases_export import (
    build_purchases_excel,
    build_purchases_pdf,
)
from .services.expenses_export import (
    build_expenses_excel,
    build_expenses_pdf,
)
from .services.cash_export import (
    build_cash_excel,
    build_cash_pdf
)
from .services.inventory_export import (
    build_inventory_excel,
    build_inventory_pdf,
)
from .services.profitability_export import (
    build_profitability_excel,
    build_profitability_pdf,
)

def get_inventory_export_queryset(
    *,
    company_id,
    branch_id,
    search=None,
    is_active=None,
    category_id=None,
    brand_id=None,
    product_type=None,
):
    queryset = (
        ProductStock.objects
        .filter(
            company_id=company_id,
            branch_id=branch_id,
            product__track_inventory=True,
        )
        .select_related(
            "product",
            "product__category",
            "product__brand",
            "product__base_unit",
        )
    )
    if search:
        queryset = queryset.filter(
            Q(product__name__icontains=search)
            | Q(product__sku__icontains=search)
            | Q(product__barcode__icontains=search)
            | Q(product__description__icontains=search)
        )
    if is_active is not None:
        normalized_is_active = str(
            is_active
        ).lower()
        if normalized_is_active in (
            "true",
            "1",
        ):
            queryset = queryset.filter(
                product__is_active=True,
            )
        elif normalized_is_active in (
            "false",
            "0",
        ):
            queryset = queryset.filter(
                product__is_active=False,
            )
    if category_id:
        queryset = queryset.filter(
            product__category_id=category_id,
        )
    if brand_id:
        queryset = queryset.filter(
            product__brand_id=brand_id,
        )
    if product_type:
        queryset = queryset.filter(
            product__product_type=product_type,
        )
    return queryset.order_by(
        "product__name",
        "product__sku",
    )

class InventoryExcelReportView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):
        serializer = InventoryReportQuerySerializer(
            data=request.query_params,
        )
        serializer.is_valid(
            raise_exception=True,
        )
        company_id = serializer.validated_data[
            "company_id"
        ]
        branch_id = serializer.validated_data[
            "branch_id"
        ]
        validate_company_branch_access(
            request.user,
            company_id,
            branch_id,
        )
        branch = (
            Branch.objects
            .select_related("company")
            .get(
                id=branch_id,
                company_id=company_id,
            )
        )
        stocks = list(
            get_inventory_export_queryset(
                company_id=company_id,
                branch_id=branch_id,
                search=request.query_params.get(
                    "search",
                ),
                is_active=request.query_params.get(
                    "is_active",
                ),
                category_id=request.query_params.get(
                    "category_id",
                ),
                brand_id=request.query_params.get(
                    "brand_id",
                ),
                product_type=request.query_params.get(
                    "product_type",
                ),
            )
        )
        file = build_inventory_excel(
            stocks=stocks,
            company_name=branch.company.name,
            branch_name=branch.name,
            currency=branch.company.currency,
        )
        response = HttpResponse(
            file.getvalue(),
            content_type=(
                "application/"
                "vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
        response[
            "Content-Disposition"
        ] = (
            'attachment; '
            'filename="inventario.xlsx"'
        )
        return response

class InventoryPdfReportView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):
        serializer = InventoryReportQuerySerializer(
            data=request.query_params,
        )
        serializer.is_valid(
            raise_exception=True,
        )
        company_id = serializer.validated_data[
            "company_id"
        ]
        branch_id = serializer.validated_data[
            "branch_id"
        ]
        validate_company_branch_access(
            request.user,
            company_id,
            branch_id,
        )
        branch = (
            Branch.objects
            .select_related("company")
            .get(
                id=branch_id,
                company_id=company_id,
            )
        )
        stocks = list(
            get_inventory_export_queryset(
                company_id=company_id,
                branch_id=branch_id,
                search=request.query_params.get(
                    "search",
                ),
                is_active=request.query_params.get(
                    "is_active",
                ),
                category_id=request.query_params.get(
                    "category_id",
                ),
                brand_id=request.query_params.get(
                    "brand_id",
                ),
                product_type=request.query_params.get(
                    "product_type",
                ),
            )
        )
        file = build_inventory_pdf(
            stocks=stocks,
            company_name=branch.company.name,
            branch_name=branch.name,
            currency=branch.company.currency,
        )
        response = HttpResponse(
            file.getvalue(),
            content_type="application/pdf",
        )
        response[
            "Content-Disposition"
        ] = (
            'attachment; '
            'filename="inventario.pdf"'
        )
        return response

def get_cash_report_queryset(
    *,
    company_id,
    branch_id,
    date_from,
    date_to,
    cash_register_id=None,
    movement_type=None,
    direction=None,
    search=None,
):
    start_datetime, end_datetime = build_datetime_range(
        date_from,
        date_to,
    )
    queryset = (
        CashMovement.objects
        .filter(
            company_id=company_id,
            branch_id=branch_id,
            created_at__gte=start_datetime,
            created_at__lt=end_datetime,
        )
        .select_related(
            "cash_session",
            "cash_session__cash_register",
        )
    )
    if cash_register_id:
        queryset = queryset.filter(
            cash_session__cash_register_id=cash_register_id,
        )
    if movement_type:
        queryset = queryset.filter(
            movement_type=movement_type,
        )
    if direction:
        queryset = queryset.filter(
            direction=direction,
        )
    if search:
        queryset = queryset.filter(
            Q(reference__icontains=search)
            | Q(notes__icontains=search)
            | Q(
                cash_session__cash_register__name__icontains=search
            )
            | Q(
                cash_session__cash_register__code__icontains=search
            )
        )
    return queryset.order_by(
        "-created_at",
        "-id",
    )

def get_expenses_report_queryset(
    *,
    company_id,
    branch_id,
    date_from,
    date_to,
):
    return (
        Expense.objects
        .filter(
            company_id=company_id,
            branch_id=branch_id,
            status=ExpenseStatus.COMPLETED,
            expense_date__range=(
                date_from,
                date_to,
            ),
        )
        .select_related(
            "supplier",
        )
        .order_by(
            "-expense_date",
            "-created_at",
        )
    )

def get_purchases_report_queryset(
    *,
    company_id,
    branch_id,
    date_from,
    date_to,
):
    return (
        Purchase.objects
        .filter(
            company_id=company_id,
            branch_id=branch_id,
            status=PurchaseStatus.COMPLETED,
            purchase_date__range=(
                date_from,
                date_to,
            ),
        )
        .select_related(
            "supplier",
        )
        .order_by(
            "-purchase_date",
            "-created_at",
        )
    )

def get_sales_report_queryset(
    *,
    company_id,
    branch_id,
    date_from,
    date_to,
):
    start_datetime, end_datetime = (
        build_datetime_range(
            date_from,
            date_to,
        )
    )
    return (
        Sale.objects
        .filter(
            company_id=company_id,
            branch_id=branch_id,
            status=SaleStatus.COMPLETED,
            completed_at__gte=start_datetime,
            completed_at__lt=end_datetime,
        )
        .order_by(
            "-completed_at",
            "-id",
        )
    )

class ReportPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

def decimal_string(value):
    return f"{value or Decimal('0.00'):.2f}"

def quantity_string(value):
    return f"{value or Decimal('0.000'):.3f}"

def build_datetime_range(
    date_from,
    date_to,
):
    current_timezone = (
        timezone.get_current_timezone()
    )
    start_datetime = timezone.make_aware(
        datetime.combine(
            date_from,
            time.min,
        ),
        current_timezone,
    )
    end_datetime = timezone.make_aware(
        datetime.combine(
            date_to + timedelta(days=1),
            time.min,
        ),
        current_timezone,
    )
    return (
        start_datetime,
        end_datetime,
    )

class ReportSummaryView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    @extend_schema(
        parameters=[
            ReportSummaryQuerySerializer,
        ],
        responses=OpenApiTypes.OBJECT,
    )

    def get(self, request):
        serializer = ReportSummaryQuerySerializer(
            data=request.query_params,
        )
        serializer.is_valid(
            raise_exception=True,
        )
        company_id = (
            serializer.validated_data[
                "company_id"
            ]
        )
        branch_id = (
            serializer.validated_data[
                "branch_id"
            ]
        )
        date_from = (
            serializer.validated_data[
                "date_from"
            ]
        )
        date_to = (
            serializer.validated_data[
                "date_to"
            ]
        )
        start_datetime, end_datetime = (
            build_datetime_range(
                date_from,
                date_to,
            )
        )
        validate_company_branch_access(
            request.user,
            company_id,
            branch_id,
        )
        sales = (
            Sale.objects
            .filter(
                company_id=company_id,
                branch_id=branch_id,
                status=SaleStatus.COMPLETED,
                completed_at__gte=(
                    start_datetime
                ),
                completed_at__lt=(
                    end_datetime
                ),
            )
            .aggregate(
                count=Count("id"),
                total=Sum("total"),
            )
        )
        purchases = (
            Purchase.objects
            .filter(
                company_id=company_id,
                branch_id=branch_id,
                status=PurchaseStatus.COMPLETED,
                purchase_date__range=(
                    date_from,
                    date_to,
                ),
            )
            .aggregate(
                count=Count("id"),
                total=Sum("total"),
            )
        )
        expenses = (
            Expense.objects
            .filter(
                company_id=company_id,
                branch_id=branch_id,
                status=ExpenseStatus.COMPLETED,
                expense_date__range=(
                    date_from,
                    date_to,
                ),
            )
            .aggregate(
                count=Count("id"),
                total=Sum("amount"),
            )
        )
        cash_in = (
            CashMovement.objects
            .filter(
                company_id=company_id,
                branch_id=branch_id,
                direction=(
                    CashMovementDirection.IN
                ),
                created_at__gte=(
                    start_datetime
                ),
                created_at__lt=(
                    end_datetime
                ),
            )
            .aggregate(
                count=Count("id"),
                total=Sum("amount"),
            )
        )
        cash_out = (
            CashMovement.objects
            .filter(
                company_id=company_id,
                branch_id=branch_id,
                direction=(
                    CashMovementDirection.OUT
                ),
                created_at__gte=(
                    start_datetime
                ),
                created_at__lt=(
                    end_datetime
                ),
            )
            .aggregate(
                count=Count("id"),
                total=Sum("amount"),
            )
        )
        cash_in_total = (
            cash_in["total"]
            or Decimal("0.00")
        )
        cash_out_total = (
            cash_out["total"]
            or Decimal("0.00")
        )
        cash_net = (
            cash_in_total
            - cash_out_total
        )
        return Response(
            {
                "period": {
                    "date_from": date_from,
                    "date_to": date_to,
                },
                "company_id": company_id,
                "branch_id": branch_id,
                "sales": {
                    "count": (
                        sales["count"]
                    ),
                    "total": decimal_string(
                        sales["total"],
                    ),
                },
                "purchases": {
                    "count": (
                        purchases["count"]
                    ),
                    "total": decimal_string(
                        purchases["total"],
                    ),
                },
                "expenses": {
                    "count": (
                        expenses["count"]
                    ),
                    "total": decimal_string(
                        expenses["total"],
                    ),
                },
                "cash": {
                    "in": {
                        "count": (
                            cash_in["count"]
                        ),
                        "total": decimal_string(
                            cash_in_total,
                        ),
                    },
                    "out": {
                        "count": (
                            cash_out["count"]
                        ),
                        "total": decimal_string(
                            cash_out_total,
                        ),
                    },
                    "net": decimal_string(
                        cash_net,
                    ),
                },
            }
        )

class ReportDailyView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    @extend_schema(
        parameters=[
            ReportSummaryQuerySerializer,
        ],
        responses=OpenApiTypes.OBJECT,
    )

    def get(self, request):
        serializer = (
            ReportSummaryQuerySerializer(
                data=request.query_params,
            )
        )
        serializer.is_valid(
            raise_exception=True,
        )
        company_id = (
            serializer.validated_data[
                "company_id"
            ]
        )
        branch_id = (
            serializer.validated_data[
                "branch_id"
            ]
        )
        date_from = (
            serializer.validated_data[
                "date_from"
            ]
        )
        date_to = (
            serializer.validated_data[
                "date_to"
            ]
        )
        start_datetime, end_datetime = (
            build_datetime_range(
                date_from,
                date_to,
            )
        )
        validate_company_branch_access(
            request.user,
            company_id,
            branch_id,
        )
        sales_rows = (
            Sale.objects
            .filter(
                company_id=company_id,
                branch_id=branch_id,
                status=SaleStatus.COMPLETED,
                completed_at__gte=(
                    start_datetime
                ),
                completed_at__lt=(
                    end_datetime
                ),
            )
            .annotate(
                date=TruncDate(
                    "completed_at",
                )
            )
            .values(
                "date",
            )
            .annotate(
                count=Count("id"),
                total=Sum("total"),
            )
            .order_by(
                "date",
            )
        )
        purchase_rows = (
            Purchase.objects
            .filter(
                company_id=company_id,
                branch_id=branch_id,
                status=(
                    PurchaseStatus.COMPLETED
                ),
                purchase_date__range=(
                    date_from,
                    date_to,
                ),
            )
            .values(
                "purchase_date",
            )
            .annotate(
                count=Count("id"),
                total=Sum("total"),
            )
            .order_by(
                "purchase_date",
            )
        )
        expense_rows = (
            Expense.objects
            .filter(
                company_id=company_id,
                branch_id=branch_id,
                status=(
                    ExpenseStatus.COMPLETED
                ),
                expense_date__range=(
                    date_from,
                    date_to,
                ),
            )
            .values(
                "expense_date",
            )
            .annotate(
                count=Count("id"),
                total=Sum("amount"),
            )
            .order_by(
                "expense_date",
            )
        )
        cash_in_rows = (
            CashMovement.objects
            .filter(
                company_id=company_id,
                branch_id=branch_id,
                direction=(
                    CashMovementDirection.IN
                ),
                created_at__gte=(
                    start_datetime
                ),
                created_at__lt=(
                    end_datetime
                ),
            )
            .annotate(
                date=TruncDate(
                    "created_at",
                )
            )
            .values(
                "date",
            )
            .annotate(
                count=Count("id"),
                total=Sum("amount"),
            )
            .order_by(
                "date",
            )
        )
        cash_out_rows = (
            CashMovement.objects
            .filter(
                company_id=company_id,
                branch_id=branch_id,
                direction=(
                    CashMovementDirection.OUT
                ),
                created_at__gte=(
                    start_datetime
                ),
                created_at__lt=(
                    end_datetime
                ),
            )
            .annotate(
                date=TruncDate(
                    "created_at",
                )
            )
            .values(
                "date",
            )
            .annotate(
                count=Count("id"),
                total=Sum("amount"),
            )
            .order_by(
                "date",
            )
        )
        sales_map = {
            row["date"]: row
            for row in sales_rows
        }
        purchases_map = {
            row["purchase_date"]: row
            for row in purchase_rows
        }
        expenses_map = {
            row["expense_date"]: row
            for row in expense_rows
        }
        cash_in_map = {
            row["date"]: row
            for row in cash_in_rows
        }
        cash_out_map = {
            row["date"]: row
            for row in cash_out_rows
        }
        results = []
        current_date = date_from
        while current_date <= date_to:
            sales = sales_map.get(
                current_date
            )
            purchases = purchases_map.get(
                current_date
            )
            expenses = expenses_map.get(
                current_date
            )
            cash_in = cash_in_map.get(
                current_date
            )
            cash_out = cash_out_map.get(
                current_date
            )
            cash_in_total = (
                cash_in["total"]
                if cash_in
                else Decimal("0.00")
            )
            cash_out_total = (
                cash_out["total"]
                if cash_out
                else Decimal("0.00")
            )
            results.append(
                {
                    "date": current_date,
                    "sales": {
                        "count": (
                            sales["count"]
                            if sales
                            else 0
                        ),
                        "total": decimal_string(
                            sales["total"]
                            if sales
                            else None
                        ),
                    },
                    "purchases": {
                        "count": (
                            purchases["count"]
                            if purchases
                            else 0
                        ),
                        "total": decimal_string(
                            purchases["total"]
                            if purchases
                            else None
                        ),
                    },
                    "expenses": {
                        "count": (
                            expenses["count"]
                            if expenses
                            else 0
                        ),
                        "total": decimal_string(
                            expenses["total"]
                            if expenses
                            else None
                        ),
                    },
                    "cash": {
                        "in": decimal_string(
                            cash_in_total
                        ),
                        "out": decimal_string(
                            cash_out_total
                        ),
                        "net": decimal_string(
                            cash_in_total
                            - cash_out_total
                        ),
                    },
                }
            )
            current_date += timedelta(
                days=1
            )
        return Response(
            {
                "period": {
                    "date_from": date_from,
                    "date_to": date_to,
                },
                "company_id": company_id,
                "branch_id": branch_id,
                "results": results,
            }
        )

class SalesReportView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    @extend_schema(
        parameters=[
            ReportSummaryQuerySerializer,
        ],
        responses=OpenApiTypes.OBJECT,
    )

    def get(self, request):
        serializer = (
            ReportSummaryQuerySerializer(
                data=request.query_params,
            )
        )
        serializer.is_valid(
            raise_exception=True,
        )
        company_id = (
            serializer.validated_data[
                "company_id"
            ]
        )
        branch_id = (
            serializer.validated_data[
                "branch_id"
            ]
        )
        date_from = (
            serializer.validated_data[
                "date_from"
            ]
        )
        date_to = (
            serializer.validated_data[
                "date_to"
            ]
        )
        start_datetime, end_datetime = (
            build_datetime_range(
                date_from,
                date_to,
            )
        )
        validate_company_branch_access(
            request.user,
            company_id,
            branch_id,
        )
        queryset = get_sales_report_queryset(
            company_id=company_id,
            branch_id=branch_id,
            date_from=date_from,
            date_to=date_to,
        )
        summary = queryset.aggregate(
            count=Count("id"),
            total_amount=Sum("total"),
            average_ticket=Avg("total"),
        )
        paginator = ReportPagination()
        page = paginator.paginate_queryset(
            queryset,
            request,
        )
        results = [
            {
                "id": sale.id,
                "sale_number": (
                    sale.sale_number
                ),
                "customer_name": (
                    sale.customer_name
                ),
                "subtotal": decimal_string(
                    sale.subtotal
                ),
                "discount_total": (
                    decimal_string(
                        sale.discount_total
                    )
                ),
                "tax_total": decimal_string(
                    sale.tax_total
                ),
                "total": decimal_string(
                    sale.total
                ),
                "completed_at": (
                    sale.completed_at
                ),
            }
            for sale in page
        ]
        return Response(
            {
                "period": {
                    "date_from": date_from,
                    "date_to": date_to,
                },
                "company_id": company_id,
                "branch_id": branch_id,
                "summary": {
                    "count": (
                        summary["count"]
                    ),
                    "total": decimal_string(
                        summary["total_amount"]
                    ),
                    "average_ticket": (
                        decimal_string(
                            summary[
                                "average_ticket"
                            ]
                        )
                    ),
                },
                "count": (
                    paginator.page
                    .paginator
                    .count
                ),
                "next": (
                    paginator.get_next_link()
                ),
                "previous": (
                    paginator
                    .get_previous_link()
                ),
                "results": results,
            }
        )

class PurchasesReportView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    @extend_schema(
        parameters=[
            ReportSummaryQuerySerializer,
        ],
        responses=OpenApiTypes.OBJECT,
    )

    def get(self, request):
        serializer = (
            ReportSummaryQuerySerializer(
                data=request.query_params,
            )
        )
        serializer.is_valid(
            raise_exception=True,
        )
        company_id = (
            serializer.validated_data[
                "company_id"
            ]
        )
        branch_id = (
            serializer.validated_data[
                "branch_id"
            ]
        )
        date_from = (
            serializer.validated_data[
                "date_from"
            ]
        )
        date_to = (
            serializer.validated_data[
                "date_to"
            ]
        )
        validate_company_branch_access(
            request.user,
            company_id,
            branch_id,
        )
        queryset = get_purchases_report_queryset(
            company_id=company_id,
            branch_id=branch_id,
            date_from=date_from,
            date_to=date_to,
        )
        summary = queryset.aggregate(
            count=Count("id"),
            total_amount=Sum("total"),
            average_purchase=Avg("total"),
        )
        paginator = ReportPagination()
        page = paginator.paginate_queryset(
            queryset,
            request,
        )
        results = [
            {
                "id": purchase.id,
                "purchase_number": (
                    purchase.purchase_number
                ),
                "supplier_name": (
                    purchase.supplier.name
                ),
                "supplier_invoice_number": (
                    purchase
                    .supplier_invoice_number
                ),
                "purchase_date": (
                    purchase.purchase_date
                ),
                "payment_method": (
                    purchase.payment_method
                ),
                "payment_method_display": (
                    purchase
                    .get_payment_method_display()
                ),
                "subtotal": decimal_string(
                    purchase.subtotal
                ),
                "discount_total": (
                    decimal_string(
                        purchase.discount_total
                    )
                ),
                "tax_total": decimal_string(
                    purchase.tax_total
                ),
                "total": decimal_string(
                    purchase.total
                ),
            }
            for purchase in page
        ]
        return Response(
            {
                "period": {
                    "date_from": date_from,
                    "date_to": date_to,
                },
                "company_id": company_id,
                "branch_id": branch_id,
                "summary": {
                    "count": (
                        summary["count"]
                    ),
                    "total": decimal_string(
                        summary[
                            "total_amount"
                        ]
                    ),
                    "average_purchase": (
                        decimal_string(
                            summary[
                                "average_purchase"
                            ]
                        )
                    ),
                },
                "count": (
                    paginator.page
                    .paginator
                    .count
                ),
                "next": (
                    paginator.get_next_link()
                ),
                "previous": (
                    paginator
                    .get_previous_link()
                ),
                "results": results,
            }
        )

class ExpensesReportView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    @extend_schema(
        parameters=[
            ReportSummaryQuerySerializer,
        ],
        responses=OpenApiTypes.OBJECT,
    )

    def get(self, request):
        serializer = (
            ReportSummaryQuerySerializer(
                data=request.query_params,
            )
        )
        serializer.is_valid(
            raise_exception=True,
        )
        company_id = (
            serializer.validated_data[
                "company_id"
            ]
        )
        branch_id = (
            serializer.validated_data[
                "branch_id"
            ]
        )
        date_from = (
            serializer.validated_data[
                "date_from"
            ]
        )
        date_to = (
            serializer.validated_data[
                "date_to"
            ]
        )
        validate_company_branch_access(
            request.user,
            company_id,
            branch_id,
        )
        queryset = (
            get_expenses_report_queryset(
                company_id=company_id,
                branch_id=branch_id,
                date_from=date_from,
                date_to=date_to,
            )
        )
        summary = queryset.aggregate(
            count=Count("id"),
            total_amount=Sum("amount"),
            average_expense=Avg("amount"),
        )
        paginator = ReportPagination()
        page = paginator.paginate_queryset(
            queryset,
            request,
        )
        results = [
            {
                "id": expense.id,
                "description": (
                    expense.description
                ),
                "expense_date": (
                    expense.expense_date
                ),
                "payment_method": (
                    expense.payment_method
                ),
                "payment_method_display": (
                    expense
                    .get_payment_method_display()
                ),
                "supplier_name": (
                    expense.supplier.name
                    if expense.supplier
                    else None
                ),
                "reference": (
                    expense.reference
                ),
                "amount": decimal_string(
                    expense.amount
                ),
            }
            for expense in page
        ]
        return Response(
            {
                "period": {
                    "date_from": date_from,
                    "date_to": date_to,
                },
                "company_id": company_id,
                "branch_id": branch_id,
                "summary": {
                    "count": (
                        summary["count"]
                    ),
                    "total": decimal_string(
                        summary[
                            "total_amount"
                        ]
                    ),
                    "average_expense": (
                        decimal_string(
                            summary[
                                "average_expense"
                            ]
                        )
                    ),
                },
                "count": (
                    paginator.page
                    .paginator
                    .count
                ),
                "next": (
                    paginator.get_next_link()
                ),
                "previous": (
                    paginator
                    .get_previous_link()
                ),
                "results": results,
            }
        )

class CashReportView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    @extend_schema(
        parameters=[
            ReportSummaryQuerySerializer,
        ],
        responses=OpenApiTypes.OBJECT,
    )

    def get(self, request):
        serializer = (
            ReportSummaryQuerySerializer(
                data=request.query_params,
            )
        )
        serializer.is_valid(
            raise_exception=True,
        )
        company_id = (
            serializer.validated_data[
                "company_id"
            ]
        )
        branch_id = (
            serializer.validated_data[
                "branch_id"
            ]
        )
        date_from = (
            serializer.validated_data[
                "date_from"
            ]
        )
        date_to = (
            serializer.validated_data[
                "date_to"
            ]
        )
        start_datetime, end_datetime = (
            build_datetime_range(
                date_from,
                date_to,
            )
        )
        validate_company_branch_access(
            request.user,
            company_id,
            branch_id,
        )
        queryset = (
            CashMovement.objects
            .filter(
                company_id=company_id,
                branch_id=branch_id,
                created_at__gte=(
                    start_datetime
                ),
                created_at__lt=(
                    end_datetime
                ),
            )
            .order_by(
                "-created_at",
                "-id",
            )
        )
        in_summary = (
            queryset
            .filter(
                direction=(
                    CashMovementDirection.IN
                ),
            )
            .aggregate(
                count=Count("id"),
                total_amount=Sum("amount"),
            )
        )
        out_summary = (
            queryset
            .filter(
                direction=(
                    CashMovementDirection.OUT
                ),
            )
            .aggregate(
                count=Count("id"),
                total_amount=Sum("amount"),
            )
        )
        total_in = (
            in_summary["total_amount"]
            or Decimal("0.00")
        )
        total_out = (
            out_summary["total_amount"]
            or Decimal("0.00")
        )
        net = total_in - total_out
        paginator = ReportPagination()
        page = paginator.paginate_queryset(
            queryset,
            request,
        )
        results = [
            {
                "id": movement.id,
                "direction": (
                    movement.direction
                ),
                "direction_display": (
                    movement
                    .get_direction_display()
                ),
                "movement_type": (
                    movement.movement_type
                ),
                "movement_type_display": (
                    movement
                    .get_movement_type_display()
                ),
                "amount": decimal_string(
                    movement.amount
                ),
                "source_type": (
                    movement.source_type
                ),
                "reference": (
                    movement.reference
                ),
                "notes": movement.notes,
                "created_at": (
                    movement.created_at
                ),
            }
            for movement in page
        ]
        return Response(
            {
                "period": {
                    "date_from": date_from,
                    "date_to": date_to,
                },
                "company_id": company_id,
                "branch_id": branch_id,
                "summary": {
                    "in": {
                        "count": (
                            in_summary[
                                "count"
                            ]
                        ),
                        "total": (
                            decimal_string(
                                total_in
                            )
                        ),
                    },
                    "out": {
                        "count": (
                            out_summary[
                                "count"
                            ]
                        ),
                        "total": (
                            decimal_string(
                                total_out
                            )
                        ),
                    },
                    "net": decimal_string(
                        net
                    ),
                },
                "count": (
                    paginator.page
                    .paginator
                    .count
                ),
                "next": (
                    paginator.get_next_link()
                ),
                "previous": (
                    paginator
                    .get_previous_link()
                ),
                "results": results,
            }
        )

class InventoryReportView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    @extend_schema(
        parameters=[
            InventoryReportQuerySerializer,
        ],
        responses=OpenApiTypes.OBJECT,
    )

    def get(self, request):
        serializer = (
            InventoryReportQuerySerializer(
                data=request.query_params,
            )
        )
        serializer.is_valid(
            raise_exception=True,
        )
        company_id = (
            serializer.validated_data[
                "company_id"
            ]
        )
        branch_id = (
            serializer.validated_data[
                "branch_id"
            ]
        )
        validate_company_branch_access(
            request.user,
            company_id,
            branch_id,
        )
        queryset = (
            ProductStock.objects
            .filter(
                company_id=company_id,
                branch_id=branch_id,
                product__track_inventory=True,
            )
            .select_related(
                "product",
            )
            .order_by(
                "product__name",
            )
        )
        cost_value_expression = (
            ExpressionWrapper(
                F("quantity")
                * F("product__cost_price"),
                output_field=DecimalField(
                    max_digits=24,
                    decimal_places=5,
                ),
            )
        )
        sale_value_expression = (
            ExpressionWrapper(
                F("quantity")
                * F("product__sale_price"),
                output_field=DecimalField(
                    max_digits=24,
                    decimal_places=5,
                ),
            )
        )
        summary = queryset.aggregate(
            products=Count(
                "product_id"
            ),
            total_units=Sum(
                "quantity"
            ),
            total_cost_value=Sum(
                cost_value_expression
            ),
            total_sale_value=Sum(
                sale_value_expression
            ),
        )
        paginator = ReportPagination()
        page = paginator.paginate_queryset(
            queryset,
            request,
        )
        results = [
            {
                "product_id": (
                    stock.product_id
                ),
                "name": stock.product.name,
                "sku": stock.product.sku,
                "barcode": (
                    stock.product.barcode
                ),
                "quantity": quantity_string(
                    stock.quantity
                ),
                "cost_price": (
                    decimal_string(
                        stock.product.cost_price
                    )
                ),
                "sale_price": (
                    decimal_string(
                        stock.product.sale_price
                    )
                ),
                "cost_value": (
                    decimal_string(
                        stock.quantity
                        * stock.product.cost_price
                    )
                ),
                "sale_value": (
                    decimal_string(
                        stock.quantity
                        * stock.product.sale_price
                    )
                ),
            }
            for stock in page
        ]
        return Response(
            {
                "company_id": company_id,
                "branch_id": branch_id,
                "summary": {
                    "products": (
                        summary["products"]
                    ),
                    "total_units": (
                        quantity_string(
                            summary[
                                "total_units"
                            ]
                        )
                    ),
                    "total_cost_value": (
                        decimal_string(
                            summary[
                                "total_cost_value"
                            ]
                        )
                    ),
                    "total_sale_value": (
                        decimal_string(
                            summary[
                                "total_sale_value"
                            ]
                        )
                    ),
                },
                "count": (
                    paginator.page
                    .paginator
                    .count
                ),
                "next": (
                    paginator.get_next_link()
                ),
                "previous": (
                    paginator
                    .get_previous_link()
                ),
                "results": results,
            }
        )

def get_profitability_report_data(
    *,
    company_id,
    branch_id,
    date_from,
    date_to,
):
    start_datetime, end_datetime = build_datetime_range(
        date_from,
        date_to,
    )

    items = SaleItem.objects.filter(
        sale__company_id=company_id,
        sale__branch_id=branch_id,
        sale__status=SaleStatus.COMPLETED,
        sale__completed_at__gte=start_datetime,
        sale__completed_at__lt=end_datetime,
    )

    missing_cost_items = items.filter(
        unit_cost__isnull=True,
    ).count()
    cost_coverage_complete = missing_cost_items == 0

    cost_expression = ExpressionWrapper(
        F("quantity") * F("unit_cost"),
        output_field=DecimalField(
            max_digits=24,
            decimal_places=5,
        ),
    )

    sales_summary = items.aggregate(
        revenue=Sum("line_total"),
        cost_of_sales=Sum(cost_expression),
    )
    revenue = sales_summary["revenue"] or Decimal("0.00")
    cost_of_sales = sales_summary["cost_of_sales"] or Decimal("0.00")

    expenses_summary = Expense.objects.filter(
        company_id=company_id,
        branch_id=branch_id,
        status=ExpenseStatus.COMPLETED,
        expense_date__range=(date_from, date_to),
    ).aggregate(total_amount=Sum("amount"))
    expenses = expenses_summary["total_amount"] or Decimal("0.00")

    gross_profit = None
    operating_result = None
    gross_margin = None

    if cost_coverage_complete:
        gross_profit = revenue - cost_of_sales
        operating_result = gross_profit - expenses
        if revenue > 0:
            gross_margin = (gross_profit / revenue) * Decimal("100")

    summary = {
        "revenue": decimal_string(revenue),
        "cost_of_sales": (
            decimal_string(cost_of_sales)
            if cost_coverage_complete
            else None
        ),
        "gross_profit": (
            decimal_string(gross_profit)
            if gross_profit is not None
            else None
        ),
        "expenses": decimal_string(expenses),
        "operating_result": (
            decimal_string(operating_result)
            if operating_result is not None
            else None
        ),
        "gross_margin": (
            f"{gross_margin:.2f}"
            if gross_margin is not None
            else None
        ),
        "missing_cost_items": missing_cost_items,
        "cost_coverage_complete": cost_coverage_complete,
    }

    products = (
        items.values(
            "product_id",
            "product_name",
            "product_sku",
        )
        .annotate(
            quantity_sold=Sum("quantity"),
            revenue=Sum("line_total"),
            cost_of_sales=Sum(cost_expression),
            missing_cost_items=Count(
                "id",
                filter=Q(unit_cost__isnull=True),
            ),
        )
        .order_by("-revenue", "product_name")
    )

    return summary, products


def serialize_profitability_product(product):
    product_revenue = product["revenue"] or Decimal("0.00")
    product_cost = product["cost_of_sales"] or Decimal("0.00")
    product_cost_complete = product["missing_cost_items"] == 0

    product_profit = None
    product_margin = None

    if product_cost_complete:
        product_profit = product_revenue - product_cost
        if product_revenue > 0:
            product_margin = (
                product_profit / product_revenue
            ) * Decimal("100")

    return {
        "product_id": product["product_id"],
        "product_name": product["product_name"],
        "product_sku": product["product_sku"],
        "quantity_sold": quantity_string(product["quantity_sold"]),
        "revenue": decimal_string(product_revenue),
        "cost_of_sales": (
            decimal_string(product_cost)
            if product_cost_complete
            else None
        ),
        "gross_profit": (
            decimal_string(product_profit)
            if product_profit is not None
            else None
        ),
        "gross_margin": (
            f"{product_margin:.2f}"
            if product_margin is not None
            else None
        ),
        "cost_coverage_complete": product_cost_complete,
    }


class ProfitabilityReportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[ReportSummaryQuerySerializer],
        responses=OpenApiTypes.OBJECT,
    )

    def get(self, request):
        serializer = ReportSummaryQuerySerializer(
            data=request.query_params,
        )
        serializer.is_valid(raise_exception=True)

        company_id = serializer.validated_data["company_id"]
        branch_id = serializer.validated_data["branch_id"]
        date_from = serializer.validated_data["date_from"]
        date_to = serializer.validated_data["date_to"]

        validate_company_branch_access(
            request.user,
            company_id,
            branch_id,
        )

        summary, product_queryset = get_profitability_report_data(
            company_id=company_id,
            branch_id=branch_id,
            date_from=date_from,
            date_to=date_to,
        )

        paginator = ReportPagination()
        page = paginator.paginate_queryset(
            product_queryset,
            request,
        )
        results = [
            serialize_profitability_product(product)
            for product in page
        ]

        return Response(
            {
                "period": {
                    "date_from": date_from,
                    "date_to": date_to,
                },
                "company_id": company_id,
                "branch_id": branch_id,
                "summary": summary,
                "count": paginator.page.paginator.count,
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link(),
                "results": results,
            }
        )


def build_profitability_export_response(
    request,
    *,
    builder,
    content_type,
    extension,
):
    serializer = ReportSummaryQuerySerializer(
        data=request.query_params,
    )
    serializer.is_valid(raise_exception=True)

    company_id = serializer.validated_data["company_id"]
    branch_id = serializer.validated_data["branch_id"]
    date_from = serializer.validated_data["date_from"]
    date_to = serializer.validated_data["date_to"]

    validate_company_branch_access(
        request.user,
        company_id,
        branch_id,
    )

    branch = (
        Branch.objects
        .select_related("company")
        .get(
            id=branch_id,
            company_id=company_id,
        )
    )

    summary, product_queryset = get_profitability_report_data(
        company_id=company_id,
        branch_id=branch_id,
        date_from=date_from,
        date_to=date_to,
    )
    products = [
        serialize_profitability_product(product)
        for product in product_queryset
    ]

    file = builder(
        summary=summary,
        products=products,
        date_from=date_from,
        date_to=date_to,
        company_name=branch.company.name,
        branch_name=branch.name,
        currency=branch.company.currency or "Q",
    )

    filename = f"rentabilidad_{date_from}_{date_to}.{extension}"
    response = HttpResponse(
        file.getvalue(),
        content_type=content_type,
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )
    return response


class ProfitabilityExcelReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return build_profitability_export_response(
            request,
            builder=build_profitability_excel,
            content_type=(
                "application/"
                "vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            extension="xlsx",
        )


class ProfitabilityPdfReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return build_profitability_export_response(
            request,
            builder=build_profitability_pdf,
            content_type="application/pdf",
            extension="pdf",
        )


class SalesExcelReportView(APIView):
    permission_classes = [IsAuthenticated,]

    def get(self, request):
        serializer = (
            ReportSummaryQuerySerializer(
                data=request.query_params,
            )
        )
        serializer.is_valid(
            raise_exception=True,
        )
        company_id = (
            serializer.validated_data[
                "company_id"
            ]
        )
        branch_id = (
            serializer.validated_data[
                "branch_id"
            ]
        )
        date_from = (
            serializer.validated_data[
                "date_from"
            ]
        )
        date_to = (
            serializer.validated_data[
                "date_to"
            ]
        )
        validate_company_branch_access(
            request.user,
            company_id,
            branch_id,
        )
        branch = (
            Branch.objects
            .select_related("company")
            .get(
                id=branch_id,
                company_id=company_id,
            )
        )
        sales = get_sales_report_queryset(
            company_id=company_id,
            branch_id=branch_id,
            date_from=date_from,
            date_to=date_to,
        )
        file = build_sales_excel(
            sales=sales,
            date_from=date_from,
            date_to=date_to,
            company_name=branch.company.name,
            branch_name=branch.name,
        )
        filename = (
            f"ventas_"
            f"{date_from}_"
            f"{date_to}.xlsx"
        )
        response = HttpResponse(
            file.getvalue(),
            content_type=(
                "application/"
                "vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
        response[
            "Content-Disposition"
        ] = (
            f'attachment; filename="{filename}"'
        )
        return response

class SalesPdfReportView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):
        serializer = (
            ReportSummaryQuerySerializer(
                data=request.query_params,
            )
        )
        serializer.is_valid(
            raise_exception=True,
        )
        company_id = (
            serializer.validated_data[
                "company_id"
            ]
        )
        branch_id = (
            serializer.validated_data[
                "branch_id"
            ]
        )
        date_from = (
            serializer.validated_data[
                "date_from"
            ]
        )
        date_to = (
            serializer.validated_data[
                "date_to"
            ]
        )
        validate_company_branch_access(
            request.user,
            company_id,
            branch_id,
        )
        branch = (
            Branch.objects
            .select_related("company")
            .get(
                id=branch_id,
                company_id=company_id,
            )
        )
        sales = get_sales_report_queryset(
            company_id=company_id,
            branch_id=branch_id,
            date_from=date_from,
            date_to=date_to,
        )
        file = build_sales_pdf(
            sales=sales,
            date_from=date_from,
            date_to=date_to,
            company_name=branch.company.name,
            branch_name=branch.name,
        )
        filename = (
            f"ventas_"
            f"{date_from}_"
            f"{date_to}.pdf"
        )
        response = HttpResponse(
            file.getvalue(),
            content_type="application/pdf",
        )
        response[
            "Content-Disposition"
        ] = (
            f'attachment; filename="{filename}"'
        )
        return response

class PurchasesExcelReportView(
    APIView,
):
    permission_classes = [
        IsAuthenticated,
    ]

    @extend_schema(
        parameters=[
            ReportSummaryQuerySerializer,
        ],
        responses=OpenApiTypes.BINARY,
    )

    def get(
        self,
        request,
    ):
        serializer = (
            ReportSummaryQuerySerializer(
                data=request.query_params,
            )
        )
        serializer.is_valid(
            raise_exception=True,
        )
        company_id = (
            serializer.validated_data[
                "company_id"
            ]
        )
        branch_id = (
            serializer.validated_data[
                "branch_id"
            ]
        )
        date_from = (
            serializer.validated_data[
                "date_from"
            ]
        )
        date_to = (
            serializer.validated_data[
                "date_to"
            ]
        )
        validate_company_branch_access(
            request.user,
            company_id,
            branch_id,
        )
        branch = (
            Branch.objects
            .select_related(
                "company",
            )
            .get(
                id=branch_id,
                company_id=company_id,
            )
        )
        purchases = (
            get_purchases_report_queryset(
                company_id=company_id,
                branch_id=branch_id,
                date_from=date_from,
                date_to=date_to,
            )
        )
        file = build_purchases_excel(
            purchases=purchases,
            date_from=date_from,
            date_to=date_to,
            company_name=(
                branch.company.name
            ),
            branch_name=branch.name,
        )
        filename = (
            f"compras_"
            f"{date_from}_"
            f"{date_to}.xlsx"
        )
        response = HttpResponse(
            file.getvalue(),
            content_type=(
                "application/"
                "vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
        response[
            "Content-Disposition"
        ] = (
            f'attachment; filename="{filename}"'
        )
        return response

class PurchasesPdfReportView(
    APIView,
):
    permission_classes = [
        IsAuthenticated,
    ]

    @extend_schema(
        parameters=[
            ReportSummaryQuerySerializer,
        ],
        responses=OpenApiTypes.BINARY,
    )

    def get(
        self,
        request,
    ):
        serializer = (
            ReportSummaryQuerySerializer(
                data=request.query_params,
            )
        )
        serializer.is_valid(
            raise_exception=True,
        )
        company_id = (
            serializer.validated_data[
                "company_id"
            ]
        )
        branch_id = (
            serializer.validated_data[
                "branch_id"
            ]
        )
        date_from = (
            serializer.validated_data[
                "date_from"
            ]
        )
        date_to = (
            serializer.validated_data[
                "date_to"
            ]
        )
        validate_company_branch_access(
            request.user,
            company_id,
            branch_id,
        )
        branch = (
            Branch.objects
            .select_related(
                "company",
            )
            .get(
                id=branch_id,
                company_id=company_id,
            )
        )
        purchases = (
            get_purchases_report_queryset(
                company_id=company_id,
                branch_id=branch_id,
                date_from=date_from,
                date_to=date_to,
            )
        )
        file = build_purchases_pdf(
            purchases=purchases,
            date_from=date_from,
            date_to=date_to,
            company_name=(
                branch.company.name
            ),
            branch_name=branch.name,
        )
        filename = (
            f"compras_"
            f"{date_from}_"
            f"{date_to}.pdf"
        )
        response = HttpResponse(
            file.getvalue(),
            content_type=(
                "application/pdf"
            ),
        )
        response[
            "Content-Disposition"
        ] = (
            f'attachment; filename="{filename}"'
        )
        return response

class ExpensesExcelReportView(
    APIView,
):
    permission_classes = [
        IsAuthenticated,
    ]

    @extend_schema(
        parameters=[
            ReportSummaryQuerySerializer,
        ],
        responses=OpenApiTypes.BINARY,
    )

    def get(
        self,
        request,
    ):
        serializer = (
            ReportSummaryQuerySerializer(
                data=request.query_params,
            )
        )
        serializer.is_valid(
            raise_exception=True,
        )
        company_id = (
            serializer.validated_data[
                "company_id"
            ]
        )
        branch_id = (
            serializer.validated_data[
                "branch_id"
            ]
        )
        date_from = (
            serializer.validated_data[
                "date_from"
            ]
        )
        date_to = (
            serializer.validated_data[
                "date_to"
            ]
        )
        validate_company_branch_access(
            request.user,
            company_id,
            branch_id,
        )
        branch = (
            Branch.objects
            .select_related(
                "company",
            )
            .get(
                id=branch_id,
                company_id=company_id,
            )
        )
        expenses = (
            get_expenses_report_queryset(
                company_id=company_id,
                branch_id=branch_id,
                date_from=date_from,
                date_to=date_to,
            )
        )
        file = build_expenses_excel(
            expenses=expenses,
            date_from=date_from,
            date_to=date_to,
            company_name=(
                branch.company.name
            ),
            branch_name=branch.name,
        )
        filename = (
            f"gastos_"
            f"{date_from}_"
            f"{date_to}.xlsx"
        )
        response = HttpResponse(
            file.getvalue(),
            content_type=(
                "application/"
                "vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
        response[
            "Content-Disposition"
        ] = (
            f'attachment; filename="{filename}"'
        )
        return response

class ExpensesPdfReportView(
    APIView,
):
    permission_classes = [
        IsAuthenticated,
    ]

    @extend_schema(
        parameters=[
            ReportSummaryQuerySerializer,
        ],
        responses=OpenApiTypes.BINARY,
    )

    def get(
        self,
        request,
    ):
        serializer = (
            ReportSummaryQuerySerializer(
                data=request.query_params,
            )
        )
        serializer.is_valid(
            raise_exception=True,
        )
        company_id = (
            serializer.validated_data[
                "company_id"
            ]
        )
        branch_id = (
            serializer.validated_data[
                "branch_id"
            ]
        )
        date_from = (
            serializer.validated_data[
                "date_from"
            ]
        )
        date_to = (
            serializer.validated_data[
                "date_to"
            ]
        )
        validate_company_branch_access(
            request.user,
            company_id,
            branch_id,
        )
        branch = (
            Branch.objects
            .select_related(
                "company",
            )
            .get(
                id=branch_id,
                company_id=company_id,
            )
        )
        expenses = (
            get_expenses_report_queryset(
                company_id=company_id,
                branch_id=branch_id,
                date_from=date_from,
                date_to=date_to,
            )
        )
        file = build_expenses_pdf(
            expenses=expenses,
            date_from=date_from,
            date_to=date_to,
            company_name=(
                branch.company.name
            ),
            branch_name=branch.name,
        )
        filename = (
            f"gastos_"
            f"{date_from}_"
            f"{date_to}.pdf"
        )
        response = HttpResponse(
            file.getvalue(),
            content_type="application/pdf",
        )
        response[
            "Content-Disposition"
        ] = (
            f'attachment; filename="{filename}"'
        )
        return response

class CashExcelReportView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):
        serializer = ReportSummaryQuerySerializer(
            data=request.query_params,
        )
        serializer.is_valid(
            raise_exception=True,
        )
        company_id = serializer.validated_data["company_id"]
        branch_id = serializer.validated_data["branch_id"]
        date_from = serializer.validated_data["date_from"]
        date_to = serializer.validated_data["date_to"]
        validate_company_branch_access(
            request.user,
            company_id,
            branch_id,
        )
        cash_register_id = request.query_params.get(
            "cash_register_id",
        )
        movement_type = request.query_params.get(
            "movement_type",
        )
        direction = request.query_params.get(
            "direction",
        )
        search = request.query_params.get(
            "search",
        )
        branch = (
            Branch.objects
            .select_related(
                "company",
            )
            .get(
                id=branch_id,
                company_id=company_id,
            )
        )
        movements = get_cash_report_queryset(
            company_id=company_id,
            branch_id=branch_id,
            date_from=date_from,
            date_to=date_to,
            cash_register_id=cash_register_id,
            movement_type=movement_type,
            direction=direction,
            search=search,
        )
        file = build_cash_excel(
            movements=movements,
            date_from=date_from,
            date_to=date_to,
            company_name=branch.company.name,
            branch_name=branch.name,
        )
        filename = (
            f"movimientos_caja_"
            f"{date_from}_"
            f"{date_to}.xlsx"
        )
        response = HttpResponse(
            file.getvalue(),
            content_type=(
                "application/"
                "vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
        response[
            "Content-Disposition"
        ] = ( f'attachment; filename="{filename}"' )
        return response

class CashPdfReportView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):
        serializer = ReportSummaryQuerySerializer(
            data=request.query_params,
        )
        serializer.is_valid(
            raise_exception=True,
        )
        company_id = serializer.validated_data["company_id"]
        branch_id = serializer.validated_data["branch_id"]
        date_from = serializer.validated_data["date_from"]
        date_to = serializer.validated_data["date_to"]
        validate_company_branch_access(
            request.user,
            company_id,
            branch_id,
        )
        cash_register_id = request.query_params.get(
            "cash_register_id",
        )
        movement_type = request.query_params.get(
            "movement_type",
        )
        direction = request.query_params.get(
            "direction",
        )
        search = request.query_params.get(
            "search",
        )
        branch = (
            Branch.objects
            .select_related(
                "company",
            )
            .get(
                id=branch_id,
                company_id=company_id,
            )
        )
        movements = get_cash_report_queryset(
            company_id=company_id,
            branch_id=branch_id,
            date_from=date_from,
            date_to=date_to,
            cash_register_id=cash_register_id,
            movement_type=movement_type,
            direction=direction,
            search=search,
        )
        file = build_cash_pdf(
            movements=movements,
            date_from=date_from,
            date_to=date_to,
            company_name=branch.company.name,
            branch_name=branch.name,
        )
        filename = (
            f"movimientos_caja_"
            f"{date_from}_"
            f"{date_to}.pdf"
        )
        response = HttpResponse(
            file.getvalue(),
            content_type="application/pdf",
        )
        response[
            "Content-Disposition"
        ] = (
            f'attachment; filename="{filename}"'
        )
        return response
