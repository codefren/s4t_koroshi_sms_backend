"""
WebSocket endpoint para operarios de PDA.

Maneja la conexión WebSocket y el escaneo de productos en tiempo real.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from datetime import datetime

from .manager import manager
from ...secondary.database.orm import Operator, Order, OrderLine


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
        operator = db.query(Operator).filter_by(codigo_operario=codigo_operario).first()
        
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
            if line.product_reference.color:
                producto_nombre += f" {line.product_reference.color}"
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
