
from datetime import datetime, time, timedelta
from decimal import Decimal
from django.http import HttpResponse
from django.db.models import Sum, F, OuterRef, Subquery, Value, DecimalField
from django.db.models.functions import (TruncDate, TruncMonth, Coalesce)
from django.utils import timezone

from rest_framework.response import Response
from rest_framework import status

from django.db.models import (
    Avg,
    Count,
    DecimalField,
    ExpressionWrapper,
    Exists,
    F,
    IntegerField,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Sum,
    Value,
)

from rest_framework import (filters, mixins, status, viewsets,)
from rest_framework.permissions import (IsAuthenticated,)
from rest_framework.response import Response

from branches.models import (BranchMembership,)
from companies.models import (CompanyMembership,)

from .access import (get_membership_role_code,)
from .models import Sale
from .pagination import SalePagination, PageNumberPagination
from .serializers import (CustomerSerializer, SaleCheckoutSerializer, SaleDetailSerializer, SaleListSerializer, SalePaymentSerializer)
from .models import Sale, SaleStatus, PaymentMethod, Customer, Payment, SaleItem

from django.db import transaction


from cash.models import CashMovement, CashMovementType, CashMovementSource, CashSessionStatus, CashMovementDirection
from cash.services import get_open_cash_session, reverse_cash_movement, create_cash_movement
from inventory.services import InventoryStockError, restore_sale_stock
from common.access import (
    get_user_company_branch_scope,
    validate_company_branch_access,
)
from .services.sale_receipt import build_sale_receipt_pdf

from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)


class CustomerPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class CustomerViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    pagination_class = CustomerPagination
    permission_classes = (IsAuthenticated,)
    serializer_class = CustomerSerializer

    filter_backends = (
        filters.SearchFilter,
        filters.OrderingFilter,
    )

    search_fields = (
        "first_name",
        "last_name",
        "phone",
    )

    ordering_fields = (
        "first_name",
        "last_name",
        "created_at",
        "updated_at",
    )

    ordering = (
        "last_name",
        "first_name",
    )

    def get_queryset(self):
        company_ids = (
            CompanyMembership.objects
            .filter(
                user=self.request.user,
                is_active=True,
                company__is_active=True,
            )
            .values_list("company_id", flat=True)
        )

        queryset = Customer.objects.filter(
            company_id__in=company_ids,
        )

        company_id = self.request.query_params.get("company_id")

        if company_id:
            queryset = queryset.filter(
                company_id=company_id,
            )

        return queryset

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]

        has_access = CompanyMembership.objects.filter(
            user=self.request.user,
            company=company,
            is_active=True,
            company__is_active=True,
        ).exists()

        if not has_access:
            raise PermissionDenied(
                "No tienes acceso a esta empresa."
            )

        serializer.save()

    def perform_update(self, serializer):
        customer = serializer.instance

        serializer.save(
            company=customer.company,
        )

class SaleViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (
        IsAuthenticated,
    )

    pagination_class = SalePagination

    filter_backends = (
        filters.SearchFilter,
        filters.OrderingFilter,
    )

    search_fields = (
        "sale_number",
        "customer_name",
        "customer_tax_id",
        "created_by__first_name",
        "created_by__last_name",
        "created_by__email",
    )

    ordering_fields = (
        "sale_number",
        "subtotal",
        "discount_total",
        "total",
        "completed_at",
        "created_at",
    )

    ordering = (
        "-created_at",
        "-id",
    )

    def get_serializer_class(self):
        if self.action == "list":
            return SaleListSerializer

        return SaleDetailSerializer


    def get_queryset(self):
        owner_company_ids, assigned_branch_ids = get_user_company_branch_scope(
            self.request.user
        )

        queryset = (
            Sale.objects
            .filter(
                Q(
                    company_id__in=owner_company_ids,
                )
                | Q(
                    branch_id__in=assigned_branch_ids,
                )
            )
            .select_related(
                "company",
                "branch",
                "created_by",
            )
            .annotate(
                item_count=Count(
                    "items",
                    distinct=True,
                )
            )
        )

        company_id = self.request.query_params.get(
            "company_id"
        )

        branch_id = self.request.query_params.get(
            "branch_id"
        )

        sale_status = self.request.query_params.get(
            "status"
        )

        if company_id:
            queryset = queryset.filter(
                company_id=company_id,
            )

        if branch_id:
            queryset = queryset.filter(
                branch_id=branch_id,
            )

        if sale_status:
            queryset = queryset.filter(
                status=sale_status,
            )

        return queryset.distinct()

    def accounts_receivable(self, request):
        payment_total_subquery = (
            Payment.objects
            .filter(
                sale_id=OuterRef("pk"),
            )
            .values("sale_id")
            .annotate(
                total=Sum("amount"),
            )
            .values("total")[:1]
        )

        queryset = (
            self.get_queryset()
            .filter(
                status=SaleStatus.COMPLETED,
                customer__isnull=False,
            )
            .select_related("customer")
            .prefetch_related(
                "items",
                "payments",
            )
            .annotate(
                paid_total_for_receivable=Coalesce(
                    Subquery(
                        payment_total_subquery,
                        output_field=DecimalField(
                            max_digits=12,
                            decimal_places=2,
                        ),
                    ),
                    F("amount_received"),
                    Value(Decimal("0.00")),
                    output_field=DecimalField(
                        max_digits=12,
                        decimal_places=2,
                    ),
                )
            )
            .filter(
                paid_total_for_receivable__lt=F("total"),
            )
        )

        customer_id = request.query_params.get("customer_id")

        if customer_id:
            queryset = queryset.filter(
                customer_id=customer_id,
            )

        queryset = self.filter_queryset(queryset)

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = SaleDetailSerializer(
                page,
                many=True,
                context=self.get_serializer_context(),
            )

            return self.get_paginated_response(
                serializer.data,
            )

        serializer = SaleDetailSerializer(
            queryset,
            many=True,
            context=self.get_serializer_context(),
        )

        return Response(serializer.data)

    def weekly_summary(self, request):
        company_id = request.query_params.get("company_id")

        branch_id = request.query_params.get("branch_id")

        if not company_id:
            return Response(
                {
                    "detail": (
                        "El parámetro company_id "
                        "es obligatorio."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not branch_id:
            return Response(
                {
                    "detail": (
                        "El parámetro branch_id "
                        "es obligatorio."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        validate_company_branch_access(
            request.user,
            company_id,
            branch_id,
        )

        today = timezone.localdate()

        week_start = (today - timedelta(days=today.weekday()))
        next_week_start = (week_start + timedelta(days=7))
        week_end = ( next_week_start - timedelta(days=1))
        current_timezone = (timezone.get_current_timezone())
        week_start_datetime = (timezone.make_aware(datetime.combine(week_start, time.min,),current_timezone,))
        next_week_start_datetime = (timezone.make_aware(datetime.combine(next_week_start,time.min,),current_timezone,))

        queryset = (
            self.get_queryset()
            .filter(
                company_id=company_id,
                branch_id=branch_id,
                status=SaleStatus.COMPLETED,
                completed_at__gte=(week_start_datetime),
                completed_at__lt=(next_week_start_datetime),
            )
        )

        sales_by_day = (
            queryset
            .annotate(
                sale_date=TruncDate(
                    "completed_at",
                    tzinfo=current_timezone,
                )
            )
            .values("sale_date")
            .annotate(
                total=Sum("total"),
                sales_count=Count(
                    "id",
                    distinct=True,
                ),
            )
            .order_by("sale_date")
        )

        sales_data_by_date = {
            row["sale_date"]: {
                "total": (
                        row["total"]
                        or Decimal("0.00")
                ),
                "sales_count": (
                        row["sales_count"]
                        or 0
                ),
            }
            for row in sales_by_day
        }

        day_names = (
            "Lun",
            "Mar",
            "Mié",
            "Jue",
            "Vie",
            "Sáb",
            "Dom",
        )

        days = []
        weekly_total = Decimal("0.00")
        weekly_sales_count = 0

        for index in range(7):
            current_date = (
                    week_start
                    + timedelta(days=index)
            )

            day_data = sales_data_by_date.get(
                current_date,
                {
                    "total": Decimal("0.00"),
                    "sales_count": 0,
                },
            )

            daily_total = day_data["total"]
            daily_sales_count = (
                day_data["sales_count"]
            )

            weekly_total += daily_total
            weekly_sales_count += (
                daily_sales_count
            )

            days.append(
                {
                    "date": (
                        current_date.isoformat()
                    ),
                    "day": day_names[index],
                    "sales_count": (
                        daily_sales_count
                    ),
                    "total": str(
                        daily_total.quantize(
                            Decimal("0.01")
                        )
                    ),
                }
            )

        return Response(
            {
                "week_start": (
                    week_start.isoformat()
                ),
                "week_end": (
                    week_end.isoformat()
                ),
                "sales_count": (
                    weekly_sales_count
                ),
                "total": str(
                    weekly_total.quantize(
                        Decimal("0.01")
                    )
                ),
                "days": days,
            }
        )

    def yearly_summary(self, request):
        company_id = request.query_params.get(
            "company_id"
        )

        branch_id = request.query_params.get(
            "branch_id"
        )

        if not company_id:
            return Response(
                {
                    "detail": (
                        "El parámetro company_id "
                        "es obligatorio."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not branch_id:
            return Response(
                {
                    "detail": (
                        "El parámetro branch_id "
                        "es obligatorio."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        print("USER ID:", request.user.id)
        print("USER EMAIL:", request.user.email)
        print("COMPANY ID:", company_id)
        print("BRANCH ID:", branch_id)

        validate_company_branch_access(
            request.user,
            company_id,
            branch_id,
        )

        today = timezone.localdate()

        year = today.year

        year_start = today.replace(
            month=1,
            day=1,
        )

        next_year_start = year_start.replace(
            year=year + 1,
        )

        current_timezone = (
            timezone.get_current_timezone()
        )

        year_start_datetime = (
            timezone.make_aware(
                datetime.combine(
                    year_start,
                    time.min,
                ),
                current_timezone,
            )
        )

        next_year_start_datetime = (
            timezone.make_aware(
                datetime.combine(
                    next_year_start,
                    time.min,
                ),
                current_timezone,
            )
        )

        queryset = (
            self.get_queryset()
            .filter(
                company_id=company_id,
                branch_id=branch_id,
                status=SaleStatus.COMPLETED,
                completed_at__gte=(
                    year_start_datetime
                ),
                completed_at__lt=(
                    next_year_start_datetime
                ),
            )
        )

        sales_by_month = (
            queryset
            .annotate(
                sale_month=TruncMonth(
                    "completed_at",
                    tzinfo=current_timezone,
                )
            )
            .values("sale_month")
            .annotate(
                total=Sum("total"),
                sales_count=Count(
                    "id",
                    distinct=True,
                ),
            )
            .order_by("sale_month")
        )

        sales_data_by_month = {
            row["sale_month"].month: {
                "total": (
                        row["total"]
                        or Decimal("0.00")
                ),
                "sales_count": (
                        row["sales_count"]
                        or 0
                ),
            }
            for row in sales_by_month
        }

        month_names = (
            "Ene",
            "Feb",
            "Mar",
            "Abr",
            "May",
            "Jun",
            "Jul",
            "Ago",
            "Sep",
            "Oct",
            "Nov",
            "Dic",
        )

        months = []

        yearly_total = Decimal("0.00")
        yearly_sales_count = 0

        for index in range(12):
            month_number = index + 1

            month_data = (
                sales_data_by_month.get(
                    month_number,
                    {
                        "total": Decimal("0.00"),
                        "sales_count": 0,
                    },
                )
            )

            monthly_total = (
                month_data["total"]
            )

            monthly_sales_count = (
                month_data["sales_count"]
            )

            yearly_total += monthly_total

            yearly_sales_count += (
                monthly_sales_count
            )

            months.append(
                {
                    "month_number": (
                        month_number
                    ),
                    "month": (
                        month_names[index]
                    ),
                    "sales_count": (
                        monthly_sales_count
                    ),
                    "total": str(
                        monthly_total.quantize(
                            Decimal("0.01")
                        )
                    ),
                }
            )

        return Response(
            {
                "year": year,
                "sales_count": (
                    yearly_sales_count
                ),
                "total": str(
                    yearly_total.quantize(
                        Decimal("0.01")
                    )
                ),
                "months": months,
            }
        )

    def checkout(self, request):
        print("CHECKOUT EJECUTADO")
        print("PATH:", request.path)
        print("METHOD:", request.method)
        print("DATA:", request.data)
        serializer = SaleCheckoutSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )

        serializer.is_valid(
            raise_exception=True,
        )

        sale = serializer.save()

        print(
            "SALE DEVOLVED:",
            sale.id,
            sale.sale_number,
            sale.status,
            sale.created_at,
        )

        response_serializer = (
            SaleDetailSerializer(
                sale,
                context=(
                    self.get_serializer_context()
                ),
            )
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )

    def receipt(self, request, pk=None):
        try:
            sale = (
                self.get_queryset()
                .prefetch_related(
                    "items",
                    "payments",
                )
                .get(pk=pk)
            )
        except Sale.DoesNotExist:
            return Response(
                {
                    "detail": (
                        "La venta no existe o no tienes "
                        "acceso a ella."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if sale.status != SaleStatus.COMPLETED:
            return Response(
                {
                    "detail": (
                        "Solo se puede generar el comprobante "
                        "de una venta completada."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        pdf = build_sale_receipt_pdf(sale)

        filename = f"comprobante-{sale.sale_number}.pdf"

        response = HttpResponse(
            pdf,
            content_type="application/pdf",
        )

        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response


    def add_payment(self, request, pk=None):
        input_serializer = SalePaymentSerializer(
            data=request.data,
        )
        input_serializer.is_valid(
            raise_exception=True,
        )

        payment_data = input_serializer.validated_data

        with transaction.atomic():
            try:
                sale = (
                    self.get_queryset()
                    .select_for_update()
                    .get(pk=pk)
                )
            except Sale.DoesNotExist:
                return Response(
                    {
                        "detail": (
                            "La venta no existe "
                            "o no tienes acceso a ella."
                        )
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            if sale.status != SaleStatus.COMPLETED:
                raise ValidationError({
                    "detail": (
                        "Solo puedes registrar abonos "
                        "en ventas completadas."
                    )
                })

            if not sale.customer_id:
                raise ValidationError({
                    "customer_id": (
                        "La venta no tiene un cliente "
                        "asociado."
                    )
                })

            paid_total = (
                    sale.payments.aggregate(
                        total=Sum("amount"),
                    )["total"]
                    or sale.amount_received
                    or Decimal("0.00")
            )

            balance_due = sale.total - paid_total
            amount = payment_data["amount"]

            if balance_due <= Decimal("0.00"):
                raise ValidationError({
                    "amount": "La venta ya está pagada."
                })

            if amount > balance_due:
                raise ValidationError({
                    "amount": (
                        f"El abono no puede superar "
                        f"el saldo pendiente de {balance_due}."
                    )
                })

            cash_session = None

            if payment_data["method"] == PaymentMethod.CASH:
                cash_session = get_open_cash_session(
                    cash_session_id=payment_data.get(
                        "cash_session_id",
                    ),
                    company=sale.company,
                    branch=sale.branch,
                )

            payment = Payment.objects.create(
                sale=sale,
                created_by=request.user,
                method=payment_data["method"],
                amount=amount,
                reference=payment_data.get(
                    "reference",
                    "",
                ),
            )

            sale.amount_received = paid_total + amount
            sale.change_amount = Decimal("0.00")
            sale.save(
                update_fields=[
                    "amount_received",
                    "change_amount",
                    "updated_at",
                ]
            )

            if cash_session:
                create_cash_movement(
                    cash_session=cash_session,
                    direction=CashMovementDirection.IN,
                    movement_type=CashMovementType.SALE,
                    amount=amount,
                    source_type=CashMovementSource.SALE,
                    source_id=payment.id,
                    reference=sale.sale_number,
                    notes=(
                        f"Abono de venta "
                        f"{sale.sale_number}"
                    ),
                    user=request.user,
                )

        return Response(
            SaleDetailSerializer(
                sale,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_200_OK,
        )


    def cancel(self, request, pk=None):
        with transaction.atomic():
            owner_company_ids, assigned_branch_ids = (
                get_user_company_branch_scope(
                    request.user,
                )
            )

            try:
                sale = (
                    Sale.objects
                    .select_for_update()
                    .filter(
                        Q(
                            company_id__in=(
                                owner_company_ids
                            ),
                        )
                        | Q(
                            branch_id__in=(
                                assigned_branch_ids
                            ),
                        )
                    )
                    .get(
                        pk=pk,
                    )
                )
            except Sale.DoesNotExist:
                return Response(
                    {
                        "detail": (
                            "La venta no existe o "
                            "no tienes acceso a ella."
                        )
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            if sale.status == SaleStatus.CANCELLED:
                return Response(
                    {"detail": "La venta ya está cancelada."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if sale.status != SaleStatus.COMPLETED:
                return Response(
                    {"detail": "Solo se pueden cancelar ventas completadas."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            cash_total = sale.payments.filter(method=PaymentMethod.CASH).aggregate(total=Sum("amount"))[
                             "total"] or Decimal("0.00")
            cash_effect = cash_total - sale.change_amount

            original_cash_movements = []
            cash_session = None

            if cash_effect > Decimal("0.00"):
                payment_ids = list(
                    sale.payments.values_list(
                        "id",
                        flat=True,
                    )
                )

                source_ids = [
                    sale.id,
                    *payment_ids,
                ]

                original_cash_movements = list(
                    CashMovement.objects
                    .select_for_update()
                    .select_related("cash_session")
                    .filter(
                        source_type=CashMovementSource.SALE,
                        source_id__in=source_ids,
                        movement_type=CashMovementType.SALE,
                    )
                    .order_by(
                        "created_at",
                        "id",
                    )
                )

                if not original_cash_movements:
                    raise ValidationError({
                        "detail": (
                            "No se encontraron los movimientos "
                            "de caja de la venta."
                        )
                    })

                original_cash_session = next(
                    (
                        movement.cash_session
                        for movement in original_cash_movements
                        if movement.cash_session.status
                           == CashSessionStatus.OPEN
                    ),
                    None,
                )

                if original_cash_session:
                    cash_session = get_open_cash_session(
                        cash_session_id=original_cash_session.id,
                        company=sale.company,
                        branch=sale.branch,
                    )
                else:
                    cash_session = get_open_cash_session(
                        cash_session_id=request.data.get(
                            "cash_session_id",
                        ),
                        company=sale.company,
                        branch=sale.branch,
                    )

            try:
                restore_sale_stock(
                    sale=sale,
                    user=request.user,
                )
            except InventoryStockError as error:
                raise ValidationError({
                    "detail": str(error)
                }) from error

            if cash_session and original_cash_movements:
                for original_cash_movement in original_cash_movements:
                    reverse_cash_movement(
                        original_movement=original_cash_movement,
                        cash_session=cash_session,
                        user=request.user,
                        reference=sale.sale_number,
                        notes=(
                            f"Reversión por cancelación "
                            f"de venta {sale.sale_number}"
                        ),
                    )

            sale.mark_as_cancelled()
            sale.save(update_fields=["status", "cancelled_at", "updated_at"])

        return Response(
            SaleDetailSerializer(
                sale,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_200_OK,
        )


