"""
Pydantic models for stock movement endpoints.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict
from datetime import datetime


class StockMovementResponse(BaseModel):
    """Modelo de respuesta para movimiento de stock."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    tipo: str = Field(description="Tipo: RESERVE, DEDUCT, RELEASE, ADJUSTMENT, MOVE_OUT, MOVE_IN")
    cantidad: int = Field(description="Cantidad del movimiento (+ o -)")
    stock_antes: int = Field(description="Stock antes del movimiento")
    stock_despues: int = Field(description="Stock después del movimiento")
    notas: Optional[str] = Field(None, description="Notas del movimiento")
    created_at: datetime = Field(description="Fecha y hora del movimiento")
    
    # Datos del producto
    producto_sku: Optional[str] = Field(None, description="SKU del producto")
    producto_nombre: Optional[str] = Field(None, description="Nombre del producto")
    producto_color: Optional[str] = Field(None, description="Color del producto")
    producto_talla: Optional[str] = Field(None, description="Talla del producto")
    
    # Datos de ubicación
    ubicacion_codigo: Optional[str] = Field(None, description="Código de ubicación")
    
    # Datos de orden (si aplica)
    order_id: Optional[int] = Field(None, description="ID de orden relacionada")
    numero_orden: Optional[str] = Field(None, description="Número de orden")
    order_line_id: Optional[int] = Field(None, description="ID de línea de orden")


class TipoEstadistica(BaseModel):
    """Estadística por tipo de movimiento."""
    count: int
    total_cantidad: int


class StockMovementListResponse(BaseModel):
    """Respuesta con lista de movimientos y estadísticas."""
    total: int = Field(description="Total de movimientos encontrados")
    movimientos: List[StockMovementResponse] = Field(description="Lista de movimientos")
    estadisticas: Dict[str, TipoEstadistica] = Field(description="Estadísticas por tipo de movimiento")


class StockMovementStatsSummary(BaseModel):
    """Resumen estadístico de movimientos de stock."""
    total_movimientos: int = Field(description="Total de movimientos")
    fecha_desde: Optional[str] = Field(None, description="Fecha desde filtro")
    fecha_hasta: Optional[str] = Field(None, description="Fecha hasta filtro")
    estadisticas_por_tipo: Dict[str, TipoEstadistica] = Field(description="Estadísticas agrupadas por tipo")
