from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import models
from django.test import TestCase
from django.utils import timezone

from rest_framework.exceptions import PermissionDenied, ValidationError

from branches.models import Branch, BranchMembership
from companies.models import Company, CompanyMembership
from common.access import (
    get_user_company_branch_scope,
    validate_company_branch_access,
)


User = get_user_model()


class CompanyBranchAccessTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@sellsys.tests",
            password="SellSys123!",
        )

        self.employee = User.objects.create_user(
            email="employee@sellsys.tests",
            password="SellSys123!",
        )

        self.outsider = User.objects.create_user(
            email="outsider@sellsys.tests",
            password="SellSys123!",
        )

        self.company = self.create_instance(
            Company,
            "company-a",
        )

        self.other_company = self.create_instance(
            Company,
            "company-b",
        )

        self.branch_a = self.create_instance(
            Branch,
            "branch-a",
            company=self.company,
            is_active=True,
        )

        self.branch_b = self.create_instance(
            Branch,
            "branch-b",
            company=self.company,
            is_active=True,
        )

        self.other_branch = self.create_instance(
            Branch,
            "branch-other",
            company=self.other_company,
            is_active=True,
        )

        self.owner_membership = CompanyMembership.objects.create(
            company=self.company,
            user=self.owner,
            role=CompanyMembership.Role.OWNER,
            is_active=True,
        )

        normal_role = next(
            role
            for role, _ in CompanyMembership.Role.choices
            if role != CompanyMembership.Role.OWNER
        )

        self.employee_membership = CompanyMembership.objects.create(
            company=self.company,
            user=self.employee,
            role=normal_role,
            is_active=True,
        )

        self.branch_membership = BranchMembership.objects.create(
            company_membership=self.employee_membership,
            branch=self.branch_a,
            is_default=True,
            is_active=True,
        )

    def create_instance(self, model, suffix, **overrides):
        values = {}

        for field in model._meta.fields:
            if field.primary_key:
                continue

            if field.name in overrides:
                continue

            if getattr(field, "auto_now", False):
                continue

            if getattr(field, "auto_now_add", False):
                continue

            if field.has_default():
                continue

            if field.null:
                continue

            if field.blank:
                continue

            if isinstance(field, models.ForeignKey):
                raise AssertionError(
                    f"Debes proporcionar el campo requerido '{field.name}'."
                )

            if field.choices:
                values[field.name] = field.choices[0][0]
                continue

            if isinstance(field, models.EmailField):
                values[field.name] = f"{suffix}@sellsys.tests"
                continue

            if isinstance(field, (models.CharField, models.TextField)):
                value = f"tests-{field.name}-{suffix}"

                if getattr(field, "max_length", None):
                    value = value[:field.max_length]

                values[field.name] = value
                continue

            if isinstance(field, models.BooleanField):
                values[field.name] = True
                continue

            if isinstance(field, models.DecimalField):
                values[field.name] = Decimal("0.00")
                continue

            if isinstance(field, models.IntegerField):
                values[field.name] = 1
                continue

            if isinstance(field, models.DateTimeField):
                values[field.name] = timezone.now()
                continue

            if isinstance(field, models.DateField):
                values[field.name] = date.today()
                continue

            raise AssertionError(
                f"No hay valor de prueba definido para '{field.name}'."
            )

        values.update(overrides)

        return model.objects.create(**values)

    def test_owner_has_access_to_company_without_branch_membership(self):
        owner_company_ids, assigned_branch_ids = get_user_company_branch_scope(
            self.owner
        )

        self.assertIn(
            self.company.id,
            set(owner_company_ids),
        )

        self.assertNotIn(
            self.branch_a.id,
            set(assigned_branch_ids),
        )

    def test_non_owner_only_has_assigned_branch(self):
        owner_company_ids, assigned_branch_ids = get_user_company_branch_scope(
            self.employee
        )

        self.assertNotIn(
            self.company.id,
            set(owner_company_ids),
        )

        self.assertIn(
            self.branch_a.id,
            set(assigned_branch_ids),
        )

        self.assertNotIn(
            self.branch_b.id,
            set(assigned_branch_ids),
        )

    def test_inactive_company_membership_removes_access(self):
        self.employee_membership.is_active = False
        self.employee_membership.save(update_fields=[ "is_active" ])

        owner_company_ids, assigned_branch_ids = get_user_company_branch_scope(
            self.employee
        )

        self.assertNotIn(
            self.company.id,
            set(owner_company_ids),
        )

        self.assertNotIn(
            self.branch_a.id,
            set(assigned_branch_ids),
        )

    def test_inactive_branch_membership_removes_access(self):
        self.branch_membership.is_active = False
        self.branch_membership.save(update_fields=[ "is_active" ])

        _, assigned_branch_ids = get_user_company_branch_scope(
            self.employee
        )

        self.assertNotIn(
            self.branch_a.id,
            set(assigned_branch_ids),
        )

    def test_inactive_branch_removes_access(self):
        self.branch_a.is_active = False
        self.branch_a.save(update_fields=[ "is_active" ])

        _, assigned_branch_ids = get_user_company_branch_scope(
            self.employee
        )

        self.assertNotIn(
            self.branch_a.id,
            set(assigned_branch_ids),
        )

    def test_owner_can_access_any_active_branch_of_company(self):
        membership, branch = validate_company_branch_access(
            self.owner,
            self.company.id,
            self.branch_b.id,
        )

        self.assertEqual(
            membership.id,
            self.owner_membership.id,
        )

        self.assertEqual(
            branch.id,
            self.branch_b.id,
        )

    def test_non_owner_can_access_assigned_branch(self):
        membership, branch = validate_company_branch_access(
            self.employee,
            self.company.id,
            self.branch_a.id,
        )

        self.assertEqual(
            membership.id,
            self.employee_membership.id,
        )

        self.assertEqual(
            branch.id,
            self.branch_a.id,
        )

    def test_non_owner_cannot_access_unassigned_branch(self):
        with self.assertRaises(PermissionDenied):
            validate_company_branch_access(
                self.employee,
                self.company.id,
                self.branch_b.id,
            )

    def test_branch_from_another_company_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_company_branch_access(
                self.owner,
                self.company.id,
                self.other_branch.id,
            )

    def test_user_without_company_membership_is_rejected(self):
        with self.assertRaises(PermissionDenied):
            validate_company_branch_access(
                self.outsider,
                self.company.id,
                self.branch_a.id,
            )