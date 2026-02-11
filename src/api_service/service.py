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

from src.adapters.secondary.database.orm import (
    Order, OrderLine, ProductReference, PackingBox, Customer, OrderStatus, OrderLineBoxDistribution, APIStockHistorico, APIMatricula, Almacen
)
from src.api_service.auth import get_customer_almacenes, verify_warehouse_access
from src.api_service.schemas import (
    OrderListItem, OrderLineSimple, OrderLinesResponse, UpdateOrderResponse,
    OrdersListResponse, OrderLineUpdate, BatchUpdateOrderResponse, RegisterStockRequest, RegisterStockResponse,
    RegisterBoxNumberRequest, RegisterBoxNumberResponse
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

    ready_status = db.query(OrderStatus).filter(OrderStatus.codigo == 'READY').first()
    if ready_status:
        order.status_id = ready_status.id
        order_status_code = 'READY'

    # 7. Mark order as updated (first and only time) - blocks further updates
    order.fecha_fin_picking = datetime.now(timezone.utc)
    
    # 8. If order is READY, send to external Packing API
    if order_status_code == 'READY':
        try:
            # 8.1 Build lines with box distribution
            external_lines = []
            
            # Get all order lines with their box distributions
            for order_line in db.query(OrderLine).filter(OrderLine.order_id == order.id).all():
                # Get box distributions for this line
                distributions = db.query(OrderLineBoxDistribution).filter(
                    OrderLineBoxDistribution.order_line_id == order_line.id
                ).all()
                
                if distributions:
                    # Add one entry per box distribution
                    for dist in distributions:
                        packing_box = db.query(PackingBox).filter(
                            PackingBox.id == dist.packing_box_id
                        ).first()
                        
                        if packing_box and dist.quantity_in_box > 0:
                            external_lines.append({
                                "sku": order_line.product_reference.sku,
                                "matricula": packing_box.codigo_caja,
                                "cantidad": dist.quantity_in_box
                            })
            
            # 8.2 Build external API payload
            external_payload = {
                "empresaId": "0001",
                "almacenId": order.almacen.codigo if order.almacen else "00000001",
                "clienteId": order.cliente,
                "ordenServicioId": order.numero_orden,
                "operarioId": "000001",
                "generarTraspaso": True,
                "tipoOperacionStockTraspaso": "SOLO_ENTRADAS",
                "lineas": external_lines
            }
            
            # 8.3 Log request to external API
            logger.info("Sending packing request to external API")
            logger.info(f"URL: http://localhost:5053/api/Packing")
            logger.debug(f"Payload: {json.dumps(external_payload, indent=2, ensure_ascii=False)}")
            
            # 8.4 Send POST to external Packing API
            external_api_url = "http://localhost:5053/api/Packing"
            response = requests.post(
                external_api_url,
                json=external_payload,
                headers={
                    "Content-Type": "application/json",
                    "X-API-Key": EXTERNAL_API_KEY
                },
                timeout=10
            )
            
            # 8.6 Log response from external API
            logger.info(f"External Packing API response - Status: {response.status_code}")
            logger.debug(f"Response Body: {response.text}")
            
            # 8.7 Check response status
            if response.status_code != 201:
                db.rollback()
                error_detail = f"External Packing API returned {response.status_code}: {response.text}"
                logger.error(f"External Packing API error: {error_detail}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Error al registrar packing en sistema externo: {error_detail}"
                )
            
            logger.info("External Packing API returned 201 - Success!")
            
        except requests.exceptions.RequestException as e:
            db.rollback()
            error_msg = f"Error conectando con API externo de Packing: {str(e)}"
            logger.error(f"Network error: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
        except HTTPException:
            raise
    
    db.commit()
    
    return BatchUpdateOrderResponse(
        status="success",
        message=f"Updated {len(lines_updates)} lines for order {order_number}",
        order_number=order_number,
        order_status=order_status_code,
        lines_updated=len(lines_updates),
        lines_completed=lines_completed,
        lines_partial=lines_partial,
        lines_pending=lines_pending
    )


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
                "articuloId": str(product.id) if product else "",
                "colorId": product.color_id if product else "",
                "cantidades": {
                    "additionalProp1": 0,
                    "additionalProp2": 0,
                    "additionalProp3": 0
                },
                "ean": "",
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
        logger.debug(f"Payload: {json.dumps(external_payload, indent=2, ensure_ascii=False)}")
        
        # Step 3: Send POST to external API with authentication
        external_api_url = "http://localhost:5053/api/Traspasos/simple"
        response = requests.post(
            external_api_url,
            json=external_payload,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": EXTERNAL_API_KEY
            },
            timeout=10
        )
        
        # Step 4: Log response from external API
        logger.info(f"External API response - Status: {response.status_code}")
        logger.debug(f"Response Body: {response.text}")
        
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
