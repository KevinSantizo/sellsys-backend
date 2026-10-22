from django.contrib import admin

from .models import (
    Company,
    CompanyMembership,
    CompanyModule,
    CompanySettings,
    Module,
)

# Register your models here.

class CompanyMembershipInline(admin.TabularInline):
    model = CompanyMembership
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "business_type",
        "currency",
        "is_active",
        "created_at",
        "logo_url"
    )

    list_filter = (
        "business_type",
        "currency",
        "is_active",
    )

    search_fields = (
        "name",
        "legal_name",
        "tax_identifier",
    )

    ordering = ("name",)
    inlines = (CompanyMembershipInline,)


@admin.register(CompanyMembership)
class CompanyMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "company",
        "role",
        "is_active",
    )

    list_filter = (
        "role",
        "is_active",
    )

    search_fields = (
        "user__email",
        "company__name",
    )

    autocomplete_fields = (
        "user",
        "company",
    )


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    list_display = (
        'company',
        'allow_negative_stock',
        'require_customer_on_sale',
        'allow_manual_discounts',
    )

    search_fields = (
        'company__name',
    )

    autocomplete_fields = (
        'company',
    )


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'is_core',
        'default_enabled',
        'is_active',
        'display_order',
    )

    list_filter = (
        'is_core',
        'default_enabled',
        'is_active',
    )

    search_fields = (
        'code',
        'name',
    )

    ordering = (
        'display_order',
        'name',
    )


@admin.register(CompanyModule)
class CompanyModuleAdmin(admin.ModelAdmin):
    list_display = (
        'company',
        'module',
        'enabled',
    )

    list_filter = (
        'enabled',
        'module',
    )

    search_fields = (
        'company__name',
        'module__name',
        'module__code',
    )

    autocomplete_fields = (
        'company',
        'module',
    )
