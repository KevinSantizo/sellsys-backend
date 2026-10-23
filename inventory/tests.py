from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TransactionTestCase

from branches.models import Branch
from catalog.models import Product, UnitOfMeasure
from companies.models import Company
from inventory.models import ProductStock
from inventory.services import (
    InventoryStockError,
    lock_and_validate_sale_stock,
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