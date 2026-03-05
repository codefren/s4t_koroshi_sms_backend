"""
Modelos Pydantic para API de Almacenes.
"""

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional


class AlmacenBase(BaseModel):
    """Modelo base para almacén."""
    codigo: str = Field(..., description="Código del almacén")
    descripciones: str = Field(..., description="Descripción del almacén")


class AlmacenCreate(AlmacenBase):
    """Modelo para crear almacén."""
    pass


class AlmacenUpdate(BaseModel):
    """Modelo para actualizar almacén."""
    codigo: Optional[str] = Field(None, description="Código del almacén")
    descripciones: Optional[str] = Field(None, description="Descripción del almacén")


class AlmacenResponse(AlmacenBase):
    """Modelo de respuesta para almacén."""
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class AlmacenWithStats(AlmacenResponse):
    """Modelo de respuesta con estadísticas de almacén."""
    total_ubicaciones: int = Field(0, description="Total de ubicaciones en este almacén")
    total_productos: int = Field(0, description="Total de productos únicos en este almacén")
    total_stock: int = Field(0, description="Suma total de stock en este almacén")
    
    model_config = ConfigDict(from_attributes=True)
