from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from rest_framework import status
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
from catalog.models import Product, UnitOfMeasure
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
from inventory.models import ProductStock
from purchases.models import (
    Purchase,
    PurchasePaymentMethod,
    PurchaseStatus,
    Supplier,
)
from reports.serializers import (
    ReportSummaryQuerySerializer,
)
from reports.views import (
    CashReportView,
    ExpensesReportView,
    InventoryReportView,
    ProfitabilityReportView,
    PurchasesReportView,
    ReportDailyView,
    ReportSummaryView,
    SalesReportView,
)
from sales.models import (
    Sale,
    SaleItem,
    SaleStatus,
)


User = get_user_model()


class ReportTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="reports@sellsys.tests",
            password="SellSys123!",
        )

        self.company = Company.objects.create(
            name="Empresa A",
        )

        self.branch = Branch.objects.create(
            company=self.company,
            name="Sucursal A",
            code="A",
        )

        self.branch_b = Branch.objects.create(
            company=self.company,
            name="Sucursal B",
            code="B",
        )

        CompanyMembership.objects.create(
            company=self.company,
            user=self.user,
            role=CompanyMembership.Role.OWNER,
        )

        self.unit = UnitOfMeasure.objects.create(
            company=self.company,
            name="Unidad",
            symbol="un",
            allows_decimal=False,
        )

        self.product = Product.objects.create(
            company=self.company,
            base_unit=self.unit,
            name="Producto A",
            sku="PROD-A",
            cost_price=Decimal("20.00"),
            sale_price=Decimal("100.00"),
            track_inventory=True,
        )

        self.product_b = Product.objects.create(
            company=self.company,
            base_unit=self.unit,
            name="Producto B",
            sku="PROD-B",
            cost_price=Decimal("10.00"),
            sale_price=Decimal("50.00"),
            track_inventory=True,
        )

        self.service = Product.objects.create(
            company=self.company,
            name="Servicio A",
            sku="SERV-A",
            product_type=Product.ProductType.SERVICE,
            cost_price=Decimal("0.00"),
            sale_price=Decimal("50.00"),
            track_inventory=False,
        )

        self.supplier = Supplier.objects.create(
            company=self.company,
            name="Proveedor A",
        )

        self.expense_category = (
            ExpenseCategory.objects.create(
                company=self.company,
                name="Servicios",
            )
        )

        self.today = timezone.localdate()
        now = timezone.now()

        self.sale = Sale.objects.create(
            company=self.company,
            branch=self.branch,
            sale_number="V-REPORT-001",
            status=SaleStatus.COMPLETED,
            subtotal=Decimal("200.00"),
            discount_total=Decimal("0.00"),
            tax_total=Decimal("0.00"),
            total=Decimal("200.00"),
            amount_received=Decimal("200.00"),
            change_amount=Decimal("0.00"),
            completed_at=now,
            created_by=self.user,
        )

        SaleItem.objects.create(
            sale=self.sale,
            product=self.product,
            product_name=self.product.name,
            product_sku=self.product.sku,
            quantity=Decimal("2.000"),
            unit_price=Decimal("100.00"),
            unit_cost=Decimal("60.00"),
            discount_percent=Decimal("0.00"),
            discount_amount=Decimal("0.00"),
            line_subtotal=Decimal("200.00"),
            line_total=Decimal("200.00"),
        )

        Sale.objects.create(
            company=self.company,
            branch=self.branch,
            sale_number="V-REPORT-CANCELLED",
            status=SaleStatus.CANCELLED,
            subtotal=Decimal("999.00"),
            total=Decimal("999.00"),
            amount_received=Decimal("999.00"),
            completed_at=now,
            cancelled_at=now,
            created_by=self.user,
        )

        Sale.objects.create(
            company=self.company,
            branch=self.branch_b,
            sale_number="V-REPORT-BRANCH-B",
            status=SaleStatus.COMPLETED,
            subtotal=Decimal("500.00"),
            total=Decimal("500.00"),
            amount_received=Decimal("500.00"),
            completed_at=now,
            created_by=self.user,
        )

        self.purchase = Purchase.objects.create(
            company=self.company,
            branch=self.branch,
            supplier=self.supplier,
            purchase_number="COMP-REPORT-001",
            purchase_date=self.today,
            payment_method=(
                PurchasePaymentMethod.TRANSFER
            ),
            status=PurchaseStatus.COMPLETED,
            subtotal=Decimal("50.00"),
            discount_total=Decimal("0.00"),
            tax_total=Decimal("0.00"),
            total=Decimal("50.00"),
            completed_at=now,
            created_by=self.user,
        )

        Purchase.objects.create(
            company=self.company,
            branch=self.branch,
            supplier=self.supplier,
            purchase_number="COMP-REPORT-DRAFT",
            purchase_date=self.today,
            payment_method=(
                PurchasePaymentMethod.TRANSFER
            ),
            status=PurchaseStatus.DRAFT,
            subtotal=Decimal("999.00"),
            total=Decimal("999.00"),
            created_by=self.user,
        )

        self.expense = Expense.objects.create(
            company=self.company,
            branch=self.branch,
            category=self.expense_category,
            supplier=self.supplier,
            description="Internet",
            amount=Decimal("30.00"),
            expense_date=self.today,
            payment_method=(
                ExpensePaymentMethod.TRANSFER
            ),
            status=ExpenseStatus.COMPLETED,
            created_by=self.user,
        )

        Expense.objects.create(
            company=self.company,
            branch=self.branch,
            category=self.expense_category,
            description="Gasto cancelado",
            amount=Decimal("999.00"),
            expense_date=self.today,
            payment_method=(
                ExpensePaymentMethod.TRANSFER
            ),
            status=ExpenseStatus.CANCELLED,
            created_by=self.user,
        )

        self.cash_register = CashRegister.objects.create(
            company=self.company,
            branch=self.branch,
            name="Caja principal",
            code="CAJA-01",
        )

        self.cash_session = CashSession.objects.create(
            company=self.company,
            branch=self.branch,
            cash_register=self.cash_register,
            opening_amount=Decimal("100.00"),
            status=CashSessionStatus.OPEN,
            opened_by=self.user,
        )

        CashMovement.objects.create(
            company=self.company,
            branch=self.branch,
            cash_session=self.cash_session,
            direction=CashMovementDirection.IN,
            movement_type=CashMovementType.MANUAL_IN,
            amount=Decimal("100.00"),
            source_type=CashMovementSource.MANUAL,
            reference="IN-001",
            created_by=self.user,
        )

        CashMovement.objects.create(
            company=self.company,
            branch=self.branch,
            cash_session=self.cash_session,
            direction=CashMovementDirection.OUT,
            movement_type=CashMovementType.MANUAL_OUT,
            amount=Decimal("30.00"),
            source_type=CashMovementSource.MANUAL,
            reference="OUT-001",
            created_by=self.user,
        )

        ProductStock.objects.create(
            company=self.company,
            branch=self.branch,
            product=self.product,
            quantity=Decimal("5.000"),
        )

        self.factory = APIRequestFactory()

    def report_params(
        self,
        **changes,
    ):
        data = {
            "company_id": str(self.company.id),
            "branch_id": str(self.branch.id),
            "date_from": self.today.isoformat(),
            "date_to": self.today.isoformat(),
        }

        data.update(changes)

        return data

    def execute_report(
        self,
        view_class,
        params,
    ):
        request = self.factory.get(
            "/reports/",
            params,
        )

        force_authenticate(
            request,
            user=self.user,
        )

        return view_class.as_view()(
            request
        )

    def test_date_from_cannot_be_after_date_to(self):
        serializer = ReportSummaryQuerySerializer(
            data={
                "company_id": str(
                    self.company.id
                ),
                "branch_id": str(
                    self.branch.id
                ),
                "date_from": (
                    self.today
                    + timezone.timedelta(days=1)
                ),
                "date_to": self.today,
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "date_to",
            serializer.errors,
        )

    def test_summary_report_aggregates_completed_records(self):
        response = self.execute_report(
            ReportSummaryView,
            self.report_params(),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["sales"]["count"],
            1,
        )

        self.assertEqual(
            response.data["sales"]["total"],
            "200.00",
        )

        self.assertEqual(
            response.data["purchases"]["count"],
            1,
        )

        self.assertEqual(
            response.data["purchases"]["total"],
            "50.00",
        )

        self.assertEqual(
            response.data["expenses"]["count"],
            1,
        )

        self.assertEqual(
            response.data["expenses"]["total"],
            "30.00",
        )

        self.assertEqual(
            response.data["cash"]["in"]["total"],
            "100.00",
        )

        self.assertEqual(
            response.data["cash"]["out"]["total"],
            "30.00",
        )

        self.assertEqual(
            response.data["cash"]["net"],
            "70.00",
        )

    def test_summary_report_returns_zero_for_empty_period(self):
        future_date = (
            self.today
            + timezone.timedelta(days=30)
        )

        response = self.execute_report(
            ReportSummaryView,
            self.report_params(
                date_from=future_date.isoformat(),
                date_to=future_date.isoformat(),
            ),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["sales"]["count"],
            0,
        )

        self.assertEqual(
            response.data["sales"]["total"],
            "0.00",
        )

        self.assertEqual(
            response.data["purchases"]["total"],
            "0.00",
        )

        self.assertEqual(
            response.data["expenses"]["total"],
            "0.00",
        )

        self.assertEqual(
            response.data["cash"]["net"],
            "0.00",
        )

    def test_daily_report_includes_days_without_activity(self):
        date_from = (
            self.today
            - timezone.timedelta(days=1)
        )

        date_to = (
            self.today
            + timezone.timedelta(days=1)
        )

        response = self.execute_report(
            ReportDailyView,
            self.report_params(
                date_from=date_from.isoformat(),
                date_to=date_to.isoformat(),
            ),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data["results"]),
            3,
        )

        today_result = next(
            result
            for result
            in response.data["results"]
            if result["date"] == self.today
        )

        self.assertEqual(
            today_result["sales"]["total"],
            "200.00",
        )

        self.assertEqual(
            today_result["purchases"]["total"],
            "50.00",
        )

        self.assertEqual(
            today_result["expenses"]["total"],
            "30.00",
        )

        empty_result = next(
            result
            for result
            in response.data["results"]
            if result["date"] == date_from
        )

        self.assertEqual(
            empty_result["sales"]["count"],
            0,
        )

        self.assertEqual(
            empty_result["cash"]["net"],
            "0.00",
        )

    def test_sales_report_calculates_summary(self):
        response = self.execute_report(
            SalesReportView,
            self.report_params(),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["summary"]["count"],
            1,
        )

        self.assertEqual(
            response.data["summary"]["total"],
            "200.00",
        )

        self.assertEqual(
            response.data["summary"][
                "average_ticket"
            ],
            "200.00",
        )

        self.assertEqual(
            response.data["count"],
            1,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

    def test_sales_report_respects_pagination(self):
        for index in range(2):
            Sale.objects.create(
                company=self.company,
                branch=self.branch,
                sale_number=(
                    f"V-PAGINATION-{index}"
                ),
                status=SaleStatus.COMPLETED,
                subtotal=Decimal("10.00"),
                total=Decimal("10.00"),
                amount_received=Decimal("10.00"),
                completed_at=timezone.now(),
                created_by=self.user,
            )

        response = self.execute_report(
            SalesReportView,
            self.report_params(
                page_size="1",
            ),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["count"],
            3,
        )

        self.assertEqual(
            len(response.data["results"]),
            1,
        )

    def test_purchases_report_calculates_summary(self):
        response = self.execute_report(
            PurchasesReportView,
            self.report_params(),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["summary"]["count"],
            1,
        )

        self.assertEqual(
            response.data["summary"]["total"],
            "50.00",
        )

        self.assertEqual(
            response.data["summary"][
                "average_purchase"
            ],
            "50.00",
        )

    def test_expenses_report_calculates_summary(self):
        response = self.execute_report(
            ExpensesReportView,
            self.report_params(),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["summary"]["count"],
            1,
        )

        self.assertEqual(
            response.data["summary"]["total"],
            "30.00",
        )

        self.assertEqual(
            response.data["summary"][
                "average_expense"
            ],
            "30.00",
        )

    def test_cash_report_calculates_net(self):
        response = self.execute_report(
            CashReportView,
            self.report_params(),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["summary"]["in"][
                "count"
            ],
            1,
        )

        self.assertEqual(
            response.data["summary"]["in"][
                "total"
            ],
            "100.00",
        )

        self.assertEqual(
            response.data["summary"]["out"][
                "total"
            ],
            "30.00",
        )

        self.assertEqual(
            response.data["summary"]["net"],
            "70.00",
        )

    def test_inventory_report_calculates_values(self):
        response = self.execute_report(
            InventoryReportView,
            {
                "company_id": str(
                    self.company.id
                ),
                "branch_id": str(
                    self.branch.id
                ),
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["summary"]["products"],
            1,
        )

        self.assertEqual(
            response.data["summary"][
                "total_units"
            ],
            "5.000",
        )

        self.assertEqual(
            response.data["summary"][
                "total_cost_value"
            ],
            "100.00",
        )

        self.assertEqual(
            response.data["summary"][
                "total_sale_value"
            ],
            "500.00",
        )

        self.assertEqual(
            response.data["results"][0][
                "cost_value"
            ],
            "100.00",
        )

        self.assertEqual(
            response.data["results"][0][
                "sale_value"
            ],
            "500.00",
        )

    def test_profitability_report_calculates_profit(self):
        response = self.execute_report(
            ProfitabilityReportView,
            self.report_params(),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        summary = response.data["summary"]

        self.assertEqual(
            summary["revenue"],
            "200.00",
        )

        self.assertEqual(
            summary["cost_of_sales"],
            "120.00",
        )

        self.assertEqual(
            summary["gross_profit"],
            "80.00",
        )

        self.assertEqual(
            summary["expenses"],
            "30.00",
        )

        self.assertEqual(
            summary["operating_result"],
            "50.00",
        )

        self.assertEqual(
            summary["gross_margin"],
            "40.00",
        )

        self.assertEqual(
            summary["missing_cost_items"],
            0,
        )

        self.assertTrue(
            summary["cost_coverage_complete"]
        )

    def test_profitability_report_handles_missing_cost(self):
        SaleItem.objects.create(
            sale=self.sale,
            product=self.product_b,
            product_name=self.product_b.name,
            product_sku=self.product_b.sku,
            quantity=Decimal("1.000"),
            unit_price=Decimal("50.00"),
            unit_cost=None,
            discount_percent=Decimal("0.00"),
            discount_amount=Decimal("0.00"),
            line_subtotal=Decimal("50.00"),
            line_total=Decimal("50.00"),
        )

        response = self.execute_report(
            ProfitabilityReportView,
            self.report_params(),
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        summary = response.data["summary"]

        self.assertEqual(
            summary["revenue"],
            "250.00",
        )

        self.assertEqual(
            summary["missing_cost_items"],
            1,
        )

        self.assertFalse(
            summary["cost_coverage_complete"]
        )

        self.assertIsNone(
            summary["cost_of_sales"]
        )

        self.assertIsNone(
            summary["gross_profit"]
        )

        self.assertIsNone(
            summary["operating_result"]
        )

        self.assertIsNone(
            summary["gross_margin"]
        )