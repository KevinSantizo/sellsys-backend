from django.contrib import admin

from .models import (
    Expense,
    ExpenseCategory,
)

# Register your models here.

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(
    admin.ModelAdmin
):
    list_display = (
        "name",
        "company",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
        "company",
        "created_at",
    )

    search_fields = (
        "name",
        "description",
    )

    ordering = (
        "company",
        "name",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    list_select_related = (
        "company",
    )


@admin.register(Expense)
class ExpenseAdmin(
    admin.ModelAdmin
):
    list_display = (
        "description",
        "company",
        "branch",
        "category",
        "supplier",
        "amount",
        "expense_date",
        "payment_method",
        "status",
        "created_by",
    )

    list_filter = (
        "status",
        "payment_method",
        "company",
        "branch",
        "category",
        "expense_date",
    )

    search_fields = (
        "description",
        "reference",
        "notes",
        "supplier__name",
        "category__name",
    )

    ordering = (
        "-expense_date",
        "-created_at",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    list_select_related = (
        "company",
        "branch",
        "category",
        "supplier",
        "created_by",
    )

    date_hierarchy = (
        "expense_date"
    )
