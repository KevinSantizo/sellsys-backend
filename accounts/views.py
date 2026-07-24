from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from companies.serializers import CompanyDetailSerializer, CompanyListSerializer
from branches.models import Branch, BranchMembership
from branches.serializers import BranchListSerializer
from companies.models import CompanyMembership

from .serializers import (
    RegisterSerializer,
    UserDetailSerializer,
)


class AuthViewSet(ViewSet):
    def get_permissions(self):
        if self.action == "register":
            return [AllowAny()]

        return [IsAuthenticated()]

    def register(self, request):
        serializer = RegisterSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        user = serializer.save()

        return Response(
            {
                "message": "Cuenta creada correctamente.",
                "user": UserDetailSerializer(
                    user,
                ).data,
                "company": CompanyDetailSerializer(
                    serializer.company,
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def me(self, request):
        return Response(
            UserDetailSerializer(
                request.user,
            ).data,
        )


class SessionContextViewSet(ViewSet):
    def context(self, request):
        company_id = request.query_params.get(
            "company_id",
        )

        if not company_id:
            raise ValidationError({
                "company_id": (
                    "Debes indicar el ID de la empresa."
                ),
            })

        membership = get_object_or_404(
            CompanyMembership.objects.select_related(
                "company",
                "user",
            ),
            user=request.user,
            company_id=company_id,
            is_active=True,
            company__is_active=True,
        )

        unrestricted_roles = {
            CompanyMembership.Role.OWNER,
            CompanyMembership.Role.ADMIN,
        }

        if membership.role == CompanyMembership.Role.OWNER:
            branches = (
                Branch.objects
                .filter(
                    company=membership.company,
                    is_active=True,
                )
                .order_by(
                    "-is_main",
                    "name",
                )
            )

            default_branch = (
                    branches.filter(
                        is_main=True,
                    ).first()
                    or branches.first()
            )

        else:
            assignments = (
                BranchMembership.objects
                .filter(
                    company_membership=membership,
                    is_active=True,
                    branch__is_active=True,
                )
                .select_related("branch")
                .order_by(
                    "-is_default",
                    "-branch__is_main",
                    "branch__name",
                )
            )

            default_assignment = (
                    assignments.filter(
                        is_default=True,
                    ).first()
                    or assignments.first()
            )

            default_branch = (
                default_assignment.branch
                if default_assignment
                else None
            )

            # A los usuarios que no son OWNER solamente
            # les devolvemos su sucursal predeterminada.
            branches = (
                Branch.objects
                .filter(
                    id=default_branch.id,
                )
                if default_branch
                else Branch.objects.none()
            )

        if default_branch is None:
            raise ValidationError({
                "branches": (
                    "El usuario no tiene una sucursal "
                    "activa asignada."
                ),
            })

        return Response({
            "company": CompanyListSerializer(
                membership.company,
            ).data,

            "membership": {
                "id": str(membership.id),
                "role": membership.role,
                "role_display": (
                    membership.get_role_display()
                ),
            },

            "branches": BranchListSerializer(
                branches,
                many=True,
            ).data,

            "default_branch": BranchListSerializer(
                default_branch,
            ).data,
        })


