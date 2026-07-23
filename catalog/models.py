from django.core.validators import MinValueValidator
from django.db import models

from common.models import BaseModel
from companies.models import Company

# Create your models here.

class Category(BaseModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='categories',
    )

    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        related_name='children',
        null=True,
        blank=True,
    )

    name = models.CharField(
        max_length=150,
    )

    description = models.TextField(
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering = ['name']

        constraints = [
            models.UniqueConstraint(
                fields=['company', 'name'],
                name='unique_category_name_per_company',
            ),
        ]

    def __str__(self):
        return f'{self.company.name} - {self.name}'


class Brand(BaseModel):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='brands',
    )

    name = models.CharField(
        max_length=150,
    )

    description = models.TextField(
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        verbose_name = 'Marca'
        verbose_name_plural = 'Marcas'
        ordering = ['name']

        constraints = [
            models.UniqueConstraint(
                fields=['company', 'name'],
                name='unique_brand_name_per_company',
            ),
        ]

    def __str__(self):
        return f'{self.company.name} - {self.name}'


class UnitOfMeasure(BaseModel):
    class UnitType(models.TextChoices):
        UNIT = 'UNIT', 'Unidad'
        WEIGHT = 'WEIGHT', 'Peso'
        LENGTH = 'LENGTH', 'Longitud'
        VOLUME = 'VOLUME', 'Volumen'
        AREA = 'AREA', 'Área'
        TIME = 'TIME', 'Tiempo'
        OTHER = 'OTHER', 'Otro'

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='units_of_measure',
    )

    name = models.CharField(
        max_length=100,
    )

    symbol = models.CharField(
        max_length=20,
    )

    unit_type = models.CharField(
        max_length=20,
        choices=UnitType.choices,
        default=UnitType.UNIT,
    )

    allows_decimal = models.BooleanField(
        default=False,
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        verbose_name = 'Unidad de medida'
        verbose_name_plural = 'Unidades de medida'
        ordering = ['name']

        constraints = [
            models.UniqueConstraint(
                fields=['company', 'name'],
                name='unique_unit_name_per_company',
            ),
            models.UniqueConstraint(
                fields=['company', 'symbol'],
                name='unique_unit_symbol_per_company',
            ),
        ]

    def __str__(self):
        return (
            f'{self.company.name} - '
            f'{self.name} ({self.symbol})'
        )

class Product(BaseModel):
    class ProductType(models.TextChoices):
        PRODUCT = "PRODUCT", "Producto"
        SERVICE = "SERVICE", "Servicio"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="products",
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        null=True,
        blank=True,
    )

    brand = models.ForeignKey(
        Brand,
        on_delete=models.PROTECT,
        related_name="products",
        null=True,
        blank=True,
    )

    base_unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        related_name="products",
        null=True,
        blank=True,
    )

    name = models.CharField(
        max_length=200,
    )

    description = models.TextField(
        blank=True,
    )

    sku = models.CharField(
        max_length=100,
    )

    barcode = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    product_type = models.CharField(
        max_length=20,
        choices=ProductType.choices,
        default=ProductType.PRODUCT,
    )

    cost_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[
            MinValueValidator(0),
        ],
    )

    sale_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[
            MinValueValidator(0),
        ],
    )

    track_inventory = models.BooleanField(
        default=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["name"]

        constraints = [
            models.UniqueConstraint(
                fields=["company", "sku"],
                name="unique_product_sku_per_company",
            ),

            models.UniqueConstraint(
                fields=["company", "barcode"],
                condition=models.Q(
                    barcode__isnull=False,
                ),
                name="unique_product_barcode_per_company",
            ),

            models.CheckConstraint(
                condition=(
                    models.Q(
                        product_type="PRODUCT",
                    )
                    | models.Q(
                        track_inventory=False,
                    )
                ),
                name="service_cannot_track_inventory",
            ),

            models.CheckConstraint(
                condition=(
                    models.Q(
                        product_type="SERVICE",
                    )
                    | models.Q(
                        base_unit__isnull=False,
                    )
                ),
                name="product_requires_base_unit",
            ),
        ]

        indexes = [
            models.Index(
                fields=["company", "name"],
                name="product_company_name_idx",
            ),

            models.Index(
                fields=["company", "barcode"],
                name="product_company_barcode_idx",
            ),
        ]

    def __str__(self):
        return f"{self.company.name} - {self.name}"