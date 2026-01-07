#!/usr/bin/env python3
"""
Script para verificar el estado del sistema de órdenes.
Muestra estadísticas, estados de órdenes y diagnósticos.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sqlalchemy import func, text
from src.adapters.secondary.database.config import SessionLocal
from src.adapters.secondary.database.orm import (
    OrderViewCache,
    OrderStatus,
    Operator,
    Order,
    OrderLine,
    OrderHistory,
    PickingTask
)


def print_header(title: str):
    """Imprime un header formateado."""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def check_tables():
    """Verifica que todas las tablas existan y muestra conteo."""
    print_header("📊 ESTADO DE LAS TABLAS")
    
    db = SessionLocal()
    
    try:
        tables = [
            ("Caché de VIEW", OrderViewCache),
            ("Estados", OrderStatus),
            ("Operarios", Operator),
            ("Órdenes", Order),
            ("Líneas de Orden", OrderLine),
            ("Historial", OrderHistory),
            ("Tareas de Picking", PickingTask),
        ]
        
        print(f"\n{'Tabla':<25} {'Registros':>15} {'Estado'}")
        print("-" * 70)
        
        all_ok = True
        for name, model in tables:
            try:
                count = db.query(model).count()
                status = "✅ OK" if count >= 0 else "⚠️"
                print(f"{name:<25} {count:>15,} {status}")
            except Exception as e:
                print(f"{name:<25} {'ERROR':>15} ❌")
                print(f"  Error: {e}")
                all_ok = False
        
        return all_ok
        
    finally:
        db.close()


def check_order_statuses():
    """Verifica los estados de órdenes."""
    print_header("🏷️  ESTADOS DE ÓRDENES")
    
    db = SessionLocal()
    
    try:
        statuses = db.query(OrderStatus).order_by(OrderStatus.orden).all()
        
        if not statuses:
            print("\n⚠️  No hay estados configurados. Ejecuta: python init_order_system.py")
            return False
        
        print(f"\n{'Orden':<8} {'Código':<15} {'Nombre':<25} {'Activo':<8} {'Órdenes'}")
        print("-" * 70)
        
        for status in statuses:
            order_count = db.query(Order).filter_by(status_id=status.id).count()
            active = "✅ Sí" if status.activo else "❌ No"
            print(f"{status.orden:<8} {status.codigo:<15} {status.nombre:<25} {active:<8} {order_count:>6}")
        
        return True
        
    finally:
        db.close()


def check_operators():
    """Verifica operarios del sistema."""
    print_header("👷 OPERARIOS")
    
    db = SessionLocal()
    
    try:
        operators = db.query(Operator).all()
        
        if not operators:
            print("\n⚠️  No hay operarios registrados.")
            return True
        
        print(f"\n{'Código':<12} {'Nombre':<30} {'Activo':<10} {'Órdenes':<10} {'Tareas'}")
        print("-" * 70)
        
        for op in operators:
            orders_count = db.query(Order).filter_by(operator_id=op.id).count()
            tasks_count = db.query(PickingTask).filter_by(operator_id=op.id).count()
            active = "✅ Activo" if op.activo else "❌ Inactivo"
            
            print(f"{op.codigo_operario:<12} {op.nombre:<30} {active:<10} {orders_count:<10} {tasks_count}")
        
        return True
        
    finally:
        db.close()


def check_recent_orders():
    """Muestra órdenes recientes."""
    print_header("📦 ÓRDENES RECIENTES (Últimas 10)")
    
    db = SessionLocal()
    
    try:
        orders = db.query(Order)\
            .order_by(Order.created_at.desc())\
            .limit(10)\
            .all()
        
        if not orders:
            print("\n⚠️  No hay órdenes en el sistema.")
            print("   Ejecuta: python etl_import_orders.py")
            return True
        
        print(f"\n{'No. Orden':<15} {'Cliente':<20} {'Estado':<15} {'Items':<8} {'Operario'}")
        print("-" * 70)
        
        for order in orders:
            status_name = db.query(OrderStatus).filter_by(id=order.status_id).first().nombre
            operator_name = ""
            if order.operator_id:
                op = db.query(Operator).filter_by(id=order.operator_id).first()
                operator_name = op.nombre if op else "N/A"
            
            items_info = f"{order.items_completados}/{order.total_items}"
            print(f"{order.numero_orden:<15} {order.cliente:<20} {status_name:<15} {items_info:<8} {operator_name}")
        
        return True
        
    finally:
        db.close()


def check_pending_orders():
    """Muestra órdenes pendientes de asignación."""
    print_header("⏳ ÓRDENES PENDIENTES DE ASIGNACIÓN")
    
    db = SessionLocal()
    
    try:
        pending_status = db.query(OrderStatus).filter_by(codigo="PENDING").first()
        
        if not pending_status:
            print("\n⚠️  Estado PENDING no encontrado")
            return False
        
        pending_orders = db.query(Order)\
            .filter_by(status_id=pending_status.id)\
            .order_by(Order.fecha_orden.asc())\
            .all()
        
        if not pending_orders:
            print("\n✅ No hay órdenes pendientes")
            return True
        
        print(f"\nTotal: {len(pending_orders)} órdenes")
        print(f"\n{'No. Orden':<15} {'Cliente':<25} {'Fecha':<12} {'Items':<8} {'Días'}")
        print("-" * 70)
        
        for order in pending_orders[:20]:  # Mostrar solo primeras 20
            days_old = (datetime.now().date() - order.fecha_orden).days
            print(f"{order.numero_orden:<15} {order.nombre_cliente or order.cliente:<25} "
                  f"{order.fecha_orden.strftime('%Y-%m-%d'):<12} {order.total_items:<8} {days_old}")
        
        if len(pending_orders) > 20:
            print(f"\n... y {len(pending_orders) - 20} órdenes más")
        
        return True
        
    finally:
        db.close()


def check_active_picking():
    """Muestra picking activo."""
    print_header("🔄 PICKING EN PROCESO")
    
    db = SessionLocal()
    
    try:
        in_picking_status = db.query(OrderStatus).filter_by(codigo="IN_PICKING").first()
        
        if not in_picking_status:
            print("\n⚠️  Estado IN_PICKING no encontrado")
            return False
        
        active_orders = db.query(Order)\
            .filter_by(status_id=in_picking_status.id)\
            .all()
        
        if not active_orders:
            print("\n✅ No hay picking en proceso")
            return True
        
        print(f"\nTotal: {len(active_orders)} órdenes")
        print(f"\n{'No. Orden':<15} {'Operario':<25} {'Progreso':<15} {'Inicio'}")
        print("-" * 70)
        
        for order in active_orders:
            operator = db.query(Operator).filter_by(id=order.operator_id).first()
            operator_name = operator.nombre if operator else "N/A"
            
            progress = f"{order.items_completados}/{order.total_items}"
            percent = int((order.items_completados / order.total_items * 100)) if order.total_items > 0 else 0
            progress_bar = f"{progress} ({percent}%)"
            
            inicio = order.fecha_inicio_picking.strftime('%H:%M') if order.fecha_inicio_picking else "N/A"
            
            print(f"{order.numero_orden:<15} {operator_name:<25} {progress_bar:<15} {inicio}")
        
        return True
        
    finally:
        db.close()


def check_cache_status():
    """Verifica estado del caché de la VIEW."""
    print_header("💾 ESTADO DEL CACHÉ")
    
    db = SessionLocal()
    
    try:
        total = db.query(OrderViewCache).count()
        procesados = db.query(OrderViewCache).filter_by(procesado=True).count()
        pendientes = total - procesados
        
        print(f"\nTotal en caché:      {total:>10,}")
        print(f"Procesados:          {procesados:>10,}")
        print(f"Pendientes:          {pendientes:>10,}")
        
        if pendientes > 0:
            print(f"\n⚠️  Hay {pendientes} órdenes en caché sin procesar")
            print("   Ejecuta: python etl_import_orders.py")
        else:
            print("\n✅ Todos los registros del caché han sido procesados")
        
        # Última importación
        last_import = db.query(OrderViewCache)\
            .order_by(OrderViewCache.fecha_importacion.desc())\
            .first()
        
        if last_import:
            print(f"\nÚltima importación:  {last_import.fecha_importacion.strftime('%Y-%m-%d %H:%M:%S')}")
            hours_ago = (datetime.now() - last_import.fecha_importacion).total_seconds() / 3600
            print(f"Hace:                {hours_ago:.1f} horas")
        
        return True
        
    finally:
        db.close()


def check_system_health():
    """Verifica salud general del sistema."""
    print_header("🏥 SALUD DEL SISTEMA")
    
    db = SessionLocal()
    
    try:
        issues = []
        
        # 1. Estados configurados
        status_count = db.query(OrderStatus).count()
        if status_count < 8:
            issues.append(f"⚠️  Solo {status_count} estados configurados (se esperan 8)")
        
        # 2. Órdenes sin operario asignado hace más de 24h
        yesterday = datetime.now() - timedelta(days=1)
        old_pending = db.query(Order).join(OrderStatus)\
            .filter(OrderStatus.codigo == "PENDING")\
            .filter(Order.created_at < yesterday)\
            .count()
        
        if old_pending > 0:
            issues.append(f"⚠️  {old_pending} órdenes pendientes de más de 24 horas")
        
        # 3. Picking tasks estancadas
        stalled_tasks = db.query(PickingTask)\
            .filter(PickingTask.estado == "IN_PROGRESS")\
            .filter(PickingTask.fecha_inicio < yesterday)\
            .count()
        
        if stalled_tasks > 0:
            issues.append(f"⚠️  {stalled_tasks} tareas de picking en progreso por más de 24h")
        
        # 4. Operarios activos
        active_operators = db.query(Operator).filter_by(activo=True).count()
        if active_operators == 0:
            issues.append("⚠️  No hay operarios activos")
        
        # Mostrar resultados
        if issues:
            print("\n🔴 Problemas detectados:")
            for issue in issues:
                print(f"  {issue}")
        else:
            print("\n✅ Sistema en buen estado")
        
        # Métricas generales
        print("\n📈 Métricas:")
        print(f"  Total de órdenes:        {db.query(Order).count():>6,}")
        print(f"  Órdenes completadas:     {db.query(Order).join(OrderStatus).filter(OrderStatus.codigo.in_(['SHIPPED', 'READY'])).count():>6,}")
        print(f"  Operarios activos:       {active_operators:>6,}")
        print(f"  Tareas de picking:       {db.query(PickingTask).count():>6,}")
        
        return len(issues) == 0
        
    finally:
        db.close()


def main():
    """Función principal."""
    print("="*70)
    print("  🔍 DIAGNÓSTICO DEL SISTEMA DE ÓRDENES")
    print("="*70)
    print(f"\n  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    checks = [
        ("Tablas", check_tables),
        ("Estados", check_order_statuses),
        ("Operarios", check_operators),
        ("Órdenes Recientes", check_recent_orders),
        ("Órdenes Pendientes", check_pending_orders),
        ("Picking Activo", check_active_picking),
        ("Caché", check_cache_status),
        ("Salud del Sistema", check_system_health),
    ]
    
    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"\n❌ Error en {name}: {e}")
            results[name] = False
    
    # Resumen final
    print_header("📋 RESUMEN")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\nChecks pasados: {passed}/{total}")
    
    if passed == total:
        print("\n✅ Todos los checks pasaron exitosamente")
        return 0
    else:
        print(f"\n⚠️  {total - passed} checks fallaron")
        return 1


if __name__ == "__main__":
    exit(main())
