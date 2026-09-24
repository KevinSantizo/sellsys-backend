from django.shortcuts import render
from decimal import Decimal
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from rest_framework import filters, mixins, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from branches.models import BranchMembership
from companies.models import CompanyMembership

from .models import CashRegister, CashSession, CashSessionStatus, CashMovement, CashMovementDirection, CashMovementType, CashMovementSource
from .serializers import CashRegisterSerializer, CashSessionSerializer, CashMovementSerializer, OpenCashSessionSerializer, CloseCashSessionSerializer, ManualCashMovementSerializer
from .pagination import CashPagination

from common.access import (
    get_user_company_branch_scope,
    validate_company_branch_access,
)

# Create your views here.


class CashRegisterViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, GenericViewSet):
    serializer_class = CashRegisterSerializer
    permission_classes = [ IsAuthenticated ]
    filter_backends = [ filters.SearchFilter, filters.OrderingFilter ]
    search_fields = [ "name", "code", "company__name", "branch__name" ]
    ordering_fields = [ "name", "code", "created_at", "updated_at" ]
    ordering = [ "-created_at", "-id" ]
    pagination_class = CashPagination

    def get_queryset(self):
        owner_company_ids, assigned_branch_ids = get_user_company_branch_scope(self.request.user)

        queryset = CashRegister.objects.filter(
            Q(company_id__in=owner_company_ids) |
            Q(branch_id__in=assigned_branch_ids)
        ).select_related("company", "branch")

        company_id = self.request.query_params.get("company_id")
        branch_id = self.request.query_params.get("branch_id")
        is_active = self.request.query_params.get("is_active")

        if company_id:
            queryset = queryset.filter(company_id=company_id)

        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)

        if is_active in ( "true", "false", ):
            queryset = queryset.filter(is_active=is_active == "true")

        return queryset

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        branch = serializer.validated_data["branch"]

        validate_company_branch_access(
            self.request.user,
            company.id,
            branch.id,
        )

        serializer.save()

    def perform_update(self, serializer):
        cash_register = self.get_object()

        validate_company_branch_access(
            self.request.user,
            cash_register.company_id,
            cash_register.branch_id,
        )

        serializer.save(company=cash_register.company, branch=cash_register.branch)


class CashSessionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    serializer_class = CashSessionSerializer
    permission_classes = [ IsAuthenticated ]
    filter_backends = [ filters.OrderingFilter ]
    ordering_fields = [ "opened_at", "closed_at", "opening_amount", "expected_amount", "counted_amount", "difference" ]
    ordering = [ "-opened_at" ]
    pagination_class = CashPagination

    def get_queryset(self):
        owner_company_ids, assigned_branch_ids = get_user_company_branch_scope(self.request.user)

        queryset = CashSession.objects.filter(
            Q(company_id__in=owner_company_ids) |
            Q(branch_id__in=assigned_branch_ids)
        ).select_related(
            "company",
            "branch",
            "cash_register",
            "opened_by",
            "closed_by",
        )

        company_id = self.request.query_params.get("company_id")
        branch_id = self.request.query_params.get("branch_id")
        cash_register_id = self.request.query_params.get("cash_register_id")
        session_status = self.request.query_params.get("status")

        if company_id:
            queryset = queryset.filter(company_id=company_id)

        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)

        if cash_register_id:
            queryset = queryset.filter(cash_register_id=cash_register_id)

        if session_status:
            queryset = queryset.filter(status=session_status)

        return queryset

    def open_session(self, request):
        serializer = OpenCashSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        company = serializer.validated_data["company"]
        branch = serializer.validated_data["branch"]
        cash_register = serializer.validated_data["cash_register"]
        opening_amount = serializer.validated_data["opening_amount"]
        notes = serializer.validated_data.get("notes", "")

        validate_company_branch_access(
            request.user,
            company.id,
            branch.id,
        )

        with transaction.atomic():
            try:
                cash_register = CashRegister.objects.select_for_update().select_related("company", "branch").get(
                    pk=cash_register.pk,
                    is_active=True,
                )
            except CashRegister.DoesNotExist:
                raise ValidationError({ "cash_register_id": "La caja seleccionada no está disponible." })

            if cash_register.company_id != company.id:
                raise ValidationError({ "cash_register_id": "La caja seleccionada no pertenece a la empresa." })

            if cash_register.branch_id != branch.id:
                raise ValidationError({ "cash_register_id": "La caja seleccionada no pertenece a la sucursal." })

            already_open = CashSession.objects.filter(
                cash_register=cash_register,
                status=CashSessionStatus.OPEN,
            ).exists()

            if already_open:
                raise ValidationError({ "cash_register_id": "Esta caja ya tiene una sesión abierta." })

            cash_session = CashSession.objects.create(
                company=company,
                branch=branch,
                cash_register=cash_register,
                opening_amount=opening_amount,
                status=CashSessionStatus.OPEN,
                opened_by=request.user,
                notes=notes,
            )

        response_serializer = CashSessionSerializer(cash_session)

        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def close_session(self, request, pk=None):
        serializer = CloseCashSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        counted_amount = serializer.validated_data["counted_amount"]
        close_notes = serializer.validated_data.get("notes", "").strip()

        with transaction.atomic():
            try:
                cash_session = self.get_queryset().select_for_update().get(pk=pk)
            except CashSession.DoesNotExist:
                raise ValidationError({ "detail": "La sesión de caja no existe o no tienes acceso a ella." })

            validate_company_branch_access(
                request.user,
                cash_session.company_id,
                cash_session.branch_id,
            )

            if cash_session.status != CashSessionStatus.OPEN:
                raise ValidationError({ "detail": "Esta sesión de caja ya está cerrada." })

            movements = CashMovement.objects.filter(cash_session=cash_session)

            total_in = movements.filter(direction=CashMovementDirection.IN).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
            total_out = movements.filter(direction=CashMovementDirection.OUT).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

            expected_amount = cash_session.opening_amount + total_in - total_out
            difference = counted_amount - expected_amount

            cash_session.expected_amount = expected_amount
            cash_session.counted_amount = counted_amount
            cash_session.difference = difference
            cash_session.status = CashSessionStatus.CLOSED
            cash_session.closed_by = request.user
            cash_session.closed_at = timezone.now()

            if close_notes:
                cash_session.notes = f"{cash_session.notes}\n{close_notes}".strip()

            cash_session.save(
                update_fields=[
                    "expected_amount",
                    "counted_amount",
                    "difference",
                    "status",
                    "closed_by",
                    "closed_at",
                    "notes",
                    "updated_at",
                ]
            )

        response_serializer = CashSessionSerializer(cash_session)

        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def summary(self, request, pk=None):
        try:
            cash_session = self.get_queryset().get(pk=pk)
        except CashSession.DoesNotExist:
            return Response(
                {"detail": "La sesión de caja no existe o no tienes acceso a ella."},
                status=status.HTTP_404_NOT_FOUND,
            )

        movements = CashMovement.objects.filter(cash_session=cash_session)

        total_in = movements.filter(direction=CashMovementDirection.IN).aggregate(total=Sum("amount"))[
                       "total"] or Decimal("0.00")
        total_out = movements.filter(direction=CashMovementDirection.OUT).aggregate(total=Sum("amount"))[
                        "total"] or Decimal("0.00")

        expected_amount = cash_session.opening_amount + total_in - total_out

        return Response({
            "session_id": str(cash_session.id),
            "cash_register_id": str(cash_session.cash_register_id),
            "cash_register_name": cash_session.cash_register.name,
            "status": cash_session.status,
            "status_display": cash_session.get_status_display(),
            "opening_amount": str(cash_session.opening_amount),
            "total_in": str(total_in),
            "total_out": str(total_out),
            "expected_amount": str(expected_amount),
        })

class CashMovementViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet):
    serializer_class = CashMovementSerializer
    permission_classes = [ IsAuthenticated ]
    filter_backends = [ filters.SearchFilter, filters.OrderingFilter ]
    search_fields = [ "reference", "notes", "cash_session__cash_register__name", "cash_session__cash_register__code", ]
    ordering_fields = ["created_at", "amount", "direction", "movement_type"]
    ordering = ["-created_at", "-id"]
    pagination_class = CashPagination

    def get_queryset(self):
        owner_company_ids, assigned_branch_ids = get_user_company_branch_scope(self.request.user)

        queryset = CashMovement.objects.filter(
            Q(company_id__in=owner_company_ids) |
            Q(branch_id__in=assigned_branch_ids)
        ).select_related(
            "company",
            "branch",
            "cash_session",
            "cash_session__cash_register",
            "created_by",
            "reversal_of",
        )

        company_id = self.request.query_params.get("company_id")
        branch_id = self.request.query_params.get("branch_id")
        cash_session_id = self.request.query_params.get("cash_session_id")
        cash_register_id = self.request.query_params.get("cash_register_id")
        direction = self.request.query_params.get("direction")
        movement_type = self.request.query_params.get("movement_type")
        source_type = self.request.query_params.get("source_type")

        if company_id: queryset = queryset.filter(company_id=company_id)
        if branch_id: queryset = queryset.filter(branch_id=branch_id)
        if cash_session_id: queryset = queryset.filter(cash_session_id=cash_session_id)
        if cash_register_id: queryset = queryset.filter(cash_session__cash_register_id=cash_register_id)
        if direction: queryset = queryset.filter(direction=direction)
        if movement_type: queryset = queryset.filter(movement_type=movement_type)
        if source_type: queryset = queryset.filter(source_type=source_type)

        return queryset

    def manual(self, request):
        serializer = ManualCashMovementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cash_session = serializer.validated_data["cash_session"]
        direction = serializer.validated_data["direction"]
        amount = serializer.validated_data["amount"]
        reference = serializer.validated_data.get("reference", "")
        notes = serializer.validated_data.get("notes", "")

        validate_company_branch_access(
            request.user,
            cash_session.company_id,
            cash_session.branch_id,
        )

        with transaction.atomic():
            try:
                cash_session = CashSession.objects.select_for_update().select_related(
                    "company",
                    "branch",
                    "cash_register",
                ).get(pk=cash_session.pk)
            except CashSession.DoesNotExist:
                raise ValidationError({"cash_session_id": "La sesión de caja no existe."})

            if cash_session.status != CashSessionStatus.OPEN:
                raise ValidationError({"cash_session_id": "La sesión de caja debe estar abierta."})

            movement_type = CashMovementType.MANUAL_IN if direction == CashMovementDirection.IN else CashMovementType.MANUAL_OUT

            movement = CashMovement.objects.create(
                company=cash_session.company,
                branch=cash_session.branch,
                cash_session=cash_session,
                direction=direction,
                movement_type=movement_type,
                amount=amount,
                source_type=CashMovementSource.MANUAL,
                reference=reference,
                notes=notes,
                created_by=request.user,
            )

        response_serializer = CashMovementSerializer(movement)

        return Response(response_serializer.data, status=status.HTTP_201_CREATED)