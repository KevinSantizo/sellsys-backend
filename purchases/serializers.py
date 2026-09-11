from decimal import Decimal

from django.db import transaction

from rest_framework import serializers

from branches.models import Branch
from catalog.models import Product
from companies.models import Company

from .models import (
    Purchase,
    PurchaseItem,
    Supplier,
)

class SupplierSerializer(serializers.ModelSerializer):
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.filter(
            is_active=True,
        ),
        source="company",
        write_only=True,
    )

    class Meta:
        model = Supplier

        fields = (
            "id",
            "company_id",
            "name",
            "tax_id",
            "contact_name",
            "phone",
            "email",
            "address",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        )

        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )

    def validate_name(self, value):
        name = value.strip()

        if not name:
            raise serializers.ValidationError(
                "El nombre del proveedor es obligatorio."
            )

        return name


class PurchaseItemSerializer(
    serializers.ModelSerializer
):
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(
            is_active=True,
        ),
        source="product",
    )

    product_name = serializers.CharField(
        source="product.name",
        read_only=True,
    )

    product_sku = serializers.CharField(
        source="product.sku",
        read_only=True,
    )

    quantity = serializers.DecimalField(
        max_digits=14,
        decimal_places=3,
        min_value=Decimal("0.001"),
    )

    unit_cost = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.00"),
    )

    subtotal = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = PurchaseItem

        fields = (
            "id",
            "product_id",
            "product_name",
            "product_sku",
            "quantity",
            "unit_cost",
            "subtotal",
            "created_at",
            "updated_at",
        )

        read_only_fields = (
            "id",
            "subtotal",
            "created_at",
            "updated_at",
        )


class PurchaseSerializer(
    serializers.ModelSerializer
):
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.filter(
            is_active=True,
        ),
        source="company",
    )

    branch_id = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.filter(
            is_active=True,
        ),
        source="branch",
    )

    supplier_id = serializers.PrimaryKeyRelatedField(
        queryset=Supplier.objects.filter(
            is_active=True,
        ),
        source="supplier",
    )

    company_name = serializers.CharField(
        source="company.name",
        read_only=True,
    )

    branch_name = serializers.CharField(
        source="branch.name",
        read_only=True,
    )

    supplier_name = serializers.CharField(
        source="supplier.name",
        read_only=True,
    )

    payment_method_display = serializers.CharField(
        source="get_payment_method_display",
        read_only=True,
    )

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    created_by_name = serializers.SerializerMethodField()

    discount_total = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
        default=Decimal("0.00"),
    )

    tax_total = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
        default=Decimal("0.00"),
    )

    items = PurchaseItemSerializer(
        many=True,
        required=False,
    )

    class Meta:
        model = Purchase

        fields = (
            "id",
            "company_id",
            "company_name",
            "branch_id",
            "branch_name",
            "supplier_id",
            "supplier_name",
            "purchase_number",
            "supplier_invoice_number",
            "purchase_date",
            "payment_method",
            "payment_method_display",
            "status",
            "status_display",
            "subtotal",
            "discount_total",
            "tax_total",
            "total",
            "notes",
            "items",
            "created_by_name",
            "completed_at",
            "cancelled_at",
            "created_at",
            "updated_at",
        )

        read_only_fields = (
            "id",
            "purchase_number",
            "status",
            "subtotal",
            "total",
            "completed_at",
            "cancelled_at",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs, ):
        instance = self.instance

        if instance:
            if "company" in attrs and attrs["company"].id != instance.company_id:
                raise serializers.ValidationError({"company_id": "No puedes cambiar la empresa de una compra existente."})

            if "branch" in attrs and attrs["branch"].id != instance.branch_id:
                raise serializers.ValidationError({"branch_id": "No puedes cambiar la sucursal de una compra existente."})

        company = instance.company if instance else attrs.get("company")
        branch = instance.branch if instance else attrs.get("branch")
        supplier = attrs.get("supplier") or (instance.supplier if instance else None)

        items = attrs.get("items")

        discount_total = attrs.get(
            "discount_total",
            (
                instance.discount_total
                if instance
                else Decimal("0.00")
            ),
        )

        tax_total = attrs.get(
            "tax_total",
            (
                instance.tax_total
                if instance
                else Decimal("0.00")
            ),
        )


        if (
            company
            and branch
            and branch.company_id != company.id
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
            and supplier
            and supplier.company_id != company.id
        ):
            raise serializers.ValidationError(
                {
                    "supplier_id": (
                        "El proveedor no pertenece "
                        "a la empresa seleccionada."
                    )
                }
            )


        if not instance and not items:
            raise serializers.ValidationError(
                {
                    "items": (
                        "La compra debe contener "
                        "al menos un producto."
                    )
                }
            )


        if items is not None:
            product_ids = set()

            subtotal = Decimal("0.00")

            for item in items:
                product = item["product"]

                if (
                    company
                    and product.company_id
                    != company.id
                ):
                    raise serializers.ValidationError(
                        {
                            "items": (
                                f'El producto "{product.name}" '
                                "no pertenece a la empresa "
                                "seleccionada."
                            )
                        }
                    )


                if (
                    hasattr(
                        product,
                        "product_type",
                    )
                    and product.product_type
                    == "SERVICE"
                ):
                    raise serializers.ValidationError(
                        {
                            "items": (
                                f'"{product.name}" es un '
                                "servicio y no puede "
                                "agregarse a una compra "
                                "de inventario."
                            )
                        }
                    )


                if product.id in product_ids:
                    raise serializers.ValidationError(
                        {
                            "items": (
                                f'El producto "{product.name}" '
                                "está repetido en la compra."
                            )
                        }
                    )

                product_ids.add(
                    product.id
                )

                quantity = item[
                    "quantity"
                ]

                unit_cost = item[
                    "unit_cost"
                ]

                subtotal += (
                    quantity
                    * unit_cost
                )


            if discount_total > subtotal:
                raise serializers.ValidationError(
                    {
                        "discount_total": (
                            "El descuento no puede "
                            "ser mayor al subtotal "
                            "de la compra."
                        )
                    }
                )


            total = (
                subtotal
                - discount_total
                + tax_total
            )

            if total < Decimal("0.00"):
                raise serializers.ValidationError(
                    {
                        "total": (
                            "El total de la compra "
                            "no puede ser negativo."
                        )
                    }
                )


        return attrs


    @transaction.atomic
    def create(self, validated_data,):
        items_data = (
            validated_data.pop(
                "items",
                [],
            )
        )

        purchase = Purchase.objects.create(
            **validated_data
        )

        self._replace_items(
            purchase,
            items_data,
        )

        self._recalculate_totals(
            purchase,
        )

        return purchase


    @transaction.atomic
    def update(
        self,
        instance,
        validated_data,
    ):
        items_data = (
            validated_data.pop(
                "items",
                None,
            )
        )

        for (
            attribute,
            value,
        ) in validated_data.items():
            setattr(
                instance,
                attribute,
                value,
            )

        instance.save()

        if items_data is not None:
            self._replace_items(
                instance,
                items_data,
            )

        self._recalculate_totals(
            instance,
        )

        return instance


    def _replace_items(
        self,
        purchase,
        items_data,
    ):
        purchase.items.all().delete()

        purchase_items = []

        for item_data in items_data:
            quantity = item_data[
                "quantity"
            ]

            unit_cost = item_data[
                "unit_cost"
            ]

            subtotal = (
                quantity
                * unit_cost
            )

            purchase_items.append(
                PurchaseItem(
                    purchase=purchase,
                    product=item_data[
                        "product"
                    ],
                    quantity=quantity,
                    unit_cost=unit_cost,
                    subtotal=subtotal,
                )
            )

        PurchaseItem.objects.bulk_create(
            purchase_items
        )


    def _recalculate_totals(self, purchase,):
        subtotal = sum(
            (
                item.subtotal
                for item
                in purchase.items.all()
            ),
            Decimal("0.00"),
        )

        total = (
            subtotal
            - purchase.discount_total
            + purchase.tax_total
        )

        purchase.subtotal = subtotal
        purchase.total = total

        purchase.save(
            update_fields=(
                "subtotal",
                "total",
                "updated_at",
            )
        )


    def get_created_by_name( self, obj,):
        if not obj.created_by:
            return None

        return (
            obj.created_by.get_full_name()
            or obj.created_by.email
        )


