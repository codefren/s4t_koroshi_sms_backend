#!/usr/bin/env python3
"""
Script ETL para importar órdenes desde la VIEW de SQL Server.
Consulta la VIEW, detecta órdenes nuevas y las normaliza en la base de datos local.
"""

import sys
import json
from pathlib import Path
from datetime import datetime, date
from collections import defaultdict
from typing import Dict, List, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sqlalchemy.orm import Session
from src.adapters.secondary.database.config import SessionLocal
from src.adapters.secondary.database.orm import (
    OrderViewCache,
    OrderStatus,
    Operator,
    Order,
    OrderLine,
    OrderHistory,
    InventoryItemModel,  # La VIEW mapeada como InventoryItemModel
    ProductReference,
    ProductLocation
)


class OrderETL:
    """Clase para manejar el proceso ETL de órdenes."""
    
    def __init__(self, db: Session):
        self.db = db
        self.stats = {
            "total_rows": 0,
            "new_orders": 0,
            "skipped_orders": 0,
            "lines_created": 0,
            "lines_linked_product": 0,
            "lines_linked_location": 0,
            "errors": 0
        }
    
    def get_status_id(self, codigo: str) -> int:
        """Obtiene el ID de un estado por su código."""
        status = self.db.query(OrderStatus).filter_by(codigo=codigo).first()
        if not status:
            raise ValueError(f"Estado '{codigo}' no encontrado en la base de datos")
        return status.id
    
    def parse_date(self, date_str: str) -> date:
        """Parsea una fecha en formato string a date."""
        if not date_str:
            return date.today()
        
        # Intentar diferentes formatos
        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d"
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        # Si no se puede parsear, usar fecha actual
        print(f"⚠️  No se pudo parsear fecha '{date_str}', usando fecha actual")
        return date.today()
    
    def find_product_reference(self, ean: str, sku: str) -> ProductReference:
        """Busca un producto en el catálogo por EAN o SKU."""
        product = None
        
        # Estrategia 1: Match por EAN (más confiable)
        if ean and ean.strip():
            product = self.db.query(ProductReference).filter(
                ProductReference.ean == ean.strip()
            ).first()
        
        # Estrategia 2: Match por SKU
        if not product and sku and sku.strip():
            product = self.db.query(ProductReference).filter(
                ProductReference.sku == sku.strip()
            ).first()
        
        return product
    
    def find_best_location(self, product_id: int) -> ProductLocation:
        """Busca la mejor ubicación disponible para un producto."""
        # Criterios: activa, prioridad alta, stock disponible
        location = self.db.query(ProductLocation).filter(
            ProductLocation.product_id == product_id,
            ProductLocation.activa == True
        ).order_by(
            ProductLocation.prioridad.asc(),
            ProductLocation.stock_actual.desc()
        ).first()
        
        return location
    
    def fetch_view_data(self) -> List[Dict[str, Any]]:
        """
        Consulta la VIEW de SQL Server y retorna los datos.
        
        En producción, esto consultaría directamente la VIEW via ODBC.
        Por ahora, consulta la tabla InventoryItemModel como ejemplo.
        """
        print("📡 Consultando VIEW de SQL Server...")
        
        try:
            # Query a la VIEW (InventoryItemModel mapea la VIEW)
            rows = self.db.query(InventoryItemModel).all()
            self.stats["total_rows"] = len(rows)
            
            print(f"✅ Se obtuvieron {len(rows)} filas de la VIEW")
            
            # Convertir a diccionarios
            data = []
            for row in rows:
                data.append({
                    "ean": row.ean,
                    "ubicación": row.ubicacion,
                    "articulo": row.articulo,
                    "color": row.color,
                    "talla": row.talla,
                    "posiciontalla": row.posicion_talla,
                    "descripcion producto": row.descripcion_producto,
                    "descripcion color": row.descripcion_color,
                    "temporada": row.temporada,
                    "no.orden": row.numero_orden,
                    "cliente": row.cliente,
                    "nombre cliente": row.nombre_cliente,
                    "cantidad": row.cantidad,
                    "servida": row.servida,
                    "operario": row.operario,
                    "status": row.status,
                    "fecha": row.fecha,
                    "hora": row.hora,
                    "caja": row.caja,
                })
            
            return data
            
        except Exception as e:
            print(f"❌ Error al consultar VIEW: {e}")
            raise
    
    def cache_view_data(self, rows: List[Dict[str, Any]]) -> List[str]:
        """
        Guarda los datos de la VIEW en la tabla de caché.
        Retorna lista de numero_orden nuevos.
        """
        print("\n💾 Cacheando datos de la VIEW...")
        
        nuevos_numeros_orden = []
        
        for row in rows:
            numero_orden = row.get("no.orden")
            if not numero_orden:
                continue
            
            # Verificar si ya existe en cache
            existing = self.db.query(OrderViewCache).filter_by(
                numero_orden=numero_orden
            ).first()
            
            if not existing:
                # Nueva entrada en cache
                cache_entry = OrderViewCache(
                    numero_orden=numero_orden,
                    raw_data=row,
                    fecha_importacion=datetime.now(),
                    procesado=False
                )
                self.db.add(cache_entry)
                nuevos_numeros_orden.append(numero_orden)
        
        self.db.commit()
        print(f"✅ Cache actualizado. {len(nuevos_numeros_orden)} órdenes nuevas detectadas")
        
        return list(set(nuevos_numeros_orden))  # Eliminar duplicados
    
    def group_by_order(self, rows: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """Agrupa las filas por numero_orden."""
        grouped = defaultdict(list)
        
        for row in rows:
            numero_orden = row.get("no.orden")
            if numero_orden:
                grouped[numero_orden].append(row)
        
        return dict(grouped)
    
    def process_order(self, numero_orden: str, lines: List[Dict[str, Any]]) -> bool:
        """
        Procesa una orden: crea la orden y sus líneas.
        Retorna True si se procesó exitosamente.
        """
        try:
            # Verificar si la orden ya existe
            existing_order = self.db.query(Order).filter_by(
                numero_orden=numero_orden
            ).first()
            
            if existing_order:
                print(f"⏭️  Orden {numero_orden} ya existe, saltando...")
                self.stats["skipped_orders"] += 1
                return False
            
            # Tomar datos de la primera línea (son iguales en todas las líneas)
            first_line = lines[0]
            
            # Crear la orden
            order = Order(
                numero_orden=numero_orden,
                cliente=first_line.get("cliente", ""),
                nombre_cliente=first_line.get("nombre cliente"),
                status_id=self.get_status_id("PENDING"),
                fecha_orden=self.parse_date(first_line.get("fecha")),
                fecha_importacion=datetime.now(),
                total_items=len(lines),
                prioridad="NORMAL"
            )
            
            self.db.add(order)
            self.db.flush()  # Para obtener el order.id
            
            # Crear las líneas de la orden
            for line_data in lines:
                # Buscar producto en catálogo normalizado
                product = self.find_product_reference(
                    line_data.get("ean"),
                    line_data.get("articulo")
                )
                
                # Buscar mejor ubicación si se encontró el producto
                location = None
                ubicacion_str = line_data.get("ubicación")
                
                if product:
                    location = self.find_best_location(product.id)
                    # Usar ubicación real si existe
                    if location:
                        ubicacion_str = location.codigo_ubicacion
                
                order_line = OrderLine(
                    order_id=order.id,
                    
                    # === Referencias normalizadas ===
                    product_reference_id=product.id if product else None,
                    product_location_id=location.id if location else None,
                    
                    # === Datos mínimos ===
                    ean=line_data.get("ean"),  # Solo para match rápido
                    
                    # === Cantidades y estado ===
                    cantidad_solicitada=int(line_data.get("cantidad", 0)),
                    cantidad_servida=int(line_data.get("servida", 0)),
                    estado="PENDING"
                )
                self.db.add(order_line)
                self.stats["lines_created"] += 1
                
                # Actualizar contadores de vinculación
                if product:
                    self.stats["lines_linked_product"] += 1
                if location:
                    self.stats["lines_linked_location"] += 1
            
            # Crear entrada en historial
            history = OrderHistory(
                order_id=order.id,
                status_id=order.status_id,
                accion="IMPORTED_FROM_VIEW",
                fecha=datetime.now(),
                notas=f"Orden importada desde VIEW con {len(lines)} líneas",
                event_metadata={"source": "etl_import_orders.py"}
            )
            self.db.add(history)
            
            # Marcar como procesada en cache
            cache_entry = self.db.query(OrderViewCache).filter_by(
                numero_orden=numero_orden
            ).first()
            if cache_entry:
                cache_entry.procesado = True
            
            self.db.commit()
            self.stats["new_orders"] += 1
            
            print(f"✅ Orden {numero_orden} procesada: {len(lines)} líneas")
            return True
            
        except Exception as e:
            print(f"❌ Error procesando orden {numero_orden}: {e}")
            self.db.rollback()
            self.stats["errors"] += 1
            return False
    
    def run(self):
        """Ejecuta el proceso ETL completo."""
        print("="*60)
        print("🔄 PROCESO ETL - IMPORTACIÓN DE ÓRDENES")
        print("="*60)
        print()
        
        try:
            # Paso 1: Consultar VIEW
            rows = self.fetch_view_data()
            
            if not rows:
                print("ℹ️  No hay datos en la VIEW")
                return
            
            # Paso 2: Cachear datos
            nuevos_numeros_orden = self.cache_view_data(rows)
            
            if not nuevos_numeros_orden:
                print("\nℹ️  No hay órdenes nuevas para procesar")
                self.print_stats()
                return
            
            # Paso 3: Agrupar por orden
            print(f"\n📦 Procesando {len(nuevos_numeros_orden)} órdenes nuevas...")
            grouped = self.group_by_order(rows)
            
            # Paso 4: Procesar cada orden
            for numero_orden in nuevos_numeros_orden:
                if numero_orden in grouped:
                    self.process_order(numero_orden, grouped[numero_orden])
            
            # Paso 5: Estadísticas
            self.print_stats()
            
        except Exception as e:
            print(f"\n❌ Error en proceso ETL: {e}")
            raise
    
    def print_stats(self):
        """Imprime estadísticas del proceso."""
        print("\n" + "="*60)
        print("📊 ESTADÍSTICAS DEL PROCESO ETL")
        print("="*60)
        print(f"Filas consultadas:       {self.stats['total_rows']}")
        print(f"Órdenes nuevas:          {self.stats['new_orders']}")
        print(f"Órdenes saltadas:        {self.stats['skipped_orders']}")
        print(f"Líneas creadas:          {self.stats['lines_created']}")
        
        # Estadísticas de vinculación con productos
        if self.stats['lines_created'] > 0:
            link_rate = (self.stats['lines_linked_product'] / self.stats['lines_created']) * 100
            loc_rate = (self.stats['lines_linked_location'] / self.stats['lines_created']) * 100
            print(f"\n🔗 Vinculación con catálogo:")
            print(f"  - Con productos:       {self.stats['lines_linked_product']} ({link_rate:.1f}%)")
            print(f"  - Con ubicaciones:     {self.stats['lines_linked_location']} ({loc_rate:.1f}%)")
        
        print(f"\nErrores:                 {self.stats['errors']}")
        print("="*60)
        
        if self.stats["new_orders"] > 0:
            print(f"\n✅ {self.stats['new_orders']} órdenes importadas exitosamente")
        
        if self.stats["errors"] > 0:
            print(f"\n⚠️  Proceso completado con {self.stats['errors']} errores")


def main():
    """Función principal."""
    db = SessionLocal()
    
    try:
        etl = OrderETL(db)
        etl.run()
        
        print("\n💡 Las órdenes importadas están en estado PENDING")
        print("   Siguiente paso: Asignar órdenes a operarios")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    exit(main())
