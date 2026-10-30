from django.contrib import admin
from .models import Suggestion

# Register your models here.
@admin.register(Suggestion)
class SuggestionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "company",
        "branch",
        "suggestion_type",
        "status",
        "created_by",
        "created_at",
    )

    list_filter = (
        "status",
        "suggestion_type",
        "company",
        "created_at",
    )

    search_fields = (
        "title",
        "description",
        "created_by__email",
        "company__name",
    )

    readonly_fields = (
        "created_by",
        "created_at",
        "updated_at",
    )
