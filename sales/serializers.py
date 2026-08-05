from decimal import Decimal, ROUND_HALF_UP
import uuid

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers
 
from catalog.models import Product
from companies.models import Company

from .models import (
    Payment,
    PaymentMethod,
    Sale,
    SaleItem,
    SaleStatus,
)

from .access import get_allowed_branches

from inventory.services import (
    InventoryStockError,
    deduct_sale_stock,
    lock_and_validate_sale_stock,
)




MONEY_PLACES = Decimal("0.01")


def quantize_money(value):
    return Decimal(value).quantize(
        MONEY_PLACES,
        rounding=ROUND_HALF_UP,
    )


def generate_sale_number():
    date_part = timezone.localdate().strftime(
        "%Y%m%d"
    )

    random_part = (
        uuid.uuid4().hex[:8].upper()
    )

    return (
        f"V-{date_part}-{random_part}"
    )


class SaleItemSerializer(
    serializers.ModelSerializer,
):
    product_id = serializers.UUIDField(
        source="product.id",
        read_only=True,
    )

    class Meta:
        model = SaleItem

        fields = (
            "id",
            "product_id",
            "product_name",
            "product_sku",
            "quantity",
            "unit_price",
            "discount_percent",
            "discount_amount",
            "line_subtotal",
            "line_total",
            "created_at",
        )

        read_only_fields = fields


class PaymentSerializer(
    serializers.ModelSerializer,
):
    method_display = serializers.CharField(
        source="get_method_display",
        read_only=True,
    )

    class Meta:
        model = Payment

        fields = (
            "id",
            "method",
            "method_display",
            "amount",
            "reference",
            "created_at",
        )

        read_only_fields = fields


class SaleListSerializer(
    serializers.ModelSerializer,
):
    company_name = serializers.CharField(
        source="company.name",
        read_only=True,
    )

    branch_name = serializers.CharField(
        source="branch.name",
        read_only=True,
    )

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    created_by_name = serializers.SerializerMethodField()
    item_count = serializers.IntegerField(
        read_only=True,
    )

    class Meta:
        model = Sale

        fields = (
            "id",
            "sale_number",
            "company_name",
            "branch_name",
            "status",
            "status_display",
            "customer_name",
            "subtotal",
            "discount_total",
            "tax_total",
            "total",
            "amount_received",
            "change_amount",
            "item_count",
            "created_by_name",
            "completed_at",
            "created_at",
        )

        read_only_fields = fields

    def get_created_by_name(self, instance):
        user = instance.created_by

        if not user:
            return None

        full_name = user.get_full_name()

        return (
            full_name
            or getattr(user, "email", "")
            or str(user)
        )


class SaleDetailSerializer(
    serializers.ModelSerializer,
):
    company_name = serializers.CharField(
        source="company.name",
        read_only=True,
    )

    branch_name = serializers.CharField(
        source="branch.name",
        read_only=True,
    )

    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    created_by_name = serializers.SerializerMethodField()

    items = SaleItemSerializer(
        many=True,
        read_only=True,
    )

    payments = PaymentSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = Sale

        fields = (
            "id",
            "sale_number",
            "company",
            "company_name",
            "branch",
            "branch_name",
            "status",
            "status_display",
            "customer_name",
            "customer_tax_id",
            "subtotal",
            "discount_total",
            "tax_total",
            "total",
            "amount_received",
            "change_amount",
            "notes",
            "created_by_name",
            "completed_at",
            "cancelled_at",
            "created_at",
            "updated_at",
            "items",
            "payments",
        )

        read_only_fields = fields

    def get_created_by_name(self, instance):
        user = instance.created_by

        if not user:
            return None

        full_name = user.get_full_name()

        return (
            full_name
            or getattr(user, "email", "")
            or str(user)
        )

class SaleItemInputSerializer(
    serializers.Serializer,
):
    product_id = serializers.UUIDField()

    quantity = serializers.DecimalField(
        max_digits=14,
        decimal_places=3,
        min_value=Decimal("0.001"),
    )

    discount_percent = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0.00"),
        max_value=Decimal("100.00"),
        default=Decimal("0.00"),
        required=False,
    )


class PaymentInputSerializer(
    serializers.Serializer,
):
    method = serializers.ChoiceField(
        choices=PaymentMethod.choices,
    )

    amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    reference = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        default="",
    )

    def validate(self, attrs):
        method = attrs["method"]
        reference = attrs.get(
            "reference",
            "",
        ).strip()

        if (
            method
            in {
                PaymentMethod.CARD,
                PaymentMethod.TRANSFER,
            }
            and not reference
        ):
            raise serializers.ValidationError({
                "reference": (
                    "Debes ingresar una referencia "
                    "para pagos con tarjeta o "
                    "transferencia."
                )
            })

        attrs["reference"] = reference

        return attrs

class SaleCheckoutSerializer(
    serializers.Serializer,
):
    company_id = serializers.UUIDField()
    branch_id = serializers.UUIDField()

    customer_name = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
        default="",
    )

    customer_tax_id = serializers.CharField(
        max_length=30,
        required=False,
        allow_blank=True,
        default="",
    )

    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

    items = SaleItemInputSerializer(
        many=True,
        allow_empty=False,
    )

    payments = PaymentInputSerializer(
        many=True,
        allow_empty=False,
    )

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user

        company_id = attrs["company_id"]
        branch_id = attrs["branch_id"]

        try:
            company = Company.objects.get(
                id=company_id,
                is_active=True,
                memberships__user=user,
                memberships__is_active=True,
            )
        except Company.DoesNotExist as error:
            raise serializers.ValidationError({
                "company_id": (
                    "No tienes acceso a esta empresa."
                )
            }) from error

        branch = (
            get_allowed_branches(
                user=user,
                company=company,
            )
            .filter(id=branch_id)
            .first()
        )

        if not branch:
            raise serializers.ValidationError({
                "branch_id": (
                    "No tienes acceso a esta "
                    "sucursal o está inactiva."
                )
            })

        item_data = attrs["items"]

        product_ids = [
            item["product_id"]
            for item in item_data
        ]

        if len(product_ids) != len(
            set(product_ids)
        ):
            raise serializers.ValidationError({
                "items": (
                    "No debes enviar el mismo "
                    "producto más de una vez."
                )
            })

        products = Product.objects.filter(
            id__in=product_ids,
            company=company,
            is_active=True,
        ).select_related(
            "company",
            "base_unit",
        )

        product_map = {
            product.id: product
            for product in products
        }

        missing_product_ids = [
            product_id
            for product_id in product_ids
            if product_id not in product_map
        ]

        if missing_product_ids:
            raise serializers.ValidationError({
                "items": (
                    "Uno o más productos no existen, "
                    "están inactivos o pertenecen "
                    "a otra empresa."
                )
            })

        calculated_items = []

        subtotal = Decimal("0.00")
        discount_total = Decimal("0.00")
        total = Decimal("0.00")

        for item in item_data:
            product = product_map[
                item["product_id"]
            ]

            quantity = item["quantity"]

            discount_percent = item.get(
                "discount_percent",
                Decimal("0.00"),
            )

            unit_price = quantize_money(
                product.sale_price
            )

            line_subtotal = quantize_money(
                quantity * unit_price
            )

            discount_amount = quantize_money(
                line_subtotal
                * discount_percent
                / Decimal("100")
            )

            line_total = quantize_money(
                line_subtotal
                - discount_amount
            )

            subtotal += line_subtotal
            discount_total += (
                discount_amount
            )
            total += line_total

            calculated_items.append({
                "product": product,
                "quantity": quantity,
                "unit_price": unit_price,
                "discount_percent": (
                    discount_percent
                ),
                "discount_amount": (
                    discount_amount
                ),
                "line_subtotal": (
                    line_subtotal
                ),
                "line_total": line_total,
            })

        subtotal = quantize_money(subtotal)

        discount_total = quantize_money(
            discount_total
        )

        total = quantize_money(total)

        payment_total = quantize_money(
            sum(
                (
                    payment["amount"]
                    for payment
                    in attrs["payments"]
                ),
                Decimal("0.00"),
            )
        )

        if payment_total < total:
            missing_amount = quantize_money(
                total - payment_total
            )

            raise serializers.ValidationError({
                "payments": (
                    "El pago es insuficiente. "
                    f"Faltan {missing_amount}."
                )
            })

        attrs["company"] = company
        attrs["branch"] = branch
        attrs["calculated_items"] = (
            calculated_items
        )
        attrs["subtotal"] = subtotal
        attrs["discount_total"] = (
            discount_total
        )
        attrs["total"] = total
        attrs["payment_total"] = (
            payment_total
        )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]

        company = validated_data[
            "company"
        ]

        branch = validated_data[
            "branch"
        ]

        calculated_items = validated_data[
            "calculated_items"
        ]

        payments_data = validated_data[
            "payments"
        ]

        subtotal = validated_data[
            "subtotal"
        ]

        discount_total = validated_data[
            "discount_total"
        ]

        total = validated_data["total"]

        payment_total = validated_data[
            "payment_total"
        ]

        change_amount = quantize_money(
            payment_total - total
        )

        try:
            locked_stocks = (
                lock_and_validate_sale_stock(
                    company=company,
                    branch=branch,
                    calculated_items=(
                        calculated_items
                    ),
                )
            )
        except InventoryStockError as error:
            raise serializers.ValidationError({
                "items": str(error),
            }) from error


        sale = Sale.objects.create(
            company=company,
            branch=branch,
            created_by=request.user,
            sale_number=(
                generate_sale_number()
            ),
            status=SaleStatus.COMPLETED,
            customer_name=validated_data.get(
                "customer_name",
                "",
            ).strip(),
            customer_tax_id=validated_data.get(
                "customer_tax_id",
                "",
            ).strip(),
            notes=validated_data.get(
                "notes",
                "",
            ).strip(),
            subtotal=subtotal,
            discount_total=(
                discount_total
            ),
            tax_total=Decimal("0.00"),
            total=total,
            amount_received=payment_total,
            change_amount=change_amount,
            completed_at=timezone.now(),
        )

        sale_items = [
            SaleItem(
                sale=sale,
                product=item["product"],
                product_name=(
                    item["product"].name
                ),
                product_sku=(
                    item["product"].sku
                ),
                quantity=item["quantity"],
                unit_price=(
                    item["unit_price"]
                ),
                discount_percent=(
                    item["discount_percent"]
                ),
                discount_amount=(
                    item["discount_amount"]
                ),
                line_subtotal=(
                    item["line_subtotal"]
                ),
                line_total=(
                    item["line_total"]
                ),
            )
            for item in calculated_items
        ]

        SaleItem.objects.bulk_create(
            sale_items,
            batch_size=100,
        )

        payments = [
            Payment(
                sale=sale,
                created_by=request.user,
                method=payment["method"],
                amount=payment["amount"],
                reference=payment.get(
                    "reference",
                    "",
                ),
            )
            for payment in payments_data
        ]

        Payment.objects.bulk_create(
            payments,
            batch_size=20,
        )

        deduct_sale_stock(
            sale=sale,
            calculated_items=calculated_items,
            locked_stocks=locked_stocks,
            user=request.user,
        )

        return sale

    def to_representation(self, instance):
        return SaleDetailSerializer(
            instance,
            context=self.context,
        ).data