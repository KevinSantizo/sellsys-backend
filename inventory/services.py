from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import F

from .models import (
    InventoryLot,
    InventoryLotSaleAllocation,
    InventoryMovement,
    InventoryMovementType,
    ProductStock,
)

class InventoryStockError(Exception):
    """Error de disponibilidad de inventario."""


def lock_and_validate_sale_stock(*, company, branch, calculated_items: list[dict[str, Any]]) -> dict:
    connection = transaction.get_connection()

    if not connection.in_atomic_block:
        raise RuntimeError(
            "La validación de inventario debe ejecutarse dentro de una transacción."
        )

    if branch.company_id != company.id:
        raise InventoryStockError(
            "La sucursal no pertenece a la empresa seleccionada."
        )

    tracked_items = [
        item
        for item in calculated_items
        if item["product"].track_inventory
    ]

    if not tracked_items:
        return {}

    requested_by_product = {}

    for item in tracked_items:
        product = item["product"]
        requested_quantity = Decimal(item["quantity"])

        if product.company_id != company.id:
            raise InventoryStockError(
                f'El producto "{product.name}" no pertenece a la empresa seleccionada.'
            )

        if requested_quantity <= Decimal("0.000"):
            raise InventoryStockError(
                f'La cantidad del producto "{product.name}" debe ser mayor a cero.'
            )

        requested_by_product[product.id] = requested_by_product.get(product.id, Decimal("0.000")) + requested_quantity

    product_ids = list(requested_by_product.keys())

    stocks = (
        ProductStock.objects
        .select_for_update()
        .filter(
            company=company,
            branch=branch,
            product_id__in=product_ids,
        )
        .select_related(
            "product",
            "branch",
        )
    )

    stock_map = {
        stock.product_id: stock
        for stock in stocks
    }

    errors = []

    products_by_id = {
        item["product"].id: item["product"]
        for item in tracked_items
    }

    for product_id, requested_quantity in requested_by_product.items():
        product = products_by_id[product_id]
        stock = stock_map.get(product_id)

        if stock is None:
            errors.append(
                f'El producto "{product.name}" no tiene stock registrado en '
                f'la sucursal "{branch.name}".'
            )

            continue

        if stock.quantity < requested_quantity:
            errors.append(
                f'Stock insuficiente para "{product.name}". '
                f"Disponible: {stock.quantity}. "
                f"Solicitado: {requested_quantity}."
            )

    if errors:
        raise InventoryStockError(" ".join(errors))

    return stock_map


def deduct_sale_stock(
    *,
    sale,
    calculated_items: list[dict[str, Any]],
    locked_stocks: dict,
    user,
) -> None:
    connection = transaction.get_connection()

    if not connection.in_atomic_block:
        raise RuntimeError(
            "El descuento de inventario debe ejecutarse "
            "dentro de una transacción."
        )

    quantities_by_product = {}
    products_by_id = {}

    for item in calculated_items:
        product = item["product"]

        if not product.track_inventory:
            continue

        quantity = Decimal(
            item["quantity"]
        )

        if quantity <= Decimal("0.000"):
            raise InventoryStockError(
                f'La cantidad del producto '
                f'"{product.name}" debe ser mayor a cero.'
            )

        quantities_by_product[
            product.id
        ] = (
            quantities_by_product.get(
                product.id,
                Decimal("0.000"),
            )
            + quantity
        )

        products_by_id[
            product.id
        ] = product

    movements = []
    allocations = []

    for (
        product_id,
        quantity,
    ) in quantities_by_product.items():
        product = products_by_id[
            product_id
        ]

        stock = locked_stocks[
            product_id
        ]

        if (
            stock.company_id
            != sale.company_id
        ):
            raise InventoryStockError(
                f'El inventario de "{product.name}" '
                "no pertenece a la empresa de la venta."
            )

        if (
            stock.branch_id
            != sale.branch_id
        ):
            raise InventoryStockError(
                f'El inventario de "{product.name}" '
                "no pertenece a la sucursal de la venta."
            )

        previous_stock = stock.quantity

        new_stock = (
            previous_stock
            - quantity
        )

        if new_stock < Decimal("0.000"):
            raise InventoryStockError(
                f'Stock insuficiente para '
                f'"{product.name}".'
            )

        # ==========================================
        # FEFO
        # ==========================================

        lots = list(
            InventoryLot.objects
            .select_for_update()
            .filter(
                company=sale.company,
                branch=sale.branch,
                product=product,
                quantity_available__gt=0,
            )
            .order_by(
                F(
                    "expiration_date"
                ).asc(
                    nulls_last=True
                ),
                "received_at",
                "created_at",
            )
        )

        available_in_lots = sum(
            (
                lot.quantity_available
                for lot in lots
            ),
            Decimal("0.000"),
        )

        if available_in_lots < quantity:
            raise InventoryStockError(
                (
                    f'No existe suficiente stock '
                    f'por lote para "{product.name}". '
                    f"Disponible en lotes: "
                    f"{available_in_lots}. "
                    f"Solicitado: {quantity}."
                )
            )

        quantity_remaining = quantity

        for lot in lots:
            if (
                quantity_remaining
                <= Decimal("0.000")
            ):
                break

            quantity_from_lot = min(
                lot.quantity_available,
                quantity_remaining,
            )

            lot.quantity_available = (
                lot.quantity_available
                - quantity_from_lot
            )

            lot.save(
                update_fields=[
                    "quantity_available",
                    "updated_at",
                ]
            )

            allocations.append(
                InventoryLotSaleAllocation(
                    sale=sale,
                    product=product,
                    inventory_lot=lot,
                    quantity=quantity_from_lot,
                )
            )

            quantity_remaining -= (
                quantity_from_lot
            )

        # ==========================================
        # STOCK GENERAL
        # ==========================================

        stock.quantity = new_stock

        stock.save(
            update_fields=(
                "quantity",
                "updated_at",
            )
        )

        movements.append(
            InventoryMovement(
                company=sale.company,
                branch=sale.branch,
                product=product,
                movement_type=(
                    InventoryMovementType.SALE
                ),
                quantity=quantity,
                previous_stock=previous_stock,
                new_stock=new_stock,
                sale=sale,
                reference=sale.sale_number,
                notes=(
                    "Salida automática generada "
                    "al completar la venta."
                ),
                created_by=user,
            )
        )

    if allocations:
        InventoryLotSaleAllocation.objects.bulk_create(
            allocations,
            batch_size=100,
        )

    if movements:
        InventoryMovement.objects.bulk_create(
            movements,
            batch_size=100,
        )


def restore_sale_stock(
    *,
    sale,
    user,
) -> None:
    """
    Devuelve al inventario las existencias de
    una venta cancelada y restaura exactamente
    los lotes utilizados por FEFO.

    Debe ejecutarse dentro de transaction.atomic().
    """

    connection = transaction.get_connection()

    if not connection.in_atomic_block:
        raise RuntimeError(
            "La devolución de inventario debe "
            "ejecutarse dentro de una transacción."
        )

    tracked_items = [
        item
        for item
        in sale.items
        .select_related("product")
        .all()
        if item.product.track_inventory
    ]

    if not tracked_items:
        return

    quantities_by_product = {}
    products_by_id = {}

    for item in tracked_items:
        quantities_by_product[
            item.product_id
        ] = (
            quantities_by_product.get(
                item.product_id,
                Decimal("0.000"),
            )
            + Decimal(
                item.quantity
            )
        )

        products_by_id[
            item.product_id
        ] = item.product

    product_ids = list(
        quantities_by_product.keys()
    )

    stocks = (
        ProductStock.objects
        .select_for_update()
        .filter(
            company=sale.company,
            branch=sale.branch,
            product_id__in=product_ids,
        )
        .select_related(
            "product",
            "branch",
        )
    )

    stock_map = {
        stock.product_id: stock
        for stock in stocks
    }

    for product_id in product_ids:
        product = products_by_id[
            product_id
        ]

        if product_id not in stock_map:
            raise InventoryStockError(
                (
                    f'El producto "{product.name}" '
                    f"no tiene stock registrado en "
                    f'la sucursal "{sale.branch.name}".'
                )
            )

    # ==========================================
    # RECUPERAR ASIGNACIONES DE LOTES
    # ==========================================

    allocations = list(
        InventoryLotSaleAllocation.objects
        .select_for_update()
        .filter(
            sale=sale,
        )
        .select_related(
            "inventory_lot",
            "product",
        )
    )

    if not allocations:
        raise InventoryStockError(
            (
                "No se encontraron los lotes utilizados "
                "por esta venta."
            )
        )

    # ==========================================
    # RESTAURAR LOTES
    # ==========================================

    lot_ids = [
        allocation.inventory_lot_id
        for allocation in allocations
    ]

    lots = (
        InventoryLot.objects
        .select_for_update()
        .filter(
            id__in=lot_ids,
        )
    )

    lot_map = {
        lot.id: lot
        for lot in lots
    }

    for allocation in allocations:
        lot = lot_map.get(
            allocation.inventory_lot_id
        )

        if lot is None:
            raise InventoryStockError(
                (
                    "No se encontró uno de los lotes "
                    "utilizados por la venta."
                )
            )

        restored_quantity = (
            lot.quantity_available
            + allocation.quantity
        )

        if (
            restored_quantity
            > lot.quantity_initial
        ):
            raise InventoryStockError(
                (
                    f'No se puede restaurar el lote '
                    f'"{lot.lot_number or "Sin lote"}" '
                    f'del producto "{allocation.product.name}" '
                    "porque superaría su cantidad inicial."
                )
            )

        lot.quantity_available = (
            restored_quantity
        )

        lot.save(
            update_fields=[
                "quantity_available",
                "updated_at",
            ]
        )

    # ==========================================
    # RESTAURAR PRODUCT STOCK
    # ==========================================

    movements = []

    for (
        product_id,
        quantity,
    ) in quantities_by_product.items():
        stock = stock_map[
            product_id
        ]

        product = products_by_id[
            product_id
        ]

        previous_stock = (
            stock.quantity
        )

        new_stock = (
            previous_stock
            + quantity
        )

        stock.quantity = new_stock

        stock.save(
            update_fields=(
                "quantity",
                "updated_at",
            )
        )

        movements.append(
            InventoryMovement(
                company=sale.company,
                branch=sale.branch,
                product=product,
                movement_type=(
                    InventoryMovementType
                    .SALE_RETURN
                ),
                quantity=quantity,
                previous_stock=previous_stock,
                new_stock=new_stock,
                sale=sale,
                reference=sale.sale_number,
                notes=(
                    "Entrada automática generada "
                    "al cancelar la venta."
                ),
                created_by=user,
            )
        )

    if movements:
        InventoryMovement.objects.bulk_create(
            movements,
            batch_size=100,
        )

    # Ya devolvimos las cantidades.
    # Estas asignaciones ya no representan
    # una salida activa.
    InventoryLotSaleAllocation.objects.filter(
        sale=sale,
    ).delete()