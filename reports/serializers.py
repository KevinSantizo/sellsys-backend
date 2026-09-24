from rest_framework import serializers


class ReportSummaryQuerySerializer(serializers.Serializer):
    company_id = serializers.UUIDField()
    branch_id = serializers.UUIDField()
    date_from = serializers.DateField()
    date_to = serializers.DateField()

    def validate(self, attrs):
        if attrs["date_from"] > attrs["date_to"]:
            raise serializers.ValidationError({
                "date_to": "La fecha final debe ser mayor o igual a la fecha inicial."
            })

        return attrs


class InventoryReportQuerySerializer(serializers.Serializer):
    company_id = serializers.UUIDField()
    branch_id = serializers.UUIDField()