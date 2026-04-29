"""
Business logic for B2B API Service operations.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from typing import List, Optional
from datetime import datetime, timezone
import requests
import json
import os
import logging

from src.api_service.xpo_service import XpoExpedicionParams, send_xpo_expedicion

XPO_LABELS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "media", "xpo", "labels"
)


def _download_xpo_pdf(consignment_id: str, pdf_url: str) -> Optional[str]:
    """Downloads the XPO label PDF and returns its relative path for /media serving."""
    try:
        os.makedirs(XPO_LABELS_DIR, exist_ok=True)
        filename  = f"{consignment_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        full_path = os.path.join(XPO_LABELS_DIR, filename)
        r = requests.get(pdf_url, timeout=30)
        r.raise_for_status()
        with open(full_path, "wb") as f:
            f.write(r.content)
        return f"xpo/labels/{filename}"   # relativa a /media
    except Exception as exc:
        logger.error(f"Error descargando PDF XPO: {exc}")
        return None
from src.api_service.erp_service import get_packing_info

from src.adapters.secondary.database.orm import (
    Order, OrderLine, ProductReference, PackingBox, Customer, OrderStatus, OrderLineBoxDistribution, APIStockHistorico, APIMatricula, Almacen,
    PackingPro, PackingProLine, XpoExpedicion
)
from src.api_service.auth import get_customer_almacenes, verify_warehouse_access
from src.api_service.schemas import (
    OrderListItem, OrderLineSimple, OrderLinesResponse, UpdateOrderResponse,
    OrdersListResponse, OrderLineUpdate, BatchUpdateOrderResponse, RegisterStockRequest, RegisterStockResponse,
    RegisterBoxNumberRequest, RegisterBoxNumberResponse,
    PackingProListItem, PackingProListResponse, PackingProLineItem, PackingProLinesResponse
)

# Logger configuration
logger = logging.getLogger(__name__)

# External API configuration
EXTERNAL_API_KEY = os.getenv('EXTERNAL_API_KEY', 'T3sT3')


def get_customer_b2b_orders(
    customer: Customer,
    db: Session,
    skip: int = 0,
    limit: int = 100,
    viewed: Optional[bool] = False
) -> OrdersListResponse:
    """
    Get B2B orders for customer filtered by assigned warehouses.
    Only returns B2B type orders from warehouses customer has access to.
    
    Args:
        customer: Authenticated customer
        db: Database session
        skip: Pagination offset
        limit: Max results to return
        viewed: Optional filter by view status (True=viewed, False=not viewed, None=all)
        
    Returns:
        OrdersListResponse with pagination metadata
    """
    allowed_warehouses = get_customer_almacenes(customer, db)
    
    if not allowed_warehouses:
        return OrdersListResponse(
            total_count=0,
            skip=skip,
            limit=limit,
            orders=[]
        )
    
    # Get PENDING status ID to filter only pending orders
    pending_status = db.query(OrderStatus).filter(OrderStatus.codigo == 'PENDING').first()
    
    # Build base query - only show PENDING orders (not READY)
    base_query = db.query(Order).filter(
        Order.type == 'B2B',
        Order.almacen_id.in_(allowed_warehouses)
    )
    
    # Filter only PENDING orders if status exists
    if pending_status:
        base_query = base_query.filter(Order.status_id == pending_status.id)
    
    # Apply viewed filter if specified
    if viewed is not None:
        if viewed:
            # Only viewed orders (customer_viewed_at IS NOT NULL)
            base_query = base_query.filter(Order.customer_viewed_at.isnot(None))
        else:
            # Only not viewed orders (customer_viewed_at IS NULL)
            base_query = base_query.filter(Order.customer_viewed_at.is_(None))
    
    # Get total count with filters applied
    total_count = base_query.count()
    
    # Get orders with pagination
    orders = base_query.order_by(Order.created_at.desc()).offset(skip).limit(limit).all()
    
    # Update customer_viewed_at timestamp only on first view (if NULL)
    now = datetime.utcnow()
    for order in orders:
        if order.customer_viewed_at is None:
            order.customer_viewed_at = now
    
    db.commit()
    
    # Add total_lines count to each order
    orders_with_lines = []
    for order in orders:
        lines_count = db.query(OrderLine).filter(OrderLine.order_id == order.id).count()
        order_dict = {
            "id": order.id,
            "order_number": order.numero_orden,
            "total_lines": lines_count
        }
        orders_with_lines.append(order_dict)
    
    return OrdersListResponse(
        total_count=total_count,
        skip=skip,
        limit=limit,
        orders=orders_with_lines
    )


def get_customer_b2c_orders(
    customer: Customer,
    db: Session,
    skip: int = 0,
    limit: int = 100,
    viewed: Optional[bool] = False
) -> OrdersListResponse:
    """
    Get B2C orders for customer filtered by assigned warehouses.
    Only returns B2C type orders from warehouses customer has access to.
    
    Args:
        customer: Authenticated customer
        db: Database session
        skip: Pagination offset
        limit: Max results to return
        viewed: Optional filter by view status (True=viewed, False=not viewed, None=all)
        
    Returns:
        OrdersListResponse with pagination metadata
    """
    allowed_warehouses = get_customer_almacenes(customer, db)
    
    if not allowed_warehouses:
        return OrdersListResponse(
            total_count=0,
            skip=skip,
            limit=limit,
            orders=[]
        )
    
    # Get PENDING status ID to filter only pending orders
    pending_status = db.query(OrderStatus).filter(OrderStatus.codigo == 'PENDING').first()
    
    # Build base query for B2C orders - only show PENDING orders (not READY)
    base_query = db.query(Order).filter(
        Order.type == 'B2C',
        Order.almacen_id.in_(allowed_warehouses)
    )
    
    # Filter only PENDING orders if status exists
    if pending_status:
        base_query = base_query.filter(Order.status_id == pending_status.id)
    
    # Apply viewed filter if specified
    if viewed is not None:
        if viewed:
            # Only viewed orders (customer_viewed_at IS NOT NULL)
            base_query = base_query.filter(Order.customer_viewed_at.isnot(None))
        else:
            # Only not viewed orders (customer_viewed_at IS NULL)
            base_query = base_query.filter(Order.customer_viewed_at.is_(None))
    
    # Get total count with filters applied
    total_count = base_query.count()
    
    # Get orders with pagination
    orders = base_query.order_by(Order.created_at.desc()).offset(skip).limit(limit).all()
    
    # Update customer_viewed_at timestamp only on first view (if NULL)
    now = datetime.utcnow()
    for order in orders:
        if order.customer_viewed_at is None:
            order.customer_viewed_at = now
    
    db.commit()
    
    # Add total_lines count to each order
    orders_with_lines = []
    for order in orders:
        lines_count = db.query(OrderLine).filter(OrderLine.order_id == order.id).count()
        order_dict = {
            "id": order.id,
            "order_number": order.numero_orden,
            "total_lines": lines_count
        }
        orders_with_lines.append(order_dict)
    
    return OrdersListResponse(
        total_count=total_count,
        skip=skip,
        limit=limit,
        orders=orders_with_lines
    )


def get_order_lines_for_customer(
    order_id: int,
    customer: Customer,
    db: Session,
    skip: int = 0,
    limit: int = 100,
    viewed: Optional[bool] = False
) -> OrderLinesResponse:
    """
    Get order lines with SKU and quantity for a specific order.
    Validates customer has access to the order's warehouse.
    
    Args:
        order_id: Order ID to retrieve lines for
        customer: Authenticated customer
        db: Database session
        skip: Pagination offset
        limit: Max results to return
        viewed: Optional filter by view status (True=viewed, False=not viewed, None=all)
        
    Returns:
        OrderLinesResponse with order lines
        
    Raises:
        HTTPException: If order not found or access denied
    """
    # Get order
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check if order is READY - don't allow viewing lines of completed orders
    order_status = db.query(OrderStatus).filter(OrderStatus.id == order.status_id).first()
    if order_status and order_status.codigo == 'READY':
        raise HTTPException(
            status_code=403, 
            detail="Order is already completed (READY) and lines are no longer accessible"
        )
    
    # Verify warehouse access
    if order.almacen_id:
        verify_warehouse_access(customer, order.almacen_id, db)
    
    # Build base query for order lines
    base_query = db.query(OrderLine).filter(
        OrderLine.order_id == order_id
    )
    
    # Apply viewed filter if specified
    if viewed is not None:
        if viewed:
            # Only viewed lines (customer_viewed_at IS NOT NULL)
            base_query = base_query.filter(OrderLine.customer_viewed_at.isnot(None))
        else:
            # Only not viewed lines (customer_viewed_at IS NULL)
            base_query = base_query.filter(OrderLine.customer_viewed_at.is_(None))
    
    # Get total count for pagination with filters applied
    total_count = base_query.count()
    
    # Get order lines with pagination
    order_lines = base_query.order_by(OrderLine.id).offset(skip).limit(limit).all()
    
    # Update customer_viewed_at timestamp only on first view (if NULL)
    now = datetime.utcnow()
    
    # Update order timestamp if this is first view
    if order.customer_viewed_at is None:
        order.customer_viewed_at = now
    
    # Update order lines timestamps if this is first view
    for line in order_lines:
        if line.customer_viewed_at is None:
            line.customer_viewed_at = now
    
    db.commit()
    
    # Map to simple schema
    lines_simple = [
        OrderLineSimple(
            sku=line.product_reference.sku if line.product_reference else f"PRODUCT-{line.id}",
            quantity=line.cantidad_solicitada,
            quantity_served=line.cantidad_servida
        )
        for line in order_lines
    ]
    
    return OrderLinesResponse(
        order_id=order.id,
        order_number=order.numero_orden,
        total_count=total_count,
        skip=skip,
        limit=limit,
        lines=lines_simple
    )


def update_order_quantity(
    order_number: str,
    sku: str,
    quantity_served: int,
    box_code: Optional[str],
    customer: Customer,
    db: Session
) -> UpdateOrderResponse:
    """
    Update quantity served for a product in an order.
    Creates product if it doesn't exist.
    Assigns to packing box if box_code provided.
    
    Args:
        order_number: Order number to update
        sku: Product SKU
        quantity_served: Quantity served
        box_code: Optional box tracking code
        customer: Authenticated customer
        db: Database session
        
    Returns:
        UpdateOrderResponse with update details
        
    Raises:
        HTTPException: If order not found or access denied
    """
    # 1. Find order by order_number
    order = db.query(Order).filter(Order.numero_orden == order_number).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_number} not found")
    
    # 2. Verify warehouse access
    if order.almacen_id:
        verify_warehouse_access(customer, order.almacen_id, db)
    
    # 3. Find or create product by SKU
    product = db.query(ProductReference).filter(ProductReference.sku == sku).first()
    if not product:
        # Create product with minimal data
        product = ProductReference(
            sku=sku,
            referencia=f"AUTO-{sku}",
            nombre_producto=f"Auto-created product {sku}",
            color_id="000000",
            talla="UNI",
            activo=True
        )
        db.add(product)
        db.flush()
    
    # 4. Find or create order_line
    order_line = db.query(OrderLine).filter(
        OrderLine.order_id == order.id,
        OrderLine.product_reference_id == product.id
    ).first()
    
    previous_cantidad = 0
    if order_line:
        previous_cantidad = order_line.cantidad_servida
    else:
        # Create new order line
        order_line = OrderLine(
            order_id=order.id,
            product_reference_id=product.id,
            ean=sku,
            cantidad_solicitada=quantity_served,
            cantidad_servida=0,
            estado='PENDING'
        )
        db.add(order_line)
        db.flush()
    
    # 5. Update cantidad_servida
    order_line.cantidad_servida = quantity_served
    
    # Update estado based on quantity
    if quantity_served >= order_line.cantidad_solicitada:
        order_line.estado = 'COMPLETED'
    elif quantity_served > 0:
        order_line.estado = 'PARTIAL'
    else:
        order_line.estado = 'PENDING'
    
    # 6. Handle packing box if box_code provided
    if box_code:
        # Find or create packing box with this box_code
        packing_box = db.query(PackingBox).filter(
            PackingBox.codigo_caja == box_code
        ).first()
        
        if not packing_box:
            # Create new packing box
            # Get next box number for this order
            max_numero = db.query(PackingBox).filter(
                PackingBox.order_id == order.id
            ).count()
            
            packing_box = PackingBox(
                order_id=order.id,
                numero_caja=max_numero + 1,
                codigo_caja=box_code,
                estado='OPEN',
                total_items=0
            )
            db.add(packing_box)
            db.flush()
        
        # Assign order_line to packing_box
        if order_line.packing_box_id != packing_box.id:
            # If was in another box, decrement that box's count
            if order_line.packing_box_id:
                old_box = db.query(PackingBox).filter(
                    PackingBox.id == order_line.packing_box_id
                ).first()
                if old_box:
                    old_box.total_items = max(0, old_box.total_items - 1)
            
            # Assign to new box
            order_line.packing_box_id = packing_box.id
            order_line.fecha_empacado = datetime.utcnow()
            packing_box.total_items += 1
    
    db.commit()
    
    return UpdateOrderResponse(
        status="success",
        message=f"Updated {sku} quantity to {quantity_served}",
        order_number=order.numero_orden,
        sku=sku,
        quantity_served=quantity_served
    )


def batch_update_order(
    order_number: str,
    lines_updates: List[OrderLineUpdate],
    customer: Customer,
    db: Session
) -> BatchUpdateOrderResponse:
    """
    Update all lines of an order at once in a single transaction.
    Changes order status to READY if all lines are completed.
    
    Args:
        order_number: Order number to update
        lines_updates: List of line updates with SKU and quantity
        customer: Authenticated customer
        db: Database session
        
    Returns:
        BatchUpdateOrderResponse with update summary
        
    Raises:
        HTTPException: If order not found, access denied, or order already READY
    """
    # 1. Find order by order_number
    order = db.query(Order).filter(Order.numero_orden == order_number).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_number} not found")
    
    # 2. Check if order is already READY
    order_status = db.query(OrderStatus).filter(OrderStatus.id == order.status_id).first()
    if order_status and order_status.codigo == 'READY':
        raise HTTPException(
            status_code=400, 
            detail=f"Order {order_number} is already READY and cannot be updated"
        )
    
    # 2.1. Check if order has already been updated (fecha_fin_picking set)
    if order.fecha_fin_picking is not None:
        raise HTTPException(
            status_code=403,
            detail=f"Order {order_number} has already been updated on {order.fecha_fin_picking}. No further updates allowed."
        )
    
    # 3. Verify warehouse access
    if order.almacen_id:
        verify_warehouse_access(customer, order.almacen_id, db)
    
    # Counters
    lines_completed = 0
    lines_partial = 0
    lines_pending = 0
    
    # 4. Group by SKU to accumulate total quantities, but keep box distributions separate
    sku_quantities = {}  # {sku: total_quantity}
    sku_box_distributions = {}  # {sku: [{box_code: str, quantity: int}, ...]}
    
    for line_update in lines_updates:
        # Accumulate total quantity per SKU
        if line_update.sku not in sku_quantities:
            sku_quantities[line_update.sku] = 0
            sku_box_distributions[line_update.sku] = []
        
        sku_quantities[line_update.sku] += line_update.quantity_served
        
        # Keep track of each box distribution for this SKU
        if line_update.box_code:
            sku_box_distributions[line_update.sku].append({
                'box_code': line_update.box_code,
                'quantity': line_update.quantity_served
            })
    
    # 5. Process each unique SKU with accumulated quantity
    for sku, accumulated_quantity in sku_quantities.items():
        # Find product by SKU (SKU != EAN)
        product = db.query(ProductReference).filter(ProductReference.sku == sku).first()
        if not product:
            # Create ProductReference AUTO_CREATED if SKU doesn't exist
            product = ProductReference(
                sku=sku,
                referencia=f"AUTO-{sku[:20]}",  # Truncate to avoid overflow
                nombre_producto=f"AUTO CREATED - {sku}",
                color_id="000000",
                nombre_color="",
                talla="U",
                posicion_talla=1,  # Default position for auto-created products
                temporada="0",  # Mark as auto-created for review
                activo=True
            )
            db.add(product)
            db.flush()
        
        # Find existing order_line
        order_line = db.query(OrderLine).filter(
            OrderLine.order_id == order.id,
            OrderLine.product_reference_id == product.id
        ).first()
        
        if not order_line:
            # Create new line with AUTO_CREATED status
            # cantidad_solicitada = quantity_served (first time)
            # This allows the line to be updated multiple times
            
            # Determine estado based on quantity
            if accumulated_quantity > 0:
                new_estado = 'AUTO_CREATED'
                lines_completed += 1
            else:
                new_estado = 'PENDING'
                lines_pending += 1
            
            order_line = OrderLine(
                order_id=order.id,
                product_reference_id=product.id,
                ean=sku,
                cantidad_solicitada=accumulated_quantity if accumulated_quantity > 0 else 1,
                cantidad_servida=accumulated_quantity,
                estado=new_estado
            )
            db.add(order_line)
            db.flush()
        else:
            # Update existing line - ACCUMULATE quantities
            # For AUTO_CREATED lines, allow updating cantidad_solicitada
            if order_line.estado == 'AUTO_CREATED' and accumulated_quantity > order_line.cantidad_solicitada:
                order_line.cantidad_solicitada = accumulated_quantity
            
            # Update cantidad_servida with accumulated quantity
            order_line.cantidad_servida = accumulated_quantity
            
            # Update estado based on quantity compared to cantidad_solicitada
            if accumulated_quantity >= order_line.cantidad_solicitada:
                order_line.estado = 'COMPLETED'
                lines_completed += 1
            elif accumulated_quantity > 0:
                order_line.estado = 'PARTIAL'
                lines_partial += 1
            else:
                order_line.estado = 'PENDING'
                lines_pending += 1
        
        # 6. Handle distribution across multiple boxes
        box_distributions = sku_box_distributions.get(sku, [])
        if box_distributions:
            first_box_id = None
            for dist in box_distributions:
                # Find or create packing box
                packing_box = db.query(PackingBox).filter(
                    PackingBox.codigo_caja == dist['box_code']
                ).first()
                
                if not packing_box:
                    # Create new packing box as CLOSED (products already served)
                    max_numero = db.query(PackingBox).filter(
                        PackingBox.order_id == order.id
                    ).count()
                    
                    packing_box = PackingBox(
                        order_id=order.id,
                        numero_caja=max_numero + 1,
                        codigo_caja=dist['box_code'],
                        estado='CLOSED',
                        total_items=0
                    )
                    db.add(packing_box)
                    db.flush()
                
                # Track first box for legacy compatibility
                if first_box_id is None:
                    first_box_id = packing_box.id
                
                # Create or update distribution record
                existing_dist = db.query(OrderLineBoxDistribution).filter(
                    OrderLineBoxDistribution.order_line_id == order_line.id,
                    OrderLineBoxDistribution.packing_box_id == packing_box.id
                ).first()
                
                if existing_dist:
                    # Update existing distribution
                    old_quantity = existing_dist.quantity_in_box
                    existing_dist.quantity_in_box = dist['quantity']
                    existing_dist.fecha_empacado = datetime.now(timezone.utc)
                    
                    # Adjust box total_items (remove old, add new)
                    packing_box.total_items = packing_box.total_items - old_quantity + dist['quantity']
                else:
                    # Create new distribution record
                    distribution = OrderLineBoxDistribution(
                        order_line_id=order_line.id,
                        packing_box_id=packing_box.id,
                        quantity_in_box=dist['quantity'],
                        fecha_empacado=datetime.now(timezone.utc)
                    )
                    db.add(distribution)
                    
                    # Update box total_items with specific quantity
                    packing_box.total_items += dist['quantity']
            
            # Update legacy fields for backward compatibility
            # If distributed across multiple boxes, assign to first box
            if first_box_id:
                order_line.packing_box_id = first_box_id
                order_line.fecha_empacado = datetime.now(timezone.utc)
    
    # Flush changes to DB before counting
    db.flush()



    # 7. Mark order as updated (first and only time) - blocks further updates
    order.fecha_fin_picking = datetime.now(timezone.utc)
    
    # 8. If order is READY, send to external Packing API
    external_api_response = None

    try:
        # 8.1 Build lines with box distribution - ONLY for items in current request
        external_lines = []
        
        # Iterate only over SKUs that came in the current request
        for sku in sku_quantities.keys():
            # Find the order line for this SKU
            order_line = db.query(OrderLine).join(ProductReference).filter(
                OrderLine.order_id == order.id,
                ProductReference.sku == sku
            ).first()
            
            if not order_line:
                continue
            
            # Check if this SKU has box distributions in the current request
            box_distributions = sku_box_distributions.get(sku, [])
            
            if box_distributions:
                # Add one entry per box distribution from the request
                for dist in box_distributions:
                    external_lines.append({
                        "sku": sku,
                        "matricula": dist['box_code'],
                        "cantidad": dist['quantity']
                    })
            else:
                # No box distribution - add line without matricula using the quantity from request
                quantity = sku_quantities.get(sku, 0)
                if quantity > 0:
                    external_lines.append({
                        "sku": sku,
                        "matricula": "",
                        "cantidad": quantity
                    })
        
        # 8.2 Build external API payload
        external_payload = {
            "empresaId": "0001",
            "almacenId": order.almacen.codigo if order.almacen else "00000001",
            "clienteId": order.cliente,
            "ordenServicioId": order.numero_orden,
            "pedidoId": order.numero_pedido,
            "pedidoEmpresa": "0001",
            "operarioId": "000001",
            "generarTraspaso": True,
            "tipoOperacionStockTraspaso": 5,
            "lineas": external_lines
        }
        
        # 8.3 Log request to external API
        logger.info("Sending packing request to external API")
        logger.info(f"URL: http://localhost:5053/api/Packing")
        logger.info(f"Payload: {json.dumps(external_payload, indent=2, ensure_ascii=False)}")
        
        # 8.4 Send POST to external Packing API
        external_api_url = "http://localhost:5053/api/Packing"
        response = requests.post(
            external_api_url,
            json=external_payload,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": EXTERNAL_API_KEY
            },
            timeout=None
        )
        
        # 8.6 Log response from external API
        logger.info(f"External Packing API response - Status: {response.status_code}")
        logger.info(f"Response Body: {response.text}")
        
        # 8.7 Parse external API response
        try:
            external_api_response = response.json()
        except json.JSONDecodeError:
            external_api_response = {"raw_response": response.text}
        
        # 8.8 Check response status and commit/rollback accordingly
        # Verify both HTTP status code AND success field in response body
        api_success = False
        if response.status_code == 201 and isinstance(external_api_response, dict):
            api_success = external_api_response.get('success', False)
        
        if not api_success:
            db.rollback()
            logger.error(f"External Packing API returned status {response.status_code}, success={external_api_response.get('success', 'N/A') if isinstance(external_api_response, dict) else 'N/A'}")
            
            # Extract error message from external API response
            error_message = "Unknown error from external API"
            if isinstance(external_api_response, dict):
                error_message = external_api_response.get('error', external_api_response.get('message', str(external_api_response)))
            
            logger.info(f"External Packing API error response: {external_api_response}")
            
            # Return properly formatted error response matching BatchUpdateOrderResponse schema
            return BatchUpdateOrderResponse(
                status="error",
                message=f"External API error: {error_message}",
                order_number=order.numero_orden,
                order_status="PENDING",
                lines_updated=len(sku_quantities),
                lines_completed=lines_completed,
                lines_partial=lines_partial,
                lines_pending=lines_pending
            )
        else:
            ready_status = db.query(OrderStatus).filter(OrderStatus.codigo == 'READY').first()
            if ready_status:
                order.status_id = ready_status.id
            logger.info("External Packing API returned 201 with success=true - Success!")
            db.commit()
        
        # Always return external API response
        logger.info(f"External Packing API response: {external_api_response}")
        return external_api_response
        
    except requests.exceptions.RequestException as e:
        db.rollback()
        error_msg = f"Error conectando con API externo de Packing: {str(e)}"
        logger.error(f"Network error: {error_msg}")
        return {"status": False, "error": error_msg}



def batch_update_picked_order(
    order_number: str,
    lines_updates: List[OrderLineUpdate],
    db: Session
) -> BatchUpdateOrderResponse:
    """
    Register a PICKED order against the external Packing API.

    Does NOT modify any order lines. Only:
    1. Validates order is in PICKED status
    2. Sends lines to external Packing API
    3. If external API returns success → marks order as READY + sets fecha_fin_picking
    4. If external API fails → rolls back and returns error (no DB changes)

    Raises:
        HTTPException 404: Order not found
        HTTPException 400: Order is not in PICKED status or already completed
    """
    # 1. Find order
    order = db.query(Order).filter(Order.numero_orden == order_number).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_number} not found")

    # 2. Validate PICKED status
    order_status = db.query(OrderStatus).filter(OrderStatus.id == order.status_id).first()
    current_status = order_status.codigo if order_status else "unknown"

    if current_status != 'PICKED':
        raise HTTPException(
            status_code=400,
            detail=f"Order {order_number} must be in PICKED status. Current status: {current_status}"
        )

    # # 3. Verify warehouse access
    # if order.almacen_id:
    #     verify_warehouse_access(customer, order.almacen_id, db)

    # # 5. Build external API payload from incoming lines
    # external_lines = []
    # for line in lines_updates:
    #     if line.quantity_served > 0:
    #         external_lines.append({
    #             "sku": line.sku,
    #             "matricula": line.box_code or "",
    #             "cantidad": line.quantity_served
    #         })

    # external_payload = {
    #     "empresaId": "0001",
    #     "almacenId": order.almacen.codigo if order.almacen else "00000001",
    #     "clienteId": order.cliente,
    #     "ordenServicioId": order.numero_orden,
    #     "pedidoId": order.numero_pedido,
    #     "pedidoEmpresa": "0001",
    #     "operarioId": "000001",
    #     "generarTraspaso": True,
    #     "tipoOperacionStockTraspaso": 5,
    #     "lineas": external_lines
    # }

    # # 6. Send to external Packing API
    # try:
    #     logger.info(f"Sending PICKED order {order_number} to external Packing API")
    #     logger.info(f"Payload: {json.dumps(external_payload, indent=2, ensure_ascii=False)}")

    #     response = requests.post(
    #         "http://localhost:5053/api/Packing",
    #         json=external_payload,
    #         headers={
    #             "Content-Type": "application/json",
    #             "X-API-Key": EXTERNAL_API_KEY
    #         },
    #         timeout=None
    #     )

    #     logger.info(f"External API response - Status: {response.status_code}, Body: {response.text}")

    #     try:
    #         external_api_response = response.json()
    #     except json.JSONDecodeError:
    #         external_api_response = {"raw_response": response.text}

    #     # 7. Check success
    #     api_success = (
    #         response.status_code == 201
    #         and isinstance(external_api_response, dict)
    #         and external_api_response.get('success', False)
    #     )

    #     if not api_success:
    #         error_message = "Unknown error from external API"
    #         if isinstance(external_api_response, dict):
    #             error_message = external_api_response.get('error', external_api_response.get('message', str(external_api_response)))

    #         logger.error(f"External API failed for order {order_number}: {error_message}")
    #         return BatchUpdateOrderResponse(
    #             status="error",
    #             message=f"External API error: {error_message}",
    #             order_number=order_number,
    #             order_status=current_status,
    #             lines_updated=0,
    #             lines_completed=0,
    #             lines_partial=0,
    #             lines_pending=len(lines_updates),
    #             external_api_data=external_api_response
    #         )

    #     # 8. External API succeeded → update order status only
    #     ready_status = db.query(OrderStatus).filter(OrderStatus.codigo == 'READY').first()
    #     if ready_status:
    #         order.status_id = ready_status.id

    #     db.commit()
    #     logger.info(f"Order {order_number} marked as READY after successful external API response")

    # 9. Send expedition to XPO (DRY RUN: solo construye el XML, sin DB writes ni llamadas externas)
    fecha_now = datetime.now()
    total_cajas    = len({l.box_code for l in lines_updates if l.box_code})
    total_unidades = sum(l.quantity_served for l in lines_updates if l.quantity_served > 0)
    logger.info(f"total_cajas={total_cajas}, total_unidades={total_unidades}")

    erp = get_packing_info(order.numero_orden, num_cajas=total_cajas if total_cajas > 0 else 1)

    xpo_params = XpoExpedicionParams(
        dest_nombre    = (erp.nombre    if erp else None) or order.nombre_cliente or "",
        dest_direccion = (erp.direccion if erp else None) or "",
        dest_cp        = (erp.cp        if erp else None) or "",
        dest_localidad = (erp.poblacion if erp else None) or "",
        dest_provincia = (erp.provincia if erp else None) or "",
        dest_pais      = (erp.pais      if erp else None) or "ES",
        dest_movil     = (erp.telefono  if erp else None) or "",
        dest_email     = (erp.email     if erp else None) or "",
        dest_cod_tienda= (erp.cod_tienda if erp else None) or "",
        obs_linea1        = f"{order.nombre_cliente or ''} / PACKING / {order.numero_orden}",
        #referencia        = f"{order.numero_pedido or ''} - {fecha_now.strftime('%Y%m%d')}",
        referencia        = f"9999900000 - {fecha_now.strftime('%Y%m%d')}",
        fecha_expedicion  = fecha_now,
        total_cajas    = total_cajas if total_cajas > 0 else 1,
        tipo_caja      = "5",
        total_unidades = total_unidades,
        peso_neto      = erp.peso_neto    if erp else 0.0,
        peso_bruto     = erp.peso_bruto   if erp else 0.0,
        volumen_neto   = erp.volumen      if erp else 0.0,
        volumen_bruto  = erp.volumen      if erp else 0.0,
        #nro_pedido_ventas = order.numero_pedido or "",
        nro_pedido_ventas = "9999900000",
        nro_su_pedido     = (erp.ped_cli if erp else None) or "",
    )

    xpo_result = send_xpo_expedicion(xpo_params)

    pdf_path = None
    if xpo_result["success"]:
        consignment_id = xpo_result.get("consignment_id", "")
        pdf_url        = xpo_result.get("pdf_url", "")
        logger.info(f"XPO expedition registered — consignment_id: {consignment_id}")

        pdf_path = _download_xpo_pdf(consignment_id, pdf_url) if pdf_url else None

        db.add(XpoExpedicion(
            order_id         = order.id,
            numero_orden     = order_number,
            consignment_id   = consignment_id,
            referencia       = xpo_params.referencia,
            pdf_url          = pdf_url,
            pdf_path         = pdf_path,
            fecha_expedicion = fecha_now,
        ))
        db.commit()
    else:
        logger.error(f"XPO expedition failed: {xpo_result.get('error')} — raw: {xpo_result.get('raw_response')}")

    return BatchUpdateOrderResponse(
        status="ok" if xpo_result["success"] else "error",
        message=f"Expedición XPO registrada para la orden {order_number}" if xpo_result["success"] else xpo_result.get("error", "XPO error"),
        order_number=order_number,
        order_status=current_status,
        lines_updated=0,
        lines_completed=0,
        lines_partial=0,
        lines_pending=len(lines_updates),
        external_api_data={
            "consignment_id": xpo_result.get("consignment_id"),
            "pdf_url":        xpo_result.get("pdf_url"),
            "pdf_path":       pdf_path,
        }
    )

    # except requests.exceptions.RequestException as e:
    #     error_msg = f"Error connecting to external Packing API: {str(e)}"
    #     logger.error(error_msg)
    #     return BatchUpdateOrderResponse(
    #         status="error",
    #         message=error_msg,
    #         order_number=order_number,
    #         order_status=current_status,
    #         lines_updated=0,
    #         lines_completed=0,
    #         lines_partial=0,
    #         lines_pending=len(lines_updates),
    #         external_api_data=None
    #     )


def register_stock(request: RegisterStockRequest, db: Session) -> RegisterStockResponse:
    """
    Register stock movements between locations.
    
    Process:
    1. Transform request to Spanish format for external API
    2. Send POST to external API (localhost:5053/api/Traspasos/simple)
    3. If external API returns 201:
       - Accumulate quantities for duplicate SKUs
       - Auto-create products if not found
       - Save to local database
    4. If external API returns 400 or error:
       - Rollback and return error 400
    
    Args:
        request: RegisterStockRequest with origin, destinity, and stock_line
        db: Database session
        
    Returns:
        RegisterStockResponse with operation summary
        
    Raises:
        HTTPException 400: If external API fails or validation fails
    """
    try:
        # Step 1: Transform to Spanish format for external API
        lineas_espanol = []
        
        for item in request.stock_line:
            # Buscar producto por SKU para obtener articuloId y colorId
            product = db.query(ProductReference).filter(ProductReference.sku == item.sku).first()
            
            lineas_espanol.append({
                "sku": item.sku,
                "cantidad": item.quantity
            })
        
        external_payload = {
            "empresaId": "0001",  # Hardcoded as requested
            "origen": request.origin,
            "destino": request.destinity,
            "lineas": lineas_espanol
        }
        
        # Step 2: Log request to external API
        logger.info("Sending stock transfer request to external API")
        logger.info(f"URL: http://localhost:5053/api/Traspasos/simple")
        logger.info(f"Payload: {json.dumps(external_payload, indent=2, ensure_ascii=False)}")
        
        # Step 3: Send POST to external API with authentication
        external_api_url = "http://localhost:5053/api/Traspasos/simple"
        response = requests.post(
            external_api_url,
            json=external_payload,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": EXTERNAL_API_KEY
            },
            timeout=None
        )
        
        # Step 4: Log response from external API
        logger.info(f"External API response - Status: {response.status_code}")
        logger.info(f"Response Body: {response.text}")
        
        # Step 5: Check response status
        if response.status_code != 201:
            # External API failed - rollback and return error
            db.rollback()
            error_detail = f"External API returned {response.status_code}: {response.text}"
            logger.error(f"External API error: {error_detail}")
            raise HTTPException(
                status_code=400,
                detail=f"Error al registrar en sistema externo: {error_detail}"
            )
        
        # Step 6: External API returned 201 - proceed with local DB storage
        logger.info("External API returned 201 - Proceeding with local DB storage")
        
        # Step 7: Accumulate quantities by SKU (handle duplicates)
        sku_quantities = {}
        total_lines_received = len(request.stock_line)
        
        for item in request.stock_line:
            if item.sku not in sku_quantities:
                sku_quantities[item.sku] = 0
            sku_quantities[item.sku] += item.quantity
        
        # Step 8: Process each unique SKU
        products_auto_created = 0
        records_created = 0
        
        for sku, accumulated_quantity in sku_quantities.items():
            # 8.1 Search for product by SKU
            product = db.query(ProductReference).filter(ProductReference.sku == sku).first()
            
            # 8.2 Auto-create product if it doesn't exist
            if not product:
                product = ProductReference(
                    sku=sku,
                    referencia=f"AUTO-{sku[:20]}",  # Truncate to avoid overflow
                    nombre_producto=f"AUTO-{sku}",
                    color_id="AUTO",
                    nombre_color="Auto Created",
                    talla="N/A",
                    posicion_talla=0,  # NOT NULL constraint
                    temporada="AUTO_CREATED",
                    activo=True
                )
                db.add(product)
                db.flush()  # Get product.id for FK
                products_auto_created += 1
            
            # 8.3 Create stock movement record with FK to product
            stock_record = APIStockHistorico(
                product_reference_id=product.id,  # FK NOT NULL
                quantity=accumulated_quantity,
                origin=request.origin,
                destinity=request.destinity,
                status='PENDING'  # Default status
            )
            db.add(stock_record)
            records_created += 1
        
        # Step 9: Commit all changes to local DB
        db.commit()
        logger.info(f"Successfully saved {records_created} records to local DB")
        
        # Step 10: Return summary
        return RegisterStockResponse(
            status="success",
            message=f"Successfully registered {records_created} stock movements from {request.origin} to {request.destinity}",
            total_lines_received=total_lines_received,
            unique_skus_processed=len(sku_quantities),
            products_auto_created=products_auto_created,
            records_created=records_created
        )
        
    except requests.exceptions.RequestException as e:
        # Network error or timeout
        db.rollback()
        error_msg = f"Error conectando con API externo: {str(e)}"
        logger.error(f"Network error: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    except HTTPException:
        # Re-raise HTTPException without modification
        raise
    except Exception as e:
        # Any other error
        db.rollback()
        error_msg = f"Error al registrar stock: {str(e)}"
        logger.error(f"Error: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)


def register_box_number(request: RegisterBoxNumberRequest, db: Session) -> RegisterBoxNumberResponse:
    """
    Register a box number for external validation.
    
    Box numbers must be unique. If the box_number already exists, 
    an HTTP 409 Conflict error is raised.
    
    Process:
    1. Check if box_number already exists
    2. If exists: raise HTTPException 409 Conflict
    3. If new: create record with status PENDING
    
    Args:
        request: RegisterBoxNumberRequest with box_number
        db: Database session
        
    Returns:
        RegisterBoxNumberResponse with operation result
        
    Raises:
        HTTPException 409: If box_number already exists (duplicate)
    """
    # Step 1: Check if box_number already exists
    existing_record = db.query(APIMatricula).filter(
        APIMatricula.box_number == request.box_number
    ).first()
    
    # Step 2: If exists, raise conflict error
    if existing_record:
        raise HTTPException(
            status_code=409,
            detail=f"Box number '{request.box_number}' has already been verified and registered"
        )
    
    # Step 3: Create new record with status PENDING
    new_record = APIMatricula(
        box_number=request.box_number,
        status='PENDING'
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    
    # Step 4: Return success response
    return RegisterBoxNumberResponse(
        status="success",
        message=f"Box number '{request.box_number}' registered successfully",
        box_number=new_record.box_number
    )


# ============================================================================
# PACKING PRO
# ============================================================================

def get_packing_pro_list(
    customer: Customer,
    db: Session,
    skip: int = 0,
    limit: int = 100,
    viewed: Optional[bool] = None
) -> PackingProListResponse:
    """
    Get paginated list of packing_pro headers.
    Updates customer_viewed_at on first view.

    Args:
        customer: Authenticated customer
        db: Database session
        skip: Pagination offset
        limit: Max results to return
        viewed: Filter by view status (True=viewed, False=not viewed, None=all)

    Returns:
        PackingProListResponse with pagination metadata
    """
    base_query = db.query(PackingPro)

    if viewed is not None:
        if viewed:
            base_query = base_query.filter(PackingPro.customer_viewed_at.isnot(None))
        else:
            base_query = base_query.filter(PackingPro.customer_viewed_at.is_(None))

    total_count = base_query.count()
    packings = base_query.order_by(PackingPro.created_at.desc()).offset(skip).limit(limit).all()

    # Mark as viewed on first access
    now = datetime.now(timezone.utc)
    for packing in packings:
        if packing.customer_viewed_at is None:
            packing.customer_viewed_at = now
    db.commit()

    return PackingProListResponse(
        total_count=total_count,
        skip=skip,
        limit=limit,
        packings=packings
    )


def get_packing_pro_lines(
    company: str,
    packing_id: str,
    db: Session,
    skip: int = 0,
    limit: int = 100
) -> PackingProLinesResponse:
    """
    Get lines for a specific packing_pro identified by (company, packing_id).

    Args:
        company: Company code
        packing_id: Packing identifier
        db: Database session
        skip: Pagination offset
        limit: Max results to return

    Returns:
        PackingProLinesResponse with lines detail

    Raises:
        HTTPException 404: If packing not found
    """
    packing = db.query(PackingPro).filter(
        PackingPro.company == company,
        PackingPro.packing_id == packing_id
    ).first()

    if not packing:
        raise HTTPException(
            status_code=404,
            detail=f"Packing '{packing_id}' not found for company '{company}'"
        )

    base_query = db.query(PackingProLine).filter(
        PackingProLine.company == company,
        PackingProLine.packing_id == packing_id
    )

    total_count = base_query.count()
    lines = base_query.order_by(PackingProLine.line_id).offset(skip).limit(limit).all()

    lines_out = [
        PackingProLineItem(
            id=line.id,
            line_id=line.line_id,
            box_no=line.box_no,
            sku=line.product.sku if line.product else None,
            quantity=line.quantity,
            po_company=line.po_company,
            po_id=line.po_id,
            po_order_id=line.po_order_id,
            po_line_id=line.po_line_id,
            pack_id=line.pack_id
        )
        for line in lines
    ]

    return PackingProLinesResponse(
        company=company,
        packing_id=packing_id,
        total_count=total_count,
        skip=skip,
        limit=limit,
        lines=lines_out
    )
