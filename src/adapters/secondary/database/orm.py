from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, Date, ForeignKey, JSON, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from src.adapters.secondary.database.config import Base


class Address(Base):
    """
    Direcciones
    """
    __tablename__ = "direcciones"
    id = Column(Integer, primary_key=True, index=True)
    description = Column(String(100), nullable=True)
    address = Column(String(100), nullable=True)
    zipcode = Column(String(10), nullable=True)
    city = Column(String(50), nullable=True)
    country = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow(), onupdate=datetime.utcnow(), nullable=False)


class Client(Base):
    """
    Clientes
    """
    __tablename__ = "clientes"
    id = Column(Integer, primary_key=True, index=True)
    description = Column(String(100), nullable=False)
    codigo = Column(String(10), nullable=False, index=True)
    phone_number = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow(), onupdate=datetime.utcnow(), nullable=False)
    

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

    numero_pedido = Column(String(100), nullable=True, index=True)

    client = Column(Integer, ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True, index=True)

    address = Column(Integer, ForeignKey("direcciones.id", ondelete="SET NULL"), nullable=True, index=True)

    # Almacén de origen de la orden
    # NULL = No asignado a almacén específico
    almacen_id = Column(Integer, ForeignKey("almacenes.id", ondelete="SET NULL"), nullable=True, index=True)

    type = Column(String(10), nullable=False, index=True)
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
    # Prioridad de la orden: LOW, NORMAL, HIGH, URGENT
    # Determina el orden en que se procesan las órdenes
    prioridad = Column(String(20), default='NORMAL', nullable=False, index=True)
    
    # Caja actualmente OPEN (recibiendo items)
    # NULL = No hay caja abierta
    # NOT NULL = ID de la caja actual donde se están empacando items
    # Solo puede haber UNA caja activa por orden
    caja_activa_id = Column(
        Integer,
        ForeignKey("packing_boxes.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # === CONTADORES (desnormalizados para performance) ===
    # Total de UNIDADES solicitadas en la orden (suma de cantidad_solicitada de todas las líneas)
    # Ejemplo: 3 líneas con cantidades [5, 10, 3] = total_items: 18
    # Se calcula al importar y evita hacer SUM(cantidad_solicitada) constantemente
    total_items = Column(Integer, default=0, nullable=False)
    
    # Cuántas UNIDADES han sido servidas hasta ahora (suma de cantidad_servida de todas las líneas)
    # Ejemplo: 3 líneas con cantidades servidas [5, 7, 3] = items_completados: 15
    # Permite calcular progreso rápidamente: items_completados/total_items * 100
    items_completados = Column(Integer, default=0, nullable=False)
    
    # === METADATOS ===
    # Notas o comentarios adicionales sobre la orden
    notas = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    status = relationship("OrderStatus", back_populates="orders", foreign_keys=[status_id])
    operator = relationship("Operator", back_populates="orders")
    almacen = relationship("Almacen", back_populates="orders")
    order_lines = relationship("OrderLine", back_populates="order", cascade="all, delete-orphan")
    history = relationship("OrderHistory", back_populates="order", cascade="all, delete-orphan")
    
    # Relación con cajas de embalaje
    packing_boxes = relationship("PackingBox", back_populates="order", cascade="all, delete-orphan", foreign_keys="[PackingBox.order_id]")
    # Caja actualmente abierta (relación especial, sin cascade)
    caja_activa = relationship("PackingBox", foreign_keys=[caja_activa_id], post_update=True)

    __table_args__ = (
        Index('idx_status_operator', 'status_id', 'operator_id'),
        Index('idx_status_fecha', 'status_id', 'fecha_orden'),
        Index('idx_fecha_importacion', 'fecha_importacion'),
    )


class PackingBox(Base):
    """
    Cajas de embalaje para órdenes de picking.
    
    Representa una caja física donde se colocan los items durante el proceso
    de picking. El flujo es dinámico:
    
    1. Al iniciar picking → Se crea automáticamente la Caja #1 (estado OPEN)
    2. Operario escanea items → Se asignan a la caja activa
    3. Caja se llena → Operario la cierra (estado CLOSED)
    4. Necesita más espacio → Se abre automáticamente Caja #2
    5. Repite hasta completar la orden
    
    Una orden puede tener N cajas. Cada caja tiene un código único escaneable
    para trazabilidad en el proceso de envío.
    
    Estados:
    - OPEN: Caja abierta, recibiendo items (solo 1 por orden)
    - CLOSED: Caja cerrada, lista para envío
    - SHIPPED: Caja enviada al cliente
    """
    __tablename__ = "packing_boxes"

    id = Column(Integer, primary_key=True, index=True)
    
    # Orden a la que pertenece esta caja
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # === IDENTIFICACIÓN ===
    # Número secuencial de la caja dentro de la orden (1, 2, 3...)
    # Se incrementa automáticamente al crear nueva caja
    numero_caja = Column(Integer, nullable=False)
    
    # Código único escaneable para identificar la caja
    # Formato: "ORD-{numero_orden}-BOX-{numero_caja:03d}"
    # Ejemplo: "ORD-12345-BOX-001", "ORD-12345-BOX-002"
    # Permite escanear la caja para asociar productos o rastrear envíos
    codigo_caja = Column(String(150), unique=True, nullable=False, index=True)
    
    # === ESTADO Y CONTROL ===
    # Estado actual de la caja: OPEN, CLOSED, SHIPPED
    # Solo puede haber UNA caja OPEN por orden
    estado = Column(String(20), default='OPEN', nullable=False, index=True)
    
    # Operario que está/estuvo empacando en esta caja
    # Normalmente es el mismo operario asignado a la orden
    operator_id = Column(Integer, ForeignKey("operators.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # === CARACTERÍSTICAS FÍSICAS (Opcionales) ===
    # Peso de la caja en kilogramos
    # Se puede registrar al cerrar la caja (con báscula)
    peso_kg = Column(Float, nullable=True)
    
    # Dimensiones de la caja en formato texto
    # Ejemplo: "40x30x20 cm", "50x40x35"
    dimensiones = Column(String(50), nullable=True)
    
    # === CONTADOR DESNORMALIZADO ===
    # Total de items (order_lines) asignados a esta caja
    # Se incrementa cada vez que se empaca un item
    # Permite saber rápidamente si la caja está vacía o cuántos items tiene
    total_items = Column(Integer, default=0, nullable=False)
    
    # === FECHAS DE CONTROL ===
    # Cuándo se abrió/creó la caja
    fecha_apertura = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Cuándo se cerró la caja (NULL si aún está OPEN)
    fecha_cierre = Column(DateTime, nullable=True)
    
    # === METADATOS ===
    # Notas del operario sobre esta caja
    # Ejemplo: "Productos frágiles", "Requiere empaque especial"
    notas = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    order = relationship("Order", back_populates="packing_boxes", foreign_keys=[order_id])
    operator = relationship("Operator", backref="packing_boxes")
    order_lines = relationship("OrderLine", back_populates="packing_box")

    __table_args__ = (
        # No duplicar número de caja en la misma orden
        UniqueConstraint('order_id', 'numero_caja', name='uq_order_numero_caja'),
        # Índice para buscar caja activa de una orden
        Index('idx_order_estado', 'order_id', 'estado'),
        # Índice para búsqueda por código de caja
        Index('idx_codigo_caja', 'codigo_caja'),
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
    
    # === REFERENCIAS NORMALIZADAS (Nueva Arquitectura) ===
    # Referencia al producto en el catálogo normalizado
    # NULL para órdenes históricas importadas antes de la normalización
    # Permite consultar info actualizada del producto (nombre, activo, etc.)
    product_reference_id = Column(
        Integer, 
        ForeignKey("product_references.id", ondelete="NO ACTION"), 
        nullable=True, 
        index=True
    )
    
    # Referencia a la ubicación específica del producto en el almacén
    # NULL para órdenes históricas
    # Permite optimizar rutas de picking y validar stock en tiempo real
    product_location_id = Column(
        Integer, 
        ForeignKey("product_locations.id", ondelete="NO ACTION"), 
        nullable=True, 
        index=True
    )
    
    # === EMPAQUE EN CAJAS ===
    # Caja en la que se empacó este item
    # NULL = Item aún no ha sido empacado en ninguna caja
    # NOT NULL = Item ya está en una caja específica
    # Se asigna durante el proceso de picking cuando el operario coloca el item en la caja
    # IMPORTANTE: ondelete="NO ACTION" para evitar ciclo de cascadas en SQL Server
    # (order_lines -> orders CASCADE, packing_boxes -> orders CASCADE)
    packing_box_id = Column(
        Integer,
        ForeignKey("packing_boxes.id", ondelete="NO ACTION"),
        nullable=True,
        index=True
    )
    
    # Cuándo se empacó este item en la caja
    # NULL si aún no se ha empacado
    # Se registra automáticamente al asignar packing_box_id
    fecha_empacado = Column(DateTime, nullable=True)
    
    # === DATOS MÍNIMOS (para búsquedas rápidas) ===
    # Código de barras EAN del producto - usado para escanear y match rápido
    # Único campo desnormalizado que se mantiene por performance
    ean = Column(String(50), nullable=True, index=True)
    
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
    
    # Relaciones con el catálogo normalizado de productos
    product_reference = relationship("ProductReference", backref="order_lines")
    product_location = relationship("ProductLocation", backref="order_lines")
    
    # Relación con la caja de embalaje
    packing_box = relationship("PackingBox", back_populates="order_lines")

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
class EAN(Base):
    """
    Códigos de barras EAN asociados a productos.
        
    Permite gestionar múltiples códigos EAN para el mismo producto.
    Un producto puede tener varios EANs (diferentes proveedores o presentaciones).
    
    Ejemplo:
    - EAN: "1234567890123" → Producto: Camisa Roja M (Proveedor A)
    - EAN: "9876543210987" → Producto: Camisa Roja M (Proveedor B)
    """
    __tablename__ = "ean"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Código de barras EAN (generalmente 13 dígitos)
    # UNIQUE: Un mismo EAN no puede repetirse en el sistema
    ean = Column(String(13), unique=True, nullable=False, index=True)
    
    # Referencia al producto asociado
    # NULL = EAN sin producto asignado (pendiente de catalogar)
    product_reference_id = Column(
        Integer, 
        ForeignKey("product_references.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )
    
    # Relationships
    product = relationship("ProductReference", back_populates="eans")


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
    nombre_producto = Column(String(200), nullable=False)
    
    # ID del color en el catálogo
    # Puede ser numérico ("000001", "000002") o código ("RED", "BLUE")
    # Se mantiene como string para flexibilidad
    color_id = Column(String(50), nullable=False, index=True)
    
    # Nombre corto del color (ej: "Rojo", "Azul", "Negro")
    color = Column(String(100), nullable=True)
    
    # Talla del producto
    # Ejemplos: "XS", "S", "M", "L", "XL", "XXL", "38", "40", "42"
    talla = Column(String(20), nullable=False, index=True)
    
    # Posición de la talla en el catálogo (para ordenamiento)
    # Ejemplo: "1", "2", "3" para ordenar XS < S < M < L
    posicion_talla = Column(String(50), nullable=True)

    
    # Código de barras EAN del producto
    ean = Column(String(50), nullable=True, index=True)

    # un ean puede tener multiples rf_id y cada rf id es unico
    rf_id = Column(String(70), nullable=True, index=True)
    
    # SKU o código interno del artículo (referencia - color - talla)
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
    
    # Un producto puede tener múltiples códigos EAN
    eans = relationship("EAN", back_populates="product", cascade="all, delete-orphan")

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

class Almacen(Base):
    """
    Almacenes
    """
    __tablename__ = "almacenes"
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(10), nullable=False, index=True)
    descripciones = Column(String(250), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow(), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow(), onupdate=datetime.utcnow(), nullable=False)
    
    # Relationships
    locations = relationship("ProductLocation", back_populates="almacen", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="almacen")


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
    almacen_id = Column(Integer, ForeignKey("almacenes.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("product_references.id", ondelete="CASCADE"), nullable=False)
    
    # === COMPONENTES DE LA UBICACIÓN ===
    
    # Pasillo del almacén (alfanumérico)
    # Ejemplos: "A", "B", "C", "A1", "B2", "C3", "AA", "BB"
    # Permite letras, números y combinaciones
    pasillo = Column(String(10), nullable=True, index=True)
    
    # Lado del pasillo: "IZQUIERDA" o "DERECHA"
    # Se puede usar enum para mayor consistencia
    # Valores permitidos: "IZQUIERDA", "DERECHA", "IZQ", "DER", "L", "R"
    lado = Column(String(20), nullable=True, index=True)
    
    # Ubicación específica dentro del lado
    # Puede ser número ("1", "2", "12") o alfanumérico ("A1", "B3")
    ubicacion = Column(String(20), nullable=True, index=True)
    
    # Altura o nivel vertical
    # Valores típicos: 1, 2, 3, 4, 5
    # 1 = Nivel más bajo (fácil acceso)
    # 5 = Nivel más alto (requiere escalera/elevador)
    altura = Column(Integer, nullable=True, index=True)
    
    # === GESTIÓN DE STOCK ===
    
    # Stock mínimo que debe haber en esta ubicación
    # Cuando el stock actual sea menor, se genera alerta de reposición
    stock_minimo = Column(Integer, default=0, nullable=True)
    
    # Stock actual en esta ubicación específica (opcional)
    # Puede actualizarse con sistema de inventario
    stock_actual = Column(Integer, default=0, nullable=True)
    
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
    almacen = relationship("Almacen", back_populates="locations")
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