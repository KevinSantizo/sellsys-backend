from django.db import transaction
from django.db.models import Q
from rest_framework.viewsets import ModelViewSet

from companies.mixins import CompanyAccessMixin
from companies.models import CompanyMembership

from .models import Branch, BranchMembership
from .serializers import (
    BranchDetailSerializer,
    BranchListSerializer,
    BranchMembershipDetailSerializer,
    BranchMembershipListSerializer,
)

from common.access import get_user_company_branch_scope
from rest_framework.permissions import IsAuthenticated

class BranchViewSet(
    CompanyAccessMixin,
    ModelViewSet,
):
    permission_classes = [ IsAuthenticated ]

    def get_queryset(self):
        owner_company_ids, assigned_branch_ids = get_user_company_branch_scope(
            self.request.user
        )

        queryset = (
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
        )

        return (
            self.filter_by_company(queryset)
            .order_by(
                "company__name",
                "name",
            )
        )

    def get_serializer_class(self):
        if self.action == "list":
            return BranchListSerializer

        return BranchDetailSerializer

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]

        self.ensure_company_manager(company)

        serializer.save()

    def perform_update(self, serializer):
        self.ensure_company_manager(
            serializer.instance.company,
        )

        serializer.save()

    def perform_destroy(self, instance):
        self.ensure_company_manager(
            instance.company,
        )

        instance.delete()


class BranchMembershipViewSet(
    CompanyAccessMixin,
    ModelViewSet,
):
    permission_classes = [IsAuthenticated]
    
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
            BranchMembership.objects
            .filter(
                company_membership__company_id__in=(
                    managed_company_ids
                ),
            )
            .select_related(
                "company_membership",
                "company_membership__company",
                "company_membership__user",
                "branch",
                "branch__company",
            )
        )

        company_id = self.request.query_params.get(
            "company_id",
        )

        if company_id:
            company = self.get_accessible_company(
                company_id,
            )

            self.ensure_company_manager(company)

            queryset = queryset.filter(
                company_membership__company=company,
            )

        return queryset.order_by(
            "company_membership__user__email",
            "branch__name",
        )

    def get_serializer_class(self):
        if self.action == "list":
            return BranchMembershipListSerializer

        return BranchMembershipDetailSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        membership = serializer.validated_data[
            "company_membership"
        ]

        self.ensure_company_manager(
            membership.company,
        )

        if serializer.validated_data.get(
            "is_default",
            False,
        ):
            BranchMembership.objects.filter(
                company_membership=membership,
                is_default=True,
            ).update(
                is_default=False,
            )

        serializer.save()

    @transaction.atomic
    def perform_update(self, serializer):
        instance = serializer.instance

        membership = serializer.validated_data.get(
            "company_membership",
            instance.company_membership,
        )

        self.ensure_company_manager(
            membership.company,
        )

        will_be_default = serializer.validated_data.get(
            "is_default",
            instance.is_default,
        )

        if will_be_default:
            BranchMembership.objects.filter(
                company_membership=membership,
                is_default=True,
            ).exclude(
                id=instance.id,
            ).update(
                is_default=False,
            )

        serializer.save()

    def perform_destroy(self, instance):
        self.ensure_company_manager(
            instance.company_membership.company,
        )

        instance.delete()