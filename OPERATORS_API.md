# 👷 API de Gestión de Operarios - Documentación Completa

Documentación detallada de los endpoints para la gestión de operarios del almacén en el sistema de picking.

## 📋 Tabla de Contenidos

- [Introducción](#-introducción)
- [⚠️ Advertencias Importantes](#️-advertencias-importantes)
- [Base URL](#-base-url)
- [Modelo de Datos](#-modelo-de-datos)
- [Endpoints Disponibles](#-endpoints-disponibles)
  - [GET - Listar Operarios](#1-listar-operarios)
  - [GET - Obtener Detalle de Operario](#2-obtener-detalle-de-operario)
  - [POST - Crear Operario](#3-crear-operario)
  - [PUT - Actualizar Operario](#4-actualizar-operario)
  - [PATCH - Activar/Desactivar Operario](#5-activardesactivar-operario)
- [Casos de Uso Comunes](#-casos-de-uso-comunes)
- [Códigos de Respuesta](#-códigos-de-respuesta)
- [Relaciones con Otros Módulos](#-relaciones-con-otros-módulos)

---

## 🎯 Introducción

Los operarios son las personas que trabajan en el almacén realizando tareas de picking. Este módulo permite gestionar la información de los operarios, consultar su estado, y asignarlos a órdenes de trabajo.

**Características principales:**
- ✅ Consulta de operarios activos/inactivos
- ✅ Gestión de códigos únicos de operario
- ✅ Sistema de activación/desactivación (soft delete)
- ✅ Integración con sistema de órdenes y tareas de picking
- ✅ Auditoría automática con timestamps

---

## ⚠️ Advertencias Importantes

### 🚨 Limitaciones Actuales del Backend

#### 1. **POST/PUT/PATCH AHORA DISPONIBLES** ✅
- ✅ **ACTUALIZADO**: Todos los endpoints CRUD están implementados
- **POST** `/api/v1/operators/` - Crear operario
- **PUT** `/api/v1/operators/{id}` - Actualizar operario
- **PATCH** `/api/v1/operators/{id}/toggle-status` - Activar/Desactivar
- **Validaciones implementadas:**
  - Códigos de operario únicos
  - Campos requeridos
  - Soft delete (no eliminación física)

#### 2. **Sin Paginación Server-Side**
- La API retorna **todos los registros** en una sola respuesta
- Si hay muchos operarios (>100), la respuesta puede ser pesada
- **Solución**: Implementa paginación client-side:
  ```javascript
  const itemsPerPage = 20;
  const paginatedItems = allOperators.slice(page * itemsPerPage, (page + 1) * itemsPerPage);
  ```

#### 3. **Sin Búsqueda Server-Side**
- No hay parámetros de búsqueda como `?search=Juan`
- La búsqueda debe hacerse **client-side** filtrando el array:
  ```javascript
  const filteredOperators = operators.filter(op => 
    op.nombre.toLowerCase().includes(searchTerm.toLowerCase()) ||
    op.codigo_operario.toLowerCase().includes(searchTerm.toLowerCase())
  );
  ```

#### 4. **Timestamps en UTC**
- Los campos `created_at` y `updated_at` están en **UTC** (sin timezone)
- **Solución**: Convierte a timezone local si es necesario:
  ```javascript
  const localDate = new Date(operator.created_at + 'Z'); // Añade 'Z' para indicar UTC
  const formatted = localDate.toLocaleString('es-ES');
  ```

#### 5. **Validación de Códigos Duplicados**
- El backend **valida que `codigo_operario` sea único** (cuando POST esté implementado)
- Si intentas crear un operario con código duplicado → Error `400 Bad Request`
- **Para Frontend**: Maneja el error apropiadamente:
  ```javascript
  if (error.status === 400 && error.detail.includes('código')) {
    showError('⚠️ Ya existe un operario con ese código');
  }
  ```

#### 6. **No Hay Validación de Operarios en Uso**
- Al desactivar un operario (cuando PATCH esté implementado), el backend **NO valida** si tiene órdenes activas
- **Riesgo**: Podrías desactivar un operario que está trabajando en órdenes
- **Recomendación**: Valida en frontend antes de desactivar:
  ```javascript
  // Verificar si tiene órdenes activas
  const ordersResponse = await fetch(`/api/v1/orders?estado_codigo=IN_PICKING`);
  const orders = await ordersResponse.json();
  const hasActiveOrders = orders.some(o => o.operario_asignado === operator.nombre);
  
  if (hasActiveOrders) {
    confirm('⚠️ Este operario tiene órdenes activas. ¿Deseas continuar?');
  }
  ```

### 💡 Recomendaciones para Desarrollo Frontend

1. **Deshabilita botones de acciones no disponibles**
   ```jsx
   <Button 
     disabled={true}
     onClick={() => alert('Funcionalidad no disponible')}
     title="Esta función aún no está implementada"
   >
     Crear Operario (Próximamente)
   </Button>
   ```

2. **Cachea la lista de operarios**
   ```javascript
   // No recargar en cada render, usar cache de 5 minutos
   const { data: operators } = useQuery(
     ['operators', activeFilter],
     () => fetchOperators(activeFilter),
     { staleTime: 5 * 60 * 1000 } // 5 minutos
   );
   ```

3. **Muestra indicadores de funcionalidad limitada**
   ```jsx
   <Badge color="warning">Solo lectura</Badge>
   <Tooltip content="El backend solo permite consultas GET">
     <InfoIcon />
   </Tooltip>
   ```

4. **Prepara para futuras implementaciones**
   - Crea los formularios y funciones
   - Mantenlos deshabilitados con mensajes claros
   - Cuando el backend esté listo, solo habilita los botones

---

## 🔗 Base URL

```
http://localhost:8000/api/v1
```

**Documentación interactiva:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 📦 Modelo de Datos

### Estructura de un Operario

```json
{
  "id": 1,
  "codigo_operario": "OP001",
  "nombre": "Juan Pérez García",
  "activo": true,
  "created_at": "2025-12-30T03:00:00.000000",
  "updated_at": "2025-12-30T03:00:00.000000"
}
```

### Descripción de Campos

| Campo | Tipo | Descripción | Restricciones |
|-------|------|-------------|---------------|
| `id` | integer | Identificador único interno | Auto-generado, PK |
| `codigo_operario` | string(50) | Código único del operario | Único, requerido, indexado |
| `nombre` | string(100) | Nombre completo del operario | Requerido |
| `activo` | boolean | Indica si el operario está activo | Default: `true`, indexado |
| `created_at` | datetime | Fecha de creación del registro | Auto-generado |
| `updated_at` | datetime | Fecha de última actualización | Auto-actualizado |

### Convenciones para `codigo_operario`

Se recomienda seguir un formato estándar:
- **Formato**: `OP` + número secuencial de 3 dígitos
- **Ejemplos**: `OP001`, `OP002`, `OP099`, `OP100`
- **Alternativas**: También puede usar códigos del sistema de nómina

---

## ✅ Endpoints Disponibles

### 1. Listar Operarios

Lista todos los operarios del sistema con opción de filtrar por estado.

**Método:** `GET`  
**Endpoint:** `/api/v1/operators`

#### Parámetros de Query (Opcionales)

| Parámetro | Tipo | Descripción | Valores | Ejemplo |
|-----------|------|-------------|---------|---------|
| `activo` | boolean | Filtrar por estado activo/inactivo | `true`, `false` | `activo=true` |

#### Respuesta Exitosa (200 OK)

```json
[
  {
    "id": 1,
    "codigo_operario": "OP001",
    "nombre": "Juan Pérez García",
    "activo": true,
    "created_at": "2025-12-30T03:00:00.000000",
    "updated_at": "2025-12-30T03:00:00.000000"
  },
  {
    "id": 2,
    "codigo_operario": "OP002",
    "nombre": "María García López",
    "activo": true,
    "created_at": "2025-12-30T03:15:00.000000",
    "updated_at": "2025-12-30T03:15:00.000000"
  },
  {
    "id": 3,
    "codigo_operario": "OP003",
    "nombre": "Carlos Rodríguez",
    "activo": false,
    "created_at": "2025-12-25T10:00:00.000000",
    "updated_at": "2026-01-02T14:30:00.000000"
  }
]
```

#### Características

- ✅ Retorna lista completa si no hay filtros
- ✅ Los resultados están ordenados por `nombre` (alfabéticamente)
- ✅ Siempre retorna un array (vacío si no hay resultados)
- ✅ No hay paginación (puede agregarse si hay muchos operarios)

#### Ejemplos de Uso

```bash
# Listar todos los operarios
curl http://localhost:8000/api/v1/operators

# Listar solo operarios activos (disponibles para asignar)
curl "http://localhost:8000/api/v1/operators?activo=true"

# Listar solo operarios inactivos (vacaciones, bajas, etc.)
curl "http://localhost:8000/api/v1/operators?activo=false"
```

#### Uso desde JavaScript/TypeScript

```javascript
// Obtener todos los operarios activos
async function getActiveOperators() {
  const response = await fetch('http://localhost:8000/api/v1/operators?activo=true');
  const operators = await response.json();
  return operators;
}

// Ejemplo de uso en React
useEffect(() => {
  fetch('http://localhost:8000/api/v1/operators?activo=true')
    .then(res => res.json())
    .then(data => setOperators(data));
}, []);
```

#### Casos de Uso

1. **Dropdown de Selección**: Cargar operarios activos para asignar a órdenes
2. **Listado en Dashboard**: Mostrar todos los operarios y su estado
3. **Reportes**: Generar informes de personal activo/inactivo
4. **Gestión de Recursos**: Verificar disponibilidad de personal

---

### 2. Obtener Detalle de Operario

Obtiene la información completa de un operario específico por su ID.

**Método:** `GET`  
**Endpoint:** `/api/v1/operators/{operator_id}`

#### Parámetros de Ruta (Requeridos)

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `operator_id` | integer | ID único del operario |

#### Respuesta Exitosa (200 OK)

```json
{
  "id": 1,
  "codigo_operario": "OP001",
  "nombre": "Juan Pérez García",
  "activo": true,
  "created_at": "2025-12-30T03:00:00.000000",
  "updated_at": "2025-12-30T03:00:00.000000"
}
```

#### Respuesta de Error (404 Not Found)

```json
{
  "detail": "Operario con ID 999 no encontrado"
}
```

#### Ejemplos de Uso

```bash
# Obtener operario con ID 1
curl http://localhost:8000/api/v1/operators/1

# Obtener operario con ID 5
curl http://localhost:8000/api/v1/operators/5
```

#### Uso desde JavaScript/TypeScript

```javascript
// Obtener detalles de un operario
async function getOperatorDetails(operatorId) {
  try {
    const response = await fetch(`http://localhost:8000/api/v1/operators/${operatorId}`);
    
    if (!response.ok) {
      throw new Error('Operario no encontrado');
    }
    
    const operator = await response.json();
    return operator;
  } catch (error) {
    console.error('Error al obtener operario:', error);
    return null;
  }
}

// Ejemplo de uso
const operator = await getOperatorDetails(1);
console.log(`Operario: ${operator.nombre} - Estado: ${operator.activo ? 'Activo' : 'Inactivo'}`);
```

#### Casos de Uso

1. **Vista de Perfil**: Mostrar información del operario en una página de perfil
2. **Validación**: Verificar que un operario existe antes de asignarlo
3. **Auditoría**: Revisar cuándo fue creado/actualizado un operario
4. **Detalle en Modal**: Mostrar información completa al hacer clic en un operario

---

### 3. Crear Operario

**Método:** `POST`  
**Endpoint:** `/api/v1/operators`

#### Body Esperado (JSON)

```json
{
  "codigo_operario": "OP004",
  "nombre": "Pedro Martínez",
  "activo": true
}
```

#### Respuesta Esperada (201 Created)

```json
{
  "id": 4,
  "codigo_operario": "OP004",
  "nombre": "Pedro Martínez",
  "activo": true,
  "created_at": "2026-01-05T12:30:00.000000",
  "updated_at": "2026-01-05T12:30:00.000000"
}
```

#### Validaciones Necesarias

- ✅ `codigo_operario` debe ser único
- ✅ `nombre` no puede estar vacío
- ✅ `codigo_operario` debe seguir formato válido
- ❌ Error 400 si el código ya existe
- ❌ Error 422 si faltan campos requeridos

#### Ejemplo de Implementación Sugerida

```python
@router.post("/", response_model=OperatorResponse, status_code=201)
def create_operator(
    operator: OperatorCreate,
    db: Session = Depends(get_db)
):
    """Crea un nuevo operario en el sistema."""
    
    # Verificar que el código no exista
    existing = db.query(Operator).filter(
        Operator.codigo_operario == operator.codigo_operario
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe un operario con código '{operator.codigo_operario}'"
        )
    
    # Crear nuevo operario
    db_operator = Operator(**operator.model_dump())
    db.add(db_operator)
    db.commit()
    db.refresh(db_operator)
    
    return db_operator
```

---

### 4. Actualizar Operario

**Método:** `PUT`  
**Endpoint:** `/api/v1/operators/{operator_id}`

#### Body Esperado (JSON)

```json
{
  "nombre": "Juan Pérez García (Supervisor)",
  "activo": true
}
```

#### Respuesta Esperada (200 OK)

```json
{
  "id": 1,
  "codigo_operario": "OP001",
  "nombre": "Juan Pérez García (Supervisor)",
  "activo": true,
  "created_at": "2025-12-30T03:00:00.000000",
  "updated_at": "2026-01-05T12:35:00.000000"
}
```

#### Características

- ✅ Solo actualiza los campos enviados (actualización parcial)
- ✅ No permite cambiar `id` ni `codigo_operario`
- ✅ Actualiza automáticamente `updated_at`
- ❌ Error 404 si el operario no existe

---

### 5. Activar/Desactivar Operario

**Método:** `PATCH`  
**Endpoint:** `/api/v1/operators/{operator_id}/toggle-status`

#### Body Esperado (JSON)

```json
{
  "activo": false,
  "razon": "Vacaciones hasta 15/01/2026"
}
```

#### Respuesta Esperada (200 OK)

```json
{
  "id": 1,
  "codigo_operario": "OP001",
  "nombre": "Juan Pérez García",
  "activo": false,
  "created_at": "2025-12-30T03:00:00.000000",
  "updated_at": "2026-01-05T12:40:00.000000"
}
```

#### Características

- ✅ Soft delete (no elimina del sistema)
- ✅ Operarios inactivos no pueden ser asignados a órdenes
- ✅ Se mantiene el historial de órdenes previas
- ⚠️ Debe validar que el operario no tenga órdenes activas antes de desactivar

---

### 6. Obtener Estadísticas de Operario (Recomendado)

**Método:** `GET`  
**Endpoint:** `/api/v1/operators/{operator_id}/stats`

#### Respuesta Esperada (200 OK)

```json
{
  "operator_id": 1,
  "operator_name": "Juan Pérez García",
  "total_orders_completed": 45,
  "total_orders_active": 3,
  "total_picking_tasks": 230,
  "average_time_per_order_minutes": 25.5,
  "efficiency_score": 92.3,
  "last_activity": "2026-01-05T11:30:00.000000",
  "orders_by_status": {
    "ASSIGNED": 1,
    "IN_PICKING": 2,
    "PICKED": 0
  }
}
```

#### Casos de Uso

1. **Dashboard de Performance**: Mostrar métricas de cada operario
2. **Reportes Gerenciales**: Comparar eficiencia entre operarios
3. **Planificación**: Asignar órdenes según disponibilidad y eficiencia
4. **Gamificación**: Sistema de rankings y metas

---

## 🎯 Casos de Uso Comunes

### Caso 1: Cargar Dropdown de Operarios para Asignación

```javascript
// Obtener solo operarios activos para un formulario
async function loadOperatorDropdown() {
  const response = await fetch('http://localhost:8000/api/v1/operators?activo=true');
  const operators = await response.json();
  
  // Formatear para dropdown
  return operators.map(op => ({
    value: op.id,
    label: `${op.codigo_operario} - ${op.nombre}`
  }));
}

// Ejemplo de uso en React Select
<Select
  options={operatorOptions}
  placeholder="Seleccionar operario..."
/>
```

### Caso 2: Verificar Estado de Operario Antes de Asignar

```javascript
async function canAssignOperator(operatorId) {
  try {
    const response = await fetch(`http://localhost:8000/api/v1/operators/${operatorId}`);
    const operator = await response.json();
    
    if (!operator.activo) {
      alert(`El operario ${operator.nombre} está inactivo y no puede ser asignado.`);
      return false;
    }
    
    return true;
  } catch (error) {
    alert('Error al verificar operario');
    return false;
  }
}
```

### Caso 3: Dashboard de Personal del Almacén

```javascript
async function getWarehouseStaffSummary() {
  const allOperators = await fetch('http://localhost:8000/api/v1/operators')
    .then(res => res.json());
  
  const summary = {
    total: allOperators.length,
    active: allOperators.filter(op => op.activo).length,
    inactive: allOperators.filter(op => !op.activo).length
  };
  
  return summary;
}

// Resultado: { total: 15, active: 12, inactive: 3 }
```

### Caso 4: Validación en Formulario de Asignación

```javascript
// Validar operario antes de enviar formulario
async function handleAssignOrder(orderId, operatorId) {
  // 1. Verificar que el operario existe y está activo
  const operator = await fetch(`http://localhost:8000/api/v1/operators/${operatorId}`)
    .then(res => res.json());
  
  if (!operator.activo) {
    throw new Error('No se puede asignar un operario inactivo');
  }
  
  // 2. Asignar orden
  const response = await fetch(
    `http://localhost:8000/api/v1/orders/${orderId}/assign-operator`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ operator_id: operatorId })
    }
  );
  
  return response.json();
}
```

---

## 📊 Códigos de Respuesta

| Código | Descripción | Cuándo Ocurre |
|--------|-------------|---------------|
| **200** | OK | Operación exitosa (GET, PUT, PATCH) |
| **201** | Created | Operario creado exitosamente (POST) |
| **400** | Bad Request | Código de operario duplicado, datos inválidos |
| **404** | Not Found | Operario no encontrado con el ID especificado |
| **422** | Unprocessable Entity | Error de validación de datos (campos requeridos faltantes) |
| **500** | Internal Server Error | Error del servidor (raro, contactar soporte) |

---

## 🔗 Relaciones con Otros Módulos

Los operarios están relacionados con otros módulos del sistema:

### 1. Módulo de Órdenes

**Endpoint de integración:** `PUT /api/v1/orders/{order_id}/assign-operator`

```bash
# Asignar operario a una orden
curl -X PUT http://localhost:8000/api/v1/orders/1/assign-operator \
  -H "Content-Type: application/json" \
  -d '{"operator_id": 1}'
```

**Validación automática:**
- ✅ Verifica que el operario exista
- ✅ Verifica que el operario esté activo
- ❌ Error 404 si el operario no existe
- ❌ Error 400 si el operario está inactivo

### 2. Tabla `orders`

**Relación:** Un operario puede tener muchas órdenes (`One-to-Many`)

```sql
SELECT o.numero_orden, o.fecha_orden, os.nombre as estado
FROM orders o
JOIN operators op ON o.operator_id = op.id
WHERE op.id = 1;
```

### 3. Tabla `picking_tasks`

**Relación:** Un operario puede tener muchas tareas de picking (`One-to-Many`)

Las tareas de picking se crean cuando se asigna una orden a un operario.

### 4. Tabla `order_history`

**Relación:** Un operario puede tener muchas entradas de historial (`One-to-Many`)

Todas las acciones del operario quedan registradas para auditoría:
- Asignación a órdenes
- Cambios de estado
- Inicio/fin de picking

---

## 🔍 Consultas Avanzadas (Ejemplos SQL)

### Obtener órdenes activas de un operario

```sql
SELECT 
    o.numero_orden,
    os.nombre as estado,
    o.fecha_asignacion,
    o.total_items,
    o.items_completados
FROM orders o
JOIN order_status os ON o.status_id = os.id
JOIN operators op ON o.operator_id = op.id
WHERE op.id = 1
  AND os.codigo IN ('ASSIGNED', 'IN_PICKING', 'PICKED', 'PACKING');
```

### Obtener performance de operarios

```sql
SELECT 
    op.codigo_operario,
    op.nombre,
    COUNT(o.id) as total_ordenes,
    SUM(CASE WHEN os.codigo = 'SHIPPED' THEN 1 ELSE 0 END) as ordenes_completadas,
    AVG(EXTRACT(EPOCH FROM (o.fecha_fin_picking - o.fecha_inicio_picking))/60) as tiempo_promedio_minutos
FROM operators op
LEFT JOIN orders o ON o.operator_id = op.id
LEFT JOIN order_status os ON o.status_id = os.id
WHERE op.activo = true
GROUP BY op.id, op.codigo_operario, op.nombre
ORDER BY ordenes_completadas DESC;
```

---

## 🛡️ Validaciones de Negocio

### Al Asignar Operario a Orden

1. ✅ El operario debe existir en la base de datos
2. ✅ El operario debe estar activo (`activo = true`)
3. ✅ La orden debe existir
4. ✅ Se registra automáticamente en `order_history`

### Al Crear Operario (Cuando se implemente)

1. ✅ `codigo_operario` debe ser único
2. ✅ `nombre` no puede estar vacío
3. ✅ `codigo_operario` debe tener formato válido (ej: alfanumérico, máx 50 chars)
4. ✅ Por defecto se crea como activo (`activo = true`)

### Al Desactivar Operario (Cuando se implemente)

1. ⚠️ **Recomendado**: Verificar que no tenga órdenes activas
2. ⚠️ **Recomendado**: Notificar/confirmar antes de desactivar
3. ✅ No se elimina del sistema (soft delete)
4. ✅ Las órdenes históricas se mantienen intactas

---

## 💡 Mejores Prácticas

### Para Frontend

1. **Cache de Operarios Activos**
   ```javascript
   // Cachear lista de operarios activos por 5 minutos
   const cachedOperators = useMemo(() => {
     return operators.filter(op => op.activo);
   }, [operators]);
   ```

2. **Validación Antes de Submit**
   ```javascript
   // Verificar estado antes de enviar formulario
   if (!selectedOperator?.activo) {
     alert('Selecciona un operario activo');
     return;
   }
   ```

3. **Manejo de Errores**
   ```javascript
   try {
     const result = await assignOperator(orderId, operatorId);
     showSuccess('Operario asignado exitosamente');
   } catch (error) {
     if (error.status === 404) {
       showError('Operario no encontrado');
     } else if (error.status === 400) {
       showError('El operario no está disponible');
     } else {
       showError('Error al asignar operario');
     }
   }
   ```

### Para Backend

1. **Usar Índices**: Los campos `codigo_operario` y `activo` ya están indexados
2. **Transacciones**: Usar transacciones al crear/actualizar operarios
3. **Validación en Capa de Negocio**: No confiar solo en validación del frontend
4. **Logging**: Registrar todas las creaciones/modificaciones de operarios

---

## 📚 Recursos Adicionales

### Documentos Relacionados

- `API_ENDPOINTS.md` - Documentación completa de todos los endpoints
- `DATABASE_MODEL_REFERENCE.md` - Referencia del modelo de datos
- `ORDERS_SYSTEM_README.md` - Documentación del sistema de órdenes

### Código Fuente

- **Router**: `src/adapters/primary/api/operator_router.py`
- **Modelo ORM**: `src/adapters/secondary/database/orm.py` (clase `Operator`)
- **Modelos Pydantic**: `src/core/domain/models.py` (clases `Operator*`)

### Swagger UI

Accede a la documentación interactiva en: http://localhost:8000/docs

Desde allí puedes:
- ✅ Probar todos los endpoints directamente
- ✅ Ver los schemas completos
- ✅ Ejecutar requests de ejemplo

---

## 🚀 Inicio Rápido

```bash
# 1. Iniciar el servidor
uvicorn src.main:app --reload

# 2. Listar operarios activos
curl "http://localhost:8000/api/v1/operators?activo=true"

# 3. Ver detalle de operario
curl http://localhost:8000/api/v1/operators/1

# 4. Asignar operario a orden
curl -X PUT http://localhost:8000/api/v1/orders/1/assign-operator \
  -H "Content-Type: application/json" \
  -d '{"operator_id": 1}'
```

---

## 📞 Soporte y Contacto

Para preguntas o problemas:
1. Revisa la documentación en `/docs`
2. Consulta `API_ENDPOINTS.md` para ejemplos completos
3. Revisa los logs del servidor para errores específicos

---

**Última actualización:** 2026-01-05  
**Versión de API:** v1  
**Estado de Implementación:** ✅ CRUD Completo (GET, POST, PUT, PATCH)  
**Endpoints Disponibles:** 5/5 ✅ | **Endpoint Sugerido:** Stats (0/1 ⏳)
