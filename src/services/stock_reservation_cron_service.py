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
from sqlalchemy.orm import Session, selectinload

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
        # db_session se acepta para tests; en producción se crea en run()
        self._external_session = db_session

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
        La sesión se abre y cierra aquí para garantizar que siempre se libere.
        """
        self.stats["start_time"] = datetime.utcnow()
        logger.info("📦 [STOCK-CRON] Iniciando ciclo de reserva de stock")

        # Usar sesión externa (tests) o crear una nueva y cerrarla aquí
        self.db = self._external_session or SessionLocal()
        owns_session = self._external_session is None

        try:
            self._reserve_stock_for_orders()
            self.db.commit()

        except Exception as e:
            logger.error(f"❌ [STOCK-CRON] Error fatal: {e}", exc_info=True)
            self.db.rollback()
            self.stats["errors"] += 1
        finally:
            if owns_session:
                self.db.close()

        self._log_stats()
        return self.stats
    
    def _reserve_stock_for_orders(self):
        """
        Busca órdenes en estados PENDING/ASSIGNED y reserva stock para líneas
        que aún no tienen reserva completa.

        Optimización: pre-carga assignments y ubicaciones en 3 queries totales
        en lugar de una query por línea (evita N+1).
        """
        # Query 1: estados objetivo
        status_ids = self.db.query(OrderStatus.id).filter(
            OrderStatus.codigo.in_(RESERVATION_STATUS_CODES)
        ).all()
        self.status_id_list = [s[0] for s in status_ids]

        if not self.status_id_list:
            logger.warning("  [STOCK-CRON] No se encontraron estados de reserva en BD")
            return

        # Query 2: órdenes + líneas (selectinload = 2 SELECTs planos, sin subqueries gigantes)
        orders = (
            self.db.query(Order)
            .filter(
                Order.status_id.in_(self.status_id_list),
                Order.almacen_id == ALMACEN_PICKING_ID,
            )
            .options(selectinload(Order.order_lines))
            .all()
        )

        if not orders:
            logger.info("  [STOCK-CRON] No hay órdenes pendientes de reserva")
            return

        logger.info(f"  [STOCK-CRON] Procesando {len(orders)} órdenes en {RESERVATION_STATUS_CODES}")

        # Subquery de líneas activas — evita pasar miles de IDs como parámetros (límite pyodbc ~2100)
        active_lines_sq = (
            self.db.query(OrderLine.id)
            .join(Order, OrderLine.order_id == Order.id)
            .filter(
                Order.status_id.in_(self.status_id_list),
                Order.almacen_id == ALMACEN_PICKING_ID,
            )
            .subquery()
        )

        # Subquery de productos activos
        active_products_sq = (
            self.db.query(OrderLine.product_reference_id)
            .join(Order, OrderLine.order_id == Order.id)
            .filter(
                Order.status_id.in_(self.status_id_list),
                Order.almacen_id == ALMACEN_PICKING_ID,
                OrderLine.product_reference_id.isnot(None),
            )
            .distinct()
            .subquery()
        )

        # Query 3: assignments via subquery (sin IN con miles de parámetros)
        assignments_rows = (
            self.db.query(OrderLineStockAssignment)
            .filter(OrderLineStockAssignment.order_line_id.in_(active_lines_sq))
            .all()
        )
        # Índice: line_id → suma de cantidad_reservada
        reserved_by_line: dict[int, int] = {}
        for a in assignments_rows:
            reserved_by_line[a.order_line_id] = (
                reserved_by_line.get(a.order_line_id, 0) + a.cantidad_reservada
            )

        # Query 4: ubicaciones picking disponibles via subquery
        available_stock_expr = (
            ProductLocation.stock_actual - func.coalesce(ProductLocation.stock_reservado, 0)
        )
        location_rows = (
            self.db.query(ProductLocation)
            .filter(
                ProductLocation.product_id.in_(active_products_sq),
                ProductLocation.almacen_id == ALMACEN_PICKING_ID,
                ProductLocation.activa == True,
                available_stock_expr > 0,
            )
            .order_by(ProductLocation.product_id, available_stock_expr.desc())
            .all()
        )
        # Índice: product_id → lista de ubicaciones ordenadas por stock desc
        locations_by_product: dict[int, list] = {}
        for loc in location_rows:
            locations_by_product.setdefault(loc.product_id, []).append(loc)

        # Procesar cada orden usando los datos ya cargados en memoria
        for order in orders:
            try:
                self._reserve_order_lines(order, reserved_by_line, locations_by_product)
                self.stats["orders_processed"] += 1
            except Exception as e:
                logger.error(
                    f"  [STOCK-CRON] Error en orden #{order.id} ({order.numero_orden}): {e}",
                    exc_info=True
                )
                self.stats["errors"] += 1

    def _reserve_order_lines(
        self,
        order: Order,
        reserved_by_line: dict,
        locations_by_product: dict,
    ):
        """
        Reserva stock para cada línea de la orden que no tenga reserva completa.

        Recibe los datos de assignments y ubicaciones ya pre-cargados en memoria
        para evitar queries adicionales por línea.
        """
        for line in order.order_lines:
            # Saltar líneas sin producto asociado
            if not line.product_reference_id:
                self.stats["lines_skipped_no_product"] += 1
                continue

            # Cuánto ya está reservado (de la pre-carga en memoria)
            total_already_reserved = reserved_by_line.get(line.id, 0)

            cantidad_needed = line.cantidad_solicitada - total_already_reserved
            if cantidad_needed <= 0:
                continue  # Ya completamente reservada

            # Ubicaciones disponibles (de la pre-carga en memoria)
            locations = locations_by_product.get(line.product_reference_id, [])

            total_available = sum(
                (loc.stock_actual or 0) - (loc.stock_reservado or 0)
                for loc in locations
            )

            if total_available > 0:
                reserved = self._reserve_line_multi(order, line, locations, cantidad_needed)

                deficit = cantidad_needed - reserved
                if deficit > 0:
                    self._create_or_upgrade_replenishment_request(
                        line.product_reference_id, deficit, order
                    )
            else:
                self.stats["lines_skipped_no_stock"] += 1
                self._create_or_upgrade_replenishment_request(
                    line.product_reference_id, cantidad_needed, order
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

            # No liberar si hay otros productos activos en la misma coordenada física.
            # Una ubicación puede tener múltiples productos; el slot no queda "libre"
            # solo porque uno de ellos se agotó.
            other_products_same_slot = db.query(ProductLocation).filter(
                ProductLocation.almacen_id == location.almacen_id,
                ProductLocation.pasillo == location.pasillo,
                ProductLocation.lado == location.lado,
                ProductLocation.ubicacion == location.ubicacion,
                ProductLocation.altura == location.altura,
                ProductLocation.product_id.isnot(None),
                ProductLocation.id != location.id,
            ).first()

            if other_products_same_slot:
                logger.info(
                    f"  [RELEASE SKIP] Ubicación {old_code} no liberada: "
                    f"hay otros productos en la misma coordenada física "
                    f"(producto agotado: {old_product_id}, orden: {order.numero_orden})"
                )
            else:
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

    Usa un bloqueo en BD para evitar ejecuciones paralelas cuando la app
    corre con múltiples workers de uvicorn (cada worker tiene su propio
    scheduler, pero solo uno debe ejecutar el cron a la vez).
    """
    from sqlalchemy import text

    db = SessionLocal()
    try:
        # sp_getapplock usa RETURN value (no result set), hay que capturarlo con DECLARE.
        # Devuelve 0 = lock adquirido, -1/-2/-3 = timeout/cancelado/error (otro worker activo).
        row = db.execute(
            text(
                "DECLARE @ret INT; "
                "EXEC @ret = sp_getapplock "
                "  @Resource = 'stock_reservation_cron', "
                "  @LockMode = 'Exclusive', "
                "  @LockOwner = 'Session', "
                "  @LockTimeout = 0; "
                "SELECT @ret AS lock_result;"
            )
        ).fetchone()

        lock_result = row[0] if row is not None else -1
        if lock_result < 0:
            logger.info("⏭️  [STOCK-CRON] Otro worker ya está ejecutando el cron — saltando")
            return

        # Lock adquirido: ejecutar el servicio con esta misma sesión
        service = StockReservationCronService(db_session=db)
        service.run()
        # No llamar sp_releaseapplock explícitamente: después de service.run()
        # SQLAlchemy puede haber devuelto la conexión al pool (distinto SPID),
        # lo que causaría error 1223. El lock @LockOwner='Session' se libera
        # automáticamente cuando db.close() cierra la conexión en el finally.

    except Exception as e:
        logger.error(f"❌ [STOCK-CRON] Error en launcher: {e}", exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


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
        coalesce=True,           # Si se acumulan disparos perdidos, ejecutar solo una vez
        misfire_grace_time=60,   # Tolerar hasta 60s de retraso antes de cancelar el disparo
    )
    scheduler.start()
    
    logger.info(
        f"⏰ [STOCK-CRON] Scheduler iniciado — cada {CRON_INTERVAL_MINUTES} minutos"
    )
    
    return scheduler
