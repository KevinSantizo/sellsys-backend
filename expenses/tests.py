from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from rest_framework import serializers, status
from rest_framework.test import APIRequestFactory, force_authenticate

from branches.models import Branch
from companies.models import Company, CompanyMembership
from expenses.models import (
    Expense,
    ExpenseCategory,
    ExpensePaymentMethod,
    ExpenseStatus,
)
from expenses.serializers import (
    ExpenseCategorySerializer,
    ExpenseSerializer,
)
from expenses.views import ExpenseViewSet
from purchases.models import Supplier


User = get_user_model()


class ExpenseTests(TestCase):

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

        self.category = ExpenseCategory.objects.create(
            company=self.company,
            name="Servicios",
        )

        self.other_category = ExpenseCategory.objects.create(
            company=self.other_company,
            name="Servicios",
        )

        self.supplier = Supplier.objects.create(
            company=self.company,
            name="Proveedor A",
        )

        self.other_supplier = Supplier.objects.create(
            company=self.other_company,
            name="Proveedor B",
        )

        self.factory = APIRequestFactory()

    def expense_data(
        self,
        amount="100.00",
        branch=None,
        category=None,
        supplier=None,
        **changes,
    ):
        branch = branch or self.branch
        category = category or self.category
        supplier = (
            self.supplier
            if supplier is None
            else supplier
        )

        data = {
            "company_id": str(self.company.id),
            "branch_id": str(branch.id),
            "category_id": str(category.id),
            "supplier_id": (
                str(supplier.id)
                if supplier
                else None
            ),
            "description": "Pago de servicio",
            "amount": amount,
            "payment_method": (
                ExpensePaymentMethod.TRANSFER
            ),
            "reference": "REF-001",
            "notes": "",
        }

        data.update(changes)

        return data

    def create_expense(self, **changes):
        serializer = ExpenseSerializer(
            data=self.expense_data(**changes)
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        return serializer.save(
            created_by=self.user,
        )

    def execute_action(
        self,
        action,
        expense,
        data=None,
    ):
        request = self.factory.post(
            f"/expenses/{expense.id}/{action}/",
            data or {},
            format="json",
        )

        force_authenticate(
            request,
            user=self.user,
        )

        view = ExpenseViewSet.as_view({
            "post": action,
        })

        return view(
            request,
            pk=expense.id,
        )

    def test_category_name_is_trimmed(self):
        serializer = ExpenseCategorySerializer(
            data={
                "company_id": str(self.company.id),
                "name": "  Servicios básicos  ",
            }
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        self.assertEqual(
            serializer.validated_data["name"],
            "Servicios básicos",
        )

    def test_blank_category_name_is_rejected(self):
        serializer = ExpenseCategorySerializer(
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

    def test_description_is_trimmed(self):
        serializer = ExpenseSerializer(
            data=self.expense_data(
                description="  Pago de internet  ",
            )
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        self.assertEqual(
            serializer.validated_data["description"],
            "Pago de internet",
        )

    def test_blank_description_is_rejected(self):
        serializer = ExpenseSerializer(
            data=self.expense_data(
                description="   ",
            )
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "description",
            serializer.errors,
        )

    def test_amount_must_be_greater_than_zero(self):
        serializer = ExpenseSerializer(
            data=self.expense_data(
                amount="0.00",
            )
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "amount",
            serializer.errors,
        )

    def test_branch_must_belong_to_company(self):
        serializer = ExpenseSerializer(
            data=self.expense_data(
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

    def test_category_must_belong_to_company(self):
        serializer = ExpenseSerializer(
            data=self.expense_data(
                category=self.other_category,
            )
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "category_id",
            serializer.errors,
        )

    def test_supplier_must_belong_to_company(self):
        serializer = ExpenseSerializer(
            data=self.expense_data(
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

    def test_existing_expense_cannot_change_company(self):
        expense = self.create_expense()

        serializer = ExpenseSerializer(
            expense,
            data={
                "company_id": str(
                    self.other_company.id
                ),
                "branch_id": str(
                    self.other_branch.id
                ),
                "category_id": str(
                    self.other_category.id
                ),
                "supplier_id": str(
                    self.other_supplier.id
                ),
                "description": "Otro gasto",
                "amount": "100.00",
                "payment_method": (
                    ExpensePaymentMethod.TRANSFER
                ),
            },
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "company_id",
            serializer.errors,
        )

    def test_existing_expense_cannot_change_branch(self):
        expense = self.create_expense()

        serializer = ExpenseSerializer(
            expense,
            data={
                "company_id": str(
                    self.company.id
                ),
                "branch_id": str(
                    self.branch_b.id
                ),
                "category_id": str(
                    self.category.id
                ),
                "supplier_id": str(
                    self.supplier.id
                ),
                "description": "Otro gasto",
                "amount": "100.00",
                "payment_method": (
                    ExpensePaymentMethod.TRANSFER
                ),
            },
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "branch_id",
            serializer.errors,
        )

    def test_new_expense_is_created_as_draft(self):
        expense = self.create_expense()

        self.assertEqual(
            expense.status,
            ExpenseStatus.DRAFT,
        )

        self.assertEqual(
            expense.created_by,
            self.user,
        )

        self.assertEqual(
            expense.amount,
            Decimal("100.00"),
        )

    def test_completed_expense_cannot_be_updated(self):
        expense = self.create_expense()

        expense.status = ExpenseStatus.COMPLETED

        expense.save(
            update_fields=[ "status" ]
        )

        serializer = ExpenseSerializer(
            expense,
            data=self.expense_data(
                amount="150.00",
            ),
        )

        self.assertTrue(
            serializer.is_valid(),
            serializer.errors,
        )

        view = ExpenseViewSet()

        with self.assertRaises(
            serializers.ValidationError
        ):
            view.perform_update(
                serializer
            )

    def test_complete_transfer_expense(self):
        expense = self.create_expense()

        response = self.execute_action(
            "complete",
            expense,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        expense.refresh_from_db()

        self.assertEqual(
            expense.status,
            ExpenseStatus.COMPLETED,
        )

    def test_only_draft_expense_can_be_completed(self):
        expense = self.create_expense()

        expense.status = ExpenseStatus.CANCELLED

        expense.save(
            update_fields=[ "status" ]
        )

        response = self.execute_action(
            "complete",
            expense,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        expense.refresh_from_db()

        self.assertEqual(
            expense.status,
            ExpenseStatus.CANCELLED,
        )

    def test_draft_expense_can_be_cancelled(self):
        expense = self.create_expense()

        response = self.execute_action(
            "cancel",
            expense,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        expense.refresh_from_db()

        self.assertEqual(
            expense.status,
            ExpenseStatus.CANCELLED,
        )

    def test_completed_transfer_expense_can_be_cancelled(self):
        expense = self.create_expense()

        complete_response = self.execute_action(
            "complete",
            expense,
        )

        self.assertEqual(
            complete_response.status_code,
            status.HTTP_200_OK,
        )

        expense.refresh_from_db()

        self.assertEqual(
            expense.status,
            ExpenseStatus.COMPLETED,
        )

        cancel_response = self.execute_action(
            "cancel",
            expense,
        )

        self.assertEqual(
            cancel_response.status_code,
            status.HTTP_200_OK,
        )

        expense.refresh_from_db()

        self.assertEqual(
            expense.status,
            ExpenseStatus.CANCELLED,
        )