import uuid
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase

from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from branches.models import Branch, BranchMembership
from catalog.models import Product, UnitOfMeasure
from companies.models import Company, CompanyMembership, CompanySettings
from inventory.models import (
    InventoryMovement,
    InventoryMovementType,
    ProductStock,
)
from sales.access import get_allowed_branches
from sales.models import (
    Payment,
    PaymentMethod,
    Sale,
    SaleItem,
    SaleStatus,
)
from sales.serializers import (
    PaymentInputSerializer,
    SaleCheckoutSerializer,
)
from sales.views import SaleViewSet


User = get_user_model()


class SaleTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@sellsys.tests",
            password="SellSys123!",
        )

        self.employee = User.objects.create_user(
            email="seller@sellsys.tests",
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

        self.branch_b = Branch.objects.create(
            company=self.company,
            name="Sucursal B",
            code="B",
        )

        self.other_branch = Branch.objects.create(
            company=self.other_company,
            name="Sucursal Otra",
            code="OTHER",
        )

        self.owner_membership = CompanyMembership.objects.create(
            company=self.company,
            user=self.user,
            role=CompanyMembership.Role.OWNER,
        )

        self.employee_membership = CompanyMembership.objects.create(
            company=self.company,
            user=self.employee,
            role=CompanyMembership.Role.SELLER,
        )

        BranchMembership.objects.create(
            company_membership=self.employee_membership,
            branch=self.branch,
            is_default=True,
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
            cost_price=Decimal("50.00"),
            sale_price=Decimal("100.00"),
            track_inventory=True,
        )

        self.other_product = Product.objects.create(
            company=self.other_company,
            base_unit=self.other_unit,
            name="Producto Otra Empresa",
            sku="PROD-B",
            cost_price=Decimal("50.00"),
            sale_price=Decimal("100.00"),
            track_inventory=True,
        )

        self.stock = ProductStock.objects.create(
            company=self.company,
            branch=self.branch,
            product=self.product,
            quantity=Decimal("10.000"),
        )

    def build_request(self, idempotency_key=None):
        return SimpleNamespace(
            user=self.user,
            headers={
                "Idempotency-Key": str(
                    idempotency_key or uuid.uuid4()
                ),
            },
        )

    def checkout_data(
        self,
        quantity="2.000",
        discount_percent="0.00",
        payment_amount="200.00",
        product=None,
        **changes,
    ):
        product = product or self.product

        data = {
            "company_id": str(self.company.id),
            "branch_id": str(self.branch.id),
            "customer_name": "",
            "customer_tax_id": "",
            "notes": "",
            "items": [
                {
                    "product_id": str(product.id),
                    "quantity": quantity,
                    "discount_percent": discount_percent,
                },
            ],
            "payments": [
                {
                    "method": PaymentMethod.CARD,
                    "amount": payment_amount,
                    "reference": "CARD-001",
                },
            ],
            "cart_discount_type": Sale.DiscountType.NONE,
            "cart_discount_value": "0.00",
        }

        data.update(changes)

        return data

    def test_sale_branch_must_belong_to_company(self):
        sale = Sale(
            company=self.company,
            branch=self.other_branch,
            sale_number="V-001",
        )

        with self.assertRaises(DjangoValidationError) as context:
            sale.full_clean()

        self.assertIn(
            "branch",
            context.exception.message_dict,
        )

    def test_sale_item_product_must_belong_to_sale_company(self):
        sale = Sale.objects.create(
            company=self.company,
            branch=self.branch,
            sale_number="V-001",
        )

        item = SaleItem(
            sale=sale,
            product=self.other_product,
            product_name=self.other_product.name,
            product_sku=self.other_product.sku,
            quantity=Decimal("1.000"),
            unit_price=Decimal("100.00"),
            unit_cost=Decimal("50.00"),
            line_subtotal=Decimal("100.00"),
            line_total=Decimal("100.00"),
        )

        with self.assertRaises(DjangoValidationError) as context:
            item.full_clean()

        self.assertIn(
            "product",
            context.exception.message_dict,
        )

    def test_card_payment_requires_reference(self):
        serializer = PaymentInputSerializer(
            data={
                "method": PaymentMethod.CARD,
                "amount": "100.00",
                "reference": "",
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "reference",
            serializer.errors,
        )

    def test_duplicate_product_is_rejected(self):
        data = self.checkout_data()

        data["items"].append({
            "product_id": str(self.product.id),
            "quantity": "1.000",
            "discount_percent": "0.00",
        })

        serializer = SaleCheckoutSerializer(
            data=data,
            context={
                "request": self.build_request(),
            },
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "items",
            serializer.errors,
        )

    def test_decimal_quantity_is_rejected_when_unit_disallows_it(self):
        serializer = SaleCheckoutSerializer(
            data=self.checkout_data(
                quantity="1.500",
                payment_amount="150.00",
            ),
            context={
                "request": self.build_request(),
            },
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "items",
            serializer.errors,
        )

    def test_product_from_other_company_is_rejected(self):
        serializer = SaleCheckoutSerializer(
            data=self.checkout_data(
                product=self.other_product,
                quantity="1.000",
                payment_amount="100.00",
            ),
            context={
                "request": self.build_request(),
            },
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "items",
            serializer.errors,
        )

    def test_insufficient_payment_is_rejected(self):
        serializer = SaleCheckoutSerializer(
            data=self.checkout_data(
                payment_amount="199.00",
            ),
            context={
                "request": self.build_request(),
            },
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "payments",
            serializer.errors,
        )

    def test_line_and_cart_discounts_are_calculated_correctly(self):
        serializer = SaleCheckoutSerializer(
            data=self.checkout_data(
                discount_percent="10.00",
                payment_amount="162.00",
                cart_discount_type=(
                    Sale.DiscountType.PERCENTAGE
                ),
                cart_discount_value="10.00",
            ),
            context={
                "request": self.build_request(),
            },
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        self.assertEqual(
            serializer.validated_data["subtotal"],
            Decimal("200.00"),
        )

        self.assertEqual(
            serializer.validated_data["cart_discount_amount"],
            Decimal("18.00"),
        )

        self.assertEqual(
            serializer.validated_data["discount_total"],
            Decimal("38.00"),
        )

        self.assertEqual(
            serializer.validated_data["total"],
            Decimal("162.00"),
        )

    def test_fixed_discount_cannot_exceed_cart_total(self):
        serializer = SaleCheckoutSerializer(
            data=self.checkout_data(
                cart_discount_type=Sale.DiscountType.FIXED,
                cart_discount_value="201.00",
            ),
            context={
                "request": self.build_request(),
            },
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "cart_discount_value",
            serializer.errors,
        )

    def test_manual_discounts_can_be_disabled(self):
        settings = CompanySettings.objects.get(
            company=self.company,
        )

        settings.allow_manual_discounts = False

        settings.save(
            update_fields=[
                "allow_manual_discounts",
                "updated_at",
            ]
        )

        serializer = SaleCheckoutSerializer(
            data=self.checkout_data(
                discount_percent="10.00",
                payment_amount="180.00",
            ),
            context={
                "request": self.build_request(),
            },
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "discount",
            serializer.errors,
        )

    def test_customer_can_be_required(self):
        settings = CompanySettings.objects.get(
            company=self.company,
        )

        settings.require_customer_on_sale = True

        settings.save(
            update_fields=[
                "require_customer_on_sale",
                "updated_at",
            ]
        )

        serializer = SaleCheckoutSerializer(
            data=self.checkout_data(),
            context={
                "request": self.build_request(),
            },
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "customer_name",
            serializer.errors,
        )

    def test_maximum_discount_is_enforced(self):
        settings = CompanySettings.objects.get(
            company=self.company,
        )

        settings.allow_manual_discounts = True
        settings.max_discount_percent = Decimal("5.00")

        settings.save(
            update_fields=[
                "allow_manual_discounts",
                "max_discount_percent",
                "updated_at",
            ]
        )

        serializer = SaleCheckoutSerializer(
            data=self.checkout_data(
                discount_percent="10.00",
                payment_amount="180.00",
            ),
            context={
                "request": self.build_request(),
            },
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "discount",
            serializer.errors,
        )

    def test_non_owner_only_gets_assigned_branches(self):
        branches = get_allowed_branches(
            self.employee,
            self.company,
        )

        self.assertIn(
            self.branch,
            branches,
        )

        self.assertNotIn(
            self.branch_b,
            branches,
        )

    def test_successful_checkout_creates_sale_and_deducts_stock(self):
        serializer = SaleCheckoutSerializer(
            data=self.checkout_data(),
            context={
                "request": self.build_request(),
            },
        )

        serializer.is_valid(
            raise_exception=True
        )

        sale = serializer.save()

        self.stock.refresh_from_db()

        self.assertEqual(
            sale.status,
            SaleStatus.COMPLETED,
        )

        self.assertEqual(
            sale.subtotal,
            Decimal("200.00"),
        )

        self.assertEqual(
            sale.total,
            Decimal("200.00"),
        )

        self.assertEqual(
            self.stock.quantity,
            Decimal("8.000"),
        )

        self.assertEqual(
            SaleItem.objects.filter(
                sale=sale,
            ).count(),
            1,
        )

        self.assertEqual(
            Payment.objects.filter(
                sale=sale,
            ).count(),
            1,
        )

        movement = InventoryMovement.objects.get(
            sale=sale,
            movement_type=InventoryMovementType.SALE,
        )

        self.assertEqual(
            movement.quantity,
            Decimal("2.000"),
        )

        self.assertEqual(
            movement.previous_stock,
            Decimal("10.000"),
        )

        self.assertEqual(
            movement.new_stock,
            Decimal("8.000"),
        )

    def test_insufficient_stock_rolls_back_entire_sale(self):
        self.stock.quantity = Decimal("1.000")
        self.stock.save(update_fields=[ "quantity" ])

        serializer = SaleCheckoutSerializer(
            data=self.checkout_data(),
            context={
                "request": self.build_request(),
            },
        )

        serializer.is_valid(
            raise_exception=True
        )

        with self.assertRaises(DRFValidationError):
            serializer.save()

        self.stock.refresh_from_db()

        self.assertEqual(
            self.stock.quantity,
            Decimal("1.000"),
        )

        self.assertEqual(
            Sale.objects.count(),
            0,
        )

        self.assertEqual(
            SaleItem.objects.count(),
            0,
        )

        self.assertEqual(
            Payment.objects.count(),
            0,
        )

        self.assertEqual(
            InventoryMovement.objects.count(),
            0,
        )

    def test_cancel_sale_restores_stock(self):
        serializer = SaleCheckoutSerializer(
            data=self.checkout_data(),
            context={
                "request": self.build_request(),
            },
        )

        serializer.is_valid(
            raise_exception=True
        )

        sale = serializer.save()

        self.stock.refresh_from_db()

        self.assertEqual(
            self.stock.quantity,
            Decimal("8.000"),
        )

        factory = APIRequestFactory()

        request = factory.post(
            f"/sales/{sale.id}/cancel/",
            {},
            format="json",
        )

        force_authenticate(
            request,
            user=self.user,
        )

        view = SaleViewSet.as_view({
            "post": "cancel",
        })

        response = view(
            request,
            pk=sale.id,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        sale.refresh_from_db()
        self.stock.refresh_from_db()

        self.assertEqual(
            sale.status,
            SaleStatus.CANCELLED,
        )

        self.assertEqual(
            self.stock.quantity,
            Decimal("10.000"),
        )

        return_movement = InventoryMovement.objects.get(
            sale=sale,
            movement_type=InventoryMovementType.SALE_RETURN,
        )

        self.assertEqual(
            return_movement.quantity,
            Decimal("2.000"),
        )

        second_request = factory.post(
            f"/sales/{sale.id}/cancel/",
            {},
            format="json",
        )

        force_authenticate(
            second_request,
            user=self.user,
        )

        second_response = view(
            second_request,
            pk=sale.id,
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.stock.refresh_from_db()

        self.assertEqual(
            self.stock.quantity,
            Decimal("10.000"),
        )

        self.assertEqual(
            InventoryMovement.objects.filter(
                sale=sale,
                movement_type=(
                    InventoryMovementType.SALE_RETURN
                ),
            ).count(),
            1,
        )


class SaleIdempotencyTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="idempotency@sellsys.tests",
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

        self.branch_b = Branch.objects.create(
            company=self.company,
            name="Sucursal B",
            code="B",
        )

        self.other_branch = Branch.objects.create(
            company=self.other_company,
            name="Sucursal Otra",
            code="OTHER",
        )

        CompanyMembership.objects.create(
            company=self.company,
            user=self.user,
            role=CompanyMembership.Role.OWNER,
        )

        CompanyMembership.objects.create(
            company=self.other_company,
            user=self.user,
            role=CompanyMembership.Role.OWNER,
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
            cost_price=Decimal("50.00"),
            sale_price=Decimal("100.00"),
            track_inventory=True,
        )

        self.other_product = Product.objects.create(
            company=self.other_company,
            base_unit=self.other_unit,
            name="Producto B",
            sku="PROD-B",
            cost_price=Decimal("50.00"),
            sale_price=Decimal("100.00"),
            track_inventory=True,
        )

        self.stock = ProductStock.objects.create(
            company=self.company,
            branch=self.branch,
            product=self.product,
            quantity=Decimal("10.000"),
        )

        self.other_stock = ProductStock.objects.create(
            company=self.other_company,
            branch=self.other_branch,
            product=self.other_product,
            quantity=Decimal("10.000"),
        )

    def build_request(
        self,
        idempotency_key=None,
        headers=None,
    ):
        if headers is not None:
            request_headers = headers
        elif idempotency_key is not None:
            request_headers = {
                "Idempotency-Key": str(
                    idempotency_key
                ),
            }
        else:
            request_headers = {}

        return SimpleNamespace(
            user=self.user,
            headers=request_headers,
        )

    def checkout_data(
        self,
        company=None,
        branch=None,
        product=None,
        quantity="2.000",
        payment_amount="200.00",
    ):
        company = company or self.company
        branch = branch or self.branch
        product = product or self.product

        return {
            "company_id": str(company.id),
            "branch_id": str(branch.id),
            "customer_name": "",
            "customer_tax_id": "",
            "notes": "",
            "items": [
                {
                    "product_id": str(product.id),
                    "quantity": quantity,
                    "discount_percent": "0.00",
                },
            ],
            "payments": [
                {
                    "method": PaymentMethod.CARD,
                    "amount": payment_amount,
                    "reference": "CARD-001",
                },
            ],
            "cart_discount_type": (
                Sale.DiscountType.NONE
            ),
            "cart_discount_value": "0.00",
        }

    def create_sale(
        self,
        idempotency_key,
        **changes,
    ):
        serializer = SaleCheckoutSerializer(
            data=self.checkout_data(
                **changes
            ),
            context={
                "request": self.build_request(
                    idempotency_key
                ),
            },
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        return serializer.save()

    def test_idempotency_key_is_required(self):
        serializer = SaleCheckoutSerializer(
            data=self.checkout_data(),
            context={
                "request": self.build_request(),
            },
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "idempotency_key",
            serializer.errors,
        )

    def test_idempotency_key_must_be_valid_uuid(self):
        serializer = SaleCheckoutSerializer(
            data=self.checkout_data(),
            context={
                "request": self.build_request(
                    headers={
                        "Idempotency-Key": (
                            "esto-no-es-un-uuid"
                        ),
                    }
                ),
            },
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "idempotency_key",
            serializer.errors,
        )

    def test_retry_returns_same_sale(self):
        idempotency_key = uuid.uuid4()

        first_sale = self.create_sale(
            idempotency_key
        )

        second_sale = self.create_sale(
            idempotency_key
        )

        self.assertEqual(
            first_sale.id,
            second_sale.id,
        )

        self.assertEqual(
            Sale.objects.filter(
                company=self.company,
                idempotency_key=idempotency_key,
            ).count(),
            1,
        )

    def test_retry_does_not_duplicate_items_or_payments(self):
        idempotency_key = uuid.uuid4()

        sale = self.create_sale(
            idempotency_key
        )

        self.create_sale(
            idempotency_key
        )

        self.assertEqual(
            SaleItem.objects.filter(
                sale=sale,
            ).count(),
            1,
        )

        self.assertEqual(
            Payment.objects.filter(
                sale=sale,
            ).count(),
            1,
        )

    def test_retry_does_not_deduct_stock_twice(self):
        idempotency_key = uuid.uuid4()

        self.create_sale(
            idempotency_key
        )

        self.stock.refresh_from_db()

        self.assertEqual(
            self.stock.quantity,
            Decimal("8.000"),
        )

        self.create_sale(
            idempotency_key
        )

        self.stock.refresh_from_db()

        self.assertEqual(
            self.stock.quantity,
            Decimal("8.000"),
        )

    def test_retry_does_not_duplicate_inventory_movement(self):
        idempotency_key = uuid.uuid4()

        sale = self.create_sale(
            idempotency_key
        )

        self.create_sale(
            idempotency_key
        )

        self.assertEqual(
            InventoryMovement.objects.filter(
                sale=sale,
                movement_type=(
                    InventoryMovementType.SALE
                ),
            ).count(),
            1,
        )

    def test_same_key_cannot_be_used_in_another_branch(self):
        idempotency_key = uuid.uuid4()

        self.create_sale(
            idempotency_key
        )

        serializer = SaleCheckoutSerializer(
            data=self.checkout_data(
                branch=self.branch_b,
            ),
            context={
                "request": self.build_request(
                    idempotency_key
                ),
            },
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "idempotency_key",
            serializer.errors,
        )

        self.assertEqual(
            Sale.objects.filter(
                company=self.company,
                idempotency_key=idempotency_key,
            ).count(),
            1,
        )

    def test_same_key_can_be_used_by_different_company(self):
        idempotency_key = uuid.uuid4()

        first_sale = self.create_sale(
            idempotency_key
        )

        second_sale = self.create_sale(
            idempotency_key,
            company=self.other_company,
            branch=self.other_branch,
            product=self.other_product,
        )

        self.assertNotEqual(
            first_sale.id,
            second_sale.id,
        )

        self.assertEqual(
            first_sale.idempotency_key,
            second_sale.idempotency_key,
        )

        self.assertEqual(
            Sale.objects.filter(
                idempotency_key=idempotency_key,
            ).count(),
            2,
        )

        self.stock.refresh_from_db()
        self.other_stock.refresh_from_db()

        self.assertEqual(
            self.stock.quantity,
            Decimal("8.000"),
        )

        self.assertEqual(
            self.other_stock.quantity,
            Decimal("8.000"),
        )