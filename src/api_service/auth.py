"""
Authentication and authorization for B2B API Service.
"""
from fastapi import Header, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List

from src.adapters.secondary.database.orm import Customer, CustomerAlmacen
from src.adapters.secondary.database.config import get_db


async def verify_customer_api_key(
    x_api_key: str = Header(..., description="Customer API Key"),
    request: Request = None,
    db: Session = Depends(get_db)
) -> Customer:
    """
    Verify customer API key and return authenticated customer.
    
    Args:
        x_api_key: API key from request header
        request: FastAPI request object for IP tracking
        db: Database session
        
    Returns:
        Customer object if authentication successful
        
    Raises:
        HTTPException: If API key is invalid or customer is inactive
    """
    # Query customer by API key
    customer = db.query(Customer).filter(
        Customer.api_key == x_api_key,
        Customer.activo == True
    ).first()
    
    if not customer:
        raise HTTPException(
            status_code=401,
            detail="Invalid or inactive API key"
        )
    
    # Check API key expiration
    if customer.api_key_expires_at:
        if datetime.utcnow() > customer.api_key_expires_at:
            raise HTTPException(
                status_code=401,
                detail="API key has expired"
            )
    
    # Update last access tracking
    customer.ultimo_acceso = datetime.utcnow()
    if request:
        customer.ultima_ip = request.client.host if request.client else None
    
    db.commit()
    
    return customer


def get_customer_almacenes(customer: Customer, db: Session) -> List[int]:
    """
    Get list of warehouse IDs that customer has access to.
    
    Args:
        customer: Authenticated customer
        db: Database session
        
    Returns:
        List of almacen_id integers
    """
    almacen_ids = db.query(CustomerAlmacen.almacen_id).filter(
        CustomerAlmacen.customer_id == customer.id
    ).all()
    
    return [almacen_id[0] for almacen_id in almacen_ids]


def verify_warehouse_access(customer: Customer, almacen_id: int, db: Session):
    """
    Verify customer has access to specific warehouse.
    
    Args:
        customer: Authenticated customer
        almacen_id: Warehouse ID to check
        db: Database session
        
    Raises:
        HTTPException: If customer doesn't have access to warehouse
    """
    allowed_warehouses = get_customer_almacenes(customer, db)
    
    if almacen_id not in allowed_warehouses:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied to warehouse {almacen_id}"
        )
