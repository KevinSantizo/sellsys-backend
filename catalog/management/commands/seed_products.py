from decimal import Decimal
from itertools import cycle
from random import Random

from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.db import transaction

from companies.models import Company
from catalog.models import Product


class Command(BaseCommand):
    help = (
        "Crea productos de prueba para validar "
        "la paginación del catálogo."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--company-id",
            type=str,
            required=True,
            help="UUID de la empresa.",
        )

        parser.add_argument(
            "--count",
            type=int,
            default=200,
            help="Cantidad de productos a crear.",
        )

        parser.add_argument(
            "--reset",
            action="store_true",
            help=(
                "Elimina previamente los productos "
                "generados por este comando."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        company_id = options["company_id"]
        count = options["count"]
        reset = options["reset"]

        if count <= 0:
            raise CommandError(
                "La cantidad debe ser mayor que cero."
            )

        try:
            company = Company.objects.get(
                id=company_id,
            )
        except Company.DoesNotExist as error:
            raise CommandError(
                "No existe una empresa con ese UUID."
            ) from error

        seed_prefix = (
            f"SEED-{company.id.hex[:6].upper()}-"
        )

        if reset:
            deleted_count, _ = (
                Product.objects.filter(
                    company=company,
                    sku__startswith=seed_prefix,
                ).delete()
            )

            self.stdout.write(
                self.style.WARNING(
                    f"Se eliminaron {deleted_count} "
                    "registros de prueba."
                )
            )

        template_products = list(
            Product.objects.filter(
                company=company,
            )
            .exclude(
                sku__startswith=seed_prefix,
            )
            .order_by("created_at")[:20]
        )

        if not template_products:
            raise CommandError(
                "La empresa necesita al menos un producto "
                "creado manualmente para usar su categoría, "
                "marca y unidad como plantilla."
            )

        random_generator = Random(2026)
        template_cycle = cycle(template_products)

        product_names = [
            "Crema hidratante",
            "Sérum facial",
            "Protector solar",
            "Limpiador facial",
            "Tónico facial",
            "Mascarilla nutritiva",
            "Aceite corporal",
            "Gel limpiador",
            "Champú nutritivo",
            "Acondicionador",
            "Loción corporal",
            "Bálsamo labial",
            "Exfoliante facial",
            "Agua micelar",
            "Crema para manos",
            "Tratamiento capilar",
            "Jabón líquido",
            "Desodorante",
            "Perfume corporal",
            "Crema nocturna",
        ]

        presentations = [
            "30 ml",
            "50 ml",
            "75 ml",
            "100 ml",
            "120 ml",
            "150 ml",
            "200 ml",
            "250 ml",
            "500 ml",
            "1 unidad",
        ]

        company_barcode_code = (
            company.id.int % 10_000
        )

        products_to_create = []

        for index in range(1, count + 1):
            template = next(template_cycle)

            base_name = random_generator.choice(
                product_names
            )

            presentation = random_generator.choice(
                presentations
            )

            cost_price = Decimal(
                str(
                    random_generator.uniform(
                        5,
                        500,
                    )
                )
            ).quantize(Decimal("0.01"))

            margin = Decimal(
                str(
                    random_generator.uniform(
                        1.25,
                        2.20,
                    )
                )
            )

            sale_price = (
                cost_price * margin
            ).quantize(Decimal("0.01"))

            sku = (
                f"{seed_prefix}{index:04d}"
            )

            barcode = (
                f"789"
                f"{company_barcode_code:04d}"
                f"{index:06d}"
            )

            is_service = (
                index % 20 == 0
            )

            product_data = {
                "company": company,
                "name": (
                    f"{base_name} "
                    f"{presentation} "
                    f"Demo {index:03d}"
                ),
                "description": (
                    "Producto generado automáticamente "
                    "para probar paginación, búsqueda "
                    "y rendimiento del catálogo."
                ),
                "sku": sku,
                "barcode": barcode,
                "product_type": (
                    "SERVICE"
                    if is_service
                    else "PRODUCT"
                ),
                "cost_price": cost_price,
                "sale_price": sale_price,
                "track_inventory": (
                    not is_service
                ),
                "is_active": (
                    index % 15 != 0
                ),
            }

            # Copia las relaciones del producto plantilla.
            if hasattr(template, "category_id"):
                product_data["category_id"] = (
                    template.category_id
                )

            if hasattr(template, "brand_id"):
                product_data["brand_id"] = (
                    template.brand_id
                )

            if hasattr(template, "base_unit_id"):
                product_data["base_unit_id"] = (
                    template.base_unit_id
                )

            # Por si Product hereda created_by.
            if (
                hasattr(template, "created_by_id")
                and template.created_by_id
            ):
                product_data["created_by_id"] = (
                    template.created_by_id
                )

            products_to_create.append(
                Product(**product_data)
            )

        Product.objects.bulk_create(
            products_to_create,
            batch_size=100,
        )

        total_products = (
            Product.objects.filter(
                company=company,
            ).count()
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Se crearon {count} productos "
                f"para {company.name}."
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Total actual de productos: "
                f"{total_products}."
            )
        )