"""
Pydantic models for replenishment request system.

Models for API requests/responses related to stock replenishment
between picking and replenishment zones.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime


class ReplenishmentRequestCreate(BaseModel):
    """Request body for creating replenishment request from PDA (WebSocket)"""
    location_destino_id: int = Field(..., description="Picking location without stock")
    product_id: int = Field(..., description="Product needing replenishment")
    requested_quantity: Optional[int] = Field(None, description="Requested quantity (if not sent, calculates deficit)")
    requester_id: int = Field(..., description="Operator requesting")
    order_id: Optional[int] = Field(None, description="Related order (if from picking)")


class LocationInfo(BaseModel):
    """Location information"""
    id: int
    codigo: str
    stock_actual: int
    almacen_id: int


class ProductInfo(BaseModel):
    """Basic product information"""
    id: int
    nombre: str
    sku: Optional[str]
    ean: Optional[str]


class ReplenishmentRequestResponse(BaseModel):
    """Replenishment request response"""
    id: int
    status: str
    priority: str
    requested_quantity: int
    
    product: ProductInfo
    location_origin: Optional[LocationInfo]
    location_destination: LocationInfo
    
    requester_name: str
    executor_name: Optional[str]
    
    requested_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    order_id: Optional[int]
    notes: Optional[str]
    
    model_config = ConfigDict(from_attributes=True)


class ReplenishmentRequestListItem(BaseModel):
    """List item for replenishment requests (summarized version)"""
    id: int
    status: str
    priority: str
    requested_quantity: int
    
    product_name: str
    product_sku: Optional[str]
    
    origin_code: Optional[str]
    origin_stock: Optional[int]
    destination_code: str
    destination_stock: int
    
    requester_name: str
    executor_name: Optional[str]
    
    requested_at: datetime
    time_waiting: str  # "15 min", "2 hours", etc.


class PriorityCounts(BaseModel):
    """Count of requests per priority"""
    URGENT: int = 0
    HIGH: int = 0


class StatusCounts(BaseModel):
    """Count of requests per status"""
    READY: int = 0
    IN_PROGRESS: int = 0
    COMPLETED: int = 0
    REJECTED: int = 0


class ReplenishmentRequestListResponse(BaseModel):
    """Paginated list response"""
    total: int
    page: int
    per_page: int
    total_pages: int
    status_counts: StatusCounts
    priority_counts: PriorityCounts
    requests: list[ReplenishmentRequestListItem]


class StartExecutionRequest(BaseModel):
    """Request to start execution"""
    executor_id: int = Field(..., description="Operator who will execute replenishment")


class RejectRequest(BaseModel):
    """Request to reject replenishment"""
    notes: str = Field(..., description="Rejection reason")


# ============================================================================
# MODELOS DE RESPUESTA PARA ENDPOINTS DE REPOSICIÓN
# ============================================================================

class StartReplenishmentResponse(BaseModel):
    """Respuesta para inicio de ejecución de reposición."""
    success: bool
    message: str
    request_id: int
    status: str
    executor: str
    started_at: str


class LocationStockChange(BaseModel):
    """Cambio de stock en una ubicación."""
    code: str
    stock_before: int
    stock_after: int


class CompleteReplenishmentResponse(BaseModel):
    """Respuesta para completar reposición."""
    success: bool
    message: str
    request_id: int
    quantity_moved: int
    origin_location: LocationStockChange
    destination_location: LocationStockChange
    completed_at: str


class RejectReplenishmentResponse(BaseModel):
    """Respuesta para rechazar reposición."""
    success: bool
    message: str
    request_id: int
    reason: str


class OperatorInfo(BaseModel):
    """Información de operario en detalle de reposición."""
    id: int
    nombre: str
    codigo: str


class ReplenishmentRequestDetail(BaseModel):
    """Detalle completo de una solicitud de reposición."""
    id: int
    status: str
    priority: str
    requested_quantity: int
    product: Optional[ProductInfo] = None
    location_origin: Optional[LocationInfo] = None
    location_destination: Optional[LocationInfo] = None
    requester: Optional[OperatorInfo] = None
    executor: Optional[OperatorInfo] = None
    order_id: Optional[int] = None
    notes: Optional[str] = None
    requested_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    time_waiting: str


class DiagnosticLocationDetail(BaseModel):
    """Detalle de ubicación en diagnóstico."""
    location_id: int
    product_id: int
    product_name: str
    sku: str
    location_code: str
    stock_actual: int
    stock_minimo: int
    deficit: int
    has_origin_stock: bool
    origin_stock: int
    reason: str


class ReplenishmentDiagnosticResponse(BaseModel):
    """Respuesta de diagnóstico del sistema de reposición."""
    system_operator_exists: bool
    system_operator_id: Optional[int] = None
    picking_warehouse_id: int
    replenishment_warehouse_id: int
    total_low_stock_locations: int
    ignored_zero_minimum: int
    ignored_null_minimum: int
    already_has_pending_request: int
    missing_request: int
    active_requests_total: int
    details: list[DiagnosticLocationDetail]
