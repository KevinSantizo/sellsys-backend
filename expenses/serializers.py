from decimal import Decimal

from rest_framework import serializers

from branches.models import Branch
from companies.models import Company
from purchases.models import Supplier

from .models import (
    Expense,
    ExpenseCategory,
)


class ExpenseCategorySerializer(
    serializers.ModelSerializer
):
    company_id = (
        serializers.PrimaryKeyRelatedField(
            queryset=Company.objects.filter(
                is_active=True,
            ),
            source="company",
            write_only=True,
        )
    )

    class Meta:
        model = ExpenseCategory

        fields = (
            "id",
            "company_id",
            "name",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        )

        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )

    def validate_name(
        self,
        value,
    ):
        name = value.strip()

        if not name:
            raise serializers.ValidationError(
                "El nombre de la categoría es obligatorio."
            )

        return name

class ExpenseSerializer(
    serializers.ModelSerializer
):
    company_id = (
        serializers.PrimaryKeyRelatedField(
            queryset=Company.objects.filter(
                is_active=True,
            ),
            source="company",
            write_only=True,
        )
    )

    branch_id = (
        serializers.PrimaryKeyRelatedField(
            queryset=Branch.objects.filter(
                is_active=True,
            ),
            source="branch",
            write_only=True,
        )
    )

    category_id = serializers.PrimaryKeyRelatedField(
        queryset=ExpenseCategory.objects.filter(
            is_active=True,
        ),
        source="category",
    )

    supplier_id = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.filter(
            is_active=True,
        ),
        source="supplier",
        required=False,
        allow_null=True,
    )

    amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    branch_name = serializers.CharField(
        source="branch.name",
        read_only=True,
    )

    category_name = serializers.CharField(
        source="category.name",
        read_only=True,
    )

    supplier_name = serializers.CharField(
        source="supplier.name",
        read_only=True,
        allow_null=True,
    )

    payment_method_display = (
        serializers.CharField(
            source="get_payment_method_display",
            read_only=True,
        )
    )

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    created_by_name = (
        serializers.SerializerMethodField()
    )

    class Meta:
        model = Expense

        fields = (
            "id",
            "company_id",
            "branch_id",
            "branch_name",
            "category_id",
            "category_name",
            "supplier_id",
            "supplier_name",
            "description",
            "amount",
            "expense_date",
            "payment_method",
            "payment_method_display",
            "reference",
            "notes",
            "status",
            "status_display",
            "created_by_name",
            "created_at",
            "updated_at",
        )

        read_only_fields = (
            "id",
            "status",
            "created_by_name",
            "created_at",
            "updated_at",
        )

    def validate_description(
        self,
        value,
    ):
        description = value.strip()

        if not description:
            raise serializers.ValidationError(
                "La descripción del gasto es obligatoria."
            )

        return description

    def validate(
        self,
        attrs,
    ):
        instance = self.instance

        company = (
            attrs.get("company")
            or (
                instance.company
                if instance
                else None
            )
        )

        branch = (
            attrs.get("branch")
            or (
                instance.branch
                if instance
                else None
            )
        )

        category = (
            attrs.get("category")
            or (
                instance.category
                if instance
                else None
            )
        )

        supplier = (
            attrs.get(
                "supplier",
                instance.supplier
                if instance
                else None,
            )
        )

        if (
            company
            and branch
            and branch.company_id
            != company.id
        ):
            raise serializers.ValidationError(
                {
                    "branch_id": (
                        "La sucursal no pertenece "
                        "a la empresa seleccionada."
                    )
                }
            )

        if (
            company
            and category
            and category.company_id
            != company.id
        ):
            raise serializers.ValidationError(
                {
                    "category_id": (
                        "La categoría de gasto no "
                        "pertenece a la empresa "
                        "seleccionada."
                    )
                }
            )

        if (
            company
            and supplier
            and supplier.company_id
            != company.id
        ):
            raise serializers.ValidationError(
                {
                    "supplier_id": (
                        "El proveedor no pertenece "
                        "a la empresa seleccionada."
                    )
                }
            )

        return attrs

    def get_created_by_name(
        self,
        obj,
    ):
        if not obj.created_by:
            return None

        return (
            obj.created_by.get_full_name()
            or obj.created_by.email
        )