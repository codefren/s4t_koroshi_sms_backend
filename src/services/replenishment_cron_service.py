"""
Replenishment Cron Service

Servicio programado que ejecuta periódicamente dos tareas:
1. Actualizar solicitudes WAITING_STOCK → READY cuando hay stock disponible
   en el almacén de reposición (ID=1).
2. Crear solicitudes automáticas cuando productos en el almacén de picking (ID=2)
   tienen stock por debajo del mínimo.

Arquitectura:
    - Se ejecuta cada N minutos via APScheduler
    - Usa sesión de BD independiente por ejecución
    - Broadcast WebSocket para alertar operadores conectados
    - Operador SYSTEM como requester de solicitudes automáticas
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from src.adapters.secondary.database.config import (
    SessionLocal,
    ALMACEN_REPOSICION_ID as REPLENISHMENT_WAREHOUSE_ID,  # Almacén origen (reposición)
    ALMACEN_PICKING_ID as PICKING_WAREHOUSE_ID,  # Almacén destino (picking)
    CRON_INTERVAL_MINUTES,
    SYSTEM_OPERATOR_CODE
)
from src.adapters.secondary.database.orm import (
    ProductLocation,
    ProductReference,
    ReplenishmentRequest,
    Operator,
)
from src.adapters.primary.websocket.manager import manager

logger = logging.getLogger(__name__)


class ReplenishmentCronService:
    """
    Servicio cron para gestión automática de reposiciones.
    
    Responsabilidades:
        - Promover solicitudes WAITING_STOCK → READY
        - Crear solicitudes automáticas por stock bajo
        - Broadcast alertas a operadores conectados
        - Logging detallado de operaciones
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session or SessionLocal()
        self.owns_session = db_session is None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Estadísticas de ejecución
        self.stats = {
            "promoted_to_ready": 0,
            "requests_created": 0,
            "requests_created_waiting": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None,
        }
    
    def run(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        """
        Ejecuta el ciclo completo del cron.
        
        Args:
            loop: Event loop de asyncio para broadcast WebSocket
        """
        self.loop = loop
        self.stats["start_time"] = datetime.utcnow()
        logger.info("🔄 [CRON] Iniciando ciclo de reposición automática")
        
        try:
            # Tarea 1: Promover WAITING_STOCK → READY
            self._update_waiting_stock_requests()
            
            # Tarea 2: Crear solicitudes por stock bajo en picking
            self._create_low_stock_requests()
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"❌ [CRON] Error fatal: {e}", exc_info=True)
            self.db.rollback()
            self.stats["errors"] += 1
        finally:
            if self.owns_session:
                self.db.close()
        
        self._log_stats()
        return self.stats
    
    # =========================================================================
    # TAREA 1: Promover WAITING_STOCK → READY
    # =========================================================================
    
    def _update_waiting_stock_requests(self):
        """
        Recorre todas las solicitudes en WAITING_STOCK y busca stock
        disponible en el almacén de reposición (ID=1).
        
        Si encuentra stock, asigna location_origen_id y cambia a READY.
        """
        waiting_requests = self.db.query(ReplenishmentRequest).filter(
            ReplenishmentRequest.status == "WAITING_STOCK"
        ).all()
        
        if not waiting_requests:
            logger.info("  [T1] No hay solicitudes en WAITING_STOCK")
            return
        
        logger.info(f"  [T1] Procesando {len(waiting_requests)} solicitudes WAITING_STOCK")
        
        for request in waiting_requests:
            try:
                self._try_promote_request(request)
            except Exception as e:
                logger.error(
                    f"  [T1] Error procesando solicitud #{request.id}: {e}",
                    exc_info=True
                )
                self.stats["errors"] += 1
    
    def _try_promote_request(self, request: ReplenishmentRequest):
        """
        Intenta promover una solicitud de WAITING_STOCK a READY.
        
        Busca stock en almacén de reposición (ID=1) para el producto.
        """
        origin_location = self._find_origin_in_replenishment_warehouse(
            request.product_id
        )
        
        if not origin_location:
            return  # Sin stock disponible, sigue en WAITING_STOCK
        
        # Asignar origen y cambiar estado
        request.location_origen_id = origin_location.id
        request.status = "READY"
        
        # Recalcular prioridad solo si es NORMAL (URGENT y HIGH se mantienen)
        if request.priority == "NORMAL":
            destination = self.db.query(ProductLocation).filter_by(
                id=request.location_destino_id
            ).first()
            if destination:
                request.priority = self._calculate_priority(destination)
        
        request.updated_at = datetime.utcnow()
        
        logger.info(
            f"  [T1] ✅ Solicitud #{request.id} promovida a READY "
            f"(origen: ubicación {origin_location.id}, "
            f"stock: {origin_location.stock_actual})"
        )
        self.stats["promoted_to_ready"] += 1
        
        # Broadcast alerta a operadores conectados
        self._broadcast_alert(request, origin_location)
    
    # =========================================================================
    # TAREA 2: Crear solicitudes automáticas por stock bajo en picking
    # =========================================================================
    
    def _create_low_stock_requests(self):
        """
        Escanea ubicaciones activas en el almacén de picking (ID=2) con
        stock por debajo del mínimo y crea solicitudes automáticas.
        """
        low_stock_locations = self.db.query(ProductLocation).filter(
            ProductLocation.almacen_id == PICKING_WAREHOUSE_ID,
            ProductLocation.activa == True,
            ProductLocation.stock_actual < ProductLocation.stock_minimo,
            ProductLocation.stock_minimo > 0,
        ).all()
        
        if not low_stock_locations:
            logger.info("  [T2] No hay ubicaciones con stock bajo en picking")
            return
        
        logger.info(
            f"  [T2] Encontradas {len(low_stock_locations)} ubicaciones "
            f"con stock bajo en almacén de picking"
        )
        
        # Obtener operador SYSTEM
        system_operator = self.db.query(Operator).filter(
            Operator.codigo == SYSTEM_OPERATOR_CODE
        ).first()
        
        if not system_operator:
            logger.error(
                f"  [T2] ❌ Operador '{SYSTEM_OPERATOR_CODE}' no encontrado. "
                f"Ejecute: migrations/insert_system_operator.sql"
            )
            self.stats["errors"] += 1
            return
        
        for location in low_stock_locations:
            try:
                self._try_create_request(location, system_operator)
            except Exception as e:
                logger.error(
                    f"  [T2] Error creando solicitud para ubicación "
                    f"{location.id} (producto {location.product_id}): {e}",
                    exc_info=True
                )
                self.stats["errors"] += 1
    
    def _try_create_request(
        self,
        picking_location: ProductLocation,
        system_operator: Operator,
    ):
        """
        Crea una solicitud de reposición si no existe una pendiente
        para el mismo producto + ubicación destino.
        """
        # Verificar duplicados
        existing = self.db.query(ReplenishmentRequest).filter(
            ReplenishmentRequest.product_id == picking_location.product_id,
            ReplenishmentRequest.location_destino_id == picking_location.id,
            ReplenishmentRequest.status.in_(["WAITING_STOCK", "READY", "IN_PROGRESS"]),
        ).first()
        
        if existing:
            return  # Ya existe solicitud pendiente
        
        # Buscar origen en almacén de reposición
        origin_location = self._find_origin_in_replenishment_warehouse(
            picking_location.product_id
        )
        
        # Calcular déficit
        deficit = max(
            picking_location.stock_minimo - picking_location.stock_actual, 1
        )
        
        # Determinar estado
        if origin_location:
            status = "READY"
            origin_id = origin_location.id
        else:
            status = "WAITING_STOCK"
            origin_id = None
        
        priority = self._calculate_priority(picking_location)
        
        # Crear solicitud
        new_request = ReplenishmentRequest(
            location_origen_id=origin_id,
            location_destino_id=picking_location.id,
            product_id=picking_location.product_id,
            requested_quantity=deficit,
            status=status,
            priority=priority,
            requester_id=system_operator.id,
            requested_at=datetime.utcnow(),
        )
        
        self.db.add(new_request)
        self.db.flush()  # Para obtener el ID
        
        logger.info(
            f"  [T2] ✅ Solicitud #{new_request.id} creada "
            f"(producto: {picking_location.product_id}, "
            f"destino: {picking_location.codigo_ubicacion}, "
            f"estado: {status}, prioridad: {priority}, "
            f"cantidad: {deficit})"
        )
        
        if status == "READY":
            self.stats["requests_created"] += 1
            self._broadcast_alert(new_request, origin_location)
        else:
            self.stats["requests_created_waiting"] += 1
    
    # =========================================================================
    # UTILIDADES
    # =========================================================================
    
    def _find_origin_in_replenishment_warehouse(
        self, product_id: int
    ) -> Optional[ProductLocation]:
        """
        Busca la ubicación con mayor stock para un producto
        en el almacén de reposición (ID=1).
        
        Returns:
            ProductLocation con stock > 0 o None
        """
        origin = self.db.query(ProductLocation).filter(
            ProductLocation.product_id == product_id,
            ProductLocation.almacen_id == REPLENISHMENT_WAREHOUSE_ID,
            ProductLocation.activa == True,
            ProductLocation.stock_actual > 0,
        ).order_by(
            ProductLocation.stock_actual.desc()
        ).first()
        
        return origin
    
    def _calculate_priority(self, destination: ProductLocation) -> str:
        """
        Siempre que se crea una solicitud automatica, se le da prioridad NORMAL.
        """
        return "NORMAL"
    
    def _broadcast_alert(
        self,
        request: ReplenishmentRequest,
        origin_location: Optional[ProductLocation],
    ):
        """
        Envía new_replenishment_alert a operadores conectados via WebSocket.
        Se ejecuta de forma segura desde hilo del scheduler.
        """
        if not self.loop:
            return
        
        # Obtener datos del producto
        product_name = "Producto"
        prod = self.db.query(ProductReference).filter_by(
            id=request.product_id
        ).first()
        if prod:
            product_name = prod.nombre_producto
        
        # Obtener código de ubicación destino
        destination = self.db.query(ProductLocation).filter_by(
            id=request.location_destino_id
        ).first()
        destination_code = destination.codigo_ubicacion if destination else "N/A"
        
        origin_code = None
        if origin_location:
            origin_code = origin_location.codigo_ubicacion
        
        message = {
            "action": "new_replenishment_alert",
            "data": {
                "request_id": request.id,
                "status": request.status,
                "priority": request.priority,
                "product_name": product_name,
                "product_id": request.product_id,
                "destination_code": destination_code,
                "origin_code": origin_code,
                "requested_quantity": request.requested_quantity,
                "source": "cron_automatic",
                "timestamp": datetime.utcnow().isoformat(),
            },
        }
        
        try:
            future = asyncio.run_coroutine_threadsafe(
                manager.broadcast(message), self.loop
            )
            future.result(timeout=5)
        except Exception as e:
            logger.warning(f"  [BROADCAST] Error enviando alerta: {e}")
    
    def _log_stats(self):
        """Imprime estadísticas de la ejecución."""
        self.stats["end_time"] = datetime.utcnow()
        duration = (
            self.stats["end_time"] - self.stats["start_time"]
        ).total_seconds()
        
        logger.info("=" * 60)
        logger.info("🔄 [CRON] CICLO COMPLETADO")
        logger.info(f"   Promovidas WAITING→READY: {self.stats['promoted_to_ready']}")
        logger.info(f"   Solicitudes creadas (READY): {self.stats['requests_created']}")
        logger.info(f"   Solicitudes creadas (WAITING): {self.stats['requests_created_waiting']}")
        logger.info(f"   Errores: {self.stats['errors']}")
        logger.info(f"   Duración: {duration:.2f}s")
        logger.info("=" * 60)


def _run_replenishment_cron(loop: asyncio.AbstractEventLoop):
    """
    Función ejecutada por APScheduler en cada intervalo.
    Crea una instancia fresca del servicio con su propia sesión de BD.
    """
    service = ReplenishmentCronService()
    service.run(loop=loop)


def start_replenishment_scheduler():
    """
    Configura e inicia APScheduler con el cron de reposición.
    
    Returns:
        BackgroundScheduler instance (para shutdown en lifespan)
    """
    from apscheduler.schedulers.background import BackgroundScheduler
    
    loop = asyncio.get_event_loop()
    
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _run_replenishment_cron,
        "interval",
        minutes=CRON_INTERVAL_MINUTES,
        args=[loop],
        id="replenishment_cron",
        name="Replenishment Stock Check",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.start()
    
    logger.info(
        f"⏰ [CRON] Scheduler iniciado — cada {CRON_INTERVAL_MINUTES} minutos"
    )
    
    return scheduler
