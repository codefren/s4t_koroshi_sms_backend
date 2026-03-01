"""
REST API router for replenishment requests management.

Endpoints for operators to view, manage and execute stock replenishment
between picking and replenishment zones.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload, aliased
from datetime import datetime, timedelta
from typing import Optional
import math

from src.adapters.secondary.database.config import SessionLocal
from src.adapters.secondary.database.orm import (
    ReplenishmentRequest, ProductLocation, ProductReference, Operator
)
from sqlalchemy import func as sa_func
from src.core.domain.replenishment_models import (
    ReplenishmentRequestListItem,
    ReplenishmentRequestListResponse,
    StatusCounts,
    PriorityCounts,
    StartExecutionRequest,
    RejectRequest
)


router = APIRouter(prefix="/replenishment", tags=["replenishment"])


def get_db():
    """Dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def calculate_time_waiting(requested_at: datetime) -> str:
    """Calculate time waiting in human-readable format."""
    delta = datetime.utcnow() - requested_at
    
    if delta < timedelta(minutes=1):
        return "menos de 1 min"
    elif delta < timedelta(hours=1):
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes} min"
    elif delta < timedelta(days=1):
        hours = int(delta.total_seconds() / 3600)
        return f"{hours} hora{'s' if hours > 1 else ''}"
    else:
        days = delta.days
        return f"{days} día{'s' if days > 1 else ''}"


@router.get("/requests", response_model=ReplenishmentRequestListResponse)
def list_replenishment_requests(
    status: Optional[str] = Query(None, description="Filter by status: WAITING_STOCK, READY, IN_PROGRESS, COMPLETED, REJECTED"),
    priority: Optional[str] = Query(None, description="Filter by priority: URGENT, HIGH, NORMAL"),
    solo_prioritarias: bool = Query(False, description="Solo URGENT y HIGH (para PDA). Ignora el filtro priority si está activo."),
    almacen_id: Optional[int] = Query(None, description="Filter by warehouse"),
    product_id: Optional[int] = Query(None, description="Filter by product"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """
    List replenishment requests with filters and pagination.
    
    **Filters:**
    - `status`: Filter by request status
    - `priority`: Filter by priority level
    - `solo_prioritarias`: Solo URGENT y HIGH (para PDA)
    - `almacen_id`: Filter by warehouse
    - `product_id`: Filter by product
    
    **Response:**
    - Paginated list of replenishment requests
    - Includes product, location, operator information
    - Time waiting calculated automatically
    """
    # Base query with joins
    query = db.query(ReplenishmentRequest).options(
        joinedload(ReplenishmentRequest.product),
        joinedload(ReplenishmentRequest.location_origin),
        joinedload(ReplenishmentRequest.location_destination),
        joinedload(ReplenishmentRequest.requester),
        joinedload(ReplenishmentRequest.executor)
    )
    
    # Apply filters
    if status:
        query = query.filter(ReplenishmentRequest.status == status)
    
    if solo_prioritarias:
        query = query.filter(ReplenishmentRequest.priority.in_(["URGENT", "HIGH"]))
        # PDA: solo reposiciones de almacén 1 (reposición) → almacén 2 (picking)
        origin_loc = aliased(ProductLocation)
        dest_loc = aliased(ProductLocation)
        query = query.join(
            origin_loc,
            ReplenishmentRequest.location_origen_id == origin_loc.id
        ).join(
            dest_loc,
            ReplenishmentRequest.location_destino_id == dest_loc.id
        ).filter(
            origin_loc.almacen_id == 1,
            dest_loc.almacen_id == 2
        )
    elif priority:
        query = query.filter(ReplenishmentRequest.priority == priority)
    
    if almacen_id and not solo_prioritarias:
        query = query.join(
            ProductLocation,
            ReplenishmentRequest.location_destino_id == ProductLocation.id
        ).filter(ProductLocation.almacen_id == almacen_id)
    
    if product_id:
        query = query.filter(ReplenishmentRequest.product_id == product_id)
    
    # Count total
    total = query.count()
    
    # Order by priority and date
    query = query.order_by(
        ReplenishmentRequest.priority.desc(),
        ReplenishmentRequest.requested_at.asc()
    )
    
    # Paginate
    offset = (page - 1) * per_page
    requests = query.offset(offset).limit(per_page).all()
    
    # Build response
    items = []
    for req in requests:
        items.append(ReplenishmentRequestListItem(
            id=req.id,
            status=req.status,
            priority=req.priority,
            requested_quantity=req.requested_quantity,
            product_name=req.product.nombre_producto if req.product else "Unknown",
            product_sku=req.product.sku if req.product else None,
            origin_code=req.location_origin.codigo_ubicacion if req.location_origin else None,
            origin_stock=req.location_origin.stock_actual if req.location_origin else None,
            destination_code=req.location_destination.codigo_ubicacion if req.location_destination else "Unknown",
            destination_stock=req.location_destination.stock_actual if req.location_destination else 0,
            requester_name=req.requester.nombre if req.requester else "Unknown",
            executor_name=req.executor.nombre if req.executor else None,
            requested_at=req.requested_at,
            time_waiting=calculate_time_waiting(req.requested_at)
        ))
    
    total_pages = math.ceil(total / per_page) if total > 0 else 0
    
    # Count by status (global, ignoring filters)
    counts_rows = db.query(
        ReplenishmentRequest.status,
        sa_func.count(ReplenishmentRequest.id)
    ).group_by(ReplenishmentRequest.status).all()
    
    counts_dict = {row[0]: row[1] for row in counts_rows}
    
    status_counts = StatusCounts(
        WAITING_STOCK=counts_dict.get("WAITING_STOCK", 0),
        READY=counts_dict.get("READY", 0),
        IN_PROGRESS=counts_dict.get("IN_PROGRESS", 0),
        COMPLETED=counts_dict.get("COMPLETED", 0),
        REJECTED=counts_dict.get("REJECTED", 0),
    )
    
    # Count by priority (global, ignoring filters)
    priority_rows = db.query(
        ReplenishmentRequest.priority,
        sa_func.count(ReplenishmentRequest.id)
    ).group_by(ReplenishmentRequest.priority).all()
    
    priority_dict = {row[0]: row[1] for row in priority_rows}
    priority_counts = PriorityCounts(
        URGENT=priority_dict.get("URGENT", 0),
        HIGH=priority_dict.get("HIGH", 0),
        NORMAL=priority_dict.get("NORMAL", 0),
    )
    
    return ReplenishmentRequestListResponse(
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        status_counts=status_counts,
        priority_counts=priority_counts,
        requests=items
    )


@router.post("/requests/{request_id}/start")
def start_replenishment_execution(
    request_id: int,
    data: StartExecutionRequest,
    db: Session = Depends(get_db)
):
    """
    Start execution of a replenishment request.
    
    Changes status from READY to IN_PROGRESS and assigns executor operator.
    
    **Validations:**
    - Request must exist
    - Status must be READY
    - Origin location must have sufficient stock
    - Executor operator must exist and be active
    """
    # Get request
    request = db.query(ReplenishmentRequest).filter_by(id=request_id).first()
    
    if not request:
        raise HTTPException(status_code=404, detail="Replenishment request not found")
    
    # Validate status
    if request.status != "READY":
        raise HTTPException(
            status_code=400,
            detail=f"Request status is {request.status}. Must be READY to start execution"
        )
    
    # Validate origin location exists and has stock
    if not request.location_origen_id:
        raise HTTPException(
            status_code=400,
            detail="No origin location assigned. Cannot execute request"
        )
    
    origin_location = db.query(ProductLocation).filter_by(id=request.location_origen_id).first()
    if not origin_location or origin_location.stock_actual < request.requested_quantity:
        raise HTTPException(
            status_code=400,
            detail="Insufficient stock in origin location"
        )
    
    # Validate executor operator
    executor = db.query(Operator).filter_by(id=data.executor_id).first()
    if not executor:
        raise HTTPException(status_code=404, detail="Executor operator not found")
    
    if not executor.activo:
        raise HTTPException(status_code=400, detail="Executor operator is inactive")
    
    # Update request
    request.status = "IN_PROGRESS"
    request.executor_id = data.executor_id
    request.started_at = datetime.utcnow()
    request.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(request)
    
    return {
        "success": True,
        "message": "Replenishment execution started",
        "request_id": request.id,
        "status": request.status,
        "executor": executor.nombre,
        "started_at": request.started_at.isoformat()
    }


@router.post("/requests/{request_id}/complete")
def complete_replenishment(
    request_id: int,
    db: Session = Depends(get_db)
):
    """
    Complete a replenishment request.
    
    **Actions:**
    1. Validates request is IN_PROGRESS
    2. Updates stock in origin location (subtract)
    3. Updates stock in destination location (add)
    4. Marks request as COMPLETED
    5. Records completion timestamp
    
    **Stock update is atomic** - either both locations update or none.
    """
    # Get request with locations
    request = db.query(ReplenishmentRequest).options(
        joinedload(ReplenishmentRequest.location_origin),
        joinedload(ReplenishmentRequest.location_destination)
    ).filter_by(id=request_id).first()
    
    if not request:
        raise HTTPException(status_code=404, detail="Replenishment request not found")
    
    # Validate status
    if request.status != "IN_PROGRESS":
        raise HTTPException(
            status_code=400,
            detail=f"Request status is {request.status}. Must be IN_PROGRESS to complete"
        )
    
    # Validate locations exist
    if not request.location_origin or not request.location_destination:
        raise HTTPException(status_code=400, detail="Origin or destination location not found")
    
    # Validate origin has sufficient stock
    if request.location_origin.stock_actual < request.requested_quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient stock in origin. Available: {request.location_origin.stock_actual}, Required: {request.requested_quantity}"
        )
    
    # Update stock atomically
    origin_stock_before = request.location_origin.stock_actual
    dest_stock_before = request.location_destination.stock_actual
    
    request.location_origin.stock_actual -= request.requested_quantity
    request.location_destination.stock_actual += request.requested_quantity
    
    # Update last stock update timestamp
    request.location_origin.ultima_actualizacion_stock = datetime.utcnow()
    request.location_destination.ultima_actualizacion_stock = datetime.utcnow()
    
    # Mark request as completed
    request.status = "COMPLETED"
    request.completed_at = datetime.utcnow()
    request.updated_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "success": True,
        "message": "Replenishment completed successfully",
        "request_id": request.id,
        "quantity_moved": request.requested_quantity,
        "origin_location": {
            "code": request.location_origin.codigo_ubicacion,
            "stock_before": origin_stock_before,
            "stock_after": request.location_origin.stock_actual
        },
        "destination_location": {
            "code": request.location_destination.codigo_ubicacion,
            "stock_before": dest_stock_before,
            "stock_after": request.location_destination.stock_actual
        },
        "completed_at": request.completed_at.isoformat()
    }


@router.post("/requests/{request_id}/reject")
def reject_replenishment(
    request_id: int,
    data: RejectRequest,
    db: Session = Depends(get_db)
):
    """
    Reject a replenishment request.
    
    Can reject requests in WAITING_STOCK or READY status.
    Includes rejection reason in notes.
    """
    request = db.query(ReplenishmentRequest).filter_by(id=request_id).first()
    
    if not request:
        raise HTTPException(status_code=404, detail="Replenishment request not found")
    
    # Can only reject pending requests
    if request.status not in ["WAITING_STOCK", "READY", "IN_PROGRESS"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject request with status {request.status}"
        )
    
    request.status = "REJECTED"
    request.notes = data.notes
    request.updated_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "success": True,
        "message": "Replenishment request rejected",
        "request_id": request.id,
        "reason": data.notes
    }


@router.get("/requests/{request_id}")
def get_replenishment_request(
    request_id: int,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific replenishment request.
    """
    request = db.query(ReplenishmentRequest).options(
        joinedload(ReplenishmentRequest.product),
        joinedload(ReplenishmentRequest.location_origin),
        joinedload(ReplenishmentRequest.location_destination),
        joinedload(ReplenishmentRequest.requester),
        joinedload(ReplenishmentRequest.executor),
        joinedload(ReplenishmentRequest.order)
    ).filter_by(id=request_id).first()
    
    if not request:
        raise HTTPException(status_code=404, detail="Replenishment request not found")
    
    return {
        "id": request.id,
        "status": request.status,
        "priority": request.priority,
        "requested_quantity": request.requested_quantity,
        "product": {
            "id": request.product.id,
            "nombre": request.product.nombre_producto,
            "sku": request.product.sku,
            "ean": request.product.ean
        } if request.product else None,
        "location_origin": {
            "id": request.location_origin.id,
            "code": request.location_origin.codigo_ubicacion,
            "stock_actual": request.location_origin.stock_actual,
            "almacen_id": request.location_origin.almacen_id
        } if request.location_origin else None,
        "location_destination": {
            "id": request.location_destination.id,
            "code": request.location_destination.codigo_ubicacion,
            "stock_actual": request.location_destination.stock_actual,
            "stock_minimo": request.location_destination.stock_minimo,
            "almacen_id": request.location_destination.almacen_id
        } if request.location_destination else None,
        "requester": {
            "id": request.requester.id,
            "nombre": request.requester.nombre,
            "codigo": request.requester.codigo
        } if request.requester else None,
        "executor": {
            "id": request.executor.id,
            "nombre": request.executor.nombre,
            "codigo": request.executor.codigo
        } if request.executor else None,
        "order_id": request.order_id,
        "notes": request.notes,
        "requested_at": request.requested_at.isoformat(),
        "started_at": request.started_at.isoformat() if request.started_at else None,
        "completed_at": request.completed_at.isoformat() if request.completed_at else None,
        "time_waiting": calculate_time_waiting(request.requested_at)
    }


@router.get("/diagnostic")
def replenishment_diagnostic(
    db: Session = Depends(get_db)
):
    """
    Diagnóstico del sistema de reposición automática.
    
    Muestra por qué ciertos productos con stock bajo NO tienen solicitud de reposición.
    """
    from sqlalchemy import func
    
    PICKING_WAREHOUSE_ID = 2
    REPLENISHMENT_WAREHOUSE_ID = 1
    
    # 1. Operador SYSTEM existe?
    system_operator = db.query(Operator).filter(Operator.codigo == "SYSTEM").first()
    
    # 2. Ubicaciones con stock bajo en picking
    low_stock_locations = db.query(ProductLocation).filter(
        ProductLocation.almacen_id == PICKING_WAREHOUSE_ID,
        ProductLocation.activa == True,
        ProductLocation.stock_actual < ProductLocation.stock_minimo,
        ProductLocation.stock_minimo > 0,
    ).all()
    
    # 3. Ubicaciones con stock_minimo = 0 (ignoradas por el cron)
    zero_minimum = db.query(func.count(ProductLocation.id)).filter(
        ProductLocation.almacen_id == PICKING_WAREHOUSE_ID,
        ProductLocation.activa == True,
        ProductLocation.stock_minimo == 0,
    ).scalar()
    
    # 4. Ubicaciones con stock_minimo NULL
    null_minimum = db.query(func.count(ProductLocation.id)).filter(
        ProductLocation.almacen_id == PICKING_WAREHOUSE_ID,
        ProductLocation.activa == True,
        ProductLocation.stock_minimo == None,
    ).scalar()
    
    # 5. Para cada ubicación con stock bajo, verificar si ya tiene solicitud
    details = []
    already_has_request = 0
    no_request = 0
    
    for loc in low_stock_locations:
        existing = db.query(ReplenishmentRequest).filter(
            ReplenishmentRequest.product_id == loc.product_id,
            ReplenishmentRequest.location_destino_id == loc.id,
            ReplenishmentRequest.status.in_(["WAITING_STOCK", "READY", "IN_PROGRESS"]),
        ).first()
        
        # Buscar stock en almacén de reposición
        origin = db.query(ProductLocation).filter(
            ProductLocation.product_id == loc.product_id,
            ProductLocation.almacen_id == REPLENISHMENT_WAREHOUSE_ID,
            ProductLocation.activa == True,
            ProductLocation.stock_actual > 0,
        ).first()
        
        product = db.query(ProductReference).filter_by(id=loc.product_id).first()
        
        if existing:
            already_has_request += 1
            reason = f"Ya tiene solicitud #{existing.id} ({existing.status})"
        else:
            no_request += 1
            reason = "SIN SOLICITUD - debería crearse"
        
        details.append({
            "location_id": loc.id,
            "product_id": loc.product_id,
            "product_name": product.nombre_producto if product else "N/A",
            "sku": product.sku if product else "N/A",
            "location_code": loc.codigo_ubicacion,
            "stock_actual": loc.stock_actual,
            "stock_minimo": loc.stock_minimo,
            "deficit": loc.stock_minimo - loc.stock_actual,
            "has_origin_stock": origin is not None,
            "origin_stock": origin.stock_actual if origin else 0,
            "reason": reason,
        })
    
    # 6. Solicitudes activas
    active_requests = db.query(func.count(ReplenishmentRequest.id)).filter(
        ReplenishmentRequest.status.in_(["WAITING_STOCK", "READY", "IN_PROGRESS"])
    ).scalar()
    
    return {
        "system_operator_exists": system_operator is not None,
        "system_operator_id": system_operator.id if system_operator else None,
        "picking_warehouse_id": PICKING_WAREHOUSE_ID,
        "replenishment_warehouse_id": REPLENISHMENT_WAREHOUSE_ID,
        "total_low_stock_locations": len(low_stock_locations),
        "ignored_zero_minimum": zero_minimum,
        "ignored_null_minimum": null_minimum,
        "already_has_pending_request": already_has_request,
        "missing_request": no_request,
        "active_requests_total": active_requests,
        "details": details[:50],
    }
