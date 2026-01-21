"""
Router de API para productos y ubicaciones.

Endpoints diseñados para cumplir con los requerimientos
del componente Products.jsx del frontend React.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func
from typing import Optional
import math

from src.adapters.secondary.database.config import SessionLocal
from src.adapters.secondary.database.orm import ProductReference, ProductLocation
from src.core.domain.models import ProductLocationCreate, ProductLocationResponse
from src.core.domain.product_api_models import (
    ProductListResponse,
    ProductListItem,
    ProductDetail,
    ProductLocationsResponse,
    ProductLocationDetail,
    LocationItem,
    ProductStatusFilter,
    calculate_product_status,
    format_location_code
)


router = APIRouter(prefix="/products", tags=["products"])


# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

def get_db():
    """Dependency para obtener sesión de base de datos."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# UTILIDADES
# ============================================================================

def _calculate_total_stock(product: ProductReference) -> int:
    """Calcula el stock total de un producto sumando todas sus ubicaciones."""
    return sum(loc.stock_actual for loc in product.locations if loc.activa)


def _format_locations_for_list(
    locations: list[ProductLocation], 
    max_display: int = 2
) -> list[LocationItem]:
    """
    Formatea ubicaciones para el listado (muestra solo las primeras N + indicador).
    
    Args:
        locations: Lista de ubicaciones del producto
        max_display: Número máximo de ubicaciones a mostrar antes del "+X más"
        
    Returns:
        Lista de LocationItem formateados
    """
    # Filtrar solo ubicaciones activas y ordenar por prioridad
    active_locs = [loc for loc in locations if loc.activa]
    active_locs.sort(key=lambda x: (x.prioridad, -x.stock_actual))
    
    result = []
    
    # Agregar las primeras N ubicaciones
    for loc in active_locs[:max_display]:
        result.append(LocationItem(
            code=format_location_code(loc.pasillo, loc.lado, loc.ubicacion, loc.altura),
            is_more=False,
            stock=loc.stock_actual
        ))
    
    # Si hay más ubicaciones, agregar indicador
    remaining = len(active_locs) - max_display
    if remaining > 0:
        result.append(LocationItem(
            code=f"+{remaining} más",
            is_more=True
        ))
    
    return result


def _apply_status_filter(query, status_filter: ProductStatusFilter):
    """
    Aplica filtro de estado a la query.
    
    Nota: Este filtro es aproximado porque el estado se calcula en base al stock.
    Para mayor precisión, se puede agregar una columna 'status' calculada en la BD.
    """
    if status_filter == ProductStatusFilter.ALL:
        return query
    
    # Subconsulta para calcular stock total por producto
    stock_subquery = (
        Session.query(
            ProductLocation.product_id,
            func.sum(ProductLocation.stock_actual).label('total_stock')
        )
        .filter(ProductLocation.activa == True)
        .group_by(ProductLocation.product_id)
        .subquery()
    )
    
    # Aplicar filtros según estado
    if status_filter == ProductStatusFilter.OUT:
        # Sin stock (stock_actual = 0 en todas las ubicaciones o sin ubicaciones)
        query = query.outerjoin(
            stock_subquery, ProductReference.id == stock_subquery.c.product_id
        ).filter(
            or_(
                stock_subquery.c.total_stock == 0,
                stock_subquery.c.total_stock == None
            )
        )
    elif status_filter == ProductStatusFilter.LOW:
        # Stock bajo (1-49)
        query = query.join(
            stock_subquery, ProductReference.id == stock_subquery.c.product_id
        ).filter(
            stock_subquery.c.total_stock > 0,
            stock_subquery.c.total_stock < 50
        )
    elif status_filter == ProductStatusFilter.ACTIVE:
        # Stock activo (>= 50)
        query = query.join(
            stock_subquery, ProductReference.id == stock_subquery.c.product_id
        ).filter(stock_subquery.c.total_stock >= 50)
    
    return query


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("", response_model=ProductListResponse)
def list_products(
    status: ProductStatusFilter = Query(
        ProductStatusFilter.ALL,
        description="Filtrar por estado: all, active, low, out"
    ),
    search: Optional[str] = Query(
        None,
        description="Buscar por nombre, SKU, categoría o referencia"
    ),
    page: int = Query(1, ge=1, description="Número de página"),
    per_page: int = Query(20, ge=1, le=100, description="Productos por página"),
    db: Session = Depends(get_db)
):
    """
    Lista productos con filtros y paginación.
    
    **Filtros disponibles:**
    - `status`: all, active (stock >= 50), low (stock 1-49), out (stock = 0)
    - `search`: Busca en nombre, SKU, categoría (descripción_color) o referencia
    
    **Respuesta:**
    - Lista de productos con ubicaciones limitadas (primeras 2 + "+X más")
    - Información de paginación
    - Stock total calculado
    - Estado calculado automáticamente
    """
    # Query base con ubicaciones pre-cargadas
    query = db.query(ProductReference).options(
        joinedload(ProductReference.locations)
    )
    
    # Aplicar búsqueda
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                ProductReference.nombre_producto.ilike(search_pattern),
                ProductReference.sku.ilike(search_pattern),
                ProductReference.color.ilike(search_pattern),
                ProductReference.referencia.ilike(search_pattern)
            )
        )
    
    # Aplicar filtro de estado
    # Nota: El filtro se aplica después para no afectar la búsqueda
    # Si necesitas mejor performance, considera agregar columna 'stock_total' calculada
    
    # Contar total antes de paginar
    total = query.count()
    
    # Aplicar ordenamiento (requerido por SQL Server para OFFSET/LIMIT)
    query = query.order_by(ProductReference.id.asc())
    
    # Aplicar paginación
    offset = (page - 1) * per_page
    products = query.offset(offset).limit(per_page).all()
    
    # Filtrar por estado en memoria (para simplicidad)
    # Para mejor performance con muchos registros, mover el filtro a SQL
    filtered_products = []
    for product in products:
        stock = _calculate_total_stock(product)
        status_text, status_class = calculate_product_status(stock)
        
        # Aplicar filtro de estado
        if status != ProductStatusFilter.ALL:
            if status == ProductStatusFilter.ACTIVE and status_class != "active":
                continue
            elif status == ProductStatusFilter.LOW and status_class != "low-stock":
                continue
            elif status == ProductStatusFilter.OUT and status_class != "out-of-stock":
                continue
        
        filtered_products.append(product)
    
    # Construir respuesta
    product_items = []
    for product in filtered_products:
        stock = _calculate_total_stock(product)
        status_text, status_class = calculate_product_status(stock)
        
        product_items.append(ProductListItem(
            id=product.id,
            sku=product.sku or product.referencia,
            name=product.nombre_producto,
            category=product.color or "Sin categoría",
            talla=product.talla,
            image=None,  # TODO: Agregar soporte para imágenes
            locations=_format_locations_for_list(product.locations),
            stock=stock,
            status=status_text,
            statusClass=status_class
        ))
    
    # Calcular páginas totales
    total_pages = math.ceil(total / per_page) if total > 0 else 0
    
    return ProductListResponse(
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        products=product_items
    )


@router.get("/{product_id}", response_model=ProductDetail)
def get_product(
    product_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene los detalles completos de un producto.
    
    **Incluye:**
    - Toda la información del producto
    - Todas las ubicaciones (sin límite)
    - Stock total calculado
    - Estado calculado
    """
    product = db.query(ProductReference).options(
        joinedload(ProductReference.locations)
    ).filter(ProductReference.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail=f"Producto con ID {product_id} no encontrado")
    
    # Calcular stock total
    stock = _calculate_total_stock(product)
    status_text, status_class = calculate_product_status(stock)
    
    # Formatear ubicaciones detalladas
    location_details = []
    for loc in product.locations:
        if loc.activa:
            location_details.append(ProductLocationDetail(
                id=loc.id,
                code=format_location_code(loc.pasillo, loc.lado, loc.ubicacion, loc.altura),
                pasillo=loc.pasillo,
                lado=loc.lado,
                ubicacion=loc.ubicacion,
                altura=loc.altura,
                stock_actual=loc.stock_actual,
                stock_minimo=loc.stock_minimo,
                prioridad=loc.prioridad,
                activa=loc.activa
            ))
    
    return ProductDetail(
        id=product.id,
        referencia=product.referencia,
        sku=product.sku,
        nombre_producto=product.nombre_producto,
        name=product.nombre_producto,
        color_id=product.color_id,
        descripcion_color=product.color,
        category=product.color,
        talla=product.talla,
        ean=product.ean,
        temporada=product.temporada,
        activo=product.activo,
        stock=stock,
        locations=location_details,
        status=status_text,
        statusClass=status_class
    )


@router.get("/{product_id}/locations", response_model=ProductLocationsResponse)
def get_product_locations(
    product_id: int,
    include_inactive: bool = Query(
        False,
        description="Incluir ubicaciones inactivas"
    ),
    db: Session = Depends(get_db)
):
    """
    Obtiene todas las ubicaciones de un producto específico.
    
    **Respuesta detallada:**
    - Lista completa de ubicaciones (sin límite)
    - Stock por ubicación
    - Prioridad de cada ubicación
    - Stock total sumado
    - Estado del producto
    
    **Parámetros:**
    - `include_inactive`: Si es true, incluye ubicaciones inactivas
    """
    product = db.query(ProductReference).options(
        joinedload(ProductReference.locations)
    ).filter(ProductReference.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail=f"Producto con ID {product_id} no encontrado")
    
    # Filtrar ubicaciones según parámetro
    locations = product.locations
    if not include_inactive:
        locations = [loc for loc in locations if loc.activa]
    
    # Calcular stock total
    total_stock = sum(loc.stock_actual for loc in locations)
    status_text, status_class = calculate_product_status(total_stock)
    
    # Formatear ubicaciones
    location_details = []
    for loc in sorted(locations, key=lambda x: (x.prioridad, -x.stock_actual)):
        location_details.append(ProductLocationDetail(
            id=loc.id,
            code=format_location_code(loc.pasillo, loc.lado, loc.ubicacion, loc.altura),
            pasillo=loc.pasillo,
            lado=loc.lado,
            ubicacion=loc.ubicacion,
            altura=loc.altura,
            stock_actual=loc.stock_actual,
            stock_minimo=loc.stock_minimo,
            prioridad=loc.prioridad,
            activa=loc.activa
        ))
    
    return ProductLocationsResponse(
        product_id=product.id,
        product_name=product.nombre_producto,
        product_sku=product.sku or product.referencia,
        locations=location_details,
        total_locations=len(location_details),
        total_stock=total_stock,
        status=status_text,
        status_class=status_class
    )


@router.get("/{product_id}/stock-summary")
def get_product_stock_summary(
    product_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene un resumen rápido del stock de un producto.
    
    **Útil para:**
    - Verificaciones rápidas de stock
    - Alertas de stock bajo
    - Dashboards
    """
    product = db.query(ProductReference).options(
        joinedload(ProductReference.locations)
    ).filter(ProductReference.id == product_id).first()
    
    if not product:
        raise HTTPException(status_code=404, detail=f"Producto con ID {product_id} no encontrado")
    
    # Calcular métricas
    active_locations = [loc for loc in product.locations if loc.activa]
    total_stock = sum(loc.stock_actual for loc in active_locations)
    low_stock_locations = [
        loc for loc in active_locations 
        if loc.stock_actual < loc.stock_minimo
    ]
    
    status_text, status_class = calculate_product_status(total_stock)
    
    return {
        "product_id": product.id,
        "product_name": product.nombre_producto,
        "sku": product.sku or product.referencia,
        "total_stock": total_stock,
        "total_locations": len(active_locations),
        "low_stock_locations": len(low_stock_locations),
        "status": status_text,
        "status_class": status_class,
        "needs_restock": len(low_stock_locations) > 0,
        "locations_summary": [
            {
                "code": format_location_code(loc.pasillo, loc.lado, loc.ubicacion, loc.altura),
                "stock": loc.stock_actual,
                "needs_restock": loc.stock_actual < loc.stock_minimo
            }
            for loc in active_locations
        ]
    }


@router.post("/{product_id}/locations", response_model=ProductLocationResponse, status_code=201)
def create_product_location(
    product_id: int,
    location_data: ProductLocationCreate,
    db: Session = Depends(get_db)
):
    """
    Crea una nueva ubicación para un producto.
    
    **Campos requeridos:**
    - `pasillo`: Identificador del pasillo (ej: "A", "B3", "C")
    - `lado`: Lado del pasillo ("IZQUIERDA" o "DERECHA")
    - `ubicacion`: Posición específica (ej: "12", "05")
    - `altura`: Nivel de altura (1-10)
    
    **Campos opcionales:**
    - `stock_minimo`: Stock mínimo (default: 0)
    - `stock_actual`: Stock actual (default: 0)
    - `prioridad`: Prioridad para picking 1-5 (default: 3)
    - `activa`: Si está activa (default: true)
    
    **Validaciones:**
    - El producto debe existir
    - No puede haber ubicaciones duplicadas (mismo pasillo, lado, ubicacion, altura)
    - El lado debe ser "IZQUIERDA" o "DERECHA"
    - La altura debe estar entre 1 y 10
    - La prioridad debe estar entre 1 y 5
    
    **Retorna:**
    - La ubicación creada con su ID y código generado
    """
    # Verificar que el producto existe
    product = db.query(ProductReference).filter(
        ProductReference.id == product_id
    ).first()
    
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Producto con ID {product_id} no encontrado"
        )
    
    # Validar lado
    if location_data.lado.upper() not in ["IZQUIERDA", "DERECHA"]:
        raise HTTPException(
            status_code=400,
            detail="El lado debe ser 'IZQUIERDA' o 'DERECHA'"
        )
    
    # Verificar que no exista una ubicación duplicada
    existing_location = db.query(ProductLocation).filter(
        ProductLocation.product_id == product_id,
        ProductLocation.pasillo == location_data.pasillo,
        ProductLocation.lado == location_data.lado.upper(),
        ProductLocation.ubicacion == location_data.ubicacion,
        ProductLocation.altura == location_data.altura
    ).first()
    
    if existing_location:
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe una ubicación para este producto en {location_data.pasillo}-{location_data.lado}-{location_data.ubicacion}-{location_data.altura}"
        )
    
    # Crear nueva ubicación
    new_location = ProductLocation(
        product_id=product_id,
        pasillo=location_data.pasillo,
        lado=location_data.lado.upper(),
        ubicacion=location_data.ubicacion,
        altura=location_data.altura,
        stock_minimo=location_data.stock_minimo,
        stock_actual=location_data.stock_actual,
        prioridad=location_data.prioridad,
        activa=location_data.activa
    )
    
    db.add(new_location)
    db.commit()
    db.refresh(new_location)
    
    # Convertir a response model
    return ProductLocationResponse(
        id=new_location.id,
        product_id=new_location.product_id,
        pasillo=new_location.pasillo,
        lado=new_location.lado,
        ubicacion=new_location.ubicacion,
        altura=new_location.altura,
        stock_minimo=new_location.stock_minimo,
        stock_actual=new_location.stock_actual,
        prioridad=new_location.prioridad,
        activa=new_location.activa,
        codigo_ubicacion=new_location.codigo_ubicacion,
        created_at=new_location.created_at,
        updated_at=new_location.updated_at
    )
