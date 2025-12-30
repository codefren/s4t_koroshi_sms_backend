"""
Router para gestión de operarios.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from src.adapters.secondary.database.config import get_db
from src.adapters.secondary.database.orm import Operator
from src.core.domain.models import OperatorResponse

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
