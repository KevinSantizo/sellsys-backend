from django.contrib import admin
from django.db import transaction

from .models import (
    InventoryMovement,
    InventoryMovementType,
    ProductStock, InventoryLot,
    InventoryLotSaleAllocation
)

@admin.register(InventoryLotSaleAllocation)
class InventoryLotSaleAllocationAdmin(
    admin.ModelAdmin
):
    list_display = (
        "sale",
        "product",
        "inventory_lot",
        "quantity",
        "created_at",
    )

    list_filter = (
        "product",
        "created_at",
    )

    search_fields = (
        "sale__sale_number",
        "product__name",
        "product__sku",
        "inventory_lot__lot_number",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    autocomplete_fields = (
        "sale",
        "product",
        "inventory_lot",
    )

@admin.register(ProductStock)
class ProductStockAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "company",
        "branch",
        "quantity",
        "updated_at",
    )

    list_filter = (
        "company",
        "branch",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "product__name",
        "product__sku",
        "product__barcode",
        "company__name",
        "branch__name",
    )

    ordering = (
        "company__name",
        "branch__name",
        "product__name",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    list_select_related = (
        "company",
        "branch",
        "product",
    )

    fieldsets = (
        (
            "Existencia",
            {
                "fields": (
                    "id",
                    "company",
                    "branch",
                    "product",
                    "quantity",
                ),
            },
        ),
        (
            "Auditoría",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def get_readonly_fields(
        self,
        request,
        obj=None,
    ):
        readonly_fields = list(
            super().get_readonly_fields(
                request,
                obj,
            )
        )

        # Cuando el registro ya existe, no permitimos
        # cambiarlo a otra empresa, sucursal o producto.
        if obj:
            readonly_fields.extend([
                "company",
                "branch",
                "product",
            ])

        return readonly_fields

    @transaction.atomic
    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        previous_quantity = 0

        if change:
            previous_stock = (
                ProductStock.objects
                .select_for_update()
                .get(pk=obj.pk)
            )

            previous_quantity = (
                previous_stock.quantity
            )

        obj.full_clean()

        super().save_model(
            request,
            obj,
            form,
            change,
        )

        new_quantity = obj.quantity

        quantity_difference = (
            new_quantity
            - previous_quantity
        )

        if quantity_difference == 0:
            return

        if not change:
            movement_type = (
                InventoryMovementType
                .INITIAL_STOCK
            )

            notes = (
                "Stock inicial registrado "
                "desde el administrador."
            )

        elif quantity_difference > 0:
            movement_type = (
                InventoryMovementType
                .ADJUSTMENT_IN
            )

            notes = (
                "Ajuste de entrada realizado "
                "desde el administrador."
            )

        else:
            movement_type = (
                InventoryMovementType
                .ADJUSTMENT_OUT
            )

            notes = (
                "Ajuste de salida realizado "
                "desde el administrador."
            )

        InventoryMovement.objects.create(
            company=obj.company,
            branch=obj.branch,
            product=obj.product,
            movement_type=movement_type,
            quantity=abs(
                quantity_difference
            ),
            previous_stock=(
                previous_quantity
            ),
            new_stock=new_quantity,
            reference="DJANGO-ADMIN",
            notes=notes,
            created_by=request.user,
        )


@admin.register(InventoryMovement)
class InventoryMovementAdmin(
    admin.ModelAdmin,
):
    list_display = (
        "created_at",
        "product",
        "company",
        "branch",
        "movement_type",
        "quantity",
        "previous_stock",
        "new_stock",
        "sale",
        "created_by",
    )

    list_filter = (
        "movement_type",
        "company",
        "branch",
        "created_at",
    )

    search_fields = (
        "product__name",
        "product__sku",
        "product__barcode",
        "company__name",
        "branch__name",
        "sale__sale_number",
        "reference",
        "notes",
        "created_by__email",
    )

    ordering = (
        "-created_at",
        "-id",
    )

    date_hierarchy = "created_at"

    list_select_related = (
        "company",
        "branch",
        "product",
        "sale",
        "created_by",
    )

    readonly_fields = (
        "id",
        "company",
        "branch",
        "product",
        "movement_type",
        "quantity",
        "previous_stock",
        "new_stock",
        "sale",
        "reference",
        "notes",
        "created_by",
        "created_at",
    )

    fieldsets = (
        (
            "Movimiento",
            {
                "fields": (
                    "id",
                    "movement_type",
                    "company",
                    "branch",
                    "product",
                    "quantity",
                ),
            },
        ),
        (
            "Existencias",
            {
                "fields": (
                    "previous_stock",
                    "new_stock",
                ),
            },
        ),
        (
            "Referencia",
            {
                "fields": (
                    "sale",
                    "reference",
                    "notes",
                ),
            },
        ),
        (
            "Auditoría",
            {
                "fields": (
                    "created_by",
                    "created_at",
                ),
            },
        ),
    )

    def has_add_permission(
        self,
        request,
    ):
        # Los movimientos se generan al modificar
        # existencias o completar una venta.
        return False

    def has_delete_permission(self, request, obj=None):
        return True


@admin.register(InventoryLot)
class InventoryLotAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "company",
        "branch",
        "lot_number",
        "quantity_initial",
        "quantity_available",
        "received_at",
        "expiration_date",
    )

    list_filter = (
        "company",
        "branch",
        "expiration_date",
        "received_at",
    )

    search_fields = (
        "product__name",
        "product__sku",
        "lot_number",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )