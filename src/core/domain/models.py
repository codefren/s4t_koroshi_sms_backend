from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date

class Item(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    price: float

class InventoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    ean: Optional[str] = None
    ubicacion: Optional[str] = None
    articulo: Optional[str] = None
    color: Optional[str] = None
    talla: Optional[str] = None
    posicion_talla: Optional[str] = None
    descripcion_producto: Optional[str] = None
    descripcion_color: Optional[str] = None
    temporada: Optional[str] = None
    numero_orden: Optional[str] = None
    cliente: Optional[str] = None
    nombre_cliente: Optional[str] = None
    cantidad: Optional[int] = None
    servida: Optional[int] = None
    operario: Optional[str] = None
    status: Optional[str] = None
    fecha: Optional[str] = None
    hora: Optional[str] = None
    caja: Optional[str] = None


# ============================================================================
# MODELOS PYDANTIC PARA SISTEMA DE GESTIÓN DE ÓRDENES Y PICKING
# ============================================================================

class OrderViewCacheBase(BaseModel):
    """Modelo base para caché de la VIEW."""
    model_config = ConfigDict(from_attributes=True)
    
    numero_orden: str
    raw_data: Dict[str, Any]
    procesado: bool = False

class OrderViewCacheCreate(OrderViewCacheBase):
    """Modelo para crear entrada de caché."""
    pass

class OrderViewCacheResponse(OrderViewCacheBase):
    """Modelo de respuesta para caché."""
    id: int
    fecha_importacion: datetime
    created_at: datetime


class OrderStatusBase(BaseModel):
    """Modelo base para estados de orden."""
    model_config = ConfigDict(from_attributes=True)
    
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    orden: int
    activo: bool = True

class OrderStatusCreate(OrderStatusBase):
    """Modelo para crear estado."""
    pass

class OrderStatusUpdate(BaseModel):
    """Modelo para actualizar estado."""
    model_config = ConfigDict(from_attributes=True)
    
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    orden: Optional[int] = None
    activo: Optional[bool] = None

class OrderStatusResponse(OrderStatusBase):
    """Modelo de respuesta para estado."""
    id: int
    created_at: datetime
    updated_at: datetime


class OperatorBase(BaseModel):
    """Modelo base para operarios."""
    model_config = ConfigDict(from_attributes=True)
    
    codigo_operario: str
    nombre: str
    activo: bool = True

class OperatorCreate(OperatorBase):
    """Modelo para crear operario."""
    pass

class OperatorUpdate(BaseModel):
    """Modelo para actualizar operario."""
    model_config = ConfigDict(from_attributes=True)
    
    nombre: Optional[str] = None
    activo: Optional[bool] = None

class OperatorResponse(OperatorBase):
    """Modelo de respuesta para operario."""
    id: int
    created_at: datetime
    updated_at: datetime


class AssignOperatorRequest(BaseModel):
    """Modelo para solicitud de asignación de operario a orden."""
    operator_id: int = Field(description="ID del operario a asignar")


class UpdateOrderStatusRequest(BaseModel):
    """Modelo para solicitud de actualización de estado de orden."""
    estado_codigo: str = Field(
        description="Código del nuevo estado (PENDING, ASSIGNED, IN_PICKING, PICKED, PACKING, READY, SHIPPED, CANCELLED)"
    )
    notas: Optional[str] = Field(None, description="Notas opcionales sobre el cambio de estado")


class UpdateOrderPriorityRequest(BaseModel):
    """Modelo para solicitud de actualización de prioridad de orden."""
    prioridad: str = Field(
        description="Nueva prioridad (NORMAL, HIGH, URGENT)"
    )
    notas: Optional[str] = Field(None, description="Notas opcionales sobre el cambio de prioridad")


class OrderLineBase(BaseModel):
    """Modelo base para líneas de orden."""
    model_config = ConfigDict(from_attributes=True)
    
    ean: Optional[str] = None
    ubicacion: Optional[str] = None
    articulo: Optional[str] = None
    color: Optional[str] = None
    talla: Optional[str] = None
    posicion_talla: Optional[str] = None
    descripcion_producto: Optional[str] = None
    descripcion_color: Optional[str] = None
    temporada: Optional[str] = None
    cantidad_solicitada: int
    cantidad_servida: int = 0
    estado: str = 'PENDING'

class OrderLineCreate(OrderLineBase):
    """Modelo para crear línea de orden."""
    order_id: int

class OrderLineUpdate(BaseModel):
    """Modelo para actualizar línea de orden."""
    model_config = ConfigDict(from_attributes=True)
    
    cantidad_servida: Optional[int] = None
    estado: Optional[str] = None

class OrderLineResponse(OrderLineBase):
    """Modelo de respuesta para línea de orden."""
    id: int
    order_id: int
    created_at: datetime
    updated_at: datetime


class OrderBase(BaseModel):
    """Modelo base para órdenes."""
    model_config = ConfigDict(from_attributes=True)
    
    numero_orden: str
    cliente: str
    nombre_cliente: Optional[str] = None
    fecha_orden: date
    caja: Optional[str] = None
    prioridad: str = 'NORMAL'
    notas: Optional[str] = None

class OrderCreate(OrderBase):
    """Modelo para crear orden."""
    status_id: int
    order_lines: Optional[List[OrderLineBase]] = []

class OrderUpdate(BaseModel):
    """Modelo para actualizar orden."""
    model_config = ConfigDict(from_attributes=True)
    
    status_id: Optional[int] = None
    operator_id: Optional[int] = None
    fecha_asignacion: Optional[datetime] = None
    fecha_inicio_picking: Optional[datetime] = None
    fecha_fin_picking: Optional[datetime] = None
    caja: Optional[str] = None
    prioridad: Optional[str] = None
    notas: Optional[str] = None

class OrderResponse(OrderBase):
    """Modelo de respuesta para orden."""
    id: int
    status_id: int
    operator_id: Optional[int] = None
    fecha_importacion: datetime
    fecha_asignacion: Optional[datetime] = None
    fecha_inicio_picking: Optional[datetime] = None
    fecha_fin_picking: Optional[datetime] = None
    total_items: int = 0
    items_completados: int = 0
    created_at: datetime
    updated_at: datetime

class OrderDetailResponse(OrderResponse):
    """Modelo de respuesta detallado para orden con sus líneas."""
    order_lines: List[OrderLineResponse] = []
    status: Optional[OrderStatusResponse] = None
    operator: Optional[OperatorResponse] = None


class OrderListItem(BaseModel):
    """Modelo simplificado para listar órdenes."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    numero_orden: str
    cliente: str
    nombre_cliente: Optional[str] = None
    total_items: int = Field(description="Total de unidades solicitadas")
    items_completados: int = Field(default=0, description="Total de unidades servidas")
    progreso: float = Field(default=0.0, description="Porcentaje de progreso (0-100)")
    operario_asignado: Optional[str] = Field(default="Sin asignar", description="Nombre del operario o 'Sin asignar'")
    prioridad: str
    estado: str = Field(description="Nombre del estado de la orden")
    estado_codigo: str = Field(description="Código del estado")
    fecha_orden: date
    fecha_importacion: datetime


class OrderProductDetail(BaseModel):
    """Modelo para detalle de producto en una orden."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    nombre: Optional[str] = Field(None, description="Nombre/descripción del producto")
    descripcion: Optional[str] = Field(None, description="Descripción del color")
    color: Optional[str] = Field(None, description="Código del color")
    talla: Optional[str] = Field(None, description="Talla del producto")
    ubicacion: Optional[str] = Field(None, description="Ubicación en almacén")
    sku: Optional[str] = Field(None, description="Código del artículo/SKU")
    ean: Optional[str] = Field(None, description="Código de barras EAN")
    cantidad_solicitada: int = Field(description="Cantidad pedida")
    cantidad_servida: int = Field(description="Cantidad recogida")
    estado: str = Field(description="Estado de la línea (PENDING, PARTIAL, COMPLETED)")


class OrderDetailFull(BaseModel):
    """Modelo completo para detalle de una orden."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    numero_orden: str
    cliente: str
    nombre_cliente: Optional[str] = None
    fecha_creacion: date = Field(description="Fecha de creación de la orden")
    fecha_limite: Optional[str] = Field(default="Sin fecha límite", description="Fecha límite de la orden")
    total_cajas: str = Field(description="Total de cajas o 'Sin cajas'")
    operario_asignado: str = Field(description="Nombre del operario o 'Sin operario'")
    estado: str = Field(description="Nombre del estado")
    estado_codigo: str = Field(description="Código del estado")
    prioridad: str = Field(description="Prioridad de la orden")
    total_items: int = Field(description="Total de líneas/productos")
    items_completados: int = Field(description="Líneas completadas")
    progreso_porcentaje: float = Field(description="Porcentaje de completitud")
    productos: List[OrderProductDetail] = Field(default=[], description="Lista de productos de la orden")


class OrderHistoryBase(BaseModel):
    """Modelo base para historial de órdenes."""
    model_config = ConfigDict(from_attributes=True)
    
    order_id: int
    status_id: int
    operator_id: Optional[int] = None
    accion: str
    status_anterior: Optional[int] = None
    status_nuevo: Optional[int] = None
    notas: Optional[str] = None
    event_metadata: Optional[Dict[str, Any]] = None

class OrderHistoryCreate(OrderHistoryBase):
    """Modelo para crear entrada de historial."""
    pass

class OrderHistoryResponse(OrderHistoryBase):
    """Modelo de respuesta para historial."""
    id: int
    fecha: datetime
    created_at: datetime


class PickingTaskBase(BaseModel):
    """Modelo base para tareas de picking."""
    model_config = ConfigDict(from_attributes=True)
    
    order_line_id: int
    operator_id: int
    ubicacion: str
    cantidad_a_recoger: int
    cantidad_recogida: int = 0
    estado: str = 'PENDING'
    secuencia: Optional[int] = None
    prioridad: int = 1
    tiempo_estimado_seg: Optional[int] = None
    notas: Optional[str] = None

class PickingTaskCreate(PickingTaskBase):
    """Modelo para crear tarea de picking."""
    pass

class PickingTaskUpdate(BaseModel):
    """Modelo para actualizar tarea de picking."""
    model_config = ConfigDict(from_attributes=True)
    
    cantidad_recogida: Optional[int] = None
    estado: Optional[str] = None
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    notas: Optional[str] = None

class PickingTaskResponse(PickingTaskBase):
    """Modelo de respuesta para tarea de picking."""
    id: int
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    tiempo_real_seg: Optional[int] = None
    intentos: int = 0
    created_at: datetime
    updated_at: datetime

class PickingTaskDetailResponse(PickingTaskResponse):
    """Modelo de respuesta detallado con información de la orden."""
    order_line: Optional[OrderLineResponse] = None
    operator: Optional[OperatorResponse] = None


# ============================================================================
# MODELOS PYDANTIC PARA GESTIÓN DE PRODUCTOS Y UBICACIONES
# ============================================================================

class ProductReferenceBase(BaseModel):
    """Modelo base para referencias de producto."""
    model_config = ConfigDict(from_attributes=True)
    
    referencia: str = Field(
        ..., 
        pattern=r'^[0-9A-Fa-f]+$',
        min_length=1,
        max_length=50,
        description="Código hexadecimal único del producto (solo 0-9, A-F)"
    )
    nombre_producto: str = Field(
        ..., 
        min_length=1, 
        max_length=200,
        description="Nombre descriptivo del producto"
    )
    color_id: str = Field(
        ..., 
        max_length=50,
        description="ID del color (numérico o alfanumérico)"
    )
    talla: str = Field(
        ..., 
        max_length=20,
        description="Talla del producto (S, M, L, 38, 40, etc.)"
    )
    descripcion_color: Optional[str] = Field(None, max_length=100)
    ean: Optional[str] = Field(None, max_length=50)
    sku: Optional[str] = Field(None, max_length=100)
    temporada: Optional[str] = Field(None, max_length=50)
    activo: bool = True


class ProductReferenceCreate(ProductReferenceBase):
    """Modelo para crear referencia de producto."""
    pass


class ProductReferenceUpdate(BaseModel):
    """Modelo para actualizar referencia de producto."""
    model_config = ConfigDict(from_attributes=True)
    
    nombre_producto: Optional[str] = Field(None, min_length=1, max_length=200)
    color_id: Optional[str] = Field(None, max_length=50)
    talla: Optional[str] = Field(None, max_length=20)
    descripcion_color: Optional[str] = Field(None, max_length=100)
    ean: Optional[str] = Field(None, max_length=50)
    sku: Optional[str] = Field(None, max_length=100)
    temporada: Optional[str] = Field(None, max_length=50)
    activo: Optional[bool] = None


class ProductReferenceResponse(ProductReferenceBase):
    """Modelo de respuesta para referencia de producto."""
    id: int
    created_at: datetime
    updated_at: datetime


class ProductLocationBase(BaseModel):
    """Modelo base para ubicaciones de producto."""
    model_config = ConfigDict(from_attributes=True)
    
    pasillo: str = Field(
        ..., 
        max_length=10,
        description="Identificador del pasillo (alfanumérico: A, B1, C3)"
    )
    lado: str = Field(
        ..., 
        max_length=20,
        description="Lado del pasillo (IZQUIERDA, DERECHA, IZQ, DER, L, R)"
    )
    ubicacion: str = Field(
        ..., 
        max_length=20,
        description="Posición específica en el lado"
    )
    altura: int = Field(
        ..., 
        ge=1, 
        le=10,
        description="Nivel vertical (1=bajo, 5=alto)"
    )
    stock_minimo: int = Field(
        default=0, 
        ge=0,
        description="Stock mínimo para alerta de reposición"
    )
    stock_actual: int = Field(
        default=0, 
        ge=0,
        description="Stock actual en esta ubicación"
    )
    prioridad: int = Field(
        default=3, 
        ge=1, 
        le=5,
        description="Prioridad para picking (1=alta, 5=baja)"
    )
    activa: bool = True


class ProductLocationCreate(ProductLocationBase):
    """Modelo para crear ubicación de producto (product_id viene en la URL)."""
    pass


class ProductLocationUpdate(BaseModel):
    """Modelo para actualizar ubicación de producto."""
    model_config = ConfigDict(from_attributes=True)
    
    pasillo: Optional[str] = Field(None, max_length=10)
    lado: Optional[str] = Field(None, max_length=20)
    ubicacion: Optional[str] = Field(None, max_length=20)
    altura: Optional[int] = Field(None, ge=1, le=10)
    stock_minimo: Optional[int] = Field(None, ge=0)
    stock_actual: Optional[int] = Field(None, ge=0)
    prioridad: Optional[int] = Field(None, ge=1, le=5)
    activa: Optional[bool] = None


class ProductLocationResponse(ProductLocationBase):
    """Modelo de respuesta para ubicación de producto."""
    id: int
    product_id: int
    codigo_ubicacion: str = Field(
        ...,
        description="Código de ubicación generado automáticamente (propiedad computada)"
    )
    created_at: datetime
    updated_at: datetime


class ProductReferenceWithLocations(ProductReferenceResponse):
    """Modelo de respuesta para producto con sus ubicaciones."""
    locations: List[ProductLocationResponse] = Field(
        default=[],
        description="Lista de ubicaciones donde está almacenado este producto"
    )


class ProductLocationWithProduct(ProductLocationResponse):
    """Modelo de respuesta para ubicación con información del producto."""
    product: Optional[ProductReferenceResponse] = Field(
        None,
        description="Información del producto en esta ubicación"
    )
