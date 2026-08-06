from django.db.models import (
    Count,
    Q,
)
from rest_framework import (
    filters,
    mixins,
    status,
    viewsets,
)
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response

from branches.models import (
    BranchMembership,
)
from companies.models import (
    CompanyMembership,
)

from .access import (
    get_membership_role_code,
)
from .models import Sale
from .pagination import SalePagination
from .serializers import (
    SaleCheckoutSerializer,
    SaleDetailSerializer,
    SaleListSerializer,
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
        user = self.request.user

        company_memberships = list(
            CompanyMembership.objects
            .filter(
                user=user,
                is_active=True,
                company__is_active=True,
            )
        )

        allowed_company_ids = [
            membership.company_id
            for membership
            in company_memberships
        ]

        owner_company_ids = [
            membership.company_id
            for membership
            in company_memberships
            if get_membership_role_code(
                membership,
            ) == "OWNER"
        ]

        assigned_branch_ids = (
            BranchMembership.objects
            .filter(
                user=user,
                is_active=True,
                branch__is_active=True,
                branch__company_id__in=(
                    allowed_company_ids
                ),
            )
            .values_list(
                "branch_id",
                flat=True,
            )
        )

        queryset = (
            Sale.objects
            .filter(
                Q(
                    company_id__in=(
                        owner_company_ids
                    )
                )
                | Q(
                    branch_id__in=(
                        assigned_branch_ids
                    )
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

        company_id = (
            self.request.query_params.get(
                "company_id"
            )
        )

        branch_id = (
            self.request.query_params.get(
                "branch_id"
            )
        )

        sale_status = (
            self.request.query_params.get(
                "status"
            )
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