"""
Replenishment Service — Shared logic for creating/upgrading replenishment requests.

Used by:
    - StockReservationCronService (automatic, priority HIGH)
    - WebSocket PDA handlers (operator-triggered, priority URGENT)

Centralizes:
    - Finding REPO origin locations with available stock
    - Calculating product capacity from family
    - Finding/assigning free picking locations
    - Distributing requests across multiple origins → multiple destinations
    - Reserving stock on REPO origins to prevent double allocation
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.adapters.secondary.database.config import (
    ALMACEN_REPOSICION_ID,
    ALMACEN_PICKING_ID,
)
from src.adapters.secondary.database.orm import (
    Order,
    OrderLine,
    ProductLocation,
    ProductReference,
    ProductFamily,
    ReplenishmentRequest,
)

DEFAULT_LOCATION_CAPACITY = 20

logger = logging.getLogger(__name__)


@dataclass
class ReplenishmentResult:
    """Result of a replenishment request creation attempt."""
    status: str  # "created", "upgraded", "no_stock", "product_inactive", "no_locations"
    created_requests: List = field(default_factory=list)
    upgraded_requests: List = field(default_factory=list)
    total_needed: int = 0
    total_available_in_repo: int = 0
    origin_count: int = 0
    dest_count: int = 0
    warnings: List[str] = field(default_factory=list)


def find_all_replenishment_origins(db: Session, product_id: int) -> List[ProductLocation]:
    """
    Busca TODAS las ubicaciones con stock disponible en almacén de reposición.
    Disponible = stock_actual - stock_reservado > 0.
    Ordenadas por stock disponible descendente.
    """
    available_stock = ProductLocation.stock_actual - func.coalesce(ProductLocation.stock_reservado, 0)
    return (
        db.query(ProductLocation)
        .filter(
            ProductLocation.product_id == product_id,
            ProductLocation.almacen_id == ALMACEN_REPOSICION_ID,
            ProductLocation.activa == True,
            available_stock > 0,
        )
        .order_by(available_stock.desc())
        .all()
    )


def get_product_capacity(db: Session, product_id: int) -> int:
    """
    Obtiene la capacidad máxima por ubicación para un producto,
    basada en su familia. Si no tiene familia, usa DEFAULT_LOCATION_CAPACITY.
    """
    product = db.query(ProductReference).filter_by(id=product_id).first()
    if product and product.familia_id:
        familia = db.query(ProductFamily).filter_by(id=product.familia_id).first()
        if familia and familia.capacidad_ubicacion:
            return familia.capacidad_ubicacion
    return DEFAULT_LOCATION_CAPACITY


def find_free_picking_locations(db: Session, count: int) -> List[ProductLocation]:
    """
    Busca ubicaciones disponibles en el almacén de picking.

    Retorna hasta 'count' ubicaciones.
    """
    result: List[ProductLocation] = []

    # 1. Ubicaciones sin producto asignado (las más limpias)
    free_locations = (
        db.query(ProductLocation)
        .filter(
            ProductLocation.almacen_id == ALMACEN_PICKING_ID,
            ProductLocation.product_id.is_(None),
            ProductLocation.activa == True,
        )
        .order_by(
            ProductLocation.pasillo.asc(),
            ProductLocation.ubicacion.asc(),
            ProductLocation.altura.asc(),
        )
        .limit(count)
        .all()
    )
    result.extend(free_locations)

    # 2. Si no hay suficientes, buscar ubicaciones asignadas pero disponibles
    remaining = count - len(result)
    if remaining > 0:
        candidates = (
            db.query(ProductLocation)
            .filter(
                ProductLocation.almacen_id == ALMACEN_PICKING_ID,
                ProductLocation.product_id.isnot(None),
                ProductLocation.activa == True,
                ProductLocation.stock_actual <= 0,
                ProductLocation.stock_reservado <= 0,
            )
            .order_by(
                ProductLocation.pasillo.asc(),
                ProductLocation.ubicacion.asc(),
                ProductLocation.altura.asc(),
            )
            .all()
        )

        for loc in candidates:
            if len(result) >= count:
                break
            if loc.is_available(db):
                old_product = loc.product_id
                loc.product_id = None
                logger.info(
                    f"    🔄 Ubicación {loc.codigo_ubicacion} liberada "
                    f"(producto anterior={old_product}, sin stock ni solicitud)"
                )
                result.append(loc)

    return result


def assign_product_to_location(
    location: ProductLocation, product_id: int, capacity: int
):
    """
    Asigna un producto a una ubicación libre.
    Configura stock_minimo = capacity para futuras referencias.
    """
    location.product_id = product_id
    location.stock_minimo = capacity
    location.stock_actual = 0
    location.stock_reservado = 0
    location.ultima_actualizacion_stock = datetime.utcnow()

    logger.info(
        f"    📍 Producto {product_id} asignado a ubicación "
        f"{location.codigo_ubicacion} (capacidad={capacity})"
    )


def create_or_upgrade_replenishment(
    db: Session,
    product_id: int,
    requester_id: int,
    priority: str = "HIGH",
    order_id: Optional[int] = None,
    cantidad_needed: int = 0,
    status_id_list: Optional[List[int]] = None,
) -> ReplenishmentResult:
    """
    Lógica central de creación/escalado de solicitudes de reposición.

    1. Obtener TODAS las ubicaciones origen en REPO con stock disponible
    2. Calcular demanda total de TODAS las órdenes activas sin reserva
    3. Asignar ubicaciones destino en picking según demanda
    4. Distribuir solicitudes: múltiples orígenes → múltiples destinos
    5. Solo crear solicitudes por la cantidad realmente disponible en REPO
    6. Reservar stock en REPO para evitar doble asignación

    Args:
        db: Sesión de base de datos
        product_id: ID del producto a reponer
        requester_id: ID del operador que solicita
        priority: "HIGH" (cron) o "URGENT" (PDA)
        order_id: ID de la orden que originó la solicitud (opcional)
        cantidad_needed: Cantidad mínima necesaria
        status_id_list: IDs de estados de orden activos (para calcular total needed)

    Returns:
        ReplenishmentResult con el detalle de lo que se creó/actualizó
    """
    result = ReplenishmentResult(status="created")

    # Verificar que el producto esté activo
    product = db.query(ProductReference).filter_by(id=product_id).first()
    if not product or not product.activo:
        result.status = "product_inactive"
        return result

    capacity = get_product_capacity(db, product_id)

    # === ORÍGENES: obtener TODAS las ubicaciones con stock en REPO ===
    origin_locations = find_all_replenishment_origins(db, product_id)

    if not origin_locations:
        result.status = "no_stock"
        logger.warning(
            f"    ⚠️ Sin stock en REPO para producto {product_id}. "
            f"No se crea solicitud de reposición."
        )
        return result

    total_available_in_repo = sum(
        (loc.stock_actual or 0) - (loc.stock_reservado or 0)
        for loc in origin_locations
    )
    result.total_available_in_repo = total_available_in_repo
    result.origin_count = len(origin_locations)

    # === DESTINOS: ubicaciones en picking para este producto ===
    # Ordenadas por stock ASC: primero llenar las que menos stock tienen
    existing_locations = (
        db.query(ProductLocation)
        .filter(
            ProductLocation.product_id == product_id,
            ProductLocation.almacen_id == ALMACEN_PICKING_ID,
            ProductLocation.activa == True,
        )
        .order_by(ProductLocation.stock_actual.asc())
        .all()
    )

    # Calcular cantidad TOTAL pendiente en TODAS las órdenes activas
    total_needed = cantidad_needed
    if status_id_list:
        total_needed = (
            db.query(func.sum(OrderLine.cantidad_solicitada))
            .join(Order, Order.id == OrderLine.order_id)
            .filter(
                OrderLine.product_reference_id == product_id,
                OrderLine.stock_reserved == False,
                Order.status_id.in_(status_id_list),
            )
            .scalar() or 0
        )
        total_needed = max(total_needed, cantidad_needed)

    result.total_needed = total_needed

    # Calcular cuántas ubicaciones destino se necesitan
    locations_needed = math.ceil(total_needed / capacity) if total_needed > 0 else 1
    locations_needed = max(locations_needed, 1)

    # Asignar ubicaciones libres si faltan
    new_locations_needed = max(0, locations_needed - len(existing_locations))

    if new_locations_needed > 0:
        free_locations = find_free_picking_locations(db, new_locations_needed)

        if len(free_locations) < new_locations_needed:
            result.warnings.append(
                f"Solo hay {len(free_locations)} ubicaciones libres "
                f"de {new_locations_needed} necesarias para producto {product_id}"
            )
            logger.warning(
                f"    ⚠️ Solo hay {len(free_locations)} ubicaciones libres "
                f"de {new_locations_needed} necesarias para producto {product_id}"
            )

        for loc in free_locations:
            assign_product_to_location(loc, product_id, capacity)
            existing_locations.append(loc)

    if not existing_locations:
        result.status = "no_locations"
        logger.error(
            f"    ❌ No hay ubicaciones disponibles para producto {product_id}. "
            f"Almacén de picking lleno."
        )
        return result

    result.dest_count = len(existing_locations)

    # === DISTRIBUCIÓN: múltiples orígenes → múltiples destinos ===
    origin_remaining = {
        loc.id: (loc.stock_actual or 0) - (loc.stock_reservado or 0)
        for loc in origin_locations
    }
    origin_map = {loc.id: loc for loc in origin_locations}
    origin_ids = [loc.id for loc in origin_locations]
    origin_idx = 0

    logger.info(
        f"    📊 Producto {product_id}: total_needed={total_needed}, "
        f"repo_disponible={total_available_in_repo}, "
        f"orígenes={len(origin_locations)}, destinos={len(existing_locations)}"
    )

    for dest_location in existing_locations:
        current_stock = (dest_location.stock_actual or 0)
        deficit = capacity - current_stock

        if deficit <= 0:
            continue

        # Verificar si ya existe solicitud pendiente para esta ubicación
        existing_request = db.query(ReplenishmentRequest).filter(
            ReplenishmentRequest.product_id == product_id,
            ReplenishmentRequest.location_destino_id == dest_location.id,
            ReplenishmentRequest.status.in_(["READY", "IN_PROGRESS"]),
        ).first()

        if existing_request:
            # Escalar prioridad si la nueva es mayor
            escalated = False
            if priority == "URGENT" and existing_request.priority != "URGENT":
                existing_request.priority = "URGENT"
                existing_request.updated_at = datetime.utcnow()
                escalated = True
            elif existing_request.priority not in ("HIGH", "URGENT"):
                existing_request.priority = priority
                existing_request.updated_at = datetime.utcnow()
                escalated = True

            if escalated:
                logger.info(
                    f"    ⬆ Solicitud #{existing_request.id} escalada a {existing_request.priority} "
                    f"(producto={product_id})"
                )
            result.upgraded_requests.append(existing_request)
            continue

        # Distribuir el déficit entre ubicaciones origen disponibles
        remaining_deficit = deficit

        while remaining_deficit > 0 and origin_idx < len(origin_ids):
            oid = origin_ids[origin_idx]
            available = origin_remaining[oid]

            if available <= 0:
                origin_idx += 1
                continue

            take = min(remaining_deficit, available)
            origin_remaining[oid] -= take
            remaining_deficit -= take

            new_request = ReplenishmentRequest(
                location_origen_id=oid,
                location_destino_id=dest_location.id,
                product_id=product_id,
                requested_quantity=take,
                status="READY",
                priority=priority,
                requester_id=requester_id,
                requested_at=datetime.utcnow(),
                order_id=order_id,
            )

            db.add(new_request)
            db.flush()

            # Reservar stock en ubicación origen para evitar doble asignación
            origin_loc = origin_map[oid]
            origin_loc.stock_reservado = (origin_loc.stock_reservado or 0) + take
            logger.info(
                f"    🆕 Solicitud #{new_request.id} {priority}/READY "
                f"(producto={product_id}, "
                f"origen={origin_loc.codigo_ubicacion}[disp={available}], "
                f"destino={dest_location.codigo_ubicacion}, "
                f"cantidad={take})"
            )
            result.created_requests.append(new_request)

            if origin_remaining[oid] <= 0:
                origin_idx += 1

        # Si no queda stock en REPO, dejar de crear solicitudes
        if origin_idx >= len(origin_ids):
            if remaining_deficit > 0:
                result.warnings.append(
                    f"Stock en REPO agotado para producto {product_id}. "
                    f"Faltan {remaining_deficit} uds para {dest_location.codigo_ubicacion}"
                )
                logger.warning(
                    f"    ⚠️ Stock en REPO agotado para producto {product_id}. "
                    f"Faltan {remaining_deficit} uds para "
                    f"{dest_location.codigo_ubicacion}"
                )
            break

    if not result.created_requests and result.upgraded_requests:
        result.status = "upgraded"

    return result
