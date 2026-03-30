"""
Script de migración para importar ubicaciones de productos desde CSV.

Formato CSV esperado (separado por punto y coma):
sku;pasillo;ubicacion;stock_actual

Ejemplo:
2612JA04-000015-L;01;013/015;22
2612JA04-000015-S;01;013/015;9
2611ZT07-000323-L;01;024;507

El script:
1. Lee el CSV línea por línea
2. Busca el producto por SKU en product_references
3. Crea o actualiza la ubicación en product_locations para el almacén de picking
4. Actualiza el stock_actual
5. Genera reporte de éxitos y errores

Uso:
    python scripts/import_ubicaciones_csv.py ubicaciones.csv
"""

import sys
import csv
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session

# Agregar el directorio raíz al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.secondary.database.config import SessionLocal, ALMACEN_PICKING_ID
from src.adapters.secondary.database.orm import ProductReference, ProductLocation, Almacen


class UbicacionImporter:
    def __init__(self, csv_file_path: str, almacen_id: int = ALMACEN_PICKING_ID):
        self.csv_file_path = Path(csv_file_path)
        self.almacen_id = almacen_id
        self.db: Session = SessionLocal()
        
        # Contadores
        self.total_lines = 0
        self.success_count = 0
        self.created_count = 0
        self.updated_count = 0
        self.error_count = 0
        self.errors = []
        
    def validate_csv_file(self) -> bool:
        """Valida que el archivo CSV existe y es accesible."""
        if not self.csv_file_path.exists():
            print(f"❌ ERROR: Archivo no encontrado: {self.csv_file_path}")
            return False
        
        if not self.csv_file_path.is_file():
            print(f"❌ ERROR: La ruta no es un archivo: {self.csv_file_path}")
            return False
        
        return True
    
    def validate_almacen(self) -> bool:
        """Valida que el almacén existe en la base de datos."""
        almacen = self.db.query(Almacen).filter(Almacen.id == self.almacen_id).first()
        if not almacen:
            print(f"❌ ERROR: Almacén con ID {self.almacen_id} no encontrado en la base de datos")
            return False
        
        print(f"✅ Almacén destino: ID={almacen.id}, Código={almacen.codigo}, Descripción={almacen.descripciones}")
        return True
    
    def parse_csv_line(self, row: dict, line_num: int) -> dict:
        """
        Parsea una línea del CSV y extrae los campos necesarios.
        
        Returns:
            dict con campos: sku, pasillo, ubicacion, stock_actual
            None si hay error de parsing
        """
        try:
            sku = row.get('sku', '').strip()
            pasillo = row.get('pasillo', '').strip()
            ubicacion = row.get('ubicacion', '').strip()
            stock_str = row.get('stock_actual', '').strip()
            
            # Validar campos obligatorios
            if not sku:
                self.errors.append(f"Línea {line_num}: SKU vacío")
                return None
            
            if not pasillo:
                self.errors.append(f"Línea {line_num}: Pasillo vacío para SKU {sku}")
                return None
            
            if not ubicacion:
                self.errors.append(f"Línea {line_num}: Ubicación vacía para SKU {sku}")
                return None
            
            # Parsear stock (puede ser 0)
            try:
                stock_actual = int(stock_str) if stock_str else 0
            except ValueError:
                self.errors.append(f"Línea {line_num}: Stock inválido '{stock_str}' para SKU {sku}")
                return None
            
            return {
                'sku': sku,
                'pasillo': pasillo,
                'ubicacion': ubicacion,
                'stock_actual': stock_actual
            }
        
        except Exception as e:
            self.errors.append(f"Línea {line_num}: Error de parsing - {str(e)}")
            return None
    
    def find_product_by_sku(self, sku: str) -> ProductReference:
        """Busca un producto por SKU en la base de datos."""
        return self.db.query(ProductReference).filter(
            ProductReference.sku == sku
        ).first()
    
    def find_or_create_location(self, product_id: int, pasillo: str, ubicacion: str) -> tuple[ProductLocation, bool]:
        """
        Busca o crea una ubicación para el producto en el almacén.
        
        Returns:
            tuple (ProductLocation, is_new)
            - ProductLocation: la ubicación encontrada o creada
            - is_new: True si se creó, False si ya existía
        """
        # Buscar ubicación existente
        existing = self.db.query(ProductLocation).filter(
            ProductLocation.almacen_id == self.almacen_id,
            ProductLocation.product_id == product_id,
            ProductLocation.pasillo == pasillo,
            ProductLocation.ubicacion == ubicacion
        ).first()
        
        if existing:
            return existing, False
        
        # Crear nueva ubicación
        new_location = ProductLocation(
            almacen_id=self.almacen_id,
            product_id=product_id,
            pasillo=pasillo,
            ubicacion=ubicacion,
            lado=None,  # No tenemos esta info en el CSV
            altura=None,  # No tenemos esta info en el CSV
            stock_actual=0,  # Se actualizará después
            stock_reservado=0,
            stock_minimo=0,
            prioridad=3,  # Prioridad media por defecto
            activa=True,
            ultima_actualizacion_stock=datetime.utcnow()
        )
        
        self.db.add(new_location)
        return new_location, True
    
    def process_line(self, data: dict, line_num: int) -> bool:
        """
        Procesa una línea del CSV y crea/actualiza la ubicación.
        
        Returns:
            True si se procesó correctamente, False si hubo error
        """
        sku = data['sku']
        pasillo = data['pasillo']
        ubicacion = data['ubicacion']
        stock_actual = data['stock_actual']
        
        # 1. Buscar producto por SKU
        product = self.find_product_by_sku(sku)
        if not product:
            self.errors.append(f"Línea {line_num}: Producto no encontrado para SKU '{sku}'")
            return False
        
        # 2. Buscar o crear ubicación
        try:
            location, is_new = self.find_or_create_location(product.id, pasillo, ubicacion)
            
            # 3. Actualizar stock
            old_stock = location.stock_actual
            location.stock_actual = stock_actual
            location.ultima_actualizacion_stock = datetime.utcnow()
            
            # 4. Commit
            self.db.commit()
            
            # 5. Logging
            if is_new:
                self.created_count += 1
                print(f"  ✅ CREADO: {sku} → {pasillo}-{ubicacion} (stock: {stock_actual})")
            else:
                self.updated_count += 1
                print(f"  ✅ ACTUALIZADO: {sku} → {pasillo}-{ubicacion} (stock: {old_stock} → {stock_actual})")
            
            return True
        
        except Exception as e:
            self.db.rollback()
            self.errors.append(f"Línea {line_num}: Error al procesar SKU '{sku}' - {str(e)}")
            return False
    
    def run(self) -> bool:
        """
        Ejecuta el proceso completo de importación.
        
        Returns:
            True si el proceso completó sin errores críticos
        """
        print("\n" + "=" * 80)
        print("IMPORTACIÓN DE UBICACIONES DESDE CSV")
        print("=" * 80)
        print(f"Archivo: {self.csv_file_path}")
        print(f"Almacén destino: ID {self.almacen_id}")
        print()
        
        # Validaciones previas
        if not self.validate_csv_file():
            return False
        
        if not self.validate_almacen():
            return False
        
        print("\nIniciando importación...")
        print("-" * 80)
        
        # Leer y procesar CSV
        try:
            # utf-8-sig maneja BOM automáticamente
            with open(self.csv_file_path, 'r', encoding='utf-8-sig') as csvfile:
                # Leer primera línea para detectar si tiene headers
                first_line = csvfile.readline().strip()
                csvfile.seek(0)
                
                expected_headers = ['sku', 'pasillo', 'ubicacion', 'stock_actual']
                first_fields = [f.strip().lower() for f in first_line.split(';')]
                
                has_header = set(expected_headers).issubset(set(first_fields))
                
                if has_header:
                    reader = csv.DictReader(csvfile, delimiter=';')
                    start_line = 2
                else:
                    # CSV sin headers: asignar nombres de columna manualmente
                    reader = csv.DictReader(csvfile, fieldnames=expected_headers, delimiter=';')
                    start_line = 1
                    print("ℹ️  CSV sin cabecera detectado, usando columnas: sku;pasillo;ubicacion;stock_actual")
                
                # Procesar cada línea
                for line_num, row in enumerate(reader, start=start_line):
                    self.total_lines += 1
                    
                    # Parsear línea
                    data = self.parse_csv_line(row, line_num)
                    if not data:
                        self.error_count += 1
                        continue
                    
                    # Procesar línea
                    if self.process_line(data, line_num):
                        self.success_count += 1
                    else:
                        self.error_count += 1
        
        except Exception as e:
            print(f"\n❌ ERROR CRÍTICO al leer CSV: {str(e)}")
            return False
        
        finally:
            self.db.close()
        
        # Reporte final
        self.print_report()
        
        return self.error_count == 0
    
    def print_report(self):
        """Imprime el reporte final de la importación."""
        print("\n" + "=" * 80)
        print("REPORTE FINAL")
        print("=" * 80)
        print(f"Total líneas procesadas: {self.total_lines}")
        print(f"✅ Exitosas: {self.success_count}")
        print(f"   - Ubicaciones creadas: {self.created_count}")
        print(f"   - Ubicaciones actualizadas: {self.updated_count}")
        print(f"❌ Errores: {self.error_count}")
        
        if self.errors:
            print("\n" + "-" * 80)
            print("DETALLE DE ERRORES:")
            print("-" * 80)
            for error in self.errors[:50]:  # Mostrar máximo 50 errores
                print(f"  • {error}")
            
            if len(self.errors) > 50:
                print(f"\n  ... y {len(self.errors) - 50} errores más")
        
        print("\n" + "=" * 80)
        
        if self.error_count == 0:
            print("✅ IMPORTACIÓN COMPLETADA EXITOSAMENTE")
        else:
            print(f"⚠️  IMPORTACIÓN COMPLETADA CON {self.error_count} ERRORES")
        
        print("=" * 80 + "\n")


def main():
    """Función principal del script."""
    if len(sys.argv) < 2:
        print("Uso: python scripts/import_ubicaciones_csv.py <archivo.csv>")
        print("\nEjemplo:")
        print("  python scripts/import_ubicaciones_csv.py ubicaciones.csv")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    
    # Permitir override del almacén vía argumento opcional
    almacen_id = ALMACEN_PICKING_ID
    if len(sys.argv) >= 3:
        try:
            almacen_id = int(sys.argv[2])
        except ValueError:
            print(f"❌ ERROR: ID de almacén inválido: {sys.argv[2]}")
            sys.exit(1)
    
    # Ejecutar importación
    importer = UbicacionImporter(csv_file, almacen_id)
    success = importer.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()