#!/usr/bin/env python3
"""
Script para agregar columnas faltantes a product_references de forma directa.
"""

import sys
sys.path.append('.')

from sqlalchemy import text
from src.adapters.secondary.database.config import SessionLocal


def add_column_if_not_exists(db, column_name, column_type):
    """Agrega una columna si no existe."""
    try:
        # Verificar si existe
        check_query = text("""
            SELECT COUNT(*) as count
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'product_references'
              AND COLUMN_NAME = :column_name
        """)
        
        result = db.execute(check_query, {"column_name": column_name})
        exists = result.scalar() > 0
        
        if exists:
            print(f"  ⏭️  Columna '{column_name}' ya existe")
            return True
        
        # Agregar columna
        alter_query = text(f"""
            ALTER TABLE product_references
            ADD {column_name} {column_type}
        """)
        
        db.execute(alter_query)
        db.commit()
        
        print(f"  ✅ Columna '{column_name}' agregada exitosamente")
        return True
    
    except Exception as e:
        print(f"  ❌ Error agregando '{column_name}': {e}")
        db.rollback()
        return False


def main():
    print("=" * 60)
    print("🔧 AGREGANDO COLUMNAS A product_references")
    print("=" * 60)
    print()
    
    db = SessionLocal()
    
    try:
        # Agregar columna 'color'
        print("1. Agregando columna 'color'...")
        success1 = add_column_if_not_exists(db, 'color', 'VARCHAR(100) NULL')
        
        print()
        
        # Agregar columna 'posicion_talla'
        print("2. Agregando columna 'posicion_talla'...")
        success2 = add_column_if_not_exists(db, 'posicion_talla', 'VARCHAR(50) NULL')
        
        print()
        print("=" * 60)
        
        if success1 and success2:
            print("✅ COLUMNAS AGREGADAS CORRECTAMENTE")
            print()
            print("Próximos pasos:")
            print("  1. python seed_products.py --force")
            print("  2. python recreate_orders_with_products.py")
            print("  3. uvicorn src.main:app --reload")
            return 0
        else:
            print("❌ ALGUNAS COLUMNAS NO SE AGREGARON")
            return 1
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
