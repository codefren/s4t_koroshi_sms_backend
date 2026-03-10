"""
Router para consulta de movimientos de stock.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func
from typing import List, Optional
from datetime import datetime, date

from src.adapters.secondary.database.config import get_db
from src.adapters.secondary.database.orm import (
    StockMovement, ProductLocation, ProductReference, Order, OrderLine
)
from src.core.domain.stock_movement_models import (
    StockMovementResponse,
    StockMovementListResponse,
    StockMovementStatsSummary
)

router = APIRouter(prefix="/stock-movements", tags=["Stock Movements"])


@router.get("", response_model=StockMovementListResponse)
def list_stock_movements(
    tipo: Optional[str] = Query(None, description="Filtrar por tipo: RESERVE, DEDUCT, RELEASE, ADJUSTMENT, MOVE_OUT, MOVE_IN"),
    fecha_desde: Optional[date] = Query(None, description="Fecha desde (YYYY-MM-DD)"),
    fecha_hasta: Optional[date] = Query(None, description="Fecha hasta (YYYY-MM-DD)"),
    product_location_id: Optional[int] = Query(None, description="Filtrar por ubicación específica"),
    product_id: Optional[int] = Query(None, description="Filtrar por producto específico"),
    order_id: Optional[int] = Query(None, description="Filtrar por orden específica"),
    limit: int = Query(100, ge=1, le=1000, description="Límite de resultados"),
    offset: int = Query(0, ge=0, description="Offset para paginación"),
    db: Session = Depends(get_db)
):
    """
    Lista movimientos de stock con filtros opcionales.
    
    **Tipos de movimiento:**
    - `RESERVE` - Stock reservado por orden (PENDING/ASSIGNED/IN_PICKING)
    - `DEDUCT` - Stock descontado al pasar orden a READY (cantidad_servida)
    - `RELEASE` - Reserva liberada por cancelación de orden
    - `ADJUSTMENT` - Ajuste manual de stock
    - `MOVE_OUT` - Stock movido desde esta ubicación a otra
    - `MOVE_IN` - Stock recibido en esta ubicación desde otra
    
    **Filtros disponibles:**
    - Por tipo de movimiento
    - Por rango de fechas (desde/hasta)
    - Por ubicación específica
    - Por producto específico
    - Por orden específica
    
    **Retorna:**
    - Lista de movimientos con información completa
    - Estadísticas por tipo de movimiento
    - Total de registros
    """
    # Construir query base con joins
    query = db.query(StockMovement).options(
        joinedload(StockMovement.product_location),
        joinedload(StockMovement.product),
        joinedload(StockMovement.order),
        joinedload(StockMovement.order_line)
    )
    
    # Aplicar filtros
    filters = []
    
    if tipo:
        filters.append(StockMovement.tipo == tipo.upper())
    
    if fecha_desde:
        fecha_desde_dt = datetime.combine(fecha_desde, datetime.min.time())
        filters.append(StockMovement.created_at >= fecha_desde_dt)
    
    if fecha_hasta:
        fecha_hasta_dt = datetime.combine(fecha_hasta, datetime.max.time())
        filters.append(StockMovement.created_at <= fecha_hasta_dt)
    
    if product_location_id:
        filters.append(StockMovement.product_location_id == product_location_id)
    
    if product_id:
        filters.append(StockMovement.product_id == product_id)
    
    if order_id:
        filters.append(StockMovement.order_id == order_id)
    
    if filters:
        query = query.filter(and_(*filters))
    
    # Contar total antes de paginación
    total = query.count()
    
    # Aplicar ordenamiento y paginación
    movements = query.order_by(StockMovement.created_at.desc()).limit(limit).offset(offset).all()
    
    # Formatear respuesta
    movimientos_response = []
    for mov in movements:
        movimientos_response.append(StockMovementResponse(
            id=mov.id,
            tipo=mov.tipo,
            cantidad=mov.cantidad,
            stock_antes=mov.stock_antes,
            stock_despues=mov.stock_despues,
            notas=mov.notas,
            created_at=mov.created_at,
            producto_sku=mov.product.sku if mov.product else None,
            producto_nombre=mov.product.nombre_producto if mov.product else None,
            producto_color=mov.product.nombre_color if mov.product else None,
            producto_talla=mov.product.talla if mov.product else None,
            ubicacion_codigo=mov.product_location.codigo_ubicacion if mov.product_location else None,
            order_id=mov.order_id,
            numero_orden=mov.order.numero_orden if mov.order else None,
            order_line_id=mov.order_line_id
        ))
    
    # Calcular estadísticas por tipo
    estadisticas_query = db.query(
        StockMovement.tipo,
        func.count(StockMovement.id).label('count'),
        func.sum(StockMovement.cantidad).label('total_cantidad')
    )
    
    if filters:
        estadisticas_query = estadisticas_query.filter(and_(*filters))
    
    stats = estadisticas_query.group_by(StockMovement.tipo).all()
    
    estadisticas = {}
    for stat in stats:
        estadisticas[stat.tipo] = {
            "count": stat.count,
            "total_cantidad": stat.total_cantidad or 0
        }
    
    return StockMovementListResponse(
        total=total,
        movimientos=movimientos_response,
        estadisticas=estadisticas
    )


@router.get("/tipos", response_model=List[str])
def list_movement_types(db: Session = Depends(get_db)):
    """
    Lista todos los tipos de movimiento disponibles en el sistema.
    
    **Retorna:**
    - Lista de tipos únicos de movimiento
    """
    tipos = db.query(StockMovement.tipo).distinct().all()
    return [t[0] for t in tipos]


@router.get("/stats/summary", response_model=StockMovementStatsSummary)
def get_movement_stats_summary(
    fecha_desde: Optional[date] = Query(None, description="Fecha desde"),
    fecha_hasta: Optional[date] = Query(None, description="Fecha hasta"),
    db: Session = Depends(get_db)
):
    """
    Obtiene resumen estadístico de movimientos de stock.
    
    **Retorna:**
    - Total de movimientos por tipo
    - Suma de cantidades por tipo
    - Total general de movimientos
    """
    query = db.query(StockMovement)
    
    # Aplicar filtros de fecha
    if fecha_desde:
        fecha_desde_dt = datetime.combine(fecha_desde, datetime.min.time())
        query = query.filter(StockMovement.created_at >= fecha_desde_dt)
    
    if fecha_hasta:
        fecha_hasta_dt = datetime.combine(fecha_hasta, datetime.max.time())
        query = query.filter(StockMovement.created_at <= fecha_hasta_dt)
    
    total_movimientos = query.count()
    
    # Estadísticas por tipo
    stats = query.with_entities(
        StockMovement.tipo,
        func.count(StockMovement.id).label('count'),
        func.sum(StockMovement.cantidad).label('total_cantidad')
    ).group_by(StockMovement.tipo).all()
    
    stats_por_tipo = {}
    for stat in stats:
        stats_por_tipo[stat.tipo] = {
            "count": stat.count,
            "total_cantidad": stat.total_cantidad or 0
        }
    
    return {
        "total_movimientos": total_movimientos,
        "fecha_desde": fecha_desde.isoformat() if fecha_desde else None,
        "fecha_hasta": fecha_hasta.isoformat() if fecha_hasta else None,
        "estadisticas_por_tipo": stats_por_tipo
    }
