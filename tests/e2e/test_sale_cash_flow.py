import uuid
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

from catalog.models import (
    Product,
    UnitOfMeasure,
)
from companies.models import (
    Company,
    CompanyMembership,
)

from inventory.models import (
    InventoryMovement,
    ProductStock,
)

from reports.views import ReportSummaryView

from sales.models import (
    Payment,
    PaymentMethod,
    Sale,
    SaleItem,
    SaleStatus,
)

from sales.views import SaleViewSet


class SaleCashFlowE2ETest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

        User = get_user_model()

        self.user = User.objects.create_user(
            email="e2e@sellsys.tests",
            password="Test12345!",
        )

        self.company = Company.objects.create(
            name="Empresa E2E",
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
            name="Sucursal E2E",
            code="E2E",
            is_main=True,
            is_active=True,
        )

        self.base_unit = (
            UnitOfMeasure.objects.create(
                company=self.company,
                name="Unidad",
                symbol="und",
                unit_type=(
                    UnitOfMeasure
                    ._meta
                    .get_field("unit_type")
                    .choices[0][0]
                ),
                allows_decimal=True,
                is_active=True,
            )
        )

        self.product = Product.objects.create(
            company=self.company,
            name="Producto E2E",
            sku="E2E-001",
            product_type=Product.ProductType.PRODUCT,
            base_unit=self.base_unit,
            cost_price=Decimal("10.00"),
            sale_price=Decimal("25.00"),
            track_inventory=True,
            is_active=True,
        )

        self.stock = ProductStock.objects.create(
            company=self.company,
            branch=self.branch,
            product=self.product,
            quantity=Decimal("10.000"),
        )

        self.cash_register = (
            CashRegister.objects.create(
                company=self.company,
                branch=self.branch,
                name="Caja E2E",
                code="CAJA-E2E",
                is_active=True,
            )
        )

        self.cash_session = (
            CashSession.objects.create(
                company=self.company,
                branch=self.branch,
                cash_register=(
                    self.cash_register
                ),
                opening_amount=Decimal(
                    "100.00"
                ),
                status=CashSessionStatus.OPEN,
                opened_by=self.user,
                notes="Sesión E2E",
            )
        )

    def test_cash_sale_updates_inventory_cash_and_report(
        self,
    ):
        checkout_payload = {
            "company_id": str(
                self.company.id
            ),
            "branch_id": str(
                self.branch.id
            ),
            "cash_session_id": str(
                self.cash_session.id
            ),
            "customer_name": (
                "Cliente E2E"
            ),
            "customer_tax_id": "CF",
            "notes": (
                "Venta E2E"
            ),
            "cart_discount_type": (
                "NONE"
            ),
            "cart_discount_value": (
                "0.00"
            ),
            "items": [
                {
                    "product_id": str(
                        self.product.id
                    ),
                    "quantity": "2.000",
                    "discount_percent": (
                        "0.00"
                    ),
                }
            ],
            "payments": [
                {
                    "method": (
                        PaymentMethod.CASH
                    ),
                    "amount": "60.00",
                    "reference": "",
                }
            ],
        }

        checkout_request = (
            self.factory.post(
                "/api/sales/checkout/",
                checkout_payload,
                format="json",
                HTTP_IDEMPOTENCY_KEY=str(
                    uuid.uuid4()
                ),
            )
        )

        force_authenticate(
            checkout_request,
            user=self.user,
        )

        checkout_view = (
            SaleViewSet.as_view(
                {
                    "post": "checkout",
                }
            )
        )

        checkout_response = (
            checkout_view(
                checkout_request
            )
        )

        self.assertEqual(
            checkout_response.status_code,
            201,
            checkout_response.data,
        )

        sale = Sale.objects.get(
            id=checkout_response.data[
                "id"
            ],
        )

        self.assertEqual(
            sale.status,
            SaleStatus.COMPLETED,
        )

        self.assertEqual(
            sale.subtotal,
            Decimal("50.00"),
        )

        self.assertEqual(
            sale.total,
            Decimal("50.00"),
        )

        self.assertEqual(
            sale.amount_received,
            Decimal("60.00"),
        )

        self.assertEqual(
            sale.change_amount,
            Decimal("10.00"),
        )

        self.assertEqual(
            SaleItem.objects.filter(
                sale=sale,
            ).count(),
            1,
        )

        sale_item = (
            SaleItem.objects.get(
                sale=sale,
            )
        )

        self.assertEqual(
            sale_item.product_id,
            self.product.id,
        )

        self.assertEqual(
            sale_item.quantity,
            Decimal("2.000"),
        )

        self.assertEqual(
            sale_item.unit_price,
            Decimal("25.00"),
        )

        self.assertEqual(
            sale_item.line_total,
            Decimal("50.00"),
        )

        self.assertEqual(
            Payment.objects.filter(
                sale=sale,
            ).count(),
            1,
        )

        payment = (
            Payment.objects.get(
                sale=sale,
            )
        )

        self.assertEqual(
            payment.method,
            PaymentMethod.CASH,
        )

        self.assertEqual(
            payment.amount,
            Decimal("60.00"),
        )

        self.stock.refresh_from_db()

        self.assertEqual(
            self.stock.quantity,
            Decimal("8.000"),
        )

        inventory_movement = (
            InventoryMovement.objects.get(
                sale=sale,
                product=self.product,
            )
        )

        self.assertEqual(
            inventory_movement.quantity,
            Decimal("2.000"),
        )

        self.assertEqual(
            inventory_movement.previous_stock,
            Decimal("10.000"),
        )

        self.assertEqual(
            inventory_movement.new_stock,
            Decimal("8.000"),
        )

        cash_movement = (
            CashMovement.objects.get(
                source_type=(
                    CashMovementSource.SALE
                ),
                source_id=sale.id,
                movement_type=(
                    CashMovementType.SALE
                ),
            )
        )

        self.assertEqual(
            cash_movement.cash_session_id,
            self.cash_session.id,
        )

        self.assertEqual(
            cash_movement.direction,
            CashMovementDirection.IN,
        )

        # La venta fue Q50.00.
        # Se recibieron Q60.00 pero hubo
        # Q10.00 de cambio, por lo que
        # caja solamente recibe Q50.00.
        self.assertEqual(
            cash_movement.amount,
            Decimal("50.00"),
        )

        today = timezone.localdate()

        report_request = (
            self.factory.get(
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
        )

        force_authenticate(
            report_request,
            user=self.user,
        )

        report_response = (
            ReportSummaryView.as_view()(
                report_request
            )
        )

        self.assertEqual(
            report_response.status_code,
            200,
            report_response.data,
        )

        self.assertEqual(
            report_response.data[
                "sales"
            ]["count"],
            1,
        )

        self.assertEqual(
            report_response.data[
                "sales"
            ]["total"],
            "50.00",
        )

        self.assertEqual(
            report_response.data[
                "cash"
            ]["in"]["count"],
            1,
        )

        self.assertEqual(
            report_response.data[
                "cash"
            ]["in"]["total"],
            "50.00",
        )

        self.assertEqual(
            report_response.data[
                "cash"
            ]["out"]["count"],
            0,
        )

        self.assertEqual(
            report_response.data[
                "cash"
            ]["out"]["total"],
            "0.00",
        )

        self.assertEqual(
            report_response.data[
                "cash"
            ]["net"],
            "50.00",
        )

    def test_cancel_cash_sale_restores_stock_and_reverses_cash(
            self,
    ):
        checkout_payload = {
            "company_id": str(
                self.company.id
            ),
            "branch_id": str(
                self.branch.id
            ),
            "cash_session_id": str(
                self.cash_session.id
            ),
            "customer_name": "Cliente E2E",
            "customer_tax_id": "CF",
            "notes": "Venta E2E a cancelar",
            "cart_discount_type": "NONE",
            "cart_discount_value": "0.00",
            "items": [
                {
                    "product_id": str(
                        self.product.id
                    ),
                    "quantity": "2.000",
                    "discount_percent": "0.00",
                }
            ],
            "payments": [
                {
                    "method": PaymentMethod.CASH,
                    "amount": "60.00",
                    "reference": "",
                }
            ],
        }

        checkout_request = (
            self.factory.post(
                "/api/sales/checkout/",
                checkout_payload,
                format="json",
                HTTP_IDEMPOTENCY_KEY=str(
                    uuid.uuid4()
                ),
            )
        )

        force_authenticate(
            checkout_request,
            user=self.user,
        )

        checkout_view = (
            SaleViewSet.as_view(
                {
                    "post": "checkout",
                }
            )
        )

        checkout_response = (
            checkout_view(
                checkout_request
            )
        )

        self.assertEqual(
            checkout_response.status_code,
            201,
            checkout_response.data,
        )

        sale = Sale.objects.get(
            id=checkout_response.data[
                "id"
            ],
        )

        self.stock.refresh_from_db()

        self.assertEqual(
            self.stock.quantity,
            Decimal("8.000"),
        )

        original_cash_movement = (
            CashMovement.objects.get(
                source_type=(
                    CashMovementSource.SALE
                ),
                source_id=sale.id,
                movement_type=(
                    CashMovementType.SALE
                ),
            )
        )

        self.assertEqual(
            original_cash_movement.direction,
            CashMovementDirection.IN,
        )

        self.assertEqual(
            original_cash_movement.amount,
            Decimal("50.00"),
        )

        cancel_request = (
            self.factory.post(
                (
                    f"/api/sales/"
                    f"{sale.id}/cancel/"
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
            SaleViewSet.as_view(
                {
                    "post": "cancel",
                }
            )
        )

        cancel_response = cancel_view(
            cancel_request,
            pk=sale.id,
        )

        self.assertEqual(
            cancel_response.status_code,
            200,
            cancel_response.data,
        )

        sale.refresh_from_db()

        self.assertEqual(
            sale.status,
            SaleStatus.CANCELLED,
        )

        self.assertIsNotNone(
            sale.cancelled_at,
        )

        # El stock debe volver de 8 a 10.
        self.stock.refresh_from_db()

        self.assertEqual(
            self.stock.quantity,
            Decimal("10.000"),
        )

        # Debe existir un movimiento que
        # restaure las dos unidades.
        stock_reversal = (
            InventoryMovement.objects.filter(
                company=self.company,
                branch=self.branch,
                product=self.product,
                quantity=Decimal("2.000"),
                previous_stock=Decimal(
                    "8.000"
                ),
                new_stock=Decimal(
                    "10.000"
                ),
            )
            .exclude(
                id__in=(
                    InventoryMovement.objects
                    .filter(
                        sale=sale,
                        new_stock=Decimal(
                            "8.000"
                        ),
                    )
                    .values_list(
                        "id",
                        flat=True,
                    )
                )
            )
            .first()
        )

        self.assertIsNotNone(
            stock_reversal,
        )

        # La cancelación debe generar una
        # salida de caja por los Q50.00 que
        # realmente habían entrado.
        reversal_cash_movement = (
            CashMovement.objects
            .filter(
                company=self.company,
                branch=self.branch,
                cash_session=(
                    self.cash_session
                ),
                direction=(
                    CashMovementDirection.OUT
                ),
                amount=Decimal("50.00"),
            )
            .exclude(
                id=original_cash_movement.id,
            )
            .first()
        )

        self.assertIsNotNone(
            reversal_cash_movement,
        )

        today = timezone.localdate()

        report_request = (
            self.factory.get(
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
        )

        force_authenticate(
            report_request,
            user=self.user,
        )

        report_response = (
            ReportSummaryView.as_view()(
                report_request
            )
        )

        self.assertEqual(
            report_response.status_code,
            200,
            report_response.data,
        )

        # Una venta cancelada ya no cuenta
        # como venta completada.
        self.assertEqual(
            report_response.data[
                "sales"
            ]["count"],
            0,
        )

        self.assertEqual(
            report_response.data[
                "sales"
            ]["total"],
            "0.00",
        )

        # Caja conserva el movimiento
        # original y registra su reversión.
        self.assertEqual(
            report_response.data[
                "cash"
            ]["in"]["total"],
            "50.00",
        )

        self.assertEqual(
            report_response.data[
                "cash"
            ]["out"]["total"],
            "50.00",
        )

        self.assertEqual(
            report_response.data[
                "cash"
            ]["net"],
            "0.00",
        )