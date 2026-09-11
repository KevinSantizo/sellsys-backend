from decimal import Decimal

from rest_framework.exceptions import ValidationError

from .models import CashSession, CashSessionStatus, CashMovement, CashMovementType


def get_open_cash_session(*, cash_session_id, company, branch):
    if not cash_session_id:
        raise ValidationError({ "cash_session_id": "Debes seleccionar una caja abierta." })

    try:
        cash_session = CashSession.objects.select_for_update().select_related("cash_register").get(
            pk=cash_session_id,
            status=CashSessionStatus.OPEN,
        )
    except CashSession.DoesNotExist:
        raise ValidationError({ "cash_session_id": "La sesión de caja no existe o ya está cerrada." })

    if cash_session.company_id != company.id:
        raise ValidationError({ "cash_session_id": "La sesión de caja no pertenece a la empresa." })

    if cash_session.branch_id != branch.id:
        raise ValidationError({ "cash_session_id": "La sesión de caja no pertenece a la sucursal." })

    return cash_session


def create_cash_movement(*, cash_session, direction, movement_type, amount, source_type, source_id, user, reference="", notes=""):
    amount = Decimal(amount)

    if amount <= Decimal("0.00"):
        raise ValidationError({ "amount": "El monto del movimiento debe ser mayor a cero." })

    if cash_session.status != CashSessionStatus.OPEN:
        raise ValidationError({ "cash_session_id": "La sesión de caja debe estar abierta." })

    existing_movement = CashMovement.objects.filter(
        source_type=source_type,
        source_id=source_id,
        movement_type=movement_type,
    ).exists()

    if existing_movement:
        raise ValidationError({ "detail": "Esta operación ya tiene un movimiento de caja registrado." })

    return CashMovement.objects.create(
        company=cash_session.company,
        branch=cash_session.branch,
        cash_session=cash_session,
        direction=direction,
        movement_type=movement_type,
        amount=amount,
        source_type=source_type,
        source_id=source_id,
        reference=reference,
        notes=notes,
        created_by=user,
    )


def reverse_cash_movement(*, original_movement, cash_session, user, reference="", notes=""):
    if CashMovement.objects.filter(reversal_of=original_movement).exists():
        raise ValidationError({ "detail": "Este movimiento de caja ya fue revertido." })

    direction = "OUT" if original_movement.direction == "IN" else "IN"

    return CashMovement.objects.create(
        company=cash_session.company,
        branch=cash_session.branch,
        cash_session=cash_session,
        direction=direction,
        movement_type=CashMovementType.REVERSAL,
        amount=original_movement.amount,
        source_type=original_movement.source_type,
        source_id=original_movement.source_id,
        reference=reference,
        notes=notes,
        reversal_of=original_movement,
        created_by=user,
    )