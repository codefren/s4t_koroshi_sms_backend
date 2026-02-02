"""
Configuración de base de datos SQLite en memoria para tests
Reutiliza el mismo ORM de producción pero con SQLite
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import OperationalError

from src.adapters.secondary.database.orm import (
    Base,
    Order,
    OrderLine,
    OrderStatus,
    OrderHistory,
    ProductReference,
    Almacen,
    Customer,
    PackingBox,
    OrderLineBoxDistribution,
    PickingTask,
    ProductLocation,
    Operator,
    APIStockHistorico
)


# Engine SQLite en memoria
# StaticPool mantiene la conexión abierta durante toda la sesión de tests
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False  # Set to True para debug SQL
)


# Habilitar foreign keys en SQLite (por defecto deshabilitadas)
@event.listens_for(test_engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Session factory para tests
TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine
)


def create_test_database():
    """
    Crea todas las tablas en la BD de test
    Debe llamarse una vez al inicio de la sesión de tests
    """
    try:
        # Limpiar primero para evitar conflictos
        Base.metadata.drop_all(bind=test_engine)
    except:
        pass  # Ignorar si falla (BD vacía)
    
    try:
        Base.metadata.create_all(bind=test_engine)
    except OperationalError as e:
        # Ignorar errores de índices duplicados en SQLite
        if "already exists" not in str(e):
            raise
    
    # Forzar creación de OrderLineBoxDistribution si no existe
    # (fix para modelos agregados después de la sesión inicial)
    from sqlalchemy import inspect
    inspector = inspect(test_engine)
    existing_tables = inspector.get_table_names()
    
    if "order_line_box_distribution" not in existing_tables:
        try:
            OrderLineBoxDistribution.__table__.create(test_engine, checkfirst=True)
        except:
            pass  # Si ya existe, ignorar


def drop_test_database():
    """
    Elimina todas las tablas de la BD de test
    Útil para limpiar después de tests
    """
    Base.metadata.drop_all(bind=test_engine)


def get_test_db():
    """
    Dependency override para FastAPI
    Retorna una sesión de test en lugar de producción
    """
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()
