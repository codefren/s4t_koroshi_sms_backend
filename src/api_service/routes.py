"""
FastAPI routes for B2B Customer API Service.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from src.adapters.secondary.database.config import get_db
from src.adapters.secondary.database.orm import Customer
from src.api_service.auth import verify_customer_api_key
from src.api_service.schemas import (
    OrderListItem,
    OrdersListResponse,
    OrderLinesResponse,
    UpdateOrderRequest,
    UpdateOrderResponse,
    CustomerResponse
)
from src.api_service.service import (
    get_customer_b2b_orders,
    get_customer_b2c_orders,
    get_order_lines_for_customer,
    update_order_quantity
)


router = APIRouter()


@router.get("/me", response_model=CustomerResponse, tags=["Customer"])
async def get_current_customer(
    customer: Customer = Depends(verify_customer_api_key)
):
    """
    Get current authenticated customer information.
    
    Returns customer details including assigned warehouses.
    """
    return customer


@router.get("/orders/b2b", response_model=OrdersListResponse, tags=["Orders"])
async def list_b2b_orders(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    viewed: Optional[bool] = Query(None, description="Filter by view status: true=viewed, false=not viewed, null=all"),
    customer: Customer = Depends(verify_customer_api_key),
    db: Session = Depends(get_db)
):
    """
    List B2B orders for authenticated customer with pagination.
    
    Returns only B2B type orders from warehouses assigned to the customer.
    Results are paginated and sorted by creation date (newest first).
    
    **Authentication:** Requires X-Api-Key header
    
    **Pagination:** Use skip and limit parameters
    
    **Filters:** Use viewed parameter to filter by view status
    
    **Example:**
    ```
    curl -H "X-Api-Key: cust_live_abc123..." \
         "http://localhost:8000/api/service/orders/b2b?skip=0&limit=50"
    ```
    
    **Response:**
    ```json
    {
        "total_count": 150,
        "skip": 0,
        "limit": 50,
        "orders": [
            {
                "id": 123,
                "order_number": "ORD-12345",
                "type": "B2B",
                "customer_name": "Cliente B2B Ejemplo"
            }
        ]
    }
    ```
    """
    return get_customer_b2b_orders(customer, db, skip, limit, viewed)


@router.get("/orders/b2c", response_model=OrdersListResponse, tags=["Orders"])
async def list_b2c_orders(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    viewed: Optional[bool] = Query(None, description="Filter by view status: true=viewed, false=not viewed, null=all"),
    customer: Customer = Depends(verify_customer_api_key),
    db: Session = Depends(get_db)
):
    """
    List B2C orders for authenticated customer with pagination.
    
    Returns only B2C type orders from warehouses assigned to the customer.
    Results are paginated and sorted by creation date (newest first).
    
    **Authentication:** Requires X-Api-Key header
    
    **Pagination:** Use skip and limit parameters
    
    **Filters:** Use viewed parameter to filter by view status
    
    **Example:**
    ```
    curl -H "X-Api-Key: cust_live_abc123..." \
         "http://localhost:8000/api/service/orders/b2c?skip=0&limit=50"
    ```
    
    **Response:**
    ```json
    {
        "total_count": 85,
        "skip": 0,
        "limit": 50,
        "orders": [
            {
                "id": 456,
                "order_number": "ORD-67890",
                "type": "B2C",
                "customer_name": "Cliente B2C Ejemplo"
            }
        ]
    }
    ```
    """
    return get_customer_b2c_orders(customer, db, skip, limit, viewed)


@router.get(
    "/orders/{order_id}/lines",
    response_model=OrderLinesResponse,
    tags=["Orders"]
)
async def get_order_lines(
    order_id: int,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    viewed: Optional[bool] = Query(None, description="Filter lines by view status: true=viewed, false=not viewed, null=all"),
    customer: Customer = Depends(verify_customer_api_key),
    db: Session = Depends(get_db)
):
    """
    Get order lines with SKU and quantity for a specific order.
    
    Returns minimal order line data: SKU and quantity with pagination support.
    Validates customer has access to the order's warehouse.
    
    **Authentication:** Requires X-Api-Key header
    
    **Pagination:** Use skip and limit parameters
    
    **Example:**
    ```
    curl -H "X-Api-Key: cust_live_abc123..." \
         "http://localhost:8000/api/service/orders/123/lines?skip=0&limit=50"
    ```
    
    **Response:**
    ```json
    {
        "order_id": 123,
        "order_number": "ORD-12345",
        "total_count": 150,
        "skip": 0,
        "limit": 50,
        "lines": [
            {"sku": "ABC123", "quantity": 10, "quantity_served": 5},
            {"sku": "DEF456", "quantity": 5, "quantity_served": 0}
        ]
    }
    ```
    """
    return get_order_lines_for_customer(order_id, customer, db, skip, limit, viewed)


@router.put(
    "/orders/update",
    response_model=UpdateOrderResponse,
    tags=["Orders"]
)
async def update_order(
    request: UpdateOrderRequest,
    customer: Customer = Depends(verify_customer_api_key),
    db: Session = Depends(get_db)
):
    """
    Update quantity served for a product in an order.
    
    This endpoint allows customers to:
    - Update the quantity served for a specific product
    - Automatically create the product if it doesn't exist
    - Optionally assign items to a packing box using box_code
    
    **Product Auto-creation:**
    If the SKU doesn't exist in the system, a new product will be created
    automatically with minimal required data.
    
    **Packing Box Assignment:**
    If `box_code` is provided, the order line will be assigned to that box.
    If the box doesn't exist, it will be created.
    
    **Authentication:** Requires X-Api-Key header
    
    **Example:**
    ```
    curl -X PUT -H "X-Api-Key: cust_live_abc123..." \
         -H "Content-Type: application/json" \
         -d '{
           "order_number": "ORD-12345",
           "sku": "ABC123",
           "quantity_served": 10,
           "box_code": "BOX-001"
         }' \
         http://localhost:8000/api/service/orders/update
    ```
    
    **Response:**
    ```json
    {
        "status": "success",
        "message": "Updated ABC123 quantity to 10",
        "order_id": 123,
        "order_number": "ORD-12345",
        "order_line_id": 456,
        "sku": "ABC123",
        "quantity_served": 10,
        "previous_quantity": 5
    }
    ```
    """
    return update_order_quantity(
        order_number=request.order_number,
        sku=request.sku,
        quantity_served=request.quantity_served,
        box_code=request.box_code,
        customer=customer,
        db=db
    )


@router.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint for B2B API Service.
    """
    return {
        "status": "healthy",
        "service": "B2B Customer API",
        "version": "1.0.0"
    }
