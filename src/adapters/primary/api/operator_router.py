"""
Router para gestión de operarios.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from src.adapters.secondary.database.config import get_db
from src.adapters.secondary.database.orm import Operator
from src.core.domain.models import (
    OperatorResponse,
    OperatorCreate,
    OperatorUpdate
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
        Operator.codigo_operario == operator_data.codigo_operario
    ).first()
    
    if existing_operator:
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe un operario con el código '{operator_data.codigo_operario}'"
        )
    
    # Crear nuevo operario
    new_operator = Operator(
        codigo_operario=operator_data.codigo_operario,
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
