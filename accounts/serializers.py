from django.db import transaction
from rest_framework import serializers

from branches.models import Branch
from companies.models import Company, CompanyMembership

from .models import User


class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "is_active",
            "is_platform_admin",
            "created_at",
            "updated_at",
        )

        read_only_fields = (
            "id",
            "email",
            "is_active",
            "is_platform_admin",
            "created_at",
            "updated_at",
        )


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={
            "input_type": "password",
        },
    )

    company_name = serializers.CharField(
        write_only=True,
        max_length=150,
    )

    business_type = serializers.ChoiceField(
        write_only=True,
        choices=Company.BusinessType.choices,
        default=Company.BusinessType.GENERAL_RETAIL,
    )

    class Meta:
        model = User
        fields = (
            "email",
            "password",
            "first_name",
            "last_name",
            "phone",
            "company_name",
            "business_type",
        )

    @transaction.atomic
    def create(self, validated_data):
        company_name = validated_data.pop(
            "company_name",
        )

        business_type = validated_data.pop(
            "business_type",
        )

        password = validated_data.pop(
            "password",
        )

        user = User.objects.create_user(
            password=password,
            **validated_data,
        )

        company = Company.objects.create(
            name=company_name,
            business_type=business_type,
        )

        CompanyMembership.objects.create(
            company=company,
            user=user,
            role=CompanyMembership.Role.OWNER,
        )

        Branch.objects.create(
            company=company,
            name="Sucursal principal",
            code="PRINCIPAL",
            is_main=True,
        )

        self.company = company

        return user