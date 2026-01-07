#!/usr/bin/env python3
"""
Script para aplicar la normalización completa del sistema.

Este script ejecuta todas las migraciones necesarias y recrea las órdenes
con la nueva estructura normalizada.

Uso:
    python apply_normalization.py
    python apply_normalization.py --skip-orders  # No recrear órdenes
"""

import sys
import subprocess
import argparse
from pathlib import Path

sys.path.append('.')

from sqlalchemy import text
from src.adapters.secondary.database.config import SessionLocal


def print_banner(title):
    """Imprime un banner bonito."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def run_migration(migration_file):
    """Ejecuta un archivo de migración SQL."""
    print(f"📄 Ejecutando: {migration_file.name}\n")
    
    db = SessionLocal()
    
    try:
        # Leer archivo SQL
        sql_content = migration_file.read_text(encoding='utf-8')
        
        # Dividir por GO (separador de SQL Server)
        batches = []
        current_batch = []
        
        for line in sql_content.split('\n'):
            if line.strip().upper() == 'GO':
                if current_batch:
                    batches.append('\n'.join(current_batch))
                    current_batch = []
            else:
                current_batch.append(line)
        
        if current_batch:
            batches.append('\n'.join(current_batch))
        
        # Ejecutar cada batch
        for i, batch in enumerate(batches, 1):
            batch = batch.strip()
            if not batch or batch.startswith('--'):
                continue
            
            try:
                # Ejecutar batch
                result = db.execute(text(batch))
                db.commit()
                
                # Mostrar mensajes PRINT de SQL Server
                if result.returns_rows:
                    for row in result:
                        if row:
                            print(f"   {row[0]}")
            
            except Exception as e:
                error_msg = str(e)
                
                # Ignorar errores de "ya existe"
                if "already exists" in error_msg.lower() or "does not exist" in error_msg.lower():
                    print(f"   ⚠️  {error_msg.split(':')[0]}")
                    db.rollback()
                    continue
                else:
                    print(f"\n❌ Error en batch {i}: {error_msg}")
                    db.rollback()
                    return False
        
        print(f"\n✅ Migración {migration_file.name} completada\n")
        return True
    
    except Exception as e:
        print(f"\n❌ Error ejecutando migración: {e}\n")
        db.rollback()
        return False
    
    finally:
        db.close()


def seed_products():
    """Carga productos de ejemplo."""
    print("📦 Cargando productos de ejemplo...\n")
    
    try:
        result = subprocess.run(
            ['python', 'seed_products.py', '--force'],
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        
        if result.returncode != 0:
            print(f"⚠️  Error cargando productos: {result.stderr}")
            return False
        
        return True
    
    except Exception as e:
        print(f"⚠️  Error: {e}")
        return False


def recreate_orders(num_orders=10):
    """Recrea órdenes con productos vinculados."""
    print(f"📦 Recreando {num_orders} órdenes con productos vinculados...\n")
    
    try:
        result = subprocess.run(
            ['python', 'recreate_orders_with_products.py', '--num-orders', str(num_orders)],
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        
        if result.returncode != 0:
            print(f"⚠️  Error recreando órdenes: {result.stderr}")
            return False
        
        return True
    
    except Exception as e:
        print(f"⚠️  Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Aplicar normalización completa')
    parser.add_argument('--skip-orders', action='store_true', help='No recrear órdenes')
    parser.add_argument('--num-orders', type=int, default=10, help='Número de órdenes a crear')
    
    args = parser.parse_args()
    
    print_banner("🚀 APLICANDO NORMALIZACIÓN COMPLETA")
    
    migrations_dir = Path('migrations')
    
    # Paso 1: Migración 001 (FKs)
    print_banner("PASO 1: Agregar Foreign Keys a order_lines")
    
    migration_001 = migrations_dir / '001_add_product_fks_to_order_lines.sql'
    if not migration_001.exists():
        print("⚠️  Migración 001 no encontrada, saltando...")
    else:
        if not run_migration(migration_001):
            print("❌ Error en migración 001")
            return 1
    
    # Paso 2: Migración 002 (Normalización)
    print_banner("PASO 2: Normalizar order_lines")
    
    migration_002 = migrations_dir / '002_normalize_order_lines.sql'
    if not migration_002.exists():
        print("❌ Migración 002 no encontrada")
        return 1
    
    if not run_migration(migration_002):
        print("❌ Error en migración 002")
        return 1
    
    # Paso 3: Cargar productos
    print_banner("PASO 3: Cargar productos de ejemplo")
    
    if not seed_products():
        print("⚠️  Error cargando productos, pero continuando...")
    
    # Paso 4: Recrear órdenes (opcional)
    if not args.skip_orders:
        print_banner(f"PASO 4: Recrear {args.num_orders} órdenes")
        
        if not recreate_orders(args.num_orders):
            print("⚠️  Error recreando órdenes")
            return 1
    else:
        print_banner("PASO 4: Recreación de órdenes SALTADA")
    
    # Resumen final
    print_banner("✅ NORMALIZACIÓN COMPLETADA")
    
    print("📊 Resumen de cambios:")
    print("   ✅ product_references: +2 columnas (color, posicion_talla)")
    print("   ✅ order_lines: -8 columnas redundantes eliminadas")
    print("   ✅ order_lines: Solo mantiene EAN + FKs + cantidades")
    print("   ✅ Datos 100% normalizados")
    print()
    print("🎯 Próximos pasos:")
    print("   1. Reiniciar API: uvicorn src.main:app --reload")
    print("   2. Probar endpoints: http://localhost:8000/docs")
    print("   3. Verificar órdenes: GET /api/v1/orders")
    print("   4. Optimizar ruta: POST /api/v1/orders/1/optimize-picking-route")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
