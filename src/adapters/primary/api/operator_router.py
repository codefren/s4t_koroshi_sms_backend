"""
Router para gestión de operarios.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import case
from typing import List, Optional
from datetime import datetime

from src.adapters.secondary.database.config import get_db, ALMACEN_PICKING_ID
from src.adapters.secondary.database.orm import (
    Operator, Order, OrderStatus, OrderLine, OrderHistory, 
    PackingBox, ProductLocation, ProductReference, OrderLineStockAssignment
)
from src.core.domain.models import (
    OperatorResponse,
    OperatorCreate,
    OperatorUpdate,
    VerifyOperatorResponse,
    OperatorOrderItem,
    OrderSummaryResponse,
    OrderLineListItem,
    ResetOrderLineResponse,
    OperatorStartPickingResponse
)

router = APIRouter(prefix="/operators", tags=["Operators"])


@router.get("/", response_model=List[OperatorResponse])
def list_operators(
    activo: Optional[bool] = Query(None, description="Filtrar por operarios activos/inactivos"),
    db: Session = Depends(get_db)
):
    """
    Lista todos los operarios del sistema.
    
    **Parámetros opcionales:**
    - `activo`: Filtrar por operarios activos (true) o inactivos (false)
    
    **Retorna:**
    - Lista de operarios con su información completa
    """
    query = db.query(Operator)
    
    # Aplicar filtro de activo si se especifica
    if activo is not None:
        query = query.filter(Operator.activo == activo)
    
    # Ordenar por nombre
    query = query.order_by(Operator.nombre)
    
    operators = query.all()
    
    return operators


@router.get("/verify/{codigo}", response_model=VerifyOperatorResponse)
def verify_operator_by_code(
    codigo: str,
    db: Session = Depends(get_db)
):
    """
    Verifica si existe un operario con el código especificado.
    
    **Parámetros:**
    - `codigo`: Código del operario (ej: "21", "OP001", "OP002")
    
    **Retorna:**
    - Información del operario si existe
    - 404 si no existe
    
    **Ejemplo:**
    ```
    GET /api/v1/operators/verify/21
    ```
    """
    operator = db.query(Operator).filter(Operator.codigo == codigo).first()
    
    if not operator:
        raise HTTPException(
            status_code=404,
            detail=f"Operario con código '{codigo}' no encontrado"
        )
    
    return {
        "exists": True,
        "operator": {
            "id": operator.id,
            "codigo": operator.codigo,
            "nombre": operator.nombre,
            "activo": operator.activo,
            "created_at": operator.created_at.isoformat() if operator.created_at else None
        }
    }


@router.get("/{operator_id}", response_model=OperatorResponse)
def get_operator(
    operator_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene los detalles de un operario específico.
    
    **Parámetros:**
    - `operator_id`: ID del operario
    
    **Retorna:**
    - Información completa del operario
    """
    operator = db.query(Operator).filter(Operator.id == operator_id).first()
    
    if not operator:
        raise HTTPException(status_code=404, detail=f"Operario con ID {operator_id} no encontrado")
    
    return operator


@router.post("/", response_model=OperatorResponse, status_code=201)
def create_operator(
    operator_data: OperatorCreate,
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo operario en el sistema.
    
    **Body (JSON):**
    ```json
    {
        "codigo_operario": "OP005",
        "nombre": "Carlos Martínez",
        "activo": true
    }
    ```
    
    **Validaciones:**
    - El `codigo_operario` debe ser único
    - El `nombre` no puede estar vacío
    - Por defecto se crea como activo
    
    **Retorna:**
    - Información completa del operario creado
    """
    # Verificar que el código de operario no exista
    existing_operator = db.query(Operator).filter(
        Operator.codigo == operator_data.codigo_operario
    ).first()
    
    if existing_operator:
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe un operario con el código '{operator_data.codigo_operario}'"
        )
    
    # Crear nuevo operario
    new_operator = Operator(
        codigo=operator_data.codigo_operario,
        nombre=operator_data.nombre,
        activo=operator_data.activo
    )
    
    db.add(new_operator)
    db.commit()
    db.refresh(new_operator)
    
    return new_operator


@router.put("/{operator_id}", response_model=OperatorResponse)
def update_operator(
    operator_id: int,
    operator_data: OperatorUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualiza la información de un operario existente.
    
    **Parámetros:**
    - `operator_id`: ID del operario
    
    **Body (JSON) - Todos los campos son opcionales:**
    ```json
    {
        "nombre": "Carlos Martínez García",
        "activo": true
    }
    ```
    
    **Nota:** No se puede cambiar el `codigo_operario`
    
    **Retorna:**
    - Información actualizada del operario
    """
    # Buscar el operario
    operator = db.query(Operator).filter(Operator.id == operator_id).first()
    
    if not operator:
        raise HTTPException(
            status_code=404,
            detail=f"Operario con ID {operator_id} no encontrado"
        )
    
    # Actualizar solo los campos que se enviaron
    update_data = operator_data.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(operator, field, value)
    
    db.commit()
    db.refresh(operator)
    
    return operator


@router.patch("/{operator_id}/toggle-status", response_model=OperatorResponse)
def toggle_operator_status(
    operator_id: int,
    db: Session = Depends(get_db)
):
    """
    Activa o desactiva un operario (toggle del campo activo).
    
    **Parámetros:**
    - `operator_id`: ID del operario
    
    **Acción:**
    - Si está activo → lo desactiva
    - Si está inactivo → lo activa
    
    **Nota:** Este es un soft delete. El operario no se elimina de la base de datos.
    
    **Retorna:**
    - Información actualizada del operario
    """
    # Buscar el operario
    operator = db.query(Operator).filter(Operator.id == operator_id).first()
    
    if not operator:
        raise HTTPException(
            status_code=404,
            detail=f"Operario con ID {operator_id} no encontrado"
        )
    
    # Cambiar el estado
    operator.activo = not operator.activo
    
    db.commit()
    db.refresh(operator)
    
    return operator


# ============================================================================
# ENDPOINTS PARA GESTIÓN DE ÓRDENES DEL OPERARIO (PDA)
# ============================================================================

@router.get("/{operator_codigo}/orders", response_model=List[OperatorOrderItem])
def list_operator_orders(
    operator_codigo: str,
    db: Session = Depends(get_db)
):
    """
    Lista todas las órdenes asignadas a un operario.
    
    **Parámetros:**
    - `operator_codigo`: Código del operario (ej: "OP001", "OP002")
    
    **Retorna:**
    - Lista de órdenes con información básica
    - **Ordenamiento:** STOPPED primero, luego por prioridad (URGENT → HIGH → NORMAL), luego por fecha
    """
    # Buscar operario por código
    operator = db.query(Operator).filter(Operator.codigo == operator_codigo).first()
    if not operator:
        raise HTTPException(
            status_code=404,
            detail=f"Operario con código '{operator_codigo}' no encontrado"
        )
    
    # Obtener órdenes asignadas al operario
    # Ordenar: STOPPED primero, luego por prioridad (URGENT → HIGH → NORMAL → LOW), luego por fecha de creación
    
    # Obtener IDs de estados válidos (ASSIGNED, IN_PICKING, STOPPED)
    valid_statuses = db.query(OrderStatus.id).filter(
        OrderStatus.codigo.in_(['ASSIGNED', 'IN_PICKING', 'STOPPED'])
    ).all()
    valid_status_ids = [s.id for s in valid_statuses]
    
    # Ordenamiento: STOPPED primero
    stopped_first = case(
        (OrderStatus.codigo == 'STOPPED', 0),
        else_=1
    )
    
    # Ordenamiento: prioridad
    priority_order = case(
        (Order.prioridad == 'URGENT', 1),
        (Order.prioridad == 'HIGH', 2),
        (Order.prioridad == 'NORMAL', 3),
        (Order.prioridad == 'LOW', 4),
        else_=5
    )
    
    orders = db.query(Order).join(OrderStatus).filter(
        Order.operator_id == operator.id
    ).filter(
        Order.status_id.in_(valid_status_ids)
    ).order_by(
        stopped_first.asc(),
        priority_order.asc(),
        Order.created_at.desc()
    ).all()
    
    # Formatear respuesta
    result = []
    for order in orders:
        result.append({
            "id": order.id,
            "numero_orden": order.numero_orden,
            "prioridad": order.prioridad,
            "estado": order.status.codigo if order.status else None,
            "total_items": order.total_items,
            "items_completados": order.items_completados,
            "nombre_cliente": order.nombre_cliente,
            "progreso": round((order.items_completados / order.total_items * 100) if order.total_items > 0 else 0, 2),
            "fecha_asignacion": order.fecha_asignacion.isoformat() if order.fecha_asignacion else None,
            "created_at": order.created_at.isoformat()
        })
    
    return result


@router.get("/{operator_codigo}/orders/{order_id}/summary", response_model=OrderSummaryResponse)
def get_order_summary(
    operator_codigo: str,
    order_id: int,
    db: Session = Depends(get_db)
):
    """
    Resumen de una orden asignada a un operario.
    
    **Retorna:**
    - total_productos: suma de cantidad_solicitada de todas las líneas
    - total_servido: suma de cantidad_servida de todas las líneas
    - fecha_asignacion: fecha en que se asignó al operario
    - prioridad: prioridad de la orden
    - progreso: porcentaje completado (servido / solicitado)
    """
    operator = db.query(Operator).filter(Operator.codigo == operator_codigo).first()
    if not operator:
        raise HTTPException(
            status_code=404,
            detail=f"Operario con código '{operator_codigo}' no encontrado"
        )
    
    order = db.query(Order).options(
        joinedload(Order.order_lines),
        joinedload(Order.status),
        joinedload(Order.caja_activa)
    ).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(
            status_code=404,
            detail=f"Orden con ID {order_id} no encontrada"
        )
    
    if order.operator_id != operator.id:
        raise HTTPException(
            status_code=403,
            detail="Esta orden no está asignada a este operario"
        )
    
    total_solicitado = sum(line.cantidad_solicitada for line in order.order_lines)
    total_servido = sum(line.cantidad_servida for line in order.order_lines)
    progreso = round((total_servido / total_solicitado * 100) if total_solicitado > 0 else 0, 2)
    
    # Obtener información de la caja activa si existe
    caja_activa = None
    if order.caja_activa:
        caja_activa = {
            "id": order.caja_activa.id,
            "numero_caja": order.caja_activa.numero_caja,
            "codigo_caja": order.caja_activa.codigo_caja,
            "estado": order.caja_activa.estado,
            "total_items": order.caja_activa.total_items
        }
    
    return {
        "order_id": order.id,
        "numero_orden": order.numero_orden,
        "estado": order.status.codigo if order.status else "UNKNOWN",
        "total_productos": total_solicitado,
        "total_servido": total_servido,
        "fecha_asignacion": order.fecha_asignacion.isoformat() if order.fecha_asignacion else None,
        "prioridad": order.prioridad,
        "progreso": progreso,
        "caja_activa": caja_activa
    }


@router.get("/{operator_codigo}/orders/{order_id}/lines", response_model=List[OrderLineListItem])
def list_order_lines(
    operator_codigo: str,
    order_id: int,
    ultimos: Optional[bool] = Query(False, description="Si es true, retorna solo los últimos 3 registros actualizados"),
    db: Session = Depends(get_db)
):
    """
    Lista todos los productos (líneas) de una orden específica.
    
    **Parámetros:**
    - `operator_codigo`: Código del operario (ej: "OP001", "OP002")
    - `order_id`: ID de la orden
    - `ultimos`: (Opcional) Si es true, retorna solo los últimos 3 registros actualizados por fecha de actualización
    
    **Retorna:**
    - Lista de productos con cantidades y ubicaciones
    - Si `ultimos=true`: Solo los últimos 3 registros actualizados (ordenados por updated_at desc)
    - Si `ultimos=false` o no especificado: Todos los registros de la orden
    """
    # Buscar operario por código
    operator = db.query(Operator).filter(Operator.codigo == operator_codigo).first()
    if not operator:
        raise HTTPException(
            status_code=404,
            detail=f"Operario con código '{operator_codigo}' no encontrado"
        )
    
    # Verificar que la orden existe y está asignada al operario
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=404,
            detail=f"Orden con ID {order_id} no encontrada"
        )
    
    if order.operator_id != operator.id:
        raise HTTPException(
            status_code=403,
            detail="Esta orden no está asignada a este operario"
        )
    
    # Obtener líneas de la orden
    query = db.query(OrderLine).filter(
        OrderLine.order_id == order_id
    )
    
    # Si se solicita solo los últimos 3 actualizados
    if ultimos:
        query = query.order_by(OrderLine.updated_at.desc()).limit(3)
    
    lines = query.all()
    
    # Formatear respuesta
    result = []
    for line in lines:
        ubicacion_id = None
        ubicacion = None
        asignaciones = []
        
        # Buscar assignments para esta línea (multi-ubicación)
        assignments = (
            db.query(OrderLineStockAssignment)
            .filter_by(order_line_id=line.id)
            .all()
        )
        
        if assignments:
            for a in assignments:
                loc = db.get(ProductLocation, a.product_location_id)
                if loc:
                    asignaciones.append({
                        "product_location_id": loc.id,
                        "codigo": loc.codigo_ubicacion,
                        "pasillo": loc.pasillo,
                        "lado": loc.lado,
                        "ubicacion": loc.ubicacion,
                        "altura": loc.altura,
                        "stock_actual": loc.stock_actual,
                        "cantidad_reservada": a.cantidad_reservada,
                        "cantidad_servida": a.cantidad_servida,
                    })
            # Ubicación principal = primera asignación
            if asignaciones:
                ubicacion_id = asignaciones[0]["product_location_id"]
                ubicacion = {
                    "codigo": asignaciones[0]["codigo"],
                    "pasillo": asignaciones[0]["pasillo"],
                    "lado": asignaciones[0]["lado"],
                    "ubicacion": asignaciones[0]["ubicacion"],
                    "altura": asignaciones[0]["altura"],
                    "stock_actual": asignaciones[0]["stock_actual"],
                    "stock_minimo": None
                }
        elif line.product_reference_id:
            # Fallback: buscar la mejor ubicación en el almacén de picking
            picking_location = db.query(ProductLocation).filter(
                ProductLocation.product_id == line.product_reference_id,
                ProductLocation.almacen_id == ALMACEN_PICKING_ID,
                ProductLocation.activa == True
            ).order_by(
                ProductLocation.prioridad.asc(),
                ProductLocation.stock_actual.desc()
            ).first()
            
            if picking_location:
                ubicacion_id = picking_location.id
                ubicacion = {
                    "codigo": picking_location.codigo_ubicacion,
                    "pasillo": picking_location.pasillo,
                    "lado": picking_location.lado,
                    "ubicacion": picking_location.ubicacion,
                    "altura": picking_location.altura,
                    "stock_actual": picking_location.stock_actual,
                    "stock_minimo": picking_location.stock_minimo
                }
        
        # Información del producto
        producto = None
        if line.product_reference:
            producto = {
                "nombre": line.product_reference.nombre_producto,
                "color": line.product_reference.nombre_color,
                "talla": line.product_reference.talla,
                "sku": line.product_reference.sku
            }
        
        line_data = {
            "id": line.id,
            "producto_id": line.product_reference_id,
            "ubicacion_id": ubicacion_id,
            "ean": line.ean,
            "producto": producto,
            "ubicacion": ubicacion,
            "cantidad_solicitada": line.cantidad_solicitada,
            "cantidad_servida": line.cantidad_servida,
            "cantidad_pendiente": line.cantidad_solicitada - line.cantidad_servida,
            "estado": line.estado,
            "progreso": round((line.cantidad_servida / line.cantidad_solicitada * 100) if line.cantidad_solicitada > 0 else 0, 2)
        }
        
        # Incluir asignaciones multi-ubicación si existen
        if asignaciones:
            line_data["asignaciones"] = asignaciones
        
        result.append(line_data)
    
    return result


@router.put("/{operator_codigo}/orders/{order_id}/lines/{order_line_id}/reset", response_model=ResetOrderLineResponse)
def reset_order_line_quantity(
    operator_codigo: str,
    order_id: int,
    order_line_id: int,
    db: Session = Depends(get_db)
):
    """
    Resetea la cantidad servida de una línea de orden a 0.
    
    **Parámetros:**
    - `operator_codigo`: Código del operario (ej: "OP001", "OP002")
    - `order_id`: ID de la orden
    - `order_line_id`: ID de la línea de orden a resetear
    
    **Acción:**
    - Resetea `cantidad_servida` a 0
    - Cambia el estado de la línea a 'PENDING'
    - Registra el cambio en el historial
    
    **Retorna:**
    - Información actualizada de la línea
    """
    # Buscar operario por código
    operator = db.query(Operator).filter(Operator.codigo == operator_codigo).first()
    if not operator:
        raise HTTPException(
            status_code=404,
            detail=f"Operario con código '{operator_codigo}' no encontrado"
        )
    
    # Verificar que la orden existe y está asignada al operario
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=404,
            detail=f"Orden con ID {order_id} no encontrada"
        )
    
    if order.operator_id != operator.id:
        raise HTTPException(
            status_code=403,
            detail="Esta orden no está asignada a este operario"
        )
    
    # Verificar que la línea de orden existe y pertenece a la orden
    order_line = db.query(OrderLine).filter(
        OrderLine.id == order_line_id,
        OrderLine.order_id == order_id
    ).first()
    
    if not order_line:
        raise HTTPException(
            status_code=404,
            detail=f"Línea de orden con ID {order_line_id} no encontrada en la orden {order_id}"
        )
    
    # Guardar valores anteriores para el historial
    cantidad_servida_anterior = order_line.cantidad_servida
    estado_anterior = order_line.estado
    
    # Resetear cantidad servida a 0 y cambiar estado a PENDING
    order_line.cantidad_servida = 0
    order_line.estado = 'PENDING'
    
    # Registrar cambio en el historial
    history = OrderHistory(
        order_id=order_id,
        status_id=order.status_id,
        operator_id=operator.id,
        event_type="LINE_RESET",
        accion="LINE_RESET",
        notas=f"Cantidad servida reseteada de {cantidad_servida_anterior} a 0. Estado cambiado de {estado_anterior} a PENDING",
        fecha=datetime.utcnow(),
        event_metadata={
            "order_line_id": order_line_id,
            "cantidad_servida_anterior": cantidad_servida_anterior,
            "estado_anterior": estado_anterior,
            "ean": order_line.ean
        }
    )
    db.add(history)
    
    db.commit()
    db.refresh(order_line)
    
    return {
        "success": True,
        "message": "Cantidad servida reseteada exitosamente",
        "order_line": {
            "id": order_line.id,
            "order_id": order_line.order_id,
            "ean": order_line.ean,
            "cantidad_solicitada": order_line.cantidad_solicitada,
            "cantidad_servida": order_line.cantidad_servida,
            "cantidad_pendiente": order_line.cantidad_solicitada - order_line.cantidad_servida,
            "estado": order_line.estado,
            "cantidad_servida_anterior": cantidad_servida_anterior,
            "estado_anterior": estado_anterior
        }
    }


@router.post("/{operator_codigo}/orders/{order_id}/start-picking", response_model=OperatorStartPickingResponse)
def start_picking(
    operator_codigo: str,
    order_id: int,
    db: Session = Depends(get_db)
):
    """
    Inicia el proceso de picking de una orden.
    
    **Parámetros:**
    - `operator_codigo`: Código del operario (ej: "OP001", "OP002")
    - `order_id`: ID de la orden
    
    **Acción:**
    - Cambia el estado de la orden a IN_PICKING
    - Registra la fecha de inicio de picking
    
    **Retorna:**
    - Información actualizada de la orden
    """
    # Buscar operario por código
    operator = db.query(Operator).filter(Operator.codigo == operator_codigo).first()
    if not operator:
        raise HTTPException(
            status_code=404,
            detail=f"Operario con código '{operator_codigo}' no encontrado"
        )
    
    # Verificar que la orden existe y está asignada al operario
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=404,
            detail=f"Orden con ID {order_id} no encontrada"
        )
    
    if order.operator_id != operator.id:
        raise HTTPException(
            status_code=403,
            detail="Esta orden no está asignada a este operario"
        )
    
    # Verificar estado actual
    # Si ya está en IN_PICKING, devolver respuesta exitosa (idempotente)
    if order.status.codigo == "IN_PICKING":
        return {
            "message": "La orden ya está en proceso de picking",
            "order_id": order.id,
            "numero_orden": order.numero_orden,
            "estado": order.status.codigo,
            "fecha_inicio_picking": order.fecha_inicio_picking.isoformat() if order.fecha_inicio_picking else None
        }
    
    # Si no está en estado válido para iniciar picking
    if order.status.codigo not in ["PENDING", "ASSIGNED", "STOPPED"]:
        raise HTTPException(
            status_code=400,
            detail=f"No se puede iniciar picking. Estado actual: {order.status.codigo}. Estados válidos: PENDING, ASSIGNED, STOPPED"
        )
    
    # Cambiar estado a IN_PICKING
    in_picking_status = db.query(OrderStatus).filter(
        OrderStatus.codigo == "IN_PICKING"
    ).first()
    
    if not in_picking_status:
        raise HTTPException(
            status_code=500,
            detail="Estado IN_PICKING no encontrado en el sistema"
        )
    
    # Guardar estado anterior para historial
    old_status_id = order.status_id
    old_status = db.query(OrderStatus).filter(OrderStatus.id == old_status_id).first()
    
    order.status_id = in_picking_status.id
    # Solo establecer fecha_inicio_picking si no existe (primera vez, no retomando desde STOPPED)
    if not order.fecha_inicio_picking:
        order.fecha_inicio_picking = datetime.utcnow()
    
    # Registrar cambio de estado en historial
    history = OrderHistory(
        order_id=order.id,
        status_id=in_picking_status.id,
        operator_id=operator.id,
        event_type="STATUS_CHANGE",
        accion="STATUS_CHANGE",
        status_anterior=old_status_id,
        status_nuevo=in_picking_status.id,
        notas=f"Picking {'retomado' if old_status and old_status.codigo == 'STOPPED' else 'iniciado'}. Estado cambiado de {old_status.codigo if old_status else 'N/A'} a IN_PICKING",
        fecha=datetime.utcnow(),
        event_metadata={
            "resumed": old_status and old_status.codigo == "STOPPED"
        }
    )
    db.add(history)
    
    db.commit()
    db.refresh(order)
    
    return {
        "message": f"Picking {'retomado' if old_status and old_status.codigo == 'STOPPED' else 'iniciado'} correctamente",
        "order_id": order.id,
        "numero_orden": order.numero_orden,
        "estado": order.status.codigo,
        "fecha_inicio_picking": order.fecha_inicio_picking.isoformat()
    }
