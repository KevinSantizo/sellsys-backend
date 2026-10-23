from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from rest_framework.test import (
    APIRequestFactory,
    force_authenticate,
)

from branches.models import Branch

from cash.models import (
    CashMovement,
    CashMovementDirection,
    CashMovementSource,
    CashMovementType,
    CashRegister,
    CashSession,
    CashSessionStatus,
)

from companies.models import (
    Company,
    CompanyMembership,
)

from expenses.models import (
    Expense,
    ExpenseCategory,
    ExpensePaymentMethod,
    ExpenseStatus,
)

from expenses.views import ExpenseViewSet

from reports.views import ReportSummaryView


class ExpenseCashFlowE2ETest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

        User = get_user_model()

        self.user = User.objects.create_user(
            email="expense-e2e@sellsys.test",
            password="Test12345!",
        )

        self.company = Company.objects.create(
            name="Empresa Expense E2E",
            is_active=True,
        )

        CompanyMembership.objects.create(
            user=self.user,
            company=self.company,
            role=CompanyMembership.Role.OWNER,
            is_active=True,
        )

        self.branch = Branch.objects.create(
            company=self.company,
            name="Sucursal Expense E2E",
            code="EXP-E2E",
            is_main=True,
            is_active=True,
        )

        self.category = (
            ExpenseCategory.objects.create(
                company=self.company,
                name="Servicios E2E",
                is_active=True,
            )
        )

        self.cash_register = (
            CashRegister.objects.create(
                company=self.company,
                branch=self.branch,
                name="Caja Gastos E2E",
                code="EXP-CAJA",
                is_active=True,
            )
        )

        self.cash_session = (
            CashSession.objects.create(
                company=self.company,
                branch=self.branch,
                cash_register=self.cash_register,
                opening_amount=Decimal(
                    "500.00"
                ),
                status=CashSessionStatus.OPEN,
                opened_by=self.user,
                notes="Sesión gastos E2E",
            )
        )

    def _create_expense(
        self,
        reference,
    ):
        today = timezone.localdate()

        payload = {
            "company_id": str(
                self.company.id
            ),
            "branch_id": str(
                self.branch.id
            ),
            "category_id": str(
                self.category.id
            ),
            "supplier_id": None,
            "description": (
                "Pago de servicio E2E"
            ),
            "amount": "75.00",
            "expense_date": (
                today.isoformat()
            ),
            "payment_method": (
                ExpensePaymentMethod.CASH
            ),
            "reference": reference,
            "notes": (
                "Gasto generado por E2E"
            ),
        }

        request = self.factory.post(
            "/api/expenses/",
            payload,
            format="json",
        )

        force_authenticate(
            request,
            user=self.user,
        )

        view = ExpenseViewSet.as_view(
            {
                "post": "create",
            }
        )

        response = view(request)

        self.assertEqual(
            response.status_code,
            201,
            response.data,
        )

        expense = Expense.objects.get(
            id=response.data["id"]
        )

        return expense

    def _complete_expense(
        self,
        expense,
    ):
        request = self.factory.post(
            (
                f"/api/expenses/"
                f"{expense.id}/complete/"
            ),
            {
                "cash_session_id": str(
                    self.cash_session.id
                ),
            },
            format="json",
        )

        force_authenticate(
            request,
            user=self.user,
        )

        view = ExpenseViewSet.as_view(
            {
                "post": "complete",
            }
        )

        response = view(
            request,
            pk=expense.id,
        )

        self.assertEqual(
            response.status_code,
            200,
            response.data,
        )

        expense.refresh_from_db()

        return expense

    def _get_summary_report(self):
        today = timezone.localdate()

        request = self.factory.get(
            "/api/reports/summary/",
            {
                "company_id": str(
                    self.company.id
                ),
                "branch_id": str(
                    self.branch.id
                ),
                "date_from": (
                    today.isoformat()
                ),
                "date_to": (
                    today.isoformat()
                ),
            },
        )

        force_authenticate(
            request,
            user=self.user,
        )

        response = (
            ReportSummaryView.as_view()(
                request
            )
        )

        self.assertEqual(
            response.status_code,
            200,
            response.data,
        )

        return response

    def test_cash_expense_updates_cash_and_report(
        self,
    ):
        expense = self._create_expense(
            "EXP-E2E-001"
        )

        self.assertEqual(
            expense.status,
            ExpenseStatus.DRAFT,
        )

        self.assertEqual(
            expense.amount,
            Decimal("75.00"),
        )

        # Crear el gasto todavía
        # no debe afectar caja.
        self.assertFalse(
            CashMovement.objects.filter(
                source_type=(
                    CashMovementSource.EXPENSE
                ),
                source_id=expense.id,
            ).exists()
        )

        expense = self._complete_expense(
            expense
        )

        self.assertEqual(
            expense.status,
            ExpenseStatus.COMPLETED,
        )

        cash_movement = (
            CashMovement.objects.get(
                source_type=(
                    CashMovementSource.EXPENSE
                ),
                source_id=expense.id,
                movement_type=(
                    CashMovementType.EXPENSE
                ),
            )
        )

        self.assertEqual(
            cash_movement.cash_session_id,
            self.cash_session.id,
        )

        self.assertEqual(
            cash_movement.direction,
            CashMovementDirection.OUT,
        )

        self.assertEqual(
            cash_movement.amount,
            Decimal("75.00"),
        )

        report_response = (
            self._get_summary_report()
        )

        self.assertEqual(
            report_response.data[
                "expenses"
            ]["count"],
            1,
        )

        self.assertEqual(
            report_response.data[
                "expenses"
            ]["total"],
            "75.00",
        )

        self.assertEqual(
            report_response.data[
                "cash"
            ]["in"]["total"],
            "0.00",
        )

        self.assertEqual(
            report_response.data[
                "cash"
            ]["out"]["total"],
            "75.00",
        )

        self.assertEqual(
            report_response.data[
                "cash"
            ]["net"],
            "-75.00",
        )

    def test_cancel_cash_expense_reverses_cash_and_report(
        self,
    ):
        expense = self._create_expense(
            "EXP-E2E-CANCEL-001"
        )

        expense = self._complete_expense(
            expense
        )

        original_movement = (
            CashMovement.objects.get(
                source_type=(
                    CashMovementSource.EXPENSE
                ),
                source_id=expense.id,
                movement_type=(
                    CashMovementType.EXPENSE
                ),
            )
        )

        self.assertEqual(
            original_movement.direction,
            CashMovementDirection.OUT,
        )

        self.assertEqual(
            original_movement.amount,
            Decimal("75.00"),
        )

        cancel_request = (
            self.factory.post(
                (
                    f"/api/expenses/"
                    f"{expense.id}/cancel/"
                ),
                {},
                format="json",
            )
        )

        force_authenticate(
            cancel_request,
            user=self.user,
        )

        cancel_view = (
            ExpenseViewSet.as_view(
                {
                    "post": "cancel",
                }
            )
        )

        cancel_response = cancel_view(
            cancel_request,
            pk=expense.id,
        )

        self.assertEqual(
            cancel_response.status_code,
            200,
            cancel_response.data,
        )

        expense.refresh_from_db()

        self.assertEqual(
            expense.status,
            ExpenseStatus.CANCELLED,
        )

        # La reversión debe ingresar
        # nuevamente los Q75.00.
        reversal_movement = (
            CashMovement.objects
            .filter(
                company=self.company,
                branch=self.branch,
                cash_session=(
                    self.cash_session
                ),
                direction=(
                    CashMovementDirection.IN
                ),
                amount=Decimal("75.00"),
            )
            .exclude(
                id=original_movement.id,
            )
            .first()
        )

        self.assertIsNotNone(
            reversal_movement,
        )

        report_response = (
            self._get_summary_report()
        )

        # El gasto cancelado deja
        # de contarse en gastos.
        self.assertEqual(
            report_response.data[
                "expenses"
            ]["count"],
            0,
        )

        self.assertEqual(
            report_response.data[
                "expenses"
            ]["total"],
            "0.00",
        )

        # Pero caja conserva
        # ambos movimientos:
        #
        # OUT 75 gasto
        # IN 75 reversión.
        self.assertEqual(
            report_response.data[
                "cash"
            ]["out"]["total"],
            "75.00",
        )

        self.assertEqual(
            report_response.data[
                "cash"
            ]["in"]["total"],
            "75.00",
        )

        self.assertEqual(
            report_response.data[
                "cash"
            ]["net"],
            "0.00",
        )