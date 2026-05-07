"""
FastAPI routes for B2B Customer API Service.
"""
import csv
import io
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os

from src.adapters.secondary.database.config import get_db
from src.adapters.secondary.database.orm import Customer
from src.api_service.auth import verify_customer_api_key
from src.api_service.schemas import (
    OrderListItem,
    OrdersListResponse,
    OrderLinesResponse,
    UpdateOrderRequest,
    UpdateOrderResponse,
    CustomerResponse,
    BatchUpdateOrderRequest,
    BatchUpdateOrderResponse,
    PickedBatchUpdateRequest,
    RegisterStockRequest,
    RegisterStockResponse,
    RegisterBoxNumberRequest,
    RegisterBoxNumberResponse,
    SeasonsListResponse,
    ProductsBySeasonResponse,
    PackingProListResponse,
    PackingProLinesResponse,

)
from src.api_service.service import (
    get_customer_b2b_orders,
    get_customer_b2c_orders,
    get_order_lines_for_customer,
    update_order_quantity,
    batch_update_order,
    batch_update_picked_order,
    register_stock,
    register_box_number,
    get_available_seasons,
    get_products_by_season,
    get_products_by_season_csv,
    get_packing_pro_list,
    get_packing_pro_lines,
)


router = APIRouter()


@router.get("/me", response_model=CustomerResponse, tags=["Customer"])
def get_current_customer(
    customer: Customer = Depends(verify_customer_api_key)
):
    """
    Get current authenticated customer information.
    
    Returns customer details including assigned warehouses.
    """
    return customer


@router.get("/orders/b2b", response_model=OrdersListResponse, tags=["Orders"])
def list_b2b_orders(
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
def list_b2c_orders(
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
def get_order_lines(
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
    "/orders/batch-update",
    response_model=BatchUpdateOrderResponse,
    tags=["Orders"]
)
def batch_update_order_endpoint(
    request: BatchUpdateOrderRequest,
    customer: Customer = Depends(verify_customer_api_key),
    db: Session = Depends(get_db)
):
    """
    Update ALL lines of an order at once (Batch Update).
    
    This endpoint processes all order lines in a single transaction:
    - Updates quantity served for all products
    - Automatically changes order status to READY when all lines completed
    - Orders with READY status disappear from order lists
    - Optionally assigns items to packing boxes
    
    **Order Status Logic:**
    - If ALL lines have quantity_served >= quantity_requested → Order status = READY
    - Otherwise → Order status = PENDING
    
    **READY Orders:**
    - Automatically filtered from /orders/b2b and /orders/b2c endpoints
    - Cannot access lines via /orders/{id}/lines
    - Cannot be updated again
    
    **Authentication:** Requires X-Api-Key header
    
    **Example:**
    ```
    curl -X PUT -H "X-Api-Key: cust_live_abc123..." \
         -H "Content-Type: application/json" \
         -d '{
           "order_number": "ORD-12345",
           "lines": [
             {"sku": "ABC123", "quantity_served": 10, "box_code": "BOX-001"},
             {"sku": "DEF456", "quantity_served": 5, "box_code": "BOX-001"},
             {"sku": "GHI789", "quantity_served": 0}
           ]
         }' \
         http://localhost:8000/api/service/orders/batch-update
    ```
    
    **Response:**
    ```json
    {
        "status": "success",
        "message": "Updated 3 lines for order ORD-12345",
        "order_number": "ORD-12345",
        "order_status": "READY",
        "lines_updated": 3,
        "lines_completed": 2,
        "lines_partial": 0,
        "lines_pending": 1
    }
    ```
    """
    return batch_update_order(
        order_number=request.order_number,
        lines_updates=request.lines,
        customer=customer,
        db=db
    )


@router.put(
    "/orders/{order_number}/batch-update",
    tags=["Orders"]
)
def batch_update_picked_order_endpoint(
    order_number: str,
    request: PickedBatchUpdateRequest,
    # customer: Customer = Depends(verify_customer_api_key),
    db: Session = Depends(get_db)
):
    """
    Update ALL lines of an order that is in **PICKED** status.
    If XPO expedition succeeds, returns the PDF label as a direct download.
    """
    result = batch_update_picked_order(
        order_number=order_number,
        lines_updates=request.lines,
        db=db
    )

    return result


@router.put(
    "/orders/update",
    response_model=UpdateOrderResponse,
    tags=["Orders"],
    deprecated=True
)
def update_order(
    request: UpdateOrderRequest,
    customer: Customer = Depends(verify_customer_api_key),
    db: Session = Depends(get_db)
):
    """
    **DEPRECATED:** Use /orders/batch-update instead.
    
    Update quantity served for a product in an order (single line).
    
    This endpoint is deprecated. Please use /orders/batch-update to update
    all lines of an order at once.
    """
    return update_order_quantity(
        order_number=request.order_number,
        sku=request.sku,
        quantity_served=request.quantity_served,
        box_code=request.box_code,
        customer=customer,
        db=db
    )


@router.post(
    "/stock/register",
    response_model=RegisterStockResponse,
    tags=["Stock"]
)
def register_stock_movements(
    request: RegisterStockRequest,
    customer: Customer = Depends(verify_customer_api_key),
    db: Session = Depends(get_db)
):
    """
    Register stock movements between locations.
    
    **Process:**
    1. Receives list of stock items with SKU and quantity
    2. Accumulates quantities for duplicate SKUs
    3. Auto-creates products in catalog if SKU doesn't exist
    4. Creates stock movement records with status PENDING
    
    **Features:**
    - Duplicate SKU handling: quantities are accumulated
    - Auto-creation: missing products are created with name AUTO-{SKU}
    - Status tracking: all records start as PENDING
    
    **Request example:**
    ```json
    {
        "origin": "WAREHOUSE1",
        "destinity": "STORE1",
        "stock_line": [
            {"sku": "ABC123", "quantity": 10},
            {"sku": "DEF456", "quantity": 25},
            {"sku": "ABC123", "quantity": 5}
        ]
    }
    ```
    
    **Response includes:**
    - Total lines received
    - Unique SKUs processed
    - Products auto-created
    - Records created in database
    
    **Authentication:** Required - Customer API Key in X-API-Key header.
    """
    return register_stock(request=request, db=db)


@router.post(
    "/box-number/register",
    response_model=RegisterBoxNumberResponse,
    tags=["Box Number"],
    responses={
        409: {
            "description": "Box number already verified and registered",
            "content": {
                "application/json": {
                    "example": {"detail": "Box number 'BOX-12345' has already been verified and registered"}
                }
            }
        }
    }
)
def register_box_number_endpoint(
    request: RegisterBoxNumberRequest,
    customer: Customer = Depends(verify_customer_api_key),
    db: Session = Depends(get_db)
):
    """
    Register a box number for external validation.
    
    **Process:**
    1. Receives a box number (unique identifier)
    2. Checks if already registered
    3. Creates new record with status PENDING if new
    4. Returns HTTP 409 Conflict if duplicate
    
    **Features:**
    - Strict uniqueness: duplicate registrations return 409 Conflict error
    - Status tracking: PENDING → SYNCHRONIZED → ERROR
    - Unique constraint: box_number must be unique in database
    
    **Request example:**
    ```json
    {
        "box_number": "BOX-12345"
    }
    ```
    
    **Success Response (201):**
    ```json
    {
        "status": "success",
        "message": "Box number 'BOX-12345' registered successfully",
        "box_number": "BOX-12345"
    }
    ```
    
    **Error Response (409):**
    ```json
    {
        "detail": "Box number 'BOX-12345' has already been verified and registered"
    }
    ```
    
    **Authentication:** Required - Customer API Key in X-API-Key header.
    """
    return register_box_number(request=request, db=db)


@router.get("/packing-pro", response_model=PackingProListResponse, tags=["Packing Pro"])
def list_packing_pro(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    viewed: Optional[bool] = Query(None, description="Filter by view status: true=viewed, false=not viewed, null=all"),
    customer: Customer = Depends(verify_customer_api_key),
    db: Session = Depends(get_db)
):
    """
    List packing_pro headers with pagination.

    Returns all supplier merchandise reception records ordered by creation date (newest first).

    **Filters:** Use `viewed` to filter by whether the customer has already seen each record.

    **Authentication:** Requires X-Api-Key header
    """
    return get_packing_pro_list(customer, db, skip, limit, viewed)


@router.get(
    "/packing-pro/{company}/{packing_id}/lines",
    response_model=PackingProLinesResponse,
    tags=["Packing Pro"]
)
def get_packing_pro_lines_endpoint(
    company: str,
    packing_id: str,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    customer: Customer = Depends(verify_customer_api_key),
    db: Session = Depends(get_db)
):
    """
    Get lines for a specific packing_pro identified by company + packing_id.

    Returns line detail including resolved SKU from the product catalogue.

    **Authentication:** Requires X-Api-Key header
    """
    return get_packing_pro_lines(company, packing_id, db, skip, limit)


@router.get("/health", tags=["Health"])
def health_check():
    """
    Health check endpoint for B2B API Service.
    """
    return {
        "status": "healthy",
        "service": "B2B Customer API",
        "version": "1.0.0"
    }


# ─── Products by Season ─────────────────────────────────────────────────────

@router.get(
    "/products/seasons",
    response_model=SeasonsListResponse,
    tags=["Products"],
    summary="List available seasons",
)
async def list_seasons(
    customer: Customer = Depends(verify_customer_api_key),
    db: Session = Depends(get_db),
):
    """
    Returns the list of distinct season names available in the product catalog.

    Use this endpoint to discover valid season values before calling
    `/products/by-season/{temporada}`.

    **Authentication:** Requires `X-Api-Key` header.

    **Example:**
    ```
    curl -H "X-Api-Key: cust_live_abc123..." \\
         http://localhost:8000/api/service/products/seasons
    ```

    **Response:**
    ```json
    {
        "seasons": ["Invierno 2024", "Primavera 2025", "Verano 2025"],
        "total": 3
    }
    ```
    """
    seasons = get_available_seasons(db)
    return SeasonsListResponse(seasons=seasons, total=len(seasons))


@router.get(
    "/products/by-season/{temporada}",
    response_model=ProductsBySeasonResponse,
    tags=["Products"],
    summary="Download products by season",
    responses={
        404: {
            "description": "No products found for the given season",
            "content": {
                "application/json": {
                    "example": {"detail": "No products found for season 'Verano 2025'"}
                }
            },
        }
    },
)
async def get_products_by_season_endpoint(
    temporada: str,
    skip: int = Query(0, ge=0, description="Number of records to skip (pagination)"),
    limit: int = Query(100, ge=1, le=500, description="Max records to return per page"),
    only_active: bool = Query(True, description="Exclude inactive products from catalog"),
    customer: Customer = Depends(verify_customer_api_key),
    db: Session = Depends(get_db),
):
    """
    Download the full product catalog for a specific season.

    Returns all products whose `temporada` field matches the given value
    (case-insensitive). Supports pagination and active-only filtering.

    **Path parameter:**
    - `temporada`: Season name, e.g. `Verano 2025` or `Invierno 2024`.
      Use `/products/seasons` to list valid values.

    **Query parameters:**
    | Param | Default | Description |
    |---|---|---|
    | `skip` | 0 | Pagination offset |
    | `limit` | 100 | Max records (1–500) |
    | `only_active` | true | Exclude inactive products |

    **Authentication:** Requires `X-Api-Key` header.

    **Example — first page:**
    ```
    curl -H "X-Api-Key: cust_live_abc123..." \\
         "http://localhost:8000/api/service/products/by-season/Verano%202025?skip=0&limit=100"
    ```

    **Example — include inactive:**
    ```
    curl -H "X-Api-Key: cust_live_abc123..." \\
         "http://localhost:8000/api/service/products/by-season/Verano%202025?only_active=false"
    ```

    **Response:**
    ```json
    {
        "temporada": "Verano 2025",
        "total_count": 342,
        "skip": 0,
        "limit": 100,
        "only_active": true,
        "products": [
            {
                "id": 1,
                "referencia": "A1B2C3",
                "sku": "KOR-A1B2C3",
                "nombre_producto": "Camisa Polo Manga Corta",
                "color_id": "000001",
                "nombre_color": "Rojo",
                "talla": "M",
                "posicion_talla": 3,
                "temporada": "Verano 2025",
                "activo": true
            }
        ]
    }
    ```
    """
    result = get_products_by_season(
        temporada=temporada,
        db=db,
        skip=skip,
        limit=limit,
        only_active=only_active,
    )
    return ProductsBySeasonResponse(**result)


@router.get(
    "/products/by-season/{temporada}/csv",
    tags=["Products"],
    summary="Download products by season as CSV",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "CSV file download",
            "content": {"text/csv": {}},
        },
        404: {
            "description": "No products found for the given season",
            "content": {
                "application/json": {
                    "example": {"detail": "No products found for season 'V99'"}
                }
            },
        },
    },
)
async def download_products_by_season_csv(
    temporada: str,
    only_active: bool = Query(True, description="Exclude inactive products from catalog"),
    customer: Customer = Depends(verify_customer_api_key),
    db: Session = Depends(get_db),
):
    """
    Download the full product catalog for a season as a **CSV file**.

    Returns all matching products in a single file — no pagination needed.
    The response triggers a browser file download with a descriptive filename.

    **CSV columns:**
    `id`, `referencia`, `sku`, `nombre_producto`, `color_id`, `nombre_color`,
    `talla`, `posicion_talla`, `temporada`, `activo`

    **Path parameter:**
    - `temporada`: Season code, e.g. `V25` or `I16`.
      Use `/products/seasons` to list valid values.

    **Query parameters:**
    | Param | Default | Description |
    |---|---|---|
    | `only_active` | true | Exclude inactive products |

    **Authentication:** Requires `X-Api-Key` header.

    **Example:**
    ```
    curl -H "X-Api-Key: cust_live_abc123..." \\
         "http://localhost:8000/api/service/products/by-season/V25/csv" \\
         --output productos_V25.csv
    ```

    **CSV output sample:**
    ```
    id,referencia,sku,nombre_producto,color_id,nombre_color,talla,posicion_talla,temporada,activo
    1,A1B2C3,KOR-A1B2C3,Camisa Polo Manga Corta,000001,Rojo,M,3,V25,True
    2,D4E5F6,KOR-D4E5F6,Pantalon Slim Fit,000002,Azul,L,4,V25,True
    ```
    """
    products = get_products_by_season_csv(
        temporada=temporada,
        db=db,
        only_active=only_active,
    )

    # Build CSV in memory
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    # Header row
    writer.writerow([
        "id", "referencia", "sku", "nombre_producto",
        "color_id", "nombre_color", "talla", "posicion_talla",
        "temporada", "activo",
    ])

    # Data rows
    for p in products:
        writer.writerow([
            p.id,
            p.referencia,
            p.sku or "",
            p.nombre_producto,
            p.color_id,
            p.nombre_color or "",
            p.talla,
            p.posicion_talla if p.posicion_talla is not None else "",
            p.temporada or "",
            p.activo,
        ])

    output.seek(0)
    safe_season = temporada.strip().replace(" ", "_")
    filename = f"productos_{safe_season}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Total-Count": str(len(products)),
        },
    )
