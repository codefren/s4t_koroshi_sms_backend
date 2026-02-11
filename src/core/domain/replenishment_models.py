"""
Pydantic models for replenishment request system.

Models for API requests/responses related to stock replenishment
between picking and replenishment zones.
"""

from pydantic import BaseModel, Field
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
    
    class Config:
        from_attributes = True


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


class ReplenishmentRequestListResponse(BaseModel):
    """Paginated list response"""
    total: int
    page: int
    per_page: int
    total_pages: int
    requests: list[ReplenishmentRequestListItem]


class StartExecutionRequest(BaseModel):
    """Request to start execution"""
    executor_id: int = Field(..., description="Operator who will execute replenishment")


class RejectRequest(BaseModel):
    """Request to reject replenishment"""
    notes: str = Field(..., description="Rejection reason")
