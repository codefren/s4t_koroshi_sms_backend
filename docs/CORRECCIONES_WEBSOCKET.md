# 🔧 Correcciones al Código WebSocket

## handle_scan_product - Versión Mejorada

```python
async def handle_scan_product(
    websocket: WebSocket,
    operator_id: int,
    data: dict,
    db: Session
):
    """Procesar escaneo de producto con validación completa."""
    try:
        order_id = data['order_id']
        ean = data['ean']
        ubicacion_escaneada = data.get('ubicacion')
        
        # 1. Validar orden asignada al operario
        order = db.query(Order).filter_by(id=order_id).first()
        if not order:
            await send_error(websocket, "ORDER_NOT_FOUND", "Orden no encontrada")
            return
        
        if order.operator_id != operator_id:
            await send_error(websocket, "ORDER_NOT_ASSIGNED", 
                           "Orden no asignada a este operario")
            return
        
        if order.status.codigo != "IN_PICKING":
            await send_error(websocket, "ORDER_WRONG_STATUS",
                           f"Orden en estado {order.status.codigo}")
            return
        
        # 2. Buscar producto por EAN
        line = db.query(OrderLine).filter(
            OrderLine.order_id == order_id,
            OrderLine.ean == ean
        ).first()
        
        if not line:
            await send_error(websocket, "EAN_NOT_IN_ORDER",
                           f"EAN {ean} no pertenece a esta orden")
            return
        
        # 3. Validar cantidad
        if line.cantidad_servida >= line.cantidad_solicitada:
            await send_error(websocket, "MAX_QUANTITY_REACHED",
                           "Ya se completó la cantidad solicitada")
            return
        
        # 4. Validar ubicación (opcional pero recomendado)
        ubicacion_esperada = None
        ubicacion_match = None
        if line.product_location:
            ubicacion_esperada = (
                f"{line.product_location.pasillo}-"
                f"{line.product_location.lado[:3]}-"
                f"{line.product_location.ubicacion}-"
                f"H{line.product_location.altura}"
            )
            if ubicacion_escaneada:
                ubicacion_match = (ubicacion_escaneada == ubicacion_esperada)
        
        # 5. Incrementar cantidad +1
        line.cantidad_servida += 1
        
        # 6. Actualizar estado de línea
        if line.cantidad_servida == line.cantidad_solicitada:
            line.estado = "COMPLETED"
        elif line.cantidad_servida > 0:
            line.estado = "PARTIAL"
        
        # 7. Actualizar contadores de orden
        items_completados = db.query(OrderLine).filter(
            OrderLine.order_id == order_id,
            OrderLine.estado == "COMPLETED"
        ).count()
        
        order.items_completados = items_completados
        
        db.commit()
        
        # 8. Preparar información del producto
        producto_info = {
            "nombre": line.product_reference.nombre_producto if line.product_reference else "Producto",
            "color": line.product_reference.color if line.product_reference else None,
            "talla": line.product_reference.talla if line.product_reference else None,
            "sku": line.product_reference.sku if line.product_reference else None,
            "ean": line.ean,
        }
        
        # 9. Preparar información de ubicación
        ubicacion_info = {
            "escaneada": ubicacion_escaneada,
            "esperada": ubicacion_esperada,
            "match": ubicacion_match
        }
        
        # 10. Calcular progreso
        progreso_linea = (
            (line.cantidad_servida / line.cantidad_solicitada * 100)
            if line.cantidad_solicitada > 0 else 0
        )
        
        progreso_orden = (
            (order.items_completados / order.total_items * 100)
            if order.total_items > 0 else 0
        )
        
        # 11. Enviar confirmación ENRIQUECIDA
        await manager.send_message(operator_id, {
            "action": "scan_confirmed",
            "data": {
                "line_id": line.id,
                
                # Información del producto
                "producto": producto_info,
                
                # Información de ubicación
                "ubicacion": ubicacion_info,
                
                # Cantidades y progreso
                "cantidades": {
                    "actual": line.cantidad_servida,
                    "solicitada": line.cantidad_solicitada,
                    "pendiente": line.cantidad_solicitada - line.cantidad_servida,
                    "progreso_porcentaje": round(progreso_linea, 2)
                },
                
                "estado_linea": line.estado,
                
                # Progreso de la orden completa
                "progreso_orden": {
                    "total_items": order.total_items,
                    "items_completados": order.items_completados,
                    "progreso_porcentaje": round(progreso_orden, 2)
                },
                
                "mensaje": "✅ Producto escaneado correctamente"
            }
        })
    
    except KeyError as e:
        await send_error(websocket, "INVALID_DATA", f"Campo faltante: {e}")
        db.rollback()
    except Exception as e:
        print(f"Error en scan_product: {e}")
        await send_error(websocket, "INTERNAL_ERROR", str(e))
        db.rollback()


async def send_error(websocket: WebSocket, error_code: str, message: str):
    """Enviar error al cliente."""
    await websocket.send_json({
        "action": "scan_error",
        "data": {
            "error_code": error_code,
            "message": message,
            "can_retry": True
        }
    })
```

---

## Cambios Principales

1. ✅ **Validación de ubicación:** Compara ubicación escaneada vs. esperada
2. ✅ **Respuesta enriquecida:** Incluye color, talla, SKU del producto
3. ✅ **Información estructurada:** Separada en `producto`, `ubicacion`, `cantidades`
4. ✅ **Manejo de errores:** Captura `KeyError` para datos faltantes
5. ✅ **Ubicación formateada:** Construye código completo desde componentes

---

## Respuesta Mejorada al Cliente

```json
{
  "action": "scan_confirmed",
  "data": {
    "line_id": 456,
    
    "producto": {
      "nombre": "Camisa Polo Manga Corta",
      "color": "Rojo",
      "talla": "M",
      "sku": "CAM-POL-M-RJ",
      "ean": "8445962763983"
    },
    
    "ubicacion": {
      "escaneada": "A-IZQ-12-H2",
      "esperada": "A-IZQ-12-H2",
      "match": true
    },
    
    "cantidades": {
      "actual": 3,
      "solicitada": 5,
      "pendiente": 2,
      "progreso_porcentaje": 60.0
    },
    
    "estado_linea": "PARTIAL",
    
    "progreso_orden": {
      "total_items": 15,
      "items_completados": 8,
      "progreso_porcentaje": 53.33
    },
    
    "mensaje": "✅ Producto escaneado correctamente"
  }
}
```

---

## Ventajas de esta Versión

- ✅ Muestra color y talla en la PDA (mejor UX)
- ✅ Valida que el operario esté en la ubicación correcta
- ✅ Respuesta JSON más estructurada y clara
- ✅ Compatible con el modelo ORM real
- ✅ Fácil de consumir desde el frontend

