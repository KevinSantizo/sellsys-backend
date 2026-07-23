from rest_framework import serializers

from companies.models import Company, CompanyMembership


class CompanyOwnedModelSerializer(serializers.ModelSerializer):
    company_id = serializers.PrimaryKeyRelatedField(
        source='company',
        queryset=Company.objects.filter(is_active=True),
        write_only=True,
        required=False,
    )

    def validate_company_id(self, company):
        request = self.context['request']

        has_access = CompanyMembership.objects.filter(
            company=company,
            user=request.user,
            is_active=True,
        ).exists()

        if not has_access:
            raise serializers.ValidationError(
                'No tienes acceso a esta empresa.'
            )

        if (
            self.instance
            and self.instance.company_id != company.id
        ):
            raise serializers.ValidationError(
                'No puedes cambiar la empresa del registro.'
            )

        return company

    def validate(self, attrs):
        if self.instance is None and 'company' not in attrs:
            raise serializers.ValidationError({
                'company_id': (
                    'Debes enviar el ID de la empresa.'
                ),
            })

        return attrs