"""
Modelos Pydantic específicos para la API de productos del frontend.

Estos modelos están diseñados para cumplir con los requerimientos
específicos de la vista Products.jsx del frontend React.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class ProductStatusEnum(str, Enum):
    """Estados posibles de un producto."""
    ACTIVE = "active"
    LOW_STOCK = "low-stock"
    OUT_OF_STOCK = "out-of-stock"


class ProductStatusFilter(str, Enum):
    """Filtros de estado para búsqueda."""
    ALL = "all"
    ACTIVE = "active"
    LOW = "low"
    OUT = "out"


class LocationItem(BaseModel):
    """
    Modelo para una ubicación individual en la respuesta.
    
    Formato de código esperado: "B-08, Der, C2-08"
    """
    model_config = ConfigDict(from_attributes=True)
    
    code: str = Field(
        ...,
        description="Código de ubicación formateado (ej: 'B-08, Der, C2-08')"
    )
    is_more: bool = Field(
        default=False,
        description="True si es un indicador '+X más' para ubicaciones adicionales",
        alias="isMore"
    )
    stock: Optional[int] = Field(
        None,
        description="Stock en esta ubicación específica (opcional)"
    )


class ProductListItem(BaseModel):
    """
    Modelo para un producto en el listado.
    
    Este modelo cumple con los requerimientos del componente Products.jsx
    """
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    
    # Identificación
    id: int = Field(..., description="ID único del producto")
    sku: str = Field(..., description="Código SKU único del producto")
    
    # Información básica
    name: str = Field(..., description="Nombre del producto")
    category: str = Field(..., description="Categoría del producto")
    talla: Optional[str] = Field(None, description="Talla del producto (XS, S, M, L, XL, etc.)")
    image: Optional[str] = Field(
        None,
        description="URL de la imagen del producto"
    )
    
    # Ubicaciones (máximo 2-3, luego "+X más")
    locations: List[LocationItem] = Field(
        default=[],
    )
    
    # Stock
    stock: int = Field(..., ge=0, description="Cantidad total en stock")
    
    # Estado
    status: str = Field(..., description="Estado del producto: 'Activo', 'Stock Bajo', 'Sin Stock'")
    status_class: str = Field(
        ...,
        description="Clase CSS del estado: 'active', 'low-stock', 'out-of-stock'",
        alias="statusClass"
    )


class ProductLocationDetail(BaseModel):
    """Modelo detallado de ubicación con stock."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    code: str = Field(..., description="Código completo de ubicación")
    pasillo: str
    lado: str
    ubicacion: str
    altura: int
    stock_actual: int = Field(..., description="Stock en esta ubicación")
    stock_minimo: int
    prioridad: int = Field(..., description="Prioridad para picking (1=alta, 5=baja)")
    activa: bool


class ProductDetail(BaseModel):
    """
    Modelo detallado de un producto individual.
    
    Incluye todas las ubicaciones sin límite.
    """
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    
    # Identificación
    id: int
    referencia: str = Field(..., description="Código hexadecimal único")
    sku: Optional[str] = Field(None, description="SKU del producto")
    
    # Información básica
    nombre_producto: str = Field(..., alias="name")
    color_id: str
    descripcion_color: Optional[str] = Field(None, alias="category")
    talla: str
    ean: Optional[str]
    temporada: Optional[str]
    
    # Estado
    activo: bool
    
    # Stock total (calculado de todas las ubicaciones)
    stock: int = Field(..., description="Stock total en todas las ubicaciones")
    
    # Ubicaciones completas
    locations: List[ProductLocationDetail] = Field(
        default=[],
        description="Lista completa de ubicaciones"
    )
    
    # Estado calculado
    status: str
    status_class: str = Field(..., alias="statusClass")


class ProductLocationsResponse(BaseModel):
    """
    Respuesta para el endpoint de ubicaciones de un producto.
    
    Retorna todas las ubicaciones sin límite.
    """
    model_config = ConfigDict(from_attributes=True)
    
    product_id: int
    product_name: str
    product_sku: Optional[str]
    locations: List[ProductLocationDetail]
    total_locations: int = Field(..., description="Número total de ubicaciones")
    total_stock: int = Field(..., description="Stock total sumado de todas las ubicaciones")
    status: str
    status_class: str


class ProductListResponse(BaseModel):
    """
    Respuesta paginada para el listado de productos.
    """
    model_config = ConfigDict(from_attributes=True)
    
    total: int = Field(..., description="Total de productos que cumplen el filtro")
    page: int = Field(default=1, description="Página actual")
    per_page: int = Field(default=20, description="Productos por página")
    total_pages: int = Field(..., description="Total de páginas")
    products: List[ProductListItem] = Field(default=[], description="Lista de productos")


# ============================================================================
# UTILIDADES PARA CALCULAR ESTADO
# ============================================================================

def calculate_product_status(stock: int) -> tuple[str, str]:
    """
    Calcula el estado del producto basado en el stock.
    
    Args:
        stock: Cantidad total de stock
        
    Returns:
        Tupla (status_text, status_class)
        
    Ejemplo:
        >>> calculate_product_status(100)
        ('Activo', 'active')
        >>> calculate_product_status(25)
        ('Stock Bajo', 'low-stock')
        >>> calculate_product_status(0)
        ('Sin Stock', 'out-of-stock')
    """
    if stock == 0:
        return ("Sin Stock", "out-of-stock")
    elif stock < 50:
        return ("Stock Bajo", "low-stock")
    else:
        return ("Activo", "active")


def format_location_code(pasillo: str, lado: str, ubicacion: str, altura: int) -> str:
    """
    Formatea un código de ubicación según el formato esperado por el frontend.
    
    Formato: "[Pasillo]-[Posición], [Lado_Corto], [Estante]-[Nivel]"
    Ejemplo: "B-08, Der, C2-08"
    
    Args:
        pasillo: Identificador del pasillo
        lado: IZQUIERDA o DERECHA
        ubicacion: Posición específica
        altura: Nivel de altura
        
    Returns:
        String formateado
    """
    # Abreviar lado
    lado_short = "Der" if lado.upper() == "DERECHA" else "Izq"
    
    # Formatear estante (usando pasillo como prefijo + ubicación)
    estante = f"{pasillo}{altura}-{ubicacion}"
    
    # Formato final
    return f"{pasillo}-{ubicacion}, {lado_short}, {estante}"
