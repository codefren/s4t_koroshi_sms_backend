"""
API Router para gestión de Almacenes.

Endpoints:
- GET /almacenes - Lista todos los almacenes
- GET /almacenes/{almacen_id} - Obtiene detalles de un almacén
- GET /almacenes/{almacen_id}/stats - Obtiene estadísticas de un almacén
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.adapters.secondary.database.config import get_db
from src.adapters.secondary.database.orm import Almacen, ProductLocation
from src.core.domain.almacen_models import (
    AlmacenResponse,
    AlmacenWithStats
)

router = APIRouter(prefix="/almacenes", tags=["Almacenes"])


@router.get("/", response_model=List[AlmacenResponse])
def list_almacenes(
    skip: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(100, ge=1, le=500, description="Número máximo de registros a retornar"),
    db: Session = Depends(get_db)
):
    """
    Lista todos los almacenes del sistema.
    
    **Retorna:**
    - Lista de almacenes con su información básica
    """
    almacenes = db.query(Almacen).order_by(Almacen.id).offset(skip).limit(limit).all()
    return almacenes


@router.get("/{almacen_id}", response_model=AlmacenResponse)
def get_almacen(
    almacen_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene los detalles de un almacén específico.
    
    **Parámetros:**
    - almacen_id: ID del almacén
    
    **Retorna:**
    - Información completa del almacén
    """
    almacen = db.query(Almacen).filter(Almacen.id == almacen_id).first()
    
    if not almacen:
        raise HTTPException(
            status_code=404,
            detail=f"Almacén con ID {almacen_id} no encontrado"
        )
    
    return almacen


@router.get("/{almacen_id}/stats", response_model=AlmacenWithStats)
def get_almacen_stats(
    almacen_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene estadísticas detalladas de un almacén.
    
    **Incluye:**
    - Total de ubicaciones
    - Total de productos únicos
    - Suma total de stock
    
    **Parámetros:**
    - almacen_id: ID del almacén
    
    **Retorna:**
    - Información del almacén con estadísticas
    """
    almacen = db.query(Almacen).filter(Almacen.id == almacen_id).first()
    
    if not almacen:
        raise HTTPException(
            status_code=404,
            detail=f"Almacén con ID {almacen_id} no encontrado"
        )
    
    # Calcular estadísticas
    stats = db.query(
        func.count(ProductLocation.id).label('total_ubicaciones'),
        func.count(func.distinct(ProductLocation.product_id)).label('total_productos'),
        func.coalesce(func.sum(ProductLocation.stock_actual), 0).label('total_stock')
    ).filter(
        ProductLocation.almacen_id == almacen_id,
        ProductLocation.activa == True
    ).first()
    
    # Construir respuesta
    almacen_data = {
        "id": almacen.id,
        "codigo": almacen.codigo,
        "descripciones": almacen.descripciones,
        "created_at": almacen.created_at,
        "updated_at": almacen.updated_at,
        "total_ubicaciones": stats.total_ubicaciones if stats else 0,
        "total_productos": stats.total_productos if stats else 0,
        "total_stock": stats.total_stock if stats else 0
    }
    
    return AlmacenWithStats(**almacen_data)
