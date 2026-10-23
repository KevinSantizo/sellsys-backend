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
    InventoryMovementType,
    ProductStock,
)

from purchases.models import (
    Purchase,
    PurchasePaymentMethod,
    PurchaseStatus,
    Supplier,
)

from purchases.views import PurchaseViewSet

from reports.views import ReportSummaryView


class PurchaseCashFlowE2ETest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

        User = get_user_model()

        self.user = User.objects.create_user(
            email="purchase-e2e@sellsys.test",
            password="Test12345!",
        )

        self.company = Company.objects.create(
            name="Empresa Purchase E2E",
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
            name="Sucursal Purchase E2E",
            code="PUR-E2E",
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
            name="Producto Compra E2E",
            sku="PUR-E2E-001",
            product_type=(
                Product.ProductType.PRODUCT
            ),
            base_unit=self.base_unit,
            cost_price=Decimal("15.00"),
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

        self.supplier = Supplier.objects.create(
            company=self.company,
            name="Proveedor E2E",
            is_active=True,
        )

        self.cash_register = (
            CashRegister.objects.create(
                company=self.company,
                branch=self.branch,
                name="Caja Compra E2E",
                code="PUR-CAJA",
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
                    "500.00"
                ),
                status=CashSessionStatus.OPEN,
                opened_by=self.user,
                notes="Sesión compras E2E",
            )
        )

    def test_cancel_cash_purchase_restores_inventory_and_cash(
            self,
    ):
        today = timezone.localdate()

        purchase_payload = {
            "company_id": str(
                self.company.id
            ),
            "branch_id": str(
                self.branch.id
            ),
            "supplier_id": str(
                self.supplier.id
            ),
            "supplier_invoice_number": (
                "FAC-E2E-CANCEL-001"
            ),
            "purchase_date": (
                today.isoformat()
            ),
            "payment_method": (
                PurchasePaymentMethod.CASH
            ),
            "discount_total": "0.00",
            "tax_total": "0.00",
            "notes": (
                "Compra E2E para cancelar"
            ),
            "items": [
                {
                    "product_id": str(
                        self.product.id
                    ),
                    "quantity": "3.000",
                    "unit_cost": "15.00",
                }
            ],
        }

        # Crear compra.
        create_request = (
            self.factory.post(
                "/api/purchases/",
                purchase_payload,
                format="json",
            )
        )

        force_authenticate(
            create_request,
            user=self.user,
        )

        create_view = (
            PurchaseViewSet.as_view(
                {
                    "post": "create",
                }
            )
        )

        create_response = create_view(
            create_request
        )

        self.assertEqual(
            create_response.status_code,
            201,
            create_response.data,
        )

        purchase = Purchase.objects.get(
            id=create_response.data["id"]
        )

        # Completar compra.
        complete_request = (
            self.factory.post(
                (
                    f"/api/purchases/"
                    f"{purchase.id}/complete/"
                ),
                {
                    "cash_session_id": str(
                        self.cash_session.id
                    ),
                },
                format="json",
            )
        )

        force_authenticate(
            complete_request,
            user=self.user,
        )

        complete_view = (
            PurchaseViewSet.as_view(
                {
                    "post": "complete",
                }
            )
        )

        complete_response = complete_view(
            complete_request,
            pk=purchase.id,
        )

        self.assertEqual(
            complete_response.status_code,
            200,
            complete_response.data,
        )

        purchase.refresh_from_db()
        self.stock.refresh_from_db()

        self.assertEqual(
            purchase.status,
            PurchaseStatus.COMPLETED,
        )

        self.assertEqual(
            self.stock.quantity,
            Decimal("13.000"),
        )

        original_cash_movement = (
            CashMovement.objects.get(
                source_type=(
                    CashMovementSource.PURCHASE
                ),
                source_id=purchase.id,
                movement_type=(
                    CashMovementType.PURCHASE
                ),
            )
        )

        self.assertEqual(
            original_cash_movement.direction,
            CashMovementDirection.OUT,
        )

        self.assertEqual(
            original_cash_movement.amount,
            Decimal("45.00"),
        )

        # Cancelar compra.
        cancel_request = (
            self.factory.post(
                (
                    f"/api/purchases/"
                    f"{purchase.id}/cancel/"
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
            PurchaseViewSet.as_view(
                {
                    "post": "cancel",
                }
            )
        )

        cancel_response = cancel_view(
            cancel_request,
            pk=purchase.id,
        )

        self.assertEqual(
            cancel_response.status_code,
            200,
            cancel_response.data,
        )

        purchase.refresh_from_db()
        self.stock.refresh_from_db()

        self.assertEqual(
            purchase.status,
            PurchaseStatus.CANCELLED,
        )

        self.assertIsNotNone(
            purchase.cancelled_at,
        )

        # Stock:
        # 10 inicial
        # + 3 compra
        # - 3 cancelación
        # = 10
        self.assertEqual(
            self.stock.quantity,
            Decimal("10.000"),
        )

        inventory_reversal = (
            InventoryMovement.objects.get(
                company=self.company,
                branch=self.branch,
                product=self.product,
                movement_type=(
                    InventoryMovementType
                    .PURCHASE_REVERSAL
                ),
                reference=(
                    purchase.purchase_number
                ),
            )
        )

        self.assertEqual(
            inventory_reversal.quantity,
            Decimal("3.000"),
        )

        self.assertEqual(
            inventory_reversal.previous_stock,
            Decimal("13.000"),
        )

        self.assertEqual(
            inventory_reversal.new_stock,
            Decimal("10.000"),
        )

        # La compra había generado una
        # salida de Q45.00.
        # La cancelación debe generar
        # una entrada de Q45.00.
        reversal_cash_movement = (
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
                amount=Decimal("45.00"),
            )
            .exclude(
                id=original_cash_movement.id,
            )
            .first()
        )

        self.assertIsNotNone(
            reversal_cash_movement,
        )

        # Validar reporte después
        # de la cancelación.
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

        # La compra cancelada ya no debe
        # contar como compra completada.
        self.assertEqual(
            report_response.data[
                "purchases"
            ]["count"],
            0,
        )

        self.assertEqual(
            report_response.data[
                "purchases"
            ]["total"],
            "0.00",
        )

        # Caja conserva ambos movimientos:
        # OUT 45 compra
        # IN 45 reversión.
        self.assertEqual(
            report_response.data[
                "cash"
            ]["out"]["total"],
            "45.00",
        )

        self.assertEqual(
            report_response.data[
                "cash"
            ]["in"]["total"],
            "45.00",
        )

        self.assertEqual(
            report_response.data[
                "cash"
            ]["net"],
            "0.00",
        )

    def test_cash_purchase_updates_inventory_cash_and_report(
        self,
    ):
        today = timezone.localdate()

        purchase_payload = {
            "company_id": str(
                self.company.id
            ),
            "branch_id": str(
                self.branch.id
            ),
            "supplier_id": str(
                self.supplier.id
            ),
            "supplier_invoice_number": (
                "FAC-E2E-001"
            ),
            "purchase_date": (
                today.isoformat()
            ),
            "payment_method": (
                PurchasePaymentMethod.CASH
            ),
            "discount_total": "0.00",
            "tax_total": "0.00",
            "notes": (
                "Compra E2E en efectivo"
            ),
            "items": [
                {
                    "product_id": str(
                        self.product.id
                    ),
                    "quantity": "3.000",
                    "unit_cost": "15.00",
                }
            ],
        }

        create_request = (
            self.factory.post(
                "/api/purchases/",
                purchase_payload,
                format="json",
            )
        )

        force_authenticate(
            create_request,
            user=self.user,
        )

        create_view = (
            PurchaseViewSet.as_view(
                {
                    "post": "create",
                }
            )
        )

        create_response = create_view(
            create_request
        )

        self.assertEqual(
            create_response.status_code,
            201,
            create_response.data,
        )

        purchase = Purchase.objects.get(
            id=create_response.data[
                "id"
            ],
        )

        self.assertEqual(
            purchase.status,
            PurchaseStatus.DRAFT,
        )

        self.assertEqual(
            purchase.subtotal,
            Decimal("45.00"),
        )

        self.assertEqual(
            purchase.total,
            Decimal("45.00"),
        )

        self.assertTrue(
            purchase.purchase_number.startswith(
                "COMP-"
            )
        )

        # Crear la compra todavía no
        # debe modificar inventario.
        self.stock.refresh_from_db()

        self.assertEqual(
            self.stock.quantity,
            Decimal("10.000"),
        )

        complete_request = (
            self.factory.post(
                (
                    f"/api/purchases/"
                    f"{purchase.id}/complete/"
                ),
                {
                    "cash_session_id": str(
                        self.cash_session.id
                    ),
                },
                format="json",
            )
        )

        force_authenticate(
            complete_request,
            user=self.user,
        )

        complete_view = (
            PurchaseViewSet.as_view(
                {
                    "post": "complete",
                }
            )
        )

        complete_response = (
            complete_view(
                complete_request,
                pk=purchase.id,
            )
        )

        self.assertEqual(
            complete_response.status_code,
            200,
            complete_response.data,
        )

        purchase.refresh_from_db()

        self.assertEqual(
            purchase.status,
            PurchaseStatus.COMPLETED,
        )

        self.assertIsNotNone(
            purchase.completed_at,
        )

        # Stock:
        # 10 iniciales + 3 compradas = 13.
        self.stock.refresh_from_db()

        self.assertEqual(
            self.stock.quantity,
            Decimal("13.000"),
        )

        inventory_movement = (
            InventoryMovement.objects.get(
                company=self.company,
                branch=self.branch,
                product=self.product,
                movement_type=(
                    InventoryMovementType.PURCHASE
                ),
                reference=(
                    purchase.purchase_number
                ),
            )
        )

        self.assertEqual(
            inventory_movement.quantity,
            Decimal("3.000"),
        )

        self.assertEqual(
            inventory_movement.previous_stock,
            Decimal("10.000"),
        )

        self.assertEqual(
            inventory_movement.new_stock,
            Decimal("13.000"),
        )

        cash_movement = (
            CashMovement.objects.get(
                source_type=(
                    CashMovementSource.PURCHASE
                ),
                source_id=purchase.id,
                movement_type=(
                    CashMovementType.PURCHASE
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
            Decimal("45.00"),
        )

        # La compra también debe
        # reflejarse en los reportes.
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
                "purchases"
            ]["count"],
            1,
        )

        self.assertEqual(
            report_response.data[
                "purchases"
            ]["total"],
            "45.00",
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
            "45.00",
        )

        self.assertEqual(
            report_response.data[
                "cash"
            ]["net"],
            "-45.00",
        )