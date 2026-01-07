#!/usr/bin/env python3
"""
Script para recrear órdenes con productos y ubicaciones vinculadas.

Borra todas las órdenes actuales y crea nuevas órdenes de prueba
que ya están vinculadas con productos y ubicaciones reales del catálogo.

Uso:
    python recreate_orders_with_products.py
    python recreate_orders_with_products.py --num-orders 10
"""

import sys
import random
from datetime import datetime, date, timedelta

sys.path.append('.')

from sqlalchemy import text
from src.adapters.secondary.database.config import SessionLocal
from src.adapters.secondary.database.orm import (
    Order,
    OrderLine,
    OrderHistory,
    OrderViewCache,
    OrderStatus,
    ProductReference,
    ProductLocation
)


def clean_orders(db):
    """Borra todas las órdenes existentes."""
    print("🗑️  Limpiando órdenes existentes...")
    
    try:
        # Borrar en orden (por las FKs)
        db.query(OrderHistory).delete()
        print("   - OrderHistory limpiado")
        
        db.query(OrderLine).delete()
        print("   - OrderLine limpiado")
        
        db.query(Order).delete()
        print("   - Order limpiado")
        
        db.query(OrderViewCache).delete()
        print("   - OrderViewCache limpiado")
        
        db.commit()
        print("✅ Órdenes eliminadas exitosamente\n")
        return True
    
    except Exception as e:
        print(f"❌ Error limpiando órdenes: {e}")
        db.rollback()
        return False


def get_random_products(db, count=5):
    """Obtiene productos aleatorios con ubicaciones."""
    products = db.query(ProductReference).filter(
        ProductReference.activo == True
    ).all()
    
    if not products:
        print("⚠️  No hay productos en el catálogo")
        return []
    
    selected = random.sample(products, min(count, len(products)))
    
    result = []
    for product in selected:
        # Obtener ubicación activa del producto
        location = db.query(ProductLocation).filter(
            ProductLocation.product_id == product.id,
            ProductLocation.activa == True
        ).order_by(ProductLocation.prioridad.asc()).first()
        
        if location:
            result.append({
                'product': product,
                'location': location
            })
    
    return result


def create_orders(db, num_orders=5):
    """Crea órdenes nuevas vinculadas con productos."""
    print(f"📦 Creando {num_orders} órdenes nuevas...\n")
    
    # Obtener estado PENDING
    pending_status = db.query(OrderStatus).filter_by(codigo="PENDING").first()
    if not pending_status:
        print("❌ Estado PENDING no encontrado. Ejecuta init_order_system.py primero")
        return False
    
    clientes = [
        ("C001", "Tienda Centro"),
        ("C002", "Tienda Norte"),
        ("C003", "Tienda Sur"),
        ("C004", "Boutique Fashion"),
        ("C005", "Store Elite")
    ]
    
    prioridades = ["NORMAL", "HIGH", "URGENT"]
    
    created_count = 0
    
    for i in range(num_orders):
        try:
            # Datos aleatorios
            cliente_code, cliente_name = random.choice(clientes)
            prioridad = random.choice(prioridades)
            fecha_orden = date.today() - timedelta(days=random.randint(0, 7))
            
            # Obtener productos aleatorios (3-8 productos por orden)
            num_productos = random.randint(3, 8)
            productos = get_random_products(db, num_productos)
            
            if not productos:
                print(f"⚠️  Orden {i+1}: No hay productos disponibles, saltando...")
                continue
            
            # Crear orden
            numero_orden = f"ORD{1000 + i:04d}"
            
            order = Order(
                numero_orden=numero_orden,
                cliente=cliente_code,
                nombre_cliente=cliente_name,
                status_id=pending_status.id,
                fecha_orden=fecha_orden,
                fecha_importacion=datetime.now(),
                total_items=len(productos),
                items_completados=0,
                prioridad=prioridad
            )
            
            db.add(order)
            db.flush()  # Para obtener order.id
            
            # Crear líneas de orden vinculadas con productos
            for item in productos:
                product = item['product']
                location = item['location']
                
                cantidad = random.randint(2, 10)
                
                order_line = OrderLine(
                    order_id=order.id,
                    
                    # === REFERENCIAS VINCULADAS (normalizadas) ===
                    product_reference_id=product.id,
                    product_location_id=location.id,
                    
                    # === DATOS MÍNIMOS ===
                    ean=product.ean,  # Solo para match rápido
                    
                    # === CANTIDADES Y ESTADO ===
                    cantidad_solicitada=cantidad,
                    cantidad_servida=0,
                    estado="PENDING"
                )
                
                db.add(order_line)
            
            # Crear entrada en historial
            history = OrderHistory(
                order_id=order.id,
                status_id=pending_status.id,
                accion="CREATED",
                fecha=datetime.now(),
                notas=f"Orden creada con {len(productos)} productos vinculados",
                event_metadata={
                    "source": "recreate_orders_with_products.py",
                    "vinculado": True
                }
            )
            db.add(history)
            
            db.commit()
            created_count += 1
            
            print(f"✅ Orden {numero_orden} creada:")
            print(f"   - Cliente: {cliente_name}")
            print(f"   - Productos: {len(productos)}")
            print(f"   - Prioridad: {prioridad}")
            print(f"   - 100% vinculado con catálogo")
            print()
        
        except Exception as e:
            print(f"❌ Error creando orden {i+1}: {e}")
            db.rollback()
    
    return created_count


def verify_linkage(db):
    """Verifica el % de vinculación."""
    print("\n" + "=" * 60)
    print("📊 VERIFICANDO VINCULACIÓN")
    print("=" * 60)
    
    total_lines = db.query(OrderLine).count()
    
    if total_lines == 0:
        print("⚠️  No hay líneas de orden")
        return
    
    with_product = db.query(OrderLine).filter(
        OrderLine.product_reference_id != None
    ).count()
    
    with_location = db.query(OrderLine).filter(
        OrderLine.product_location_id != None
    ).count()
    
    product_rate = (with_product / total_lines * 100)
    location_rate = (with_location / total_lines * 100)
    
    print(f"Total líneas:           {total_lines}")
    print(f"Con product_reference:  {with_product} ({product_rate:.1f}%)")
    print(f"Con product_location:   {with_location} ({location_rate:.1f}%)")
    print()
    
    if product_rate == 100 and location_rate == 100:
        print("✅ 100% de vinculación - PERFECTO!")
    else:
        print("⚠️  Vinculación incompleta")
    
    print("=" * 60)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Recrear órdenes con productos vinculados'
    )
    parser.add_argument(
        '--num-orders',
        type=int,
        default=10,
        help='Número de órdenes a crear (default: 10)'
    )
    parser.add_argument(
        '--skip-clean',
        action='store_true',
        help='No borrar órdenes existentes (solo crear nuevas)'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔄 RECREAR ÓRDENES CON PRODUCTOS VINCULADOS")
    print("=" * 60)
    print()
    
    db = SessionLocal()
    
    try:
        # Paso 1: Limpiar órdenes existentes
        if not args.skip_clean:
            if not clean_orders(db):
                return 1
        else:
            print("⏭️  Saltando limpieza (--skip-clean)\n")
        
        # Paso 2: Crear nuevas órdenes
        created = create_orders(db, args.num_orders)
        
        if created == 0:
            print("\n❌ No se creó ninguna orden")
            print("\nPosibles causas:")
            print("  1. No hay productos en el catálogo")
            print("     Solución: python seed_products.py")
            print("  2. No hay ubicaciones activas")
            print("     Solución: Crear ubicaciones para los productos")
            return 1
        
        print(f"\n✅ {created} órdenes creadas exitosamente")
        
        # Paso 3: Verificar vinculación
        verify_linkage(db)
        
        print("\n📋 Próximos pasos:")
        print("  1. Iniciar API: uvicorn src.main:app --reload")
        print("  2. Ver órdenes: http://localhost:8000/docs")
        print("  3. Probar optimización: POST /api/v1/orders/1/optimize-picking-route")
        print("  4. Validar stock: GET /api/v1/orders/1/stock-validation")
        print()
        
        return 0
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1
    
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
