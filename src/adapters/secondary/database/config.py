from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import urllib

import os

# Example Connection String for ODBC
# In a real app, load these from environment variables
SERVER = os.getenv('DB_SERVER', '127.0.0.1')
DATABASE = os.getenv('DB_NAME', 's4t_sms')  # Nueva base de datos creada
USERNAME = os.getenv('DB_USER', 'sa')
PASSWORD = os.getenv('DB_PASSWORD', 'YourStrong@Passw0rd')
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
