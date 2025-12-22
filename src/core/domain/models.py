from pydantic import BaseModel, ConfigDict
from typing import Optional

class Item(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    price: float

class InventoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ean: str
    ubicacion: str
    articulo: str
    color: str
    talla: str
    posicion_talla: Optional[str] = None
    descripcion_producto: Optional[str] = None
    descripcion_color: Optional[str] = None
    temporada: Optional[str] = None
    numero_orden: str
    cliente: str
    nombre_cliente: Optional[str] = None
    cantidad: int
    servida: int
    operario: Optional[str] = None
    status: Optional[str] = None
    fecha: Optional[str] = None
    hora: Optional[str] = None
    caja: Optional[str] = None
