from django.test import TestCase

# Create your tests here.
from decimal import Decimal
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from rest_framework import serializers, status
from rest_framework.test import APIRequestFactory, force_authenticate

from branches.models import Branch
from catalog.models import Product, UnitOfMeasure
from companies.models import Company, CompanyMembership
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
from purchases.serializers import (
    PurchaseSerializer,
    SupplierSerializer,
)
from purchases.views import PurchaseViewSet


User = get_user_model()


class PurchaseTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@sellsys.tests",
            password="SellSys123!",
        )

        self.company = Company.objects.create(
            name="Empresa A",
        )

        self.other_company = Company.objects.create(
            name="Empresa B",
        )

        self.branch = Branch.objects.create(
            company=self.company,
            name="Sucursal A",
            code="A",
        )

        self.other_branch = Branch.objects.create(
            company=self.other_company,
            name="Sucursal B",
            code="B",
        )

        CompanyMembership.objects.create(
            company=self.company,
            user=self.user,
            role=CompanyMembership.Role.OWNER,
        )

        self.supplier = Supplier.objects.create(
            company=self.company,
            name="Proveedor A",
        )

        self.other_supplier = Supplier.objects.create(
            company=self.other_company,
            name="Proveedor B",
        )

        self.unit = UnitOfMeasure.objects.create(
            company=self.company,
            name="Unidad",
            symbol="un",
            allows_decimal=False,
        )

        self.other_unit = UnitOfMeasure.objects.create(
            company=self.other_company,
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
            sale_price=Decimal("30.00"),
            track_inventory=True,
        )

        self.other_product = Product.objects.create(
            company=self.other_company,
            base_unit=self.other_unit,
            name="Producto B",
            sku="PROD-B",
            cost_price=Decimal("20.00"),
            sale_price=Decimal("30.00"),
            track_inventory=True,
        )

        self.service = Product.objects.create(
            company=self.company,
            name="Servicio A",
            sku="SERV-A",
            product_type=Product.ProductType.SERVICE,
            cost_price=Decimal("10.00"),
            sale_price=Decimal("20.00"),
            track_inventory=False,
        )

        self.factory = APIRequestFactory()

    def purchase_data(
        self,
        quantity="2.000",
        unit_cost="25.00",
        sale_price="30.00",
        product=None,
        supplier=None,
        branch=None,
        **changes,
    ):
        product = product or self.product
        supplier = supplier or self.supplier
        branch = branch or self.branch

        data = {
            "company_id": str(self.company.id),
            "branch_id": str(branch.id),
            "supplier_id": str(supplier.id),
            "payment_method": PurchasePaymentMethod.TRANSFER,
            "supplier_invoice_number": "FAC-001",
            "discount_total": "0.00",
            "tax_total": "0.00",
            "notes": "",
            "items": [
                {
                    "product_id": str(product.id),
                    "quantity": quantity,
                    "unit_cost": unit_cost,
                    "sale_price": sale_price,
                },
            ],
        }

        data.update(changes)

        return data

    def create_purchase(
        self,
        purchase_number="COMP-000001",
        **changes,
    ):
        serializer = PurchaseSerializer(
            data=self.purchase_data(**changes)
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        return serializer.save(
            purchase_number=purchase_number,
            created_by=self.user,
        )

    def execute_action(
        self,
        action,
        purchase,
        data=None,
    ):
        request = self.factory.post(
            f"/purchases/{purchase.id}/{action}/",
            data or {},
            format="json",
        )

        force_authenticate(
            request,
            user=self.user,
        )

        view = PurchaseViewSet.as_view({
            "post": action,
        })

        return view(
            request,
            pk=purchase.id,
        )

    def test_supplier_name_is_trimmed(self):
        serializer = SupplierSerializer(
            data={
                "company_id": str(self.company.id),
                "name": "  Proveedor Nuevo  ",
            }
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        self.assertEqual(
            serializer.validated_data["name"],
            "Proveedor Nuevo",
        )

    def test_blank_supplier_name_is_rejected(self):
        serializer = SupplierSerializer(
            data={
                "company_id": str(self.company.id),
                "name": "   ",
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "name",
            serializer.errors,
        )

    def test_branch_must_belong_to_company(self):
        serializer = PurchaseSerializer(
            data=self.purchase_data(
                branch=self.other_branch,
            )
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "branch_id",
            serializer.errors,
        )

    def test_supplier_must_belong_to_company(self):
        serializer = PurchaseSerializer(
            data=self.purchase_data(
                supplier=self.other_supplier,
            )
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "supplier_id",
            serializer.errors,
        )

    def test_purchase_requires_items(self):
        data = self.purchase_data()
        data["items"] = []

        serializer = PurchaseSerializer(
            data=data
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "items",
            serializer.errors,
        )

    def test_product_must_belong_to_company(self):
        serializer = PurchaseSerializer(
            data=self.purchase_data(
                product=self.other_product,
            )
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "items",
            serializer.errors,
        )

    def test_service_cannot_be_purchased(self):
        serializer = PurchaseSerializer(
            data=self.purchase_data(
                product=self.service,
            )
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "items",
            serializer.errors,
        )

    def test_duplicate_product_is_rejected(self):
        data = self.purchase_data()

        data["items"].append({
            "product_id": str(self.product.id),
            "quantity": "1.000",
            "unit_cost": "20.00",
            "sale_price": "30.00",
        })

        serializer = PurchaseSerializer(
            data=data
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "items",
            serializer.errors,
        )

    def test_discount_cannot_exceed_subtotal(self):
        serializer = PurchaseSerializer(
            data=self.purchase_data(
                quantity="2.000",
                unit_cost="25.00",
                discount_total="51.00",
            )
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "discount_total",
            serializer.errors,
        )

    def test_serializer_calculates_totals_and_creates_items(self):
        serializer = PurchaseSerializer(
            data=self.purchase_data(
                quantity="2.000",
                unit_cost="25.00",
                discount_total="5.00",
                tax_total="3.00",
            )
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        purchase = serializer.save(
            purchase_number="COMP-000001",
            created_by=self.user,
        )

        self.assertEqual(
            purchase.subtotal,
            Decimal("50.00"),
        )

        self.assertEqual(
            purchase.discount_total,
            Decimal("5.00"),
        )

        self.assertEqual(
            purchase.tax_total,
            Decimal("3.00"),
        )

        self.assertEqual(
            purchase.total,
            Decimal("48.00"),
        )

        self.assertEqual(
            purchase.items.count(),
            1,
        )

    def test_purchase_number_increments_per_company(self):
        self.create_purchase(
            purchase_number="COMP-000001",
        )

        self.create_purchase(
            purchase_number="COMP-000003",
        )

        view = PurchaseViewSet()

        purchase_number = view._generate_purchase_number(
            self.company
        )

        self.assertEqual(
            purchase_number,
            "COMP-000004",
        )

    def test_completed_purchase_cannot_be_updated(self):
        purchase = self.create_purchase()

        purchase.status = PurchaseStatus.COMPLETED
        purchase.save(update_fields=[ "status" ])

        view = PurchaseViewSet()

        view.get_object = Mock(
            return_value=purchase
        )

        serializer = Mock()

        with self.assertRaises(
            serializers.ValidationError
        ):
            view.perform_update(serializer)

        serializer.save.assert_not_called()

    def test_complete_purchase_adds_stock_and_movement(self):
        ProductStock.objects.create(
            company=self.company,
            branch=self.branch,
            product=self.product,
            quantity=Decimal("5.000"),
        )

        purchase = self.create_purchase(
            quantity="2.000",
            unit_cost="25.00",
        )

        response = self.execute_action(
            "complete",
            purchase,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        purchase.refresh_from_db()

        stock = ProductStock.objects.get(
            company=self.company,
            branch=self.branch,
            product=self.product,
        )

        self.assertEqual(
            purchase.status,
            PurchaseStatus.COMPLETED,
        )

        self.assertEqual(
            stock.quantity,
            Decimal("7.000"),
        )

        movement = InventoryMovement.objects.get(
            company=self.company,
            branch=self.branch,
            product=self.product,
            movement_type=InventoryMovementType.PURCHASE,
        )

        self.assertEqual(
            movement.quantity,
            Decimal("2.000"),
        )

        self.assertEqual(
            movement.previous_stock,
            Decimal("5.000"),
        )

        self.assertEqual(
            movement.new_stock,
            Decimal("7.000"),
        )

    def test_complete_purchase_creates_stock_when_missing(self):
        purchase = self.create_purchase(
            quantity="3.000",
        )

        self.assertFalse(
            ProductStock.objects.filter(
                company=self.company,
                branch=self.branch,
                product=self.product,
            ).exists()
        )

        response = self.execute_action(
            "complete",
            purchase,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        stock = ProductStock.objects.get(
            company=self.company,
            branch=self.branch,
            product=self.product,
        )

        self.assertEqual(
            stock.quantity,
            Decimal("3.000"),
        )

    def test_non_draft_purchase_cannot_be_completed(self):
        purchase = self.create_purchase()

        purchase.status = PurchaseStatus.CANCELLED
        purchase.save(update_fields=[ "status" ])

        response = self.execute_action(
            "complete",
            purchase,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertFalse(
            InventoryMovement.objects.filter(
                reference=purchase.purchase_number,
            ).exists()
        )

    def test_cancel_draft_does_not_touch_inventory(self):
        purchase = self.create_purchase()

        response = self.execute_action(
            "cancel",
            purchase,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        purchase.refresh_from_db()

        self.assertEqual(
            purchase.status,
            PurchaseStatus.CANCELLED,
        )

        self.assertFalse(
            ProductStock.objects.filter(
                company=self.company,
                branch=self.branch,
                product=self.product,
            ).exists()
        )

        self.assertFalse(
            InventoryMovement.objects.filter(
                reference=purchase.purchase_number,
            ).exists()
        )

    def test_cancel_completed_purchase_reverts_stock(self):
        purchase = self.create_purchase(
            quantity="2.000",
        )

        complete_response = self.execute_action(
            "complete",
            purchase,
        )

        self.assertEqual(
            complete_response.status_code,
            status.HTTP_200_OK,
        )

        stock = ProductStock.objects.get(
            company=self.company,
            branch=self.branch,
            product=self.product,
        )

        self.assertEqual(
            stock.quantity,
            Decimal("2.000"),
        )

        cancel_response = self.execute_action(
            "cancel",
            purchase,
        )

        self.assertEqual(
            cancel_response.status_code,
            status.HTTP_200_OK,
        )

        purchase.refresh_from_db()
        stock.refresh_from_db()

        self.assertEqual(
            purchase.status,
            PurchaseStatus.CANCELLED,
        )

        self.assertEqual(
            stock.quantity,
            Decimal("0.000"),
        )

        reversal = InventoryMovement.objects.get(
            company=self.company,
            branch=self.branch,
            product=self.product,
            movement_type=(
                InventoryMovementType.PURCHASE_REVERSAL
            ),
        )

        self.assertEqual(
            reversal.quantity,
            Decimal("2.000"),
        )

        self.assertEqual(
            reversal.previous_stock,
            Decimal("2.000"),
        )

        self.assertEqual(
            reversal.new_stock,
            Decimal("0.000"),
        )

    def test_cancel_completed_purchase_fails_if_stock_was_consumed(self):
        purchase = self.create_purchase(
            quantity="2.000",
        )

        complete_response = self.execute_action(
            "complete",
            purchase,
        )

        self.assertEqual(
            complete_response.status_code,
            status.HTTP_200_OK,
        )

        stock = ProductStock.objects.get(
            company=self.company,
            branch=self.branch,
            product=self.product,
        )

        stock.quantity = Decimal("1.000")

        stock.save(
            update_fields=[ "quantity" ]
        )

        cancel_response = self.execute_action(
            "cancel",
            purchase,
        )

        self.assertEqual(
            cancel_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        purchase.refresh_from_db()
        stock.refresh_from_db()

        self.assertEqual(
            purchase.status,
            PurchaseStatus.COMPLETED,
        )

        self.assertEqual(
            stock.quantity,
            Decimal("1.000"),
        )

        self.assertFalse(
            InventoryMovement.objects.filter(
                reference=purchase.purchase_number,
                movement_type=(
                    InventoryMovementType.PURCHASE_REVERSAL
                ),
            ).exists()
        )