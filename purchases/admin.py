from django.contrib import admin
from .models import Supplier

from .models import (
    Purchase,
    PurchaseItem,
    Supplier,
)


# Register your models here.

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "company",
        "tax_id",
        "contact_name",
        "phone",
        "email",
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
        "tax_id",
        "contact_name",
        "phone",
        "email",
    )

    ordering = (
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

class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0

    fields = (
        "product",
        "quantity",
        "unit_cost",
        "subtotal",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = (
        "purchase_number",
        "company",
        "branch",
        "supplier",
        "purchase_date",
        "payment_method",
        "status",
        "total",
        "created_by",
    )

    list_filter = (
        "status",
        "payment_method",
        "company",
        "branch",
        "supplier",
        "purchase_date",
    )

    search_fields = (
        "purchase_number",
        "supplier_invoice_number",
        "supplier__name",
        "notes",
    )

    ordering = (
        "-purchase_date",
        "-created_at",
    )

    readonly_fields = (
        "id",
        "completed_at",
        "cancelled_at",
        "created_at",
        "updated_at",
    )

    list_select_related = (
        "company",
        "branch",
        "supplier",
        "created_by",
    )

    date_hierarchy = "purchase_date"

    inlines = (
        PurchaseItemInline,
    )


@admin.register(PurchaseItem)
class PurchaseItemAdmin(admin.ModelAdmin):
    list_display = (
        "purchase",
        "product",
        "quantity",
        "unit_cost",
        "subtotal",
        "created_at",
    )

    list_filter = (
        "purchase__company",
        "purchase__branch",
        "purchase__status",
    )

    search_fields = (
        "purchase__purchase_number",
        "product__name",
        "product__sku",
    )

    ordering = (
        "-created_at",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    list_select_related = (
        "purchase",
        "product",
    )