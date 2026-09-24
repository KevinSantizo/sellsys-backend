from django.contrib import admin

from .models import Brand, Category, Product, UnitOfMeasure

# Register your models here.

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'company',
        'parent',
        'is_active',
    )

    list_filter = (
        'is_active',
        'company',
    )

    search_fields = (
        'name',
        'company__name',
    )

    autocomplete_fields = (
        'company',
        'parent',
    )


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'company',
        'is_active',
    )

    list_filter = (
        'is_active',
        'company',
    )

    search_fields = (
        'name',
        'company__name',
    )

    autocomplete_fields = (
        'company',
    )


@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'symbol',
        'unit_type',
        'company',
        'allows_decimal',
        'is_active',
    )

    list_filter = (
        'unit_type',
        'allows_decimal',
        'is_active',
        'company',
    )

    search_fields = (
        'name',
        'symbol',
        'company__name',
    )

    autocomplete_fields = (
        'company',
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sku",
        "barcode",
        "company",
        "product_type",
        "category",
        "brand",
        "sale_price",
        "cost_price",
        "track_inventory",
        "is_active",
    )

    list_filter = (
        "product_type",
        "track_inventory",
        "is_active",
        "company",
        "category",
        "brand",
    )

    search_fields = (
        "name",
        "sku",
        "barcode",
        "company__name",
    )

    autocomplete_fields = (
        "company",
        "category",
        "brand",
        "base_unit",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = (
        "name",
    )