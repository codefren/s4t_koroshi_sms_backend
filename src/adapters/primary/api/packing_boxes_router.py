"""
Router para gestión de cajas de embalaje (Packing Boxes).
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from typing import List, Optional
from datetime import datetime

from src.adapters.secondary.database.config import get_db
from src.adapters.secondary.database.orm import (
    PackingBox,
    Order,
    OrderLine,
    Operator,
    OrderHistory,
    OrderStatus
)
from src.core.domain.models import (
    PackingBoxCreate,
    PackingBoxUpdate,
    PackingBoxClose,
    PackingBoxResponse,
    PackingBoxWithOperator,
    PackingBoxDetail,
    PackItemRequest,
    UnpackItemRequest,
    OrderLineResponse,
    OperatorResponse
)

router = APIRouter(prefix="/packing-boxes", tags=["Packing Boxes"])


# ============================================================================
# ENDPOINTS DE GESTIÓN DE CAJAS
# ============================================================================

@router.post("/orders/{order_id}/boxes", response_model=PackingBoxWithOperator, status_code=status.HTTP_201_CREATED)
def create_packing_box(
    order_id: int,
    box_data: PackingBoxCreate,
    db: Session = Depends(get_db)
):
    """
    Abre una nueva caja de embalaje para una orden.
    
    **Validaciones:**
    - La orden debe existir
    - La orden debe estar en estado IN_PICKING o PICKED
    - NO debe haber otra caja OPEN para esta orden
    
    **Acción automática:**
    - Incrementa order.total_cajas
    - Asigna order.caja_activa_id a la nueva caja
    - Genera código de caja automáticamente
    - Registra evento en OrderHistory
    
    **Retorna:**
    - Información completa de la caja creada con datos del operario
    """
    # 1. Validar que la orden existe
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Orden con ID {order_id} no encontrada"
        )
    
    # 2. Validar estado de la orden
    order_status = db.query(OrderStatus).filter(OrderStatus.id == order.status_id).first()
    if order_status.codigo not in ["IN_PICKING", "PICKED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede crear caja. La orden está en estado: {order_status.codigo}"
        )
    
    # 3. Verificar que NO hay otra caja OPEN
    existing_open_box = db.query(PackingBox).filter(
        and_(
            PackingBox.order_id == order_id,
            PackingBox.estado == "OPEN"
        )
    ).first()
    
    if existing_open_box:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe una caja abierta (ID: {existing_open_box.id}). Ciérrela antes de abrir una nueva."
        )
    
    # 4. Calcular número de caja (siguiente secuencial)
    max_numero = db.query(PackingBox).filter(
        PackingBox.order_id == order_id
    ).count()
    
    nuevo_numero_caja = max_numero + 1
    
    # 5. Generar código de caja único
    codigo_caja = f"ORD-{order.numero_orden}-BOX-{nuevo_numero_caja:03d}"
    
    # 6. Crear la nueva caja
    new_box = PackingBox(
        order_id=order_id,
        numero_caja=nuevo_numero_caja,
        codigo_caja=codigo_caja,
        estado="OPEN",
        operator_id=order.operator_id,  # Mismo operario de la orden
        total_items=0,
        fecha_apertura=datetime.utcnow(),
        notas=box_data.notas
    )
    
    db.add(new_box)
    db.flush()  # Para obtener el ID
    
    # 7. Actualizar la orden
    order.total_cajas = nuevo_numero_caja
    order.caja_activa_id = new_box.id
    
    # 8. Registrar en historial
    history_entry = OrderHistory(
        order_id=order_id,
        status_id=order.status_id,
        operator_id=order.operator_id,
        accion="BOX_OPENED",
        notas=f"Caja #{nuevo_numero_caja} abierta. Código: {codigo_caja}",
        fecha=datetime.utcnow(),
        event_metadata={
            "packing_box_id": new_box.id,
            "numero_caja": nuevo_numero_caja,
            "codigo_caja": codigo_caja
        }
    )
    db.add(history_entry)
    
    db.commit()
    db.refresh(new_box)
    
    # 9. Cargar relación con operario para respuesta
    operator = db.query(Operator).filter(Operator.id == new_box.operator_id).first() if new_box.operator_id else None
    
    # Construir respuesta
    box_data = PackingBoxWithOperator.model_validate(new_box)
    box_data.operator = OperatorResponse.model_validate(operator) if operator else None
    
    return box_data


@router.get("/orders/{order_id}/boxes", response_model=List[PackingBoxWithOperator])
def list_order_boxes(
    order_id: int,
    estado: Optional[str] = Query(None, description="Filtrar por estado: OPEN, CLOSED, SHIPPED"),
    db: Session = Depends(get_db)
):
    """
    Lista todas las cajas de una orden específica.
    
    **Parámetros:**
    - `estado`: Filtrar por estado (opcional)
    
    **Retorna:**
    - Lista de cajas con información del operario
    - Ordenadas por numero_caja ascendente
    """
    # Validar que la orden existe
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Orden con ID {order_id} no encontrada"
        )
    
    # Consultar cajas
    query = db.query(PackingBox).filter(PackingBox.order_id == order_id)
    
    if estado:
        query = query.filter(PackingBox.estado == estado.upper())
    
    boxes = query.order_by(PackingBox.numero_caja).all()
    
    # Construir respuesta con operarios
    result = []
    for box in boxes:
        operator = db.query(Operator).filter(Operator.id == box.operator_id).first() if box.operator_id else None
        box_data = PackingBoxWithOperator.model_validate(box)
        box_data.operator = OperatorResponse.model_validate(operator) if operator else None
        result.append(box_data)
    
    return result


@router.get("/{box_id}", response_model=PackingBoxDetail)
def get_box_detail(
    box_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene el detalle completo de una caja específica.
    
    **Incluye:**
    - Información de la caja
    - Operario que empacó
    - Lista completa de items (order_lines) en la caja
    
    **Retorna:**
    - Detalle completo de la caja con todos sus items
    """
    box = db.query(PackingBox).filter(PackingBox.id == box_id).first()
    
    if not box:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Caja con ID {box_id} no encontrada"
        )
    
    # Cargar operario
    operator = db.query(Operator).filter(Operator.id == box.operator_id).first() if box.operator_id else None
    
    # Cargar items de la caja
    order_lines = db.query(OrderLine).filter(OrderLine.packing_box_id == box_id).all()
    
    # Construir respuesta
    response = PackingBoxDetail.model_validate(box)
    response.operator = OperatorResponse.model_validate(operator) if operator else None
    response.items = [OrderLineResponse.model_validate(line) for line in order_lines]
    
    return response


@router.put("/{box_id}", response_model=PackingBoxWithOperator)
def update_box(
    box_id: int,
    box_data: PackingBoxUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualiza información de una caja (peso, dimensiones, notas).
    
    **Permite actualizar:**
    - Peso en kilogramos
    - Dimensiones (ej: "40x30x20 cm")
    - Notas adicionales
    
    **NO permite cambiar:**
    - Estado (usar endpoint específico para cerrar)
    - Número de caja
    - Orden asociada
    
    **Retorna:**
    - Información actualizada de la caja
    """
    box = db.query(PackingBox).filter(PackingBox.id == box_id).first()
    
    if not box:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Caja con ID {box_id} no encontrada"
        )
    
    # Actualizar campos si se proporcionan
    if box_data.peso_kg is not None:
        box.peso_kg = box_data.peso_kg
    
    if box_data.dimensiones is not None:
        box.dimensiones = box_data.dimensiones
    
    if box_data.notas is not None:
        box.notas = box_data.notas
    
    db.commit()
    db.refresh(box)
    
    # Cargar operario para respuesta
    operator = db.query(Operator).filter(Operator.id == box.operator_id).first() if box.operator_id else None
    
    response = PackingBoxWithOperator.model_validate(box)
    response.operator = OperatorResponse.model_validate(operator) if operator else None
    
    return response


@router.put("/{codigo_caja}/close", response_model=PackingBoxWithOperator)
def close_box(
    codigo_caja: str,
    close_data: PackingBoxClose,
    db: Session = Depends(get_db)
):
    """
    Cierra una caja de embalaje.
    
    **Parámetros:**
    - `codigo_caja`: Código único de la caja (ej: "ORD-12345-BOX-001")
    
    **Validaciones:**
    - La caja debe existir
    - La caja debe estar en estado OPEN
    - Se puede proporcionar peso y dimensiones finales (opcional)
    
    **Acción automática:**
    - Cambia estado a CLOSED
    - Registra fecha_cierre
    - Actualiza order.caja_activa_id = NULL
    - Registra evento en OrderHistory
    
    **Retorna:**
    - Información de la caja cerrada
    """
    box = db.query(PackingBox).filter(PackingBox.codigo_caja == codigo_caja).first()
    
    if not box:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Caja con código '{codigo_caja}' no encontrada"
        )
    
    # Validar que está OPEN
    if box.estado != "OPEN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La caja ya está en estado: {box.estado}. Solo se pueden cerrar cajas OPEN."
        )
    
    # Validar que tenga items (opcional, puede permitirse cerrar caja vacía)
    if box.total_items == 0:
        # Advertencia pero permitir cerrar
        pass
    
    # Actualizar caja
    box.estado = "CLOSED"
    box.fecha_cierre = datetime.utcnow()
    
    if close_data.peso_kg is not None:
        box.peso_kg = close_data.peso_kg
    
    if close_data.dimensiones is not None:
        box.dimensiones = close_data.dimensiones
    
    if close_data.notas:
        # Agregar a notas existentes
        if box.notas:
            box.notas += f" | Cierre: {close_data.notas}"
        else:
            box.notas = close_data.notas
    
    # Actualizar orden (quitar caja activa)
    order = db.query(Order).filter(Order.id == box.order_id).first()
    if order.caja_activa_id == box.id:
        order.caja_activa_id = None
    
    # Registrar en historial
    history_entry = OrderHistory(
        order_id=box.order_id,
        status_id=order.status_id,
        operator_id=order.operator_id,
        accion="BOX_CLOSED",
        notas=f"Caja #{box.numero_caja} cerrada. {box.total_items} items empacados.",
        fecha=datetime.utcnow(),
        event_metadata={
            "packing_box_id": box.id,
            "numero_caja": box.numero_caja,
            "total_items": box.total_items,
            "peso_kg": box.peso_kg,
            "dimensiones": box.dimensiones
        }
    )
    db.add(history_entry)
    
    db.commit()
    db.refresh(box)
    
    # Cargar operario para respuesta
    operator = db.query(Operator).filter(Operator.id == box.operator_id).first() if box.operator_id else None
    
    response = PackingBoxWithOperator.model_validate(box)
    response.operator = OperatorResponse.model_validate(operator) if operator else None
    
    return response
