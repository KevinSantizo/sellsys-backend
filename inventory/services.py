from decimal import Decimal
from typing import Any

from django.db import transaction

from .models import (
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


def deduct_sale_stock(*, sale, calculated_items: list[dict[str, Any]], locked_stocks: dict, user) -> None:
    connection = transaction.get_connection()

    if not connection.in_atomic_block:
        raise RuntimeError(
            "El descuento de inventario debe ejecutarse dentro de una transacción."
        )

    quantities_by_product = {}
    products_by_id = {}

    for item in calculated_items:
        product = item["product"]

        if not product.track_inventory:
            continue

        quantity = Decimal(item["quantity"])

        if quantity <= Decimal("0.000"):
            raise InventoryStockError(
                f'La cantidad del producto "{product.name}" debe ser mayor a cero.'
            )

        quantities_by_product[product.id] = quantities_by_product.get(product.id, Decimal("0.000")) + quantity
        products_by_id[product.id] = product

    movements = []

    for product_id, quantity in quantities_by_product.items():
        product = products_by_id[product_id]
        stock = locked_stocks[product_id]

        if stock.company_id != sale.company_id:
            raise InventoryStockError(
                f'El inventario de "{product.name}" no pertenece a la empresa de la venta.'
            )

        if stock.branch_id != sale.branch_id:
            raise InventoryStockError(
                f'El inventario de "{product.name}" no pertenece a la sucursal de la venta.'
            )

        previous_stock = stock.quantity
        new_stock = previous_stock - quantity

        if new_stock < Decimal("0.000"):
            raise InventoryStockError(
                f'Stock insuficiente para "{product.name}".'
            )

        stock.quantity = new_stock
        stock.save(update_fields=( "quantity", "updated_at", ))

        movements.append(
            InventoryMovement(
                company=sale.company,
                branch=sale.branch,
                product=product,
                movement_type=InventoryMovementType.SALE,
                quantity=quantity,
                previous_stock=previous_stock,
                new_stock=new_stock,
                sale=sale,
                reference=sale.sale_number,
                notes="Salida automática generada al completar la venta.",
                created_by=user,
            )
        )

    if movements:
        InventoryMovement.objects.bulk_create(movements, batch_size=100)


def restore_sale_stock(*, sale, user) -> None:
    """
    Devuelve al inventario las existencias de una venta cancelada
    y registra movimientos SALE_RETURN.

    Debe ejecutarse dentro de transaction.atomic().
    """

    connection = transaction.get_connection()

    if not connection.in_atomic_block:
        raise RuntimeError("La devolución de inventario debe ejecutarse dentro de una transacción.")

    tracked_items = [ item for item in sale.items.select_related("product").all() if item.product.track_inventory ]

    if not tracked_items:
        return

    product_ids = [ item.product_id for item in tracked_items ]

    stocks = (
        ProductStock.objects
        .select_for_update()
        .filter(
            company=sale.company,
            branch=sale.branch,
            product_id__in=product_ids,
        )
        .select_related("product", "branch")
    )

    stock_map = { stock.product_id: stock for stock in stocks }

    for item in tracked_items:
        if item.product_id not in stock_map:
            raise InventoryStockError(
                f'El producto "{item.product_name}" no tiene stock registrado en la sucursal "{sale.branch.name}".'
            )

    movements = []

    for item in tracked_items:
        stock = stock_map[item.product_id]
        quantity = Decimal(item.quantity)

        previous_stock = stock.quantity
        new_stock = previous_stock + quantity

        stock.quantity = new_stock
        stock.save(update_fields=( "quantity", "updated_at", ))

        movements.append(
            InventoryMovement(
                company=sale.company,
                branch=sale.branch,
                product=item.product,
                movement_type=InventoryMovementType.SALE_RETURN,
                quantity=quantity,
                previous_stock=previous_stock,
                new_stock=new_stock,
                sale=sale,
                reference=sale.sale_number,
                notes="Entrada automática generada al cancelar la venta.",
                created_by=user,
            )
        )

    if movements:
        InventoryMovement.objects.bulk_create(movements, batch_size=100)

