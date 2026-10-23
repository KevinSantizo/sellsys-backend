import uuid

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q

from branches.models import Branch
from companies.models import Company

# Create your models here.

class CashSessionStatus(models.TextChoices):
    OPEN = "OPEN", "Abierta"
    CLOSED = "CLOSED", "Cerrada"


class CashMovementDirection(models.TextChoices):
    IN = "IN", "Entrada"
    OUT = "OUT", "Salida"


class CashMovementType(models.TextChoices):
    SALE = "SALE", "Venta"
    EXPENSE = "EXPENSE", "Gasto"
    PURCHASE = "PURCHASE", "Compra"
    MANUAL_IN = "MANUAL_IN", "Entrada manual"
    MANUAL_OUT = "MANUAL_OUT", "Salida manual"
    REVERSAL = "REVERSAL", "Reversión"


class CashMovementSource(models.TextChoices):
    SALE = "SALE", "Venta"
    EXPENSE = "EXPENSE", "Gasto"
    PURCHASE = "PURCHASE", "Compra"
    MANUAL = "MANUAL", "Manual"


class CashRegister(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="cash_registers",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="cash_registers",
    )

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cash_registers"
        ordering = ( "-created_at", "-id", )

        constraints = [
            models.UniqueConstraint(
                fields=( "company", "branch", "code", ),
                name="uniq_cash_register_code",
            ),
        ]

        indexes = [
            models.Index(
                fields=( "company", "branch", "is_active", ),
                name="cash_register_branch_idx",
            ),
        ]

    def __str__(self):
        return f"{self.name} - {self.branch.name}"


class CashSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="cash_sessions",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="cash_sessions",
    )

    cash_register = models.ForeignKey(
        CashRegister,
        on_delete=models.PROTECT,
        related_name="sessions",
    )

    status = models.CharField(
        max_length=20,
        choices=CashSessionStatus.choices,
        default=CashSessionStatus.OPEN,
    )

    opening_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    expected_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    counted_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    difference = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="opened_cash_sessions",
        null=True,
        blank=True,
    )

    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="closed_cash_sessions",
        null=True,
        blank=True,
    )

    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cash_sessions"
        ordering = ( "-opened_at", )

        constraints = [
            models.CheckConstraint(
                condition=Q(opening_amount__gte=Decimal("0.00")),
                name="cash_opening_amount_gte_zero",
            ),
        ]

        indexes = [
            models.Index(
                fields=( "company", "branch", "status", ),
                name="cash_session_status_idx",
            ),

            models.Index(
                fields=( "cash_register", "status", ),
                name="cash_session_register_idx",
            ),
        ]

    def __str__(self):
        return f"{self.cash_register.name} - {self.get_status_display()}"


class CashMovement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="cash_movements",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="cash_movements",
    )

    cash_session = models.ForeignKey(
        CashSession,
        on_delete=models.PROTECT,
        related_name="movements",
    )

    direction = models.CharField(
        max_length=10,
        choices=CashMovementDirection.choices,
    )

    movement_type = models.CharField(
        max_length=30,
        choices=CashMovementType.choices,
    )

    amount = models.DecimalField(max_digits=14, decimal_places=2)

    source_type = models.CharField(
        max_length=20,
        choices=CashMovementSource.choices,
        null=True,
        blank=True,
    )

    source_id = models.UUIDField(null=True, blank=True)

    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    reversal_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="reversals",
        null=True,
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_cash_movements",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cash_movements"
        ordering = ( "-created_at", )

        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=Decimal("0.00")),
                name="cash_movement_amount_gt_zero",
            ),
        ]

        indexes = [
            models.Index(
                fields=(
                    "company",
                    "branch",
                    "created_at",
                ),
                name="cash_movement_branch_idx",
            ),

            models.Index(
                fields=(
                    "company",
                    "branch",
                    "direction",
                    "created_at",
                ),
                name="cash_movement_direction_idx",
            ),

            models.Index(
                fields=(
                    "cash_session",
                    "created_at",
                ),
                name="cash_movement_session_idx",
            ),

            models.Index(
                fields=(
                    "source_type",
                    "source_id",
                ),
                name="cash_movement_source_idx",
            ),
        ]

    def __str__(self):
        return f"{self.get_direction_display()} {self.amount} - {self.get_movement_type_display()}"