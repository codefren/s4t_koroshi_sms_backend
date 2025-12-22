import csv
import sys
import os

# Ensure src is in python path
sys.path.append(os.getcwd())

from src.adapters.secondary.database.config import SessionLocal, engine, Base
from src.adapters.secondary.database.orm import InventoryItemModel

def load_csv(file_path: str):
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        with open(file_path, mode='r', encoding='latin-1') as csvfile:
            # Detect delimiter (seems to be semicolon based on previous view)
            reader = csv.DictReader(csvfile, delimiter=';')
            
            count = 0
            for row in reader:
                # Map CSV columns to ORM model fields
                # Note: keys in row allow access by header name
                item = InventoryItemModel(
                    ean=row.get('ean'),
                    ubicacion=row.get('ubicacin') or row.get('ubicacion'), # Handle encoding issue if present
                    articulo=row.get('articulo'),
                    color=row.get('color'),
                    talla=row.get('talla'),
                    posicion_talla=row.get('posiciontalla'),
                    descripcion_producto=row.get('descripcion producto'),
                    descripcion_color=row.get('descripcion color'),
                    temporada=row.get('temporada'),
                    numero_orden=row.get('no.orden'),
                    cliente=row.get('cliente'),
                    nombre_cliente=row.get('nombre cliente'),
                    cantidad=int(row.get('cantidad', 0) or 0),
                    servida=int(row.get('servida', 0) or 0),
                    operario=row.get('operario'),
                    status=row.get('status'),
                    fecha=row.get('fecha'),
                    hora=row.get('hora'),
                    caja=row.get('caja')
                )
                db.add(item)
                count += 1
            
            db.commit()
            print(f"Successfully loaded {count} records into the database.")
            
    except Exception as e:
        print(f"Error loading data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/load_data.py <path_to_csv>")
        # Default to the known file for convenience if run without args
        default_file = "1111087088_last.csv"
        if os.path.exists(default_file):
            print(f"No file argument provided, using default: {default_file}")
            load_csv(default_file)
        else:
            sys.exit(1)
    else:
        load_csv(sys.argv[1])
