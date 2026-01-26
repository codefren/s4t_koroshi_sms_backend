"""
Business logic for B2B API Service operations.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from typing import List, Optional
from datetime import datetime, timezone

from src.adapters.secondary.database.orm import (
    Order, OrderLine, ProductReference, PackingBox, Customer, OrderStatus
)
from src.api_service.auth import get_customer_almacenes, verify_warehouse_access
from src.api_service.schemas import (
    OrderListItem, OrderLineSimple, OrderLinesResponse, UpdateOrderResponse,
    OrdersListResponse, OrderLineUpdate, BatchUpdateOrderResponse
)


def get_customer_b2b_orders(
    customer: Customer,
    db: Session,
    skip: int = 0,
    limit: int = 100,
    viewed: Optional[bool] = None
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
    
    return OrdersListResponse(
        total_count=total_count,
        skip=skip,
        limit=limit,
        orders=orders
    )


def get_customer_b2c_orders(
    customer: Customer,
    db: Session,
    skip: int = 0,
    limit: int = 100,
    viewed: Optional[bool] = None
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
    
    return OrdersListResponse(
        total_count=total_count,
        skip=skip,
        limit=limit,
        orders=orders
    )


def get_order_lines_for_customer(
    order_id: int,
    customer: Customer,
    db: Session,
    skip: int = 0,
    limit: int = 100,
    viewed: Optional[bool] = None
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
    
    # 4. Process each line update
    for line_update in lines_updates:
        # Find product by SKU (SKU != EAN)
        product = db.query(ProductReference).filter(ProductReference.sku == line_update.sku).first()
        if not product:
            # Create ProductReference AUTO_CREATED if SKU doesn't exist
            product = ProductReference(
                sku=line_update.sku,
                referencia=f"AUTO-{line_update.sku[:20]}",  # Truncate to avoid overflow
                nombre_producto=f"AUTO CREATED - {line_update.sku}",
                color_id="AUTO",
                nombre_color="Auto Created",
                talla="N/A",
                temporada="AUTO_CREATED",  # Mark as auto-created for review
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
            if line_update.quantity_served > 0:
                new_estado = 'AUTO_CREATED'
                lines_completed += 1
            else:
                new_estado = 'PENDING'
                lines_pending += 1
            
            order_line = OrderLine(
                order_id=order.id,
                product_reference_id=product.id,
                ean=line_update.sku,
                cantidad_solicitada=line_update.quantity_served if line_update.quantity_served > 0 else 1,
                cantidad_servida=line_update.quantity_served,
                estado=new_estado
            )
            db.add(order_line)
            db.flush()
        else:
            # Update existing line
            # For AUTO_CREATED lines, allow updating cantidad_solicitada
            if order_line.estado == 'AUTO_CREATED' and line_update.quantity_served > order_line.cantidad_solicitada:
                order_line.cantidad_solicitada = line_update.quantity_served
            
            # Update cantidad_servida
            order_line.cantidad_servida = line_update.quantity_served
            
            # Update estado based on quantity compared to cantidad_solicitada
            if line_update.quantity_served >= order_line.cantidad_solicitada:
                order_line.estado = 'COMPLETED'
                lines_completed += 1
            elif line_update.quantity_served > 0:
                order_line.estado = 'PARTIAL'
                lines_partial += 1
            else:
                order_line.estado = 'PENDING'
                lines_pending += 1
        
        # Handle packing box if box_code provided
        if line_update.box_code:
            # Find or create packing box
            packing_box = db.query(PackingBox).filter(
                PackingBox.codigo_caja == line_update.box_code
            ).first()
            
            if not packing_box:
                # Create new packing box as CLOSED (products already served)
                max_numero = db.query(PackingBox).filter(
                    PackingBox.order_id == order.id
                ).count()
                
                packing_box = PackingBox(
                    order_id=order.id,
                    numero_caja=max_numero + 1,
                    codigo_caja=line_update.box_code,
                    estado='CLOSED',
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
                order_line.fecha_empacado = datetime.now(timezone.utc)
                packing_box.total_items += 1
    
    # Flush changes to DB before counting
    db.flush()
    
    # 5. Check if ALL lines are completed
    total_lines = db.query(OrderLine).filter(OrderLine.order_id == order.id).count()
    completed_lines = db.query(OrderLine).filter(
        OrderLine.order_id == order.id,
        OrderLine.estado == 'COMPLETED'
    ).count()
    
    # 6. Update order status to READY if all lines completed
    if completed_lines == total_lines and total_lines > 0:
        ready_status = db.query(OrderStatus).filter(OrderStatus.codigo == 'READY').first()
        if ready_status:
            order.status_id = ready_status.id
            order_status_code = 'READY'
        else:
            order_status_code = 'PENDING'
    else:
        pending_status = db.query(OrderStatus).filter(OrderStatus.codigo == 'PENDING').first()
        if pending_status:
            order.status_id = pending_status.id
        order_status_code = 'PENDING'
    
    # 7. Mark order as updated (first and only time) - blocks further updates
    order.fecha_fin_picking = datetime.now(timezone.utc)
    
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
