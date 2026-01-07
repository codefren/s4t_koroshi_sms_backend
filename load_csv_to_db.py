#!/usr/bin/env python3
"""
Script to load inventory items from CSV into the database.
Reads 1111087088_final_complete.csv and inserts records into inventory_items table.
"""

import csv
import sys
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import text

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.adapters.secondary.database.config import SessionLocal, engine
from src.adapters.secondary.database.orm import InventoryItemModel

def load_csv_to_db(csv_file: str, batch_size: int = 50):
    """
    Load items from CSV file into database.
    
    Args:
        csv_file: Path to CSV file
        batch_size: Number of records to insert per batch
    """
    print(f"🔄 Starting to load data from {csv_file}")
    
    # Check if file exists
    if not Path(csv_file).exists():
        print(f"❌ Error: File {csv_file} not found")
        return
    
    # Create database session
    db: Session = SessionLocal()
    
    try:
        # Count existing records
        existing_count = db.query(InventoryItemModel).count()
        print(f"📊 Current records in database: {existing_count}")
        
        # Read CSV file
        with open(csv_file, 'r', encoding='latin-1') as f:
            # Use semicolon as delimiter
            reader = csv.DictReader(f, delimiter=';')
            
            batch = []
            total_processed = 0
            total_inserted = 0
            total_errors = 0
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (row 1 is header)
                try:
                    # Create InventoryItem from CSV row
                    item = InventoryItemModel(
                        ean=row.get('ean', '').strip() or None,
                        ubicacion=row.get('ubicación', '').strip() or None,
                        articulo=row.get('articulo', '').strip() or None,
                        color=row.get('color', '').strip() or None,
                        talla=row.get('talla', '').strip() or None,
                        posicion_talla=row.get('posiciontalla', '').strip() or None,
                        descripcion_producto=row.get('descripcion producto', '').strip() or None,
                        descripcion_color=row.get('descripcion color', '').strip() or None,
                        temporada=row.get('temporada', '').strip() or None,
                        numero_orden=row.get('no.orden', '').strip() or None,
                        cliente=row.get('cliente', '').strip() or None,
                        nombre_cliente=row.get('nombre cliente', '').strip() or None,
                        cantidad=int(row.get('cantidad', 0)) if row.get('cantidad', '').strip() else 0,
                        servida=int(row.get('servida', 0)) if row.get('servida', '').strip() else 0,
                        operario=row.get('operario', '').strip() or None,
                        status=row.get('status', '').strip() or None,
                        fecha=row.get('fecha', '').strip() or None,
                        hora=row.get('hora', '').strip() or None,
                        caja=row.get('caja', '').strip() or None,
                    )
                    
                    batch.append(item)
                    total_processed += 1
                    
                    # Insert batch when it reaches batch_size
                    if len(batch) >= batch_size:
                        db.bulk_save_objects(batch)
                        db.commit()
                        total_inserted += len(batch)
                        print(f"✅ Inserted batch of {len(batch)} items (Total: {total_inserted})")
                        batch = []
                        
                except Exception as e:
                    total_errors += 1
                    print(f"⚠️  Error processing row {row_num}: {e}")
                    continue
            
            # Insert remaining items
            if batch:
                db.bulk_save_objects(batch)
                db.commit()
                total_inserted += len(batch)
                print(f"✅ Inserted final batch of {len(batch)} items")
        
        # Final statistics
        print("\n" + "="*60)
        print("📈 LOADING COMPLETE")
        print("="*60)
        print(f"✅ Total rows processed: {total_processed}")
        print(f"✅ Total items inserted: {total_inserted}")
        print(f"⚠️  Total errors: {total_errors}")
        
        # Count new total
        new_count = db.query(InventoryItemModel).count()
        print(f"📊 Records in database now: {new_count}")
        print(f"📊 New records added: {new_count - existing_count}")
        
        # Show orders summary
        print("\n" + "="*60)
        print("📦 ORDERS SUMMARY")
        print("="*60)
        result = db.execute(text("""
            SELECT numero_orden, COUNT(*) as item_count
            FROM inventory_items
            GROUP BY numero_orden
            ORDER BY numero_orden
        """))
        
        for order, count in result:
            print(f"  Order {order}: {count} items")
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        db.rollback()
        raise
    finally:
        db.close()
        print("\n✅ Database connection closed")

if __name__ == "__main__":
    csv_file = "1111087088_final_complete.csv"
    load_csv_to_db(csv_file)
