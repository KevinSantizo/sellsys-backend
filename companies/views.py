from django.db import transaction
from rest_framework.exceptions import PermissionDenied
from django.db.models import Prefetch
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from catalog.models import Product

from branches.models import Branch

from .mixins import CompanyAccessMixin
from .models import (
    Company,
    CompanyMembership,
    CompanyModule,
    CompanySettings,
    Module,
)
from .serializers import (
    CompanyDetailSerializer,
    CompanyListSerializer,
    CompanyMembershipDetailSerializer,
    CompanyMembershipListSerializer,
    CompanyModuleDetailSerializer,
    CompanyModuleListSerializer,
    CompanySettingsDetailSerializer,
    CompanySettingsListSerializer,
    ModuleDetailSerializer,
    ModuleListSerializer,
)

from django.db.models import Prefetch, Q
from common.access import get_user_company_branch_scope

class CompanyViewSet(
    CompanyAccessMixin,
    ModelViewSet,
):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            self.get_accessible_companies()
            .order_by("name")
        )

        if self.action == "retrieve":
            owner_company_ids, assigned_branch_ids = get_user_company_branch_scope(
                self.request.user
            )

            branch_queryset = (
                Branch.objects
                .filter(
                    Q(
                        company_id__in=owner_company_ids,
                    )
                    | Q(
                        id__in=assigned_branch_ids,
                    ),
                    is_active=True,
                )
                .select_related("company")
                .distinct()
                .order_by("name")
            )

            queryset = queryset.prefetch_related(
                Prefetch(
                    "branches",
                    queryset=branch_queryset,
                ),
                Prefetch(
                    "products",
                    queryset=(
                        Product.objects
                        .select_related(
                            "company",
                            "category",
                            "brand",
                            "base_unit",
                        )
                        .order_by("name")
                    ),
                ),
            )

        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return CompanyListSerializer

        return CompanyDetailSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        company = serializer.save()

        CompanyMembership.objects.create(
            company=company,
            user=self.request.user,
            role=CompanyMembership.Role.OWNER,
        )

        Branch.objects.create(
            company=company,
            name="Sucursal principal",
            code="PRINCIPAL",
            is_main=True,
        )

    def perform_update(self, serializer):
        self.ensure_company_manager(
            serializer.instance
        )

        serializer.save()

    def perform_destroy(self, instance):
        self.ensure_company_owner(instance)
        instance.delete()


class CompanyMembershipViewSet(
    CompanyAccessMixin,
    ModelViewSet,
):
    permission_classes = [ IsAuthenticated ]

    def get_queryset(self):
        managed_company_ids = (
            CompanyMembership.objects
            .filter(
                user=self.request.user,
                is_active=True,
                company__is_active=True,
                role__in=[
                    CompanyMembership.Role.OWNER,
                    CompanyMembership.Role.ADMIN,
                ],
            )
            .values_list(
                "company_id",
                flat=True,
            )
        )

        queryset = (
            CompanyMembership.objects
            .filter(
                company_id__in=managed_company_ids,
                company__is_active=True,
            )
            .select_related(
                "company",
                "user",
            )
            .distinct()
        )

        company_id = self.request.query_params.get(
            "company_id"
        )

        if company_id:
            company = self.get_accessible_company(
                company_id
            )

            self.ensure_company_manager(
                company
            )

            queryset = queryset.filter(
                company=company
            )

        return queryset.order_by(
            "company__name",
            "user__email",
        )

    def get_serializer_class(self):
        if self.action == "list":
            return CompanyMembershipListSerializer

        return CompanyMembershipDetailSerializer

    def _get_request_membership(self, company):
        return CompanyMembership.objects.filter(
            user=self.request.user,
            company=company,
            is_active=True,
            company__is_active=True,
        ).first()

    def _ensure_can_manage_membership(
        self,
        company,
        target_membership=None,
        new_role=None,
    ):
        request_membership = self._get_request_membership(
            company
        )

        if not request_membership:
            raise PermissionDenied(
                "No tienes permiso para administrar "
                "usuarios de esta empresa."
            )

        is_owner = (
            request_membership.role
            == CompanyMembership.Role.OWNER
        )

        is_admin = (
            request_membership.role
            == CompanyMembership.Role.ADMIN
        )

        if not is_owner and not is_admin:
            raise PermissionDenied(
                "No tienes permiso para administrar "
                "usuarios de esta empresa."
            )

        if (
            target_membership
            and target_membership.role
            == CompanyMembership.Role.OWNER
            and not is_owner
        ):
            raise PermissionDenied(
                "Solo un propietario puede modificar "
                "a otro propietario."
            )

        if (
            new_role
            == CompanyMembership.Role.OWNER
            and not is_owner
        ):
            raise PermissionDenied(
                "Solo un propietario puede asignar "
                "el rol de propietario."
            )

        return request_membership

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        role = serializer.validated_data["role"]

        self._ensure_can_manage_membership(
            company,
            new_role=role,
        )

        serializer.save()

    def perform_update(self, serializer):
        instance = serializer.instance

        new_role = serializer.validated_data.get(
            "role",
            instance.role,
        )

        self._ensure_can_manage_membership(
            instance.company,
            target_membership=instance,
            new_role=new_role,
        )

        serializer.save(
            company=instance.company,
        )

    def perform_destroy(self, instance):
        self._ensure_can_manage_membership(
            instance.company,
            target_membership=instance,
        )

        instance.delete()


class CompanySettingsViewSet(
    CompanyAccessMixin,
    ModelViewSet,
):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = CompanySettings.objects.filter(
            company__memberships__user=self.request.user,
            company__memberships__is_active=True,
            company__is_active=True,
        ).select_related("company").distinct()

        return self.filter_by_company(
            queryset
        ).order_by("company__name")

    def get_serializer_class(self):
        if self.action == "list":
            return CompanySettingsListSerializer

        return CompanySettingsDetailSerializer

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]

        self.ensure_company_manager(company)
        serializer.save()

    def perform_update(self, serializer):
        self.ensure_company_manager(
            serializer.instance.company
        )

        serializer.save()

    def perform_destroy(self, instance):
        self.ensure_company_manager(
            instance.company
        )

        instance.delete()


class ModuleViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Module.objects.all().order_by(
        "display_order",
        "name",
    )

    def get_serializer_class(self):
        if self.action == "list":
            return ModuleListSerializer

        return ModuleDetailSerializer

    def ensure_platform_admin(self):
        user = self.request.user

        if not (
            user.is_platform_admin
            or user.is_superuser
        ):
            raise PermissionDenied(
                "Solo un administrador de SellSys "
                "puede modificar módulos globales."
            )

    def perform_create(self, serializer):
        self.ensure_platform_admin()
        serializer.save()

    def perform_update(self, serializer):
        self.ensure_platform_admin()
        serializer.save()

    def perform_destroy(self, instance):
        self.ensure_platform_admin()
        instance.delete()


class CompanyModuleViewSet(
    CompanyAccessMixin,
    ModelViewSet,
):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = CompanyModule.objects.filter(
            company__memberships__user=self.request.user,
            company__memberships__is_active=True,
            company__is_active=True,
        ).select_related(
            "company",
            "module",
        ).distinct()

        return self.filter_by_company(
            queryset
        ).order_by(
            "company__name",
            "module__display_order",
        )

    def get_serializer_class(self):
        if self.action == "list":
            return CompanyModuleListSerializer

        return CompanyModuleDetailSerializer

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]

        self.ensure_company_manager(company)
        serializer.save()

    def perform_update(self, serializer):
        self.ensure_company_manager(
            serializer.instance.company
        )

        serializer.save()

    def perform_destroy(self, instance):
        self.ensure_company_manager(
            instance.company
        )

        if instance.module.is_core:
            raise PermissionDenied(
                "No puedes eliminar un módulo esencial."
            )

        instance.delete()