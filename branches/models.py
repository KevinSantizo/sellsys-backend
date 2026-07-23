from django.db import models

from common.models import BaseModel
from companies.models import Company

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