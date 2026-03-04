"""
Stock Reservation Cron Service

Servicio programado que reserva stock para órdenes en estados
PENDING, ASSIGNED e IN_PICKING, asignando ubicaciones de picking.

Arquitectura:
    - Se ejecuta cada N minutos via APScheduler
    - Usa sesión de BD independiente por ejecución
    - Busca órdenes sin stock reservado
    - Asigna product_location_id a cada order_line
    - Incrementa stock_reservado en ProductLocation
    - Crea registro de auditoría en StockMovement
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session, joinedload

from src.adapters.secondary.database.config import (
    SessionLocal,
    ALMACEN_REPOSICION_ID,
    ALMACEN_PICKING_ID,
    CRON_INTERVAL_MINUTES,
    SYSTEM_OPERATOR_CODE
)
from src.adapters.secondary.database.orm import (
    Order,
    OrderLine,
    OrderStatus,
    ProductLocation,
    StockMovement,
    ReplenishmentRequest,
    Operator,
)

logger = logging.getLogger(__name__)

# Estados de orden donde se reserva stock
RESERVATION_STATUS_CODES = ["PENDING", "ASSIGNED", "IN_PICKING"]


class StockReservationCronService:
    """
    Servicio cron para reserva automática de stock en órdenes.
    
    Responsabilidades:
        - Buscar órdenes en PENDING/ASSIGNED/IN_PICKING con líneas sin reserva
        - Asignar product_location_id de picking a cada línea
        - Incrementar stock_reservado en la ubicación
        - Crear registros de auditoría (StockMovement)
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session or SessionLocal()
        self.owns_session = db_session is None
        
        # Estadísticas de ejecución
        self.stats = {
            "lines_reserved": 0,
            "lines_skipped_no_product": 0,
            "lines_skipped_no_stock": 0,
            "replenishment_created": 0,
            "replenishment_upgraded": 0,
            "orders_processed": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None,
        }
    
    def run(self):
        """
        Ejecuta el ciclo completo de reserva de stock.
        """
        self.stats["start_time"] = datetime.utcnow()
        logger.info("📦 [STOCK-CRON] Iniciando ciclo de reserva de stock")
        
        try:
            self._reserve_stock_for_orders()
            self.db.commit()
            
        except Exception as e:
            logger.error(f"❌ [STOCK-CRON] Error fatal: {e}", exc_info=True)
            self.db.rollback()
            self.stats["errors"] += 1
        finally:
            if self.owns_session:
                self.db.close()
        
        self._log_stats()
        return self.stats
    
    def _reserve_stock_for_orders(self):
        """
        Busca órdenes en estados PENDING/ASSIGNED/IN_PICKING y
        reserva stock para líneas que aún no tienen reserva.
        """
        # Obtener IDs de los estados objetivo
        status_ids = self.db.query(OrderStatus.id).filter(
            OrderStatus.codigo.in_(RESERVATION_STATUS_CODES)
        ).all()
        status_id_list = [s[0] for s in status_ids]
        
        if not status_id_list:
            logger.warning("  [STOCK-CRON] No se encontraron estados de reserva en BD")
            return
        
        # Buscar órdenes con al menos una línea sin reservar
        orders = (
            self.db.query(Order)
            .filter(
                Order.status_id.in_(status_id_list),
            )
            .options(joinedload(Order.order_lines))
            .all()
        )
        
        if not orders:
            logger.info("  [STOCK-CRON] No hay órdenes pendientes de reserva")
            return
        
        logger.info(f"  [STOCK-CRON] Procesando {len(orders)} órdenes en {RESERVATION_STATUS_CODES}")
        
        for order in orders:
            try:
                self._reserve_order_lines(order)
                self.stats["orders_processed"] += 1
            except Exception as e:
                logger.error(
                    f"  [STOCK-CRON] Error en orden #{order.id} ({order.numero_orden}): {e}",
                    exc_info=True
                )
                self.stats["errors"] += 1
    
    def _reserve_order_lines(self, order: Order):
        """
        Reserva stock para cada línea de la orden que no tenga reserva.
        """
        for line in order.order_lines:
            # Saltar líneas ya reservadas
            if line.stock_reserved:
                continue
            
            # Saltar líneas sin producto asociado
            if not line.product_reference_id:
                self.stats["lines_skipped_no_product"] += 1
                continue
            
            # Buscar ubicación en picking con stock disponible
            location = self._find_available_picking_location(
                line.product_reference_id,
                line.cantidad_solicitada
            )
            
            if not location:
                self.stats["lines_skipped_no_stock"] += 1
                # Sin stock en picking → crear/actualizar solicitud de reposición URGENT
                self._create_or_upgrade_replenishment_request(
                    line.product_reference_id,
                    line.cantidad_solicitada,
                    order
                )
                continue
            
            # Reservar
            self._reserve_line(order, line, location)
    
    def _find_available_picking_location(
        self, product_id: int, cantidad_needed: int
    ) -> Optional[ProductLocation]:
        """
        Busca una ubicación en el almacén de picking con stock disponible suficiente.
        
        Prioriza por:
        1. Prioridad de ubicación (menor = más prioritaria)
        2. Stock disponible (mayor primero)
        """
        locations = (
            self.db.query(ProductLocation)
            .filter(
                ProductLocation.product_id == product_id,
                ProductLocation.almacen_id == ALMACEN_PICKING_ID,
                ProductLocation.activa == True,
            )
            .order_by(
                ProductLocation.prioridad.asc(),
                ProductLocation.stock_actual.desc()
            )
            .all()
        )
        
        for loc in locations:
            disponible = (loc.stock_actual or 0) - (loc.stock_reservado or 0)
            if disponible >= cantidad_needed:
                return loc
        
        return None
    
    def _reserve_line(
        self, order: Order, line: OrderLine, location: ProductLocation
    ):
        """
        Ejecuta la reserva de stock para una línea:
        - Asigna product_location_id
        - Marca stock_reserved = True
        - Incrementa stock_reservado en la ubicación
        - Crea StockMovement de auditoría
        """
        stock_antes = location.stock_reservado or 0
        
        # Actualizar línea
        line.product_location_id = location.id
        line.stock_reserved = True
        
        # Incrementar reserva en ubicación
        location.stock_reservado = stock_antes + line.cantidad_solicitada
        
        # Crear registro de auditoría
        movement = StockMovement(
            product_location_id=location.id,
            product_id=line.product_reference_id,
            order_id=order.id,
            order_line_id=line.id,
            tipo="RESERVE",
            cantidad=line.cantidad_solicitada,
            stock_antes=location.stock_actual or 0,
            stock_despues=location.stock_actual or 0,  # stock_actual no cambia en reserva
            notas=f"Reserva automática para orden {order.numero_orden}, "
                  f"línea #{line.id}, cantidad: {line.cantidad_solicitada}, "
                  f"ubicación: {location.codigo_ubicacion}",
        )
        self.db.add(movement)
        
        self.stats["lines_reserved"] += 1
        
        logger.info(
            f"    ✓ Reserva: orden={order.numero_orden} línea={line.id} "
            f"producto={line.product_reference_id} ubicación={location.codigo_ubicacion} "
            f"cantidad={line.cantidad_solicitada} "
            f"stock_reservado: {stock_antes}→{location.stock_reservado}"
        )
    
    def _find_picking_destination(self, product_id: int) -> Optional[ProductLocation]:
        """
        Busca la ubicación destino en picking para un producto.
        Retorna la ubicación activa con mayor prioridad.
        """
        return (
            self.db.query(ProductLocation)
            .filter(
                ProductLocation.product_id == product_id,
                ProductLocation.almacen_id == ALMACEN_PICKING_ID,
                ProductLocation.activa == True,
            )
            .order_by(ProductLocation.prioridad.asc())
            .first()
        )
    
    def _find_replenishment_origin(self, product_id: int) -> Optional[ProductLocation]:
        """
        Busca ubicación con stock en almacén de reposición (ID=1).
        """
        return (
            self.db.query(ProductLocation)
            .filter(
                ProductLocation.product_id == product_id,
                ProductLocation.almacen_id == ALMACEN_REPOSICION_ID,
                ProductLocation.activa == True,
                ProductLocation.stock_actual > 0,
            )
            .order_by(ProductLocation.stock_actual.desc())
            .first()
        )
    
    def _create_or_upgrade_replenishment_request(
        self,
        product_id: int,
        cantidad_needed: int,
        order: Order,
    ):
        """
        Si ya existe solicitud pendiente para este producto en picking:
            → cambiar prioridad a HIGH
        Si no existe:
            → crear nueva solicitud HIGH (READY si hay stock en reposición, WAITING_STOCK si no)
        """
        # Buscar ubicación destino en picking
        dest_location = self._find_picking_destination(product_id)
        if not dest_location:
            return  # Sin ubicación en picking para este producto
        
        # Verificar si ya existe solicitud pendiente para este producto+destino
        existing = self.db.query(ReplenishmentRequest).filter(
            ReplenishmentRequest.product_id == product_id,
            ReplenishmentRequest.location_destino_id == dest_location.id,
            ReplenishmentRequest.status.in_(["WAITING_STOCK", "READY", "IN_PROGRESS"]),
        ).first()
        
        if existing:
            # Ya existe → escalar a HIGH si no lo es
            if existing.priority != "HIGH":
                existing.priority = "HIGH"
                existing.updated_at = datetime.utcnow()
                logger.info(
                    f"    ⬆ Solicitud #{existing.id} escalada a HIGH "
                    f"(producto={product_id}, orden={order.numero_orden})"
                )
                self.stats["replenishment_upgraded"] += 1
            return
        
        # No existe → crear nueva solicitud HIGH
        origin_location = self._find_replenishment_origin(product_id)
        
        if origin_location:
            status = "READY"
            origin_id = origin_location.id
        else:
            status = "WAITING_STOCK"
            origin_id = None
        
        # Obtener operador SYSTEM
        system_operator = self.db.query(Operator).filter(
            Operator.codigo == SYSTEM_OPERATOR_CODE
        ).first()
        
        if not system_operator:
            logger.error(
                f"    ❌ Operador '{SYSTEM_OPERATOR_CODE}' no encontrado. "
                f"No se puede crear solicitud de reposición."
            )
            return
        
        deficit = max(cantidad_needed, (dest_location.stock_minimo or 0) - (dest_location.stock_actual or 0), 1)
        
        new_request = ReplenishmentRequest(
            location_origen_id=origin_id,
            location_destino_id=dest_location.id,
            product_id=product_id,
            requested_quantity=deficit,
            status=status,
            priority="URGENT",
            requester_id=system_operator.id,
            requested_at=datetime.utcnow(),
        )
        
        self.db.add(new_request)
        self.db.flush()
        
        logger.info(
            f"    🆕 Solicitud #{new_request.id} URGENT creada "
            f"(producto={product_id}, destino={dest_location.codigo_ubicacion}, "
            f"estado={status}, cantidad={deficit}, "
            f"origen orden={order.numero_orden})"
        )
        self.stats["replenishment_created"] += 1
    
    def _log_stats(self):
        """Log de estadísticas del ciclo."""
        self.stats["end_time"] = datetime.utcnow()
        
        if not self.stats["start_time"]:
            return
        
        duration = (
            self.stats["end_time"] - self.stats["start_time"]
        ).total_seconds()
        
        logger.info("=" * 60)
        logger.info("📦 [STOCK-CRON] CICLO COMPLETADO")
        logger.info(f"   Órdenes procesadas: {self.stats['orders_processed']}")
        logger.info(f"   Líneas reservadas: {self.stats['lines_reserved']}")
        logger.info(f"   Sin producto: {self.stats['lines_skipped_no_product']}")
        logger.info(f"   Sin stock disponible: {self.stats['lines_skipped_no_stock']}")
        logger.info(f"   Reposiciones creadas: {self.stats['replenishment_created']}")
        logger.info(f"   Reposiciones escaladas a URGENT: {self.stats['replenishment_upgraded']}")
        logger.info(f"   Errores: {self.stats['errors']}")
        logger.info(f"   Duración: {duration:.2f}s")
        logger.info("=" * 60)


# =============================================================================
# Funciones de descuento y liberación (usadas desde order_router.py)
# =============================================================================

def deduct_stock_for_order(order: Order, db: Session) -> List[Dict]:
    """
    Descuenta stock_actual y libera stock_reservado al pasar orden a READY.
    
    Para cada order_line con stock reservado:
    - stock_actual -= cantidad_servida (lo realmente recogido)
    - stock_reservado -= cantidad_solicitada (libera la reserva)
    - Crea StockMovement tipo DEDUCT
    
    Returns:
        Lista de diccionarios con detalle de cada descuento realizado
    """
    deductions = []
    
    for line in order.order_lines:
        if not line.product_location_id or not line.stock_reserved:
            continue
        
        location = db.get(ProductLocation, line.product_location_id)
        if not location:
            logger.warning(
                f"  [DEDUCT] Ubicación {line.product_location_id} no encontrada "
                f"para línea #{line.id} de orden {order.numero_orden}"
            )
            continue
        
        cantidad_deducir = line.cantidad_servida or 0
        stock_antes = location.stock_actual or 0
        reservado_antes = location.stock_reservado or 0
        
        # Descontar stock real
        location.stock_actual = max(0, stock_antes - cantidad_deducir)
        # Liberar reserva
        location.stock_reservado = max(0, reservado_antes - line.cantidad_solicitada)
        # Marcar reserva como consumida
        line.stock_reserved = False
        
        # Registro de auditoría
        movement = StockMovement(
            product_location_id=location.id,
            product_id=line.product_reference_id,
            order_id=order.id,
            order_line_id=line.id,
            tipo="DEDUCT",
            cantidad=-cantidad_deducir,
            stock_antes=stock_antes,
            stock_despues=location.stock_actual,
            notas=f"Descuento por orden {order.numero_orden} completada (READY). "
                  f"Servida: {cantidad_deducir}, Solicitada: {line.cantidad_solicitada}, "
                  f"Ubicación: {location.codigo_ubicacion}",
        )
        db.add(movement)
        
        deductions.append({
            "order_line_id": line.id,
            "product_location_id": location.id,
            "ubicacion": location.codigo_ubicacion,
            "cantidad_deducida": cantidad_deducir,
            "stock_antes": stock_antes,
            "stock_despues": location.stock_actual,
            "reservado_antes": reservado_antes,
            "reservado_despues": location.stock_reservado,
        })
        
        logger.info(
            f"  [DEDUCT] orden={order.numero_orden} línea={line.id} "
            f"ubicación={location.codigo_ubicacion} "
            f"stock: {stock_antes}→{location.stock_actual} "
            f"reservado: {reservado_antes}→{location.stock_reservado}"
        )
    
    return deductions


def release_stock_for_order(order: Order, db: Session) -> List[Dict]:
    """
    Libera stock_reservado al cancelar una orden.
    
    Para cada order_line con stock reservado:
    - stock_reservado -= cantidad_solicitada
    - stock_actual NO cambia (no se recogió nada)
    - Crea StockMovement tipo RELEASE
    
    Returns:
        Lista de diccionarios con detalle de cada liberación realizada
    """
    releases = []
    
    for line in order.order_lines:
        if not line.product_location_id or not line.stock_reserved:
            continue
        
        location = db.get(ProductLocation, line.product_location_id)
        if not location:
            continue
        
        reservado_antes = location.stock_reservado or 0
        
        # Liberar reserva (stock_actual no cambia)
        location.stock_reservado = max(0, reservado_antes - line.cantidad_solicitada)
        # Quitar marca de reserva
        line.stock_reserved = False
        
        # Registro de auditoría
        movement = StockMovement(
            product_location_id=location.id,
            product_id=line.product_reference_id,
            order_id=order.id,
            order_line_id=line.id,
            tipo="RELEASE",
            cantidad=line.cantidad_solicitada,
            stock_antes=location.stock_actual or 0,
            stock_despues=location.stock_actual or 0,  # No cambia
            notas=f"Liberación por cancelación de orden {order.numero_orden}. "
                  f"Cantidad liberada: {line.cantidad_solicitada}, "
                  f"Ubicación: {location.codigo_ubicacion}",
        )
        db.add(movement)
        
        releases.append({
            "order_line_id": line.id,
            "product_location_id": location.id,
            "ubicacion": location.codigo_ubicacion,
            "cantidad_liberada": line.cantidad_solicitada,
            "reservado_antes": reservado_antes,
            "reservado_despues": location.stock_reservado,
        })
        
        logger.info(
            f"  [RELEASE] orden={order.numero_orden} línea={line.id} "
            f"ubicación={location.codigo_ubicacion} "
            f"reservado: {reservado_antes}→{location.stock_reservado}"
        )
    
    return releases


# =============================================================================
# Scheduler
# =============================================================================

def _run_stock_reservation_cron():
    """
    Función ejecutada por APScheduler en cada intervalo.
    Crea instancia fresca del servicio con su propia sesión de BD.
    """
    service = StockReservationCronService()
    service.run()


def start_stock_reservation_scheduler():
    """
    Configura e inicia APScheduler con el cron de reserva de stock.
    
    Returns:
        BackgroundScheduler instance (para shutdown en lifespan)
    """
    from apscheduler.schedulers.background import BackgroundScheduler
    
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _run_stock_reservation_cron,
        "interval",
        minutes=CRON_INTERVAL_MINUTES,
        id="stock_reservation_cron",
        name="Stock Reservation Check",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.start()
    
    logger.info(
        f"⏰ [STOCK-CRON] Scheduler iniciado — cada {CRON_INTERVAL_MINUTES} minutos"
    )
    
    return scheduler
