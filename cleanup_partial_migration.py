#!/usr/bin/env python3
"""
Script para limpiar una migración parcial fallida.
"""

import sys
sys.path.append('.')

from sqlalchemy import text
from src.adapters.secondary.database.config import SessionLocal


def cleanup():
    """Limpia cambios parciales de la migración."""
    print("=" * 60)
    print("🧹 LIMPIANDO MIGRACIÓN PARCIAL")
    print("=" * 60)
    
    db = SessionLocal()
    
    commands = [
        # Eliminar FKs si existen
        "IF EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'fk_order_lines_product_reference') ALTER TABLE order_lines DROP CONSTRAINT fk_order_lines_product_reference",
        "IF EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'fk_order_lines_product_location') ALTER TABLE order_lines DROP CONSTRAINT fk_order_lines_product_location",
        
        # Eliminar índices si existen
        "IF EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_order_lines_product_ref') DROP INDEX idx_order_lines_product_ref ON order_lines",
        "IF EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_order_lines_product_loc') DROP INDEX idx_order_lines_product_loc ON order_lines",
        
        # Eliminar columnas si existen
        "IF EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'order_lines' AND COLUMN_NAME = 'product_reference_id') ALTER TABLE order_lines DROP COLUMN product_reference_id",
        "IF EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'order_lines' AND COLUMN_NAME = 'product_location_id') ALTER TABLE order_lines DROP COLUMN product_location_id"
    ]
    
    try:
        for cmd in commands:
            try:
                print(f"  Ejecutando: {cmd[:60]}...")
                db.execute(text(cmd))
                db.commit()
                print("  ✅ OK")
            except Exception as e:
                print(f"  ⚠️  {str(e)[:50]}")
                db.rollback()
        
        print()
        print("✅ Limpieza completada")
        print("Ahora ejecuta: python run_migration.py")
        return True
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    cleanup()
