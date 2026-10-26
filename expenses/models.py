import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from branches.models import Branch
from companies.models import Company
from purchases.models import Supplier

# Create your models here.

class ExpensePaymentMethod(models.TextChoices):
    CASH = "CASH", "Efectivo"
    TRANSFER = "TRANSFER", "Transferencia"
    CARD = "CARD", "Tarjeta"
    OTHER = "OTHER", "Otro"


class ExpenseStatus(models.TextChoices):
    DRAFT = "DRAFT", "Borrador"
    COMPLETED = "COMPLETED", "Completado"
    CANCELLED = "CANCELLED", "Cancelado"


class ExpenseCategory(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False,)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="expense_categories", )
    name = models.CharField( max_length=100, )
    description = models.TextField( blank=True, )
    is_active = models.BooleanField( default=True, )
    created_at = models.DateTimeField( auto_now_add=True, ) 
    updated_at = models.DateTimeField( auto_now=True, )

    class Meta:
        db_table = "expense_categories"
        ordering = ( "name", "id", )
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "company",
                    "name",
                ),
                name="uniq_expense_category_company_name",
            ),
        ]

        indexes = [
            models.Index(
                fields=(
                    "company",
                    "is_active",
                    "name",
                ),
                name="expense_category_company_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.name} - "
            f"{self.company.name}"
        )


class Expense(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="expenses",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="expenses",
    )

    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.PROTECT,
        related_name="expenses",
    )

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="expenses",
        null=True,
        blank=True,
    )

    description = models.CharField(
        max_length=200,
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    expense_date = models.DateField(
        default=timezone.localdate,
    )

    payment_method = models.CharField(
        max_length=20,
        choices=ExpensePaymentMethod.choices,
        default=ExpensePaymentMethod.CASH,
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
    )

    notes = models.TextField(
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=ExpenseStatus.choices,
        default=ExpenseStatus.DRAFT,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_expenses",
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
        db_table = "expenses"

        ordering = (
            "-expense_date",
            "-created_at",
        )

        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="expense_amount_gt_zero",
            ),
        ]

        indexes = [
            models.Index(
                fields=(
                    "company",
                    "branch",
                    "expense_date",
                ),
                name="expense_company_branch_idx",
            ),
            models.Index(
                fields=(
                    "company",
                    "status",
                    "expense_date",
                ),
                name="expense_status_date_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.description} - "
            f"{self.amount}"
        )

    def mark_as_completed(self):
        self.status = ExpenseStatus.COMPLETED
        self.save(update_fields=["status", "updated_at"])

    def mark_as_cancelled(self):
        self.status = ExpenseStatus.CANCELLED
        self.save(update_fields=["status", "updated_at"])