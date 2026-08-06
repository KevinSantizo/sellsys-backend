import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from branches.models import Branch
from catalog.models import Product
from companies.models import Company


class SaleStatus(models.TextChoices):
    DRAFT = "DRAFT", "Borrador"
    COMPLETED = "COMPLETED", "Completada"
    CANCELLED = "CANCELLED", "Cancelada"


class PaymentMethod(models.TextChoices):
    CASH = "CASH", "Efectivo"
    CARD = "CARD", "Tarjeta"
    TRANSFER = "TRANSFER", "Transferencia"


class Sale(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="sales",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="sales",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_sales",
        null=True,
        blank=True,
    )

    sale_number = models.CharField(
        max_length=30,
    )

    status = models.CharField(
        max_length=20,
        choices=SaleStatus.choices,
        default=SaleStatus.DRAFT,
    )

    customer_name = models.CharField(
        max_length=150,
        blank=True,
    )

    customer_tax_id = models.CharField(
        max_length=30,
        blank=True,
    )

    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    discount_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    tax_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    amount_received = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    change_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    notes = models.TextField(
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "sales"

        ordering = (
            "-created_at",
            "-id",
        )

        constraints = [
            models.UniqueConstraint(
                fields=(
                    "company",
                    "sale_number",
                ),
                name="uniq_sale_number_company",
            ),
            models.CheckConstraint(
                condition=Q(subtotal__gte=0),
                name="sale_subtotal_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(
                    discount_total__gte=0
                ),
                name="sale_discount_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(tax_total__gte=0),
                name="sale_tax_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(total__gte=0),
                name="sale_total_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(
                    amount_received__gte=0
                ),
                name="sale_received_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(
                    change_amount__gte=0
                ),
                name="sale_change_gte_zero",
            ),
        ]

        indexes = [
            models.Index(
                fields=(
                    "company",
                    "branch",
                    "status",
                    "created_at",
                ),
                name="sale_company_branch_idx",
            ),
            models.Index(
                fields=(
                    "company",
                    "sale_number",
                ),
                name="sale_number_idx",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.company_id
            and self.branch_id
            and self.branch.company_id
            != self.company_id
        ):
            raise ValidationError({
                "branch": (
                    "La sucursal no pertenece "
                    "a la empresa seleccionada."
                )
            })

    def mark_as_completed(self):
        self.status = SaleStatus.COMPLETED
        self.completed_at = timezone.now()
        self.cancelled_at = None

    def mark_as_cancelled(self):
        self.status = SaleStatus.CANCELLED
        self.cancelled_at = timezone.now()

    def __str__(self):
        return (
            f"{self.sale_number} - "
            f"{self.company.name}"
        )


class SaleItem(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="sale_items",
    )

    # Fotografía de los datos del producto
    # al momento de realizar la venta.
    product_name = models.CharField(
        max_length=200,
    )

    product_sku = models.CharField(
        max_length=100,
    )

    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
    )

    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )

    discount_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    line_subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    line_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "sale_items"

        ordering = (
            "created_at",
            "id",
        )

        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="sale_item_qty_gt_zero",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=0),
                name="sale_item_price_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(
                    discount_percent__gte=0
                )
                & Q(
                    discount_percent__lte=100
                ),
                name="sale_item_discount_range",
            ),
            models.CheckConstraint(
                condition=Q(
                    discount_amount__gte=0
                ),
                name="sale_item_discount_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(
                    line_subtotal__gte=0
                ),
                name="sale_item_subtotal_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(
                    line_total__gte=0
                ),
                name="sale_item_total_gte_zero",
            ),
        ]

        indexes = [
            models.Index(
                fields=(
                    "sale",
                    "product",
                ),
                name="sale_item_product_idx",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.sale_id
            and self.product_id
            and self.product.company_id
            != self.sale.company_id
        ):
            raise ValidationError({
                "product": (
                    "El producto no pertenece "
                    "a la empresa de la venta."
                )
            })

    def __str__(self):
        return (
            f"{self.product_name} "
            f"x {self.quantity}"
        )


class Payment(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name="payments",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="registered_payments",
        null=True,
        blank=True,
    )

    method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "sale_payments"

        ordering = (
            "created_at",
            "id",
        )

        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="payment_amount_gt_zero",
            ),
        ]

        indexes = [
            models.Index(
                fields=(
                    "sale",
                    "method",
                ),
                name="payment_sale_method_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.get_method_display()} - "
            f"{self.amount}"
        )