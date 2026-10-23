from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)

from branches.models import (
    Branch,
    BranchMembership,
)
from companies.models import CompanyMembership


def is_authenticated_user(user):
    return bool(
        user
        and getattr(
            user,
            "is_authenticated",
            False,
        )
    )


def validate_company_branch_access(
    user,
    company_id,
    branch_id,
):
    if not is_authenticated_user(user):
        raise PermissionDenied(
            "Debes iniciar sesión."
        )

    membership = CompanyMembership.objects.filter(
        user=user,
        company_id=company_id,
        is_active=True,
        company__is_active=True,
    ).first()

    if not membership:
        raise PermissionDenied(
            "No tienes acceso a esta empresa."
        )

    branch = Branch.objects.filter(
        id=branch_id,
        company_id=company_id,
        is_active=True,
    ).first()

    if not branch:
        raise ValidationError({
            "branch_id": (
                "La sucursal no existe, está inactiva "
                "o no pertenece a la empresa seleccionada."
            )
        })

    if (
        membership.role
        == CompanyMembership.Role.OWNER
    ):
        return membership, branch

    has_branch_access = (
        BranchMembership.objects.filter(
            company_membership=membership,
            branch=branch,
            is_active=True,
            branch__is_active=True,
        ).exists()
    )

    if not has_branch_access:
        raise PermissionDenied(
            "No tienes acceso a esta sucursal."
        )

    return membership, branch


def get_user_company_branch_scope(user):
    if not is_authenticated_user(user):
        owner_company_ids = (
            CompanyMembership.objects.none()
            .values_list(
                "company_id",
                flat=True,
            )
        )

        assigned_branch_ids = (
            BranchMembership.objects.none()
            .values_list(
                "branch_id",
                flat=True,
            )
        )

        return (
            owner_company_ids,
            assigned_branch_ids,
        )

    memberships = CompanyMembership.objects.filter(
        user=user,
        is_active=True,
        company__is_active=True,
    )

    owner_company_ids = memberships.filter(
        role=CompanyMembership.Role.OWNER,
    ).values_list(
        "company_id",
        flat=True,
    )

    assigned_branch_ids = (
        BranchMembership.objects.filter(
            company_membership__in=memberships,
            is_active=True,
            branch__is_active=True,
        )
        .values_list(
            "branch_id",
            flat=True,
        )
    )

    return (
        owner_company_ids,
        assigned_branch_ids,
    )