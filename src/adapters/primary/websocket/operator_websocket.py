"""
WebSocket endpoint para operarios de PDA.

Maneja la conexión WebSocket y el escaneo de productos en tiempo real.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import Dict, Any
from datetime import datetime
from sqlalchemy import case

from .manager import manager
from src.adapters.secondary.database.orm import Operator, Order, OrderLine, OrderLineBoxDistribution, PackingBox, ReplenishmentRequest, ProductLocation, StockMovement
from src.adapters.secondary.database.config import ALMACEN_PICKING_ID, ALMACEN_REPOSICION_ID, SessionLocal


router = APIRouter()


@router.websocket("/ws/operators/{codigo_operario}")
async def operator_websocket_endpoint(
    websocket: WebSocket,
    codigo_operario: str
):
    """
    WebSocket endpoint para operarios de PDA.
    
    Conecta al operario y escucha mensajes de escaneo de productos.
    
    Mensaje esperado:
    {
        "action": "scan_product",
        "data": {
            "order_id": 35,                    // Opción 1: ID numérico
            "numero_orden": "ORD1001",         // Opción 2: Número de orden
            "ean": "8445962763983",
            "ubicacion": "A-IZQ-12-H2"         // opcional
        }
    }
    
    Args:
        websocket: Conexión WebSocket
        codigo_operario: Código del operario que se conecta (ej: OP001)
    """
    
    # 1. Validar que el operario existe y está activo (usar sesión temporal)
    from ...secondary.database.config import SessionLocal
    db = SessionLocal()
    try:
        operator = db.query(Operator).filter_by(codigo=codigo_operario).first()
        
        if not operator:
            await websocket.close(code=4004, reason="Operario no encontrado")
            return
        
        if not operator.activo:
            await websocket.close(code=4003, reason="Operario inactivo")
            return
        
        operator_id = operator.id
        operator_name = operator.nombre
    finally:
        db.close()
    
    # 2. Conectar al operario
    await manager.connect(websocket, codigo_operario)
    
    # 3. Enviar confirmación de conexión
    await manager.send_message(codigo_operario, {
        "action": "connected",
        "data": {
            "operator_id": operator_id,
            "codigo_operario": codigo_operario,
            "operator_name": operator_name,
            "message": f"✅ Conectado como {operator_name}"
        }
    })
    
    try:
        # 4. Loop principal: escuchar mensajes
        while True:
            # Recibir mensaje del cliente
            data = await websocket.receive_json()
            
            action = data.get("action")
            
            # Procesar según el tipo de acción
            if action == "scan_product":
                await handle_scan_product(
                    websocket, 
                    operator_id,  # ID numérico para validaciones
                    codigo_operario,  # Código para respuestas
                    data.get("data", {})
                )
            elif action == "request_replenishment":
                await handle_request_replenishment(
                    websocket,
                    operator_id,
                    codigo_operario,
                    data.get("data", {})
                )
            elif action == "request_replenishment_urgent":
                await handle_request_replenishment_urgent(
                    websocket,
                    operator_id,
                    codigo_operario,
                    data.get("data", {})
                )
            elif action == "get_next_replenishment":
                await handle_get_next_replenishment(
                    websocket,
                    operator_id,
                    codigo_operario,
                    data.get("data", {})
                )
            elif action == "scan_origin_location":
                await handle_scan_origin_location(
                    websocket,
                    operator_id,
                    codigo_operario,
                    data.get("data", {})
                )
            elif action == "scan_destination_location":
                await handle_scan_destination_location(
                    websocket,
                    operator_id,
                    codigo_operario,
                    data.get("data", {})
                )
            elif action == "confirm_replenishment":
                await handle_confirm_replenishment(
                    websocket,
                    operator_id,
                    codigo_operario,
                    data.get("data", {})
                )
            elif action == "move_stock_scan_product":
                await handle_move_stock_scan_product(
                    websocket,
                    operator_id,
                    codigo_operario,
                    data.get("data", {})
                )
            elif action == "move_stock_scan_origin":
                await handle_move_stock_scan_origin(
                    websocket,
                    operator_id,
                    codigo_operario,
                    data.get("data", {})
                )
            elif action == "move_stock_scan_destination":
                await handle_move_stock_scan_destination(
                    websocket,
                    operator_id,
                    codigo_operario,
                    data.get("data", {})
                )
            elif action == "move_stock_confirm":
                await handle_move_stock_confirm(
                    websocket,
                    operator_id,
                    codigo_operario,
                    data.get("data", {})
                )
            else:
                await send_error(
                    websocket, 
                    "UNKNOWN_ACTION",
                    f"Acción desconocida: {action}"
                )
    
    except WebSocketDisconnect:
        manager.disconnect(codigo_operario)
        print(f"Operario {codigo_operario} ({operator.nombre}) desconectado")
    
    except Exception as e:
        print(f"Error en WebSocket de operario {codigo_operario}: {e}")
        manager.disconnect(codigo_operario)
        try:
            await websocket.close(code=1011, reason="Error interno del servidor")
        except:
            pass


async def handle_scan_product(
    websocket: WebSocket,
    operator_id: int,
    codigo_operario: str,
    data: dict
):
    """
    Procesa el escaneo de un producto.
    
    Incrementa la cantidad servida en +1 para el producto escaneado
    y retorna el progreso actualizado.
    
    Args:
        websocket: Conexión WebSocket
        operator_id: ID numérico del operario (para validaciones)
        codigo_operario: Código del operario (para respuestas)
        data: Datos del escaneo (order_id o numero_orden, ean, ubicacion)
    """
    # Crear sesión de base de datos para esta operación
    from ...secondary.database.config import SessionLocal
    db = SessionLocal()
    
    try:
        # Aceptar order_id, numero_orden u order_number para flexibilidad
        order_id = data.get("order_id")
        numero_orden = data.get("numero_orden") or data.get("order_number")  # Aceptar ambos nombres
        ean = data.get("ean")
        ubicacion = data.get("ubicacion")
        
        # Validaciones de entrada
        if not order_id and not numero_orden:
            await send_error(websocket, "MISSING_ORDER_NUMBER", "Falta el ID o número de orden")
            return
        
        if not ean:
            await send_error(websocket, "MISSING_EAN", "Falta el código EAN")
            return
        
        # 1. Validar que la orden existe y está asignada al operario
        if order_id:
            order = db.query(Order).filter_by(id=order_id).first()
        else:
            order = db.query(Order).filter_by(numero_orden=numero_orden).first()
        
        if not order:
            await send_error(websocket, "ORDER_NOT_FOUND", "Orden no encontrada")
            return
        
        if order.operator_id != operator_id:
            await send_error(
                websocket, 
                "ORDER_NOT_ASSIGNED",
                "Esta orden no está asignada a ti"
            )
            return
        
        # 2. Validar que la orden está en estado IN_PICKING
        if order.status.codigo != "IN_PICKING":
            await send_error(
                websocket,
                "ORDER_WRONG_STATUS",
                f"La orden está en estado {order.status.codigo}. Debe estar en IN_PICKING"
            )
            return
        
        # 3. Buscar el producto por EAN en las líneas de la orden
        line = db.query(OrderLine).filter(
            OrderLine.order_id == order.id,
            OrderLine.ean == ean
        ).first()
        
        if not line:
            await send_error(
                websocket,
                "EAN_NOT_IN_ORDER",
                f"El EAN {ean} no pertenece a esta orden"
            )
            return
        
        # 4. Validar que no se exceda la cantidad solicitada
        if line.cantidad_servida >= line.cantidad_solicitada:
            await send_error(
                websocket,
                "MAX_QUANTITY_REACHED",
                f"Ya se completó la cantidad solicitada ({line.cantidad_solicitada})"
            )
            return
        
        # 5. Incrementar cantidad servida en +1
        line.cantidad_servida += 1
        
        # 5.1. EMPAQUE AUTOMÁTICO en caja activa usando OrderLineBoxDistribution
        if order.caja_activa_id:
            # Buscar distribución existente para esta línea en esta caja
            distribution = db.query(OrderLineBoxDistribution).filter(
                OrderLineBoxDistribution.order_line_id == line.id,
                OrderLineBoxDistribution.packing_box_id == order.caja_activa_id
            ).first()
            
            if distribution:
                # Ya existe, incrementar cantidad
                distribution.quantity_in_box += 1
            else:
                # Crear nueva distribución
                distribution = OrderLineBoxDistribution(
                    order_line_id=line.id,
                    packing_box_id=order.caja_activa_id,
                    quantity_in_box=1,
                    fecha_empacado=datetime.utcnow()
                )
                db.add(distribution)
            
            # Actualizar contador de items en la caja
            box = db.query(PackingBox).filter(
                PackingBox.id == order.caja_activa_id
            ).first()
            if box:
                box.total_items += 1
            
            # Marcar la línea como empacada si se completó
            if line.cantidad_servida >= line.cantidad_solicitada:
                line.packing_box_id = order.caja_activa_id
                line.fecha_empacado = datetime.utcnow()
        
        # 6. Actualizar estado de la línea
        if line.cantidad_servida == line.cantidad_solicitada:
            line.estado = "COMPLETED"
        elif line.cantidad_servida > 0:
            line.estado = "PARTIAL"
        
        # 7. Incrementar contador de items completados de la orden
        # Incrementamos directamente en lugar de recalcular con SUM para evitar race conditions
        order.items_completados += 1
        
        # 8. Guardar cambios
        db.commit()
        
        # 9. Calcular progreso
        progreso_linea = (
            (line.cantidad_servida / line.cantidad_solicitada * 100)
            if line.cantidad_solicitada > 0 else 0
        )
        
        progreso_orden = (
            (order.items_completados / order.total_items * 100)
            if order.total_items > 0 else 0
        )
        
        # 10. Obtener info del producto
        producto_nombre = "Producto"
        if line.product_reference:
            producto_nombre = line.product_reference.nombre_producto
            if line.product_reference.nombre_color:
                producto_nombre += f" {line.product_reference.nombre_color}"
            if line.product_reference.talla:
                producto_nombre += f" {line.product_reference.talla}"
        
        # 11. Enviar confirmación al operario
        await manager.send_message(codigo_operario, {
            "action": "scan_confirmed",
            "data": {
                "line_id": line.id,
                "producto": producto_nombre,
                "ean": ean,
                "ubicacion": ubicacion,
                "cantidad_actual": line.cantidad_servida,
                "cantidad_solicitada": line.cantidad_solicitada,
                "cantidad_pendiente": line.cantidad_solicitada - line.cantidad_servida,
                "progreso_linea": round(progreso_linea, 2),
                "estado_linea": line.estado,
                "progreso_orden": {
                    "order_id": order.id,
                    "numero_orden": order.numero_orden,
                    "total_items": order.total_items,
                    "items_completados": order.items_completados,
                    "progreso_porcentaje": round(progreso_orden, 2)
                },
                "mensaje": "✅ Producto escaneado correctamente",
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        
        print(f"✅ Operario {codigo_operario} escaneó EAN {ean} - Orden {order.numero_orden} - Progreso: {round(progreso_orden, 2)}%")
    
    except Exception as e:
        print(f"❌ Error en handle_scan_product: {e}")
        import traceback
        traceback.print_exc()
        await send_error(websocket, "INTERNAL_ERROR", f"Error interno: {str(e)}")
        db.rollback()
    finally:
        # Siempre cerrar la sesión
        db.close()


async def handle_request_replenishment(
    websocket: WebSocket,
    operator_id: int,
    codigo_operario: str,
    data: dict
):
    """
    Procesa solicitud de reposición automática desde PDA.
    
    Cuando el operador encuentra una ubicación sin stock durante el picking,
    presiona "Siguiente SKU" y se crea automáticamente una solicitud de reposición.
    
    Args:
        websocket: Conexión WebSocket
        operator_id: ID del operario solicitante
        codigo_operario: Código del operario (para respuestas)
        data: Datos de la solicitud (location_destino_id, product_id, order_id opcional)
    """
    from ...secondary.database.config import SessionLocal
    db = SessionLocal()
    
    try:
        # Validaciones de entrada
        location_destino_id = data.get("location_destino_id")
        product_id = data.get("product_id")
        order_id = data.get("order_id")
        requested_quantity = data.get("requested_quantity")
        
        if not location_destino_id:
            await send_error(websocket, "MISSING_LOCATION", "Falta el ID de ubicación destino")
            return
        
        if not product_id:
            await send_error(websocket, "MISSING_PRODUCT", "Falta el ID de producto")
            return
        
        # 1. Validar ubicación destino existe
        location_destino = db.query(ProductLocation).filter_by(id=location_destino_id).first()
        if not location_destino:
            await send_error(websocket, "LOCATION_NOT_FOUND", "Ubicación destino no encontrada")
            return
        
        # 2. Buscar ubicación con stock disponible en zona de reposición
        # Busca en el almacén de reposición (ALMACEN_REPOSICION_ID)
        location_origen = None
        available_locations = db.query(ProductLocation).filter(
            ProductLocation.product_id == product_id,
            ProductLocation.almacen_id == ALMACEN_REPOSICION_ID,
            ProductLocation.activa == True,
            ProductLocation.stock_actual > 0
        ).order_by(
            ProductLocation.prioridad.asc(),      # Prioridad alta primero
            ProductLocation.stock_actual.desc()   # Mayor stock primero
        ).all()
        
        if available_locations:
            location_origen = available_locations[0]
        
        # 3. Calcular cantidad solicitada
        if not requested_quantity:
            # Calcular déficit: stock_minimo - stock_actual
            deficit = max(location_destino.stock_minimo - location_destino.stock_actual, 1)
            requested_quantity = deficit
        
        # 4. Determinar estado y prioridad
        if location_origen:
            status = "READY"  # Hay stock disponible
            origin_id = location_origen.id
        else:
            status = "WAITING_STOCK"  # No hay stock disponible
            origin_id = None
        
        # Calcular prioridad
        if location_destino.stock_actual == 0:
            priority = "URGENT"
        elif location_destino.stock_actual < (location_destino.stock_minimo * 0.5):
            priority = "HIGH"
        else:
            priority = "NORMAL"
        
        # 5. Verificar si ya existe solicitud pendiente para este producto/ubicación
        existing_request = db.query(ReplenishmentRequest).filter(
            ReplenishmentRequest.product_id == product_id,
            ReplenishmentRequest.location_destino_id == location_destino_id,
            ReplenishmentRequest.status.in_(["WAITING_STOCK", "READY", "IN_PROGRESS"])
        ).first()
        
        if existing_request:
            await manager.send_message(codigo_operario, {
                "action": "replenishment_duplicate",
                "data": {
                    "request_id": existing_request.id,
                    "status": existing_request.status,
                    "message": "⚠️ Ya existe una solicitud de reposición pendiente para este producto en esta ubicación",
                    "timestamp": datetime.utcnow().isoformat()
                }
            })
            return
        
        # 6. Crear solicitud de reposición
        replenishment_request = ReplenishmentRequest(
            location_origen_id=origin_id,
            location_destino_id=location_destino_id,
            product_id=product_id,
            requested_quantity=requested_quantity,
            status=status,
            priority=priority,
            requester_id=operator_id,
            order_id=order_id,
            requested_at=datetime.utcnow()
        )
        
        db.add(replenishment_request)
        db.commit()
        db.refresh(replenishment_request)
        
        # 7. Preparar respuesta
        origin_code = None
        origin_stock = None
        if location_origen:
            origin_code = location_origen.codigo_ubicacion
            origin_stock = location_origen.stock_actual
        
        # 8. Enviar confirmación al operario
        await manager.send_message(codigo_operario, {
            "action": "replenishment_created",
            "data": {
                "request_id": replenishment_request.id,
                "status": status,
                "priority": priority,
                "requested_quantity": requested_quantity,
                "location_destination": {
                    "id": location_destino.id,
                    "code": location_destino.codigo_ubicacion,
                    "stock_actual": location_destino.stock_actual
                },
                "location_origin": {
                    "id": origin_id,
                    "code": origin_code,
                    "stock_available": origin_stock
                } if location_origen else None,
                "message": "✅ Solicitud de reposición creada" if status == "READY" else "⚠️ Solicitud creada pero sin stock disponible",
                "can_continue": True,
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        
        print(f"✅ Solicitud de reposición #{replenishment_request.id} creada por operario {codigo_operario} - Estado: {status}")
        
        # 9. Broadcast alert to all connected operators (for replenishment operators' PDA)
        product_name = "Producto"
        product_ref = db.query(ProductLocation).filter_by(id=location_destino_id).first()
        from ...secondary.database.orm import ProductReference
        prod = db.query(ProductReference).filter_by(id=product_id).first()
        if prod:
            product_name = prod.nombre_producto
        
        await manager.broadcast({
            "action": "new_replenishment_alert",
            "data": {
                "request_id": replenishment_request.id,
                "status": status,
                "priority": priority,
                "product_name": product_name,
                "product_id": product_id,
                "destination_code": location_destino.codigo_ubicacion,
                "origin_code": origin_code,
                "requested_quantity": requested_quantity,
                "time_waiting": "0 min",
                "timestamp": datetime.utcnow().isoformat()
            }
        }, exclude=codigo_operario)
    
    except Exception as e:
        print(f"❌ Error en handle_request_replenishment: {e}")
        import traceback
        traceback.print_exc()
        await send_error(websocket, "INTERNAL_ERROR", f"Error creando solicitud: {str(e)}")
        db.rollback()
    finally:
        db.close()


async def handle_request_replenishment_urgent(
    websocket: WebSocket,
    operator_id: int,
    codigo_operario: str,
    data: dict
):
    """
    Crea una solicitud de reposición URGENTE desde la PDA.
    
    Se invoca cuando el operario salta un SKU durante el picking
    por falta de stock en la ubicación.
    
    Args:
        websocket: Conexión WebSocket
        operator_id: ID del operario solicitante
        codigo_operario: Código del operario (para respuestas)
        data: { location_destino_id, product_id, order_id, requested_quantity }
    """
    from ...secondary.database.config import SessionLocal
    from ...secondary.database.orm import ProductReference
    db = SessionLocal()
    
    try:
        location_destino_id = data.get("location_destino_id")
        product_id = data.get("product_id")
        order_id = data.get("order_id")
        requested_quantity = data.get("requested_quantity")
        
        if not location_destino_id:
            await send_error(websocket, "MISSING_LOCATION", "Falta el ID de ubicación destino")
            return
        
        if not product_id:
            await send_error(websocket, "MISSING_PRODUCT", "Falta el ID de producto")
            return
        
        if not requested_quantity or requested_quantity <= 0:
            await send_error(websocket, "INVALID_QUANTITY", "La cantidad solicitada debe ser mayor a 0")
            return
        
        # 1. Validar ubicación destino
        location_destino = db.query(ProductLocation).filter_by(id=location_destino_id).first()
        if not location_destino:
            await send_error(websocket, "LOCATION_NOT_FOUND", "Ubicación destino no encontrada")
            return
        
        # 2. Verificar si ya existe solicitud pendiente para este producto/ubicación
        existing_request = db.query(ReplenishmentRequest).filter(
            ReplenishmentRequest.product_id == product_id,
            ReplenishmentRequest.location_destino_id == location_destino_id,
            ReplenishmentRequest.status.in_(["WAITING_STOCK", "READY", "IN_PROGRESS"])
        ).first()
        
        if existing_request:
            # Escalar a URGENT si no lo es
            if existing_request.priority != "URGENT":
                existing_request.priority = "URGENT"
                existing_request.updated_at = datetime.utcnow()
                db.commit()
            
            await manager.send_message(codigo_operario, {
                "action": "replenishment_urgent_exists",
                "data": {
                    "request_id": existing_request.id,
                    "status": existing_request.status,
                    "priority": existing_request.priority,
                    "message": "⚠️ Ya existe una solicitud de reposición para este producto. Se ha escalado a URGENTE.",
                    "timestamp": datetime.utcnow().isoformat()
                }
            })
            return
        
        # 3. Buscar ubicación origen con stock (zona reposición)
        location_origen = None
        replenishment_locations = db.query(ProductLocation).filter(
            ProductLocation.product_id == product_id,
            ProductLocation.almacen_id == location_destino.almacen_id,
            ProductLocation.activa == True,
            ProductLocation.id != location_destino_id,
            ProductLocation.stock_actual > 0
        ).order_by(ProductLocation.stock_actual.desc()).all()
        
        # Priorizar zona REP
        for loc in replenishment_locations:
            if loc.pasillo and loc.pasillo.upper().startswith("REP"):
                location_origen = loc
                break
        
        if not location_origen and replenishment_locations:
            location_origen = replenishment_locations[0]
        
        # 4. Determinar estado
        if location_origen:
            status = "READY"
            origin_id = location_origen.id
        else:
            status = "WAITING_STOCK"
            origin_id = None
        
        # 5. Crear solicitud URGENT
        replenishment_request = ReplenishmentRequest(
            location_origen_id=origin_id,
            location_destino_id=location_destino_id,
            product_id=product_id,
            requested_quantity=requested_quantity,
            status=status,
            priority="URGENT",
            requester_id=operator_id,
            order_id=order_id,
            requested_at=datetime.utcnow()
        )
        
        db.add(replenishment_request)
        db.commit()
        db.refresh(replenishment_request)
        
        # 6. Responder al operario
        origin_code = location_origen.codigo_ubicacion if location_origen else None
        origin_stock = location_origen.stock_actual if location_origen else None
        
        await manager.send_message(codigo_operario, {
            "action": "replenishment_urgent_created",
            "data": {
                "request_id": replenishment_request.id,
                "status": status,
                "priority": "URGENT",
                "requested_quantity": requested_quantity,
                "location_destination": {
                    "id": location_destino.id,
                    "code": location_destino.codigo_ubicacion,
                    "stock_actual": location_destino.stock_actual
                },
                "location_origin": {
                    "id": origin_id,
                    "code": origin_code,
                    "stock_available": origin_stock
                } if location_origen else None,
                "message": "🚨 Solicitud de reposición URGENTE creada",
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        
        # 7. Broadcast alerta a todos los operarios conectados
        prod = db.query(ProductReference).filter_by(id=product_id).first()
        product_name = prod.nombre_producto if prod else "Producto"
        
        await manager.broadcast({
            "action": "new_replenishment_alert",
            "data": {
                "request_id": replenishment_request.id,
                "status": status,
                "priority": "URGENT",
                "product_name": product_name,
                "product_id": product_id,
                "destination_code": location_destino.codigo_ubicacion,
                "origin_code": origin_code,
                "requested_quantity": requested_quantity,
                "time_waiting": "0 min",
                "timestamp": datetime.utcnow().isoformat()
            }
        }, exclude=codigo_operario)
        
        print(f"🚨 Solicitud de reposición URGENTE #{replenishment_request.id} creada por operario {codigo_operario}")
    
    except Exception as e:
        print(f"❌ Error en handle_request_replenishment_urgent: {e}")
        import traceback
        traceback.print_exc()
        await send_error(websocket, "INTERNAL_ERROR", f"Error creando solicitud urgente: {str(e)}")
        db.rollback()
    finally:
        db.close()


async def handle_get_next_replenishment(
    websocket: WebSocket,
    operator_id: int,
    codigo_operario: str,
    data: dict
):
    """
    Step 1: Get and auto-assign the next available replenishment request.
    
    Finds the highest priority READY request without an executor,
    assigns it to the current operator, and returns all data needed
    for the PDA to display and validate locally.
    
    Priority order: URGENT > HIGH > NORMAL
    Uses SELECT FOR UPDATE to prevent race conditions.
    
    Args:
        websocket: WebSocket connection
        operator_id: Operator numeric ID (becomes executor_id)
        codigo_operario: Operator code (for responses)
        data: {} (no input needed)
    """
    from ...secondary.database.config import SessionLocal
    from ...secondary.database.orm import EAN as EANModel, ProductReference
    db = SessionLocal()
    
    try:
        # 1. Find next available request (READY, no executor assigned)
        #    Priority: URGENT=1, HIGH=2, NORMAL=3
        #    Then by oldest first (requested_at ASC)
        priority_order = case(
            (ReplenishmentRequest.priority == "URGENT", 1),
            (ReplenishmentRequest.priority == "HIGH", 2),
            (ReplenishmentRequest.priority == "NORMAL", 3),
            else_=4
        )
        
        request = db.query(ReplenishmentRequest).filter(
            ReplenishmentRequest.status == "READY",
            ReplenishmentRequest.executor_id.is_(None)
        ).with_for_update().order_by(
            priority_order,
            ReplenishmentRequest.requested_at.asc()
        ).first()
        
        # 2. No requests available
        if not request:
            await manager.send_message(codigo_operario, {
                "action": "no_replenishments_available",
                "data": {
                    "message": "No hay solicitudes de reposición disponibles en este momento",
                    "timestamp": datetime.utcnow().isoformat()
                }
            })
            return
        
        # 3. Auto-assign to operator: READY → IN_PROGRESS
        request.executor_id = operator_id
        request.status = "IN_PROGRESS"
        request.started_at = datetime.utcnow()
        request.updated_at = datetime.utcnow()
        
        # 4. Load product info
        product = db.query(ProductReference).filter_by(id=request.product_id).first()
        
        # 5. Load all EANs for PDA local validation
        eans = db.query(EANModel).filter_by(product_reference_id=request.product_id).all()
        
        # 6. Load locations
        origin_location = db.query(ProductLocation).filter_by(id=request.location_origen_id).first() if request.location_origen_id else None
        destination_location = db.query(ProductLocation).filter_by(id=request.location_destino_id).first()
        
        db.commit()
        
        # 7. Send complete replenishment data
        await manager.send_message(codigo_operario, {
            "action": "replenishment_assigned",
            "data": {
                "request_id": request.id,
                "status": "IN_PROGRESS",
                "priority": request.priority,
                "requested_quantity": request.requested_quantity,
                "product": {
                    "id": product.id if product else None,
                    "nombre": product.nombre_producto if product else "Desconocido",
                    "sku": product.sku if product else None,
                    "eans": [e.ean for e in eans]
                },
                "origin_location": {
                    "id": origin_location.id,
                    "code": origin_location.codigo_ubicacion,
                    "stock_actual": origin_location.stock_actual
                } if origin_location else None,
                "destination_location": {
                    "id": destination_location.id,
                    "code": destination_location.codigo_ubicacion,
                    "stock_actual": destination_location.stock_actual
                } if destination_location else None,
                "assigned_at": request.started_at.isoformat(),
                "message": "✅ Reposición asignada. Dirígete a la ubicación de origen.",
                "next_step": "scan_origin_location",
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        
        print(f"✅ Reposición #{request.id} ({request.priority}) asignada automáticamente a operario {codigo_operario}")
    
    except Exception as e:
        print(f"❌ Error en handle_get_next_replenishment: {e}")
        import traceback
        traceback.print_exc()
        await send_error(websocket, "INTERNAL_ERROR", f"Error obteniendo reposición: {str(e)}")
        db.rollback()
    finally:
        db.close()


async def handle_scan_origin_location(
    websocket: WebSocket,
    operator_id: int,
    codigo_operario: str,
    data: dict
):
    """
    Step 2: Operator scans origin location barcode at replenishment warehouse.
    
    Validates the scanned location code matches the request's origin location
    and that there is sufficient stock.
    
    Args:
        websocket: WebSocket connection
        operator_id: Operator numeric ID
        codigo_operario: Operator code (for responses)
        data: { request_id, location_code }
    """
    from ...secondary.database.config import SessionLocal
    db = SessionLocal()
    
    try:
        request_id = data.get("request_id")
        location_code = data.get("location_code")
        
        if not request_id:
            await send_error(websocket, "MISSING_REQUEST_ID", "Falta el ID de solicitud de reposición")
            return
        
        if not location_code:
            await send_error(websocket, "MISSING_LOCATION_CODE", "Falta el código de ubicación")
            return
        
        # 1. Get request
        request = db.query(ReplenishmentRequest).filter_by(id=request_id).first()
        
        if not request:
            await send_error(websocket, "REQUEST_NOT_FOUND", "Solicitud de reposición no encontrada")
            return
        
        if request.status != "IN_PROGRESS":
            await send_error(
                websocket, "INVALID_STATUS",
                f"La solicitud está en estado {request.status}. Debe estar en IN_PROGRESS"
            )
            return
        
        # 2. Validate origin location
        if not request.location_origen_id:
            await send_error(websocket, "NO_ORIGIN", "Esta solicitud no tiene ubicación origen asignada")
            return
        
        origin_location = db.query(ProductLocation).filter_by(id=request.location_origen_id).first()
        
        if not origin_location:
            await send_error(websocket, "ORIGIN_NOT_FOUND", "Ubicación origen no encontrada en base de datos")
            return
        
        # 3. Compare scanned code with expected code
        if origin_location.codigo_ubicacion != location_code:
            await send_error(
                websocket, "WRONG_ORIGIN_LOCATION",
                f"Ubicación incorrecta. Se esperaba: {origin_location.codigo_ubicacion}"
            )
            return
        
        # # 4. Validate sufficient stock
        # if origin_location.stock_actual < request.requested_quantity:
        #     await send_error(
        #         websocket, "INSUFFICIENT_STOCK",
        #         f"Stock insuficiente en origen. Disponible: {origin_location.stock_actual}, Solicitado: {request.requested_quantity}"
        #     )
        #     return
        
        # 5. Get destination info for the response
        destination_location = db.query(ProductLocation).filter_by(id=request.location_destino_id).first()
        
        # 6. Send confirmation
        await manager.send_message(codigo_operario, {
            "action": "origin_confirmed",
            "data": {
                "request_id": request.id,
                "location_origin": {
                    "id": origin_location.id,
                    "code": origin_location.codigo_ubicacion,
                    "stock_actual": origin_location.stock_actual
                },
                "location_destination": {
                    "id": destination_location.id,
                    "code": destination_location.codigo_ubicacion,
                    "stock_actual": destination_location.stock_actual
                } if destination_location else None,
                "requested_quantity": request.requested_quantity,
                "message": "✅ Ubicación origen confirmada. Lleva el producto a la ubicación destino y escanéala.",
                "next_step": "scan_destination_location",
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        
        print(f"✅ Reposición #{request.id} - Origen confirmado: {origin_location.codigo_ubicacion}")
    
    except Exception as e:
        print(f"❌ Error en handle_scan_origin_location: {e}")
        import traceback
        traceback.print_exc()
        await send_error(websocket, "INTERNAL_ERROR", f"Error validando ubicación origen: {str(e)}")
    finally:
        db.close()


async def handle_scan_destination_location(
    websocket: WebSocket,
    operator_id: int,
    codigo_operario: str,
    data: dict
):
    """
    Step 3: Operator scans destination location barcode at picking warehouse.
    
    Validates the scanned location code matches the request's destination.
    
    Args:
        websocket: WebSocket connection
        operator_id: Operator numeric ID
        codigo_operario: Operator code (for responses)
        data: { request_id, location_code }
    """
    from ...secondary.database.config import SessionLocal
    db = SessionLocal()
    
    try:
        request_id = data.get("request_id")
        location_code = data.get("location_code")
        
        if not request_id:
            await send_error(websocket, "MISSING_REQUEST_ID", "Falta el ID de solicitud de reposición")
            return
        
        if not location_code:
            await send_error(websocket, "MISSING_LOCATION_CODE", "Falta el código de ubicación")
            return
        
        # 1. Get request
        request = db.query(ReplenishmentRequest).filter_by(id=request_id).first()
        
        if not request:
            await send_error(websocket, "REQUEST_NOT_FOUND", "Solicitud de reposición no encontrada")
            return
        
        if request.status != "IN_PROGRESS":
            await send_error(
                websocket, "INVALID_STATUS",
                f"La solicitud está en estado {request.status}. Debe estar en IN_PROGRESS"
            )
            return
        
        # 2. Validate destination location
        destination_location = db.query(ProductLocation).filter_by(id=request.location_destino_id).first()
        
        if not destination_location:
            await send_error(websocket, "DESTINATION_NOT_FOUND", "Ubicación destino no encontrada en base de datos")
            return
        
        # 3. Compare scanned code with expected code
        if destination_location.codigo_ubicacion != location_code:
            await send_error(
                websocket, "WRONG_DESTINATION_LOCATION",
                f"Ubicación incorrecta. Se esperaba: {destination_location.codigo_ubicacion}"
            )
            return
        
        # 4. Send confirmation
        await manager.send_message(codigo_operario, {
            "action": "destination_confirmed",
            "data": {
                "request_id": request.id,
                "location_destination": {
                    "id": destination_location.id,
                    "code": destination_location.codigo_ubicacion,
                    "stock_actual": destination_location.stock_actual
                },
                "requested_quantity": request.requested_quantity,
                "message": "✅ Ubicación destino confirmada. Escanea el producto e indica la cantidad para completar la reposición.",
                "next_step": "confirm_replenishment",
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        
        print(f"✅ Reposición #{request.id} - Destino confirmado: {destination_location.codigo_ubicacion}")
    
    except Exception as e:
        print(f"❌ Error en handle_scan_destination_location: {e}")
        import traceback
        traceback.print_exc()
        await send_error(websocket, "INTERNAL_ERROR", f"Error validando ubicación destino: {str(e)}")
    finally:
        db.close()


async def handle_confirm_replenishment(
    websocket: WebSocket,
    operator_id: int,
    codigo_operario: str,
    data: dict
):
    """
    Step 4: Operator scans product EAN and sends cantidad_servida to complete replenishment.
    
    Moves stock atomically between origin and destination locations.
    
    Args:
        websocket: WebSocket connection
        operator_id: Operator numeric ID
        codigo_operario: Operator code (for responses)
        data: { request_id, ean, cantidad_servida }
    """
    from ...secondary.database.config import SessionLocal
    db = SessionLocal()
    
    try:
        request_id = data.get("request_id")
        ean = data.get("ean")
        cantidad_servida = data.get("cantidad_servida")
        
        if not request_id:
            await send_error(websocket, "MISSING_REQUEST_ID", "Falta el ID de solicitud de reposición")
            return
        
        if not ean:
            await send_error(websocket, "MISSING_EAN", "Falta el código EAN del producto")
            return
        
        if not cantidad_servida or cantidad_servida <= 0:
            await send_error(websocket, "INVALID_QUANTITY", "La cantidad servida debe ser mayor a 0")
            return
        
        # 1. Get request with locations
        request = db.query(ReplenishmentRequest).filter_by(id=request_id).first()
        
        if not request:
            await send_error(websocket, "REQUEST_NOT_FOUND", "Solicitud de reposición no encontrada")
            return
        
        if request.status != "IN_PROGRESS":
            await send_error(
                websocket, "INVALID_STATUS",
                f"La solicitud está en estado {request.status}. Debe estar en IN_PROGRESS"
            )
            return
        
        # 2. Get product info
        from ...secondary.database.orm import ProductReference
        product = db.query(ProductReference).filter_by(id=request.product_id).first()
        
        # 3. Get locations
        origin_location = db.query(ProductLocation).filter_by(id=request.location_origen_id).first() if request.location_origen_id else None
        destination_location = db.query(ProductLocation).filter_by(id=request.location_destino_id).first()
        
        if not origin_location or not destination_location:
            await send_error(websocket, "LOCATIONS_NOT_FOUND", "Ubicación origen o destino no encontrada")
            return
        
        # 4. Validate sufficient stock in origin
        if origin_location.stock_actual < cantidad_servida:
            await send_error(
                websocket, "INSUFFICIENT_STOCK",
                f"Stock insuficiente en origen. Disponible: {origin_location.stock_actual}, Cantidad: {cantidad_servida}"
            )
            return
        
        # 5. Move stock atomically
        origin_stock_before = origin_location.stock_actual
        dest_stock_before = destination_location.stock_actual
        
        origin_location.stock_actual -= cantidad_servida
        destination_location.stock_actual += cantidad_servida
        
        # Update last stock update timestamp
        origin_location.ultima_actualizacion_stock = datetime.utcnow()
        destination_location.ultima_actualizacion_stock = datetime.utcnow()
        
        # 6. Mark request as completed
        request.status = "COMPLETED"
        request.actual_quantity = cantidad_servida
        request.completed_at = datetime.utcnow()
        request.updated_at = datetime.utcnow()
        
        db.commit()
        
        # 7. Send confirmation
        await manager.send_message(codigo_operario, {
            "action": "replenishment_completed",
            "data": {
                "request_id": request.id,
                "status": "COMPLETED",
                "product": {
                    "id": product.id,
                    "nombre": product.nombre_producto,
                    "ean": ean
                },
                "cantidad_servida": cantidad_servida,
                "requested_quantity": request.requested_quantity,
                "origin_location": {
                    "code": origin_location.codigo_ubicacion,
                    "stock_before": origin_stock_before,
                    "stock_after": origin_location.stock_actual
                },
                "destination_location": {
                    "code": destination_location.codigo_ubicacion,
                    "stock_before": dest_stock_before,
                    "stock_after": destination_location.stock_actual
                },
                "message": "✅ Reposición completada exitosamente",
                "completed_at": request.completed_at.isoformat(),
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        
        print(f"✅ Reposición #{request.id} completada por operario {codigo_operario} - Cantidad: {cantidad_servida}")
    
    except Exception as e:
        print(f"❌ Error en handle_confirm_replenishment: {e}")
        import traceback
        traceback.print_exc()
        await send_error(websocket, "INTERNAL_ERROR", f"Error completando reposición: {str(e)}")
        db.rollback()
    finally:
        db.close()


WAREHOUSE_NAMES = {
    1: "Almacén de Stock",
    2: "Almacén de Picking",
}


def _get_warehouse_name(almacen_id: int) -> str:
    return WAREHOUSE_NAMES.get(almacen_id, f"Almacén #{almacen_id}")


def _find_location_by_code(db, location_code: str, product_id: int = None, active_only: bool = True):
    """
    Busca ProductLocation por codigo_ubicacion (propiedad computada).
    Si product_id se proporciona, filtra por ese producto.
    Retorna la primera coincidencia.
    """
    query = db.query(ProductLocation)
    if product_id:
        query = query.filter(ProductLocation.product_id == product_id)
    if active_only:
        query = query.filter(ProductLocation.activa == True)
    
    for loc in query.all():
        if loc.codigo_ubicacion == location_code:
            return loc
    return None


def _find_any_location_by_code(db, location_code: str, active_only: bool = True):
    """
    Busca cualquier ProductLocation activa por codigo_ubicacion.
    Retorna la primera coincidencia (sin filtro de producto).
    """
    query = db.query(ProductLocation)
    if active_only:
        query = query.filter(ProductLocation.activa == True)
    
    for loc in query.all():
        if loc.codigo_ubicacion == location_code:
            return loc
    return None


async def handle_move_stock_scan_product(
    websocket: WebSocket,
    operator_id: int,
    codigo_operario: str,
    data: dict
):
    """
    Paso 1 de mover stock: escanear EAN del producto.
    
    Identifica el producto y devuelve las ubicaciones donde tiene stock.
    
    Args:
        websocket: Conexión WebSocket
        operator_id: ID del operario
        codigo_operario: Código del operario
        data: { ean }
    """
    from ...secondary.database.config import SessionLocal
    from ...secondary.database.orm import EAN as EANModel, ProductReference
    db = SessionLocal()
    
    try:
        ean = data.get("ean")
        
        if not ean:
            await send_error(websocket, "MISSING_EAN", "Falta el código EAN del producto")
            return
        
        # 1. Buscar EAN
        ean_record = db.query(EANModel).filter(EANModel.ean == ean).first()
        
        if not ean_record or not ean_record.product_reference_id:
            await send_error(websocket, "PRODUCT_NOT_FOUND", "No se encontró producto con ese EAN")
            return
        
        # 2. Cargar producto
        product = db.query(ProductReference).filter_by(id=ean_record.product_reference_id).first()
        if not product:
            await send_error(websocket, "PRODUCT_NOT_FOUND", "Producto no encontrado")
            return
        
        # 3. Cargar todos los EANs del producto
        all_eans = db.query(EANModel).filter_by(product_reference_id=product.id).all()
        
        # 4. Buscar ubicaciones con stock
        locations = db.query(ProductLocation).filter(
            ProductLocation.product_id == product.id,
            ProductLocation.activa == True,
            ProductLocation.stock_actual > 0
        ).all()
        
        locations_data = []
        for loc in locations:
            locations_data.append({
                "id": loc.id,
                "code": loc.codigo_ubicacion,
                "stock_actual": loc.stock_actual,
                "almacen_id": loc.almacen_id,
                "almacen_nombre": _get_warehouse_name(loc.almacen_id)
            })
        
        await manager.send_message(codigo_operario, {
            "action": "move_stock_product_found",
            "data": {
                "product": {
                    "id": product.id,
                    "nombre": product.nombre_producto,
                    "sku": product.sku,
                    "eans": [e.ean for e in all_eans]
                },
                "locations_with_stock": locations_data,
                "message": f"✅ Producto encontrado: {product.nombre_producto}. Escanea la ubicación de origen.",
                "next_step": "move_stock_scan_origin",
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        
        print(f"📦 [MOVE] Operario {codigo_operario} escaneó producto {product.nombre_producto} ({ean}) - {len(locations)} ubicaciones con stock")
    
    except Exception as e:
        print(f"❌ Error en handle_move_stock_scan_product: {e}")
        import traceback
        traceback.print_exc()
        await send_error(websocket, "INTERNAL_ERROR", f"Error escaneando producto: {str(e)}")
        db.rollback()
    finally:
        db.close()


async def handle_move_stock_scan_origin(
    websocket: WebSocket,
    operator_id: int,
    codigo_operario: str,
    data: dict
):
    """
    Paso 2 de mover stock: escanear ubicación de origen.
    
    Valida que el producto tenga stock en esa ubicación.
    
    Args:
        websocket: Conexión WebSocket
        operator_id: ID del operario
        codigo_operario: Código del operario
        data: { product_id, location_code }
    """
    from ...secondary.database.config import SessionLocal
    db = SessionLocal()
    
    try:
        product_id = data.get("product_id")
        location_code = data.get("location_code")
        
        if not product_id:
            await send_error(websocket, "MISSING_PRODUCT", "Falta el ID de producto")
            return
        
        if not location_code:
            await send_error(websocket, "MISSING_LOCATION_CODE", "Falta el código de ubicación")
            return
        
        # 1. Buscar ubicación del producto por código
        location = _find_location_by_code(db, location_code, product_id=product_id)
        
        if not location:
            await send_error(
                websocket, "PRODUCT_NOT_AT_LOCATION",
                f"El producto no se encuentra en la ubicación {location_code}"
            )
            return
        
        # 2. Validar stock
        if (location.stock_actual or 0) <= 0:
            await send_error(
                websocket, "NO_STOCK",
                f"No hay stock del producto en la ubicación {location_code}"
            )
            return
        
        await manager.send_message(codigo_operario, {
            "action": "move_stock_origin_confirmed",
            "data": {
                "product_id": product_id,
                "origin_location": {
                    "id": location.id,
                    "code": location.codigo_ubicacion,
                    "stock_actual": location.stock_actual,
                    "almacen_id": location.almacen_id,
                    "almacen_nombre": _get_warehouse_name(location.almacen_id)
                },
                "message": f"✅ Ubicación origen confirmada ({_get_warehouse_name(location.almacen_id)}). Stock disponible: {location.stock_actual}. Escanea la ubicación destino.",
                "next_step": "move_stock_scan_destination",
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        
        print(f"📦 [MOVE] Origen confirmado: {location_code} (stock: {location.stock_actual})")
    
    except Exception as e:
        print(f"❌ Error en handle_move_stock_scan_origin: {e}")
        import traceback
        traceback.print_exc()
        await send_error(websocket, "INTERNAL_ERROR", f"Error escaneando origen: {str(e)}")
        db.rollback()
    finally:
        db.close()


async def handle_move_stock_scan_destination(
    websocket: WebSocket,
    operator_id: int,
    codigo_operario: str,
    data: dict
):
    """
    Paso 3 de mover stock: escanear ubicación de destino.
    
    Valida que la ubicación exista (puede ser otro almacén).
    
    Args:
        websocket: Conexión WebSocket
        operator_id: ID del operario
        codigo_operario: Código del operario
        data: { product_id, origin_location_id, location_code }
    """
    from ...secondary.database.config import SessionLocal
    db = SessionLocal()
    
    try:
        product_id = data.get("product_id")
        origin_location_id = data.get("origin_location_id")
        location_code = data.get("location_code")
        
        if not product_id:
            await send_error(websocket, "MISSING_PRODUCT", "Falta el ID de producto")
            return
        
        if not origin_location_id:
            await send_error(websocket, "MISSING_ORIGIN", "Falta el ID de ubicación origen")
            return
        
        if not location_code:
            await send_error(websocket, "MISSING_LOCATION_CODE", "Falta el código de ubicación destino")
            return
        
        # 1. Validar origen existe
        origin = db.query(ProductLocation).filter_by(id=origin_location_id).first()
        if not origin:
            await send_error(websocket, "ORIGIN_NOT_FOUND", "Ubicación origen no encontrada")
            return
        
        # 2. Buscar cualquier ubicación activa con ese código (de cualquier producto/almacén)
        ref_location = _find_any_location_by_code(db, location_code)
        
        if not ref_location:
            await send_error(
                websocket, "LOCATION_NOT_FOUND",
                f"No se encontró ninguna ubicación con el código {location_code}"
            )
            return
        
        # 3. Verificar que no sea la misma ubicación origen
        if ref_location.id == origin_location_id:
            await send_error(websocket, "SAME_LOCATION", "La ubicación destino no puede ser la misma que el origen")
            return
        
        # 4. Buscar si el producto ya tiene ProductLocation en ese destino exacto
        existing_dest = _find_location_by_code(db, location_code, product_id=product_id)
        
        # Verificar que el existing_dest no sea el origen
        if existing_dest and existing_dest.id == origin_location_id:
            existing_dest = None
        
        dest_stock = existing_dest.stock_actual if existing_dest else 0
        is_new_location = existing_dest is None
        
        await manager.send_message(codigo_operario, {
            "action": "move_stock_destination_confirmed",
            "data": {
                "product_id": product_id,
                "origin_location_id": origin_location_id,
                "origin_stock": origin.stock_actual,
                "destination_location": {
                    "id": existing_dest.id if existing_dest else None,
                    "code": location_code,
                    "stock_actual": dest_stock,
                    "almacen_id": ref_location.almacen_id,
                    "almacen_nombre": _get_warehouse_name(ref_location.almacen_id),
                    "is_new": is_new_location
                },
                "quantity_to_move": origin.stock_actual,
                "message": f"✅ Ubicación destino confirmada ({_get_warehouse_name(ref_location.almacen_id)}). Se moverán {origin.stock_actual} unidades. {'Se creará nueva ubicación para este producto.' if is_new_location else f'Stock actual del producto en destino: {dest_stock}.'} Confirma el movimiento.",
                "next_step": "move_stock_confirm",
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        
        print(f"📦 [MOVE] Destino confirmado: {location_code} ({'nuevo' if is_new_location else 'existente'}) - Almacén: {_get_warehouse_name(ref_location.almacen_id)}")
    
    except Exception as e:
        print(f"❌ Error en handle_move_stock_scan_destination: {e}")
        import traceback
        traceback.print_exc()
        await send_error(websocket, "INTERNAL_ERROR", f"Error escaneando destino: {str(e)}")
        db.rollback()
    finally:
        db.close()


async def handle_move_stock_confirm(
    websocket: WebSocket,
    operator_id: int,
    codigo_operario: str,
    data: dict
):
    """
    Paso 4 de mover stock: confirmar y ejecutar movimiento.
    
    Mueve TODO el stock del producto desde origen al destino.
    No se manejan cantidades parciales.
    
    Args:
        websocket: Conexión WebSocket
        operator_id: ID del operario
        codigo_operario: Código del operario
        data: { product_id, origin_location_id, destination_location_code }
    """
    from ...secondary.database.config import SessionLocal
    db = SessionLocal()
    
    try:
        product_id = data.get("product_id")
        origin_location_id = data.get("origin_location_id")
        destination_location_code = data.get("destination_location_code")
        
        if not product_id:
            await send_error(websocket, "MISSING_PRODUCT", "Falta el ID de producto")
            return
        
        if not origin_location_id:
            await send_error(websocket, "MISSING_ORIGIN", "Falta el ID de ubicación origen")
            return
        
        if not destination_location_code:
            await send_error(websocket, "MISSING_DESTINATION", "Falta el código de ubicación destino")
            return
        
        # 1. Obtener ubicación origen
        origin = db.query(ProductLocation).filter_by(id=origin_location_id).first()
        if not origin:
            await send_error(websocket, "ORIGIN_NOT_FOUND", "Ubicación origen no encontrada")
            return
        
        # 2. Validar que haya stock
        cantidad = origin.stock_actual or 0
        if cantidad <= 0:
            await send_error(websocket, "NO_STOCK", "No hay stock disponible en la ubicación origen")
            return
        
        # 3. Buscar/crear ubicación destino para el producto
        dest = _find_location_by_code(db, destination_location_code, product_id=product_id)
        
        # Si es la misma que el origen, buscar otra
        if dest and dest.id == origin_location_id:
            dest = None
        
        # Buscar ubicación de referencia para datos de ubicación física
        ref_location = _find_any_location_by_code(db, destination_location_code)
        if not ref_location:
            await send_error(websocket, "LOCATION_NOT_FOUND", f"Ubicación {destination_location_code} no encontrada")
            return
        
        created_new = False
        if not dest:
            # Crear nueva ProductLocation para el producto en el destino
            dest = ProductLocation(
                almacen_id=ref_location.almacen_id,
                product_id=product_id,
                pasillo=ref_location.pasillo,
                lado=ref_location.lado,
                ubicacion=ref_location.ubicacion,
                altura=ref_location.altura,
                stock_actual=0,
                stock_reservado=0,
                stock_minimo=0,
                prioridad=3,
                activa=True,
                ultima_actualizacion_stock=datetime.utcnow()
            )
            db.add(dest)
            db.flush()
            created_new = True
        
        # 4. Ejecutar movimiento
        origin_stock_before = origin.stock_actual or 0
        dest_stock_before = dest.stock_actual or 0
        
        origin.stock_actual = origin_stock_before - cantidad
        dest.stock_actual = dest_stock_before + cantidad
        
        origin.ultima_actualizacion_stock = datetime.utcnow()
        dest.ultima_actualizacion_stock = datetime.utcnow()
        
        # 5. Crear registros de auditoría
        move_out = StockMovement(
            product_location_id=origin.id,
            product_id=product_id,
            order_id=None,
            order_line_id=None,
            tipo="MOVE_OUT",
            cantidad=-cantidad,
            stock_antes=origin_stock_before,
            stock_despues=origin.stock_actual,
            notas=f"Movimiento de stock hacia {destination_location_code} "
                  f"({_get_warehouse_name(ref_location.almacen_id)}), "
                  f"cantidad: {cantidad}, operario: {codigo_operario}"
        )
        
        move_in = StockMovement(
            product_location_id=dest.id,
            product_id=product_id,
            order_id=None,
            order_line_id=None,
            tipo="MOVE_IN",
            cantidad=cantidad,
            stock_antes=dest_stock_before,
            stock_despues=dest.stock_actual,
            notas=f"Movimiento de stock desde {origin.codigo_ubicacion} "
                  f"({_get_warehouse_name(origin.almacen_id)}), "
                  f"cantidad: {cantidad}, operario: {codigo_operario}"
        )
        
        db.add(move_out)
        db.add(move_in)
        db.commit()
        
        # 6. Responder
        await manager.send_message(codigo_operario, {
            "action": "move_stock_completed",
            "data": {
                "product_id": product_id,
                "cantidad": cantidad,
                "origin": {
                    "location_id": origin.id,
                    "code": origin.codigo_ubicacion,
                    "almacen_id": origin.almacen_id,
                    "almacen_nombre": _get_warehouse_name(origin.almacen_id),
                    "stock_before": origin_stock_before,
                    "stock_after": origin.stock_actual
                },
                "destination": {
                    "location_id": dest.id,
                    "code": dest.codigo_ubicacion,
                    "almacen_id": dest.almacen_id,
                    "almacen_nombre": _get_warehouse_name(dest.almacen_id),
                    "stock_before": dest_stock_before,
                    "stock_after": dest.stock_actual,
                    "is_new_location": created_new
                },
                "message": f"✅ Stock movido: {cantidad} unidades de {origin.codigo_ubicacion} ({_get_warehouse_name(origin.almacen_id)}) → {dest.codigo_ubicacion} ({_get_warehouse_name(dest.almacen_id)})",
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        
        print(
            f"✅ [MOVE] Operario {codigo_operario}: {cantidad} uds movidas "
            f"{origin.codigo_ubicacion} ({_get_warehouse_name(origin.almacen_id)}) → "
            f"{dest.codigo_ubicacion} ({_get_warehouse_name(dest.almacen_id)})"
        )
    
    except Exception as e:
        print(f"❌ Error en handle_move_stock_confirm: {e}")
        import traceback
        traceback.print_exc()
        await send_error(websocket, "INTERNAL_ERROR", f"Error moviendo stock: {str(e)}")
        db.rollback()
    finally:
        db.close()


async def send_error(websocket: WebSocket, error_code: str, message: str):
    """
    Envía un mensaje de error al cliente.
    
    Args:
        websocket: Conexión WebSocket
        error_code: Código del error
        message: Mensaje descriptivo del error
    """
    try:
        await websocket.send_json({
            "action": "scan_error",
            "data": {
                "error_code": error_code,
                "message": message,
                "can_retry": True,
                "timestamp": datetime.utcnow().isoformat()
            }
        })
    except Exception as e:
        print(f"Error enviando mensaje de error: {e}")
