from types import SimpleNamespace
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from rest_framework.exceptions import PermissionDenied

from branches.models import Branch
from companies.models import Company, CompanyMembership
from companies.views import CompanyViewSet, CompanyMembershipViewSet


User = get_user_model()


class CompanyTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@sellsys.tests",
            password="SellSys123!",
        )

        self.admin = User.objects.create_user(
            email="admin@sellsys.tests",
            password="SellSys123!",
        )

        self.seller = User.objects.create_user(
            email="seller@sellsys.tests",
            password="SellSys123!",
        )

        self.outsider = User.objects.create_user(
            email="outsider@sellsys.tests",
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

        self.admin_membership = CompanyMembership.objects.create(
            company=self.company,
            user=self.admin,
            role=CompanyMembership.Role.ADMIN,
        )

        self.seller_membership = CompanyMembership.objects.create(
            company=self.company,
            user=self.seller,
            role=CompanyMembership.Role.SELLER,
        )

    def test_accessible_companies_only_returns_user_companies(self):
        view = CompanyViewSet()

        view.request = SimpleNamespace(
            user=self.owner,
        )

        view.action = "list"

        companies = view.get_queryset()

        self.assertIn(
            self.company,
            companies,
        )

        self.assertNotIn(
            self.other_company,
            companies,
        )

    def test_inactive_membership_removes_company_access(self):
        self.owner_membership.is_active = False
        self.owner_membership.save(update_fields=[ "is_active" ])

        view = CompanyViewSet()

        view.request = SimpleNamespace(
            user=self.owner,
        )

        view.action = "list"

        companies = view.get_queryset()

        self.assertNotIn(
            self.company,
            companies,
        )

    def test_create_company_creates_owner_and_main_branch(self):
        company = Company.objects.create(
            name="Empresa Nueva",
        )

        serializer = Mock()
        serializer.save.return_value = company

        view = CompanyViewSet()

        view.request = SimpleNamespace(
            user=self.outsider,
        )

        view.perform_create(serializer)

        membership = CompanyMembership.objects.get(
            company=company,
            user=self.outsider,
        )

        branch = Branch.objects.get(
            company=company,
            code="PRINCIPAL",
        )

        self.assertEqual(
            membership.role,
            CompanyMembership.Role.OWNER,
        )

        self.assertTrue(
            membership.is_active
        )

        self.assertEqual(
            branch.name,
            "Sucursal principal",
        )

        self.assertTrue(
            branch.is_main
        )

    def test_admin_can_manage_company(self):
        view = CompanyViewSet()

        view.request = SimpleNamespace(
            user=self.admin,
        )

        view.ensure_company_manager(
            self.company
        )

    def test_seller_cannot_manage_company(self):
        view = CompanyViewSet()

        view.request = SimpleNamespace(
            user=self.seller,
        )

        with self.assertRaises(PermissionDenied):
            view.ensure_company_manager(
                self.company
            )

    def test_last_owner_cannot_be_demoted(self):
        view = CompanyMembershipViewSet()

        view.request = SimpleNamespace(
            user=self.owner,
        )

        with self.assertRaises(PermissionDenied):
            view._ensure_company_keeps_owner(
                self.owner_membership,
                new_role=CompanyMembership.Role.ADMIN,
            )

    def test_last_owner_cannot_be_deleted(self):
        view = CompanyMembershipViewSet()

        view.request = SimpleNamespace(
            user=self.owner,
        )

        with self.assertRaises(PermissionDenied):
            view.perform_destroy(
                self.owner_membership
            )

        self.assertTrue(
            CompanyMembership.objects.filter(
                id=self.owner_membership.id,
            ).exists()
        )