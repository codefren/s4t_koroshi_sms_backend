"""
Script para inicializar el sistema de gestión de productos y ubicaciones.

Este script:
1. Crea las tablas product_references y product_locations
2. Opcionalmente carga datos de ejemplo
3. Verifica la integridad de las relaciones

Ejecutar:
    python init_product_system.py
"""

import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.adapters.secondary.database.config import Base, DATABASE_URL
from src.adapters.secondary.database.orm import ProductReference, ProductLocation

def init_product_tables():
    """Crea las tablas de productos y ubicaciones."""
    print("🔧 Iniciando sistema de productos y ubicaciones...")
    
    # Crear engine
    engine = create_engine(DATABASE_URL)
    
    # Crear tablas
    print("📦 Creando tablas...")
    ProductReference.__table__.create(engine, checkfirst=True)
    ProductLocation.__table__.create(engine, checkfirst=True)
    print("✅ Tablas creadas exitosamente:")
    print("   - product_references")
    print("   - product_locations")
    
    return engine

def load_sample_data(engine):
    """Carga datos de ejemplo."""
    print("\n📝 Cargando datos de ejemplo...")
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Verificar si ya hay datos
        existing_count = session.query(ProductReference).count()
        if existing_count > 0:
            print(f"⚠️  Ya existen {existing_count} productos. Omitiendo carga de datos de ejemplo.")
            return
        
        # Producto 1: Camisa Polo Roja M
        producto1 = ProductReference(
            referencia="A1B2C3",
            nombre_producto="Camisa Polo Manga Corta",
            color_id="000001",
            talla="M",
            descripcion_color="Rojo",
            ean="8445962763983",
            sku="2523HA02",
            temporada="Verano 2024",
            activo=True
        )
        
        # Ubicaciones del producto 1
        ubicacion1_1 = ProductLocation(
            product=producto1,
            pasillo="A",
            lado="IZQUIERDA",
            ubicacion="12",
            altura=2,
            stock_minimo=10,
            stock_actual=45,
            activa=True
        )
        
        ubicacion1_2 = ProductLocation(
            product=producto1,
            pasillo="B3",
            lado="DERECHA",
            ubicacion="05",
            altura=1,
            stock_minimo=5,
            stock_actual=12,
            activa=True
        )
        
        # Producto 2: Pantalón Vaquero Azul 32
        producto2 = ProductReference(
            referencia="D4E5F6",
            nombre_producto="Pantalón Vaquero Slim",
            color_id="000010",
            talla="32",
            descripcion_color="Azul Oscuro",
            ean="8445962733320",
            sku="2521PT18",
            temporada="Otoño 2024",
            activo=True
        )
        
        # Ubicación del producto 2
        ubicacion2_1 = ProductLocation(
            product=producto2,
            pasillo="C",
            lado="IZQUIERDA",
            ubicacion="08",
            altura=3,
            stock_minimo=8,
            stock_actual=23,
            activa=True
        )
        
        # Producto 3: Camisa Polo Azul L
        producto3 = ProductReference(
            referencia="7G8H9I",
            nombre_producto="Camisa Polo Manga Corta",
            color_id="000002",
            talla="L",
            descripcion_color="Azul Marino",
            ean="8445962763990",
            sku="2523HA02",
            temporada="Verano 2024",
            activo=True
        )
        
        # Ubicaciones del producto 3 (múltiples ubicaciones)
        ubicacion3_1 = ProductLocation(
            product=producto3,
            pasillo="A",
            lado="DERECHA",
            ubicacion="14",
            altura=2,
            stock_minimo=15,
            stock_actual=38,
            activa=True
        )
        
        ubicacion3_2 = ProductLocation(
            product=producto3,
            pasillo="D",
            lado="IZQUIERDA",
            ubicacion="03",
            altura=1,
            stock_minimo=5,
            stock_actual=8,
            activa=True
        )
        
        # Agregar todos a la sesión
        session.add_all([producto1, producto2, producto3])
        session.add_all([ubicacion1_1, ubicacion1_2, ubicacion2_1, ubicacion3_1, ubicacion3_2])
        
        # Commit
        session.commit()
        
        print("✅ Datos de ejemplo cargados exitosamente:")
        print("   - 3 productos")
        print("   - 5 ubicaciones")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error al cargar datos de ejemplo: {e}")
        raise
    finally:
        session.close()

def verify_system(engine):
    """Verifica el sistema."""
    print("\n🔍 Verificando sistema...")
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Contar productos
        product_count = session.query(ProductReference).count()
        location_count = session.query(ProductLocation).count()
        active_products = session.query(ProductReference).filter(ProductReference.activo == True).count()
        
        print(f"📊 Estadísticas:")
        print(f"   - Total de productos: {product_count}")
        print(f"   - Productos activos: {active_products}")
        print(f"   - Total de ubicaciones: {location_count}")
        
        # Mostrar productos con ubicaciones
        if product_count > 0:
            print("\n📦 Productos en el sistema:")
            products = session.query(ProductReference).all()
            for prod in products:
                print(f"\n   {prod.referencia} - {prod.nombre_producto}")
                print(f"      Color: {prod.descripcion_color} ({prod.color_id}) | Talla: {prod.talla}")
                print(f"      Ubicaciones: {len(prod.locations)}")
                for loc in prod.locations:
                    print(f"         • {loc.codigo_ubicacion} (Stock: {loc.stock_actual}/{loc.stock_minimo} min)")
        
        print("\n✅ Sistema verificado correctamente")
        
    except Exception as e:
        print(f"❌ Error en verificación: {e}")
        raise
    finally:
        session.close()

def main():
    """Función principal."""
    print("=" * 70)
    print("   INICIALIZACIÓN DE SISTEMA DE PRODUCTOS Y UBICACIONES")
    print("=" * 70)
    
    try:
        # Crear tablas
        engine = init_product_tables()
        
        # Preguntar si cargar datos de ejemplo
        print("\n¿Deseas cargar datos de ejemplo? (s/n): ", end="")
        response = input().strip().lower()
        
        if response in ['s', 'si', 'yes', 'y']:
            load_sample_data(engine)
        else:
            print("⏭️  Omitiendo carga de datos de ejemplo")
        
        # Verificar sistema
        verify_system(engine)
        
        print("\n" + "=" * 70)
        print("✅ Inicialización completada exitosamente")
        print("=" * 70)
        print("\n📚 Próximos pasos:")
        print("   1. Revisar las tablas creadas en la base de datos")
        print("   2. Consultar la documentación en PRODUCTS_API.md")
        print("   3. Implementar los endpoints de la API")
        print("   4. Iniciar el servidor: uvicorn src.main:app --reload")
        
    except Exception as e:
        print("\n" + "=" * 70)
        print(f"❌ ERROR: {e}")
        print("=" * 70)
        sys.exit(1)

if __name__ == "__main__":
    main()
