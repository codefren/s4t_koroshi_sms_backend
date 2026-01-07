#!/usr/bin/env python3
"""
Script de verificación rápida del sistema de fixtures.

Verifica que todas las fixtures estén funcionando correctamente.
"""

import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

print("=" * 70)
print("   VERIFICACIÓN DEL SISTEMA DE FIXTURES")
print("=" * 70)

# Test 1: Importar fixtures
print("\n1️⃣  Verificando importaciones...")
try:
    from fixtures.product_fixtures import (
        create_product,
        create_location,
        create_product_with_locations,
        create_sample_products,
        get_sample_products_data,
        create_low_stock_scenario,
        create_multi_location_product,
        create_inactive_products,
        clear_all_products,
        get_product_stats
    )
    print("   ✅ Todas las fixtures importadas correctamente")
except ImportError as e:
    print(f"   ❌ Error al importar: {e}")
    sys.exit(1)

# Test 2: Verificar modelos ORM
print("\n2️⃣  Verificando modelos ORM...")
try:
    from src.adapters.secondary.database.orm import ProductReference, ProductLocation
    print("   ✅ Modelos ORM disponibles")
except ImportError as e:
    print(f"   ❌ Error al importar modelos: {e}")
    sys.exit(1)

# Test 3: Verificar datos de ejemplo
print("\n3️⃣  Verificando datos de ejemplo...")
try:
    sample_data = get_sample_products_data()
    print(f"   ✅ {len(sample_data)} productos de ejemplo disponibles")
    print(f"      Productos: {', '.join([p['product']['referencia'] for p in sample_data])}")
except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)

# Test 4: Test de creación en memoria
print("\n4️⃣  Probando creación en base de datos en memoria...")
try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src.adapters.secondary.database.config import Base
    
    # Crear BD en memoria
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Crear producto de prueba
    product = create_product(
        session,
        referencia="TEST01",
        nombre_producto="Test Product",
        color_id="001",
        talla="M",
        commit=True
    )
    
    print(f"   ✅ Producto creado: {product.referencia}")
    
    # Crear ubicación
    location = create_location(
        session,
        product=product,
        pasillo="A",
        lado="IZQUIERDA",
        ubicacion="99",
        altura=1,
        stock_actual=10,
        commit=True
    )
    
    print(f"   ✅ Ubicación creada: {location.codigo_ubicacion}")
    
    # Verificar relación
    assert len(product.locations) == 1
    print(f"   ✅ Relación verificada: producto tiene {len(product.locations)} ubicación")
    
    session.close()
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Verificar estadísticas
print("\n5️⃣  Probando función de estadísticas...")
try:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Cargar datos de ejemplo
    create_sample_products(session)
    
    # Obtener stats
    stats = get_product_stats(session)
    
    print(f"   ✅ Estadísticas obtenidas:")
    print(f"      • Productos: {stats['total_products']}")
    print(f"      • Ubicaciones: {stats['total_locations']}")
    print(f"      • Stock total: {stats['total_stock']}")
    
    session.close()
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)

# Test 6: Verificar escenarios especiales
print("\n6️⃣  Probando escenarios especiales...")
try:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Escenario low stock
    low_stock_locs = create_low_stock_scenario(session)
    print(f"   ✅ Escenario low-stock: {len(low_stock_locs)} ubicaciones")
    
    # Multi ubicación
    multi_prod = create_multi_location_product(session, num_locations=5)
    print(f"   ✅ Multi-ubicación: {len(multi_prod.locations)} ubicaciones")
    
    # Productos inactivos
    inactive = create_inactive_products(session, count=3)
    print(f"   ✅ Productos inactivos: {len(inactive)} productos")
    
    session.close()
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)

# Test 7: Verificar conftest.py
print("\n7️⃣  Verificando integración con tests...")
try:
    # Verificar que el archivo existe
    conftest_path = Path(__file__).parent / "tests" / "conftest.py"
    if conftest_path.exists():
        print(f"   ✅ conftest.py encontrado")
        
        # Verificar que contiene las nuevas fixtures
        content = conftest_path.read_text()
        if "populated_db_session" in content and "seeded_with_test_scenarios" in content:
            print(f"   ✅ Fixtures integradas en conftest.py")
        else:
            print(f"   ⚠️  Fixtures no encontradas en conftest.py")
    else:
        print(f"   ⚠️  conftest.py no encontrado")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

# Resumen final
print("\n" + "=" * 70)
print("✅ VERIFICACIÓN COMPLETADA EXITOSAMENTE")
print("=" * 70)
print("\n📚 Sistema de fixtures listo para usar:")
print("\n   Seeding:")
print("      python seed_products.py")
print("      python seed_products.py --force")
print("      python seed_products.py --stats")
print("\n   Testing:")
print("      pytest tests/ -v")
print("      pytest tests/test_product_models.py -v")
print("\n   Programático:")
print("      from fixtures.product_fixtures import create_product")
print()
