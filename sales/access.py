from branches.models import (
    Branch,
    BranchMembership,
)
from companies.models import (
    CompanyMembership,
)


def get_membership_role_code(
    membership,
) -> str:
    role = membership.role

    if isinstance(role, str):
        return role.upper()

    for attribute in (
        "code",
        "slug",
        "name",
    ):
        value = getattr(
            role,
            attribute,
            None,
        )

        if value:
            return str(value).upper()

    return str(role).upper()


def get_allowed_branches(
    user,
    company,
):
    membership = (
        CompanyMembership.objects
        .filter(
            user=user,
            company=company,
            is_active=True,
        )
        .first()
    )

    if not membership:
        return Branch.objects.none()

    role_code = get_membership_role_code(
        membership,
    )

    if role_code == "OWNER":
        return Branch.objects.filter(
            company=company,
            is_active=True,
        )

    branch_ids = (
        BranchMembership.objects
        .filter(
            company_membership=membership,
            branch__company=company,
            branch__is_active=True,
            is_active=True,
        )
        .values_list(
            "branch_id",
            flat=True,
        )
    )

    return Branch.objects.filter(
        id__in=branch_ids,
        is_active=True,
    )