from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied

from .models import (
    Company,
    CompanyMembership,
    CompanyModule,
)


class CompanyAccessMixin:

    def should_return_empty_queryset(self):
        if getattr(
                self,
                "swagger_fake_view",
                False,
        ):
            return True

        user = getattr(
            self.request,
            "user",
            None,
        )

        return not getattr(
            user,
            "is_authenticated",
            False,
        )

    def get_accessible_companies(self):
        if self.should_return_empty_queryset():
            return Company.objects.none()

        return Company.objects.filter(
            memberships__user=self.request.user,
            memberships__is_active=True,
            is_active=True,
        ).distinct()

    def get_accessible_company(self, company_id):
        return get_object_or_404(
            self.get_accessible_companies(),
            id=company_id,
        )

    def filter_by_company(
        self,
        queryset,
        field_name="company",
    ):
        company_id = self.request.query_params.get(
            "company_id"
        )

        if not company_id:
            return queryset

        company = self.get_accessible_company(
            company_id
        )

        module_code = getattr(
            self,
            "module_code",
            None,
        )

        if module_code:
            self.ensure_module_enabled(
                company,
                module_code,
            )

        return queryset.filter(
            **{field_name: company}
        )

    def ensure_company_manager(self, company):
        allowed = CompanyMembership.objects.filter(
            company=company,
            user=self.request.user,
            is_active=True,
            role__in=[
                CompanyMembership.Role.OWNER,
                CompanyMembership.Role.ADMIN,
            ],
        ).exists()

        if not allowed:
            raise PermissionDenied(
                "No tienes permiso para modificar "
                "registros de esta empresa."
            )

    def ensure_company_owner(self, company):
        allowed = CompanyMembership.objects.filter(
            company=company,
            user=self.request.user,
            is_active=True,
            role=CompanyMembership.Role.OWNER,
        ).exists()

        if not allowed:
            raise PermissionDenied(
                "Solo el propietario puede realizar "
                "esta operación."
            )

    def ensure_module_enabled(
        self,
        company,
        module_code,
    ):
        enabled = CompanyModule.objects.filter(
            company=company,
            module__code=module_code,
            module__is_active=True,
            enabled=True,
        ).exists()

        if not enabled:
            raise PermissionDenied(
                f"El módulo {module_code} no está "
                "habilitado para esta empresa."
            )