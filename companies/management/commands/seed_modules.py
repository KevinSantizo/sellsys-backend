from django.core.management.base import BaseCommand
from django.db import transaction

from companies.models import (
    Company,
    CompanyModule,
    Module,
)


MODULES = [
    {
        "code": "CATALOG",
        "name": "Catálogo",
        "description": (
            "Productos, servicios, categorías y marcas."
        ),
        "is_core": True,
        "default_enabled": True,
        "is_active": True,
        "display_order": 10,
    },
    {
        "code": "INVENTORY",
        "name": "Inventario",
        "description": (
            "Existencias y movimientos de inventario."
        ),
        "is_core": False,
        "default_enabled": True,
        "is_active": True,
        "display_order": 20,
    },
    {
        "code": "PURCHASES",
        "name": "Compras",
        "description": (
            "Compras y recepción de productos."
        ),
        "is_core": False,
        "default_enabled": True,
        "is_active": True,
        "display_order": 30,
    },
    {
        "code": "SALES",
        "name": "Ventas",
        "description": (
            "Punto de venta y gestión de ventas."
        ),
        "is_core": True,
        "default_enabled": True,
        "is_active": True,
        "display_order": 40,
    },
    {
        "code": "CUSTOMERS",
        "name": "Clientes",
        "description": (
            "Administración de clientes."
        ),
        "is_core": False,
        "default_enabled": True,
        "is_active": True,
        "display_order": 50,
    },
    {
        "code": "SUPPLIERS",
        "name": "Proveedores",
        "description": (
            "Administración de proveedores."
        ),
        "is_core": False,
        "default_enabled": True,
        "is_active": True,
        "display_order": 60,
    },
    {
        "code": "CREDIT_SALES",
        "name": "Ventas a crédito",
        "description": (
            "Créditos, saldos y pagos pendientes."
        ),
        "is_core": False,
        "default_enabled": False,
        "is_active": True,
        "display_order": 70,
    },
    {
        "code": "PRODUCT_VARIANTS",
        "name": "Variantes de producto",
        "description": (
            "Tallas, colores, medidas y variantes."
        ),
        "is_core": False,
        "default_enabled": False,
        "is_active": True,
        "display_order": 80,
    },
    {
        "code": "BATCHES",
        "name": "Lotes",
        "description": (
            "Control de inventario mediante lotes."
        ),
        "is_core": False,
        "default_enabled": False,
        "is_active": True,
        "display_order": 90,
    },
    {
        "code": "EXPIRATIONS",
        "name": "Vencimientos",
        "description": (
            "Control de fechas de vencimiento."
        ),
        "is_core": False,
        "default_enabled": False,
        "is_active": True,
        "display_order": 100,
    },
    {
        "code": "SERIAL_NUMBERS",
        "name": "Números de serie",
        "description": (
            "Seguimiento individual mediante series."
        ),
        "is_core": False,
        "default_enabled": False,
        "is_active": True,
        "display_order": 110,
    },
    {
        "code": "REPORTS",
        "name": "Reportes",
        "description": (
            "Indicadores y reportes empresariales."
        ),
        "is_core": False,
        "default_enabled": True,
        "is_active": True,
        "display_order": 120,
    },
]


class Command(BaseCommand):
    help = "Crea o actualiza los módulos base de SellSys."

    @transaction.atomic
    def handle(self, *args, **options):
        modules = []

        for data in MODULES:
            code = data["code"]

            defaults = {
                key: value
                for key, value in data.items()
                if key != "code"
            }

            module, _ = Module.objects.update_or_create(
                code=code,
                defaults=defaults,
            )

            modules.append(module)

        for company in Company.objects.all():
            for module in modules:
                CompanyModule.objects.get_or_create(
                    company=company,
                    module=module,
                    defaults={
                        "enabled": (
                            module.default_enabled
                        ),
                    },
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(modules)} módulos sincronizados."
            )
        )