from rest_framework.viewsets import ModelViewSet

from companies.mixins import CompanyAccessMixin

from .models import Branch
from .serializers import (
    BranchDetailSerializer,
    BranchListSerializer,
)


class BranchViewSet(
    CompanyAccessMixin,
    ModelViewSet,
):
    def get_queryset(self):
        queryset = Branch.objects.filter(
            company__memberships__user=self.request.user,
            company__memberships__is_active=True,
            company__is_active=True,
        ).select_related("company").distinct()

        return self.filter_by_company(
            queryset
        ).order_by("company__name", "name")

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
            serializer.instance.company
        )

        serializer.save()

    def perform_destroy(self, instance):
        self.ensure_company_manager(
            instance.company
        )

        instance.delete()