"""
Fixtures compartidos para tests - SQLite en memoria con ORM real
"""

import pytest
from datetime import datetime, date, timezone
from unittest.mock import Mock

from tests.database_test_config import (
    test_engine,
    TestSessionLocal,
    create_test_database,
    drop_test_database
)

from src.adapters.secondary.database.orm import (
    Base,
    Order,
    OrderLine,
    OrderStatus,
    OrderHistory,
    ProductReference,
    Almacen,
    Customer,
    OrderLineBoxDistribution
)


# ============================================================================
# DATABASE FIXTURES - SQLite en memoria
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Crea esquema de BD una vez por sesión de tests"""
    create_test_database()
    yield
    # No hacer drop: SQLite en memoria se limpia automáticamente al cerrar


@pytest.fixture(scope="function")
def test_db():
    """
    Sesión de BD limpia para cada test
    Usa transacciones con rollback automático para aislamiento
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


# ============================================================================
# DATA FIXTURES - Datos de prueba en BD test
# ============================================================================

@pytest.fixture
def order_statuses(test_db):
    """Crea estados de orden necesarios para tests"""
    statuses_data = [
        {"id": 1, "codigo": "PENDING", "nombre": "Pendiente", "orden": 1},
        {"id": 2, "codigo": "ASSIGNED", "nombre": "Asignado", "orden": 2},
        {"id": 3, "codigo": "IN_PICKING", "nombre": "En Picking", "orden": 3},
        {"id": 4, "codigo": "PICKED", "nombre": "Recogido", "orden": 4},
        {"id": 5, "codigo": "PACKING", "nombre": "Empacando", "orden": 5},
        {"id": 6, "codigo": "READY", "nombre": "Listo", "orden": 6},
        {"id": 7, "codigo": "SHIPPED", "nombre": "Enviado", "orden": 7},
        {"id": 8, "codigo": "CANCELLED", "nombre": "Cancelado", "orden": 8}
    ]
    
    statuses = []
    for data in statuses_data:
        status = OrderStatus(**data)
        test_db.add(status)
        statuses.append(status)
    
    test_db.commit()
    return statuses


@pytest.fixture
def test_warehouse(test_db):
    """Crea almacén de prueba"""
    warehouse = Almacen(
        id=1,
        codigo="TEST-WH",
        descripciones="Almacén de Prueba"
    )
    test_db.add(warehouse)
    test_db.commit()
    return warehouse


@pytest.fixture
def test_customer(test_db, test_warehouse):
    """Crea customer B2B de prueba autenticado"""
    customer = Customer(
        id=1,
        customer_code="TEST_B2B_001",
        nombre="Test B2B Customer",
        api_key="test_api_key_123",
        activo=True
    )
    test_db.add(customer)
    test_db.flush()
    
    # Dar acceso al warehouse
    customer.almacenes.append(test_warehouse)
    test_db.commit()
    
    # Mock simple para pasar verificaciones
    mock_customer = Mock()
    mock_customer.id = customer.id
    mock_customer.customer_code = customer.customer_code
    mock_customer.almacenes = [test_warehouse]
    
    return mock_customer


@pytest.fixture
def sample_product(test_db):
    """Crea producto de referencia de prueba"""
    product = ProductReference(
        id=100,
        sku="SAMPLE-SKU-12345678",
        referencia="REF-TEST-001",
        nombre_producto="Producto de Prueba",
        color_id="COLOR-001",
        nombre_color="Azul",
        talla="M",
        temporada="2024",
        activo=True
    )
    test_db.add(product)
    test_db.commit()
    return product


@pytest.fixture
def pending_order(test_db, order_statuses, test_warehouse):
    """
    Crea orden PENDING con líneas de prueba
    IMPORTANTE: fecha_fin_picking = NULL (no actualizada)
    """
    pending_status = test_db.query(OrderStatus).filter_by(codigo="PENDING").first()
    
    order = Order(
        numero_orden="TEST-ORD-001",
        type="B2B",
        cliente="TEST_CLIENT",
        nombre_cliente="Cliente de Prueba",
        status_id=pending_status.id,
        fecha_orden=date.today(),
        fecha_importacion=datetime.now(timezone.utc),
        almacen_id=test_warehouse.id,
        prioridad="NORMAL",
        fecha_fin_picking=None  # CRUCIAL: sin actualizar
    )
    test_db.add(order)
    test_db.flush()
    
    # Crear 3 líneas de orden
    for i in range(3):
        line = OrderLine(
            order_id=order.id,
            product_reference_id=None,
            ean=f"TEST-EAN-{i:03d}",
            cantidad_solicitada=10 + i,
            cantidad_servida=0,
            estado="PENDING"
        )
        test_db.add(line)
    
    test_db.commit()
    test_db.refresh(order)
    return order


@pytest.fixture
def updated_order(test_db, order_statuses, test_warehouse):
    """
    Crea orden ya actualizada (fecha_fin_picking marcada)
    Para testear rechazo de segunda actualización
    """
    pending_status = test_db.query(OrderStatus).filter_by(codigo="PENDING").first()
    
    order = Order(
        numero_orden="TEST-ORD-UPDATED",
        type="B2B",
        cliente="TEST_CLIENT",
        nombre_cliente="Cliente de Prueba",
        status_id=pending_status.id,
        fecha_orden=date.today(),
        fecha_importacion=datetime.now(timezone.utc),
        almacen_id=test_warehouse.id,
        prioridad="NORMAL",
        fecha_fin_picking=datetime.now(timezone.utc)  # YA ACTUALIZADA
    )
    test_db.add(order)
    test_db.commit()
    test_db.refresh(order)
    return order


@pytest.fixture
def ready_order(test_db, order_statuses, test_warehouse):
    """
    Crea orden en estado READY
    Para testear rechazo de actualización
    """
    ready_status = test_db.query(OrderStatus).filter_by(codigo="READY").first()
    
    order = Order(
        numero_orden="TEST-ORD-READY",
        type="B2B",
        cliente="TEST_CLIENT",
        nombre_cliente="Cliente de Prueba",
        status_id=ready_status.id,
        fecha_orden=date.today(),
        fecha_importacion=datetime.now(timezone.utc),
        almacen_id=test_warehouse.id,
        prioridad="NORMAL",
        fecha_fin_picking=datetime.now(timezone.utc)
    )
    test_db.add(order)
    test_db.commit()
    test_db.refresh(order)
    return order
