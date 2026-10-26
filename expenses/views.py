from django.db import transaction
from django.shortcuts import render
from rest_framework import ( filters, mixins, status, viewsets, )
from rest_framework.exceptions import ( PermissionDenied, ValidationError, )
from rest_framework.pagination import ( PageNumberPagination, )
from rest_framework.permissions import ( IsAuthenticated, )
from rest_framework.response import Response
from branches.models import ( BranchMembership, )
from companies.models import ( CompanyMembership, )
from .models import ( Expense, ExpenseCategory, ExpenseStatus, ExpensePaymentMethod )
from .serializers import ( ExpenseCategorySerializer, ExpenseSerializer, )
from django.db.models import Q

from cash.models import CashMovement, CashMovementDirection, CashMovementType, CashMovementSource, CashSessionStatus
from cash.services import get_open_cash_session, create_cash_movement, reverse_cash_movement
from rest_framework.exceptions import NotFound
from common.access import (
    get_user_company_branch_scope,
    validate_company_branch_access,
)

# Create your views here.

class ExpenseCategoryPagination( PageNumberPagination ):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class ExpensePagination( PageNumberPagination ):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class ExpenseCategoryViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (
        IsAuthenticated,
    )

    serializer_class = (
        ExpenseCategorySerializer
    )

    pagination_class = (
        ExpenseCategoryPagination
    )

    filter_backends = (
        filters.SearchFilter,
        filters.OrderingFilter,
    )

    search_fields = (
        "name",
        "description",
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

        queryset = (
            ExpenseCategory.objects
            .filter(
                company_id__in=company_ids,
            )
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
            if (
                is_active.lower()
                == "true"
            ):
                queryset = queryset.filter(
                    is_active=True,
                )

            elif (
                is_active.lower()
                == "false"
            ):
                queryset = queryset.filter(
                    is_active=False,
                )

        return queryset

    def perform_create(
        self,
        serializer,
    ):
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
                    "No tienes acceso "
                    "a esta empresa."
                )
            )

        serializer.save()

    def perform_update(
        self,
        serializer,
    ):
        category = serializer.instance

        serializer.save(
            company=category.company,
        )


class ExpenseViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (IsAuthenticated,)
    serializer_class = (ExpenseSerializer)
    pagination_class = (ExpensePagination)

    filter_backends = (
        filters.SearchFilter,
        filters.OrderingFilter,
    )

    search_fields = (
        "description",
        "reference",
        "notes",
        "supplier__name",
        "category__name",
    )

    ordering_fields = (
        "expense_date",
        "amount",
        "created_at",
        "updated_at",
    )

    ordering = (
        "-expense_date",
        "-created_at",
    )

    def get_queryset(self):
        owner_company_ids, assigned_branch_ids = get_user_company_branch_scope(
            self.request.user
        )

        queryset = (
            Expense.objects
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
                "category",
                "supplier",
                "created_by",
            )
        )

        company_id = self.request.query_params.get(
            "company_id"
        )

        branch_id = self.request.query_params.get(
            "branch_id"
        )

        category_id = self.request.query_params.get(
            "category_id"
        )

        supplier_id = self.request.query_params.get(
            "supplier_id"
        )

        expense_status = self.request.query_params.get(
            "status"
        )

        payment_method = self.request.query_params.get(
            "payment_method"
        )

        if company_id:
            queryset = queryset.filter(
                company_id=company_id,
            )

        if branch_id:
            queryset = queryset.filter(
                branch_id=branch_id,
            )

        if category_id:
            queryset = queryset.filter(
                category_id=category_id,
            )

        if supplier_id:
            queryset = queryset.filter(
                supplier_id=supplier_id,
            )

        if expense_status:
            queryset = queryset.filter(
                status=expense_status,
            )

        if payment_method:
            queryset = queryset.filter(
                payment_method=payment_method,
            )

        return queryset.distinct()

    def _get_locked_expense(
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
            Expense.objects
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

    def perform_create(self, serializer):
        user = self.request.user
        company = serializer.validated_data["company"]
        branch = serializer.validated_data["branch"]

        validate_company_branch_access(
            user,
            company.id,
            branch.id,
        )

        serializer.save(
            created_by=user,
        )

    def perform_update(
        self,
        serializer,
    ):
        expense = serializer.instance

        if (
            expense.status
            != ExpenseStatus.DRAFT
        ):
            raise ValidationError(
                (
                    "Solo se pueden editar "
                    "gastos en estado borrador."
                )
            )

        serializer.save(
            company=expense.company,
            branch=expense.branch,
            created_by=expense.created_by,
        )

    def complete(self, request, pk=None):
        with transaction.atomic():
            try:
                expense = self._get_locked_expense(
                    request,
                    pk,
                )
            except Expense.DoesNotExist:
                raise NotFound(
                    "El gasto no existe o "
                    "no tienes acceso a él."
                )

            if expense.status != ExpenseStatus.DRAFT:
                raise ValidationError(
                    {
                        "detail": (
                            "Solo se pueden completar "
                            "gastos en borrador."
                        )
                    }
                )

            if expense.payment_method == ExpensePaymentMethod.CASH:
                cash_session = get_open_cash_session(
                    cash_session_id=request.data.get("cash_session_id"),
                    company=expense.company,
                    branch=expense.branch,
                )

                create_cash_movement(
                    cash_session=cash_session,
                    direction=CashMovementDirection.OUT,
                    movement_type=CashMovementType.EXPENSE,
                    amount=expense.amount,
                    source_type=CashMovementSource.EXPENSE,
                    source_id=expense.id,
                    reference=expense.reference or str(expense.id),
                    notes=expense.description,
                    user=request.user,
                )

            expense.mark_as_completed()

        return Response(ExpenseSerializer(expense).data, status=status.HTTP_200_OK)


    def cancel(self, request, pk=None):
        with transaction.atomic():
            try:
                expense = self._get_locked_expense(
                    request,
                    pk,
                )
            except Expense.DoesNotExist:
                raise NotFound(
                    "El gasto no existe o "
                    "no tienes acceso a él."
                )

            if expense.status == ExpenseStatus.CANCELLED:
                raise ValidationError({"detail": "El gasto ya está cancelado."})

            if expense.status == ExpenseStatus.COMPLETED and expense.payment_method == ExpensePaymentMethod.CASH:
                try:
                    original_movement = CashMovement.objects.select_for_update().select_related("cash_session").get(
                        source_type=CashMovementSource.EXPENSE,
                        source_id=expense.id,
                        movement_type=CashMovementType.EXPENSE,
                    )
                except CashMovement.DoesNotExist:
                    raise ValidationError({"detail": "No se encontró el movimiento de caja original del gasto."})

                original_session = original_movement.cash_session

                if original_session.status == CashSessionStatus.OPEN:
                    cash_session = get_open_cash_session(
                        cash_session_id=original_session.id,
                        company=expense.company,
                        branch=expense.branch,
                    )
                else:
                    cash_session = get_open_cash_session(
                        cash_session_id=request.data.get("cash_session_id"),
                        company=expense.company,
                        branch=expense.branch,
                    )

                reverse_cash_movement(
                    original_movement=original_movement,
                    cash_session=cash_session,
                    user=request.user,
                    reference=expense.reference or str(expense.id),
                    notes=f"Reversión por cancelación del gasto: {expense.description}",
                )

            expense.mark_as_cancelled()

        return Response(ExpenseSerializer(expense).data, status=status.HTTP_200_OK)