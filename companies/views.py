from django.db import transaction
from rest_framework.exceptions import PermissionDenied
from rest_framework.viewsets import ModelViewSet

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


class CompanyViewSet(
    CompanyAccessMixin,
    ModelViewSet,
):
    def get_queryset(self):
        queryset = (
            self.get_accessible_companies()
            .order_by("name")
        )

        if self.action == "retrieve":
            queryset = queryset.prefetch_related(
                "branches"
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
    def get_queryset(self):
        queryset = CompanyMembership.objects.filter(
            company__memberships__user=self.request.user,
            company__memberships__is_active=True,
        ).select_related(
            "company",
            "user",
        ).distinct()

        return self.filter_by_company(
            queryset
        ).order_by("company__name", "user__email")

    def get_serializer_class(self):
        if self.action == "list":
            return CompanyMembershipListSerializer

        return CompanyMembershipDetailSerializer

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


class CompanySettingsViewSet(
    CompanyAccessMixin,
    ModelViewSet,
):
    def get_queryset(self):
        queryset = CompanySettings.objects.filter(
            company__memberships__user=self.request.user,
            company__memberships__is_active=True,
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
    def get_queryset(self):
        queryset = CompanyModule.objects.filter(
            company__memberships__user=self.request.user,
            company__memberships__is_active=True,
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