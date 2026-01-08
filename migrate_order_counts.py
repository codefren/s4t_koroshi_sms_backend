#!/usr/bin/env python3
"""
Script de migración para recalcular total_items e items_completados.

Este script actualiza todas las órdenes existentes para que:
- total_items = suma de cantidad_solicitada (no conteo de líneas)
- items_completados = suma de cantidad_servida (no conteo de líneas completadas)

IMPORTANTE: Ejecutar SOLO UNA VEZ después del cambio de lógica.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sqlalchemy import func
from src.adapters.secondary.database.config import SessionLocal
from src.adapters.secondary.database.orm import Order, OrderLine


def migrate_order_counts():
    """Recalcula total_items e items_completados para todas las órdenes."""
    
    print("🔄 Iniciando migración de contadores de órdenes...")
    print("=" * 60)
    
    db = SessionLocal()
    
    try:
        # Obtener todas las órdenes
        orders = db.query(Order).all()
        total_orders = len(orders)
        
        print(f"📦 Encontradas {total_orders} órdenes para actualizar\n")
        
        updated_count = 0
        errors_count = 0
        
        for idx, order in enumerate(orders, 1):
            try:
                # Valores anteriores (para log)
                old_total_items = order.total_items
                old_items_completados = order.items_completados
                
                # Recalcular total_items (suma de cantidad_solicitada)
                total_items = db.query(func.sum(OrderLine.cantidad_solicitada)).filter(
                    OrderLine.order_id == order.id
                ).scalar() or 0
                
                # Recalcular items_completados (suma de cantidad_servida)
                items_completados = db.query(func.sum(OrderLine.cantidad_servida)).filter(
                    OrderLine.order_id == order.id
                ).scalar() or 0
                
                # Actualizar solo si hay cambios
                if old_total_items != total_items or old_items_completados != items_completados:
                    order.total_items = total_items
                    order.items_completados = items_completados
                    updated_count += 1
                    
                    print(f"[{idx}/{total_orders}] Orden {order.numero_orden}:")
                    print(f"  total_items:        {old_total_items} → {total_items}")
                    print(f"  items_completados:  {old_items_completados} → {items_completados}")
                    
                    # Calcular progreso
                    progreso = (items_completados / total_items * 100) if total_items > 0 else 0
                    print(f"  progreso:           {progreso:.2f}%")
                    print()
                else:
                    # Sin cambios, solo mostrar cada 10 órdenes
                    if idx % 10 == 0:
                        print(f"[{idx}/{total_orders}] Procesadas {idx} órdenes...")
            
            except Exception as e:
                errors_count += 1
                print(f"❌ ERROR en orden {order.numero_orden}: {e}")
                continue
        
        # Confirmar cambios
        if updated_count > 0:
            print("\n" + "=" * 60)
            print(f"💾 Guardando cambios en la base de datos...")
            db.commit()
            print("✅ Cambios guardados correctamente")
        else:
            print("\n" + "=" * 60)
            print("ℹ️  No se encontraron cambios para aplicar")
        
        # Resumen
        print("\n" + "=" * 60)
        print("📊 RESUMEN DE MIGRACIÓN")
        print("=" * 60)
        print(f"Total de órdenes:        {total_orders}")
        print(f"Órdenes actualizadas:    {updated_count}")
        print(f"Órdenes sin cambios:     {total_orders - updated_count - errors_count}")
        print(f"Errores:                 {errors_count}")
        print("=" * 60)
        
        if updated_count > 0:
            print("\n✅ Migración completada exitosamente")
        else:
            print("\nℹ️  Todas las órdenes ya estaban actualizadas")
        
        return True
    
    except Exception as e:
        print(f"\n❌ ERROR CRÍTICO durante la migración: {e}")
        db.rollback()
        return False
    
    finally:
        db.close()


def verify_migration():
    """Verifica que la migración se aplicó correctamente."""
    
    print("\n🔍 Verificando migración...")
    print("=" * 60)
    
    db = SessionLocal()
    
    try:
        # Contar órdenes con inconsistencias
        orders = db.query(Order).all()
        inconsistent_count = 0
        
        for order in orders:
            # Recalcular
            total_items = db.query(func.sum(OrderLine.cantidad_solicitada)).filter(
                OrderLine.order_id == order.id
            ).scalar() or 0
            
            items_completados = db.query(func.sum(OrderLine.cantidad_servida)).filter(
                OrderLine.order_id == order.id
            ).scalar() or 0
            
            # Verificar
            if order.total_items != total_items or order.items_completados != items_completados:
                inconsistent_count += 1
                print(f"⚠️  Orden {order.numero_orden} tiene inconsistencias:")
                print(f"   total_items: {order.total_items} (esperado: {total_items})")
                print(f"   items_completados: {order.items_completados} (esperado: {items_completados})")
        
        if inconsistent_count == 0:
            print("✅ Todas las órdenes están correctamente migradas")
        else:
            print(f"⚠️  Se encontraron {inconsistent_count} órdenes con inconsistencias")
        
        print("=" * 60)
        
        return inconsistent_count == 0
    
    finally:
        db.close()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  MIGRACIÓN DE CONTADORES DE ÓRDENES")
    print("=" * 60)
    print("\nEste script recalculará:")
    print("  • total_items = suma de cantidad_solicitada")
    print("  • items_completados = suma de cantidad_servida")
    print("\n⚠️  IMPORTANTE: Este script solo debe ejecutarse UNA VEZ")
    print("=" * 60)
    
    # Pedir confirmación
    respuesta = input("\n¿Desea continuar con la migración? (s/N): ")
    
    if respuesta.lower() != 's':
        print("\n❌ Migración cancelada por el usuario")
        sys.exit(0)
    
    print()
    
    # Ejecutar migración
    success = migrate_order_counts()
    
    if success:
        # Verificar migración
        verify_migration()
        sys.exit(0)
    else:
        print("\n❌ La migración falló. Por favor revise los errores.")
        sys.exit(1)
