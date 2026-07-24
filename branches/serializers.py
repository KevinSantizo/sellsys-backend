from rest_framework import serializers
from common.serializers import CompanyOwnedModelSerializer
from companies.models import CompanyMembership
from .models import Branch, BranchMembership

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


class BranchMembershipListSerializer(
    serializers.ModelSerializer
):
    user_email = serializers.EmailField(
        source="company_membership.user.email",
        read_only=True,
    )

    company_name = serializers.CharField(
        source="company_membership.company.name",
        read_only=True,
    )

    role = serializers.CharField(
        source="company_membership.role",
        read_only=True,
    )

    role_display = serializers.CharField(
        source="company_membership.get_role_display",
        read_only=True,
    )

    branch = BranchListSerializer(
        read_only=True,
    )

    class Meta:
        model = BranchMembership
        fields = (
            "id",
            "user_email",
            "company_name",
            "role",
            "role_display",
            "branch",
            "is_default",
            "is_active",
        )

        read_only_fields = fields


class BranchMembershipDetailSerializer(
    serializers.ModelSerializer
):
    company_membership_id = (
        serializers.PrimaryKeyRelatedField(
            source="company_membership",
            queryset=CompanyMembership.objects.filter(
                is_active=True,
            ).select_related(
                "company",
                "user",
            ),
            write_only=True,
        )
    )

    branch_id = serializers.PrimaryKeyRelatedField(
        source="branch",
        queryset=Branch.objects.filter(
            is_active=True,
        ),
        write_only=True,
    )

    user_email = serializers.EmailField(
        source="company_membership.user.email",
        read_only=True,
    )

    company_name = serializers.CharField(
        source="company_membership.company.name",
        read_only=True,
    )

    role = serializers.CharField(
        source="company_membership.role",
        read_only=True,
    )

    role_display = serializers.CharField(
        source="company_membership.get_role_display",
        read_only=True,
    )

    branch = BranchListSerializer(
        read_only=True,
    )

    class Meta:
        model = BranchMembership
        fields = (
            "id",
            "company_membership_id",
            "user_email",
            "company_name",
            "role",
            "role_display",
            "branch_id",
            "branch",
            "is_default",
            "is_active",
            "created_at",
            "updated_at",
        )

        read_only_fields = (
            "id",
            "user_email",
            "company_name",
            "role",
            "role_display",
            "branch",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        membership = attrs.get(
            "company_membership",
            self.instance.company_membership
            if self.instance
            else None,
        )

        branch = attrs.get(
            "branch",
            self.instance.branch
            if self.instance
            else None,
        )

        is_default = attrs.get(
            "is_default",
            self.instance.is_default
            if self.instance
            else False,
        )

        is_active = attrs.get(
            "is_active",
            self.instance.is_active
            if self.instance
            else True,
        )

        errors = {}

        if (
            membership
            and branch
            and membership.company_id
            != branch.company_id
        ):
            errors["branch_id"] = (
                "La sucursal no pertenece a la empresa "
                "de la membresía."
            )

        if is_default and not is_active:
            errors["is_default"] = (
                "Una asignación inactiva no puede ser "
                "predeterminada."
            )

        if errors:
            raise serializers.ValidationError(errors)

        return attrs