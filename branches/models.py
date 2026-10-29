from django.core.exceptions import ValidationError

from django.db import models

from common.models import BaseModel
from companies.models import Company, CompanyMembership

# Create your models here.

class Branch(BaseModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="branches",
    )

    name = models.CharField(
        max_length=150,
    )

    code = models.CharField(
        max_length=30,
    )

    address = models.TextField(
        blank=True,
    )

    phone = models.CharField(
        max_length=30,
        blank=True,
    )

    is_main = models.BooleanField(
        default=False,
    )

    is_active = models.BooleanField(
        default=True,
    )

    website_url = models.URLField(
        max_length=1500,
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = 'Branch'
        verbose_name_plural = 'Branches'
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="unique_branch_code_per_company",
            )
        ]

        ordering = ["name"]

    def __str__(self):
        return f"{self.company.name} - {self.name}"


class BranchMembership(BaseModel):
    company_membership = models.ForeignKey(
        CompanyMembership,
        on_delete=models.CASCADE,
        related_name="branch_memberships",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="user_assignments",
    )

    is_default = models.BooleanField(
        default=False,
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        verbose_name = "Asignación de sucursal"
        verbose_name_plural = "Asignaciones de sucursales"

        ordering = [
            "company_membership__user__email",
            "branch__name",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "company_membership",
                    "branch",
                ],
                name="unique_membership_branch",
            ),

            models.UniqueConstraint(
                fields=["company_membership"],
                condition=models.Q(is_default=True),
                name="unique_default_branch_per_membership",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.company_membership_id
            and self.branch_id
            and self.company_membership.company_id
            != self.branch.company_id
        ):
            raise ValidationError({
                "branch": (
                    "La sucursal y la membresía deben "
                    "pertenecer a la misma empresa."
                ),
            })

        if self.is_default and not self.is_active:
            raise ValidationError({
                "is_default": (
                    "Una asignación inactiva no puede "
                    "ser la sucursal predeterminada."
                ),
            })

    def __str__(self):
        return (
            f"{self.company_membership.user.email} - "
            f"{self.branch.name}"
        )