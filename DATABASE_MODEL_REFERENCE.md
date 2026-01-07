# 📚 Referencia del Modelo de Datos - Sistema de Órdenes y Picking

Documentación detallada de todas las tablas, campos y relaciones del sistema.

---

## 📊 Diagrama de Relaciones

```
┌────────────────────┐
│ order_view_cache   │  (Caché de VIEW SQL Server)
└────────────────────┘
         ↓
    [ETL Process]
         ↓
┌────────────────────┐     ┌──────────────┐
│  order_status      │────→│   orders     │
└────────────────────┘     └──────┬───────┘
         ↑                        │
         │                        ├──→ order_lines
         │                        │
         │                        └──→ order_history
         │
┌────────────────────┐
│    operators       │────→ picking_tasks
└────────────────────┘           ↑
                                 │
                          order_lines
```

---

## 🗃️ TABLAS DETALLADAS

### 1. **order_view_cache**
**Propósito:** Caché temporal de datos crudos de la VIEW SQL Server

#### Campos:
| Campo | Tipo | Descripción | Uso |
|-------|------|-------------|-----|
| `id` | INTEGER | PK auto-incremental | Identificador interno |
| `numero_orden` | VARCHAR(100) UNIQUE | Número de orden del sistema externo | Usado para detectar duplicados |
| `raw_data` | JSON | Snapshot completo de la fila | Datos tal como vienen de la VIEW |
| `fecha_importacion` | DATETIME | Cuándo se consultó | Tracking de actualizaciones |
| `procesado` | BOOLEAN | Si ya se normalizó | `false` = pendiente, `true` = procesada |
| `created_at` | DATETIME | Timestamp de creación | Auditoría |

#### Índices:
- `numero_orden` (UNIQUE)
- `procesado` (para filtrar pendientes)
- `(numero_orden, procesado)` (compuesto)

#### Uso:
```python
# Detectar órdenes nuevas
nuevas = db.query(OrderViewCache)\
    .filter_by(procesado=False)\
    .filter(OrderViewCache.numero_orden.notin_(
        db.query(Order.numero_orden)
    ))\
    .all()
```

---

### 2. **order_status**
**Propósito:** Catálogo de estados del ciclo de vida

#### Campos:
| Campo | Tipo | Descripción | Valores |
|-------|------|-------------|---------|
| `id` | INTEGER | PK auto-incremental | 1-8 |
| `codigo` | VARCHAR(50) UNIQUE | Código del estado | PENDING, ASSIGNED, etc. |
| `nombre` | VARCHAR(100) | Nombre legible | "Pendiente", "Asignada" |
| `descripcion` | TEXT | Descripción detallada | Explicación del estado |
| `orden` | INTEGER | Secuencia lógica | 10, 20, 30... 99 |
| `activo` | BOOLEAN | Si está disponible | Permite deshabilitar |

#### Estados Predefinidos:
```
┌──────────┬────────────────────────┬───────┐
│ Código   │ Nombre                 │ Orden │
├──────────┼────────────────────────┼───────┤
│ PENDING  │ Pendiente              │  10   │
│ ASSIGNED │ Asignada               │  20   │
│ IN_PICKING│ En Picking            │  30   │
│ PICKED   │ Picking Completado     │  40   │
│ PACKING  │ En Empaque             │  50   │
│ READY    │ Lista para Envío       │  60   │
│ SHIPPED  │ Enviada                │  70   │
│ CANCELLED│ Cancelada              │  99   │
└──────────┴────────────────────────┴───────┘
```

#### Uso:
```python
# Obtener estado por código
pending = db.query(OrderStatus).filter_by(codigo="PENDING").first()

# Validar transición lógica
if new_status.orden > current_status.orden:
    # Transición válida (avanza)
    pass
```

---

### 3. **operators**
**Propósito:** Operarios del almacén

#### Campos:
| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `id` | INTEGER | PK auto-incremental | 1, 2, 3... |
| `codigo_operario` | VARCHAR(50) UNIQUE | Código del operario | "OP001", "OP002" |
| `nombre` | VARCHAR(100) | Nombre completo | "Juan Pérez" |
| `activo` | BOOLEAN | Si está disponible | true = trabajando |
| `created_at` | DATETIME | Fecha de creación | |
| `updated_at` | DATETIME | Última actualización | |

#### Relaciones:
- **1:N** con `orders` (un operario tiene muchas órdenes)
- **1:N** con `picking_tasks` (un operario tiene muchas tareas)
- **1:N** con `order_history` (registro de acciones)

#### Uso:
```python
# Operarios activos disponibles
operarios = db.query(Operator)\
    .filter_by(activo=True)\
    .all()

# Órdenes asignadas a un operario
ordenes = db.query(Order)\
    .filter_by(operator_id=operario.id)\
    .filter(Order.status_id.in_([...]))\
    .all()
```

---

### 4. **orders**
**Propósito:** Órdenes principales (headers)

#### Campos Principales:

##### **Identificación**
- `id`: INTEGER PK - ID interno
- `numero_orden`: VARCHAR(100) UNIQUE - Número del sistema externo

##### **Cliente (desnormalizado)**
- `cliente`: VARCHAR(100) - Código del cliente
- `nombre_cliente`: VARCHAR(200) - Nombre para UI

##### **Referencias**
- `status_id`: FK → order_status - Estado actual
- `operator_id`: FK → operators (nullable) - Operario asignado

##### **Fechas de Control**
- `fecha_orden`: DATE - Fecha de creación original
- `fecha_importacion`: DATETIME - Cuándo se importó
- `fecha_asignacion`: DATETIME (nullable) - Cuándo se asignó
- `fecha_inicio_picking`: DATETIME (nullable) - Inicio de picking
- `fecha_fin_picking`: DATETIME (nullable) - Fin de picking

##### **Información Adicional**
- `caja`: VARCHAR(50) - Número de caja
- `prioridad`: VARCHAR(20) - LOW, NORMAL, HIGH, URGENT

##### **Contadores (denormalizados)**
- `total_items`: INTEGER - Total de líneas
- `items_completados`: INTEGER - Líneas completadas

##### **Metadatos**
- `notas`: TEXT - Comentarios
- `created_at`, `updated_at`: DATETIME

#### Índices Importantes:
```sql
-- Búsqueda por número de orden
INDEX ON numero_orden

-- Dashboard de órdenes por estado y operario
INDEX ON (status_id, operator_id)

-- Órdenes por fecha
INDEX ON fecha_orden

-- Órdenes importadas hoy
INDEX ON fecha_importacion
```

#### Ejemplo de Uso:
```python
# Crear orden
order = Order(
    numero_orden="ORD-12345",
    cliente="CLI001",
    nombre_cliente="Acme Corp",
    status_id=pending_status.id,
    fecha_orden=date.today(),
    prioridad="HIGH",
    total_items=0  # Se incrementa al agregar líneas
)

# Dashboard de órdenes activas
active_orders = db.query(Order)\
    .join(OrderStatus)\
    .filter(OrderStatus.codigo.in_(['ASSIGNED', 'IN_PICKING']))\
    .order_by(Order.prioridad.desc())\
    .all()
```

---

### 5. **order_lines**
**Propósito:** Líneas individuales de productos

#### Campos de Producto (todos desnormalizados):
- `ean`: VARCHAR(50) - Código de barras
- `ubicacion`: VARCHAR(100) - Ubicación en almacén
- `articulo`: VARCHAR(100) - SKU/código de artículo
- `color`: VARCHAR(100) - Color del producto
- `talla`: VARCHAR(50) - Talla
- `posicion_talla`: VARCHAR(50) - Orden de tallas
- `descripcion_producto`: TEXT - Descripción
- `descripcion_color`: VARCHAR(200) - Descripción del color
- `temporada`: VARCHAR(50) - Temporada

#### Cantidades:
- `cantidad_solicitada`: INTEGER - Pedidas
- `cantidad_servida`: INTEGER - Recogidas

#### Estado:
- `estado`: VARCHAR(20)
  - `PENDING` - No iniciada
  - `PARTIAL` - Parcialmente recogida
  - `COMPLETED` - Completada

#### Relaciones:
- **N:1** con `orders` (muchas líneas por orden)
- **1:N** con `picking_tasks` (una tarea por línea)

#### Ejemplo:
```python
# Agregar línea a orden
line = OrderLine(
    order_id=order.id,
    ean="1234567890123",
    ubicacion="A-10-2",
    articulo="CAM-001-R-M",
    color="Rojo",
    talla="M",
    descripcion_producto="Camisa Polo Manga Corta",
    cantidad_solicitada=5,
    estado="PENDING"
)

# Líneas pendientes de una orden
pending_lines = db.query(OrderLine)\
    .filter_by(order_id=order_id, estado="PENDING")\
    .all()
```

---

### 6. **order_history**
**Propósito:** Auditoría completa de eventos

#### Campos:
- `order_id`: FK → orders
- `status_id`: FK → order_status - Estado en ese momento
- `operator_id`: FK → operators (nullable) - Quién causó el evento
- `accion`: VARCHAR(50) - Tipo de evento
- `status_anterior`: FK → order_status (nullable)
- `status_nuevo`: FK → order_status (nullable)
- `fecha`: DATETIME - Timestamp del evento
- `notas`: TEXT - Descripción
- `event_metadata`: JSON - Datos adicionales

#### Tipos de Acción:
```
IMPORTED_FROM_VIEW  - Orden recién importada
STATUS_CHANGE       - Cambio de estado
ASSIGNED            - Asignada a operario
UNASSIGNED          - Desasignada
PICKING_STARTED     - Inicio de picking
PICKING_COMPLETED   - Fin de picking
NOTE_ADDED          - Nota agregada
CANCELLED           - Cancelación
```

#### Ejemplo:
```python
# Registrar evento
history = OrderHistory(
    order_id=order.id,
    status_id=new_status.id,
    operator_id=operator.id,
    accion="STATUS_CHANGE",
    status_anterior=old_status.id,
    status_nuevo=new_status.id,
    fecha=datetime.now(),
    notas="Estado cambiado por supervisor",
    event_metadata={
        "tiempo_en_estado_anterior_min": 25,
        "razon": "Urgente"
    }
)

# Timeline de una orden
history = db.query(OrderHistory)\
    .filter_by(order_id=order_id)\
    .order_by(OrderHistory.fecha.desc())\
    .all()
```

---

### 7. **picking_tasks**
**Propósito:** Tareas granulares de picking

#### Campos:
- `order_line_id`: FK → order_lines
- `operator_id`: FK → operators
- `ubicacion`: VARCHAR(100) - Desnormalizada para acceso rápido
- `cantidad_a_recoger`: INTEGER
- `cantidad_recogida`: INTEGER
- `estado`: VARCHAR(20) - PENDING, IN_PROGRESS, COMPLETED, FAILED, SKIPPED
- `secuencia`: INTEGER - Orden en ruta optimizada
- `prioridad`: INTEGER - 1-5
- `fecha_inicio`: DATETIME
- `fecha_fin`: DATETIME
- `tiempo_estimado_seg`: INTEGER
- `tiempo_real_seg`: INTEGER
- `intentos`: INTEGER
- `notas`: TEXT

#### Ejemplo de Flujo:
```python
# 1. Crear tareas al asignar orden
for line in order.order_lines:
    task = PickingTask(
        order_line_id=line.id,
        operator_id=operator.id,
        ubicacion=line.ubicacion,
        cantidad_a_recoger=line.cantidad_solicitada,
        secuencia=calculate_sequence(line.ubicacion),
        estado="PENDING"
    )
    db.add(task)

# 2. Operario inicia tarea
task.estado = "IN_PROGRESS"
task.fecha_inicio = datetime.now()

# 3. Operario completa tarea
task.estado = "COMPLETED"
task.fecha_fin = datetime.now()
task.cantidad_recogida = task.cantidad_a_recoger
task.tiempo_real_seg = (task.fecha_fin - task.fecha_inicio).total_seconds()

# 4. Actualizar línea de orden
line.cantidad_servida += task.cantidad_recogida
if line.cantidad_servida == line.cantidad_solicitada:
    line.estado = "COMPLETED"
```

---

## 📈 Consultas Comunes

### Dashboard de Supervisor
```python
# Resumen por estado
summary = db.query(
    OrderStatus.nombre,
    func.count(Order.id).label('total')
)\
.join(Order, Order.status_id == OrderStatus.id)\
.group_by(OrderStatus.id)\
.all()
```

### Performance de Operarios
```python
# Últimos 7 días
stats = db.query(
    Operator.nombre,
    func.count(func.distinct(Order.id)).label('ordenes'),
    func.count(PickingTask.id).label('tareas'),
    func.avg(PickingTask.tiempo_real_seg).label('tiempo_prom')
)\
.join(PickingTask)\
.join(OrderLine)\
.join(Order)\
.filter(PickingTask.estado == 'COMPLETED')\
.filter(PickingTask.fecha_fin >= date.today() - timedelta(days=7))\
.group_by(Operator.id)\
.all()
```

### Próxima Tarea del Operario
```python
next_task = db.query(PickingTask)\
    .filter_by(operator_id=op_id, estado='PENDING')\
    .order_by(PickingTask.secuencia.asc())\
    .first()
```

---

## 🔒 Reglas de Negocio

### Constraints:
1. ✅ `orden.numero_orden` debe ser único
2. ✅ `orden.items_completados` ≤ `orden.total_items`
3. ✅ `order_line.cantidad_servida` ≤ `cantidad_solicitada`
4. ✅ `picking_task.cantidad_recogida` ≤ `cantidad_a_recoger`
5. ✅ Si `orden.operator_id` es NULL → estado debe ser PENDING
6. ✅ Fechas: `asignacion` ≥ `orden`, `inicio_picking` ≥ `asignacion`, etc.

### Triggers Recomendados:
1. **AFTER INSERT order_line** → Incrementar `order.total_items`
2. **AFTER UPDATE order_line** → Si `estado` = COMPLETED → Incrementar `order.items_completados`
3. **AFTER UPDATE order** → Si `status_id` cambia → Crear `order_history`
4. **AFTER UPDATE picking_task** → Si COMPLETED → Actualizar `order_line.cantidad_servida`

---

## 📝 Mejores Prácticas

1. **Siempre usar transacciones** para operaciones multi-tabla
2. **No modificar** `order_view_cache.raw_data` después de insertar
3. **No borrar** registros de `order_history` (tabla append-only)
4. **Calcular** `tiempo_real_seg` antes de setear `estado=COMPLETED`
5. **Validar** transiciones de estado antes de actualizar
6. **Usar** índices compuestos para queries frecuentes
7. **Denormalizar** cuando mejore performance significativamente

---

**Última actualización:** 2025-12-29  
**Versión:** 1.0.0
