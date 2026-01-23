"""
Business logic for B2B API Service operations.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from typing import List, Optional
from datetime import datetime

from src.adapters.secondary.database.orm import (
    Order, OrderLine, ProductReference, PackingBox, Customer
)
from src.api_service.auth import get_customer_almacenes, verify_warehouse_access
from src.api_service.schemas import (
    OrderListItem, OrderLineSimple, OrderLinesResponse, UpdateOrderResponse,
    OrdersListResponse
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
    
    # Build base query
    base_query = db.query(Order).filter(
        Order.type == 'B2B',
        Order.almacen_id.in_(allowed_warehouses)
    )
    
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
    
    # Build base query for B2C orders
    base_query = db.query(Order).filter(
        Order.type == 'B2C',
        Order.almacen_id.in_(allowed_warehouses)
    )
    
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
