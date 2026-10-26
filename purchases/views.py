from django.shortcuts import render
from rest_framework.exceptions import ValidationError

from decimal import Decimal
from django.db import transaction
from django.db.models import Q
from rest_framework import filters, mixins, serializers, status, viewsets
from rest_framework import (filters, mixins, viewsets,)
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from companies.models import CompanyMembership
from branches.models import BranchMembership
from companies.models import Company
from .models import Supplier
from .serializers import SupplierSerializer

from rest_framework.pagination import PageNumberPagination
from .serializers import PurchaseSerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from inventory.models import InventoryMovement, InventoryMovementType, ProductStock
from cash.models import CashMovement, CashMovementDirection, CashMovementType, CashMovementSource, CashSessionStatus
from cash.services import get_open_cash_session, create_cash_movement, reverse_cash_movement
from .models import Purchase, PurchaseStatus, PurchasePaymentMethod

from common.access import (
    get_user_company_branch_scope,
    validate_company_branch_access,
)
from django.db.models import IntegerField, Max
from django.db.models.functions import Cast, Substr


# Create your views here.

class PurchasePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class SupplierPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

class SupplierViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    pagination_class = SupplierPagination
    permission_classes = (IsAuthenticated,)

    serializer_class = SupplierSerializer

    filter_backends = (filters.SearchFilter, filters.OrderingFilter,)

    search_fields = (
        "name",
        "tax_id",
        "contact_name",
        "phone",
        "email",
    )

    ordering_fields = (
        "name",
        "created_at",
        "updated_at",
    )

    ordering = (
        "name",
    )

    def get_queryset(self):
        user = self.request.user

        company_ids = (
            CompanyMembership.objects
            .filter(
                user=user,
                is_active=True,
                company__is_active=True,
            )
            .values_list(
                "company_id",
                flat=True,
            )
        )

        queryset = Supplier.objects.filter(
            company_id__in=company_ids,
        )

        company_id = (
            self.request.query_params.get(
                "company_id"
            )
        )

        is_active = (
            self.request.query_params.get(
                "is_active"
            )
        )

        if company_id:
            queryset = queryset.filter(
                company_id=company_id,
            )

        if is_active is not None:
            if is_active.lower() == "true":
                queryset = queryset.filter(
                    is_active=True,
                )

            elif is_active.lower() == "false":
                queryset = queryset.filter(
                    is_active=False,
                )

        return queryset

    def perform_create(self, serializer):
        company = (
            serializer.validated_data[
                "company"
            ]
        )

        has_access = (
            CompanyMembership.objects
            .filter(
                user=self.request.user,
                company=company,
                is_active=True,
                company__is_active=True,
            )
            .exists()
        )

        if not has_access:
            raise PermissionDenied(
                (
                    "No tienes acceso a "
                    "esta empresa."
                )
            )

        serializer.save()

    def perform_update(self, serializer):
        supplier = serializer.instance

        serializer.save(
            company=supplier.company,
        )


def format_quantity(value):
    value = Decimal(value)

    if value == value.to_integral():
        return str(int(value))

    return format(value.normalize(), "f")

class PurchaseViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = PurchaseSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = PurchasePagination

    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    search_fields = [
        "purchase_number",
        "supplier_invoice_number",
        "supplier__name",
        "notes",
    ]

    ordering_fields = [
        "purchase_date",
        "total",
        "created_at",
        "updated_at",
    ]

    ordering = ["-purchase_date", "-created_at"]

    def get_queryset(self):
        user = self.request.user

        owner_company_ids, assigned_branch_ids = get_user_company_branch_scope(
            self.request.user
        )

        queryset = Purchase.objects.filter(
            Q(company_id__in=owner_company_ids)
            | Q(branch_id__in=assigned_branch_ids)
        ).select_related(
            "company",
            "branch",
            "supplier",
            "created_by",
        ).prefetch_related(
            "items__product",
        ).distinct()

        company_id = self.request.query_params.get("company_id")
        branch_id = self.request.query_params.get("branch_id")
        supplier_id = self.request.query_params.get("supplier_id")
        purchase_status = self.request.query_params.get("status")
        payment_method = self.request.query_params.get("payment_method")

        if company_id: queryset = queryset.filter(company_id=company_id)
        if branch_id: queryset = queryset.filter(branch_id=branch_id)
        if supplier_id: queryset = queryset.filter(supplier_id=supplier_id)
        if purchase_status: queryset = queryset.filter(status=purchase_status)
        if payment_method: queryset = queryset.filter(payment_method=payment_method)

        return queryset



    @transaction.atomic
    def perform_create(self, serializer):
        user = self.request.user
        company = serializer.validated_data["company"]
        branch = serializer.validated_data["branch"]

        validate_company_branch_access(
            user,
            company.id,
            branch.id,
        )

        purchase_number = self._generate_purchase_number(company)

        serializer.save(
            purchase_number=purchase_number,
            created_by=user,
        )


    @transaction.atomic
    def perform_update(self, serializer):
        purchase = self.get_object()

        if purchase.status != PurchaseStatus.DRAFT:
            raise serializers.ValidationError({
                "status": "Solo las compras en borrador pueden editarse."
            })

        serializer.save(
            company=purchase.company,
            branch=purchase.branch,
            created_by=purchase.created_by,
            purchase_number=purchase.purchase_number,
        )

    def _get_locked_purchase(
            self,
            request,
            pk,
    ):
        owner_company_ids, assigned_branch_ids = (
            get_user_company_branch_scope(
                request.user,
            )
        )

        return (
            Purchase.objects
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

    def _generate_purchase_number(
            self,
            company,
    ):
        Company.objects.select_for_update().only(
            "id",
        ).get(
            pk=company.pk,
        )

        result = (
            Purchase.objects
            .filter(
                company=company,
                purchase_number__startswith="COMP-",
            )
            .annotate(
                sequence_number=Cast(
                    Substr(
                        "purchase_number",
                        6,
                    ),
                    IntegerField(),
                )
            )
            .aggregate(
                max_number=Max(
                    "sequence_number",
                )
            )
        )

        highest_number = ( result["max_number"]or 0 )

        return (f"COMP-{highest_number + 1:06d}")

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        with transaction.atomic():
            try:
                purchase = self._get_locked_purchase(
                    request,
                    pk,
                )
            except Purchase.DoesNotExist:
                return Response(
                    {
                        "detail": (
                            "La compra no existe o "
                            "no tienes acceso a ella."
                        )
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            if purchase.status != PurchaseStatus.DRAFT:
                return Response(
                    {
                        "detail": (
                            "Solo las compras en borrador "
                            "pueden completarse."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            items = list(purchase.items.select_related("product").all())

            if not items:
                return Response(
                    {"detail": "La compra debe tener al menos un producto."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            for item in items:
                product = item.product

                if not product.track_inventory:
                    raise serializers.ValidationError({
                        "items": f'El producto "{product.name}" no controla inventario.'
                    })

                product_stock, created = ProductStock.objects.select_for_update().get_or_create(
                    company=purchase.company,
                    branch=purchase.branch,
                    product=product,
                    defaults={"quantity": Decimal("0.000")},
                )

                previous_stock = product_stock.quantity
                new_stock = previous_stock + item.quantity

                product_stock.quantity = new_stock
                product_stock.save(update_fields=["quantity", "updated_at"])

                InventoryMovement.objects.create(
                    company=purchase.company,
                    branch=purchase.branch,
                    product=product,
                    movement_type=InventoryMovementType.PURCHASE,
                    quantity=item.quantity,
                    previous_stock=previous_stock,
                    new_stock=new_stock,
                    reference=purchase.purchase_number,
                    notes=f"Entrada por compra {purchase.purchase_number}",
                    created_by=request.user,
                )

            if purchase.payment_method == PurchasePaymentMethod.CASH:
                cash_session = get_open_cash_session(
                    cash_session_id=request.data.get("cash_session_id"),
                    company=purchase.company,
                    branch=purchase.branch,
                )

                create_cash_movement(
                    cash_session=cash_session,
                    direction=CashMovementDirection.OUT,
                    movement_type=CashMovementType.PURCHASE,
                    amount=purchase.total,
                    source_type=CashMovementSource.PURCHASE,
                    source_id=purchase.id,
                    reference=purchase.purchase_number,
                    notes=f"Compra a proveedor {purchase.supplier.name}",
                    user=request.user,
                )
            purchase.mark_as_completed()

            purchase.save(update_fields=[
                "status",
                "completed_at",
                "cancelled_at",
                "updated_at",
            ])

        serializer = self.get_serializer(purchase)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        with transaction.atomic():
            try:
                purchase = self._get_locked_purchase(
                    request,
                    pk,
                )
            except Purchase.DoesNotExist:
                return Response(
                    {
                        "detail": (
                            "La compra no existe o "
                            "no tienes acceso a ella."
                        )
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            if purchase.status == PurchaseStatus.CANCELLED:
                return Response(
                    {"detail": "La compra ya está cancelada."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if purchase.status == PurchaseStatus.DRAFT:
                purchase.mark_as_cancelled()

                purchase.save(update_fields=["status", "cancelled_at", "updated_at"])

                return Response(
                    self.get_serializer(purchase).data,
                    status=status.HTTP_200_OK,
                )

            if purchase.status != PurchaseStatus.COMPLETED:
                return Response(
                    {"detail": "La compra no se encuentra en un estado válido para cancelarse."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            items = list(purchase.items.select_related("product").all())

            if not items:
                return Response(
                    {"detail": "La compra no contiene productos."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            quantities_by_product = {}
            products_by_id = {}

            for item in items:
                quantities_by_product[item.product_id] = quantities_by_product.get(item.product_id,
                                                                                   Decimal("0.000")) + item.quantity
                products_by_id[item.product_id] = item.product

            product_ids = list(quantities_by_product.keys())

            stocks = (
                ProductStock.objects
                .select_for_update()
                .filter(
                    company=purchase.company,
                    branch=purchase.branch,
                    product_id__in=product_ids,
                )
                .select_related("product")
            )

            stock_map = {
                stock.product_id: stock
                for stock in stocks
            }

            for product_id, quantity in quantities_by_product.items():
                product = products_by_id[product_id]
                product_stock = stock_map.get(product_id)

                if product_stock is None:
                    raise serializers.ValidationError({
                        "detail": f'No existe inventario para el producto "{product.name}".'
                    })

                if product_stock.quantity < quantity:
                    raise serializers.ValidationError({
                        "detail": (
                            f'No es posible cancelar la compra porque "{product.name}" '
                            f"solo tiene {format_quantity(product_stock.quantity)} unidades disponibles "
                            f"y se deben revertir {format_quantity(quantity)}."
                        )
                    })

            for product_id, quantity in quantities_by_product.items():
                product = products_by_id[product_id]
                product_stock = stock_map[product_id]

                previous_stock = product_stock.quantity
                new_stock = previous_stock - quantity

                product_stock.quantity = new_stock
                product_stock.save(update_fields=["quantity", "updated_at"])

                InventoryMovement.objects.create(
                    company=purchase.company,
                    branch=purchase.branch,
                    product=product,
                    movement_type=InventoryMovementType.PURCHASE_REVERSAL,
                    quantity=quantity,
                    previous_stock=previous_stock,
                    new_stock=new_stock,
                    reference=purchase.purchase_number,
                    notes=f"Reversión por cancelación de compra {purchase.purchase_number}",
                    created_by=request.user,
                )

            # Si fue una compra en efectivo, revertimos también el movimiento de caja.
            if purchase.payment_method == PurchasePaymentMethod.CASH:
                try:
                    original_cash_movement = CashMovement.objects.select_for_update().select_related(
                        "cash_session").get(
                        source_type=CashMovementSource.PURCHASE,
                        source_id=purchase.id,
                        movement_type=CashMovementType.PURCHASE,
                    )
                except CashMovement.DoesNotExist:
                    raise ValidationError({
                        "detail": "No se encontró el movimiento de caja original de la compra."
                    })

                original_cash_session = original_cash_movement.cash_session

                if original_cash_session.status == CashSessionStatus.OPEN:
                    cash_session = get_open_cash_session(
                        cash_session_id=original_cash_session.id,
                        company=purchase.company,
                        branch=purchase.branch,
                    )
                else:
                    cash_session = get_open_cash_session(
                        cash_session_id=request.data.get("cash_session_id"),
                        company=purchase.company,
                        branch=purchase.branch,
                    )

                reverse_cash_movement(
                    original_movement=original_cash_movement,
                    cash_session=cash_session,
                    user=request.user,
                    reference=purchase.purchase_number,
                    notes=f"Reversión por cancelación de compra {purchase.purchase_number}",
                )

            purchase.mark_as_cancelled()
            purchase.save(update_fields=["status", "cancelled_at", "updated_at"])

        return Response(
            self.get_serializer(purchase).data,
            status=status.HTTP_200_OK,
        )