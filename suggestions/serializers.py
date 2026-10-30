from rest_framework import serializers

from .models import Suggestion


class SuggestionSerializer(
    serializers.ModelSerializer
):
    company_name = serializers.CharField(
        source="company.name",
        read_only=True,
    )

    branch_name = serializers.CharField(
        source="branch.name",
        read_only=True,
    )

    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Suggestion

        fields = (
            "id",
            "company",
            "company_name",
            "branch",
            "branch_name",
            "created_by",
            "created_by_name",
            "suggestion_type",
            "title",
            "description",
            "status",
            "admin_notes",
            "created_at",
            "updated_at",
        )

        read_only_fields = (
            "id",
            "created_by",
            "status",
            "admin_notes",
            "created_at",
            "updated_at",
        )

    def get_created_by_name(
        self,
        obj,
    ):
        if not obj.created_by:
            return None

        return (
            obj.created_by.get_full_name().strip()
            or obj.created_by.email
        )