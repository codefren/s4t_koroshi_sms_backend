#!/usr/bin/env python3
"""
Script para inicializar el sistema de gestión de órdenes y picking.
Crea las tablas y carga los datos semilla (estados de órdenes).
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sqlalchemy import text
from src.adapters.secondary.database.config import engine, Base, SessionLocal
from src.adapters.secondary.database.orm import (
    OrderViewCache,
    OrderStatus,
    Operator,
    Order,
    OrderLine,
    OrderHistory,
    PickingTask
)


def create_tables():
    """Crea todas las tablas en la base de datos."""
    print("🔧 Creando tablas del sistema de órdenes...")
    
    try:
        # Crear todas las tablas definidas en Base
        Base.metadata.create_all(bind=engine)
        print("✅ Tablas creadas exitosamente")
        return True
    except Exception as e:
        print(f"❌ Error al crear tablas: {e}")
        return False


def seed_order_statuses():
    """Carga los estados iniciales de las órdenes."""
    print("\n📊 Cargando estados de órdenes...")
    
    db = SessionLocal()
    
    try:
        # Verificar si ya existen estados
        existing = db.query(OrderStatus).count()
        if existing > 0:
            print(f"⚠️  Ya existen {existing} estados en la base de datos")
            response = input("¿Desea reemplazarlos? (s/n): ")
            if response.lower() != 's':
                print("❌ Operación cancelada")
                return False
            
            # Eliminar estados existentes
            db.query(OrderStatus).delete()
            db.commit()
            print("🗑️  Estados anteriores eliminados")
        
        # Estados del sistema
        statuses = [
            {
                "codigo": "PENDING",
                "nombre": "Pendiente",
                "descripcion": "Orden creada, esperando asignación a operario",
                "orden": 10
            },
            {
                "codigo": "ASSIGNED",
                "nombre": "Asignada",
                "descripcion": "Orden asignada a un operario",
                "orden": 20
            },
            {
                "codigo": "IN_PICKING",
                "nombre": "En Picking",
                "descripcion": "Operario recogiendo ítems de la orden",
                "orden": 30
            },
            {
                "codigo": "PICKED",
                "nombre": "Picking Completado",
                "descripcion": "Todos los ítems han sido recogidos",
                "orden": 40
            },
            {
                "codigo": "PACKING",
                "nombre": "En Empaque",
                "descripcion": "Orden siendo empacada",
                "orden": 50
            },
            {
                "codigo": "READY",
                "nombre": "Lista para Envío",
                "descripcion": "Orden empacada y lista para ser enviada",
                "orden": 60
            },
            {
                "codigo": "SHIPPED",
                "nombre": "Enviada",
                "descripcion": "Orden enviada al cliente",
                "orden": 70
            },
            {
                "codigo": "CANCELLED",
                "nombre": "Cancelada",
                "descripcion": "Orden cancelada",
                "orden": 99
            }
        ]
        
        # Insertar estados
        for status_data in statuses:
            status = OrderStatus(**status_data)
            db.add(status)
        
        db.commit()
        print(f"✅ {len(statuses)} estados cargados exitosamente:")
        
        # Mostrar estados creados
        for status in db.query(OrderStatus).order_by(OrderStatus.orden).all():
            print(f"   [{status.orden:02d}] {status.codigo:15s} - {status.nombre}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error al cargar estados: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def create_sample_operators():
    """Crea operarios de ejemplo para testing."""
    print("\n👷 ¿Desea crear operarios de ejemplo? (s/n): ", end="")
    response = input()
    
    if response.lower() != 's':
        print("⏭️  Saltando creación de operarios")
        return True
    
    db = SessionLocal()
    
    try:
        sample_operators = [
            {"codigo_operario": "OP001", "nombre": "Juan Pérez", "activo": True},
            {"codigo_operario": "OP002", "nombre": "María García", "activo": True},
            {"codigo_operario": "OP003", "nombre": "Carlos López", "activo": True},
            {"codigo_operario": "OP004", "nombre": "Ana Martínez", "activo": False},
        ]
        
        for op_data in sample_operators:
            # Verificar si ya existe
            existing = db.query(Operator).filter_by(
                codigo_operario=op_data["codigo_operario"]
            ).first()
            
            if not existing:
                operator = Operator(**op_data)
                db.add(operator)
        
        db.commit()
        
        count = db.query(Operator).count()
        print(f"✅ Operarios creados. Total en base de datos: {count}")
        
        for op in db.query(Operator).all():
            status = "✅ Activo" if op.activo else "❌ Inactivo"
            print(f"   {op.codigo_operario} - {op.nombre:20s} {status}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error al crear operarios: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def show_summary():
    """Muestra un resumen de las tablas creadas."""
    print("\n" + "="*60)
    print("📋 RESUMEN DEL SISTEMA")
    print("="*60)
    
    db = SessionLocal()
    
    try:
        tables_info = [
            ("order_view_cache", OrderViewCache, "Caché de VIEW SQL Server"),
            ("order_status", OrderStatus, "Estados de órdenes"),
            ("operators", Operator, "Operarios del almacén"),
            ("orders", Order, "Órdenes principales"),
            ("order_lines", OrderLine, "Líneas de órdenes"),
            ("order_history", OrderHistory, "Historial de cambios"),
            ("picking_tasks", PickingTask, "Tareas de picking"),
        ]
        
        print(f"\n{'Tabla':<20} {'Registros':<12} {'Descripción'}")
        print("-" * 60)
        
        for table_name, model, description in tables_info:
            count = db.query(model).count()
            print(f"{table_name:<20} {count:<12} {description}")
        
        print("\n" + "="*60)
        print("✅ Sistema de órdenes inicializado correctamente")
        print("="*60)
        
    except Exception as e:
        print(f"⚠️  Error al obtener resumen: {e}")
    finally:
        db.close()


def main():
    """Función principal."""
    print("="*60)
    print("🚀 INICIALIZACIÓN DEL SISTEMA DE GESTIÓN DE ÓRDENES")
    print("="*60)
    print()
    
    # Paso 1: Crear tablas
    if not create_tables():
        print("\n❌ Inicialización fallida")
        return 1
    
    # Paso 2: Cargar estados
    if not seed_order_statuses():
        print("\n❌ Inicialización fallida")
        return 1
    
    # Paso 3: Crear operarios de ejemplo (opcional)
    create_sample_operators()
    
    # Paso 4: Mostrar resumen
    show_summary()
    
    print("\n💡 Próximos pasos:")
    print("   1. Configurar conexión ODBC a SQL Server en .env")
    print("   2. Crear script ETL para importar órdenes de la VIEW")
    print("   3. Implementar endpoints de API para gestión de órdenes")
    print("   4. Desarrollar frontend para operarios y supervisores")
    
    return 0


if __name__ == "__main__":
    exit(main())
