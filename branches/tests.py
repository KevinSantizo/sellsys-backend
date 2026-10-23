from types import SimpleNamespace
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from rest_framework.exceptions import PermissionDenied

from branches.models import Branch, BranchMembership
from branches.views import BranchViewSet, BranchMembershipViewSet
from companies.models import Company, CompanyMembership


User = get_user_model()


class BranchTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@sellsys.tests",
            password="SellSys123!",
        )

        self.employee = User.objects.create_user(
            email="employee@sellsys.tests",
            password="SellSys123!",
        )

        self.company = Company.objects.create(
            name="Empresa A",
        )

        self.other_company = Company.objects.create(
            name="Empresa B",
        )

        self.owner_membership = CompanyMembership.objects.create(
            company=self.company,
            user=self.owner,
            role=CompanyMembership.Role.OWNER,
        )

        self.employee_membership = CompanyMembership.objects.create(
            company=self.company,
            user=self.employee,
            role=CompanyMembership.Role.SELLER,
        )

        self.branch_a = Branch.objects.create(
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

        self.branch_membership = BranchMembership.objects.create(
            company_membership=self.employee_membership,
            branch=self.branch_a,
            is_default=True,
        )

    def test_owner_can_see_all_company_branches(self):
        view = BranchViewSet()

        view.request = SimpleNamespace(
            user=self.owner,
            query_params={},
        )

        branches = view.get_queryset()

        self.assertIn(
            self.branch_a,
            branches,
        )

        self.assertIn(
            self.branch_b,
            branches,
        )

        self.assertNotIn(
            self.other_branch,
            branches,
        )

    def test_non_owner_only_sees_assigned_branches(self):
        view = BranchViewSet()

        view.request = SimpleNamespace(
            user=self.employee,
            query_params={},
        )

        branches = view.get_queryset()

        self.assertIn(
            self.branch_a,
            branches,
        )

        self.assertNotIn(
            self.branch_b,
            branches,
        )

    def test_inactive_branch_is_hidden(self):
        self.branch_a.is_active = False
        self.branch_a.save(update_fields=[ "is_active" ])

        view = BranchViewSet()

        view.request = SimpleNamespace(
            user=self.employee,
            query_params={},
        )

        branches = view.get_queryset()

        self.assertNotIn(
            self.branch_a,
            branches,
        )

    def test_branch_membership_cannot_use_branch_from_another_company(self):
        membership = BranchMembership(
            company_membership=self.employee_membership,
            branch=self.other_branch,
        )

        with self.assertRaises(ValidationError):
            membership.full_clean()

    def test_inactive_assignment_cannot_be_default(self):
        membership = BranchMembership(
            company_membership=self.employee_membership,
            branch=self.branch_b,
            is_default=True,
            is_active=False,
        )

        with self.assertRaises(ValidationError):
            membership.full_clean()

    def test_creating_new_default_removes_previous_default(self):
        serializer = Mock()

        serializer.validated_data = {
            "company_membership": self.employee_membership,
            "branch": self.branch_b,
            "is_default": True,
        }

        view = BranchMembershipViewSet()

        view.request = SimpleNamespace(
            user=self.owner,
        )

        view.perform_create(serializer)

        self.branch_membership.refresh_from_db()

        self.assertFalse(
            self.branch_membership.is_default
        )

        serializer.save.assert_called_once()

    def test_seller_cannot_create_branch(self):
        serializer = Mock()

        serializer.validated_data = {
            "company": self.company,
        }

        view = BranchViewSet()

        view.request = SimpleNamespace(
            user=self.employee,
        )

        with self.assertRaises(PermissionDenied):
            view.perform_create(serializer)

        serializer.save.assert_not_called()