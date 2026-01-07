# 📡 Documentación de API - Sistema de Gestión de Órdenes

Esta es la documentación completa de los endpoints disponibles en el sistema de gestión de órdenes y picking.

## 🔗 Base URL

```
http://localhost:8000/api/v1
```

## 🌐 CORS (Cross-Origin Resource Sharing)

El servidor está configurado para aceptar peticiones desde:
- **http://localhost:5173** (Vite/React)
- **http://localhost:3000** (Next.js/React/Otros)

**Configuración:**
- ✅ Credentials habilitado
- ✅ Todos los métodos HTTP permitidos
- ✅ Todos los headers permitidos

Si necesitas agregar más orígenes, edita `src/main.py` en la sección `allow_origins`.

## 📚 Documentación Interactiva

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 📦 Endpoints de Órdenes

### 1. Listar Órdenes

Lista todas las órdenes del sistema con información resumida.

**Endpoint:**
```
GET /api/v1/orders
```

**Parámetros de Query (opcionales):**
| Parámetro | Tipo | Descripción | Ejemplo |
|-----------|------|-------------|---------|
| `skip` | integer | Número de registros a saltar (paginación) | `skip=0` |
| `limit` | integer | Número máximo de registros (1-500) | `limit=100` |
| `prioridad` | string | Filtrar por prioridad | `prioridad=HIGH` |
| `estado_codigo` | string | Filtrar por código de estado | `estado_codigo=PENDING` |

**Valores permitidos para `prioridad`:**
- `NORMAL`
- `HIGH`
- `URGENT`

**Valores permitidos para `estado_codigo`:**
- `PENDING` - Pendiente
- `ASSIGNED` - Asignada
- `IN_PICKING` - En Picking
- `PICKED` - Picking Completado
- `PACKING` - En Empaque
- `READY` - Lista para Envío
- `SHIPPED` - Enviada
- `CANCELLED` - Cancelada

**Respuesta de ejemplo:**
```json
[
  {
    "id": 1,
    "numero_orden": "1111087088",
    "cliente": "K41",
    "nombre_cliente": "K41 - SANTANDER",
    "total_items": 45,
    "operario_asignado": "Juan Pérez",
    "prioridad": "NORMAL",
    "estado": "Asignada",
    "estado_codigo": "ASSIGNED",
    "fecha_orden": "2025-12-15",
    "fecha_importacion": "2025-12-30T03:18:29.033601"
  }
]
```

**Ejemplo de uso:**
```bash
# Listar todas las órdenes
curl http://localhost:8000/api/v1/orders

# Listar órdenes pendientes
curl "http://localhost:8000/api/v1/orders?estado_codigo=PENDING"

# Listar órdenes de alta prioridad (paginado)
curl "http://localhost:8000/api/v1/orders?prioridad=HIGH&skip=0&limit=20"
```

---

### 2. Obtener Detalle de Orden

Obtiene información completa de una orden específica, incluyendo todos sus productos.

**Endpoint:**
```
GET /api/v1/orders/{order_id}
```

**Parámetros de Ruta:**
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `order_id` | integer | ID de la orden |

**Respuesta de ejemplo:**
```json
{
  "id": 1,
  "numero_orden": "1111087088",
  "cliente": "K41",
  "nombre_cliente": "K41 - SANTANDER",
  "fecha_creacion": "2025-12-15",
  "fecha_limite": "Sin fecha límite",
  "total_cajas": "CJ000304449",
  "operario_asignado": "Juan Pérez",
  "estado": "Asignada",
  "estado_codigo": "ASSIGNED",
  "prioridad": "NORMAL",
  "total_items": 45,
  "items_completados": 32,
  "progreso_porcentaje": 71.11,
  "productos": [
    {
      "id": 1,
      "nombre": "Camisa Polo Manga Corta",
      "descripcion": "Negro",
      "color": "000003",
      "talla": "M",
      "ubicacion": "A-12-3",
      "sku": "2523HA02",
      "ean": "8445962763983",
      "cantidad_solicitada": 2,
      "cantidad_servida": 2,
      "estado": "COMPLETED"
    },
    {
      "id": 2,
      "nombre": "Pantalón Vaquero Slim",
      "descripcion": "Azul Oscuro",
      "color": "000010",
      "talla": "32",
      "ubicacion": "B-05-2",
      "sku": "2521PT18",
      "ean": "8445962733320",
      "cantidad_solicitada": 1,
      "cantidad_servida": 0,
      "estado": "PENDING"
    }
  ]
}
```

**Ejemplo de uso:**
```bash
curl http://localhost:8000/api/v1/orders/1
```

**Códigos de respuesta:**
- `200` - Orden encontrada
- `404` - Orden no encontrada

---

### 3. Asignar Operario a Orden

Asigna un operario a una orden específica. Si la orden está en estado `PENDING`, automáticamente cambia a `ASSIGNED`.

**Endpoint:**
```
PUT /api/v1/orders/{order_id}/assign-operator
```

**Parámetros de Ruta:**
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `order_id` | integer | ID de la orden |

**Body (JSON):**
```json
{
  "operator_id": 1
}
```

**Acciones automáticas:**
- ✅ Asigna el operario a la orden
- ✅ Cambia estado de `PENDING` a `ASSIGNED` (si aplica)
- ✅ Registra fecha de asignación
- ✅ Crea entrada en el historial de auditoría
- ✅ Valida que el operario exista y esté activo

**Respuesta:**
Retorna el detalle completo de la orden actualizada (mismo formato que GET /orders/{order_id})

**Ejemplo de uso:**
```bash
curl -X PUT http://localhost:8000/api/v1/orders/1/assign-operator \
  -H "Content-Type: application/json" \
  -d '{"operator_id": 2}'
```

**Códigos de respuesta:**
- `200` - Asignación exitosa
- `404` - Orden u operario no encontrado
- `400` - Operario inactivo

---

### 4. Actualizar Estado de Orden

Actualiza el estado de una orden específica. Registra automáticamente fechas de inicio/fin de picking según el estado.

**Endpoint:**
```
PUT /api/v1/orders/{order_id}/status
```

**Parámetros de Ruta:**
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `order_id` | integer | ID de la orden |

**Body (JSON):**
```json
{
  "estado_codigo": "IN_PICKING",
  "notas": "Operario inició el proceso de picking" // Opcional
}
```

**Estados válidos:**
| Código | Nombre | Descripción |
|--------|--------|-------------|
| `PENDING` | Pendiente | Orden recién importada |
| `ASSIGNED` | Asignada | Operario asignado |
| `IN_PICKING` | En Picking | Recogiendo productos |
| `PICKED` | Picking Completado | Todos los productos recogidos |
| `PACKING` | En Empaque | Empacando la orden |
| `READY` | Lista para Envío | Lista para despachar |
| `SHIPPED` | Enviada | Orden enviada |
| `CANCELLED` | Cancelada | Orden cancelada |

**Acciones automáticas:**
- ✅ Actualiza el estado de la orden
- ✅ Registra `fecha_inicio_picking` cuando cambia a `IN_PICKING`
- ✅ Registra `fecha_fin_picking` cuando cambia a `PICKED`
- ✅ Crea entrada en el historial de auditoría
- ✅ Valida que el estado sea válido
- ✅ No hace nada si el estado es el mismo

**Respuesta:**
Retorna el detalle completo de la orden actualizada (mismo formato que GET /orders/{order_id})

**Ejemplo de uso:**
```bash
# Iniciar picking
curl -X PUT http://localhost:8000/api/v1/orders/1/status \
  -H "Content-Type: application/json" \
  -d '{"estado_codigo": "IN_PICKING", "notas": "Iniciando recogida de productos"}'

# Completar picking
curl -X PUT http://localhost:8000/api/v1/orders/1/status \
  -H "Content-Type: application/json" \
  -d '{"estado_codigo": "PICKED"}'

# Marcar como lista para envío
curl -X PUT http://localhost:8000/api/v1/orders/1/status \
  -H "Content-Type: application/json" \
  -d '{"estado_codigo": "READY", "notas": "Empaque completado"}'
```

**Códigos de respuesta:**
- `200` - Estado actualizado exitosamente
- `404` - Orden no encontrada
- `400` - Estado inválido

---

### 5. Actualizar Prioridad de Orden

Actualiza la prioridad de una orden específica.

**Endpoint:**
```
PUT /api/v1/orders/{order_id}/priority
```

**Parámetros de Ruta:**
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `order_id` | integer | ID de la orden |

**Body (JSON):**
```json
{
  "prioridad": "HIGH",
  "notas": "Cliente VIP - urgente" // Opcional
}
```

**Prioridades válidas:**
| Código | Descripción |
|--------|-------------|
| `NORMAL` | Prioridad normal (por defecto) |
| `HIGH` | Prioridad alta |
| `URGENT` | Prioridad urgente - procesar primero |

**Acciones automáticas:**
- ✅ Actualiza la prioridad de la orden
- ✅ Crea entrada en el historial de auditoría
- ✅ Valida que la prioridad sea válida
- ✅ No hace nada si la prioridad es la misma

**Respuesta:**
Retorna el detalle completo de la orden actualizada (mismo formato que GET /orders/{order_id})

**Ejemplo de uso:**
```bash
# Cambiar a prioridad alta
curl -X PUT http://localhost:8000/api/v1/orders/1/priority \
  -H "Content-Type: application/json" \
  -d '{"prioridad": "HIGH", "notas": "Cliente VIP"}'

# Cambiar a prioridad urgente
curl -X PUT http://localhost:8000/api/v1/orders/1/priority \
  -H "Content-Type: application/json" \
  -d '{"prioridad": "URGENT"}'

# Volver a prioridad normal
curl -X PUT http://localhost:8000/api/v1/orders/1/priority \
  -H "Content-Type: application/json" \
  -d '{"prioridad": "NORMAL"}'
```

**Códigos de respuesta:**
- `200` - Prioridad actualizada exitosamente
- `404` - Orden no encontrada
- `400` - Prioridad inválida

---

## 👷 Endpoints de Operarios

### 6. Listar Operarios

Lista todos los operarios del sistema.

**Endpoint:**
```
GET /api/v1/operators
```

**Parámetros de Query (opcionales):**
| Parámetro | Tipo | Descripción | Ejemplo |
|-----------|------|-------------|---------|
| `activo` | boolean | Filtrar por estado activo/inactivo | `activo=true` |

**Respuesta de ejemplo:**
```json
[
  {
    "id": 1,
    "codigo_operario": "OP001",
    "nombre": "Juan Pérez",
    "activo": true,
    "created_at": "2025-12-30T03:00:00",
    "updated_at": "2025-12-30T03:00:00"
  },
  {
    "id": 2,
    "codigo_operario": "OP002",
    "nombre": "María García",
    "activo": true,
    "created_at": "2025-12-30T03:00:00",
    "updated_at": "2025-12-30T03:00:00"
  }
]
```

**Ejemplo de uso:**
```bash
# Listar todos los operarios
curl http://localhost:8000/api/v1/operators

# Listar solo operarios activos
curl "http://localhost:8000/api/v1/operators?activo=true"

# Listar solo operarios inactivos
curl "http://localhost:8000/api/v1/operators?activo=false"
```

---

### 7. Obtener Detalle de Operario

Obtiene información completa de un operario específico.

**Endpoint:**
```
GET /api/v1/operators/{operator_id}
```

**Parámetros de Ruta:**
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `operator_id` | integer | ID del operario |

**Respuesta de ejemplo:**
```json
{
  "id": 1,
  "codigo_operario": "OP001",
  "nombre": "Juan Pérez",
  "activo": true,
  "created_at": "2025-12-30T03:00:00",
  "updated_at": "2025-12-30T03:00:00"
}
```

**Ejemplo de uso:**
```bash
curl http://localhost:8000/api/v1/operators/1
```

**Códigos de respuesta:**
- `200` - Operario encontrado
- `404` - Operario no encontrado

---

## 🏥 Endpoint de Health Check

### 6. Health Check

Verifica que el servidor está funcionando correctamente.

**Endpoint:**
```
GET /health
```

**Respuesta de ejemplo:**
```json
{
  "status": "ok"
}
```

**Ejemplo de uso:**
```bash
curl http://localhost:8000/health
```

---

## 📊 Resumen de Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/orders` | Lista todas las órdenes (resumido) |
| GET | `/api/v1/orders/{order_id}` | Detalle completo de una orden |
| PUT | `/api/v1/orders/{order_id}/assign-operator` | Asignar operario a orden |
| PUT | `/api/v1/orders/{order_id}/status` | Actualizar estado de orden |
| PUT | `/api/v1/orders/{order_id}/priority` | Actualizar prioridad de orden |
| GET | `/api/v1/operators` | Lista todos los operarios |
| GET | `/api/v1/operators/{operator_id}` | Detalle de un operario |
| GET | `/health` | Health check del servidor |

---

## 🚀 Cómo Iniciar el Servidor

```bash
# Activar entorno virtual
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate  # Windows

# Iniciar servidor en modo desarrollo
uvicorn src.main:app --reload

# Servidor corriendo en:
# - API: http://localhost:8000
# - Docs: http://localhost:8000/docs
```

---

## 🧪 Flujo de Trabajo Típico

### 1. Importar órdenes desde VIEW
```bash
python etl_import_orders.py
```

### 2. Ver órdenes pendientes
```bash
curl "http://localhost:8000/api/v1/orders?estado_codigo=PENDING"
```

### 3. Ver operarios disponibles
```bash
curl "http://localhost:8000/api/v1/operators?activo=true"
```

### 4. Asignar operario a orden
```bash
curl -X PUT http://localhost:8000/api/v1/orders/1/assign-operator \
  -H "Content-Type: application/json" \
  -d '{"operator_id": 1}'
```

### 5. Cambiar prioridad (opcional)
```bash
curl -X PUT http://localhost:8000/api/v1/orders/1/priority \
  -H "Content-Type: application/json" \
  -d '{"prioridad": "HIGH"}'
```

### 6. Iniciar picking
```bash
curl -X PUT http://localhost:8000/api/v1/orders/1/status \
  -H "Content-Type: application/json" \
  -d '{"estado_codigo": "IN_PICKING"}'
```

### 7. Completar picking
```bash
curl -X PUT http://localhost:8000/api/v1/orders/1/status \
  -H "Content-Type: application/json" \
  -d '{"estado_codigo": "PICKED"}'
```

### 8. Ver detalle de la orden
```bash
curl http://localhost:8000/api/v1/orders/1
```

---

## 🔐 Códigos de Estado HTTP

| Código | Descripción |
|--------|-------------|
| 200 | Operación exitosa |
| 404 | Recurso no encontrado |
| 400 | Solicitud inválida (ej: operario inactivo) |
| 422 | Error de validación de datos |
| 500 | Error interno del servidor |

---

## 💡 Notas Importantes

1. **Paginación**: Usa `skip` y `limit` para manejar grandes cantidades de datos
2. **Filtros**: Los filtros son case-insensitive internamente
3. **Historial**: Todas las asignaciones quedan registradas en `order_history`
4. **Estados**: Los cambios de estado son automáticos según las acciones
5. **Validaciones**: El sistema valida que los operarios estén activos antes de asignar
6. **CORS**: Configurado para `localhost:5173` y `localhost:3000`. Edita `src/main.py` para agregar más orígenes

---

## 📞 Soporte

Para más información, consulta:
- `ORDERS_SYSTEM_README.md` - Documentación del sistema completo
- `DATABASE_MODEL_REFERENCE.md` - Referencia del modelo de datos
- http://localhost:8000/docs - Documentación interactiva (Swagger)
