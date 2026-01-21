"""
Order Loader Service

Servicio encargado de cargar órdenes desde archivos CSV externos.
Se ejecuta periódicamente para importar nuevas órdenes al sistema.

Arquitectura:
    - Lee archivo CSV con formato específico
    - Valida datos de entrada
    - Agrupa líneas por número de orden
    - Crea órdenes y líneas en la base de datos
    - Registra en historial de auditoría
"""

import csv
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from adapters.secondary.database.config import SessionLocal
from adapters.secondary.database.orm import (
    Order, OrderLine, OrderStatus, OrderHistory,
    Operator, ProductReference, EAN, 
    Almacen, Client, Address
)

logger = logging.getLogger(__name__)


class OrderLoaderService:
    """
    Servicio de carga de órdenes desde CSV.
    
    Responsabilidades:
        - Leer y parsear archivos CSV
        - Validar formato y datos
        - Agrupar líneas por orden
        - Crear registros en base de datos
        - Manejar duplicados
        - Logging de operaciones
    """
    
    def __init__(
        self, 
        csv_file_path: str,
        db_session: Optional[Session] = None
    ):
        """
        Inicializa el servicio de carga.
        
        Args:
            csv_file_path: Ruta al archivo CSV a procesar
            db_session: Sesión de base de datos (opcional, se crea una si no se provee)
        """
        self.csv_file_path = Path(csv_file_path)
        self.db = db_session or SessionLocal()
        self.owns_session = db_session is None
        
        # Estadísticas de la carga
        self.stats = {
            'orders_processed': 0,
            'orders_created': 0,
            'orders_skipped': 0,
            'lines_created': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
    
    def run(self) -> Dict[str, int]:
        """
        Ejecuta el proceso completo de carga de órdenes.
        
        Flujo:
            1. Validar archivo CSV
            2. Leer y parsear contenido
            3. Agrupar líneas por orden
            4. Procesar cada orden
            5. Confirmar transacciones
            6. Retornar estadísticas
        
        Returns:
            Diccionario con estadísticas de la ejecución:
            {
                'orders_processed': int,
                'orders_created': int,
                'orders_skipped': int,
                'lines_created': int,
                'errors': int,
                'duration_seconds': float
            }
        """
        self.stats['start_time'] = datetime.now()
        logger.info(f"🚀 Iniciando carga de órdenes desde: {self.csv_file_path}")
        
        try:
            # 1. Validar archivo
            if not self._validate_csv_file():
                return self._finalize_stats()
            
            # 2. Leer CSV y agrupar por orden
            orders_data = self._read_and_group_csv()
            if not orders_data:
                logger.warning("No se encontraron órdenes para procesar")
                return self._finalize_stats()
            
            logger.info(f"📦 Total de órdenes encontradas: {len(orders_data)}")
            
            # 3. Procesar cada orden
            for numero_orden, order_data in orders_data.items():
                try:
                    self._process_order(numero_orden, order_data)
                    self.stats['orders_processed'] += 1
                except Exception as e:
                    logger.error(f"❌ Error procesando orden {numero_orden}: {e}")
                    self.stats['errors'] += 1
                    continue
            
            # 4. Confirmar cambios
            self.db.commit()
            logger.info("✅ Transacción confirmada exitosamente")
            
        except Exception as e:
            logger.error(f"❌ Error fatal durante la carga: {e}", exc_info=True)
            self.db.rollback()
            self.stats['errors'] += 1
        
        finally:
            if self.owns_session:
                self.db.close()
        
        return self._finalize_stats()
    
    def _validate_csv_file(self) -> bool:
        """
        Valida que el archivo CSV existe y es accesible.
        
        Returns:
            True si el archivo es válido, False en caso contrario
        """
        if not self.csv_file_path.exists():
            logger.error(f"❌ Archivo no encontrado: {self.csv_file_path}")
            return False
        
        if not self.csv_file_path.is_file():
            logger.error(f"❌ La ruta no es un archivo: {self.csv_file_path}")
            return False
        
        logger.info(f"✓ Archivo válido: {self.csv_file_path}")
        return True
    
    def _read_and_group_csv(self) -> Dict[str, Dict]:
        """
        Lee el archivo CSV y agrupa las líneas por número de orden.
        
        Returns:
            Diccionario con estructura:
            {
                'numero_orden': {
                    'header': Dict (primera línea de la orden),
                    'lines': List[Dict] (todas las líneas)
                }
            }
        """
        orders_dict = {}
        
        try:
            with open(self.csv_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                
                for row in reader:
                    numero_orden = row['no.orden'].strip()
                    
                    if numero_orden not in orders_dict:
                        orders_dict[numero_orden] = {
                            'header': row,
                            'lines': []
                        }
                    
                    orders_dict[numero_orden]['lines'].append(row)
            
            logger.info(f"✓ CSV leído: {len(orders_dict)} órdenes encontradas")
            
        except Exception as e:
            logger.error(f"❌ Error leyendo CSV: {e}", exc_info=True)
            raise
        
        return orders_dict
    
    def _process_order(self, numero_orden: str, order_data: Dict) -> None:
        """
        Procesa una orden individual: crea el registro principal y sus líneas.
        
        Args:
            numero_orden: Número único de la orden
            order_data: Diccionario con 'header' y 'lines' de la orden
        """
        logger.info(f"📝 Procesando orden: {numero_orden}")
        
        # Verificar si ya existe
        if self._order_exists(numero_orden):
            logger.warning(f"⚠️  Orden {numero_orden} ya existe, saltando...")
            self.stats['orders_skipped'] += 1
            return
        
        header = order_data['header']
        lines = order_data['lines']
        
        # 1. Obtener o crear cliente
        cliente = self._get_or_create_cliente(header)
        
        # 2. Obtener referencias necesarias
        status = self._get_pending_status()
        almacen = self._get_default_almacen()
        
        # 3. Crear orden principal
        new_order = self._create_order_record(
            numero_orden, header, cliente, status, almacen, len(lines)
        )
        
        # 4. Crear líneas de orden
        for line_data in lines:
            self._create_order_line(new_order, line_data)
            self.stats['lines_created'] += 1
        
        # 5. Crear registro en historial
        self._create_history_record(new_order, status)
        
        self.stats['orders_created'] += 1
        logger.info(f"✓ Orden {numero_orden} creada con {len(lines)} líneas")
    
    def _order_exists(self, numero_orden: str) -> bool:
        """Verifica si una orden ya existe en la base de datos."""
        return self.db.query(Order).filter(
            Order.numero_orden == numero_orden
        ).first() is not None
    
    def _get_or_create_cliente(self, header: Dict) -> Client:
        """Obtiene o crea un cliente basado en los datos del header."""
        codigo_cliente = header['cliente'].strip()
        nombre_cliente = header['nombre cliente'].strip()
        
        cliente = self.db.query(Client).filter(
            Client.codigo == codigo_cliente
        ).first()
        
        if not cliente:
            logger.info(f"Creando nuevo cliente: {codigo_cliente}")
            cliente = Client(
                codigo=codigo_cliente,
                description=nombre_cliente,
                phone_number="600000000"
            )
            self.db.add(cliente)
            self.db.flush()
        
        return cliente
    
    def _get_pending_status(self) -> OrderStatus:
        """
        Obtiene el estado PENDING.
        
        Usa directamente ID=1 que representa PENDING.
        """
        # Usar get() que es más eficiente para búsqueda por PK
        status = self.db.get(OrderStatus, 1)
        
        if not status:
            raise ValueError("Estado PENDING (ID=1) no encontrado en base de datos")
        
        return status
    
    def _get_default_almacen(self) -> Almacen:
        """Obtiene o crea el almacén por defecto."""
        almacen = self.db.query(Almacen).filter(
            Almacen.codigo == "ALM-01"
        ).first()
        
        if not almacen:
            logger.info("Creando almacén por defecto ALM-01")
            almacen = Almacen(
                codigo="ALM-01",
                descripciones="Almacén Central"
            )
            self.db.add(almacen)
            self.db.flush()
        
        return almacen
    
    def _create_order_record(
        self,
        numero_orden: str,
        header: Dict,
        cliente: Client,
        status: OrderStatus,
        almacen: Almacen,
        total_items: int
    ) -> Order:
        """Crea el registro principal de la orden."""
        fecha_orden = self._parse_csv_date(
            header['fecha'].strip(),
            header['hora'].strip()
        )
        
        new_order = Order(
            numero_orden=numero_orden,
            numero_pedido=header['caja'].strip(),
            client=cliente.id,
            almacen_id=almacen.id,
            type="B2B",
            cliente=cliente.codigo,
            nombre_cliente=cliente.description,
            status_id=status.id,
            prioridad="NORMAL",
            total_items=total_items,
            fecha_orden=fecha_orden.date(),  # Solo la fecha, no datetime
            created_at=fecha_orden,
            updated_at=fecha_orden
        )
        
        self.db.add(new_order)
        self.db.flush()
        
        return new_order
    
    def _create_order_line(self, order: Order, line_data: Dict) -> OrderLine:
        """Crea una línea de orden."""
        ean_code = line_data['ean'].strip()
        
        # Buscar producto por EAN
        product = self._find_product_by_ean(ean_code)
        
        # Parsear cantidades y estado
        cantidad_solicitada = int(line_data['cantidad'].strip())
        cantidad_servida = int(line_data['servida'].strip())
        status_line = line_data['status'].strip()
        
        # Determinar estado de la línea
        estado_linea = self._determine_line_status(
            status_line, cantidad_servida, cantidad_solicitada
        )
        
        # Crear línea
        order_line = OrderLine(
            order_id=order.id,
            product_reference_id=product.id if product else None,
            ean=ean_code,
            cantidad_solicitada=cantidad_solicitada,
            cantidad_servida=cantidad_servida,
            estado=estado_linea
        )
        
        self.db.add(order_line)
        return order_line
    
    def _find_product_by_ean(self, ean_code: str) -> Optional[ProductReference]:
        """Busca un producto por su código EAN."""
        ean_obj = self.db.query(EAN).filter(EAN.ean == ean_code).first()
        
        if not ean_obj or not ean_obj.product_reference_id:
            logger.warning(f"⚠️  EAN {ean_code} no encontrado en catálogo")
            return None
        
        return self.db.query(ProductReference).filter(
            ProductReference.id == ean_obj.product_reference_id
        ).first()
    
    def _determine_line_status(
        self, 
        status_code: str, 
        servida: int, 
        solicitada: int
    ) -> str:
        """
        Determina el estado de una línea de orden.
        
        Args:
            status_code: Código de estado del CSV ('S' o 'D')
            servida: Cantidad servida
            solicitada: Cantidad solicitada
        
        Returns:
            Estado de la línea: 'PICKED', 'PARTIAL', o 'PENDING'
        """
        if status_code == 'S' and servida == solicitada:
            return "PICKED"
        elif status_code == 'D' or servida < solicitada:
            return "PARTIAL"
        else:
            return "PENDING"
    
    def _create_history_record(self, order: Order, status: OrderStatus) -> None:
        """Crea un registro en el historial de la orden."""
        history = OrderHistory(
            order_id=order.id,
            status_id=status.id,
            accion="ORDER_IMPORTED",
            notas=f"Orden importada desde archivo CSV: {self.csv_file_path.name}",
            event_metadata={
                "source": "order_loader_service",
                "csv_file": str(self.csv_file_path),
                "total_items": order.total_items
            }
        )
        self.db.add(history)
    
    def _parse_csv_date(self, fecha_str: str, hora_str: str) -> datetime:
        """
        Parsea fecha y hora del CSV a datetime.
        
        Args:
            fecha_str: Fecha en formato YYYYMMDD
            hora_str: Hora en formato HH:MM
        
        Returns:
            Objeto datetime
        """
        try:
            fecha_completa = f"{fecha_str} {hora_str}"
            return datetime.strptime(fecha_completa, "%Y%m%d %H:%M")
        except Exception as e:
            logger.warning(f"Error parseando fecha {fecha_str} {hora_str}: {e}")
            return datetime.now()
    
    def _finalize_stats(self) -> Dict[str, int]:
        """
        Finaliza las estadísticas y calcula duración.
        
        Returns:
            Diccionario con estadísticas completas
        """
        self.stats['end_time'] = datetime.now()
        
        if self.stats['start_time']:
            duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
            self.stats['duration_seconds'] = duration
        
        logger.info("=" * 80)
        logger.info("✅ CARGA COMPLETADA")
        logger.info(f"   📦 Órdenes procesadas: {self.stats['orders_processed']}")
        logger.info(f"   ✓  Órdenes creadas: {self.stats['orders_created']}")
        logger.info(f"   ⏭️  Órdenes saltadas: {self.stats['orders_skipped']}")
        logger.info(f"   📝 Líneas creadas: {self.stats['lines_created']}")
        logger.info(f"   ❌ Errores: {self.stats['errors']}")
        
        if 'duration_seconds' in self.stats:
            logger.info(f"   ⏱️  Duración: {self.stats['duration_seconds']:.2f}s")
        
        logger.info("=" * 80)
        
        return self.stats


def run_order_loader(csv_file_path: str) -> Dict[str, int]:
    """
    Función helper para ejecutar el loader de forma simple.
    
    Args:
        csv_file_path: Ruta al archivo CSV
    
    Returns:
        Estadísticas de ejecución
    """
    service = OrderLoaderService(csv_file_path)
    return service.run()
