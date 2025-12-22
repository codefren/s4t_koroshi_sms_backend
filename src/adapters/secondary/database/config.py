from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import urllib

import os

# Example Connection String for ODBC
# In a real app, load these from environment variables
SERVER = os.getenv('DB_SERVER', '127.0.0.1')
DATABASE = os.getenv('DB_NAME', 'master')
USERNAME = os.getenv('DB_USER', 'sa')
PASSWORD = os.getenv('DB_PASSWORD', 'YourStrong@Passw0rd')
# Try ODBC Driver 18 (default for Ubuntu 22.04+), fall back manually if needed
DRIVER = '{ODBC Driver 18 for SQL Server}'

# Construct connection string
# Note: TrustServerCertificate=yes is MANDATORY for ODBC Driver 18+ with self-signed certs
params = urllib.parse.quote_plus(f'DRIVER={DRIVER};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD};TrustServerCertificate=yes;')
DATABASE_URL = f"mssql+pyodbc:///?odbc_connect={params}"

# DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
