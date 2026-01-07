"""
Configuración global de fixtures para pytest.

Este archivo contiene fixtures compartidos que pueden ser usados
en todos los tests del proyecto.
"""

import sys
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.adapters.secondary.database.config import Base
from src.adapters.secondary.database.orm import (
    ProductReference,
    ProductLocation,
    Operator,
    OrderStatus
)


# ============================================================================
# FIXTURES DE BASE DE DATOS
# ============================================================================

@pytest.fixture(scope="function")
def test_db_engine():
    """
    Crea un engine de base de datos en memoria para tests.
    Se crea y destruye para cada test (scope="function").
    """
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_db_session(test_db_engine):
    """
    Proporciona una sesión de base de datos para tests.
    Hace rollback automático después de cada test.
    """
    Session = sessionmaker(bind=test_db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


# ============================================================================
# FIXTURES DE PRODUCTOS
# ============================================================================

@pytest.fixture
def sample_product_data():
    """Datos de ejemplo para crear un producto."""
    return {
        "referencia": "A1B2C3",
        "nombre_producto": "Camisa Polo Manga Corta",
        "color_id": "000001",
        "talla": "M",
        "descripcion_color": "Rojo",
        "ean": "8445962763983",
        "sku": "2523HA02",
        "temporada": "Verano 2024",
        "activo": True
    }


@pytest.fixture
def sample_product(test_db_session, sample_product_data):
    """Crea y retorna un producto de ejemplo en la base de datos."""
    product = ProductReference(**sample_product_data)
    test_db_session.add(product)
    test_db_session.commit()
    test_db_session.refresh(product)
    return product


@pytest.fixture
def multiple_products(test_db_session):
    """Crea múltiples productos en la base de datos."""
    products = [
        ProductReference(
            referencia="A1B2C3",
            nombre_producto="Camisa Polo Manga Corta",
            color_id="000001",
            talla="M",
            descripcion_color="Rojo",
            ean="8445962763983",
            sku="2523HA02",
            temporada="Verano 2024",
            activo=True
        ),
        ProductReference(
            referencia="D4E5F6",
            nombre_producto="Pantalón Vaquero Slim",
            color_id="000010",
            talla="32",
            descripcion_color="Azul Oscuro",
            ean="8445962733320",
            sku="2521PT18",
            temporada="Otoño 2024",
            activo=True
        ),
        ProductReference(
            referencia="7G8H9I",
            nombre_producto="Camisa Polo Manga Corta",
            color_id="000002",
            talla="L",
            descripcion_color="Azul Marino",
            ean="8445962763990",
            sku="2523HA02",
            temporada="Verano 2024",
            activo=True
        ),
        ProductReference(
            referencia="ABC123",
            nombre_producto="Producto Inactivo",
            color_id="000099",
            talla="S",
            descripcion_color="Negro",
            activo=False
        )
    ]
    
    test_db_session.add_all(products)
    test_db_session.commit()
    
    for product in products:
        test_db_session.refresh(product)
    
    return products


# ============================================================================
# FIXTURES DE UBICACIONES
# ============================================================================

@pytest.fixture
def sample_location_data():
    """Datos de ejemplo para crear una ubicación."""
    return {
        "pasillo": "A",
        "lado": "IZQUIERDA",
        "ubicacion": "12",
        "altura": 2,
        "stock_minimo": 10,
        "stock_actual": 45,
        "activa": True
    }


@pytest.fixture
def sample_location(test_db_session, sample_product, sample_location_data):
    """Crea y retorna una ubicación de ejemplo en la base de datos."""
    location = ProductLocation(
        product=sample_product,
        **sample_location_data
    )
    test_db_session.add(location)
    test_db_session.commit()
    test_db_session.refresh(location)
    return location


@pytest.fixture
def product_with_multiple_locations(test_db_session):
    """Crea un producto con múltiples ubicaciones."""
    # Crear producto
    product = ProductReference(
        referencia="MULTI1",
        nombre_producto="Producto Multi-Ubicación",
        color_id="000001",
        talla="M",
        descripcion_color="Rojo",
        activo=True
    )
    
    # Crear ubicaciones
    locations = [
        ProductLocation(
            product=product,
            pasillo="A",
            lado="IZQUIERDA",
            ubicacion="12",
            altura=2,
            stock_minimo=10,
            stock_actual=45,
            activa=True
        ),
        ProductLocation(
            product=product,
            pasillo="B3",
            lado="DERECHA",
            ubicacion="05",
            altura=1,
            stock_minimo=5,
            stock_actual=12,
            activa=True
        ),
        ProductLocation(
            product=product,
            pasillo="C",
            lado="IZQUIERDA",
            ubicacion="08",
            altura=3,
            stock_minimo=8,
            stock_actual=3,  # Stock bajo
            activa=True
        ),
        ProductLocation(
            product=product,
            pasillo="D",
            lado="DERECHA",
            ubicacion="20",
            altura=4,
            stock_minimo=5,
            stock_actual=0,  # Sin stock
            activa=False  # Inactiva
        )
    ]
    
    test_db_session.add(product)
    test_db_session.add_all(locations)
    test_db_session.commit()
    
    test_db_session.refresh(product)
    for location in locations:
        test_db_session.refresh(location)
    
    return product


@pytest.fixture
def multiple_locations(test_db_session, sample_product):
    """Crea múltiples ubicaciones para un producto."""
    locations = [
        ProductLocation(
            product=sample_product,
            pasillo="A",
            lado="IZQUIERDA",
            ubicacion="12",
            altura=2,
            stock_minimo=10,
            stock_actual=45,
            activa=True
        ),
        ProductLocation(
            product=sample_product,
            pasillo="B3",
            lado="DERECHA",
            ubicacion="05",
            altura=1,
            stock_minimo=5,
            stock_actual=12,
            activa=True
        ),
        ProductLocation(
            product=sample_product,
            pasillo="C",
            lado="IZQUIERDA",
            ubicacion="08",
            altura=3,
            stock_minimo=8,
            stock_actual=23,
            activa=True
        )
    ]
    
    test_db_session.add_all(locations)
    test_db_session.commit()
    
    for location in locations:
        test_db_session.refresh(location)
    
    return locations


@pytest.fixture
def locations_with_low_stock(test_db_session, sample_product):
    """Crea ubicaciones con stock bajo para testing de alertas."""
    locations = [
        ProductLocation(
            product=sample_product,
            pasillo="A",
            lado="IZQUIERDA",
            ubicacion="12",
            altura=2,
            stock_minimo=10,
            stock_actual=3,  # Bajo stock
            activa=True
        ),
        ProductLocation(
            product=sample_product,
            pasillo="B",
            lado="DERECHA",
            ubicacion="05",
            altura=1,
            stock_minimo=20,
            stock_actual=5,  # Bajo stock
            activa=True
        ),
        ProductLocation(
            product=sample_product,
            pasillo="C",
            lado="IZQUIERDA",
            ubicacion="08",
            altura=3,
            stock_minimo=5,
            stock_actual=0,  # Sin stock
            activa=True
        )
    ]
    
    test_db_session.add_all(locations)
    test_db_session.commit()
    
    for location in locations:
        test_db_session.refresh(location)
    
    return locations


# ============================================================================
# FIXTURES DE DATOS PYDANTIC
# ============================================================================

@pytest.fixture
def product_create_data():
    """Datos válidos para ProductReferenceCreate."""
    return {
        "referencia": "AAABBB",
        "nombre_producto": "Test Product",
        "color_id": "000001",
        "talla": "M",
        "descripcion_color": "Rojo",
        "ean": "1234567890123",
        "sku": "TEST-SKU-001",
        "temporada": "Verano 2024",
        "activo": True
    }


@pytest.fixture
def product_update_data():
    """Datos válidos para ProductReferenceUpdate."""
    return {
        "nombre_producto": "Updated Product Name",
        "descripcion_color": "Azul Oscuro",
        "activo": False
    }


@pytest.fixture
def location_create_data():
    """Datos válidos para ProductLocationCreate."""
    return {
        "product_id": 1,
        "pasillo": "Z",
        "lado": "DERECHA",
        "ubicacion": "99",
        "altura": 5,
        "stock_minimo": 15,
        "stock_actual": 50,
        "activa": True
    }


@pytest.fixture
def location_update_data():
    """Datos válidos para ProductLocationUpdate."""
    return {
        "stock_actual": 100,
        "stock_minimo": 20,
        "activa": False
    }


# ============================================================================
# FIXTURES DE CASOS ESPECIALES
# ============================================================================

@pytest.fixture
def invalid_product_data():
    """Datos inválidos para testing de validaciones."""
    return [
        # Referencia no hexadecimal
        {
            "referencia": "ZZZZZ",  # Contiene Z (no hex)
            "nombre_producto": "Test",
            "color_id": "001",
            "talla": "M"
        },
        # Referencia vacía
        {
            "referencia": "",
            "nombre_producto": "Test",
            "color_id": "001",
            "talla": "M"
        },
        # Nombre vacío
        {
            "referencia": "ABC123",
            "nombre_producto": "",
            "color_id": "001",
            "talla": "M"
        }
    ]


@pytest.fixture
def invalid_location_data():
    """Datos inválidos para testing de validaciones de ubicaciones."""
    return [
        # Altura fuera de rango (menor que 1)
        {
            "product_id": 1,
            "pasillo": "A",
            "lado": "IZQUIERDA",
            "ubicacion": "12",
            "altura": 0,  # Inválido
            "stock_minimo": 10,
            "stock_actual": 45
        },
        # Altura fuera de rango (mayor que 10)
        {
            "product_id": 1,
            "pasillo": "A",
            "lado": "IZQUIERDA",
            "ubicacion": "12",
            "altura": 11,  # Inválido
            "stock_minimo": 10,
            "stock_actual": 45
        },
        # Stock negativo
        {
            "product_id": 1,
            "pasillo": "A",
            "lado": "IZQUIERDA",
            "ubicacion": "12",
            "altura": 2,
            "stock_minimo": -5,  # Inválido
            "stock_actual": 45
        }
    ]


# ============================================================================
# FIXTURES AUXILIARES
# ============================================================================

@pytest.fixture
def current_datetime():
    """Fecha y hora actual para tests."""
    return datetime.utcnow()


@pytest.fixture
def sample_operator(test_db_session):
    """Crea un operario de ejemplo (útil para tests integrados)."""
    operator = Operator(
        codigo_operario="OP001",
        nombre="Juan Pérez",
        activo=True
    )
    test_db_session.add(operator)
    test_db_session.commit()
    test_db_session.refresh(operator)
    return operator


# ============================================================================
# INTEGRACIÓN CON FIXTURES DE SEEDING
# ============================================================================

@pytest.fixture
def populated_db_session(test_db_session):
    """
    Sesión con datos semilla completos cargados.
    Usa las fixtures de fixtures/product_fixtures.py
    """
    from fixtures.product_fixtures import create_sample_products
    
    create_sample_products(test_db_session, force=False)
    yield test_db_session
    # Rollback automático por test_db_session


@pytest.fixture
def seeded_with_test_scenarios(test_db_session):
    """
    Sesión con datos de ejemplo + escenarios de prueba.
    """
    from fixtures.product_fixtures import (
        create_sample_products,
        create_low_stock_scenario,
        create_multi_location_product
    )
    
    create_sample_products(test_db_session, force=False)
    create_low_stock_scenario(test_db_session)
    create_multi_location_product(test_db_session, num_locations=5)
    
    yield test_db_session
