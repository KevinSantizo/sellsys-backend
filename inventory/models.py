import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from branches.models import Branch
from catalog.models import Product
from companies.models import Company


class InventoryMovementType(models.TextChoices):
    INITIAL_STOCK = ("INITIAL_STOCK", "Stock inicial",)
    PURCHASE = ("PURCHASE", "Entrada por compra",)
    PURCHASE_REVERSAL = "PURCHASE_REVERSAL", "Reversión de compra"
    SALE = ("SALE", "Salida por venta", )
    ADJUSTMENT_IN = ("ADJUSTMENT_IN", "Ajuste de entrada",)
    ADJUSTMENT_OUT = ("ADJUSTMENT_OUT", "Ajuste de salida",)
    SALE_RETURN = ("SALE_RETURN", "Devolución de venta",)


class ProductStock(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="product_stocks",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="product_stocks",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="stocks",
    )

    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=Decimal("0.000"),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "product_stocks"

        ordering = (
            "product__name",
            "branch__name",
        )

        constraints = [
            models.UniqueConstraint(
                fields=(
                    "company",
                    "branch",
                    "product",
                ),
                name=(
                    "uniq_product_stock_"
                    "company_branch_product"
                ),
            ),
            models.CheckConstraint(
                condition=Q(quantity__gte=0),
                name=(
                    "product_stock_quantity_"
                    "gte_zero"
                ),
            ),
        ]

        indexes = [
            models.Index(
                fields=(
                    "company",
                    "branch",
                    "product",
                ),
                name="product_stock_lookup_idx",
            ),
            models.Index(
                fields=(
                    "company",
                    "branch",
                ),
                name="product_stock_branch_idx",
            ),
        ]

    def clean(self):
        super().clean()

        errors = {}

        if (
            self.branch_id
            and self.company_id
            and self.branch.company_id
            != self.company_id
        ):
            errors["branch"] = (
                "La sucursal no pertenece a "
                "la empresa seleccionada."
            )

        if (
            self.product_id
            and self.company_id
            and self.product.company_id
            != self.company_id
        ):
            errors["product"] = (
                "El producto no pertenece a "
                "la empresa seleccionada."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"{self.product.name} - "
            f"{self.branch.name}: "
            f"{self.quantity}"
        )


class InventoryMovement(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="inventory_movements",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="inventory_movements",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="inventory_movements",
    )

    movement_type = models.CharField(
        max_length=30,
        choices=InventoryMovementType.choices,
    )

    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
    )

    previous_stock = models.DecimalField(
        max_digits=14,
        decimal_places=3,
    )

    new_stock = models.DecimalField(
        max_digits=14,
        decimal_places=3,
    )

    sale = models.ForeignKey(
        "sales.Sale",
        on_delete=models.PROTECT,
        related_name="inventory_movements",
        null=True,
        blank=True,
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
    )

    notes = models.TextField(
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_inventory_movements",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "inventory_movements"

        ordering = (
            "-created_at",
            "-id",
        )

        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name=(
                    "inventory_movement_quantity_"
                    "gt_zero"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    previous_stock__gte=0,
                ),
                name=(
                    "inventory_movement_previous_"
                    "stock_gte_zero"
                ),
            ),
            models.CheckConstraint(
                condition=Q(
                    new_stock__gte=0,
                ),
                name=(
                    "inventory_movement_new_"
                    "stock_gte_zero"
                ),
            ),
        ]

        indexes = [
            models.Index(
                fields=(
                    "company",
                    "branch",
                    "product",
                    "created_at",
                ),
                name="inventory_movement_lookup_idx",
            ),
            models.Index(
                fields=(
                    "company",
                    "movement_type",
                    "created_at",
                ),
                name="inventory_movement_type_idx",
            ),
            models.Index(
                fields=(
                    "sale",
                ),
                name="inventory_movement_sale_idx",
            ),
        ]

    def clean(self):
        super().clean()

        errors = {}

        if (
            self.branch_id
            and self.company_id
            and self.branch.company_id
            != self.company_id
        ):
            errors["branch"] = (
                "La sucursal no pertenece a "
                "la empresa seleccionada."
            )

        if (
            self.product_id
            and self.company_id
            and self.product.company_id
            != self.company_id
        ):
            errors["product"] = (
                "El producto no pertenece a "
                "la empresa seleccionada."
            )

        if (
            self.sale_id
            and self.company_id
            and self.sale.company_id
            != self.company_id
        ):
            errors["sale"] = (
                "La venta no pertenece a "
                "la empresa seleccionada."
            )

        if (
            self.sale_id
            and self.branch_id
            and self.sale.branch_id
            != self.branch_id
        ):
            errors["sale"] = (
                "La venta no pertenece a "
                "la sucursal seleccionada."
            )

        if (
            self.movement_type
            == InventoryMovementType.SALE
            and not self.sale_id
        ):
            errors["sale"] = (
                "Los movimientos por venta "
                "deben estar asociados a una venta."
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f"{self.get_movement_type_display()} - "
            f"{self.product.name} - "
            f"{self.quantity}"
        )