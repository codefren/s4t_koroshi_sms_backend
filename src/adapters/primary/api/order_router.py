"""
Router para gestión de órdenes.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from src.adapters.secondary.database.config import get_db
from src.adapters.secondary.database.orm import Order, OrderStatus, Operator, OrderLine, OrderHistory
from src.core.domain.models import (
    OrderListItem, 
    OrderDetailFull, 
    OrderProductDetail,
    AssignOperatorRequest,
    UpdateOrderStatusRequest
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
    - Cantidad total de items
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
        order_data = {
            "id": row.id,
            "numero_orden": row.numero_orden,
            "cliente": row.cliente,
            "nombre_cliente": row.nombre_cliente,
            "total_items": row.total_items,
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
    # Buscar la orden
    order = db.query(Order).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(status_code=404, detail=f"Orden con ID {order_id} no encontrada")
    
    # Obtener el estado
    status = db.query(OrderStatus).filter(OrderStatus.id == order.status_id).first()
    
    # Obtener el operario si existe
    operator = None
    if order.operator_id:
        operator = db.query(Operator).filter(Operator.id == order.operator_id).first()
    
    # Obtener todas las líneas de la orden
    order_lines = db.query(OrderLine).filter(OrderLine.order_id == order_id).all()
    
    # Construir lista de productos
    productos = []
    for line in order_lines:
        producto = OrderProductDetail(
            id=line.id,
            nombre=line.descripcion_producto,
            descripcion=line.descripcion_color,
            color=line.color,
            talla=line.talla,
            ubicacion=line.ubicacion if line.ubicacion else "Sin ubicación",
            sku=line.articulo,
            ean=line.ean,
            cantidad_solicitada=line.cantidad_solicitada,
            cantidad_servida=line.cantidad_servida,
            estado=line.estado
        )
        productos.append(producto)
    
    # Calcular progreso
    progreso = 0.0
    if order.total_items > 0:
        progreso = round((order.items_completados / order.total_items) * 100, 2)
    
    # Construir respuesta
    order_detail = OrderDetailFull(
        id=order.id,
        numero_orden=order.numero_orden,
        cliente=order.cliente,
        nombre_cliente=order.nombre_cliente,
        fecha_creacion=order.fecha_orden,
        fecha_limite="Sin fecha límite",
        total_cajas=order.caja if order.caja else "Sin cajas",
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
            "operator_codigo": operator.codigo_operario,
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