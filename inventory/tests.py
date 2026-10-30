from decimal import Decimal
from datetime import date
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TransactionTestCase

from branches.models import Branch
from catalog.models import Product, UnitOfMeasure
from companies.models import Company
from inventory.models import (
    InventoryLot,
    InventoryLotSaleAllocation,
    ProductStock,
)
from inventory.services import (
    InventoryStockError,
    deduct_sale_stock,
    lock_and_validate_sale_stock,
    restore_sale_stock,
)

from sales.models import (
    Sale,
    SaleItem,
    SaleStatus,
)

class InventoryTests(TransactionTestCase):

    def setUp(self):
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
            cost_price=Decimal("5.00"),
            sale_price=Decimal("10.00"),
            track_inventory=True,
        )

        self.other_product = Product.objects.create(
            company=self.other_company,
            base_unit=self.other_unit,
            name="Producto B",
            sku="PROD-B",
            cost_price=Decimal("5.00"),
            sale_price=Decimal("10.00"),
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

        self.stock = ProductStock.objects.create(
            company=self.company,
            branch=self.branch,
            product=self.product,
            quantity=Decimal("10.000"),
        )

    def test_stock_branch_must_belong_to_company(self):
        stock = ProductStock(
            company=self.company,
            branch=self.other_branch,
            product=self.product,
            quantity=Decimal("1.000"),
        )

        with self.assertRaises(ValidationError) as context:
            stock.full_clean()

        self.assertIn(
            "branch",
            context.exception.message_dict,
        )

    def test_stock_product_must_belong_to_company(self):
        stock = ProductStock(
            company=self.company,
            branch=self.branch,
            product=self.other_product,
            quantity=Decimal("1.000"),
        )

        with self.assertRaises(ValidationError) as context:
            stock.full_clean()

        self.assertIn(
            "product",
            context.exception.message_dict,
        )

    def test_stock_cannot_be_negative(self):
        self.stock.quantity = Decimal("-1.000")

        with self.assertRaises(ValidationError):
            self.stock.full_clean()

    def test_stock_validation_requires_transaction(self):
        items = [
            {
                "product": self.product,
                "quantity": Decimal("1.000"),
            },
        ]

        with self.assertRaises(RuntimeError):
            lock_and_validate_sale_stock(
                company=self.company,
                branch=self.branch,
                calculated_items=items,
            )

    def test_branch_must_belong_to_company(self):
        items = [
            {
                "product": self.product,
                "quantity": Decimal("1.000"),
            },
        ]

        with transaction.atomic():
            with self.assertRaises(InventoryStockError):
                lock_and_validate_sale_stock(
                    company=self.company,
                    branch=self.other_branch,
                    calculated_items=items,
                )

    def test_product_without_inventory_tracking_is_ignored(self):
        items = [
            {
                "product": self.service,
                "quantity": Decimal("1.000"),
            },
        ]

        with transaction.atomic():
            stocks = lock_and_validate_sale_stock(
                company=self.company,
                branch=self.branch,
                calculated_items=items,
            )

        self.assertEqual(
            stocks,
            {},
        )

    def test_product_must_belong_to_company(self):
        items = [
            {
                "product": self.other_product,
                "quantity": Decimal("1.000"),
            },
        ]

        with transaction.atomic():
            with self.assertRaises(InventoryStockError):
                lock_and_validate_sale_stock(
                    company=self.company,
                    branch=self.branch,
                    calculated_items=items,
                )

    def test_requested_quantity_must_be_greater_than_zero(self):
        items = [
            {
                "product": self.product,
                "quantity": Decimal("0.000"),
            },
        ]

        with transaction.atomic():
            with self.assertRaises(InventoryStockError):
                lock_and_validate_sale_stock(
                    company=self.company,
                    branch=self.branch,
                    calculated_items=items,
                )

    def test_product_without_stock_record_is_rejected(self):
        self.stock.delete()

        items = [
            {
                "product": self.product,
                "quantity": Decimal("1.000"),
            },
        ]

        with transaction.atomic():
            with self.assertRaises(InventoryStockError) as context:
                lock_and_validate_sale_stock(
                    company=self.company,
                    branch=self.branch,
                    calculated_items=items,
                )

        self.assertIn(
            "no tiene stock registrado",
            str(context.exception),
        )

    def test_insufficient_stock_is_rejected(self):
        items = [
            {
                "product": self.product,
                "quantity": Decimal("11.000"),
            },
        ]

        with transaction.atomic():
            with self.assertRaises(InventoryStockError) as context:
                lock_and_validate_sale_stock(
                    company=self.company,
                    branch=self.branch,
                    calculated_items=items,
                )

        self.assertIn(
            "Stock insuficiente",
            str(context.exception),
        )

    def test_quantities_for_same_product_are_accumulated(self):
        self.stock.quantity = Decimal("5.000")
        self.stock.save(update_fields=[ "quantity" ])

        items = [
            {
                "product": self.product,
                "quantity": Decimal("3.000"),
            },
            {
                "product": self.product,
                "quantity": Decimal("3.000"),
            },
        ]

        with transaction.atomic():
            with self.assertRaises(InventoryStockError) as context:
                lock_and_validate_sale_stock(
                    company=self.company,
                    branch=self.branch,
                    calculated_items=items,
                )

        self.assertIn(
            "Solicitado: 6.000",
            str(context.exception),
        )

    def test_available_stock_is_returned(self):
        items = [
            {
                "product": self.product,
                "quantity": Decimal("10.000"),
            },
        ]

        with transaction.atomic():
            stocks = lock_and_validate_sale_stock(
                company=self.company,
                branch=self.branch,
                calculated_items=items,
            )

        self.assertIn(
            self.product.id,
            stocks,
        )

        self.assertEqual(
            stocks[self.product.id].id,
            self.stock.id,
        )

class InventoryFefoTests(TransactionTestCase):

    def setUp(self):
        self.company = Company.objects.create(
            name="Empresa FEFO",
        )

        self.branch = Branch.objects.create(
            company=self.company,
            name="Sucursal FEFO",
            code="FEO",
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
            name="Producto FEFO",
            sku="FEFO-001",
            cost_price=Decimal("5.00"),
            sale_price=Decimal("10.00"),
            track_inventory=True,
        )

        self.stock = ProductStock.objects.create(
            company=self.company,
            branch=self.branch,
            product=self.product,
            quantity=Decimal("16.000"),
        )

        self.lot_a = InventoryLot.objects.create(
            company=self.company,
            branch=self.branch,
            product=self.product,
            lot_number="A",
            quantity_initial=Decimal("10.000"),
            quantity_available=Decimal("10.000"),
            received_at=date(2026, 10, 30),
            expiration_date=date(2026, 11, 15),
        )

        self.lot_1 = InventoryLot.objects.create(
            company=self.company,
            branch=self.branch,
            product=self.product,
            lot_number="1",
            quantity_initial=Decimal("1.000"),
            quantity_available=Decimal("1.000"),
            received_at=date(2026, 10, 30),
            expiration_date=date(2026, 12, 25),
        )

        self.lot_b = InventoryLot.objects.create(
            company=self.company,
            branch=self.branch,
            product=self.product,
            lot_number="B",
            quantity_initial=Decimal("5.000"),
            quantity_available=Decimal("5.000"),
            received_at=date(2026, 10, 30),
            expiration_date=date(2027, 1, 28),
        )

        self.sale = Sale.objects.create(
            company=self.company,
            branch=self.branch,
            sale_number="V-FEFO-001",
            status=SaleStatus.COMPLETED,
            subtotal=Decimal("110.00"),
            discount_total=Decimal("0.00"),
            tax_total=Decimal("0.00"),
            total=Decimal("110.00"),
            amount_received=Decimal("110.00"),
            change_amount=Decimal("0.00"),
        )

    def test_sale_consumes_inventory_using_fefo(self):
        items = [
            {
                "product": self.product,
                "quantity": Decimal("11.000"),
            },
        ]

        with transaction.atomic():
            locked_stocks = lock_and_validate_sale_stock(
                company=self.company,
                branch=self.branch,
                calculated_items=items,
            )

            deduct_sale_stock(
                sale=self.sale,
                calculated_items=items,
                locked_stocks=locked_stocks,
                user=None,
            )

        self.stock.refresh_from_db()
        self.lot_a.refresh_from_db()
        self.lot_1.refresh_from_db()
        self.lot_b.refresh_from_db()

        self.assertEqual(
            self.stock.quantity,
            Decimal("5.000"),
        )

        self.assertEqual(
            self.lot_a.quantity_available,
            Decimal("0.000"),
        )

        self.assertEqual(
            self.lot_1.quantity_available,
            Decimal("0.000"),
        )

        self.assertEqual(
            self.lot_b.quantity_available,
            Decimal("5.000"),
        )

        allocations = (
            InventoryLotSaleAllocation.objects
            .filter(
                sale=self.sale,
            )
            .order_by(
                "inventory_lot__expiration_date"
            )
        )

        self.assertEqual(
            allocations.count(),
            2,
        )

        first_allocation = allocations[0]
        second_allocation = allocations[1]

        self.assertEqual(
            first_allocation.inventory_lot_id,
            self.lot_a.id,
        )

        self.assertEqual(
            first_allocation.quantity,
            Decimal("10.000"),
        )

        self.assertEqual(
            second_allocation.inventory_lot_id,
            self.lot_1.id,
        )

        self.assertEqual(
            second_allocation.quantity,
            Decimal("1.000"),
        )

    def test_sale_uses_next_lot_after_first_is_exhausted(self):
        items = [
            {
                "product": self.product,
                "quantity": Decimal("12.000"),
            },
        ]

        with transaction.atomic():
            locked_stocks = lock_and_validate_sale_stock(
                company=self.company,
                branch=self.branch,
                calculated_items=items,
            )

            deduct_sale_stock(
                sale=self.sale,
                calculated_items=items,
                locked_stocks=locked_stocks,
                user=None,
            )

        self.lot_a.refresh_from_db()
        self.lot_1.refresh_from_db()
        self.lot_b.refresh_from_db()

        self.assertEqual(
            self.lot_a.quantity_available,
            Decimal("0.000"),
        )

        self.assertEqual(
            self.lot_1.quantity_available,
            Decimal("0.000"),
        )

        self.assertEqual(
            self.lot_b.quantity_available,
            Decimal("4.000"),
        )

    def test_sale_is_rejected_when_lot_stock_is_insufficient(self):
        self.stock.quantity = Decimal("20.000")
        self.stock.save(
            update_fields=[
                "quantity",
            ]
        )

        items = [
            {
                "product": self.product,
                "quantity": Decimal("17.000"),
            },
        ]

        with transaction.atomic():
            locked_stocks = lock_and_validate_sale_stock(
                company=self.company,
                branch=self.branch,
                calculated_items=items,
            )

            with self.assertRaises(
                InventoryStockError
            ) as context:
                deduct_sale_stock(
                    sale=self.sale,
                    calculated_items=items,
                    locked_stocks=locked_stocks,
                    user=None,
                )

        self.assertIn(
            "stock por lote",
            str(context.exception),
        )

    def test_cancel_sale_restores_original_lots(self):
        SaleItem.objects.create(
            sale=self.sale,
            product=self.product,
            product_name=self.product.name,
            product_sku=self.product.sku,
            quantity=Decimal("11.000"),
            unit_price=Decimal("10.00"),
            unit_cost=Decimal("5.00"),
            discount_percent=Decimal("0.00"),
            discount_amount=Decimal("0.00"),
            line_subtotal=Decimal("110.00"),
            line_total=Decimal("110.00"),
        )

        items = [
            {
                "product": self.product,
                "quantity": Decimal("11.000"),
            },
        ]

        with transaction.atomic():
            locked_stocks = lock_and_validate_sale_stock(
                company=self.company,
                branch=self.branch,
                calculated_items=items,
            )

            deduct_sale_stock(
                sale=self.sale,
                calculated_items=items,
                locked_stocks=locked_stocks,
                user=None,
            )

        self.lot_a.refresh_from_db()
        self.lot_1.refresh_from_db()

        self.assertEqual(
            self.lot_a.quantity_available,
            Decimal("0.000"),
        )

        self.assertEqual(
            self.lot_1.quantity_available,
            Decimal("0.000"),
        )

        with transaction.atomic():
            restore_sale_stock(
                sale=self.sale,
                user=None,
            )

        self.stock.refresh_from_db()
        self.lot_a.refresh_from_db()
        self.lot_1.refresh_from_db()
        self.lot_b.refresh_from_db()

        self.assertEqual(
            self.stock.quantity,
            Decimal("16.000"),
        )

        self.assertEqual(
            self.lot_a.quantity_available,
            Decimal("10.000"),
        )

        self.assertEqual(
            self.lot_1.quantity_available,
            Decimal("1.000"),
        )

        self.assertEqual(
            self.lot_b.quantity_available,
            Decimal("5.000"),
        )

        self.assertFalse(
            InventoryLotSaleAllocation.objects.filter(
                sale=self.sale,
            ).exists()
        )