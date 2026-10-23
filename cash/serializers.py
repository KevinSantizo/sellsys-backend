from decimal import Decimal
from rest_framework import serializers
from branches.models import Branch
from companies.models import Company
from .models import CashRegister, CashSession, CashSessionStatus, CashMovement, CashMovementDirection


class CashRegisterSerializer(serializers.ModelSerializer):
    company_id = serializers.PrimaryKeyRelatedField(queryset=Company.objects.all(), source="company")
    branch_id = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.filter(is_active=True), source="branch")

    company_name = serializers.CharField(source="company.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = CashRegister
        fields = ( "id", "company_id", "company_name", "branch_id", "branch_name", "name", "code", "is_active", "created_at", "updated_at", )
        read_only_fields = ( "id", "created_at", "updated_at", )

    def validate(self, attrs):
        company = attrs.get("company", getattr(self.instance, "company", None))
        branch = attrs.get("branch", getattr(self.instance, "branch", None))

        if company and branch and branch.company_id != company.id:
            raise serializers.ValidationError({ "branch_id": "La sucursal seleccionada no pertenece a la empresa." })

        if self.instance:
            if "company" in attrs and attrs["company"].id != self.instance.company_id:
                raise serializers.ValidationError({ "company_id": "No se puede cambiar la empresa de una caja existente." })

            if "branch" in attrs and attrs["branch"].id != self.instance.branch_id:
                raise serializers.ValidationError({ "branch_id": "No se puede cambiar la sucursal de una caja existente." })

        return attrs


class CashMovementSerializer(serializers.ModelSerializer):
    direction_display = serializers.CharField(source="get_direction_display", read_only=True)
    movement_type_display = serializers.CharField(source="get_movement_type_display", read_only=True)
    source_type_display = serializers.CharField(source="get_source_type_display", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    cash_register_id = serializers.UUIDField(source="cash_session.cash_register_id", read_only=True)
    cash_register_name = serializers.CharField(source="cash_session.cash_register.name", read_only=True)
    cash_register_code = serializers.CharField(source="cash_session.cash_register.code", read_only=True)

    class Meta:
        model = CashMovement
        fields = (
             "id",
            "company_id",
            "branch_id",
            "cash_session_id",
            "cash_register_id",
            "cash_register_name",
            "cash_register_code",
            "direction",
            "direction_display",
            "movement_type",
            "movement_type_display",
            "amount",
            "source_type",
            "source_id",
            "reference",
            "notes",
            "created_by_name",
            "created_at",
            "source_type_display"
        )
        read_only_fields = fields

    def get_created_by_name(self, obj) -> str | None:
        if not obj.created_by:
            return None

        full_name = obj.created_by.get_full_name().strip()
        return full_name or obj.created_by.username


class CashSessionSerializer(serializers.ModelSerializer):
    company_id = serializers.UUIDField(source="company.id", read_only=True)
    branch_id = serializers.UUIDField(source="branch.id", read_only=True)
    cash_register_id = serializers.UUIDField(source="cash_register.id", read_only=True)

    company_name = serializers.CharField(source="company.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    cash_register_name = serializers.CharField(source="cash_register.name", read_only=True)
    cash_register_code = serializers.CharField(source="cash_register.code", read_only=True)

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    opened_by_name = serializers.SerializerMethodField()
    closed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CashSession
        fields = ( "id", "company_id", "company_name", "branch_id", "branch_name", "cash_register_id", "cash_register_name", "cash_register_code", "status", "status_display", "opening_amount", "expected_amount", "counted_amount", "difference", "opened_by_name", "closed_by_name", "opened_at", "closed_at", "notes", "created_at", "updated_at", )
        read_only_fields = fields

    def get_opened_by_name(self, obj) -> str | None:
        if not obj.opened_by:
            return None

        full_name = obj.opened_by.get_full_name().strip()
        return full_name or obj.opened_by.username

    def get_closed_by_name(self, obj) -> str | None:
        if not obj.closed_by:
            return None

        full_name = obj.closed_by.get_full_name().strip()
        return full_name or obj.closed_by.username


class OpenCashSessionSerializer(serializers.Serializer):
    company_id = serializers.PrimaryKeyRelatedField(queryset=Company.objects.all(), source="company")
    branch_id = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.filter(is_active=True), source="branch")
    cash_register_id = serializers.PrimaryKeyRelatedField(queryset=CashRegister.objects.filter(is_active=True), source="cash_register")
    opening_amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.00"))
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        company = attrs["company"]
        branch = attrs["branch"]
        cash_register = attrs["cash_register"]

        if branch.company_id != company.id:
            raise serializers.ValidationError({ "branch_id": "La sucursal seleccionada no pertenece a la empresa." })

        if cash_register.company_id != company.id:
            raise serializers.ValidationError({ "cash_register_id": "La caja seleccionada no pertenece a la empresa." })

        if cash_register.branch_id != branch.id:
            raise serializers.ValidationError({ "cash_register_id": "La caja seleccionada no pertenece a la sucursal." })

        if CashSession.objects.filter(cash_register=cash_register, status=CashSessionStatus.OPEN).exists():
            raise serializers.ValidationError({ "cash_register_id": "Esta caja ya tiene una sesión abierta." })

        return attrs


class CloseCashSessionSerializer(serializers.Serializer):
    counted_amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.00"))
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class ManualCashMovementSerializer(serializers.Serializer):
    cash_session_id = serializers.PrimaryKeyRelatedField(queryset=CashSession.objects.all(), source="cash_session")
    direction = serializers.ChoiceField(choices=CashMovementDirection.choices)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_cash_session_id(self, cash_session):
        if cash_session.status != CashSessionStatus.OPEN:
            raise serializers.ValidationError("La sesión de caja debe estar abierta.")

        return cash_session