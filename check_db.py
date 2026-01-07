from src.adapters.secondary.database.config import SessionLocal
from src.adapters.secondary.database.orm import InventoryItemModel

def check_db():
    db = SessionLocal()
    try:
        items = db.query(InventoryItemModel).all()
        print(f"Found {len(items)} items in the database.")
        for item in items[:5]: # Show first 5
            print(f"EAN: {item.ean}, Articulo: {item.articulo}, Cantidad: {item.cantidad}")
    except Exception as e:
        print(f"Error querying database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_db()
