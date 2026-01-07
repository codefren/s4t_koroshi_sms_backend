"""
Fixtures/Factories para crear datos de productos y ubicaciones.

Estas funciones permiten crear datos de prueba o desarrollo de manera
consistente y reutilizable.

Uso:
    from fixtures.product_fixtures import create_sample_products
    
    products = create_sample_products(session)
"""

import sys
from pathlib import Path
from typing import List, Optional
from sqlalchemy.orm import Session

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.adapters.secondary.database.orm import ProductReference, ProductLocation


# ============================================================================
# FACTORIES DE PRODUCTOS
# ============================================================================

def create_product(
    session: Session,
    referencia: str,
    nombre_producto: str,
    color_id: str,
    talla: str,
    color: Optional[str] = None,
    posicion_talla: Optional[str] = None,
    descripcion_color: Optional[str] = None,
    ean: Optional[str] = None,
    sku: Optional[str] = None,
    temporada: Optional[str] = None,
    activo: bool = True,
    commit: bool = False
) -> ProductReference:
    """
    Factory para crear un producto.
    
    Args:
        session: Sesión de SQLAlchemy
        referencia: Código hexadecimal único
        nombre_producto: Nombre del producto
        color_id: ID del color
        talla: Talla del producto
        color: Nombre corto del color (ej: "Rojo", "Azul")
        posicion_talla: Posición para ordenamiento (opcional)
        descripcion_color: Descripción del color (opcional)
        ean: Código EAN (opcional)
        sku: SKU del producto (opcional)
        temporada: Temporada (opcional)
        activo: Si está activo (default: True)
        commit: Si hacer commit automáticamente (default: False)
    
    Returns:
        ProductReference creado
    """
    product = ProductReference(
        referencia=referencia,
        nombre_producto=nombre_producto,
        color_id=color_id,
        color=color,
        talla=talla,
        posicion_talla=posicion_talla,
        descripcion_color=descripcion_color,
        ean=ean,
        sku=sku,
        temporada=temporada,
        activo=activo
    )
    
    session.add(product)
    
    if commit:
        session.commit()
        session.refresh(product)
    
    return product


def create_location(
    session: Session,
    product: ProductReference,
    pasillo: str,
    lado: str,
    ubicacion: str,
    altura: int,
    stock_minimo: int = 0,
    stock_actual: int = 0,
    prioridad: int = 3,
    activa: bool = True,
    commit: bool = False
) -> ProductLocation:
    """
    Factory para crear una ubicación de producto.
    
    Args:
        session: Sesión de SQLAlchemy
        product: Producto al que pertenece
        pasillo: Identificador del pasillo
        lado: Lado del pasillo (IZQUIERDA/DERECHA)
        ubicacion: Posición específica
        altura: Altura (1-10)
        stock_minimo: Stock mínimo (default: 0)
        stock_actual: Stock actual (default: 0)
        prioridad: Prioridad para picking 1-5 (default: 3)
        activa: Si está activa (default: True)
        commit: Si hacer commit automáticamente (default: False)
    
    Returns:
        ProductLocation creado
    """
    location = ProductLocation(
        product=product,
        pasillo=pasillo,
        lado=lado,
        ubicacion=ubicacion,
        altura=altura,
        stock_minimo=stock_minimo,
        stock_actual=stock_actual,
        prioridad=prioridad,
        activa=activa
    )
    
    session.add(location)
    
    if commit:
        session.commit()
        session.refresh(location)
    
    return location


def create_product_with_locations(
    session: Session,
    product_data: dict,
    locations_data: List[dict],
    commit: bool = True
) -> ProductReference:
    """
    Factory para crear un producto con múltiples ubicaciones.
    
    Args:
        session: Sesión de SQLAlchemy
        product_data: Diccionario con datos del producto
        locations_data: Lista de diccionarios con datos de ubicaciones
        commit: Si hacer commit automáticamente (default: True)
    
    Returns:
        ProductReference con ubicaciones creadas
    
    Example:
        product = create_product_with_locations(
            session,
            product_data={
                "referencia": "A1B2C3",
                "nombre_producto": "Camisa Polo",
                "color_id": "001",
                "talla": "M"
            },
            locations_data=[
                {"pasillo": "A", "lado": "IZQUIERDA", "ubicacion": "12", "altura": 2, "stock_actual": 45},
                {"pasillo": "B", "lado": "DERECHA", "ubicacion": "05", "altura": 1, "stock_actual": 12}
            ]
        )
    """
    # Crear producto
    product = create_product(session, **product_data, commit=False)
    
    # Crear ubicaciones
    for loc_data in locations_data:
        create_location(session, product, **loc_data, commit=False)
    
    if commit:
        session.commit()
        session.refresh(product)
    
    return product


# ============================================================================
# DATOS SEMILLA (SEED DATA)
# ============================================================================

def get_sample_products_data() -> List[dict]:
    """
    Retorna datos de productos de ejemplo para seeding.
    
    Returns:
        Lista de diccionarios con datos de productos y sus ubicaciones
    """
    return [
        {
            "product": {
                "referencia": "A1B2C3",
                "nombre_producto": "Camisa Polo Manga Corta",
                "color_id": "000001",
                "color": "Rojo",
                "talla": "M",
                "posicion_talla": "3",
                "descripcion_color": "Rojo",
                "ean": "8445962763983",
                "sku": "2523HA02",
                "temporada": "Verano 2024",
                "activo": True
            },
            "locations": [
                {
                    "pasillo": "A",
                    "lado": "IZQUIERDA",
                    "ubicacion": "12",
                    "altura": 2,
                    "stock_minimo": 10,
                    "stock_actual": 45,
                    "activa": True
                },
                {
                    "pasillo": "B3",
                    "lado": "DERECHA",
                    "ubicacion": "05",
                    "altura": 1,
                    "stock_minimo": 5,
                    "stock_actual": 12,
                    "activa": True
                }
            ]
        },
        {
            "product": {
                "referencia": "D4E5F6",
                "nombre_producto": "Pantalón Vaquero Slim",
                "color_id": "000010",
                "color": "Azul",
                "talla": "32",
                "posicion_talla": "5",
                "descripcion_color": "Azul Oscuro",
                "ean": "8445962733320",
                "sku": "2521PT18",
                "temporada": "Otoño 2024",
                "activo": True
            },
            "locations": [
                {
                    "pasillo": "C",
                    "lado": "IZQUIERDA",
                    "ubicacion": "08",
                    "altura": 3,
                    "stock_minimo": 8,
                    "stock_actual": 23,
                    "activa": True
                }
            ]
        },
        {
            "product": {
                "referencia": "7G8H9I",
                "nombre_producto": "Camisa Polo Manga Corta",
                "color_id": "000002",
                "color": "Azul",
                "talla": "L",
                "posicion_talla": "4",
                "descripcion_color": "Azul Marino",
                "ean": "8445962763990",
                "sku": "2523HA02",
                "temporada": "Verano 2024",
                "activo": True
            },
            "locations": [
                {
                    "pasillo": "A",
                    "lado": "DERECHA",
                    "ubicacion": "14",
                    "altura": 2,
                    "stock_minimo": 15,
                    "stock_actual": 38,
                    "activa": True
                },
                {
                    "pasillo": "D",
                    "lado": "IZQUIERDA",
                    "ubicacion": "03",
                    "altura": 1,
                    "stock_minimo": 5,
                    "stock_actual": 8,
                    "activa": True
                }
            ]
        },
        {
            "product": {
                "referencia": "1A2B3C",
                "nombre_producto": "Sudadera con Capucha",
                "color_id": "000003",
                "talla": "XL",
                "descripcion_color": "Negro",
                "ean": "8445962700001",
                "sku": "2525SW01",
                "temporada": "Invierno 2024",
                "activo": True
            },
            "locations": [
                {
                    "pasillo": "B",
                    "lado": "IZQUIERDA",
                    "ubicacion": "20",
                    "altura": 4,
                    "stock_minimo": 12,
                    "stock_actual": 5,  # Stock bajo
                    "activa": True
                }
            ]
        },
        {
            "product": {
                "referencia": "FF00AA",
                "nombre_producto": "Chaqueta Deportiva",
                "color_id": "000005",
                "talla": "M",
                "descripcion_color": "Verde",
                "ean": "8445962700018",
                "sku": "2526JK01",
                "temporada": "Primavera 2024",
                "activo": True
            },
            "locations": [
                {
                    "pasillo": "E",
                    "lado": "DERECHA",
                    "ubicacion": "08",
                    "altura": 2,
                    "stock_minimo": 10,
                    "stock_actual": 25,
                    "activa": True
                },
                {
                    "pasillo": "E",
                    "lado": "DERECHA",
                    "ubicacion": "09",
                    "altura": 2,
                    "stock_minimo": 10,
                    "stock_actual": 30,
                    "activa": True
                }
            ]
        }
    ]


def create_sample_products(session: Session, force: bool = False) -> List[ProductReference]:
    """
    Crea productos de ejemplo en la base de datos.
    
    Args:
        session: Sesión de SQLAlchemy
        force: Si True, elimina productos existentes primero
    
    Returns:
        Lista de productos creados
    """
    # Verificar si ya existen productos
    existing_count = session.query(ProductReference).count()
    
    if existing_count > 0 and not force:
        print(f"⚠️  Ya existen {existing_count} productos en la base de datos")
        print("   Usa force=True para eliminarlos y recrearlos")
        return []
    
    if force and existing_count > 0:
        print(f"🗑️  Eliminando {existing_count} productos existentes...")
        session.query(ProductReference).delete()
        session.commit()
    
    # Obtener datos de ejemplo
    sample_data = get_sample_products_data()
    
    # Crear productos
    products = []
    for item in sample_data:
        product = create_product_with_locations(
            session,
            product_data=item["product"],
            locations_data=item["locations"],
            commit=False
        )
        products.append(product)
    
    # Commit una sola vez al final
    session.commit()
    
    # Refresh todos los productos
    for product in products:
        session.refresh(product)
    
    return products


# ============================================================================
# FACTORIES ESPECIALIZADAS
# ============================================================================

def create_low_stock_scenario(session: Session) -> List[ProductLocation]:
    """
    Crea un escenario con ubicaciones de stock bajo para testing.
    
    Returns:
        Lista de ubicaciones con stock bajo
    """
    product = create_product(
        session,
        referencia="LOWSTK",
        nombre_producto="Producto Stock Bajo",
        color_id="999",
        talla="M",
        commit=True
    )
    
    locations = [
        create_location(session, product, "A", "IZQUIERDA", "99", 1, 
                       stock_minimo=20, stock_actual=5, commit=False),
        create_location(session, product, "B", "DERECHA", "99", 1, 
                       stock_minimo=15, stock_actual=3, commit=False),
        create_location(session, product, "C", "IZQUIERDA", "99", 1, 
                       stock_minimo=10, stock_actual=0, commit=False),
    ]
    
    session.commit()
    
    for loc in locations:
        session.refresh(loc)
    
    return locations


def create_multi_location_product(session: Session, num_locations: int = 5) -> ProductReference:
    """
    Crea un producto con múltiples ubicaciones.
    
    Args:
        session: Sesión de SQLAlchemy
        num_locations: Número de ubicaciones a crear
    
    Returns:
        Producto con múltiples ubicaciones
    """
    product = create_product(
        session,
        referencia=f"MULTI{num_locations}",
        nombre_producto=f"Producto Multi-Ubicación ({num_locations})",
        color_id="888",
        talla="L",
        commit=True
    )
    
    pasillos = ["A", "B", "C", "D", "E", "F", "G", "H"]
    lados = ["IZQUIERDA", "DERECHA"]
    
    for i in range(num_locations):
        create_location(
            session,
            product,
            pasillo=pasillos[i % len(pasillos)],
            lado=lados[i % 2],
            ubicacion=str(i + 1),
            altura=(i % 5) + 1,
            stock_minimo=10,
            stock_actual=20 + (i * 5),
            commit=False
        )
    
    session.commit()
    session.refresh(product)
    
    return product


def create_inactive_products(session: Session, count: int = 3) -> List[ProductReference]:
    """
    Crea productos inactivos para testing.
    
    Args:
        session: Sesión de SQLAlchemy
        count: Número de productos inactivos a crear
    
    Returns:
        Lista de productos inactivos
    """
    products = []
    
    for i in range(count):
        product = create_product(
            session,
            referencia=f"INACT{i:02d}",
            nombre_producto=f"Producto Inactivo {i+1}",
            color_id=f"{i:06d}",
            talla="S",
            activo=False,
            commit=False
        )
        products.append(product)
    
    session.commit()
    
    for product in products:
        session.refresh(product)
    
    return products


# ============================================================================
# UTILIDADES
# ============================================================================

def clear_all_products(session: Session) -> int:
    """
    Elimina todos los productos y ubicaciones.
    
    Returns:
        Número de productos eliminados
    """
    count = session.query(ProductReference).count()
    session.query(ProductReference).delete()
    session.commit()
    return count


def get_product_stats(session: Session) -> dict:
    """
    Obtiene estadísticas de productos y ubicaciones.
    
    Returns:
        Diccionario con estadísticas
    """
    from sqlalchemy import func
    
    total_products = session.query(ProductReference).count()
    active_products = session.query(ProductReference).filter_by(activo=True).count()
    total_locations = session.query(ProductLocation).count()
    active_locations = session.query(ProductLocation).filter_by(activa=True).count()
    
    # Ubicaciones con stock bajo
    low_stock = session.query(ProductLocation).filter(
        ProductLocation.stock_actual < ProductLocation.stock_minimo,
        ProductLocation.activa == True
    ).count()
    
    # Stock total
    total_stock = session.query(func.sum(ProductLocation.stock_actual)).scalar() or 0
    
    return {
        "total_products": total_products,
        "active_products": active_products,
        "inactive_products": total_products - active_products,
        "total_locations": total_locations,
        "active_locations": active_locations,
        "inactive_locations": total_locations - active_locations,
        "low_stock_locations": low_stock,
        "total_stock": total_stock
    }
