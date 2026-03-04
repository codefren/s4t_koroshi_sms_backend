from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import urllib
import os
import logging
from dotenv import load_dotenv

# Configurar logger
logger = logging.getLogger(__name__)

# Cargar variables de entorno desde archivo .env
load_dotenv()

# Example Connection String for ODBC
# In a real app, load these from environment variables
SERVER = os.getenv('DB_SERVER', '127.0.0.1')
DATABASE = os.getenv('DB_NAME', 'S4T_SMS_RESTORE')  # Nueva base de datos creada
USERNAME = os.getenv('DB_USER', 'sa')
PASSWORD = os.getenv('DB_PASSWORD', 'YourStrong@Passw0rd')

# Warehouse IDs for picking and replenishment zones
ALMACEN_PICKING_ID = int(os.getenv('ALMACEN_PICKING_ID', '3'))  # Zona de picking (destino)
ALMACEN_REPOSICION_ID = int(os.getenv('ALMACEN_REPOSICION_ID', '4'))  # Zona de reposición (origen)

# Cron Services Configuration
CRON_INTERVAL_MINUTES = int(os.getenv('CRON_INTERVAL_MINUTES', '1'))  # Frecuencia de ejecución de crons
SYSTEM_OPERATOR_CODE = os.getenv('SYSTEM_OPERATOR_CODE', 'SYSTEM')  # Código del operador sistema

# Log de configuración cargada (sin información sensible)
logger.info("=" * 60)
logger.info("📋 Configuración de Base de Datos y Almacenes")
logger.info(f"   🖥️  Server: {SERVER}")
logger.info(f"   🗄️  Database: {DATABASE}")
logger.info(f"   👤 Username: {USERNAME}")
logger.info(f"   🔑 Password: {'*' * len(PASSWORD) if PASSWORD else 'NOT SET'}")
logger.info(f"   📦 Almacén Picking ID (destino): {ALMACEN_PICKING_ID}")
logger.info(f"   📦 Almacén Reposición ID (origen): {ALMACEN_REPOSICION_ID}")
logger.info("")
logger.info("⚙️  Configuración de Servicios Cron")
logger.info(f"   ⏰ Intervalo Cron: {CRON_INTERVAL_MINUTES} minuto(s)")
logger.info(f"   🤖 Operador Sistema: {SYSTEM_OPERATOR_CODE}")
logger.info("=" * 60)
# Try ODBC Driver 18 (default for Ubuntu 22.04+), fall back manually if needed
DRIVER = '{ODBC Driver 18 for SQL Server}'

# Construct connection string
# Note: TrustServerCertificate=yes is MANDATORY for ODBC Driver 18+ with self-signed certs
params = urllib.parse.quote_plus(f'DRIVER={DRIVER};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD};TrustServerCertificate=yes;')
DATABASE_URL = f"mssql+pyodbc:///?odbc_connect={params}"

# DATABASE_URL = "sqlite:///./test.db"

# Configurar engine con pool adecuado
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_size=10,              # Número de conexiones persistentes
    max_overflow=20,           # Conexiones adicionales si se necesitan
    pool_timeout=30,           # Timeout para obtener conexión del pool
    pool_recycle=3600,         # Reciclar conexiones cada hora
    pool_pre_ping=True,        # Verificar conexión antes de usarla
    echo=False                 # No mostrar SQL en logs (cambiar a True para debug)
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
