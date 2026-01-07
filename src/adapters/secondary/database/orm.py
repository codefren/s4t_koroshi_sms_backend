from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, Date, ForeignKey, JSON, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from src.adapters.secondary.database.config import Base


class InventoryItemModel(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True) # Adding an internal ID since the CSV doesn't seem to have a unique PK, or EAN isn't unique enough?
    ean = Column(String(50), index=True)
    ubicacion = Column(String)
    articulo = Column(String)
    color = Column(String)
    talla = Column(String)
    posicion_talla = Column(String, nullable=True)
    descripcion_producto = Column(String, nullable=True)
    descripcion_color = Column(String, nullable=True)
    temporada = Column(String, nullable=True)
    numero_orden = Column(String(50), index=True)
    cliente = Column(String)
    nombre_cliente = Column(String, nullable=True)
    cantidad = Column(Integer)
    servida = Column(Integer)
    operario = Column(String, nullable=True)
    status = Column(String, nullable=True)
    fecha = Column(String, nullable=True) # Could be Date type if we parse it
    hora = Column(String, nullable=True)  # Could be Time type
    caja = Column(String, nullable=True)


# ============================================================================
# MODELOS DEL SISTEMA DE GESTIÓN DE ÓRDENES Y PICKING
# ============================================================================

class OrderViewCache(Base):
    """
    Caché de la VIEW de SQL Server para detectar órdenes nuevas.
    
    Esta tabla almacena una copia de los datos crudos que vienen de la VIEW externa
    de SQL Server. Se usa para:
    - Detectar órdenes nuevas comparando numero_orden
    - Evitar procesar la misma orden múltiples veces
    - Mantener auditoría de qué datos llegaron del sistema externo
    - Permitir re-procesamiento si es necesario
    """
    __tablename__ = "order_view_cache"

    id = Column(Integer, primary_key=True, index=True)
    # Número de orden del sistema externo - usado como identificador único
    numero_orden = Column(String(100), unique=True, nullable=False, index=True)
    
    # Datos completos en formato JSON tal como vienen de la VIEW
    # Permite reconstruir el origen exacto y auditar cambios
    raw_data = Column(JSON, nullable=False)
    
    # Timestamp de cuándo se consultó esta orden desde la VIEW
    # Útil para saber la "frescura" de los datos
    fecha_importacion = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Flag que indica si esta orden ya fue normalizada a las tablas principales
    # False = pendiente de procesar, True = ya procesada
    procesado = Column(Boolean, default=False, nullable=False, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('idx_numero_orden_procesado', 'numero_orden', 'procesado'),
    )


class OrderStatus(Base):
    """
    Catálogo de estados del ciclo de vida de una orden.
    
    Define todos los estados posibles por los que puede pasar una orden,
    desde que se importa hasta que se envía. Esta tabla es de solo lectura
    después de la inicialización.
    
    Estados predefinidos:
    - PENDING (10): Orden recién importada, sin asignar
    - ASSIGNED (20): Asignada a un operario
    - IN_PICKING (30): Operario recogiendo items
    - PICKED (40): Todos los items recogidos
    - PACKING (50): Empacando la orden
    - READY (60): Lista para envío
    - SHIPPED (70): Enviada al cliente
    - CANCELLED (99): Orden cancelada
    """
    __tablename__ = "order_status"

    id = Column(Integer, primary_key=True, index=True)
    
    # Código único del estado (ej: PENDING, ASSIGNED, IN_PICKING)
    # Usado en código para referirse al estado sin depender del ID
    codigo = Column(String(50), unique=True, nullable=False, index=True)
    
    # Nombre legible para mostrar en UI (ej: "Pendiente", "En Picking")
    nombre = Column(String(100), nullable=False)
    
    # Descripción detallada de qué significa este estado
    descripcion = Column(Text, nullable=True)
    
    # Número que indica el orden secuencial del estado en el flujo
    # Permite ordenar estados y validar transiciones lógicas
    orden = Column(Integer, nullable=False, index=True)
    
    # Si el estado está activo/disponible para uso
    # Permite deshabilitar estados sin eliminarlos
    activo = Column(Boolean, default=True, nullable=False, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    orders = relationship("Order", back_populates="status", foreign_keys="Order.status_id")
    history_entries = relationship("OrderHistory", back_populates="status", foreign_keys="OrderHistory.status_id")


class Operator(Base):
    """
    Operarios del almacén que realizan las tareas de picking.
    
    Representa a las personas que trabajan en el almacén recogiendo productos.
    Cada operario puede tener múltiples órdenes asignadas y ejecuta tareas
    de picking.
    """
    __tablename__ = "operators"

    id = Column(Integer, primary_key=True, index=True)
    
    # Código único del operario (ej: OP001, OP002)
    # Puede venir del sistema de nómina o ser asignado internamente
    codigo_operario = Column(String(50), unique=True, nullable=False, index=True)
    
    # Nombre completo del operario para identificación
    nombre = Column(String(100), nullable=False)
    
    # Indica si el operario está activo/disponible para trabajar
    # False si está de vacaciones, incapacitado, o ya no trabaja
    activo = Column(Boolean, default=True, nullable=False, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    orders = relationship("Order", back_populates="operator")
    picking_tasks = relationship("PickingTask", back_populates="operator")
    history_entries = relationship("OrderHistory", back_populates="operator")


class Order(Base):
    """
    Órdenes principales del sistema, agrupadas por numero_orden.
    
    Representa el "header" de una orden que contiene múltiples líneas (productos).
    Una orden pasa por diferentes estados desde que se importa hasta que se envía.
    Esta es la tabla central del sistema de picking.
    
    Flujo típico:
    1. Se importa desde VIEW → estado PENDING
    2. Se asigna operario → ASSIGNED
    3. Inicia picking → IN_PICKING
    4. Completa picking → PICKED
    5. Se empaca → PACKING
    6. Lista para envío → READY
    7. Se envía → SHIPPED
    """
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    
    # Número de orden del sistema externo - identificador único de negocio
    # Viene de la VIEW de SQL Server y agrupa múltiples líneas
    numero_orden = Column(String(100), unique=True, nullable=False, index=True)
    
    # === DATOS DEL CLIENTE (desnormalizados) ===
    # Código del cliente del sistema externo
    cliente = Column(String(100), nullable=False, index=True)
    
    # Nombre del cliente para mostrar en UI
    nombre_cliente = Column(String(200), nullable=True)
    
    # === REFERENCIAS ===
    # Estado actual de la orden (PENDING, ASSIGNED, IN_PICKING, etc.)
    status_id = Column(Integer, ForeignKey("order_status.id", ondelete="NO ACTION"), nullable=False, index=True)
    
    # Operario asignado para hacer el picking (NULL si aún no se asignó)
    operator_id = Column(Integer, ForeignKey("operators.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # === FECHAS DE CONTROL ===
    # Fecha en que se creó la orden en el sistema externo
    fecha_orden = Column(Date, nullable=False, index=True)
    
    # Cuándo se importó desde la VIEW a nuestro sistema
    fecha_importacion = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Cuándo se asignó a un operario
    fecha_asignacion = Column(DateTime, nullable=True)
    
    # Cuándo el operario inició el picking
    fecha_inicio_picking = Column(DateTime, nullable=True)
    
    # Cuándo se completó el picking de todos los items
    fecha_fin_picking = Column(DateTime, nullable=True)
    
    # === INFORMACIÓN ADICIONAL ===
    # Número de caja donde se empacará/empacó la orden
    caja = Column(String(50), nullable=True)
    
    # Prioridad de la orden: LOW, NORMAL, HIGH, URGENT
    # Determina el orden en que se procesan las órdenes
    prioridad = Column(String(20), default='NORMAL', nullable=False, index=True)
    
    # === CONTADORES (desnormalizados para performance) ===
    # Total de líneas/items en la orden
    # Se calcula al importar y evita hacer COUNT(*) constantemente
    total_items = Column(Integer, default=0, nullable=False)
    
    # Cuántas líneas han sido completamente recogidas
    # Permite calcular progreso rápidamente: items_completados/total_items
    items_completados = Column(Integer, default=0, nullable=False)
    
    # === METADATOS ===
    # Notas o comentarios adicionales sobre la orden
    notas = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    status = relationship("OrderStatus", back_populates="orders", foreign_keys=[status_id])
    operator = relationship("Operator", back_populates="orders")
    order_lines = relationship("OrderLine", back_populates="order", cascade="all, delete-orphan")
    history = relationship("OrderHistory", back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_status_operator', 'status_id', 'operator_id'),
        Index('idx_status_fecha', 'status_id', 'fecha_orden'),
        Index('idx_fecha_importacion', 'fecha_importacion'),
    )


class OrderLine(Base):
    """
    Líneas individuales de cada orden con datos de producto desnormalizados.
    
    Cada línea representa un producto específico dentro de una orden.
    Por ejemplo, si una orden pide 3 productos diferentes, tendrá 3 order_lines.
    Los datos del producto se guardan desnormalizados (sin tabla de productos)
    para mantener simplicidad y evitar joins.
    
    Una orden puede tener muchas líneas, y cada línea tiene su propia
    ubicación en el almacén donde el operario debe ir a recogerla.
    """
    __tablename__ = "order_lines"

    id = Column(Integer, primary_key=True, index=True)
    
    # Orden a la que pertenece esta línea
    # CASCADE: si se borra la orden, se borran todas sus líneas
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # === DATOS DE PRODUCTO (desnormalizados) ===
    # Código de barras EAN del producto - usado para escanear
    ean = Column(String(50), nullable=True, index=True)
    
    # Ubicación física en el almacén (ej: "A-12-3" = Pasillo A, Rack 12, Nivel 3)
    # El operario usa esto para saber dónde ir a buscar el producto
    ubicacion = Column(String(100), nullable=True, index=True)
    
    # Código del artículo (SKU interno)
    articulo = Column(String(100), nullable=True, index=True)
    
    # Color del producto (ej: "Rojo", "Azul")
    color = Column(String(100), nullable=True)
    
    # Talla del producto (ej: "M", "42", "XL")
    talla = Column(String(50), nullable=True)
    
    # Posición de la talla en catálogo (usado para ordenamiento)
    posicion_talla = Column(String(50), nullable=True)
    
    # Descripción legible del producto (ej: "Camisa Polo Manga Corta")
    descripcion_producto = Column(Text, nullable=True)
    
    # Descripción del color (ej: "Rojo Vino")
    descripcion_color = Column(String(200), nullable=True)
    
    # Temporada del producto (ej: "Verano 2024", "Invierno 2025")
    temporada = Column(String(50), nullable=True)
    
    # === CANTIDADES ===
    # Cuántas unidades se pidieron de este producto
    cantidad_solicitada = Column(Integer, nullable=False)
    
    # Cuántas unidades se han recogido hasta ahora
    # Puede ser < cantidad_solicitada si hay picking parcial o falta stock
    cantidad_servida = Column(Integer, default=0, nullable=False)
    
    # === ESTADO DE LA LÍNEA ===
    # PENDING: No se ha empezado a recoger
    # PARTIAL: Se recogió algo pero no todo (cantidad_servida < cantidad_solicitada)
    # COMPLETED: Se recogió todo (cantidad_servida == cantidad_solicitada)
    estado = Column(String(20), default='PENDING', nullable=False, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    order = relationship("Order", back_populates="order_lines")
    picking_tasks = relationship("PickingTask", back_populates="order_line", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_order_estado', 'order_id', 'estado'),
    )


class OrderHistory(Base):
    """
    Historial de cambios y eventos de las órdenes para auditoría.
    
    Registra TODOS los eventos importantes que le suceden a una orden:
    - Cambios de estado (PENDING → ASSIGNED → IN_PICKING → etc.)
    - Asignaciones/reasignaciones de operarios
    - Importación desde VIEW
    - Cancelaciones
    - Cualquier acción relevante
    
    Esta tabla es APPEND-ONLY (solo se insertan registros, nunca se modifican).
    Permite reconstruir la línea de tiempo completa de una orden para:
    - Auditoría
    - Análisis de tiempos
    - Detección de problemas
    - Reportes gerenciales
    """
    __tablename__ = "order_history"

    id = Column(Integer, primary_key=True, index=True)
    
    # Orden a la que pertenece este evento
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Estado de la orden en el momento de este evento
    status_id = Column(Integer, ForeignKey("order_status.id", ondelete="NO ACTION"), nullable=False, index=True)
    
    # Operario que generó/causó este evento (NULL si fue automático)
    operator_id = Column(Integer, ForeignKey("operators.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # === INFORMACIÓN DEL EVENTO ===
    # Tipo de acción que ocurrió:
    # - IMPORTED_FROM_VIEW: Orden recién importada
    # - STATUS_CHANGE: Cambio de estado
    # - ASSIGNED: Asignada a operario
    # - UNASSIGNED: Desasignada de operario
    # - PICKING_STARTED: Inicio de picking
    # - PICKING_COMPLETED: Fin de picking
    # - NOTE_ADDED: Nota agregada
    # - CANCELLED: Cancelación
    accion = Column(String(50), nullable=False, index=True)
    
    # Estado anterior (antes del cambio) - solo para cambios de estado
    status_anterior = Column(Integer, ForeignKey("order_status.id", ondelete="NO ACTION"), nullable=True)
    
    # Estado nuevo (después del cambio) - solo para cambios de estado
    status_nuevo = Column(Integer, ForeignKey("order_status.id", ondelete="NO ACTION"), nullable=True)
    
    # Timestamp exacto de cuándo ocurrió el evento
    fecha = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Notas o descripción del evento en texto plano
    notas = Column(Text, nullable=True)
    
    # Datos adicionales en formato JSON flexible
    # Ejemplo: {"items_picked": 5, "tiempo_minutos": 25, "razon": "Stock insuficiente"}
    # Permite almacenar info contextual sin modificar el schema
    event_metadata = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    order = relationship("Order", back_populates="history")
    status = relationship("OrderStatus", foreign_keys=[status_id], back_populates="history_entries")
    operator = relationship("Operator", back_populates="history_entries")

    __table_args__ = (
        Index('idx_order_fecha', 'order_id', 'fecha'),
        Index('idx_operator_fecha', 'operator_id', 'fecha'),
    )


class PickingTask(Base):
    """
    Tareas granulares de picking asignadas a operarios.
    
    Cuando se asigna una orden a un operario, se crean PickingTasks individuales
    para cada línea de la orden. Cada tarea representa:
    - IR a una ubicación específica del almacén
    - RECOGER una cantidad específica de un producto
    - ESCANEAR el código de barras para confirmar
    - REGISTRAR la cantidad recogida
    
    Las tareas se pueden ordenar por 'secuencia' para optimizar la ruta
    del operario (minimizar distancia recorrida en el almacén).
    
    Ejemplo:
    Orden #12345 tiene 3 líneas → Se crean 3 PickingTasks
    - Task 1: Ir a A-10-2, recoger 5 unidades de Camisa Roja
    - Task 2: Ir a B-05-1, recoger 3 unidades de Pantalón Azul
    - Task 3: Ir a A-11-3, recoger 2 unidades de Camisa Verde
    """
    __tablename__ = "picking_tasks"

    id = Column(Integer, primary_key=True, index=True)
    
    # Línea de orden asociada a esta tarea
    order_line_id = Column(Integer, ForeignKey("order_lines.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Operario asignado para ejecutar esta tarea
    operator_id = Column(Integer, ForeignKey("operators.id", ondelete="NO ACTION"), nullable=False, index=True)
    
    # === UBICACIÓN ===
    # Ubicación desnormalizada (copiada de order_line) para acceso rápido
    # El operario ve esta ubicación en su dispositivo/pantalla
    ubicacion = Column(String(100), nullable=False, index=True)
    
    # === CANTIDADES ===
    # Cuántas unidades debe recoger el operario
    cantidad_a_recoger = Column(Integer, nullable=False)
    
    # Cuántas unidades ha recogido hasta ahora
    cantidad_recogida = Column(Integer, default=0, nullable=False)
    
    # === CONTROL DE ESTADO Y FLUJO ===
    # Estado actual de la tarea:
    # - PENDING: Aún no iniciada, en cola
    # - IN_PROGRESS: Operario actualmente trabajando en ella
    # - COMPLETED: Terminada exitosamente
    # - FAILED: Falló (ej: producto no encontrado)
    # - SKIPPED: Saltada intencionalmente
    estado = Column(String(20), default='PENDING', nullable=False, index=True)
    
    # Número de secuencia para optimizar ruta de picking
    # Las tareas con secuencia menor se hacen primero
    # Puede calcularse con algoritmos de optimización de rutas
    secuencia = Column(Integer, nullable=True, index=True)
    
    # Prioridad de la tarea (1=baja, 5=alta)
    # Tareas de alta prioridad se muestran primero
    prioridad = Column(Integer, default=1, nullable=False)
    
    # === TIEMPOS ===
    # Cuándo el operario empezó esta tarea
    fecha_inicio = Column(DateTime, nullable=True)
    
    # Cuándo el operario terminó esta tarea
    fecha_fin = Column(DateTime, nullable=True)
    
    # Tiempo estimado en segundos (puede venir de histórico o cálculos)
    tiempo_estimado_seg = Column(Integer, nullable=True)
    
    # Tiempo real que tomó (calculado: fecha_fin - fecha_inicio)
    # Usado para análisis de performance y mejorar estimaciones
    tiempo_real_seg = Column(Integer, nullable=True)
    
    # === CONTROL ===
    # Número de veces que se intentó esta tarea
    # Útil si hay fallos y se reintenta
    intentos = Column(Integer, default=0, nullable=False)
    
    # Notas del operario (ej: "Producto dañado", "Ubicación incorrecta")
    notas = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    order_line = relationship("OrderLine", back_populates="picking_tasks")
    operator = relationship("Operator", back_populates="picking_tasks")

    __table_args__ = (
        Index('idx_operator_estado', 'operator_id', 'estado'),
        Index('idx_operator_secuencia', 'operator_id', 'secuencia'),
        Index('idx_estado_prioridad', 'estado', 'prioridad'),
    )


# ============================================================================
# MODELOS DE GESTIÓN DE PRODUCTOS Y UBICACIONES
# ============================================================================

class ProductReference(Base):
    """
    Catálogo de referencias de productos del almacén.
    
    Mantiene información maestra de productos identificados por una referencia
    hexadecimal única. Cada producto puede estar almacenado en múltiples
    ubicaciones del almacén (relación One-to-Many con ProductLocation).
    
    Esta tabla sirve como:
    - Catálogo maestro de productos
    - Validación de referencias en imports/órdenes
    - Búsqueda rápida de información de producto
    - Base para gestión de inventario multi-ubicación
    
    Ejemplo:
    - Referencia: "A1B2C3"
    - Nombre: "Camisa Polo Manga Corta"
    - Color ID: "000001" (Rojo)
    - Talla: "M"
    - Ubicaciones: [Pasillo A-Altura 2, Pasillo B3-Altura 1]
    """
    __tablename__ = "product_references"

    id = Column(Integer, primary_key=True, index=True)
    
    # Referencia hexadecimal única del producto
    # Código único que identifica este producto específico (color + talla)
    # Ejemplo: "2A3F4B", "FF00AA", "A1B2C3"
    # Validación: Solo caracteres hexadecimales [0-9A-Fa-f]
    referencia = Column(String(50), unique=True, nullable=False, index=True)
    
    # Nombre descriptivo del producto
    # Ejemplo: "Camisa Polo Manga Corta", "Pantalón Vaquero Slim"
    nombre_producto = Column(String(200), nullable=False, index=True)
    
    # ID del color en el catálogo
    # Puede ser numérico ("000001", "000002") o código ("RED", "BLUE")
    # Se mantiene como string para flexibilidad
    color_id = Column(String(50), nullable=False, index=True)
    
    # Talla del producto
    # Ejemplos: "XS", "S", "M", "L", "XL", "XXL", "38", "40", "42"
    talla = Column(String(20), nullable=False, index=True)
    
    # === INFORMACIÓN ADICIONAL OPCIONAL ===
    
    # Descripción legible del color (ej: "Rojo", "Azul Marino")
    descripcion_color = Column(String(100), nullable=True)
    
    # Código de barras EAN del producto
    ean = Column(String(50), nullable=True, index=True)
    
    # SKU o código interno del artículo
    sku = Column(String(100), nullable=True, index=True)
    
    # Temporada del producto (ej: "Verano 2024", "Invierno 2025")
    temporada = Column(String(50), nullable=True)
    
    # Si el producto está activo en el catálogo
    # False = descontinuado o fuera de catálogo
    activo = Column(Boolean, default=True, nullable=False, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    # Un producto puede estar en múltiples ubicaciones
    locations = relationship("ProductLocation", back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        # Índice para búsquedas por color y talla
        Index('idx_color_talla', 'color_id', 'talla'),
        # Índice para búsqueda por nombre (autocomplete)
        Index('idx_nombre_producto', 'nombre_producto'),
        # Índice para productos activos
        Index('idx_activo', 'activo'),
        # Índice compuesto para búsquedas frecuentes
        Index('idx_nombre_color_talla', 'nombre_producto', 'color_id', 'talla'),
    )


class ProductLocation(Base):
    """
    Ubicaciones físicas de productos en el almacén.
    
    Cada registro representa una ubicación específica donde se almacena
    un producto. Un mismo producto puede estar en múltiples ubicaciones
    para optimizar el picking (ej: producto muy demandado en varias zonas).
    
    La ubicación se estructura en:
    - Pasillo: Identificador del pasillo (alfanumérico: "A", "B1", "C3")
    - Lado: Izquierda o Derecha del pasillo
    - Ubicacion: Posición específica en el lado (número o código)
    - Altura: Nivel vertical (1=bajo, 2=medio, 3=alto, etc.)
    
    Además, cada ubicación tiene un stock mínimo configurado para
    activar alertas de reposición.
    
    Ejemplo de ubicación completa:
    - Pasillo: "A"
    - Lado: "IZQUIERDA"
    - Ubicacion: "12"
    - Altura: 2
    - Código resultante: "A-IZQ-12-H2"
    - Stock mínimo: 10 unidades
    """
    __tablename__ = "product_locations"

    id = Column(Integer, primary_key=True, index=True)
    
    # Producto al que pertenece esta ubicación
    product_id = Column(Integer, ForeignKey("product_references.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # === COMPONENTES DE LA UBICACIÓN ===
    
    # Pasillo del almacén (alfanumérico)
    # Ejemplos: "A", "B", "C", "A1", "B2", "C3", "AA", "BB"
    # Permite letras, números y combinaciones
    pasillo = Column(String(10), nullable=False, index=True)
    
    # Lado del pasillo: "IZQUIERDA" o "DERECHA"
    # Se puede usar enum para mayor consistencia
    # Valores permitidos: "IZQUIERDA", "DERECHA", "IZQ", "DER", "L", "R"
    lado = Column(String(20), nullable=False, index=True)
    
    # Ubicación específica dentro del lado
    # Puede ser número ("1", "2", "12") o alfanumérico ("A1", "B3")
    ubicacion = Column(String(20), nullable=False, index=True)
    
    # Altura o nivel vertical
    # Valores típicos: 1, 2, 3, 4, 5
    # 1 = Nivel más bajo (fácil acceso)
    # 5 = Nivel más alto (requiere escalera/elevador)
    altura = Column(Integer, nullable=False, index=True)
    
    # === GESTIÓN DE STOCK ===
    
    # Stock mínimo que debe haber en esta ubicación
    # Cuando el stock actual sea menor, se genera alerta de reposición
    stock_minimo = Column(Integer, default=0, nullable=False)
    
    # Stock actual en esta ubicación específica (opcional)
    # Puede actualizarse con sistema de inventario
    stock_actual = Column(Integer, default=0, nullable=False)
    
    # === INFORMACIÓN ADICIONAL ===
    
    # Prioridad de esta ubicación para picking (1=alta, 5=baja)
    # Ubicaciones con prioridad alta se usan primero
    # Útil para optimizar rutas de picking
    prioridad = Column(Integer, default=3, nullable=False)

    # Si esta ubicación está activa/disponible
    # False = ubicación en mantenimiento o bloqueada
    activa = Column(Boolean, default=True, nullable=False, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    product = relationship("ProductReference", back_populates="locations")

    __table_args__ = (
        # Índice para búsquedas por pasillo
        Index('idx_pasillo', 'pasillo'),
        # Índice para búsquedas por lado
        Index('idx_lado', 'lado'),
        # Índice compuesto para ubicación completa
        Index('idx_ubicacion_completa', 'pasillo', 'lado', 'ubicacion', 'altura'),
        # Índice para stock bajo (alertas)
        Index('idx_stock_bajo', 'stock_actual', 'stock_minimo'),
        # Índice para ubicaciones activas con prioridad
        Index('idx_activa_prioridad', 'activa', 'prioridad'),
        # Asegurar que no haya ubicaciones duplicadas para el mismo producto
        UniqueConstraint('product_id', 'pasillo', 'lado', 'ubicacion', 'altura', 
                        name='uq_product_location'),
    )

    @property
    def codigo_ubicacion(self):
        return f"{self.pasillo}-{self.lado}-{self.ubicacion}-{self.altura}"