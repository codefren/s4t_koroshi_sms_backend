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
    total_lines: int
    
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
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "order_number": "ORD-12345",
                "sku": "ABC123",
                "quantity_served": 10,
                "box_code": "BOX-001"
            }
        }
    )
    
    order_number: str = Field(..., description="Order number to update")
    sku: str = Field(..., description="SKU of product to update")
    quantity_served: int = Field(..., ge=0, description="Quantity served")
    box_code: Optional[str] = Field(None, description="Box tracking code (optional)")


class UpdateOrderResponse(BaseModel):
    """Response after updating order"""
    status: str
    message: str
    order_number: str
    sku: str
    quantity_served: int


class OrderLineUpdate(BaseModel):
    """Single line update within a batch"""
    sku: str = Field(..., min_length=8, description="SKU of product (minimum 8 characters)")
    quantity_served: int = Field(..., ge=0, description="Quantity served for this SKU")
    box_code: Optional[str] = Field(None, description="Box tracking code (optional)")


class BatchUpdateOrderRequest(BaseModel):
    """Request to update all lines of an order at once"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "order_number": "ORD-12345",
                "lines": [
                    {"sku": "ABC123", "quantity_served": 10, "box_code": "BOX-001"},
                    {"sku": "DEF456", "quantity_served": 5, "box_code": "BOX-001"},
                    {"sku": "GHI789", "quantity_served": 0}
                ]
            }
        }
    )
    
    order_number: str = Field(..., description="Order number to update")
    lines: List[OrderLineUpdate] = Field(..., description="List of all order lines to update")


class BatchUpdateOrderResponse(BaseModel):
    """Response after batch update"""
    status: str
    message: str
    order_number: str
    order_status: str = Field(..., description="Order status after update: PENDING or READY")
    lines_updated: int
    lines_completed: int
    lines_partial: int
    lines_pending: int


# ============================================================================
# ERROR SCHEMAS
# ============================================================================

class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None


# ============================================================================
# STOCK MOVEMENT SCHEMAS
# ============================================================================

class StockLineItem(BaseModel):
    """Single stock item in a stock movement request"""
    sku: str = Field(..., max_length=100, description="Product SKU")
    quantity: int = Field(..., gt=0, description="Quantity to move (must be positive)")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sku": "ABC123",
                "quantity": 50
            }
        }
    )


class RegisterStockRequest(BaseModel):
    """Request to register stock movements between locations"""
    origin: str = Field(..., max_length=10, description="Origin location (max 10 chars)")
    destinity: str = Field(..., max_length=10, description="Destination location (max 10 chars)")
    stock_line: List[StockLineItem] = Field(..., min_length=1, description="List of stock items to move")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "origin": "WAREHOUSE1",
                "destinity": "STORE1",
                "stock_line": [
                    {"sku": "ABC123", "quantity": 10},
                    {"sku": "DEF456", "quantity": 25},
                    {"sku": "ABC123", "quantity": 5}
                ]
            }
        }
    )


class RegisterStockResponse(BaseModel):
    """Response after registering stock movements"""
    status: str = Field(..., description="Success or error status")
    message: str = Field(..., description="Descriptive message")
    total_lines_received: int = Field(..., description="Total number of lines in request")
    unique_skus_processed: int = Field(..., description="Number of unique SKUs processed")
    products_auto_created: int = Field(..., description="Number of products auto-created")
    records_created: int = Field(..., description="Number of stock records created")


# ============================================================================
# BOX NUMBER REGISTRATION SCHEMAS
# ============================================================================

class RegisterBoxNumberRequest(BaseModel):
    """Request to register a box number for external validation"""
    box_number: str = Field(
        ..., 
        max_length=20, 
        min_length=1,
        description="Box number (unique, max 20 chars)"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "box_number": "BOX-12345"
            }
        }
    )


class RegisterBoxNumberResponse(BaseModel):
    """Response after registering a box number"""
    status: str = Field(..., description="Success or error")
    message: str = Field(..., description="Descriptive message")
    box_number: str = Field(..., description="Box number registered")
