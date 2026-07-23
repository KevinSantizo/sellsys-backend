from django.contrib import admin
from .models import Branch

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