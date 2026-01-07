#!/usr/bin/env python3
"""
Verifica el estado de las migraciones en la base de datos.
"""

import sys
sys.path.append('.')

from sqlalchemy import text
from src.adapters.secondary.database.config import SessionLocal


def check_columns():
    """Verifica qué columnas existen en product_references."""
    print("=" * 60)
    print("🔍 VERIFICANDO COLUMNAS EN product_references")
    print("=" * 60)
    
    db = SessionLocal()
    
    try:
        result = db.execute(text("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'product_references'
            ORDER BY ORDINAL_POSITION
        """))
        
        columns = result.fetchall()
        
        print(f"\nColumnas encontradas: {len(columns)}\n")
        
        has_color = False
        has_posicion_talla = False
        
        for col in columns:
            col_name, data_type, nullable = col
            print(f"  - {col_name:30} {data_type:15} NULL={nullable}")
            
            if col_name == 'color':
                has_color = True
            if col_name == 'posicion_talla':
                has_posicion_talla = True
        
        print("\n" + "=" * 60)
        print("📊 RESULTADO")
        print("=" * 60)
        
        if has_color and has_posicion_talla:
            print("✅ Las columnas 'color' y 'posicion_talla' EXISTEN")
            print("✅ Migración completada correctamente")
            return True
        else:
            print("❌ FALTAN COLUMNAS:")
            if not has_color:
                print("   - color NO EXISTE")
            if not has_posicion_talla:
                print("   - posicion_talla NO EXISTE")
            
            print("\n💡 SOLUCIÓN:")
            print("   Ejecuta manualmente:")
            print("   python fix_product_references.py")
            return False
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    finally:
        db.close()


if __name__ == "__main__":
    success = check_columns()
    sys.exit(0 if success else 1)
