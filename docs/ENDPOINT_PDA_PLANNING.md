# 📱 Planificación: Endpoint PDA para Operadores

**Fecha:** 2026-01-07  
**Arquitectura:** Híbrida REST + WebSocket  
**Objetivo:** API para que operadores consulten (REST) y actualicen (WebSocket) order lines desde dispositivos PDA en tiempo real

> **🔔 IMPORTANTE:** Las actualizaciones de cantidades se harán vía **WebSocket** para feedback instantáneo.  
> REST se usa solo para consultas (GET). Ver detalles completos en `ENDPOINT_PDA_WEBSOCKET.md`

---

## 🎯 Casos de Uso

### Escenario Principal
1. **Operario** inicia sesión en PDA con su código (ej: `OP001`)
2. **PDA** consulta órdenes asignadas al operario
3. **Operario** selecciona una orden y ve lista de productos a recoger
4. **Operario** va a cada ubicación, escanea producto, y marca como completado
5. **Sistema** actualiza progreso en tiempo real

### Flujo de Trabajo
```
┌─────────────┐
│  Operario   │
│   Login     │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│ GET órdenes         │
│ asignadas           │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ GET líneas de       │
│ orden específica    │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Operario recoge     │
│ producto            │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ PUT actualizar      │
│ cantidad recogida   │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Repetir hasta       │
│ completar orden     │
└─────────────────────┘
```

---

## 🛣️ Endpoints Propuestos

### 1. GET `/api/v1/operators/{operator_id}/orders` 
**Descripción:** Lista todas las órdenes asignadas a un operario

**Parámetros:**
- `operator_id` (path, int): ID del operario
- `estado` (query, string, opcional): Filtrar por estado (ASSIGNED, IN_PICKING, PICKED)
- `prioridad` (query, string, opcional): Filtrar por prioridad (URGENT, HIGH, NORMAL)

**Respuesta:**
```json
{
  "operator_id": 1,
  "operator_name": "Juan Pérez",
  "total_orders": 3,
  "orders": [
    {
      "order_id": 123,
      "numero_orden": "ORD1001",
      "cliente": "Tienda Centro",
      "estado": "IN_PICKING",
      "prioridad": "HIGH",
      "total_items": 15,
      "items_completados": 8,
      "progreso_porcentaje": 53.33,
      "fecha_asignacion": "2026-01-07T10:30:00"
    }
  ]
}
```

---

### 2. GET `/api/v1/operators/{operator_id}/orders/{order_id}/lines` ⭐ **PRINCIPAL**
**Descripción:** Lista todas las líneas (productos) de una orden específica para el operario

**Parámetros:**
- `operator_id` (path, int): ID del operario
- `order_id` (path, int): ID de la orden
- `estado` (query, string, opcional): Filtrar por estado (PENDING, COMPLETED)
- `ordenar_por` (query, string, opcional): 
  - `ubicacion` (default): Agrupa por pasillo/ubicación
  - `secuencia`: Orden optimizado de picking
  - `prioridad`: Productos más urgentes primero

**Respuesta:**
```json
{
  "order_id": 123,
  "numero_orden": "ORD1001",
  "operator_id": 1,
  "estado_orden": "IN_PICKING",
  "total_lines": 15,
  "lines_completed": 8,
  "progreso_porcentaje": 53.33,
  "lines": [
    {
      "line_id": 456,
      "secuencia": 1,
      
      // === PRODUCTO ===
      "producto": {
        "nombre": "Camisa Polo Manga Corta",
        "referencia": "A1B2C3",
        "color": "Rojo",
        "talla": "M",
        "ean": "8445962763983",
        "sku": "2523HA02"
      },
      
      // === UBICACIÓN ===
      "ubicacion": {
        "codigo": "A-IZQ-12-H2",
        "pasillo": "A",
        "lado": "IZQUIERDA",
        "altura": 2,
        "stock_disponible": 45
      },
      
      // === CANTIDADES ===
      "cantidad_solicitada": 5,
      "cantidad_servida": 3,
      "cantidad_pendiente": 2,
      
      // === ESTADO ===
      "estado": "PARTIAL",
      "puede_escanear": true,
      
      // === METADATA ===
      "tiempo_estimado_seg": 120,
      "prioridad": 3
    }
  ],
  
  // === RESUMEN POR PASILLO ===
  "resumen_pasillos": [
    {
      "pasillo": "A",
      "total_items": 8,
      "items_completados": 5,
      "ubicaciones": ["A-IZQ-12-H2", "A-DER-14-H2"]
    },
    {
      "pasillo": "B3",
      "total_items": 7,
      "items_completados": 3,
      "ubicaciones": ["B3-DER-05-H1"]
    }
  ]
}
```

---

### 3. WebSocket `/ws/operators/{operator_id}` - PICK_ITEM ⭐
**Descripción:** Actualizar cantidad recogida vía WebSocket en tiempo real

**🔔 CAMBIO IMPORTANTE:** Este endpoint ya NO es REST PUT, ahora es **WebSocket**

**Conexión:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/operators/1?token=...');
```

**Mensaje (Cliente → Server):**
```json
{
  "action": "pick_item",
  "timestamp": "2026-01-07T13:00:00Z",
  "data": {
    "order_id": 123,
    "line_id": 456,
    "cantidad_recogida": 5,
    "ean_escaneado": "8445962763983",
    "ubicacion_escaneada": "A-IZQ-12-H2",
    "notas": ""
  }
}
```

**Respuesta (Server → Cliente):**
```json
{
  "action": "pick_confirmed",
  "timestamp": "2026-01-07T13:00:05Z",
  "data": {
    "line_id": 456,
    "estado_anterior": "PENDING",
    "estado_nuevo": "COMPLETED",
    "cantidad_solicitada": 5,
    "cantidad_servida": 5,
    "progreso_orden": {
      "order_id": 123,
      "total_items": 15,
      "items_completados": 9,
      "progreso_porcentaje": 60.0
    },
    "siguiente_producto": {
      "line_id": 457,
      "producto": "Pantalón Vaquero Slim",
      "ubicacion": "C-IZQ-08-H3",
      "ean": "8445962733320"
    }
  }
}
```

**Ventajas WebSocket vs REST:**
- ⚡ **10x más rápido** (<50ms vs 500ms)
- 🔄 **Tiempo real** - feedback instantáneo
- 📊 **Broadcast** - supervisores ven cambios en vivo
- 📶 **Menos red** - conexión persistente

**Validaciones (idénticas a REST):**
- ✅ Verificar que el operario está asignado a la orden
- ✅ Verificar que la línea pertenece a una orden del operario
- ✅ Validar EAN si se proporciona
- ✅ No permitir cantidad_recogida > cantidad_solicitada
- ✅ Actualizar automáticamente estado de la línea
- ✅ Actualizar contadores de la orden

**Ver implementación completa:** `ENDPOINT_PDA_WEBSOCKET.md`

---

### 4. POST `/api/v1/operators/{operator_id}/orders/{order_id}/start-picking`
**Descripción:** Marcar inicio de picking de una orden

**Respuesta:**
```json
{
  "order_id": 123,
  "estado_anterior": "ASSIGNED",
  "estado_nuevo": "IN_PICKING",
  "fecha_inicio_picking": "2026-01-07T11:30:00",
  "total_items": 15,
  "ruta_optimizada": true
}
```

---

### 5. POST `/api/v1/operators/{operator_id}/orders/{order_id}/complete-picking`
**Descripción:** Marcar finalización de picking de una orden

**Respuesta:**
```json
{
  "order_id": 123,
  "estado_anterior": "IN_PICKING",
  "estado_nuevo": "PICKED",
  "fecha_fin_picking": "2026-01-07T12:45:00",
  "tiempo_total_minutos": 75,
  "items_completados": 15,
  "items_pendientes": 0,
  "completado": true
}
```

---

### 6. GET `/api/v1/operators/{operator_id}/stats` (Bonus)
**Descripción:** Estadísticas del operario

**Respuesta:**
```json
{
  "operator_id": 1,
  "nombre": "Juan Pérez",
  "estadisticas_hoy": {
    "ordenes_completadas": 8,
    "items_recogidos": 156,
    "tiempo_promedio_minutos": 45,
    "eficiencia_porcentaje": 95.5
  },
  "ordenes_activas": 2,
  "ordenes_pendientes": 5
}
```

---

## 📊 Modelo de Datos

### Tablas Involucradas

```sql
-- Principal
orders (id, numero_orden, operator_id, status_id, ...)
order_lines (id, order_id, product_reference_id, product_location_id, ...)
operators (id, codigo_operario, nombre, ...)

-- Referencias
product_references (id, nombre_producto, color, talla, ean, sku, ...)
product_locations (id, codigo_ubicacion, pasillo, lado, altura, stock_actual, ...)

-- Opcional (si se implementa)
picking_tasks (id, order_line_id, operator_id, secuencia, ...)
```

### Relaciones Clave

```
Operator (1) ──┬──> (N) Orders
               │
               └──> (N) PickingTasks

Order (1) ────> (N) OrderLines

OrderLine (1) ──┬──> (1) ProductReference
                │
                └──> (1) ProductLocation
```

---

## 🔒 Seguridad y Validaciones

### Autenticación
```python
# Opción 1: Header con código de operario
headers = {"X-Operator-Code": "OP001"}

# Opción 2: JWT token
headers = {"Authorization": "Bearer <token>"}
```

### Validaciones Críticas

1. **Verificar asignación**
   ```python
   # Verificar que order.operator_id == operator_id del endpoint
   if order.operator_id != operator_id:
       raise HTTPException(403, "Orden no asignada a este operario")
   ```

2. **Validar estado de orden**
   ```python
   # Solo permitir picking si está en estado correcto
   if order.status.codigo not in ["ASSIGNED", "IN_PICKING"]:
       raise HTTPException(400, "Orden en estado incorrecto para picking")
   ```

3. **Validar cantidades**
   ```python
   # No permitir cantidades imposibles
   if cantidad_recogida > line.cantidad_solicitada:
       raise HTTPException(400, "Cantidad excede lo solicitado")
   ```

4. **Validar EAN** (opcional pero recomendado)
   ```python
   # Verificar que el EAN escaneado coincide
   if ean_escaneado and line.ean != ean_escaneado:
       raise HTTPException(400, "EAN no coincide con el producto")
   ```

---

## 🎨 Respuestas de Error

### Formato Estándar
```json
{
  "detail": "Descripción del error",
  "error_code": "OPERATOR_NOT_ASSIGNED",
  "timestamp": "2026-01-07T12:00:00",
  "path": "/api/v1/operators/1/orders/123/lines"
}
```

### Códigos de Error Específicos

| Código | HTTP | Descripción |
|--------|------|-------------|
| `OPERATOR_NOT_FOUND` | 404 | Operario no existe |
| `ORDER_NOT_FOUND` | 404 | Orden no existe |
| `ORDER_NOT_ASSIGNED` | 403 | Orden no asignada al operario |
| `ORDER_WRONG_STATUS` | 400 | Estado de orden incorrecto |
| `LINE_NOT_FOUND` | 404 | Línea de orden no existe |
| `INVALID_QUANTITY` | 400 | Cantidad inválida |
| `EAN_MISMATCH` | 400 | EAN escaneado no coincide |
| `STOCK_INSUFFICIENT` | 400 | Stock insuficiente |

---

## 🚀 Optimizaciones para PDA

### 1. Respuestas Ligeras
```python
# Solo datos esenciales
# ❌ Evitar: Enviar todo el historial, metadata innecesaria
# ✅ Preferir: Solo lo que el operario necesita ver
```

### 2. Paginación
```python
# GET /api/v1/operators/1/orders/123/lines?limit=10&offset=0
# Para órdenes con muchos items
```

### 3. Compresión
```python
# Usar gzip para reducir payload
# Configurar en FastAPI: compression middleware
```

### 4. Caching
```python
# Cache de 30 segundos para lista de productos
# Cache de 5 segundos para progreso de orden
```

### 5. Offline Support (Frontend)
```javascript
// PDA guarda lista en localStorage
// Permite trabajar sin conexión temporal
// Sincroniza cuando vuelve la conexión
```

---

## 📱 Consideraciones de UX para PDA

### Pantalla Típica de PDA
```
┌─────────────────────────┐
│ ORDEN: ORD1001         │
│ Progreso: 8/15 (53%)   │
├─────────────────────────┤
│                         │
│ 📍 Ubicación: A-IZQ-12 │
│                         │
│ Camisa Polo M Rojo     │
│ EAN: 8445962763983     │
│                         │
│ Solicita: 5            │
│ Recogido: 3            │
│                         │
│ [Escanear]  [Saltar]   │
│                         │
│ Siguiente: C-IZQ-08    │
│                         │
└─────────────────────────┘
```

### Prioridades de Información
1. **Ubicación** (grande, clara)
2. **Producto** (nombre + características)
3. **Cantidad** (pendiente vs completada)
4. **EAN** (para escaneo)
5. **Siguiente ubicación** (optimizar ruta)

---

## 🧪 Casos de Prueba

### Happy Path
```python
# 1. Operario consulta sus órdenes
GET /api/v1/operators/1/orders
✅ Retorna lista de órdenes asignadas

# 2. Operario abre orden específica
GET /api/v1/operators/1/orders/123/lines
✅ Retorna lista de productos ordenada por ubicación

# 3. Operario recoge producto
PUT /api/v1/operators/1/lines/456/pick
Body: {"cantidad_recogida": 5}
✅ Actualiza cantidad, cambia estado a COMPLETED

# 4. Operario completa orden
POST /api/v1/operators/1/orders/123/complete-picking
✅ Marca orden como PICKED
```

### Edge Cases
```python
# 1. Operario intenta acceder a orden de otro
GET /api/v1/operators/1/orders/999/lines
❌ 403 Forbidden

# 2. Operario registra más cantidad de la solicitada
PUT /api/v1/operators/1/lines/456/pick
Body: {"cantidad_recogida": 100}
❌ 400 Bad Request

# 3. EAN escaneado no coincide
PUT /api/v1/operators/1/lines/456/pick
Body: {"cantidad_recogida": 5, "ean_escaneado": "9999999999"}
❌ 400 Bad Request (EAN_MISMATCH)

# 4. Stock insuficiente en ubicación
❌ 400 Bad Request + warning
```

---

## 📝 Resumen de Implementación

### Archivos a Crear/Modificar

```
src/adapters/primary/api/
├── operator_router.py          ← NUEVO (endpoints de operarios)
└── schemas/
    └── operator_schemas.py     ← NUEVO (modelos Pydantic)

src/application/services/
└── picking_service.py          ← NUEVO (lógica de negocio)

tests/
└── test_operator_endpoints.py  ← NUEVO (tests)
```

### Orden de Implementación

1. ✅ **Paso 1:** Crear modelos Pydantic (request/response)
2. ✅ **Paso 2:** Crear `operator_router.py` con endpoints básicos
3. ✅ **Paso 3:** Implementar GET órdenes del operario
4. ✅ **Paso 4:** Implementar GET líneas de orden específica
5. ✅ **Paso 5:** Implementar PUT actualizar cantidad recogida
6. ✅ **Paso 6:** Implementar start/complete picking
7. ✅ **Paso 7:** Agregar validaciones y manejo de errores
8. ✅ **Paso 8:** Escribir tests
9. ✅ **Paso 9:** Documentar en Swagger
10. ✅ **Paso 10:** Probar con cliente PDA simulado

---

## 🎯 Endpoint Principal Recomendado

### **GET `/api/v1/operators/{operator_id}/orders/{order_id}/lines`**

**¿Por qué este es el más importante?**
- ✅ Es el que el operario usa el 90% del tiempo
- ✅ Contiene toda la información necesaria para picking
- ✅ Optimizado para mostrar en pantalla de PDA
- ✅ Incluye resumen por pasillos (ruta optimizada)
- ✅ Soporta diferentes ordenamientos

**Variantes de Ordenamiento:**
```python
# Por ubicación (default) - agrupa por pasillo
GET /api/v1/operators/1/orders/123/lines?ordenar_por=ubicacion

# Por secuencia optimizada (si existe picking_tasks)
GET /api/v1/operators/1/orders/123/lines?ordenar_por=secuencia

# Por prioridad (urgentes primero)
GET /api/v1/operators/1/orders/123/lines?ordenar_por=prioridad
```

---

## ✅ Checklist de Funcionalidades

### MVP (Mínimo Viable)
- [ ] GET órdenes asignadas a operario
- [ ] GET líneas de orden específica (ordenadas)
- [ ] PUT actualizar cantidad recogida
- [ ] Validación de asignación operario-orden
- [ ] Actualización automática de contadores

### Nice to Have
- [ ] POST start-picking (cambio de estado automático)
- [ ] POST complete-picking (cambio de estado automático)
- [ ] Validación de EAN escaneado
- [ ] Validación de ubicación escaneada
- [ ] GET estadísticas del operario
- [ ] Soporte para picking parcial
- [ ] Manejo de productos dañados/faltantes
- [ ] Historial de actividad del operario

---

## 🔄 Integración con Sistema Actual

### Ya Existente (Reutilizar)
- ✅ `Order` model con `operator_id`
- ✅ `OrderLine` model con cantidades
- ✅ `Operator` model
- ✅ `ProductReference` y `ProductLocation`
- ✅ Endpoint de asignar operario

### A Crear
- ⭐ Router específico para operarios
- ⭐ Schemas Pydantic para PDA
- ⭐ Lógica de actualización de picking
- ⭐ Validaciones específicas

---

**Versión:** 1.0  
**Estado:** 📋 Planificación Completa  
**Listo para:** Implementación
