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
    response = PackingBoxWithOperator(
        **new_box.__dict__,
        operator=OperatorResponse(**operator.__dict__) if operator else None
    )
    
    return response


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
        result.append(
            PackingBoxWithOperator(
                **box.__dict__,
                operator=OperatorResponse(**operator.__dict__) if operator else None
            )
        )
    
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
    response = PackingBoxDetail(
        **box.__dict__,
        operator=OperatorResponse(**operator.__dict__) if operator else None,
        items=[OrderLineResponse(**line.__dict__) for line in order_lines]
    )
    
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
    
    response = PackingBoxWithOperator(
        **box.__dict__,
        operator=OperatorResponse(**operator.__dict__) if operator else None
    )
    
    return response


@router.put("/{box_id}/close", response_model=PackingBoxWithOperator)
def close_box(
    box_id: int,
    close_data: PackingBoxClose,
    db: Session = Depends(get_db)
):
    """
    Cierra una caja de embalaje.
    
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
    box = db.query(PackingBox).filter(PackingBox.id == box_id).first()
    
    if not box:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Caja con ID {box_id} no encontrada"
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
    if order.caja_activa_id == box_id:
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
    
    response = PackingBoxWithOperator(
        **box.__dict__,
        operator=OperatorResponse(**operator.__dict__) if operator else None
    )
    
    return response


@router.delete("/{box_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_box(
    box_id: int,
    db: Session = Depends(get_db)
):
    """
    Elimina una caja de embalaje vacía.
    
    **Validaciones:**
    - La caja debe existir
    - La caja debe estar vacía (total_items = 0)
    - La caja debe estar OPEN (no se pueden eliminar cajas cerradas con items)
    
    **Uso:**
    - Eliminar cajas creadas por error
    - Limpiar cajas vacías antes de cerrar una orden
    
    **Retorna:**
    - 204 No Content (sin cuerpo de respuesta)
    """
    box = db.query(PackingBox).filter(PackingBox.id == box_id).first()
    
    if not box:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Caja con ID {box_id} no encontrada"
        )
    
    # Validar que está vacía
    if box.total_items > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar caja con items. La caja tiene {box.total_items} items empacados."
        )
    
    # Validar que está OPEN
    if box.estado != "OPEN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo se pueden eliminar cajas OPEN. Esta caja está: {box.estado}"
        )
    
    # Si es la caja activa, limpiar referencia en orden
    order = db.query(Order).filter(Order.id == box.order_id).first()
    if order.caja_activa_id == box_id:
        order.caja_activa_id = None
        order.total_cajas -= 1
    
    # Registrar en historial antes de eliminar
    history_entry = OrderHistory(
        order_id=box.order_id,
        status_id=order.status_id,
        operator_id=order.operator_id,
        accion="BOX_DELETED",
        notas=f"Caja #{box.numero_caja} eliminada (estaba vacía)",
        fecha=datetime.utcnow(),
        event_metadata={
            "numero_caja": box.numero_caja,
            "codigo_caja": box.codigo_caja
        }
    )
    db.add(history_entry)
    
    # Eliminar caja
    db.delete(box)
    db.commit()
    
    return None


# ============================================================================
# ENDPOINTS DE EMPAQUE DE ITEMS
# ============================================================================

@router.put("/order-lines/{line_id}/pack", response_model=OrderLineResponse)
def pack_item(
    line_id: int,
    pack_data: PackItemRequest,
    db: Session = Depends(get_db)
):
    """
    Empaca un item (order_line) en una caja específica.
    
    **Parámetros:**
    - `packing_box_id`: ID de la caja (opcional, usa caja activa si NULL)
    
    **Validaciones:**
    - El item debe existir
    - El item no debe estar ya empacado en otra caja
    - La caja debe estar OPEN
    - La caja debe pertenecer a la misma orden del item
    
    **Acción automática:**
    - Asigna packing_box_id al item
    - Registra fecha_empacado
    - Incrementa packing_box.total_items
    
    **Retorna:**
    - Información actualizada del item
    """
    # 1. Obtener order_line
    order_line = db.query(OrderLine).filter(OrderLine.id == line_id).first()
    
    if not order_line:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item con ID {line_id} no encontrado"
        )
    
    # 2. Validar que no está ya empacado
    if order_line.packing_box_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El item ya está empacado en la caja ID: {order_line.packing_box_id}"
        )
    
    # 3. Determinar caja destino
    box_id = pack_data.packing_box_id
    
    if box_id is None:
        # Usar caja activa de la orden
        order = db.query(Order).filter(Order.id == order_line.order_id).first()
        box_id = order.caja_activa_id
        
        if box_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No hay caja activa. Especifique packing_box_id o abra una caja primero."
            )
    
    # 4. Validar caja
    box = db.query(PackingBox).filter(PackingBox.id == box_id).first()
    
    if not box:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Caja con ID {box_id} no encontrada"
        )
    
    if box.estado != "OPEN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La caja está en estado: {box.estado}. Solo se puede empacar en cajas OPEN."
        )
    
    if box.order_id != order_line.order_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La caja pertenece a una orden diferente"
        )
    
    # 5. Empacar item
    order_line.packing_box_id = box_id
    order_line.fecha_empacado = datetime.utcnow()
    
    # 6. Incrementar contador de caja
    box.total_items += 1
    
    db.commit()
    db.refresh(order_line)
    
    return OrderLineResponse(**order_line.__dict__)


@router.put("/order-lines/{line_id}/unpack", response_model=OrderLineResponse)
def unpack_item(
    line_id: int,
    db: Session = Depends(get_db)
):
    """
    Desempaca un item de su caja (para correcciones).
    
    **Validaciones:**
    - El item debe existir
    - El item debe estar empacado
    - La caja debe estar OPEN (no se puede desempacar de cajas cerradas)
    
    **Acción automática:**
    - Limpia packing_box_id y fecha_empacado
    - Decrementa packing_box.total_items
    
    **Retorna:**
    - Información actualizada del item
    """
    # 1. Obtener order_line
    order_line = db.query(OrderLine).filter(OrderLine.id == line_id).first()
    
    if not order_line:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item con ID {line_id} no encontrado"
        )
    
    # 2. Validar que está empacado
    if order_line.packing_box_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El item no está empacado en ninguna caja"
        )
    
    # 3. Obtener caja
    box = db.query(PackingBox).filter(PackingBox.id == order_line.packing_box_id).first()
    
    if not box:
        # Caso extraño: la caja fue eliminada pero el item tiene referencia
        order_line.packing_box_id = None
        order_line.fecha_empacado = None
        db.commit()
        db.refresh(order_line)
        return OrderLineResponse(**order_line.__dict__)
    
    # 4. Validar que la caja está OPEN
    if box.estado != "OPEN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede desempacar. La caja está en estado: {box.estado}"
        )
    
    # 5. Desempacar
    order_line.packing_box_id = None
    order_line.fecha_empacado = None
    
    # 6. Decrementar contador de caja
    if box.total_items > 0:
        box.total_items -= 1
    
    db.commit()
    db.refresh(order_line)
    
    return OrderLineResponse(**order_line.__dict__)
