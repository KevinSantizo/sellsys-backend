
from datetime import datetime, time, timedelta
from decimal import Decimal
from django.http import HttpResponse
from django.db.models import Sum
from django.db.models.functions import (TruncDate, TruncMonth,)
from django.utils import timezone

from rest_framework.response import Response
from rest_framework import status

from django.db.models import (Count, Q,)
from rest_framework import (filters, mixins, status, viewsets,)
from rest_framework.permissions import (IsAuthenticated,)
from rest_framework.response import Response

from branches.models import (BranchMembership,)
from companies.models import (CompanyMembership,)

from .access import (get_membership_role_code,)
from .models import Sale
from .pagination import SalePagination
from .serializers import (SaleCheckoutSerializer,SaleDetailSerializer,SaleListSerializer,)
from .models import Sale, SaleStatus, PaymentMethod

from django.db import transaction

from rest_framework.exceptions import ValidationError

from cash.models import CashMovement, CashMovementType, CashMovementSource, CashSessionStatus
from cash.services import get_open_cash_session, reverse_cash_movement
from inventory.services import InventoryStockError, restore_sale_stock
from common.access import (
    get_user_company_branch_scope,
    validate_company_branch_access,
)
from .services.sale_receipt import build_sale_receipt_pdf


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
        serializer = SaleCheckoutSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )

        serializer.is_valid(
            raise_exception=True,
        )

        sale = serializer.save()

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

            original_cash_movement = None
            cash_session = None

            if cash_effect > Decimal("0.00"):
                try:
                    original_cash_movement = CashMovement.objects.select_for_update().select_related(
                        "cash_session").get(
                        source_type=CashMovementSource.SALE,
                        source_id=sale.id,
                        movement_type=CashMovementType.SALE,
                    )
                except CashMovement.DoesNotExist:
                    raise ValidationError({
                        "detail": "No se encontró el movimiento de caja original de la venta."
                    })

                original_cash_session = original_cash_movement.cash_session

                if original_cash_session.status == CashSessionStatus.OPEN:
                    cash_session = get_open_cash_session(
                        cash_session_id=original_cash_session.id,
                        company=sale.company,
                        branch=sale.branch,
                    )
                else:
                    cash_session = get_open_cash_session(
                        cash_session_id=request.data.get("cash_session_id"),
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

            if original_cash_movement and cash_session:
                reverse_cash_movement(
                    original_movement=original_cash_movement,
                    cash_session=cash_session,
                    user=request.user,
                    reference=sale.sale_number,
                    notes=f"Reversión por cancelación de venta {sale.sale_number}",
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


