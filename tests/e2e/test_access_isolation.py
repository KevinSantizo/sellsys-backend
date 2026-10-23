from django.contrib.auth import get_user_model
from django.test import TestCase

from rest_framework.test import (
    APIRequestFactory,
    force_authenticate,
)

from branches.models import (
    Branch,
    BranchMembership,
)

from cash.models import CashRegister
from cash.views import CashRegisterViewSet

from companies.models import (
    Company,
    CompanyMembership,
)

from reports.views import ReportSummaryView


class AccessIsolationE2ETest(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

        User = get_user_model()

        # Usuario que vamos a probar.
        self.user = User.objects.create_user(
            email="staff-e2e@sellsys.test",
            password="Test12345!",
        )

        # Dueño real de empresa A.
        self.owner_a = User.objects.create_user(
            email="owner-a@sellsys.test",
            password="Test12345!",
        )

        # Dueño de empresa B.
        self.owner_b = User.objects.create_user(
            email="owner-b@sellsys.test",
            password="Test12345!",
        )

        # =========================
        # EMPRESA A
        # =========================

        self.company_a = Company.objects.create(
            name="Empresa A E2E",
            is_active=True,
        )

        CompanyMembership.objects.create(
            user=self.owner_a,
            company=self.company_a,
            role=CompanyMembership.Role.OWNER,
            is_active=True,
        )

        self.user_membership = (
            CompanyMembership.objects.create(
                user=self.user,
                company=self.company_a,
                role=CompanyMembership.Role.ADMIN,
                is_active=True,
            )
        )

        self.branch_a_allowed = (
            Branch.objects.create(
                company=self.company_a,
                name="Sucursal Permitida",
                code="A-ALLOWED",
                is_main=True,
                is_active=True,
            )
        )

        self.branch_a_denied = (
            Branch.objects.create(
                company=self.company_a,
                name="Sucursal No Permitida",
                code="A-DENIED",
                is_main=False,
                is_active=True,
            )
        )

        BranchMembership.objects.create(
            company_membership=(
                self.user_membership
            ),
            branch=self.branch_a_allowed,
            is_active=True,
        )

        self.cash_register_allowed = (
            CashRegister.objects.create(
                company=self.company_a,
                branch=self.branch_a_allowed,
                name="Caja Permitida",
                code="CAJA-A1",
                is_active=True,
            )
        )

        self.cash_register_denied_branch = (
            CashRegister.objects.create(
                company=self.company_a,
                branch=self.branch_a_denied,
                name="Caja Otra Sucursal",
                code="CAJA-A2",
                is_active=True,
            )
        )

        # =========================
        # EMPRESA B
        # =========================

        self.company_b = Company.objects.create(
            name="Empresa B E2E",
            is_active=True,
        )

        CompanyMembership.objects.create(
            user=self.owner_b,
            company=self.company_b,
            role=CompanyMembership.Role.OWNER,
            is_active=True,
        )

        self.branch_b = Branch.objects.create(
            company=self.company_b,
            name="Sucursal Empresa B",
            code="B-001",
            is_main=True,
            is_active=True,
        )

        self.cash_register_company_b = (
            CashRegister.objects.create(
                company=self.company_b,
                branch=self.branch_b,
                name="Caja Empresa B",
                code="CAJA-B1",
                is_active=True,
            )
        )

    def test_user_only_sees_assigned_branch_data(
        self,
    ):
        request = self.factory.get(
            "/api/cash/registers/",
        )

        force_authenticate(
            request,
            user=self.user,
        )

        view = CashRegisterViewSet.as_view(
            {
                "get": "list",
            }
        )

        response = view(request)

        self.assertEqual(
            response.status_code,
            200,
            response.data,
        )

        results = response.data["results"]

        ids = {
            str(item["id"])
            for item in results
        }

        # Sí puede ver su sucursal asignada.
        self.assertIn(
            str(
                self.cash_register_allowed.id
            ),
            ids,
        )

        # No puede ver otra sucursal
        # de la misma empresa.
        self.assertNotIn(
            str(
                self.cash_register_denied_branch.id
            ),
            ids,
        )

        # Mucho menos una caja
        # de otra empresa.
        self.assertNotIn(
            str(
                self.cash_register_company_b.id
            ),
            ids,
        )

        self.assertEqual(
            len(results),
            1,
        )

    def test_user_cannot_retrieve_register_from_unassigned_branch(
        self,
    ):
        request = self.factory.get(
            (
                "/api/cash/registers/"
                f"{self.cash_register_denied_branch.id}/"
            )
        )

        force_authenticate(
            request,
            user=self.user,
        )

        view = CashRegisterViewSet.as_view(
            {
                "get": "retrieve",
            }
        )

        response = view(
            request,
            pk=self.cash_register_denied_branch.id,
        )

        # Al quedar fuera del queryset
        # accesible se comporta como
        # recurso inexistente.
        self.assertEqual(
            response.status_code,
            404,
            response.data,
        )

    def test_user_cannot_retrieve_register_from_other_company(
        self,
    ):
        request = self.factory.get(
            (
                "/api/cash/registers/"
                f"{self.cash_register_company_b.id}/"
            )
        )

        force_authenticate(
            request,
            user=self.user,
        )

        view = CashRegisterViewSet.as_view(
            {
                "get": "retrieve",
            }
        )

        response = view(
            request,
            pk=self.cash_register_company_b.id,
        )

        self.assertEqual(
            response.status_code,
            404,
            response.data,
        )

    def test_user_cannot_access_report_from_unassigned_branch(
        self,
    ):
        request = self.factory.get(
            "/api/reports/summary/",
            {
                "company_id": str(
                    self.company_a.id
                ),
                "branch_id": str(
                    self.branch_a_denied.id
                ),
                "date_from": "2026-10-01",
                "date_to": "2026-10-31",
            },
        )

        force_authenticate(
            request,
            user=self.user,
        )

        response = (
            ReportSummaryView.as_view()(
                request
            )
        )

        self.assertEqual(
            response.status_code,
            403,
            response.data,
        )

    def test_user_cannot_access_report_from_other_company(
        self,
    ):
        request = self.factory.get(
            "/api/reports/summary/",
            {
                "company_id": str(
                    self.company_b.id
                ),
                "branch_id": str(
                    self.branch_b.id
                ),
                "date_from": "2026-10-01",
                "date_to": "2026-10-31",
            },
        )

        force_authenticate(
            request,
            user=self.user,
        )

        response = (
            ReportSummaryView.as_view()(
                request
            )
        )

        self.assertEqual(
            response.status_code,
            403,
            response.data,
        )