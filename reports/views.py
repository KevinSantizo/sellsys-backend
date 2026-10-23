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

        queryset = (
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
            .order_by(
                "-completed_at",
                "-id",
            )
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

        queryset = (
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
            .select_related(
                "supplier",
            )
            .order_by(
                "-purchase_date",
                "-created_at",
            )
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
            .select_related(
                "supplier",
            )
            .order_by(
                "-expense_date",
                "-created_at",
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


class ProfitabilityReportView(APIView):
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

        items = (
            SaleItem.objects
            .filter(
                sale__company_id=(
                    company_id
                ),
                sale__branch_id=(
                    branch_id
                ),
                sale__status=(
                    SaleStatus.COMPLETED
                ),
                sale__completed_at__gte=(
                    start_datetime
                ),
                sale__completed_at__lt=(
                    end_datetime
                ),
            )
        )

        missing_cost_items = (
            items
            .filter(
                unit_cost__isnull=True,
            )
            .count()
        )

        cost_coverage_complete = (
            missing_cost_items == 0
        )

        cost_expression = (
            ExpressionWrapper(
                F("quantity")
                * F("unit_cost"),
                output_field=DecimalField(
                    max_digits=24,
                    decimal_places=5,
                ),
            )
        )

        sales_summary = items.aggregate(
            revenue=Sum(
                "line_total"
            ),
            cost_of_sales=Sum(
                cost_expression
            ),
        )

        revenue = (
            sales_summary["revenue"]
            or Decimal("0.00")
        )

        cost_of_sales = (
            sales_summary[
                "cost_of_sales"
            ]
            or Decimal("0.00")
        )

        expenses_summary = (
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
            .aggregate(
                total_amount=Sum(
                    "amount"
                ),
            )
        )

        expenses = (
            expenses_summary[
                "total_amount"
            ]
            or Decimal("0.00")
        )

        gross_profit = None
        operating_result = None
        gross_margin = None

        if cost_coverage_complete:
            gross_profit = (
                revenue
                - cost_of_sales
            )

            operating_result = (
                gross_profit
                - expenses
            )

            if revenue > 0:
                gross_margin = (
                    gross_profit
                    / revenue
                ) * Decimal("100")

        product_queryset = (
            items
            .values(
                "product_id",
                "product_name",
                "product_sku",
            )
            .annotate(
                quantity_sold=Sum(
                    "quantity"
                ),
                revenue=Sum(
                    "line_total"
                ),
                cost_of_sales=Sum(
                    cost_expression
                ),
                missing_cost_items=Count(
                    "id",
                    filter=Q(
                        unit_cost__isnull=True,
                    ),
                ),
            )
            .order_by(
                "-revenue",
                "product_name",
            )
        )

        paginator = ReportPagination()

        page = paginator.paginate_queryset(
            product_queryset,
            request,
        )

        results = []

        for product in page:
            product_revenue = (
                product["revenue"]
                or Decimal("0.00")
            )

            product_cost = (
                product["cost_of_sales"]
                or Decimal("0.00")
            )

            product_cost_complete = (
                product[
                    "missing_cost_items"
                ]
                == 0
            )

            product_profit = None
            product_margin = None

            if product_cost_complete:
                product_profit = (
                    product_revenue
                    - product_cost
                )

                if product_revenue > 0:
                    product_margin = (
                        product_profit
                        / product_revenue
                    ) * Decimal("100")

            results.append(
                {
                    "product_id": (
                        product[
                            "product_id"
                        ]
                    ),
                    "product_name": (
                        product[
                            "product_name"
                        ]
                    ),
                    "product_sku": (
                        product[
                            "product_sku"
                        ]
                    ),
                    "quantity_sold": (
                        quantity_string(
                            product[
                                "quantity_sold"
                            ]
                        )
                    ),
                    "revenue": (
                        decimal_string(
                            product_revenue
                        )
                    ),
                    "cost_of_sales": (
                        decimal_string(
                            product_cost
                        )
                        if (
                            product_cost_complete
                        )
                        else None
                    ),
                    "gross_profit": (
                        decimal_string(
                            product_profit
                        )
                        if (
                            product_profit
                            is not None
                        )
                        else None
                    ),
                    "gross_margin": (
                        f"{product_margin:.2f}"
                        if (
                            product_margin
                            is not None
                        )
                        else None
                    ),
                    "cost_coverage_complete": (
                        product_cost_complete
                    ),
                }
            )

        return Response(
            {
                "period": {
                    "date_from": date_from,
                    "date_to": date_to,
                },
                "company_id": company_id,
                "branch_id": branch_id,
                "summary": {
                    "revenue": (
                        decimal_string(
                            revenue
                        )
                    ),
                    "cost_of_sales": (
                        decimal_string(
                            cost_of_sales
                        )
                        if (
                            cost_coverage_complete
                        )
                        else None
                    ),
                    "gross_profit": (
                        decimal_string(
                            gross_profit
                        )
                        if (
                            gross_profit
                            is not None
                        )
                        else None
                    ),
                    "expenses": (
                        decimal_string(
                            expenses
                        )
                    ),
                    "operating_result": (
                        decimal_string(
                            operating_result
                        )
                        if (
                            operating_result
                            is not None
                        )
                        else None
                    ),
                    "gross_margin": (
                        f"{gross_margin:.2f}"
                        if (
                            gross_margin
                            is not None
                        )
                        else None
                    ),
                    "missing_cost_items": (
                        missing_cost_items
                    ),
                    "cost_coverage_complete": (
                        cost_coverage_complete
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