from django.contrib import admin
from .models import Branch, BranchMembership


# Register your models here.

@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "company",
        "is_main",
        "is_active",
    )

    list_filter = (
        "is_main",
        "is_active",
    )

    search_fields = (
        "name",
        "code",
        "company__name",
    )

    autocomplete_fields = ("company",)
    ordering = ("company__name", "name")


@admin.register(BranchMembership)
class BranchMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "company_membership",
        "branch",
        "is_default",
        "is_active",
    )

    list_filter = (
        "is_default",
        "is_active",
        "branch__company",
    )

    search_fields = (
        "company_membership__user__email",
        "company_membership__company__name",
        "branch__name",
    )

    autocomplete_fields = (
        "company_membership",
        "branch",
    )