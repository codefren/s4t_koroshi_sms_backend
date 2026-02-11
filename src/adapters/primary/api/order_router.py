"""
Router para gestión de órdenes.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.adapters.secondary.database.config import get_db
from src.adapters.secondary.database.orm import (
    Order, 
    OrderStatus, 
    Operator, 
    OrderLine, 
    OrderHistory,
    ProductReference,
    ProductLocation,
    PackingBox,
    OrderLineBoxDistribution
)
from src.core.domain.models import (
    OrderListItem, 
    OrderDetailFull, 
    OrderProductDetail,
    AssignOperatorRequest,
    UpdateOrderStatusRequest,
    UpdateOrderPriorityRequest,
    StartPickingRequest,
    OrderPackingDistribution,
    BoxDistribution,
    ProductInBox
)

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get("/", response_model=List[OrderListItem])
def list_orders(
    skip: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(100, ge=1, le=500, description="Número máximo de registros a retornar"),
    prioridad: Optional[str] = Query(None, description="Filtrar por prioridad (NORMAL, HIGH, URGENT)"),
    estado_codigo: Optional[str] = Query(None, description="Filtrar por código de estado"),
    db: Session = Depends(get_db)
):
    """
    Lista todas las órdenes con información resumida.
    
    **Incluye:**
    - Número de orden
    - Cliente
    - Total de unidades solicitadas (total_items)
    - Total de unidades servidas (items_completados)
    - Progreso en porcentaje (0-100%)
    - Operario asignado (o "Sin asignar")
    - Prioridad
    - Estado
    """
    # Query base con joins para obtener estado y operario
    query = db.query(
        Order.id,
        Order.numero_orden,
        Order.cliente,
        Order.nombre_cliente,
        Order.total_items,
        Order.items_completados,
        Order.prioridad,
        Order.fecha_orden,
        Order.fecha_importacion,
        OrderStatus.nombre.label("estado"),
        OrderStatus.codigo.label("estado_codigo"),
        Operator.nombre.label("operario_nombre")
    ).join(
        OrderStatus, Order.status_id == OrderStatus.id
    ).outerjoin(
        Operator, Order.operator_id == Operator.id
    )
    
    # Aplicar filtros opcionales
    if prioridad:
        query = query.filter(Order.prioridad == prioridad.upper())
    
    if estado_codigo:
        query = query.filter(OrderStatus.codigo == estado_codigo.upper())
    
    # Ordenar por fecha de importación descendente (más recientes primero)
    query = query.order_by(Order.fecha_importacion.desc())
    
    # Aplicar paginación
    query = query.offset(skip).limit(limit)
    
    # Ejecutar query
    results = query.all()
    
    # Transformar resultados a modelo Pydantic
    orders = []
    for row in results:
        # Calcular progreso
        progreso = 0.0
        if row.total_items > 0:
            progreso = round((row.items_completados / row.total_items) * 100, 2)
        
        order_data = {
            "id": row.id,
            "numero_orden": row.numero_orden,
            "cliente": row.cliente,
            "nombre_cliente": row.nombre_cliente,
            "total_items": row.total_items,
            "items_completados": row.items_completados,
            "progreso": progreso,
            "operario_asignado": row.operario_nombre if row.operario_nombre else "Sin asignar",
            "prioridad": row.prioridad,
            "estado": row.estado,
            "estado_codigo": row.estado_codigo,
            "fecha_orden": row.fecha_orden,
            "fecha_importacion": row.fecha_importacion
        }
        orders.append(OrderListItem(**order_data))
    
    return orders


@router.get("/{order_id}", response_model=OrderDetailFull)
def get_order_detail(
    order_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene los detalles completos de una orden específica.
    
    **Incluye:**
    - Información general de la orden
    - Fecha de creación
    - Fecha límite (si existe)
    - Total de cajas (si existe)
    - Operario asignado (si existe)
    - Lista completa de productos con:
      - Nombre del producto
      - Descripción del color
      - Color
      - Talla
      - Ubicación en almacén
      - SKU/Artículo
      - EAN
      - Cantidades solicitadas y servidas
      - Estado de la línea
    """
    # Buscar la orden con eager loading de relaciones
    order = db.query(Order).options(
        joinedload(Order.order_lines).joinedload(OrderLine.product_reference),
        joinedload(Order.order_lines).joinedload(OrderLine.product_location),
        joinedload(Order.packing_boxes)
    ).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail=f"Orden con ID {order_id} no encontrada")
    
    # Obtener el estado
    status = db.query(OrderStatus).filter(OrderStatus.id == order.status_id).first()
    
    # Obtener el operario si existe
    operator = None
    if order.operator_id:
        operator = db.query(Operator).filter(Operator.id == order.operator_id).first()
    
    # Las líneas ya están cargadas por el joinedload
    order_lines = order.order_lines
    
    # Construir lista de productos usando las relaciones
    productos = []
    for line in order_lines:
        # Obtener datos desde las relaciones (normalizadas)
        product = line.product_reference
        location = line.product_location
        
        producto = OrderProductDetail(
            id=line.id,
            nombre=product.nombre_producto if product else "Producto no vinculado",
            descripcion=product.nombre_color if product else "",  # Nombre del color
            color=product.color_id if product else "",  # Código del color
            talla=product.talla if product else "",
            ubicacion=location.codigo_ubicacion if location else "Sin ubicación",
            sku=product.sku if product else "",
            ean=line.ean,  # Se mantiene en OrderLine para match rápido
            cantidad_solicitada=line.cantidad_solicitada,
            cantidad_servida=line.cantidad_servida,
            estado=line.estado
        )
        productos.append(producto)
    
    # Calcular progreso
    progreso = 0.0
    if order.total_items > 0:
        progreso = round((order.items_completados / order.total_items) * 100, 2)
    
    # Contar cajas de la orden
    num_cajas = len(order.packing_boxes) if order.packing_boxes else 0
    # total cajas
    total_cajas_str = f"{num_cajas} caja{'s' if num_cajas != 1 else ''}" if num_cajas > 0 else "Sin cajas"
    
    # Construir respuesta
    order_detail = OrderDetailFull(
        id=order.id,
        numero_orden=order.numero_orden,
        cliente=order.cliente,
        nombre_cliente=order.nombre_cliente,
        fecha_creacion=order.fecha_orden,
        fecha_limite="Sin fecha límite",
        total_cajas=total_cajas_str,
        operario_asignado=operator.nombre if operator else "Sin operario",
        estado=status.nombre if status else "Desconocido",
        estado_codigo=status.codigo if status else "UNKNOWN",
        prioridad=order.prioridad,
        total_items=order.total_items,
        items_completados=order.items_completados,
        progreso_porcentaje=progreso,
        productos=productos
    )
    
    return order_detail


@router.put("/{order_id}/assign-operator", response_model=OrderDetailFull)
def assign_operator_to_order(
    order_id: int,
    request: AssignOperatorRequest,
    db: Session = Depends(get_db)
):
    """
    Asigna un operario a una orden específica.
    
    **Parámetros:**
    - `order_id`: ID de la orden
    - `operator_id`: ID del operario a asignar (en el body)
    
    **Acciones:**
    - Asigna el operario a la orden
    - Actualiza el estado a ASSIGNED si estaba en PENDING
    - Registra la fecha de asignación
    - Crea entrada en el historial
    
    **Retorna:**
    - Detalle completo de la orden actualizada
    """
    # Buscar la orden
    order = db.query(Order).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail=f"Orden con ID {order_id} no encontrada")
    
    # Verificar que el operario existe
    operator = db.query(Operator).filter(Operator.id == request.operator_id).first()
    
    if not operator:
        raise HTTPException(
            status_code=404, 
            detail=f"Operario con ID {request.operator_id} no encontrado"
        )
    
    # Verificar que el operario está activo
    if not operator.activo:
        raise HTTPException(
            status_code=400,
            detail=f"El operario '{operator.nombre}' está inactivo y no puede ser asignado"
        )
    
    # Guardar estado anterior
    status_anterior_id = order.status_id
    
    # Asignar operario
    order.operator_id = request.operator_id
    order.fecha_asignacion = datetime.now()
    
    # Si la orden estaba en PENDING, cambiar a ASSIGNED
    current_status = db.query(OrderStatus).filter(OrderStatus.id == order.status_id).first()
    if current_status and current_status.codigo == "PENDING":
        assigned_status = db.query(OrderStatus).filter(OrderStatus.codigo == "ASSIGNED").first()
        if assigned_status:
            order.status_id = assigned_status.id
    
    # Crear entrada en historial
    history = OrderHistory(
        order_id=order.id,
        status_id=order.status_id,
        operator_id=request.operator_id,
        accion="ASSIGN_OPERATOR",
        status_anterior=status_anterior_id,
        status_nuevo=order.status_id,
        notas=f"Operario '{operator.nombre}' asignado a la orden",
        fecha=datetime.now(),
        event_metadata={
            "operator_codigo": operator.codigo,
            "operator_nombre": operator.nombre
        }
    )
    db.add(history)
    
    # Guardar cambios
    db.commit()
    db.refresh(order)
    
    # Retornar detalle actualizado de la orden
    return get_order_detail(order_id, db)


@router.put("/{order_id}/status", response_model=OrderDetailFull)
def update_order_status(
    order_id: int,
    request: UpdateOrderStatusRequest,
    db: Session = Depends(get_db)
):
    """
    Actualiza el estado de una orden específica.
    
    **Parámetros:**
    - `order_id`: ID de la orden
    - `estado_codigo`: Código del nuevo estado (en el body)
    - `notas`: Notas opcionales sobre el cambio (en el body)
    
    **Estados válidos:**
    - `PENDING` - Pendiente
    - `ASSIGNED` - Asignada
    - `IN_PICKING` - En Picking
    - `PICKED` - Picking Completado
    - `PACKING` - En Empaque
    - `READY` - Lista para Envío
    - `SHIPPED` - Enviada
    - `CANCELLED` - Cancelada
    
    **Acciones:**
    - Actualiza el estado de la orden
    - Registra fechas según el estado:
      - `IN_PICKING`: Registra fecha_inicio_picking
      - `PICKED`: Registra fecha_fin_picking
    - Crea entrada en el historial
    
    **Retorna:**
    - Detalle completo de la orden actualizada
    """
    # Buscar la orden
    order = db.query(Order).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail=f"Orden con ID {order_id} no encontrada")
    
    # Verificar que el nuevo estado existe
    new_status = db.query(OrderStatus).filter(
        OrderStatus.codigo == request.estado_codigo.upper()
    ).first()
    
    if not new_status:
        raise HTTPException(
            status_code=400,
            detail=f"Estado '{request.estado_codigo}' no es válido. Estados válidos: PENDING, ASSIGNED, IN_PICKING, PICKED, PACKING, READY, SHIPPED, CANCELLED"
        )
    
    # Guardar estado anterior
    status_anterior_id = order.status_id
    old_status = db.query(OrderStatus).filter(OrderStatus.id == status_anterior_id).first()
    
    # No hacer nada si el estado es el mismo
    if status_anterior_id == new_status.id:
        return get_order_detail(order_id, db)
    
    # Actualizar el estado
    order.status_id = new_status.id
    
    # Registrar fechas según el estado
    now = datetime.now()
    if request.estado_codigo.upper() == "IN_PICKING" and not order.fecha_inicio_picking:
        order.fecha_inicio_picking = now
    elif request.estado_codigo.upper() == "PICKED" and not order.fecha_fin_picking:
        order.fecha_fin_picking = now
    
    # Crear entrada en historial
    notas_historial = request.notas or f"Estado cambiado de {old_status.nombre if old_status else 'N/A'} a {new_status.nombre}"
    
    history = OrderHistory(
        order_id=order.id,
        status_id=new_status.id,
        operator_id=order.operator_id,
        accion="UPDATE_STATUS",
        status_anterior=status_anterior_id,
        status_nuevo=new_status.id,
        notas=notas_historial,
        fecha=now,
        event_metadata={
            "status_anterior_codigo": old_status.codigo if old_status else None,
            "status_nuevo_codigo": new_status.codigo,
            "status_anterior_nombre": old_status.nombre if old_status else None,
            "status_nuevo_nombre": new_status.nombre
        }
    )
    db.add(history)
    
    # Guardar cambios
    db.commit()
    db.refresh(order)
    
    # Retornar detalle actualizado
    return get_order_detail(order_id, db)


@router.put("/{order_id}/priority", response_model=OrderDetailFull)
def update_order_priority(
    order_id: int,
    request: UpdateOrderPriorityRequest,
    db: Session = Depends(get_db)
):
    """
    Actualiza la prioridad de una orden específica.
    
    **Parámetros:**
    - `order_id`: ID de la orden
    - `prioridad`: Nueva prioridad (en el body)
    - `notas`: Notas opcionales sobre el cambio (en el body)
    
    **Prioridades válidas:**
    - `NORMAL` - Prioridad normal
    - `HIGH` - Prioridad alta
    - `URGENT` - Prioridad urgente
    
    **Acciones:**
    - Actualiza la prioridad de la orden
    - Crea entrada en el historial
    
    **Retorna:**
    - Detalle completo de la orden actualizada
    """
    # Buscar la orden
    order = db.query(Order).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail=f"Orden con ID {order_id} no encontrada")
    
    # Validar prioridad
    prioridad_upper = request.prioridad.upper()
    if prioridad_upper not in ["NORMAL", "HIGH", "URGENT"]:
        raise HTTPException(
            status_code=400,
            detail=f"Prioridad '{request.prioridad}' no es válida. Prioridades válidas: NORMAL, HIGH, URGENT"
        )
    
    # Guardar prioridad anterior
    prioridad_anterior = order.prioridad
    
    # No hacer nada si la prioridad es la misma
    if prioridad_anterior == prioridad_upper:
        return get_order_detail(order_id, db)
    
    # Actualizar la prioridad
    order.prioridad = prioridad_upper
    
    # Crear entrada en historial
    notas_historial = request.notas or f"Prioridad cambiada de {prioridad_anterior} a {prioridad_upper}"
    
    history = OrderHistory(
        order_id=order.id,
        status_id=order.status_id,
        operator_id=order.operator_id,
        accion="UPDATE_PRIORITY",
        status_anterior=None,
        status_nuevo=None,
        notas=notas_historial,
        fecha=datetime.now(),
        event_metadata={
            "prioridad_anterior": prioridad_anterior,
            "prioridad_nueva": prioridad_upper
        }
    )
    db.add(history)
    
    # Guardar cambios
    db.commit()
    db.refresh(order)
    
    # Retornar detalle actualizado
    return get_order_detail(order_id, db)


@router.post("/{order_id}/optimize-picking-route")
def optimize_picking_route(
    order_id: int,
    db: Session = Depends(get_db)
):
    """
    Optimiza la ruta de picking para una orden usando ubicaciones reales.
    
    **Algoritmo:**
    1. Agrupa líneas por pasillo
    2. Ordena por prioridad + altura dentro de cada pasillo
    3. Genera secuencia optimizada
    
    **Retorna:**
    - Ruta optimizada con secuencia de recogida
    - Pasillos a visitar
    - Tiempo estimado
    """
    order = db.query(Order).options(
        joinedload(Order.order_lines).joinedload(OrderLine.product_location)
    ).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail=f"Orden con ID {order_id} no encontrada")
    
    if not order.order_lines:
        raise HTTPException(status_code=400, detail="La orden no tiene líneas de productos")
    
    lines_by_aisle: Dict[str, List[OrderLine]] = {}
    lines_without_location = []
    
    for line in order.order_lines:
        if line.product_location and line.product_location.activa:
            pasillo = line.product_location.pasillo
            if pasillo not in lines_by_aisle:
                lines_by_aisle[pasillo] = []
            lines_by_aisle[pasillo].append(line)
        else:
            product_name = line.product_reference.nombre_producto if line.product_reference else "Producto desconocido"
            lines_without_location.append({
                "line_id": line.id,
                "producto": product_name,
                "ean": line.ean
            })
    
    picking_route = []
    secuencia = 1
    
    for pasillo in sorted(lines_by_aisle.keys()):
        sorted_lines = sorted(
            lines_by_aisle[pasillo],
            key=lambda x: (x.product_location.prioridad, x.product_location.altura)
        )
        
        for line in sorted_lines:
            loc = line.product_location
            product = line.product_reference
            producto_nombre = product.nombre_producto if product else "Producto desconocido"
            
            picking_route.append({
                "secuencia": secuencia,
                "order_line_id": line.id,
                "producto": producto_nombre,
                "cantidad": line.cantidad_solicitada,
                "ubicacion": loc.codigo_ubicacion,
                "pasillo": loc.pasillo,
                "lado": loc.lado,
                "altura": loc.altura,
                "prioridad": loc.prioridad,
                "stock_disponible": loc.stock_actual
            })
            secuencia += 1
    
    return {
        "order_id": order_id,
        "numero_orden": order.numero_orden,
        "total_stops": len(picking_route),
        "aisles_to_visit": sorted(lines_by_aisle.keys()),
        "estimated_time_minutes": round(len(picking_route) * 1.5, 1),
        "picking_route": picking_route,
        "warnings": {
            "lines_without_location": len(lines_without_location),
            "details": lines_without_location if lines_without_location else []
        }
    }


@router.get("/{order_id}/stock-validation")
def validate_order_stock(
    order_id: int,
    db: Session = Depends(get_db)
):
    """
    Valida si hay stock suficiente para completar la orden.
    
    **Verifica:**
    - Stock disponible vs cantidad solicitada
    - Ubicaciones activas
    - Productos vinculados al catálogo
    """
    order = db.query(Order).options(
        joinedload(Order.order_lines).joinedload(OrderLine.product_location),
        joinedload(Order.order_lines).joinedload(OrderLine.product_reference)
    ).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail=f"Orden con ID {order_id} no encontrada")
    
    validation_results = []
    has_issues = False
    issues_count = {"insufficient_stock": 0, "no_location": 0, "inactive_product": 0, "inactive_location": 0}
    
    for line in order.order_lines:
        product = line.product_reference
        producto_nombre = product.nombre_producto if product else "Producto desconocido"
        
        result: Dict[str, Any] = {
            "order_line_id": line.id,
            "producto": producto_nombre,
            "cantidad_solicitada": line.cantidad_solicitada,
            "issues": []
        }
        
        if not line.product_location:
            result["issues"].append({"type": "no_location", "message": "No hay ubicación vinculada", "severity": "warning"})
            result["stock_disponible"] = None
            result["ubicacion"] = "Sin ubicación"
            has_issues = True
            issues_count["no_location"] += 1
        else:
            loc = line.product_location
            result["stock_disponible"] = loc.stock_actual
            result["ubicacion"] = loc.codigo_ubicacion
            
            if loc.stock_actual < line.cantidad_solicitada:
                result["issues"].append({
                    "type": "insufficient_stock",
                    "message": f"Stock insuficiente: {loc.stock_actual} disponible, {line.cantidad_solicitada} solicitado",
                    "severity": "error"
                })
                has_issues = True
                issues_count["insufficient_stock"] += 1
            
            if not loc.activa:
                result["issues"].append({"type": "inactive_location", "message": "La ubicación está inactiva", "severity": "warning"})
                has_issues = True
                issues_count["inactive_location"] += 1
        
        if line.product_reference and not line.product_reference.activo:
            result["issues"].append({"type": "inactive_product", "message": "El producto está inactivo", "severity": "warning"})
            has_issues = True
            issues_count["inactive_product"] += 1
        
        result["can_pick"] = len(result["issues"]) == 0
        validation_results.append(result)
    
    return {
        "order_id": order_id,
        "numero_orden": order.numero_orden,
        "can_complete": not has_issues,
        "total_lines": len(order.order_lines),
        "lines_with_issues": sum(1 for r in validation_results if not r["can_pick"]),
        "summary": issues_count,
        "validation_results": validation_results
    }


# ============================================================================
# WORKFLOW AUTOMATIZADO CON CAJAS DE EMBALAJE
# ============================================================================

@router.post("/{order_id}/start-picking")
def start_picking_with_box(
    order_id: int,
    request: StartPickingRequest,
    db: Session = Depends(get_db)
):
    """
    Inicia el proceso de picking para una orden.
    
    **Automatización:**
    1. Cambia el estado de la orden a IN_PICKING
    2. Crea automáticamente la primera caja de embalaje (Caja #1)
    3. Asigna la caja como caja activa de la orden
    4. Registra eventos en el historial
    
    **Validaciones:**
    - La orden debe existir
    - La orden debe tener operario asignado
    - La orden debe estar en estado ASSIGNED
    - No debe tener ya una caja activa
    
    **Retorna:**
    - Información de la orden actualizada
    - Información de la caja #1 creada
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"START-PICKING: Orden {order_id}, codigo_caja: '{request.codigo_caja}'")
    except Exception as e:
        logger.error(f"START-PICKING ERROR: No se pudo leer request.codigo_caja: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Body mal formado: {str(e)}"
        )
    
    # 1. Validar orden
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        logger.error(f"START-PICKING ERROR: Orden {order_id} no encontrada")
        raise HTTPException(
            status_code=404,
            detail=f"Orden con ID {order_id} no encontrada"
        )
    
    # 2. Validar estado
    status = db.query(OrderStatus).filter(OrderStatus.id == order.status_id).first()
    logger.info(f"START-PICKING: Orden {order_id} estado: {status.codigo}")
    if status.codigo != "ASSIGNED" and status.codigo != "IN_PICKING":
        logger.error(f"START-PICKING ERROR: Estado inválido {status.codigo}")
        raise HTTPException(
            status_code=400,
            detail=f"Solo se puede iniciar picking desde estado ASSIGNED o IN_PICKING. Estado actual: {status.codigo}"
        )
    
    # 3. Validar operario asignado
    logger.info(f"START-PICKING: Orden {order_id} operario: {order.operator_id}")
    if not order.operator_id:
        logger.error(f"START-PICKING ERROR: Sin operario asignado")
        raise HTTPException(
            status_code=400,
            detail="La orden debe tener un operario asignado antes de iniciar picking"
        )
    
    # 4. Cambiar estado a IN_PICKING (si no lo está ya)
    in_picking_status = db.query(OrderStatus).filter(OrderStatus.codigo == "IN_PICKING").first()
    if not in_picking_status:
        raise HTTPException(
            status_code=500,
            detail="Estado IN_PICKING no encontrado en el sistema"
        )
    
    old_status_id = order.status_id
    if order.status_id != in_picking_status.id:
        order.status_id = in_picking_status.id
        order.fecha_inicio_picking = datetime.utcnow()
    
    # 5. Validar y procesar código de caja escaneado
    codigo_caja = request.codigo_caja
    logger.info(f"START-PICKING: Buscando caja con código '{codigo_caja}'")
    
    # Validar si ya tiene una caja activa OPEN
    if order.caja_activa_id:
        current_active_box = db.query(PackingBox).filter(PackingBox.id == order.caja_activa_id).first()
        if current_active_box and current_active_box.estado == "OPEN":
            # Verificar si está intentando escanear la misma caja (retomar picking)
            if current_active_box.codigo_caja == codigo_caja:
                logger.info(f"START-PICKING: Retomando picking con la misma caja activa {order.caja_activa_id}")
                # Retornar directamente - ya está todo configurado
                total_cajas = db.query(PackingBox).filter(PackingBox.order_id == order_id).count()
                return {
                    "success": True,
                    "message": "Retomando picking con caja activa",
                    "order": {
                        "id": order.id,
                        "numero_orden": order.numero_orden,
                        "status": in_picking_status.nombre,
                        "fecha_inicio_picking": order.fecha_inicio_picking.isoformat() if order.fecha_inicio_picking else None,
                        "total_cajas": total_cajas
                    },
                    "caja": {
                        "id": current_active_box.id,
                        "numero_caja": current_active_box.numero_caja,
                        "codigo_caja": current_active_box.codigo_caja,
                        "estado": current_active_box.estado,
                        "is_new": False
                    }
                }
            else:
                # Intenta abrir caja diferente sin cerrar la actual
                logger.error(f"START-PICKING ERROR: Intenta abrir caja '{codigo_caja}' pero ya tiene caja OPEN '{current_active_box.codigo_caja}'")
                raise HTTPException(
                    status_code=400,
                    detail=f"La orden ya tiene una caja abierta (código: {current_active_box.codigo_caja}). Debe cerrarla antes de abrir una nueva."
                )
        elif current_active_box and current_active_box.estado == "CLOSED":
            logger.info(f"START-PICKING: Caja activa {order.caja_activa_id} está cerrada, permitiendo nueva caja")
            # Permitir continuar para abrir nueva caja
    
    # Buscar caja existente con ese código
    scanned_box = db.query(PackingBox).filter(
        PackingBox.codigo_caja == codigo_caja
    ).first()
    
    active_box = None
    is_new_box = False
    
    if scanned_box:
        # CAJA EXISTE - Validar estado y disponibilidad
        logger.info(f"START-PICKING: Caja encontrada - ID: {scanned_box.id}, Estado: {scanned_box.estado}, Order: {scanned_box.order_id}")
        
        if scanned_box.estado == "CLOSED":
            logger.error(f"START-PICKING ERROR: Caja '{codigo_caja}' está cerrada")
            raise HTTPException(
                status_code=400,
                detail=f"La caja '{codigo_caja}' está cerrada y no puede ser utilizada"
            )
        
        if scanned_box.order_id and scanned_box.order_id != order_id:
            logger.error(f"START-PICKING ERROR: Caja '{codigo_caja}' asignada a orden {scanned_box.order_id}")
            raise HTTPException(
                status_code=400,
                detail=f"La caja '{codigo_caja}' ya está asignada a otra orden (ID: {scanned_box.order_id})"
            )
        
        # Caja OPEN y disponible - Asignar a esta orden
        if not scanned_box.order_id:
            scanned_box.order_id = order_id
            scanned_box.operator_id = order.operator_id
        
        active_box = scanned_box
        is_new_box = False
        logger.info(f"START-PICKING: Usando caja existente {scanned_box.id}")
        
    else:
        # CAJA NO EXISTE - Crear nueva
        logger.info(f"START-PICKING: Creando nueva caja con código '{codigo_caja}'")
        
        # Calcular número de caja para esta orden
        existing_boxes_count = db.query(PackingBox).filter(
            PackingBox.order_id == order_id
        ).count()
        
        new_box = PackingBox(
            order_id=order_id,
            numero_caja=existing_boxes_count + 1,
            codigo_caja=codigo_caja,
            estado="OPEN",
            operator_id=order.operator_id,
            total_items=0,
            fecha_apertura=datetime.utcnow(),
            notas="Caja creada al iniciar/continuar picking"
        )
        db.add(new_box)
        db.flush()  # Para obtener el ID
        
        active_box = new_box
        is_new_box = True
        logger.info(f"START-PICKING: Nueva caja creada - ID: {new_box.id}")
    
    # 7. Actualizar orden con caja activa
    order.caja_activa_id = active_box.id
    
    # 8. Registrar en historial - cambio de estado (solo si cambió)
    if old_status_id != in_picking_status.id:
        history_status = OrderHistory(
            order_id=order_id,
            status_id=in_picking_status.id,
            operator_id=order.operator_id,
            accion="STATUS_CHANGE",
            status_anterior=old_status_id,
            status_nuevo=in_picking_status.id,
            notas=f"Picking iniciado. Estado cambiado a IN_PICKING",
            fecha=datetime.utcnow()
        )
        db.add(history_status)
    
    # 9. Registrar en historial - caja asignada
    history_box = OrderHistory(
        order_id=order_id,
        status_id=in_picking_status.id,
        operator_id=order.operator_id,
        accion="BOX_OPENED" if is_new_box else "BOX_ASSIGNED",
        notas=f"Caja #{active_box.numero_caja} {'creada' if is_new_box else 'asignada'}. Código: {codigo_caja}",
        fecha=datetime.utcnow(),
        event_metadata={
            "packing_box_id": active_box.id,
            "numero_caja": active_box.numero_caja,
            "codigo_caja": codigo_caja,
            "is_new_box": is_new_box
        }
    )
    db.add(history_box)
    
    db.commit()
    db.refresh(order)
    db.refresh(active_box)
    
    logger.info(f"START-PICKING SUCCESS: Orden {order_id} con caja '{codigo_caja}' ({'nueva' if is_new_box else 'existente'})")
    
    # Calcular total de cajas dinámicamente
    total_cajas = db.query(PackingBox).filter(PackingBox.order_id == order_id).count()
    
    return {
        "success": True,
        "message": f"Picking {'iniciado' if old_status_id != in_picking_status.id else 'continuado'} exitosamente",
        "order": {
            "id": order.id,
            "numero_orden": order.numero_orden,
            "status": in_picking_status.nombre,
            "fecha_inicio_picking": order.fecha_inicio_picking.isoformat() if order.fecha_inicio_picking else None,
            "total_cajas": total_cajas
        },
        "caja": {
            "id": active_box.id,
            "numero_caja": active_box.numero_caja,
            "codigo_caja": active_box.codigo_caja,
            "estado": active_box.estado,
            "is_new": is_new_box
        }
    }


@router.post("/{order_id}/complete-picking")
def complete_picking_with_boxes(
    order_id: int,
    db: Session = Depends(get_db)
):
    """
    Completa el proceso de picking para una orden.
    
    **Automatización:**
    1. Valida que todos los items estén empacados
    2. Cierra automáticamente la caja activa si existe
    3. Cambia el estado de la orden a PICKED
    4. Registra fecha de fin de picking
    5. Registra eventos en el historial
    
    **Validaciones:**
    - La orden debe existir
    - La orden debe estar en estado IN_PICKING
    - Todos los items deben estar empacados (packing_box_id no NULL)
    - Al menos una caja debe existir
    
    **Retorna:**
    - Información de la orden actualizada
    - Resumen de cajas cerradas
    """
    # 1. Validar orden
    order = db.query(Order).options(
        joinedload(Order.order_lines)
    ).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(
            status_code=404,
            detail=f"Orden con ID {order_id} no encontrada"
        )
    
    # 2. Validar estado
    status = db.query(OrderStatus).filter(OrderStatus.id == order.status_id).first()
    if status.codigo != "IN_PICKING":
        raise HTTPException(
            status_code=400,
            detail=f"Solo se puede completar picking desde estado IN_PICKING. Estado actual: {status.codigo}"
        )
    
    # 3. Validar que todos los items estén empacados
    unpacked_items = [
        line for line in order.order_lines 
        if line.packing_box_id is None
    ]
    
    if unpacked_items:
        raise HTTPException(
            status_code=400,
            detail=f"No se puede completar picking. {len(unpacked_items)} items sin empacar. "
                   f"Todos los items deben estar en una caja antes de completar."
        )
    
    # 4. Validar que exista al menos una caja
    boxes_count = db.query(PackingBox).filter(PackingBox.order_id == order_id).count()
    if boxes_count == 0:
        raise HTTPException(
            status_code=400,
            detail="No se puede completar picking. La orden no tiene ninguna caja creada."
        )
    
    # 5. Cerrar caja activa si existe
    closed_box_info = None
    if order.caja_activa_id:
        active_box = db.query(PackingBox).filter(PackingBox.id == order.caja_activa_id).first()
        if active_box and active_box.estado == "OPEN":
            active_box.estado = "CLOSED"
            active_box.fecha_cierre = datetime.utcnow()
            
            closed_box_info = {
                "id": active_box.id,
                "numero_caja": active_box.numero_caja,
                "codigo_caja": active_box.codigo_caja,
                "total_items": active_box.total_items
            }
            
            # Registrar cierre de caja
            history_box_close = OrderHistory(
                order_id=order_id,
                status_id=order.status_id,
                operator_id=order.operator_id,
                accion="BOX_CLOSED",
                notas=f"Caja #{active_box.numero_caja} cerrada automáticamente al completar picking. "
                      f"{active_box.total_items} items empacados.",
                fecha=datetime.utcnow(),
                event_metadata={
                    "packing_box_id": active_box.id,
                    "numero_caja": active_box.numero_caja,
                    "total_items": active_box.total_items,
                    "auto_closed": True
                }
            )
            db.add(history_box_close)
        
        order.caja_activa_id = None
    
    # 6. Cambiar estado a PICKED
    picked_status = db.query(OrderStatus).filter(OrderStatus.codigo == "PICKED").first()
    if not picked_status:
        raise HTTPException(
            status_code=500,
            detail="Estado PICKED no encontrado en el sistema"
        )
    
    old_status_id = order.status_id
    order.status_id = picked_status.id
    order.fecha_fin_picking = datetime.utcnow()
    
    # 7. Registrar en historial - cambio de estado
    history_status = OrderHistory(
        order_id=order_id,
        status_id=picked_status.id,
        operator_id=order.operator_id,
        accion="PICKING_COMPLETED",
        status_anterior=old_status_id,
        status_nuevo=picked_status.id,
        notas=f"Picking completado. {order.total_cajas} cajas creadas.",
        fecha=datetime.utcnow(),
        event_metadata={
            "total_cajas": order.total_cajas,
            "total_items": order.total_items,
            "items_completados": order.items_completados
        }
    )
    db.add(history_status)
    
    db.commit()
    db.refresh(order)
    
    # 8. Obtener resumen de cajas
    all_boxes = db.query(PackingBox).filter(PackingBox.order_id == order_id).all()
    boxes_summary = [
        {
            "numero_caja": box.numero_caja,
            "codigo_caja": box.codigo_caja,
            "estado": box.estado,
            "total_items": box.total_items
        }
        for box in all_boxes
    ]
    
    return {
        "success": True,
        "message": "Picking completado exitosamente",
        "order": {
            "id": order.id,
            "numero_orden": order.numero_orden,
            "status": picked_status.nombre,
            "fecha_inicio_picking": order.fecha_inicio_picking.isoformat() if order.fecha_inicio_picking else None,
            "fecha_fin_picking": order.fecha_fin_picking.isoformat(),
            "total_cajas": order.total_cajas,
            "total_items": order.total_items,
            "items_completados": order.items_completados
        },
        "caja_cerrada_automaticamente": closed_box_info,
        "resumen_cajas": boxes_summary
    }


# ============================================================================
# CONSULTA DE DISTRIBUCIÓN DE PRODUCTOS EN CAJAS
# ============================================================================

@router.get("/{order_id}/packing-distribution", response_model=OrderPackingDistribution)
def get_order_packing_distribution(
    order_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene la orden con la distribución completa de productos en cajas.
    
    **Retorna:**
    - Información general de la orden
    - Lista de cajas con productos distribuidos
    - Resumen ejecutivo de empaque
    
    **Casos de Uso:**
    - Ver trazabilidad completa de qué productos están en cada caja
    - Verificar distribución antes de enviar
    - Auditoría de empaque
    - Reporte de cajas para logística
    """
    # Obtener orden con cajas
    order = db.query(Order).options(
        joinedload(Order.status),
        joinedload(Order.operator)
    ).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(
            status_code=404,
            detail=f"Orden con ID {order_id} no encontrada"
        )
    
    # Obtener todas las cajas de la orden
    cajas = db.query(PackingBox).filter(
        PackingBox.order_id == order_id
    ).order_by(PackingBox.numero_caja.asc()).all()
    
    # Obtener todas las líneas de la orden para cálculos
    order_lines = db.query(OrderLine).filter(
        OrderLine.order_id == order_id
    ).all()
    
    total_productos = sum(line.cantidad_solicitada for line in order_lines)
    productos_empacados = sum(line.cantidad_servida for line in order_lines)
    productos_pendientes = total_productos - productos_empacados
    
    # Construir respuesta de cajas con distribuciones
    cajas_response = []
    total_items_empacados = 0
    productos_distribuidos_set = set()
    
    for caja in cajas:
        # Obtener distribuciones de esta caja
        distributions = db.query(OrderLineBoxDistribution).options(
            joinedload(OrderLineBoxDistribution.order_line).joinedload(OrderLine.product_reference)
        ).filter(
            OrderLineBoxDistribution.packing_box_id == caja.id
        ).all()
        
        # Construir lista de productos en esta caja
        productos_en_caja = []
        for dist in distributions:
            order_line = dist.order_line
            product_ref = order_line.product_reference
            
            # Calcular porcentaje de esta línea en esta caja
            porcentaje = (dist.quantity_in_box / order_line.cantidad_solicitada * 100) if order_line.cantidad_solicitada > 0 else 0
            
            productos_en_caja.append(ProductInBox(
                order_line_id=order_line.id,
                producto_id=order_line.product_reference_id,
                producto_nombre=product_ref.nombre_producto if product_ref else "Producto desconocido",
                color=product_ref.nombre_color if product_ref else None,
                talla=product_ref.talla if product_ref else None,
                sku=product_ref.sku if product_ref else None,
                ean=order_line.ean,
                cantidad_en_caja=dist.quantity_in_box,
                cantidad_total_solicitada=order_line.cantidad_solicitada,
                porcentaje_en_caja=round(porcentaje, 2),
                fecha_empacado=dist.fecha_empacado
            ))
            
            total_items_empacados += dist.quantity_in_box
            productos_distribuidos_set.add(order_line.id)
        
        cajas_response.append(BoxDistribution(
            id=caja.id,
            numero_caja=caja.numero_caja,
            codigo_caja=caja.codigo_caja,
            estado=caja.estado,
            total_items=caja.total_items,
            peso_kg=caja.peso_kg,
            dimensiones=caja.dimensiones,
            fecha_apertura=caja.fecha_apertura,
            fecha_cierre=caja.fecha_cierre,
            productos=productos_en_caja
        ))
    
    # Construir información de la orden
    order_info = {
        "id": order.id,
        "numero_orden": order.numero_orden,
        "cliente": order.cliente,
        "nombre_cliente": order.nombre_cliente,
        "estado": order.status.codigo if order.status else "UNKNOWN",
        "total_cajas": len(cajas),  # Calcular dinámicamente
        "caja_activa_id": order.caja_activa_id,
        "total_productos": total_productos,
        "productos_empacados": productos_empacados,
        "productos_pendientes": productos_pendientes,
        "operario": order.operator.nombre if order.operator else None,
        "fecha_inicio_picking": order.fecha_inicio_picking.isoformat() if order.fecha_inicio_picking else None,
        "fecha_fin_picking": order.fecha_fin_picking.isoformat() if order.fecha_fin_picking else None
    }
    
    # Resumen ejecutivo
    cajas_abiertas = sum(1 for c in cajas if c.estado == "OPEN")
    cajas_cerradas = sum(1 for c in cajas if c.estado == "CLOSED")
    
    resumen = {
        "total_cajas": len(cajas),
        "cajas_abiertas": cajas_abiertas,
        "cajas_cerradas": cajas_cerradas,
        "total_items_empacados": total_items_empacados,
        "productos_distribuidos": len(productos_distribuidos_set),
        "productos_pendientes": len(order_lines) - len(productos_distribuidos_set),
        "completado": productos_pendientes == 0
    }
    
    return OrderPackingDistribution(
        order=order_info,
        cajas=cajas_response,
        resumen=resumen
    )