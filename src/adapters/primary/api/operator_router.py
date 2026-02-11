"""
Router para gestión de operarios.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from src.adapters.secondary.database.config import get_db
from src.adapters.secondary.database.orm import Operator, Order, OrderLine, OrderStatus, ProductLocation
from src.core.domain.models import (
    OperatorResponse,
    OperatorCreate,
    OperatorUpdate
)
from datetime import datetime

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

@router.get("/{operator_codigo}/orders")
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
    """
    # Buscar operario por código
    operator = db.query(Operator).filter(Operator.codigo == operator_codigo).first()
    if not operator:
        raise HTTPException(
            status_code=404,
            detail=f"Operario con código '{operator_codigo}' no encontrado"
        )
    
    # Obtener órdenes asignadas al operario
    orders = db.query(Order).filter(
        Order.operator_id == operator.id
    ).filter(
        Order.status_id.in_([2, 3])
    ).order_by(Order.created_at.desc()).all()
    
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
            "progreso": round((order.items_completados / order.total_items * 100) if order.total_items > 0 else 0, 2),
            "fecha_asignacion": order.fecha_asignacion.isoformat() if order.fecha_asignacion else None,
            "created_at": order.created_at.isoformat()
        })
    
    return result


@router.get("/{operator_codigo}/orders/{order_id}/lines")
def list_order_lines(
    operator_codigo: str,
    order_id: int,
    db: Session = Depends(get_db)
):
    """
    Lista todos los productos (líneas) de una orden específica.
    
    **Parámetros:**
    - `operator_codigo`: Código del operario (ej: "OP001", "OP002")
    - `order_id`: ID de la orden
    
    **Retorna:**
    - Lista de productos con cantidades y ubicaciones
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
    lines = db.query(OrderLine).filter(
        OrderLine.order_id == order_id
    ).all()
    
    # Formatear respuesta
    result = []
    for line in lines:
        # Buscar ubicación de picking (almacen_id=2) desde ProductLocation
        picking_location = None
        ubicacion_id = None
        ubicacion = None
        
        if line.product_reference_id:
            # Buscar la mejor ubicación en el almacén de picking
            picking_location = db.query(ProductLocation).filter(
                ProductLocation.product_id == line.product_reference_id,
                ProductLocation.almacen_id == 2,  # Almacén de picking
                ProductLocation.activa == True
            ).order_by(
                ProductLocation.prioridad.asc(),      # 1 = alta prioridad primero
                ProductLocation.stock_actual.desc()   # Mayor stock primero
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
        
        result.append({
            "id": line.id,
            "producto_id": line.product_reference_id,
            "ubicacion_id": ubicacion_id,  # ID de ubicación en almacén de picking
            "ean": line.ean,
            "producto": producto,
            "ubicacion": ubicacion,
            "cantidad_solicitada": line.cantidad_solicitada,
            "cantidad_servida": line.cantidad_servida,
            "cantidad_pendiente": line.cantidad_solicitada - line.cantidad_servida,
            "estado": line.estado,
            "progreso": round((line.cantidad_servida / line.cantidad_solicitada * 100) if line.cantidad_solicitada > 0 else 0, 2)
        })
    
    return result


@router.post("/{operator_codigo}/orders/{order_id}/start-picking")
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
    if order.status.codigo not in ["PENDING", "ASSIGNED"]:
        raise HTTPException(
            status_code=400,
            detail=f"No se puede iniciar picking. Estado actual: {order.status.codigo}"
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
    
    order.status_id = in_picking_status.id
    order.fecha_inicio_picking = datetime.utcnow()
    
    db.commit()
    db.refresh(order)
    
    return {
        "message": "Picking iniciado correctamente",
        "order_id": order.id,
        "numero_orden": order.numero_orden,
        "estado": order.status.codigo,
        "fecha_inicio_picking": order.fecha_inicio_picking.isoformat()
    }


@router.post("/{operator_codigo}/orders/{order_id}/complete-picking")
def complete_picking(
    operator_codigo: str,
    order_id: int,
    db: Session = Depends(get_db)
):
    """
    Completa el proceso de picking de una orden.
    
    **Parámetros:**
    - `operator_codigo`: Código del operario (ej: "OP001", "OP002")
    - `order_id`: ID de la orden
    
    **Acción:**
    - Cambia el estado de la orden a PICKED
    - Registra la fecha de fin de picking
    
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
    # Si ya está en PICKED, devolver respuesta exitosa (idempotente)
    if order.status.codigo == "PICKED":
        return {
            "message": "El picking de esta orden ya está completado",
            "order_id": order.id,
            "numero_orden": order.numero_orden,
            "estado": order.status.codigo,
            "fecha_fin_picking": order.fecha_fin_picking.isoformat() if order.fecha_fin_picking else None
        }
    
    # Si no está en IN_PICKING, no se puede completar
    if order.status.codigo != "IN_PICKING":
        raise HTTPException(
            status_code=400,
            detail=f"No se puede completar picking. Estado actual: {order.status.codigo}"
        )
    
    # Cambiar estado a PICKED
    picked_status = db.query(OrderStatus).filter(
        OrderStatus.codigo == "PICKED"
    ).first()
    
    if not picked_status:
        raise HTTPException(
            status_code=500,
            detail="Estado PICKED no encontrado en el sistema"
        )
    
    order.status_id = picked_status.id
    order.fecha_fin_picking = datetime.utcnow()
    
    db.commit()
    db.refresh(order)
    
    return {
        "message": "Picking completado correctamente",
        "order_id": order.id,
        "numero_orden": order.numero_orden,
        "estado": order.status.codigo,
        "fecha_inicio_picking": order.fecha_inicio_picking.isoformat() if order.fecha_inicio_picking else None,
        "fecha_fin_picking": order.fecha_fin_picking.isoformat()
    }
