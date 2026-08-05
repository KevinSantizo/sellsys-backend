from django.contrib import admin

from .models import (
    Payment,
    Sale,
    SaleItem,
)


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0

    fields = (
        "product",
        "product_name",
        "product_sku",
        "quantity",
        "unit_price",
        "discount_percent",
        "discount_amount",
        "line_total",
    )

    readonly_fields = (
        "product_name",
        "product_sku",
        "unit_price",
        "discount_amount",
        "line_total",
    )


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0

    fields = (
        "method",
        "amount",
        "reference",
        "created_by",
        "created_at",
    )

    readonly_fields = (
        "created_at",
    )


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        "sale_number",
        "company",
        "branch",
        "status",
        "customer_name",
        "subtotal",
        "discount_total",
        "total",
        "amount_received",
        "change_amount",
        "created_by",
        "completed_at",
        "created_at",
    )

    list_filter = (
        "status",
        "company",
        "branch",
        "created_at",
        "completed_at",
    )

    search_fields = (
        "sale_number",
        "customer_name",
        "customer_tax_id",
        "created_by__email",
    )

    readonly_fields = (
        "id",
        "sale_number",
        "subtotal",
        "discount_total",
        "tax_total",
        "total",
        "amount_received",
        "change_amount",
        "completed_at",
        "cancelled_at",
        "created_at",
        "updated_at",
    )

    ordering = (
        "-created_at",
    )

    date_hierarchy = "created_at"

    inlines = (
        SaleItemInline,
        PaymentInline,
    )

    fieldsets = (
        (
            "Información general",
            {
                "fields": (
                    "id",
                    "sale_number",
                    "company",
                    "branch",
                    "created_by",
                    "status",
                ),
            },
        ),
        (
            "Cliente",
            {
                "fields": (
                    "customer_name",
                    "customer_tax_id",
                    "notes",
                ),
            },
        ),
        (
            "Totales",
            {
                "fields": (
                    "subtotal",
                    "discount_total",
                    "tax_total",
                    "total",
                    "amount_received",
                    "change_amount",
                ),
            },
        ),
        (
            "Fechas",
            {
                "fields": (
                    "completed_at",
                    "cancelled_at",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = (
        "sale",
        "product_name",
        "product_sku",
        "quantity",
        "unit_price",
        "discount_percent",
        "line_total",
        "created_at",
    )

    list_filter = (
        "sale__company",
        "sale__branch",
        "created_at",
    )

    search_fields = (
        "sale__sale_number",
        "product_name",
        "product_sku",
        "product__name",
        "product__sku",
    )

    readonly_fields = (
        "id",
        "product_name",
        "product_sku",
        "discount_amount",
        "line_subtotal",
        "line_total",
        "created_at",
        "updated_at",
    )

    ordering = (
        "-created_at",
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "sale",
        "method",
        "amount",
        "reference",
        "created_by",
        "created_at",
    )

    list_filter = (
        "method",
        "sale__company",
        "sale__branch",
        "created_at",
    )

    search_fields = (
        "sale__sale_number",
        "reference",
        "created_by__email",
    )

    readonly_fields = (
        "id",
        "created_at",
    )

    ordering = (
        "-created_at",
    )