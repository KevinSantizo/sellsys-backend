from decimal import Decimal, ROUND_HALF_UP
import uuid

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers
 
from catalog.models import Product
from companies.models import Company, CompanySettings

from cash.models import CashMovementDirection, CashMovementType, CashMovementSource
from cash.services import get_open_cash_session, create_cash_movement
from common.access import validate_company_branch_access

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

from drf_spectacular.utils import extend_schema_field

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

    @extend_schema_field(
        serializers.CharField(
            allow_null=True,
        )
    )
    def get_created_by_name(self, instance) -> str | None:
        user = instance.created_by

        if not user:
            return None

        full_name = user.get_full_name().strip()

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

    cart_discount_type_display = serializers.CharField(
        source="get_cart_discount_type_display",
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
            "cart_discount_type",
            "cart_discount_type_display",
            "cart_discount_value",
            "cart_discount_amount",
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

    @extend_schema_field(
        serializers.CharField(
            allow_null=True,
        )
    )
    def get_created_by_name(self, instance) -> str | None:
        user = instance.created_by

        if not user:
            return None

        full_name = user.get_full_name().strip()

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


class SaleCheckoutSerializer(serializers.Serializer,):
    company_id = serializers.UUIDField()
    branch_id = serializers.UUIDField()
    cash_session_id = serializers.UUIDField(required=False, allow_null=True)
    customer_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="",)
    customer_tax_id = serializers.CharField(max_length=30, required=False, allow_blank=True, default="",)
    notes = serializers.CharField(required=False, allow_blank=True, default="",)
    items = SaleItemInputSerializer(many=True, allow_empty=False,)
    payments = PaymentInputSerializer(many=True, allow_empty=False,)
    cart_discount_type = serializers.ChoiceField( choices= Sale.DiscountType.choices, required=False, default=Sale.DiscountType.NONE, )
    cart_discount_value = serializers.DecimalField( max_digits=12, decimal_places=2, min_value=Decimal("0.00"), required=False, default=Decimal("0.00"), )

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user

        company_id = attrs["company_id"]
        branch_id = attrs["branch_id"]

        membership, branch = validate_company_branch_access(
            user,
            company_id,
            branch_id,
        )

        company = membership.company
        item_data = attrs["items"]

        raw_idempotency_key = request.headers.get("Idempotency-Key")

        if not raw_idempotency_key:
            raise serializers.ValidationError({
                "idempotency_key": "Debes enviar el encabezado Idempotency-Key."
            })

        try:
            idempotency_key = uuid.UUID(raw_idempotency_key)
        except (ValueError, TypeError, AttributeError):
            raise serializers.ValidationError({
                "idempotency_key": "El Idempotency-Key debe ser un UUID válido."
            })

        existing_sale = Sale.objects.filter(
            company=company,
            idempotency_key=idempotency_key,
        ).first()

        if existing_sale:
            if existing_sale.branch_id != branch.id:
                raise serializers.ValidationError({
                    "idempotency_key": "El Idempotency-Key ya fue utilizado en otra sucursal."
                })

            attrs["idempotency_key"] = idempotency_key
            attrs["existing_sale"] = existing_sale

            return attrs

        attrs["idempotency_key"] = idempotency_key

        company_settings = CompanySettings.objects.filter(company=company).first()
        product_ids = [
            item["product_id"]
            for item in item_data
        ]

        if len(product_ids) != len(set(product_ids)):
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
        line_discount_total = Decimal("0.00")
        subtotal_after_line_discounts = Decimal("0.00")

        for item in item_data:
            product = product_map[item["product_id"]]
            quantity = item["quantity"]

            if (
                    product.base_unit
                    and not product.base_unit.allows_decimal
                    and quantity != quantity.to_integral_value()
            ):
                raise serializers.ValidationError({
                    "items": (
                        f'El producto "{product.name}" '
                        "no permite cantidades decimales."
                    )
                })

            discount_percent = item.get("discount_percent", Decimal("0.00"))
            unit_price = quantize_money(product.sale_price)
            line_subtotal = quantize_money(quantity * unit_price)
            discount_amount = quantize_money(line_subtotal * discount_percent / Decimal("100"))
            line_total = quantize_money(line_subtotal - discount_amount)

            subtotal += line_subtotal
            line_discount_total += discount_amount
            subtotal_after_line_discounts += line_total

            calculated_items.append({
                "product": product,
                "quantity": quantity,
                "unit_price": unit_price,
                "discount_percent": discount_percent,
                "discount_amount": discount_amount,
                "line_subtotal": line_subtotal,
                "line_total": line_total,
            })

        subtotal = quantize_money(subtotal)
        line_discount_total = quantize_money(line_discount_total)
        subtotal_after_line_discounts = quantize_money(subtotal_after_line_discounts)

        cart_discount_type = attrs.get("cart_discount_type", Sale.DiscountType.NONE)
        cart_discount_value = attrs.get("cart_discount_value", Decimal("0.00"))
        cart_discount_amount = Decimal("0.00")

        if cart_discount_type == Sale.DiscountType.PERCENTAGE:
            if cart_discount_value > Decimal("100.00"):
                raise serializers.ValidationError({
                    "cart_discount_value": (
                        "El descuento porcentual "
                        "no puede ser mayor al 100%."
                    )
                })

            cart_discount_amount = subtotal_after_line_discounts * cart_discount_value / Decimal("100")

        elif cart_discount_type == Sale.DiscountType.FIXED:
            if cart_discount_value > subtotal_after_line_discounts:
                raise serializers.ValidationError({
                    "cart_discount_value": (
                        "El descuento no puede ser mayor "
                        "al total del carrito."
                    )
                })

            cart_discount_amount = cart_discount_value

        else:
            cart_discount_type = Sale.DiscountType.NONE
            cart_discount_value = Decimal("0.00")
            cart_discount_amount = Decimal("0.00")

        cart_discount_amount = quantize_money(cart_discount_amount)
        discount_total = quantize_money(line_discount_total + cart_discount_amount)
        total = quantize_money(subtotal_after_line_discounts - cart_discount_amount)

        if company_settings:
            if not company_settings.allow_manual_discounts and discount_total > Decimal("0.00"):
                raise serializers.ValidationError({
                    "discount": "Los descuentos manuales no están habilitados para esta empresa."
                })

            if company_settings.allow_manual_discounts and subtotal > Decimal("0.00"):
                effective_discount_percent = discount_total * Decimal("100") / subtotal

                if effective_discount_percent > company_settings.max_discount_percent:
                    raise serializers.ValidationError({
                        "discount": (
                            "El descuento total supera el porcentaje máximo "
                            "permitido para esta empresa."
                        )
                    })

        if (
                company_settings
                and company_settings.require_customer_on_sale
                and not attrs.get("customer_name", "").strip()
        ):
            raise serializers.ValidationError({
                "customer_name": "Debes ingresar un cliente para registrar la venta."
            })

        payment_total = quantize_money(
            sum(
                (
                    payment["amount"]
                    for payment in attrs["payments"]
                ),
                Decimal("0.00"),
            )
        )

        cash_total = quantize_money(
            sum(
                (
                    payment["amount"]
                    for payment in attrs["payments"]
                    if payment["method"] == PaymentMethod.CASH
                ),
                Decimal("0.00"),
            )
        )

        if payment_total < total:
            missing_amount = quantize_money(total - payment_total)

            raise serializers.ValidationError({
                "payments": (
                    "El pago es insuficiente. "
                    f"Faltan {missing_amount}."
                )
            })

        change_amount = quantize_money(payment_total - total)

        if cash_total > Decimal("0.00") and not attrs.get("cash_session_id"):
            raise serializers.ValidationError({
                "cash_session_id": (
                    "Debes seleccionar una caja abierta "
                    "para registrar pagos en efectivo."
                )
            })

        if change_amount > cash_total:
            raise serializers.ValidationError({
                "payments": (
                    "El cambio no puede ser mayor "
                    "al monto recibido en efectivo."
                )
            })

        attrs["company"] = company
        attrs["branch"] = branch
        attrs["calculated_items"] = calculated_items
        attrs["subtotal"] = subtotal
        attrs["line_discount_total"] = line_discount_total
        attrs["cart_discount_type"] = cart_discount_type
        attrs["cart_discount_value"] = cart_discount_value
        attrs["cart_discount_amount"] = cart_discount_amount
        attrs["discount_total"] = discount_total
        attrs["total"] = total
        attrs["payment_total"] = payment_total
        attrs["cash_total"] = cash_total

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]

        existing_sale = validated_data.get("existing_sale")

        if existing_sale:
            return existing_sale

        company = validated_data["company"]
        branch = validated_data["branch"]
        calculated_items = validated_data["calculated_items"]
        payments_data = validated_data["payments"]
        subtotal = validated_data["subtotal"]
        discount_total = validated_data["discount_total"]
        cart_discount_type = validated_data["cart_discount_type"]
        cart_discount_value = validated_data["cart_discount_value"]
        cart_discount_amount = validated_data["cart_discount_amount"]
        total = validated_data["total"]
        payment_total = validated_data["payment_total"]
        cash_total = validated_data["cash_total"]
        change_amount = quantize_money(payment_total - total)
        idempotency_key = validated_data.get("idempotency_key")

        try:
            with transaction.atomic():
                sale = Sale.objects.create(
                    company=company,
                    branch=branch,
                    created_by=request.user,
                    sale_number=generate_sale_number(),
                    idempotency_key=idempotency_key,
                    status=SaleStatus.COMPLETED,
                    customer_name=validated_data.get("customer_name", "").strip(),
                    customer_tax_id=validated_data.get("customer_tax_id", "").strip(),
                    notes=validated_data.get("notes", "").strip(),
                    subtotal=subtotal,
                    discount_total=discount_total,
                    cart_discount_type=cart_discount_type,
                    cart_discount_value=cart_discount_value,
                    cart_discount_amount=cart_discount_amount,
                    tax_total=Decimal("0.00"),
                    total=total,
                    amount_received=payment_total,
                    change_amount=change_amount,
                    completed_at=timezone.now(),
                )
        except IntegrityError:
            if idempotency_key:
                existing_sale = Sale.objects.filter(
                    company=company,
                    idempotency_key=idempotency_key,
                ).first()

                if existing_sale:
                    return existing_sale

            raise

        cash_session = None

        if cash_total > Decimal("0.00"):
            cash_session = get_open_cash_session(
                cash_session_id=validated_data.get("cash_session_id"),
                company=company,
                branch=branch,
            )

        try:
            locked_stocks = lock_and_validate_sale_stock(
                company=company,
                branch=branch,
                calculated_items=calculated_items,
            )
        except InventoryStockError as error:
            raise serializers.ValidationError({
                "items": str(error),
            }) from error


        sale_items = [
            SaleItem(
                sale=sale,
                product=item["product"],
                product_name=item["product"].name,
                product_sku=item["product"].sku,
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                unit_cost=item["product"].cost_price,
                discount_percent=item["discount_percent"],
                discount_amount=item["discount_amount"],
                line_subtotal=item["line_subtotal"],
                line_total=item["line_total"],
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
                reference=payment.get("reference", ""),
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

        if cash_session:
            cash_amount = quantize_money(cash_total - change_amount)

            if cash_amount > Decimal("0.00"):
                create_cash_movement(
                    cash_session=cash_session,
                    direction=CashMovementDirection.IN,
                    movement_type=CashMovementType.SALE,
                    amount=cash_amount,
                    source_type=CashMovementSource.SALE,
                    source_id=sale.id,
                    reference=sale.sale_number,
                    notes=f"Venta {sale.sale_number}",
                    user=request.user,
                )

        return sale


    def to_representation(self, instance):
        return SaleDetailSerializer(
            instance,
            context=self.context,
        ).data