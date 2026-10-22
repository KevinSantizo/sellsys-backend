from decimal import Decimal
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from common.models import BaseModel

# Create your models here.

class Company(BaseModel):
    class BusinessType(models.TextChoices):
        GENERAL_RETAIL = (
            "GENERAL_RETAIL",
            "Comercio general",
        )

        GROCERY_STORE = (
            "GROCERY_STORE",
            "Tienda de abarrotes",
        )

        HARDWARE_STORE = (
            "HARDWARE_STORE",
            "Ferretería",
        )

        CLOTHING_STORE = (
            "CLOTHING_STORE",
            "Tienda de ropa",
        )

        BEAUTY_AND_PERSONAL_CARE = (
            "BEAUTY_AND_PERSONAL_CARE",
            "Belleza y cuidado personal",
        )

        ELECTRONICS_STORE = (
            "ELECTRONICS_STORE",
            "Tienda de electrónicos",
        )

        DISTRIBUTOR = (
            "DISTRIBUTOR",
            "Distribuidora",
        )

        OTHER = (
            "OTHER",
            "Otro",
        )

    name = models.CharField(
        max_length=150,
    )

    legal_name = models.CharField(
        max_length=200,
        blank=True,
    )

    tax_identifier = models.CharField(
        max_length=50,
        blank=True,
    )

    business_type = models.CharField(
        max_length=30,
        choices=BusinessType.choices,
        default=BusinessType.GENERAL_RETAIL,
    )

    currency = models.CharField(
        max_length=3,
        default="GTQ",
    )

    timezone = models.CharField(
        max_length=50,
        default="America/Guatemala",
    )

    logo_url = models.URLField(
        max_length=1500,
        blank=True,
        null=True,
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Company'
        verbose_name_plural = 'Companies'

    def __str__(self):
        return self.name


class CompanyMembership(BaseModel):
    class Role(models.TextChoices):
        OWNER = "OWNER", "Propietario"
        ADMIN = "ADMIN", "Administrador"
        MANAGER = "MANAGER", "Encargado"
        CASHIER = "CASHIER", "Cajero"
        SELLER = "SELLER", "Vendedor"
        WAREHOUSE = "WAREHOUSE", "Bodega"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="company_memberships",
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        verbose_name = 'Company membership'
        verbose_name_plural = 'Companies membership'
        constraints = [
            models.UniqueConstraint(
                fields=["company", "user"],
                name="unique_company_user_membership",
            )
        ]

    def __str__(self):
        return (
            f"{self.user.email} - "
            f"{self.company.name} - "
            f"{self.role}"
        )


class CompanySettings(BaseModel):
    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name='settings',
    )

    allow_negative_stock = models.BooleanField(
        default=False,
    )

    require_customer_on_sale = models.BooleanField(
        default=False,
    )

    allow_manual_discounts = models.BooleanField(
        default=True,
    )

    max_discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('100.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00')),
        ],
    )

    prices_include_tax = models.BooleanField(
        default=False,
    )

    default_tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00')),
        ],
    )

    enable_low_stock_alerts = models.BooleanField(
        default=True,
    )

    class Meta:
        verbose_name = 'Company settings'
        verbose_name_plural = 'Companies settings'

    def __str__(self):
        return f'Configuración de {self.company.name}'


class Module(BaseModel):
    code = models.CharField(
        max_length=50,
        unique=True,
    )

    name = models.CharField(
        max_length=100,
    )

    description = models.TextField(
        blank=True,
    )

    is_core = models.BooleanField(
        default=False,
    )

    default_enabled = models.BooleanField(
        default=False,
    )

    is_active = models.BooleanField(
        default=True,
    )

    display_order = models.PositiveIntegerField(
        default=0,
    )

    class Meta:
        verbose_name = 'Module'
        verbose_name_plural = 'Modules'
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name


class CompanyModule(BaseModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='company_modules',
    )

    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='company_modules',
    )

    enabled = models.BooleanField(
        default=False,
    )

    class Meta:
        verbose_name = 'Company module'
        verbose_name_plural = 'Companies modules'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'module'],
                name='unique_company_module',
            ),
        ]

        ordering = [
            'module__display_order',
            'module__name',
        ]

    def __str__(self):
        status = 'Activo' if self.enabled else 'Inactivo'

        return (
            f'{self.company.name} - '
            f'{self.module.name} - '
            f'{status}'
        )