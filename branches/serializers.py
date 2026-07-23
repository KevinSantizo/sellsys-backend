from rest_framework import serializers

from common.serializers import CompanyOwnedModelSerializer

from .models import Branch


class BranchListSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(
        source="company.name",
        read_only=True,
    )

    class Meta:
        model = Branch
        fields = (
            "id",
            "company_name",
            "name",
            "code",
            "is_main",
            "is_active",
        )

        read_only_fields = fields


class BranchDetailSerializer(
    CompanyOwnedModelSerializer
):
    company_name = serializers.CharField(
        source="company.name",
        read_only=True,
    )

    class Meta:
        model = Branch
        fields = (
            "id",
            "company_id",
            "company_name",
            "name",
            "code",
            "address",
            "phone",
            "is_main",
            "is_active",
            "created_at",
            "updated_at",
        )

        read_only_fields = (
            "id",
            "company_name",
            "created_at",
            "updated_at",
        )