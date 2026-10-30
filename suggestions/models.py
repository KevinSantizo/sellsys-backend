from django.conf import settings
from django.db import models

from common.models import BaseModel
from companies.models import Company
from branches.models import Branch

# Create your models here.

class Suggestion(BaseModel):
    class SuggestionType(models.TextChoices):
        IMPROVEMENT = "IMPROVEMENT", "Mejora"
        FEATURE = "FEATURE", "Nueva función"
        BUG = "BUG", "Problema"
        OTHER = "OTHER", "Otro"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        REVIEWING = "REVIEWING", "En revisión"
        ACCEPTED = "ACCEPTED", "Aceptada"
        REJECTED = "REJECTED", "Rechazada"
        COMPLETED = "COMPLETED", "Implementada"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="suggestions",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        related_name="suggestions",
        null=True,
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="suggestions",
        null=True,
        blank=True,
    )

    suggestion_type = models.CharField(
        max_length=20,
        choices=SuggestionType.choices,
        default=SuggestionType.IMPROVEMENT,
    )

    title = models.CharField(
        max_length=150,
    )

    description = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    admin_notes = models.TextField(
        blank=True,
    )

    class Meta:
        ordering = (
            "-created_at",
        )

    def __str__(self):
        return self.title