"""
Script de migración para vincular order_lines con product_references y product_locations.

Este script:
1. Busca todas las order_lines que NO tienen product_reference_id
2. Intenta hacer match con productos del catálogo usando:
   - EAN (más confiable)
   - SKU/artículo
   - Nombre + talla + color (menos confiable)
3. Asigna la mejor ubicación disponible basándose en prioridad y stock
4. Genera reporte de líneas vinculadas y no vinculadas

Uso:
    python migrate_orders_to_products.py
"""

import sys
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

# Add src to path
sys.path.append('.')

from src.adapters.secondary.database.config import SessionLocal
from src.adapters.secondary.database.orm import (
    OrderLine,
    ProductReference,
    ProductLocation
)


def migrate_order_lines_to_products(db: Session, dry_run: bool = False):
    """
    Vincula order_lines existentes con product_references.
    
    Args:
        db: Sesión de base de datos
        dry_run: Si es True, no hace commit (solo muestra qué pasaría)
    
    Returns:
        Dict con estadísticas de la migración
    """
    print("=" * 80)
    print("MIGRACIÓN: Vincular OrderLines con ProductReferences")
    print("=" * 80)
    print()
    
    # Obtener todas las order_lines sin vincular
    unlinked_lines = db.query(OrderLine).filter(
        OrderLine.product_reference_id == None
    ).all()
    
    total = len(unlinked_lines)
    print(f"📊 Total de líneas sin vincular: {total}")
    
    if total == 0:
        print("✅ No hay líneas para migrar. Todo está vinculado.")
        return {
            "total_lines": 0,
            "matched": 0,
            "unmatched": 0,
            "success_rate": 100.0
        }
    
    print()
    print("🔄 Iniciando proceso de vinculación...")
    print()
    
    matched = 0
    unmatched = []
    match_methods = {
        "ean": 0,
        "sku": 0,
        "name": 0
    }
    
    for idx, line in enumerate(unlinked_lines, 1):
        product = None
        match_method = None
        
        # Estrategia 1: Match por EAN (más confiable)
        if line.ean and line.ean.strip():
            product = db.query(ProductReference).filter(
                ProductReference.ean == line.ean.strip()
            ).first()
            if product:
                match_method = "ean"
        
        # Estrategia 2: Match por SKU/artículo
        if not product and line.articulo and line.articulo.strip():
            product = db.query(ProductReference).filter(
                func.lower(ProductReference.sku) == func.lower(line.articulo.strip())
            ).first()
            if product:
                match_method = "sku"
        
        # Estrategia 3: Match por nombre + talla + color (menos confiable)
        if not product and line.descripcion_producto and line.talla:
            # Buscar por nombre similar
            search_term = f"%{line.descripcion_producto[:30]}%"
            candidates = db.query(ProductReference).filter(
                ProductReference.nombre_producto.like(search_term),
                ProductReference.talla == line.talla
            ).all()
            
            # Si hay color, filtrar más
            if candidates and line.descripcion_color:
                color_filtered = [
                    c for c in candidates 
                    if c.descripcion_color and line.descripcion_color.lower() in c.descripcion_color.lower()
                ]
                if color_filtered:
                    product = color_filtered[0]
                    match_method = "name"
        
        if product:
            # Asignar product_reference_id
            line.product_reference_id = product.id
            
            # Buscar mejor ubicación para este producto
            # Criterios: activa, prioridad alta, stock disponible
            location = db.query(ProductLocation).filter(
                ProductLocation.product_id == product.id,
                ProductLocation.activa == True
            ).order_by(
                ProductLocation.prioridad.asc(),
                ProductLocation.stock_actual.desc()
            ).first()
            
            if location:
                line.product_location_id = location.id
                # Actualizar ubicación con el código real
                line.ubicacion = location.codigo_ubicacion
            
            matched += 1
            match_methods[match_method] += 1
            
            if idx % 100 == 0:
                print(f"  Procesadas {idx}/{total} líneas... ({matched} vinculadas)")
        
        else:
            unmatched.append({
                "order_line_id": line.id,
                "order_id": line.order_id,
                "ean": line.ean,
                "articulo": line.articulo,
                "descripcion": line.descripcion_producto[:50] if line.descripcion_producto else None,
                "talla": line.talla,
                "color": line.descripcion_color[:30] if line.descripcion_color else None
            })
    
    success_rate = (matched / total * 100) if total > 0 else 0
    
    print()
    print("=" * 80)
    print("📊 RESULTADOS DE LA MIGRACIÓN")
    print("=" * 80)
    print(f"Total de líneas procesadas: {total}")
    print(f"✅ Vinculadas exitosamente:  {matched} ({success_rate:.1f}%)")
    print(f"❌ Sin vincular:             {len(unmatched)} ({100-success_rate:.1f}%)")
    print()
    print("Métodos de vinculación:")
    print(f"  - Por EAN:    {match_methods['ean']} ({match_methods['ean']/matched*100:.1f}%)" if matched > 0 else "  - Por EAN: 0")
    print(f"  - Por SKU:    {match_methods['sku']} ({match_methods['sku']/matched*100:.1f}%)" if matched > 0 else "  - Por SKU: 0")
    print(f"  - Por Nombre: {match_methods['name']} ({match_methods['name']/matched*100:.1f}%)" if matched > 0 else "  - Por Nombre: 0")
    print()
    
    if unmatched:
        print("❌ Líneas sin vincular (primeras 10):")
        for item in unmatched[:10]:
            print(f"  - OrderLine #{item['order_line_id']} | EAN: {item['ean']} | SKU: {item['articulo']} | {item['descripcion']}")
        if len(unmatched) > 10:
            print(f"  ... y {len(unmatched) - 10} más")
        print()
    
    if dry_run:
        print("⚠️  DRY RUN: No se hizo commit. Los cambios NO se guardaron.")
        db.rollback()
    else:
        db.commit()
        print("✅ Cambios guardados en la base de datos.")
    
    print()
    
    return {
        "total_lines": total,
        "matched": matched,
        "unmatched": len(unmatched),
        "success_rate": success_rate,
        "match_methods": match_methods,
        "unmatched_details": unmatched
    }


def generate_report(results: dict, output_file: str = "migration_report.txt"):
    """Genera un reporte detallado de la migración."""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("REPORTE DE MIGRACIÓN - OrderLines a ProductReferences\n")
        f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"Total procesadas:  {results['total_lines']}\n")
        f.write(f"Vinculadas:        {results['matched']} ({results['success_rate']:.1f}%)\n")
        f.write(f"Sin vincular:      {results['unmatched']}\n\n")
        
        f.write("Métodos de vinculación:\n")
        for method, count in results['match_methods'].items():
            f.write(f"  - {method.upper()}: {count}\n")
        f.write("\n")
        
        if results['unmatched_details']:
            f.write("=" * 80 + "\n")
            f.write("LÍNEAS SIN VINCULAR (DETALLE COMPLETO)\n")
            f.write("=" * 80 + "\n\n")
            for item in results['unmatched_details']:
                f.write(f"OrderLine ID: {item['order_line_id']}\n")
                f.write(f"Order ID:     {item['order_id']}\n")
                f.write(f"EAN:          {item['ean']}\n")
                f.write(f"SKU:          {item['articulo']}\n")
                f.write(f"Descripción:  {item['descripcion']}\n")
                f.write(f"Talla:        {item['talla']}\n")
                f.write(f"Color:        {item['color']}\n")
                f.write("-" * 80 + "\n")
    
    print(f"📄 Reporte detallado guardado en: {output_file}")


def validate_migration(db: Session):
    """Valida el resultado de la migración con queries SQL."""
    print()
    print("=" * 80)
    print("🔍 VALIDACIÓN POST-MIGRACIÓN")
    print("=" * 80)
    print()
    
    # 1. Estadísticas generales
    total_lines = db.query(OrderLine).count()
    with_product = db.query(OrderLine).filter(OrderLine.product_reference_id != None).count()
    with_location = db.query(OrderLine).filter(OrderLine.product_location_id != None).count()
    
    print(f"Total OrderLines:                {total_lines}")
    print(f"Con ProductReference:            {with_product} ({with_product/total_lines*100:.1f}%)")
    print(f"Con ProductLocation:             {with_location} ({with_location/total_lines*100:.1f}%)")
    print()
    
    # 2. Órdenes más recientes
    recent_orders = db.query(
        OrderLine.order_id,
        func.count(OrderLine.id).label('total_lines'),
        func.count(OrderLine.product_reference_id).label('linked_lines')
    ).group_by(OrderLine.order_id).limit(5).all()
    
    print("Órdenes más recientes:")
    for order_id, total, linked in recent_orders:
        print(f"  Order #{order_id}: {linked}/{total} líneas vinculadas ({linked/total*100:.0f}%)")
    print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrar OrderLines a ProductReferences')
    parser.add_argument('--dry-run', action='store_true', help='Ejecutar sin hacer commit')
    parser.add_argument('--report', action='store_true', help='Generar reporte detallado')
    parser.add_argument('--validate', action='store_true', help='Solo validar (no migrar)')
    
    args = parser.parse_args()
    
    db = SessionLocal()
    
    try:
        if args.validate:
            validate_migration(db)
        else:
            results = migrate_order_lines_to_products(db, dry_run=args.dry_run)
            
            if args.report:
                generate_report(results)
            
            if not args.dry_run:
                validate_migration(db)
    
    except Exception as e:
        print(f"❌ Error durante la migración: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    
    finally:
        db.close()
