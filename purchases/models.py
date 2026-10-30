import uuid
from decimal import Decimal
from django.db import models
from companies.models import Company


from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from branches.models import Branch
from catalog.models import Product

# Create your models here.

class Supplier(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="suppliers",
    )

    name = models.CharField(
        max_length=150,
    )

    tax_id = models.CharField(
        max_length=30,
        blank=True,
    )

    contact_name = models.CharField(
        max_length=150,
        blank=True,
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
    )

    email = models.EmailField(
        blank=True,
    )

    address = models.TextField(
        blank=True,
    )

    notes = models.TextField(
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "suppliers"

        ordering = (
            "name",
            "id",
        )

        constraints = [
            models.UniqueConstraint(
                fields=(
                    "company",
                    "name",
                ),
                name="uniq_supplier_name_company",
            ),
        ]

        indexes = [
            models.Index(
                fields=(
                    "company",
                    "is_active",
                    "name",
                ),
                name="supplier_company_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.name} - "
            f"{self.company.name}"
        )

class PurchaseStatus(models.TextChoices):
    DRAFT = "DRAFT", "Borrador"
    COMPLETED = "COMPLETED", "Completada"
    CANCELLED = "CANCELLED", "Cancelada"


class PurchasePaymentMethod(models.TextChoices):
    CASH = "CASH", "Efectivo"
    TRANSFER = "TRANSFER", "Transferencia"
    CARD = "CARD", "Tarjeta"
    SUPPLIER_CREDIT = (
        "SUPPLIER_CREDIT",
        "Crédito de proveedor",
    )
    OTHER = "OTHER", "Otro"


class Purchase(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="purchases",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="purchases",
    )

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="purchases",
    )

    purchase_number = models.CharField(
        max_length=30,
    )

    supplier_invoice_number = models.CharField(
        max_length=50,
        blank=True,
    )

    purchase_date = models.DateField(
        default=timezone.localdate,
    )

    payment_method = models.CharField(
        max_length=30,
        choices=PurchasePaymentMethod.choices,
        default=PurchasePaymentMethod.CASH,
    )

    status = models.CharField(
        max_length=20,
        choices=PurchaseStatus.choices,
        default=PurchaseStatus.DRAFT,
    )

    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    discount_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    tax_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    notes = models.TextField(
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_purchases",
        null=True,
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
        db_table = "purchases"

        ordering = (
            "-purchase_date",
            "-created_at",
        )

        constraints = [
            models.UniqueConstraint(
                fields=(
                    "company",
                    "purchase_number",
                ),
                name="uniq_purchase_number_company",
            ),

            models.CheckConstraint(
                condition=Q(
                    subtotal__gte=Decimal("0.00"),
                ),
                name="purchase_subtotal_gte_zero",
            ),

            models.CheckConstraint(
                condition=Q(
                    discount_total__gte=Decimal("0.00"),
                ),
                name="purchase_discount_gte_zero",
            ),

            models.CheckConstraint(
                condition=Q(
                    tax_total__gte=Decimal("0.00"),
                ),
                name="purchase_tax_gte_zero",
            ),

            models.CheckConstraint(
                condition=Q(
                    total__gte=Decimal("0.00"),
                ),
                name="purchase_total_gte_zero",
            ),
        ]

        indexes = [
            models.Index(
                fields=(
                    "company",
                    "branch",
                    "purchase_date",
                ),
                name="purchase_company_branch_idx",
            ),

            models.Index(
                fields=(
                    "company",
                    "status",
                    "purchase_date",
                ),
                name="purchase_status_date_idx",
            ),
        ]

    def mark_as_completed(self):
        self.status = (
            PurchaseStatus.COMPLETED
        )

        self.completed_at = timezone.now()
        self.cancelled_at = None

    def mark_as_cancelled(self):
        self.status = (
            PurchaseStatus.CANCELLED
        )

        self.cancelled_at = timezone.now()

    def __str__(self):
        return (
            f"{self.purchase_number} - "
            f"{self.supplier.name}"
        )


class PurchaseItem(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    purchase = models.ForeignKey(
        Purchase,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="purchase_items",
    )

    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
    )

    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    lot_number = models.CharField(
        max_length=100,
        blank=True,
    )

    expiration_date = models.DateField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "purchase_items"

        ordering = (
            "created_at",
        )

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    quantity__gt=Decimal("0.000"),
                ),
                name="purchase_item_quantity_gt_zero",
            ),

            models.CheckConstraint(
                condition=Q(
                    unit_cost__gte=Decimal("0.00"),
                ),
                name="purchase_item_cost_gte_zero",
            ),

            models.CheckConstraint(
                condition=Q(
                    subtotal__gte=Decimal("0.00"),
                ),
                name="purchase_item_subtotal_gte_zero",
            ),
        ]

        indexes = [
            models.Index(
                fields=(
                    "purchase",
                    "product",
                ),
                name="purchase_item_product_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.purchase.purchase_number} - "
            f"{self.product.name}"
        )