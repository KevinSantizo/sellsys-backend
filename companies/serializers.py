from rest_framework import serializers

from accounts.models import User
from branches.serializers import BranchListSerializer
from catalog.serializers import ProductListSerializer
from common.serializers import CompanyOwnedModelSerializer

from .models import (
    Company,
    CompanyMembership,
    CompanyModule,
    CompanySettings,
    Module,
)


class CompanyListSerializer(serializers.ModelSerializer):
    business_type_display = serializers.CharField(
        source="get_business_type_display",
        read_only=True,
    )

    class Meta:
        model = Company
        fields = (
            "id",
            "name",
            "business_type",
            "business_type_display",
            "currency",
            "is_active",
        )

        read_only_fields = fields


class CompanyDetailSerializer(serializers.ModelSerializer):
    business_type_display = serializers.CharField(
        source="get_business_type_display",
        read_only=True,
    )

    branches = BranchListSerializer(
        many=True,
        read_only=True,
    )

    products = ProductListSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = Company
        fields = (
            "id",
            "name",
            "legal_name",
            "tax_identifier",
            "business_type",
            "business_type_display",
            "currency",
            "timezone",
            "is_active",
            "branches",
            "products",
            "created_at",
            "updated_at",
        )

        read_only_fields = (
            "id",
            "business_type_display",
            "branches",
            "products",
            "created_at",
            "updated_at",
        )

class CompanyMembershipListSerializer(
    serializers.ModelSerializer
):
    company_name = serializers.CharField(
        source="company.name",
        read_only=True,
    )

    user_email = serializers.EmailField(
        source="user.email",
        read_only=True,
    )

    role_display = serializers.CharField(
        source="get_role_display",
        read_only=True,
    )

    class Meta:
        model = CompanyMembership
        fields = (
            "id",
            "company_name",
            "user_email",
            "role",
            "role_display",
            "is_active",
        )

        read_only_fields = fields


class CompanyMembershipDetailSerializer(
    CompanyOwnedModelSerializer
):
    user_id = serializers.PrimaryKeyRelatedField(
        source="user",
        queryset=User.objects.filter(is_active=True),
    )

    company_name = serializers.CharField(
        source="company.name",
        read_only=True,
    )

    user_email = serializers.EmailField(
        source="user.email",
        read_only=True,
    )

    role_display = serializers.CharField(
        source="get_role_display",
        read_only=True,
    )

    class Meta:
        model = CompanyMembership
        fields = (
            "id",
            "company_id",
            "company_name",
            "user_id",
            "user_email",
            "role",
            "role_display",
            "is_active",
            "created_at",
            "updated_at",
        )

        read_only_fields = (
            "id",
            "company_name",
            "user_email",
            "role_display",
            "created_at",
            "updated_at",
        )


class CompanySettingsListSerializer(
    serializers.ModelSerializer
):
    company_name = serializers.CharField(
        source="company.name",
        read_only=True,
    )

    class Meta:
        model = CompanySettings
        fields = (
            "id",
            "company_name",
            "allow_negative_stock",
            "require_customer_on_sale",
        )

        read_only_fields = fields


class CompanySettingsDetailSerializer(
    CompanyOwnedModelSerializer
):
    company_name = serializers.CharField(
        source="company.name",
        read_only=True,
    )

    class Meta:
        model = CompanySettings
        fields = (
            "id",
            "company_id",
            "company_name",
            "allow_negative_stock",
            "require_customer_on_sale",
            "allow_manual_discounts",
            "max_discount_percent",
            "prices_include_tax",
            "default_tax_rate",
            "enable_low_stock_alerts",
            "created_at",
            "updated_at",
        )

        read_only_fields = (
            "id",
            "company_name",
            "created_at",
            "updated_at",
        )


class ModuleListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = (
            "id",
            "code",
            "name",
            "is_core",
            "default_enabled",
            "is_active",
        )

        read_only_fields = fields


class ModuleDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = (
            "id",
            "code",
            "name",
            "description",
            "is_core",
            "default_enabled",
            "is_active",
            "display_order",
            "created_at",
            "updated_at",
        )

        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )


class CompanyModuleListSerializer(
    serializers.ModelSerializer
):
    company_name = serializers.CharField(
        source="company.name",
        read_only=True,
    )

    module_code = serializers.CharField(
        source="module.code",
        read_only=True,
    )

    module_name = serializers.CharField(
        source="module.name",
        read_only=True,
    )

    class Meta:
        model = CompanyModule
        fields = (
            "id",
            "company_name",
            "module_code",
            "module_name",
            "enabled",
        )

        read_only_fields = fields


class CompanyModuleDetailSerializer(
    CompanyOwnedModelSerializer
):
    module_id = serializers.PrimaryKeyRelatedField(
        source="module",
        queryset=Module.objects.filter(is_active=True),
    )

    company_name = serializers.CharField(
        source="company.name",
        read_only=True,
    )

    module_code = serializers.CharField(
        source="module.code",
        read_only=True,
    )

    module_name = serializers.CharField(
        source="module.name",
        read_only=True,
    )

    class Meta:
        model = CompanyModule
        fields = (
            "id",
            "company_id",
            "company_name",
            "module_id",
            "module_code",
            "module_name",
            "enabled",
            "created_at",
            "updated_at",
        )

        read_only_fields = (
            "id",
            "company_name",
            "module_code",
            "module_name",
            "created_at",
            "updated_at",
        )

    def validate_enabled(self, value):
        if (
            self.instance
            and self.instance.module.is_core
            and value is False
        ):
            raise serializers.ValidationError(
                "Los módulos esenciales no pueden "
                "desactivarse."
            )

        return value