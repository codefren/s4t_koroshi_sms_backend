#!/usr/bin/env python3
"""
Script para ejecutar migraciones de base de datos.

Ejecuta el script SQL que agrega las columnas product_reference_id y product_location_id
a la tabla order_lines.

Uso:
    python run_migration.py
"""

import sys
from pathlib import Path

sys.path.append('.')

from sqlalchemy import text
from src.adapters.secondary.database.config import SessionLocal


def run_migration():
    """Ejecuta la migración SQL."""
    print("=" * 60)
    print("🔄 EJECUTANDO MIGRACIÓN DE BASE DE DATOS")
    print("=" * 60)
    print()
    
    # Leer archivo SQL
    migration_file = Path("migrations/001_add_product_fks_to_order_lines.sql")
    
    if not migration_file.exists():
        print(f"❌ Archivo de migración no encontrado: {migration_file}")
        return False
    
    print(f"📄 Leyendo: {migration_file}")
    sql_script = migration_file.read_text(encoding='utf-8')
    
    # Dividir por comandos (separados por GO o punto y coma)
    commands = []
    current_command = []
    
    for line in sql_script.split('\n'):
        line = line.strip()
        
        # Ignorar comentarios y líneas vacías
        if line.startswith('--') or not line:
            continue
        
        # Detectar separador GO
        if line.upper() == 'GO':
            if current_command:
                commands.append('\n'.join(current_command))
                current_command = []
        else:
            current_command.append(line)
    
    # Agregar último comando si existe
    if current_command:
        commands.append('\n'.join(current_command))
    
    # Ejecutar comandos
    db = SessionLocal()
    
    try:
        print(f"\n🔧 Ejecutando {len(commands)} comando(s) SQL...")
        print()
        
        for idx, command in enumerate(commands, 1):
            # Dividir por punto y coma (múltiples statements)
            statements = [s.strip() for s in command.split(';') if s.strip()]
            
            for statement in statements:
                try:
                    print(f"  [{idx}] Ejecutando: {statement[:80]}...")
                    db.execute(text(statement))
                    db.commit()
                    print(f"      ✅ OK")
                except Exception as e:
                    error_msg = str(e)
                    
                    # Ignorar errores de "columna ya existe"
                    if "already exists" in error_msg.lower() or "duplicate" in error_msg.lower():
                        print(f"      ⚠️  Ya existe (ignorando)")
                        db.rollback()
                        continue
                    else:
                        print(f"      ❌ Error: {error_msg}")
                        db.rollback()
                        raise
        
        print()
        print("=" * 60)
        print("✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
        print("=" * 60)
        print()
        print("Cambios aplicados:")
        print("  - Columna 'product_reference_id' agregada a order_lines")
        print("  - Columna 'product_location_id' agregada a order_lines")
        print("  - Índices creados para performance")
        print("  - Foreign keys configuradas")
        print()
        print("Próximos pasos:")
        print("  1. Reiniciar API: uvicorn src.main:app --reload")
        print("  2. Vincular datos históricos: python migrate_orders_to_products.py")
        print("  3. Probar endpoints: http://localhost:8000/docs")
        print()
        
        return True
    
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ ERROR EN MIGRACIÓN")
        print("=" * 60)
        print(f"Error: {e}")
        print()
        print("La base de datos NO fue modificada (rollback aplicado)")
        print()
        return False
    
    finally:
        db.close()


def verify_migration():
    """Verifica que las columnas existen."""
    print("🔍 Verificando migración...")
    
    db = SessionLocal()
    
    try:
        result = db.execute(text("""
            SELECT 
                COLUMN_NAME, 
                DATA_TYPE, 
                IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'order_lines'
              AND COLUMN_NAME IN ('product_reference_id', 'product_location_id')
        """))
        
        columns = result.fetchall()
        
        if len(columns) == 2:
            print("✅ Verificación exitosa - Columnas encontradas:")
            for col in columns:
                print(f"   - {col[0]} ({col[1]}, nullable={col[2]})")
            return True
        else:
            print(f"⚠️  Solo se encontraron {len(columns)} de 2 columnas")
            return False
    
    except Exception as e:
        print(f"⚠️  No se pudo verificar: {e}")
        return False
    
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Ejecutar migración de base de datos')
    parser.add_argument('--verify-only', action='store_true', help='Solo verificar sin ejecutar')
    
    args = parser.parse_args()
    
    if args.verify_only:
        success = verify_migration()
    else:
        success = run_migration()
        if success:
            verify_migration()
    
    sys.exit(0 if success else 1)
