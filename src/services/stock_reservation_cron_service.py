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

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from src.adapters.secondary.database.config import (
    SessionLocal,
    ALMACEN_PICKING_ID,
    CRON_INTERVAL_MINUTES,
    SYSTEM_OPERATOR_CODE
)
from src.adapters.secondary.database.orm import (
    Order,
    OrderLine,
    OrderLineStockAssignment,
    OrderStatus,
    ProductLocation,
    ProductReference,
    StockMovement,
    ReplenishmentRequest,
    Operator,
)
from src.services.replenishment_service import create_or_upgrade_replenishment

logger = logging.getLogger(__name__)

# Estados de orden donde se reserva stock
RESERVATION_STATUS_CODES = ["PENDING", "ASSIGNED"]


class StockReservationCronService:
    """
    Servicio cron para reserva automática de stock en órdenes.
    
    Responsabilidades:
        - Buscar órdenes en PENDING/ASSIGNED con líneas sin reserva
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
        self.status_id_list = [s[0] for s in status_ids]
        
        if not self.status_id_list:
            logger.warning("  [STOCK-CRON] No se encontraron estados de reserva en BD")
            return
        
        # Buscar órdenes con al menos una línea sin reservar
        orders = (
            self.db.query(Order)
            .filter(
                Order.status_id.in_(self.status_id_list),
                Order.almacen_id == ALMACEN_PICKING_ID,
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
        Reserva stock para cada línea de la orden que no tenga reserva completa.
        
        Soporta reserva multi-ubicación: si ninguna ubicación individual tiene
        suficiente stock pero la suma sí, distribuye la reserva entre varias.
        Si hay stock parcial, reserva lo disponible y crea reposición por el déficit.
        
        Usa la suma de assignments para determinar cuánto ya está reservado,
        permitiendo completar reservas parciales tras reposiciones.
        """
        for line in order.order_lines:
            # Saltar líneas sin producto asociado
            if not line.product_reference_id:
                self.stats["lines_skipped_no_product"] += 1
                continue
            
            # Calcular cuánto ya está reservado via assignments
            total_already_reserved = sum(
                a.cantidad_reservada for a in
                self.db.query(OrderLineStockAssignment)
                .filter_by(order_line_id=line.id).all()
            )
            
            cantidad_needed = line.cantidad_solicitada - total_already_reserved
            if cantidad_needed <= 0:
                continue  # Ya completamente reservada
            
            # Buscar TODAS las ubicaciones picking con stock disponible
            locations = self._find_available_picking_locations(
                line.product_reference_id
            )
            
            total_available = sum(
                (loc.stock_actual or 0) - (loc.stock_reservado or 0)
                for loc in locations
            )
            
            if total_available > 0:
                # Reservar lo disponible (parcial o completo)
                reserved = self._reserve_line_multi(
                    order, line, locations, cantidad_needed
                )
                
                deficit = cantidad_needed - reserved
                if deficit > 0:
                    # Parcial → crear reposición por lo que falta
                    self._create_or_upgrade_replenishment_request(
                        line.product_reference_id,
                        deficit,
                        order
                    )
            else:
                # Nada disponible → reposición por lo que falta
                self.stats["lines_skipped_no_stock"] += 1
                self._create_or_upgrade_replenishment_request(
                    line.product_reference_id,
                    cantidad_needed,
                    order
                )
    
    def _find_available_picking_locations(
        self, product_id: int
    ) -> List[ProductLocation]:
        """
        Busca TODAS las ubicaciones picking del producto con stock disponible.
        Ordenadas por stock disponible descendente (mayor primero).
        """
        available_stock = (
            ProductLocation.stock_actual - func.coalesce(ProductLocation.stock_reservado, 0)
        )
        return (
            self.db.query(ProductLocation)
            .filter(
                ProductLocation.product_id == product_id,
                ProductLocation.almacen_id == ALMACEN_PICKING_ID,
                ProductLocation.activa == True,
                available_stock > 0,
            )
            .order_by(available_stock.desc())
            .all()
        )
    
    def _reserve_line_multi(
        self, order: Order, line: OrderLine,
        locations: List[ProductLocation], cantidad_needed: int
    ) -> int:
        """
        Reserva stock distribuyendo entre múltiples ubicaciones.
        
        - product_location_id apunta a la ubicación con más stock (la primera)
        - stock_reservado se incrementa proporcionalmente en cada ubicación
        - Crea un OrderLineStockAssignment por cada ubicación usada
        - Crea un StockMovement de auditoría por cada ubicación usada
        
        Args:
            cantidad_needed: Cantidad que falta por reservar (puede ser < cantidad_solicitada
                           si es una reserva complementaria tras reposición)
        
        Returns:
            Total de unidades efectivamente reservadas
        """
        # Asignar ubicación principal si no tiene una
        if not line.product_location_id:
            line.product_location_id = locations[0].id
        line.stock_reserved = True
        
        remaining = cantidad_needed
        total_reserved = 0
        
        for loc in locations:
            if remaining <= 0:
                break
            
            disponible = (loc.stock_actual or 0) - (loc.stock_reservado or 0)
            take = min(remaining, disponible)
            if take <= 0:
                continue
            
            stock_reservado_antes = loc.stock_reservado or 0
            loc.stock_reservado = stock_reservado_antes + take
            remaining -= take
            total_reserved += take
            
            # Crear assignment para trazabilidad multi-ubicación
            assignment = OrderLineStockAssignment(
                order_line_id=line.id,
                product_location_id=loc.id,
                cantidad_reservada=take,
                cantidad_servida=0,
            )
            self.db.add(assignment)
            
            # Auditoría por cada ubicación
            movement = StockMovement(
                product_location_id=loc.id,
                product_id=line.product_reference_id,
                order_id=order.id,
                order_line_id=line.id,
                tipo="RESERVE",
                cantidad=take,
                stock_antes=loc.stock_actual or 0,
                stock_despues=loc.stock_actual or 0,
                notas=f"Reserva para orden {order.numero_orden}, "
                      f"línea #{line.id}, cantidad: {take}/{cantidad_needed}, "
                      f"ubicación: {loc.codigo_ubicacion}",
            )
            self.db.add(movement)
            
            logger.info(
                f"    ✓ Reserva: orden={order.numero_orden} línea={line.id} "
                f"producto={line.product_reference_id} ubicación={loc.codigo_ubicacion} "
                f"cantidad={take}/{cantidad_needed} "
                f"stock_reservado: {stock_reservado_antes}→{loc.stock_reservado}"
            )
        
        self.stats["lines_reserved"] += 1
        return total_reserved
    
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
    
    def _create_or_upgrade_replenishment_request(
        self,
        product_id: int,
        cantidad_needed: int,
        order: Order,
    ):
        """
        Delega la creación de solicitudes de reposición al servicio compartido.
        Actualiza las estadísticas del cron con el resultado.
        """
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
        
        result = create_or_upgrade_replenishment(
            db=self.db,
            product_id=product_id,
            requester_id=system_operator.id,
            priority="HIGH",
            order_id=order.id,
            cantidad_needed=cantidad_needed,
            status_id_list=self.status_id_list,
        )
        
        # Actualizar estadísticas del cron
        self.stats["replenishment_created"] += len(result.created_requests)
        self.stats["replenishment_upgraded"] += len(result.upgraded_requests)
        
        if result.status == "no_locations":
            self.stats["errors"] += 1
    
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
    
    Usa stock_assignments para saber exactamente cuánto descontar de cada ubicación.
    Fallback: si no hay assignments, usa product_location_id (compatibilidad).
    
    Returns:
        Lista de diccionarios con detalle de cada descuento realizado
    """
    deductions = []
    
    for line in order.order_lines:
        if not line.stock_reserved:
            continue
        
        assignments = (
            db.query(OrderLineStockAssignment)
            .filter_by(order_line_id=line.id)
            .all()
        )
        
        if assignments:
            # Multi-ubicación: descontar por assignment
            for assignment in assignments:
                location = db.get(ProductLocation, assignment.product_location_id)
                if not location:
                    logger.warning(
                        f"  [DEDUCT] Ubicación {assignment.product_location_id} no encontrada "
                        f"para línea #{line.id} de orden {order.numero_orden}"
                    )
                    continue
                
                cantidad_deducir = assignment.cantidad_servida or 0
                stock_antes = location.stock_actual or 0
                reservado_antes = location.stock_reservado or 0
                
                location.stock_actual = max(0, stock_antes - cantidad_deducir)
                location.stock_reservado = max(0, reservado_antes - assignment.cantidad_reservada)
                
                db.add(StockMovement(
                    product_location_id=location.id,
                    product_id=line.product_reference_id,
                    order_id=order.id,
                    order_line_id=line.id,
                    tipo="DEDUCT",
                    cantidad=-cantidad_deducir,
                    stock_antes=stock_antes,
                    stock_despues=location.stock_actual,
                    notas=f"Descuento por orden {order.numero_orden} completada (READY). "
                          f"Servida: {cantidad_deducir}, Reservada: {assignment.cantidad_reservada}, "
                          f"Ubicación: {location.codigo_ubicacion}",
                ))
                
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
                
                _check_release_location(db, location, order)
        else:
            # Fallback: compatibilidad con reservas sin assignments
            if not line.product_location_id:
                continue
            
            location = db.get(ProductLocation, line.product_location_id)
            if not location:
                continue
            
            cantidad_deducir = line.cantidad_servida or 0
            stock_antes = location.stock_actual or 0
            reservado_antes = location.stock_reservado or 0
            
            location.stock_actual = max(0, stock_antes - cantidad_deducir)
            location.stock_reservado = max(0, reservado_antes - line.cantidad_solicitada)
            
            db.add(StockMovement(
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
                      f"Ubicación: {location.codigo_ubicacion} (fallback sin assignments)",
            ))
            
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
            
            _check_release_location(db, location, order)
        
        line.stock_reserved = False
    
    return deductions


def _check_release_location(db: Session, location: ProductLocation, order: Order):
    """
    Si stock_actual=0 y stock_reservado=0, verificar si hay reposición pendiente.
    Si no hay → liberar la ubicación (product_id = NULL).
    """
    if (location.stock_actual or 0) == 0 and (location.stock_reservado or 0) == 0:
        pending_replenishment = db.query(ReplenishmentRequest).filter(
            ReplenishmentRequest.location_destino_id == location.id,
            ReplenishmentRequest.status.in_(["READY", "IN_PROGRESS"]),
        ).first()
        
        if not pending_replenishment:
            old_product_id = location.product_id
            old_code = location.codigo_ubicacion
            location.product_id = None
            location.stock_minimo = 0
            location.ultima_actualizacion_stock = datetime.utcnow()
            
            logger.info(
                f"  [RELEASE] Ubicación {old_code} liberada "
                f"(producto anterior: {old_product_id}, "
                f"orden: {order.numero_orden})"
            )


def release_stock_for_order(order: Order, db: Session) -> List[Dict]:
    """
    Libera stock_reservado al cancelar una orden.
    
    Usa stock_assignments para liberar de cada ubicación correctamente.
    Fallback: si no hay assignments, usa product_location_id (compatibilidad).
    
    Returns:
        Lista de diccionarios con detalle de cada liberación realizada
    """
    releases = []
    
    for line in order.order_lines:
        if not line.stock_reserved:
            continue
        
        assignments = (
            db.query(OrderLineStockAssignment)
            .filter_by(order_line_id=line.id)
            .all()
        )
        
        if assignments:
            for assignment in assignments:
                location = db.get(ProductLocation, assignment.product_location_id)
                if not location:
                    continue
                
                reservado_antes = location.stock_reservado or 0
                location.stock_reservado = max(0, reservado_antes - assignment.cantidad_reservada)
                
                db.add(StockMovement(
                    product_location_id=location.id,
                    product_id=line.product_reference_id,
                    order_id=order.id,
                    order_line_id=line.id,
                    tipo="RELEASE",
                    cantidad=assignment.cantidad_reservada,
                    stock_antes=location.stock_actual or 0,
                    stock_despues=location.stock_actual or 0,
                    notas=f"Liberación por cancelación de orden {order.numero_orden}. "
                          f"Cantidad liberada: {assignment.cantidad_reservada}, "
                          f"Ubicación: {location.codigo_ubicacion}",
                ))
                
                releases.append({
                    "order_line_id": line.id,
                    "product_location_id": location.id,
                    "ubicacion": location.codigo_ubicacion,
                    "cantidad_liberada": assignment.cantidad_reservada,
                    "reservado_antes": reservado_antes,
                    "reservado_despues": location.stock_reservado,
                })
                
                logger.info(
                    f"  [RELEASE] orden={order.numero_orden} línea={line.id} "
                    f"ubicación={location.codigo_ubicacion} "
                    f"reservado: {reservado_antes}→{location.stock_reservado}"
                )
        else:
            # Fallback: compatibilidad con reservas sin assignments
            if not line.product_location_id:
                continue
            
            location = db.get(ProductLocation, line.product_location_id)
            if not location:
                continue
            
            reservado_antes = location.stock_reservado or 0
            location.stock_reservado = max(0, reservado_antes - line.cantidad_solicitada)
            
            db.add(StockMovement(
                product_location_id=location.id,
                product_id=line.product_reference_id,
                order_id=order.id,
                order_line_id=line.id,
                tipo="RELEASE",
                cantidad=line.cantidad_solicitada,
                stock_antes=location.stock_actual or 0,
                stock_despues=location.stock_actual or 0,
                notas=f"Liberación por cancelación de orden {order.numero_orden}. "
                      f"Cantidad liberada: {line.cantidad_solicitada}, "
                      f"Ubicación: {location.codigo_ubicacion} (fallback sin assignments)",
            ))
            
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
        
        line.stock_reserved = False
    
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
