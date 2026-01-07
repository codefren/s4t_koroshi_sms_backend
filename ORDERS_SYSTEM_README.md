# 📦 Sistema de Gestión de Órdenes y Picking

Sistema completo para gestionar órdenes de almacén, asignación a operarios y seguimiento de picking.

## 🏗️ Arquitectura del Sistema

```
┌─────────────────────────────────────┐
│   SQL Server (Sistema Externo)      │
│   VIEW: orders_view (READ-ONLY)     │
└─────────────────────────────────────┘
                ↓
         [Consulta 1x día]
                ↓
┌─────────────────────────────────────┐
│   Proceso ETL (etl_import_orders.py)│
└─────────────────────────────────────┘
                ↓
┌─────────────────────────────────────┐
│   Base de Datos Local                │
│   - orders                           │
│   - order_lines                      │
│   - operators                        │
│   - picking_tasks                    │
│   - order_history                    │
└─────────────────────────────────────┘
                ↓
┌─────────────────────────────────────┐
│   API REST + WebSockets              │
│   (Frontend para operarios)          │
└─────────────────────────────────────┘
```

## 📊 Modelo de Datos

### Tablas Principales

#### 1. **order_view_cache**
Caché de la VIEW de SQL Server para detectar órdenes nuevas.

```python
- numero_orden (UNIQUE)      # Identificador de la orden
- raw_data (JSON)            # Datos completos de la VIEW
- procesado (BOOLEAN)        # Si ya fue normalizada
- fecha_importacion          # Cuándo se consultó
```

#### 2. **order_status**
Catálogo de estados del ciclo de vida de una orden.

```python
Estados disponibles:
- PENDING          # Recién importada, sin asignar
- ASSIGNED         # Asignada a operario
- IN_PICKING       # En proceso de recolección
- PICKED           # Picking completado
- PACKING          # En empaque
- READY            # Lista para envío
- SHIPPED          # Enviada
- CANCELLED        # Cancelada
```

#### 3. **operators**
Operarios del almacén.

```python
- codigo_operario (UNIQUE)   # Código del operario
- nombre                     # Nombre completo
- activo (BOOLEAN)           # Si está disponible
```

#### 4. **orders**
Órdenes principales agrupadas por numero_orden.

```python
- numero_orden (UNIQUE)      # Del sistema externo
- cliente                    # Código del cliente
- nombre_cliente             # Nombre del cliente
- status_id                  # Estado actual
- operator_id                # Operario asignado
- fecha_orden                # Fecha de creación
- fecha_importacion          # Cuándo se importó
- fecha_asignacion           # Cuándo se asignó
- fecha_inicio_picking       # Inicio de picking
- fecha_fin_picking          # Fin de picking
- caja                       # Número de caja
- prioridad                  # LOW, NORMAL, HIGH, URGENT
- total_items                # Número de líneas
- items_completados          # Líneas completadas
```

#### 5. **order_lines**
Líneas individuales de cada orden (productos desnormalizados).

```python
- order_id                   # FK a orders
- ean                        # Código de barras
- ubicacion                  # Ubicación en almacén
- articulo                   # Código de artículo
- color                      # Color del producto
- talla                      # Talla
- descripcion_producto       # Descripción
- cantidad_solicitada        # Cantidad pedida
- cantidad_servida           # Cantidad recogida
- estado                     # PENDING, PARTIAL, COMPLETED
```

#### 6. **order_history**
Historial de todos los cambios de estado y eventos.

```python
- order_id                   # FK a orders
- status_id                  # Estado en ese momento
- operator_id                # Quién hizo el cambio
- accion                     # Tipo de acción
- fecha                      # Timestamp del evento
- notas                      # Descripción
- event_metadata (JSON)      # Datos adicionales
```

**Uso de event_metadata (JSON):**
```json
{
  "items_picked": 5,
  "tiempo_picking_minutos": 25,
  "razon_cancelacion": "Stock insuficiente",
  "caja_asignada": "C-001"
}
```

#### 7. **picking_tasks**
Tareas granulares de picking para operarios.

```python
- order_line_id              # FK a order_lines
- operator_id                # FK a operators
- ubicacion                  # Dónde ir a recoger
- cantidad_a_recoger         # Cantidad objetivo
- cantidad_recogida          # Cantidad actual
- estado                     # PENDING, IN_PROGRESS, COMPLETED
- secuencia                  # Orden en ruta optimizada
- fecha_inicio               # Inicio de la tarea
- fecha_fin                  # Fin de la tarea
```

## 🚀 Instalación y Configuración

### 1. Inicializar el Sistema

```bash
# Crear las tablas y cargar datos semilla
python init_order_system.py
```

Este script:
- ✅ Crea todas las tablas necesarias
- ✅ Carga los 8 estados de órdenes
- ✅ Opcionalmente crea operarios de ejemplo
- ✅ Muestra resumen del sistema

### 2. Configurar Conexión a SQL Server

Edita tu archivo `.env`:

```env
# Conexión a SQL Server (Sistema externo)
ODBC_DRIVER={ODBC Driver 17 for SQL Server}
ODBC_SERVER=your-server.database.windows.net
ODBC_DATABASE=your_database
ODBC_USERNAME=your_user
ODBC_PASSWORD=your_password

# Base de datos local
DATABASE_URL=sqlite:///./warehouse.db
```

### 3. Ejecutar Importación de Órdenes

```bash
# Importar órdenes desde la VIEW (ejecutar diariamente)
python etl_import_orders.py
```

Este script:
- 📡 Consulta la VIEW de SQL Server
- 💾 Cachea los datos para comparación
- 🔍 Detecta órdenes nuevas (por numero_orden)
- 📦 Normaliza y guarda en tablas locales
- 📊 Genera estadísticas del proceso

### 4. Programar Importación Automática

#### Linux/Mac (crontab)
```bash
# Editar crontab
crontab -e

# Ejecutar todos los días a las 6:00 AM
0 6 * * * cd /path/to/project && python etl_import_orders.py >> logs/etl.log 2>&1
```

#### Windows (Task Scheduler)
1. Abrir "Programador de tareas"
2. Crear tarea básica
3. Trigger: Diario a las 6:00 AM
4. Acción: Ejecutar `python etl_import_orders.py`

## 🔄 Flujo de Trabajo Operativo

### 1. Importación Diaria (6:00 AM)
```
VIEW SQL Server → ETL → Cache → Normalización → orders (PENDING)
```

### 2. Asignación a Operario
```
Dashboard → Supervisor selecciona orden PENDING → 
Asigna operario → Estado: ASSIGNED →
Crea picking_tasks
```

### 3. Proceso de Picking
```
Operario recibe orden → Estado: IN_PICKING →
Por cada picking_task:
  - Ir a ubicación
  - Escanear EAN
  - Confirmar cantidad
  - Estado: COMPLETED →
Todas completadas → Orden: PICKED
```

### 4. Empaque y Envío
```
PICKED → PACKING (asignar caja) →
READY → SHIPPED
```

## 📝 Ejemplos de Uso

### Consultar Órdenes Pendientes

```python
from src.adapters.secondary.database.config import SessionLocal
from src.adapters.secondary.database.orm import Order, OrderStatus

db = SessionLocal()

# Obtener ID del estado PENDING
pending_status = db.query(OrderStatus).filter_by(codigo="PENDING").first()

# Consultar órdenes pendientes
pending_orders = db.query(Order)\
    .filter_by(status_id=pending_status.id)\
    .order_by(Order.fecha_orden.asc())\
    .all()

for order in pending_orders:
    print(f"Orden: {order.numero_orden} - Cliente: {order.nombre_cliente}")
    print(f"  Total ítems: {order.total_items}")
```

### Asignar Orden a Operario

```python
from datetime import datetime

# Buscar orden y operario
order = db.query(Order).filter_by(numero_orden="ORD-12345").first()
operator = db.query(Operator).filter_by(codigo_operario="OP001").first()

# Obtener estado ASSIGNED
assigned_status = db.query(OrderStatus).filter_by(codigo="ASSIGNED").first()

# Asignar
order.operator_id = operator.id
order.status_id = assigned_status.id
order.fecha_asignacion = datetime.now()

# Crear picking tasks
for line in order.order_lines:
    task = PickingTask(
        order_line_id=line.id,
        operator_id=operator.id,
        ubicacion=line.ubicacion,
        cantidad_a_recoger=line.cantidad_solicitada,
        estado="PENDING"
    )
    db.add(task)

# Registrar en historial
history = OrderHistory(
    order_id=order.id,
    status_id=assigned_status.id,
    operator_id=operator.id,
    accion="ASSIGNED",
    notas=f"Orden asignada a {operator.nombre}"
)
db.add(history)

db.commit()
```

### Dashboard de Operario

```python
# Tareas pendientes del operario
tasks = db.query(PickingTask)\
    .filter_by(operator_id=operator.id, estado="PENDING")\
    .order_by(PickingTask.secuencia.asc())\
    .all()

for task in tasks:
    line = task.order_line
    print(f"Ubicación: {task.ubicacion}")
    print(f"  Artículo: {line.articulo}")
    print(f"  Cantidad: {task.cantidad_a_recoger}")
    print(f"  EAN: {line.ean}")
```

## 🔍 Queries Útiles

### Órdenes por Estado
```sql
SELECT 
    os.nombre as estado,
    COUNT(*) as total_ordenes,
    SUM(o.total_items) as total_items
FROM orders o
JOIN order_status os ON o.status_id = os.id
GROUP BY os.nombre
ORDER BY os.orden;
```

### Performance de Operarios (Últimos 7 días)
```sql
SELECT 
    op.nombre,
    COUNT(DISTINCT o.id) as ordenes_completadas,
    COUNT(pt.id) as tareas_completadas,
    AVG(pt.tiempo_real_seg) as tiempo_promedio_seg
FROM operators op
JOIN picking_tasks pt ON op.id = pt.operator_id
JOIN order_lines ol ON pt.order_line_id = ol.id
JOIN orders o ON ol.order_id = o.id
WHERE pt.estado = 'COMPLETED'
  AND pt.fecha_fin >= DATE('now', '-7 days')
GROUP BY op.id
ORDER BY ordenes_completadas DESC;
```

### Historial de una Orden
```sql
SELECT 
    oh.fecha,
    oh.accion,
    os.nombre as estado,
    op.nombre as operario,
    oh.notas
FROM order_history oh
LEFT JOIN order_status os ON oh.status_id = os.id
LEFT JOIN operators op ON oh.operator_id = op.id
WHERE oh.order_id = ?
ORDER BY oh.fecha DESC;
```

## 🎯 Próximos Pasos

### Backend
- [ ] Implementar endpoints REST para:
  - Gestión de órdenes (listar, detalle, actualizar)
  - Gestión de operarios (CRUD)
  - Asignación de órdenes
  - Actualización de picking tasks
  - Historial y reportes
- [ ] WebSockets para actualización en tiempo real
- [ ] Sistema de notificaciones
- [ ] Generación de reportes PDF

### Frontend
- [ ] Dashboard de supervisor
- [ ] Aplicación móvil/web para operarios
- [ ] Escaneo de códigos de barras
- [ ] Visualización de rutas de picking
- [ ] Estadísticas en tiempo real

### Optimizaciones
- [ ] Algoritmo de optimización de rutas de picking
- [ ] Cache de queries frecuentes
- [ ] Índices adicionales según patrones de uso
- [ ] Particionado de tablas históricas

## 📚 Documentación Técnica

### Modelos SQLAlchemy
Los modelos ORM están en:
```
src/adapters/secondary/database/orm.py
```

### Modelos Pydantic
Los schemas de validación están en:
```
src/core/domain/models.py
```

### Configuración de Base de Datos
```
src/adapters/secondary/database/config.py
```

## 🐛 Troubleshooting

### Error: "Tabla no existe"
```bash
# Ejecutar script de inicialización
python init_order_system.py
```

### Error: "Estado PENDING no encontrado"
```bash
# Verificar que los estados fueron cargados
python -c "from src.adapters.secondary.database.config import SessionLocal; \
from src.adapters.secondary.database.orm import OrderStatus; \
db = SessionLocal(); \
print(db.query(OrderStatus).count())"
```

### Órdenes Duplicadas
El sistema previene duplicados verificando `numero_orden`. Si aparecen duplicados:
1. Verificar que `numero_orden` sea UNIQUE en la BD
2. Revisar logs del ETL
3. Limpiar cache: `DELETE FROM order_view_cache WHERE procesado = 0`

## 📞 Soporte

Para preguntas o issues, revisar:
- Logs del ETL: `logs/etl.log`
- Estado de las tablas: `python init_order_system.py` (mostrar resumen)
- Documentación de SQLAlchemy: https://docs.sqlalchemy.org/

---

**Última actualización:** 2025-12-29
**Versión:** 1.0.0
