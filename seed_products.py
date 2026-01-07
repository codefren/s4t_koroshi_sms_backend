#!/usr/bin/env python3
"""
Script para cargar datos semilla (seed data) de productos y ubicaciones.

Similar a init_order_system.py, este script inicializa la base de datos
con datos de ejemplo para productos y ubicaciones.

Uso:
    python seed_products.py                    # Carga datos de ejemplo
    python seed_products.py --force            # Elimina datos existentes y recarga
    python seed_products.py --scenario low-stock  # Escenario específico
"""

import sys
import argparse
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.adapters.secondary.database.config import Base, DATABASE_URL
from src.adapters.secondary.database.orm import ProductReference, ProductLocation

# Importar fixtures
from fixtures.product_fixtures import (
    create_sample_products,
    create_low_stock_scenario,
    create_multi_location_product,
    create_inactive_products,
    get_product_stats,
    clear_all_products
)


def create_tables():
    """Crea las tablas de productos y ubicaciones."""
    print("🔧 Verificando tablas...")
    
    engine = create_engine(DATABASE_URL)
    
    # Crear tablas si no existen
    ProductReference.__table__.create(engine, checkfirst=True)
    ProductLocation.__table__.create(engine, checkfirst=True)
    
    print("✅ Tablas verificadas:")
    print("   - product_references")
    print("   - product_locations")
    
    return engine


def seed_sample_data(session, force=False):
    """Carga datos de ejemplo estándar."""
    print("\n📦 Cargando datos de productos...")
    
    products = create_sample_products(session, force=force)
    
    if not products:
        return False
    
    print(f"✅ {len(products)} productos creados exitosamente")
    
    # Mostrar resumen
    for product in products:
        print(f"   • {product.referencia} - {product.nombre_producto}")
        print(f"     └─ {len(product.locations)} ubicaciones")
    
    return True


def seed_test_scenarios(session):
    """Carga escenarios de prueba adicionales."""
    print("\n🧪 Creando escenarios de prueba...")
    
    # Escenario 1: Stock bajo
    print("\n   1️⃣  Creando escenario de stock bajo...")
    low_stock_locs = create_low_stock_scenario(session)
    print(f"      ✅ {len(low_stock_locs)} ubicaciones con stock bajo")
    
    # Escenario 2: Producto con muchas ubicaciones
    print("\n   2️⃣  Creando producto multi-ubicación...")
    multi_product = create_multi_location_product(session, num_locations=6)
    print(f"      ✅ Producto con {len(multi_product.locations)} ubicaciones")
    
    # Escenario 3: Productos inactivos
    print("\n   3️⃣  Creando productos inactivos...")
    inactive = create_inactive_products(session, count=3)
    print(f"      ✅ {len(inactive)} productos inactivos creados")
    
    print("\n✅ Escenarios de prueba creados")


def show_stats(session):
    """Muestra estadísticas de la base de datos."""
    print("\n📊 Estadísticas de la base de datos:")
    
    stats = get_product_stats(session)
    
    print(f"\n   📦 Productos:")
    print(f"      • Total: {stats['total_products']}")
    print(f"      • Activos: {stats['active_products']}")
    print(f"      • Inactivos: {stats['inactive_products']}")
    
    print(f"\n   📍 Ubicaciones:")
    print(f"      • Total: {stats['total_locations']}")
    print(f"      • Activas: {stats['active_locations']}")
    print(f"      • Inactivas: {stats['inactive_locations']}")
    
    print(f"\n   ⚠️  Alertas:")
    print(f"      • Stock bajo: {stats['low_stock_locations']} ubicaciones")
    
    print(f"\n   📈 Stock:")
    print(f"      • Total: {stats['total_stock']} unidades")


def main():
    """Función principal."""
    parser = argparse.ArgumentParser(description="Cargar datos semilla de productos")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Eliminar datos existentes y recargar"
    )
    parser.add_argument(
        "--scenario",
        choices=["sample", "test", "all", "clear"],
        default="sample",
        help="Escenario a cargar: sample (default), test, all, clear"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Solo mostrar estadísticas"
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("   SEED DE DATOS - Sistema de Productos y Ubicaciones")
    print("=" * 70)
    
    try:
        # Crear tablas
        engine = create_tables()
        
        # Crear sesión
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Solo estadísticas
        if args.stats:
            show_stats(session)
            session.close()
            return
        
        # Limpiar base de datos
        if args.scenario == "clear":
            print("\n🗑️  Limpiando base de datos...")
            count = clear_all_products(session)
            print(f"✅ {count} productos eliminados")
            session.close()
            return
        
        # Cargar datos según escenario
        if args.scenario in ["sample", "all"]:
            seed_sample_data(session, force=args.force)
        
        if args.scenario in ["test", "all"]:
            seed_test_scenarios(session)
        
        # Mostrar estadísticas finales
        show_stats(session)
        
        # Cerrar sesión
        session.close()
        
        print("\n" + "=" * 70)
        print("✅ Seed completado exitosamente")
        print("=" * 70)
        print("\n📚 Próximos pasos:")
        print("   1. Iniciar servidor: cd src && uvicorn main:app --reload")
        print("   2. Ver productos: GET http://localhost:8000/api/v1/products")
        print("   3. Documentación: http://localhost:8000/docs")
        print("\n💡 Comandos útiles:")
        print("   python seed_products.py --stats         # Ver estadísticas")
        print("   python seed_products.py --force         # Recargar datos")
        print("   python seed_products.py --scenario test # Solo escenarios de prueba")
        print("   python seed_products.py --scenario clear # Limpiar DB")
        print()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Operación cancelada por el usuario")
        sys.exit(1)
    except Exception as e:
        print("\n" + "=" * 70)
        print(f"❌ ERROR: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
