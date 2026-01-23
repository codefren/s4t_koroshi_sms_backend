"""
Pydantic schemas for B2B API Service.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


# ============================================================================
# CUSTOMER SCHEMAS
# ============================================================================

class CustomerBase(BaseModel):
    customer_code: str
    name: str = Field(validation_alias="nombre")
    email: Optional[str] = None
    phone: Optional[str] = Field(None, validation_alias="telefono")


class CustomerResponse(CustomerBase):
    id: int
    active: bool = Field(validation_alias="activo")
    last_access: Optional[datetime] = Field(None, validation_alias="ultimo_acceso")
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ============================================================================
# ORDER SCHEMAS
# ============================================================================

class OrderListItem(BaseModel):
    """Minimal order info for listing"""
    id: int
    order_number: str = Field(validation_alias="numero_orden")
    type: str
    customer_name: Optional[str] = Field(None, validation_alias="nombre_cliente")
    
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class OrdersListResponse(BaseModel):
    """Paginated response for orders list"""
    total_count: int
    skip: int
    limit: int
    orders: List[OrderListItem]


class OrderLineSimple(BaseModel):
    """Minimal order line with only SKU and quantity"""
    sku: Optional[str] = None
    quantity: int = Field(..., description="Quantity requested")
    quantity_served: int = 0
    
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class OrderLinesResponse(BaseModel):
    """Response for order lines endpoint"""
    order_id: int
    order_number: str
    total_count: int
    skip: int
    limit: int
    lines: List[OrderLineSimple]


# ============================================================================
# UPDATE REQUEST SCHEMAS
# ============================================================================

class UpdateOrderRequest(BaseModel):
    """Request to update order line quantity"""
    order_number: str = Field(..., description="Order number to update")
    sku: str = Field(..., description="SKU of product to update")
    quantity_served: int = Field(..., ge=0, description="Quantity served")
    box_code: Optional[str] = Field(None, description="Box tracking code (optional)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "order_number": "ORD-12345",
                "sku": "ABC123",
                "quantity_served": 10,
                "box_code": "BOX-001"
            }
        }


class UpdateOrderResponse(BaseModel):
    """Response after updating order"""
    status: str
    message: str
    order_number: str
    sku: str
    quantity_served: int


# ============================================================================
# ERROR SCHEMAS
# ============================================================================

class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
