# ✅ Normalización Completa - Guía de Implementación

**Fecha:** 2026-01-07  
**Estado:** ✅ Lista para aplicar

---

## 🎯 Resumen de Cambios

### **ANTES** ❌

```
OrderLine: 
  - ean
  - ubicacion          ← Redundante
  - articulo           ← Redundante
  - color              ← Redundante
  - talla              ← Redundante
  - posicion_talla     ← Redundante
  - descripcion_producto ← Redundante
  - descripcion_color  ← Redundante
  - temporada          ← Redundante
```

### **DESPUÉS** ✅

```
OrderLine:
  - ean                         ← Solo para match rápido
  - product_reference_id        ← FK a ProductReference
  - product_location_id         ← FK a ProductLocation
  - cantidad_solicitada
  - cantidad_servida
  - estado

ProductReference:
  - referencia, nombre_producto
  - color_id, color             ← NUEVO
  - talla, posicion_talla       ← NUEVO
  - descripcion_color
  - ean, sku, temporada
```

---

## 🚀 Aplicar Normalización (1 Comando)

### Opción 1: Aplicación Automática Completa

```bash
python apply_normalization.py
```

Esto ejecuta:
1. ✅ Migración 001: Agregar FKs a `order_lines`
2. ✅ Migración 002: Normalizar campos redundantes
3. ✅ Cargar productos de ejemplo
4. ✅ Recrear 10 órdenes vinculadas

### Opción 2: Solo Migraciones (Sin recrear órdenes)

```bash
python apply_normalization.py --skip-orders
```

### Opción 3: Crear más órdenes

```bash
python apply_normalization.py --num-orders 20
```

---

## 📋 Aplicación Manual (Paso a Paso)

Si prefieres control total:

### Paso 1: Migración de Base de Datos

```bash
# Agregar FKs
python run_migration.py

# Normalizar campos
cd migrations
sqlcmd -S localhost -d tu_database -i 002_normalize_order_lines.sql
```

### Paso 2: Cargar Productos

```bash
python seed_products.py --force
```

### Paso 3: Recrear Órdenes

```bash
python recreate_orders_with_products.py
```

---

## 🔍 Verificar Normalización

```bash
# Verificar que todo está correcto
python test_normalization.py
```

**Resultado esperado:**
```
✅ PASS - Schema ORM
✅ PASS - Vinculación de Datos (100%)
✅ PASS - Endpoint Optimización
✅ PASS - Endpoint Validación
```

---

## 📊 Estructura Final

### ProductReference (Catálogo Maestro)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | INT | PK |
| `referencia` | VARCHAR(50) | Código único |
| `nombre_producto` | VARCHAR(200) | Nombre completo |
| `color_id` | VARCHAR(50) | ID del color |
| `color` | VARCHAR(100) | **NUEVO** - Nombre corto |
| `talla` | VARCHAR(20) | Talla |
| `posicion_talla` | VARCHAR(50) | **NUEVO** - Para ordenar |
| `descripcion_color` | VARCHAR(100) | Descripción larga |
| `ean` | VARCHAR(50) | Código de barras |
| `sku` | VARCHAR(100) | SKU interno |
| `temporada` | VARCHAR(50) | Temporada |
| `activo` | BOOLEAN | Estado |

### OrderLine (Simplificada)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | INT | PK |
| `order_id` | INT | FK → orders |
| `product_reference_id` | INT | **FK → ProductReference** |
| `product_location_id` | INT | **FK → ProductLocation** |
| `ean` | VARCHAR(50) | Solo para match rápido |
| `cantidad_solicitada` | INT | Cantidad pedida |
| `cantidad_servida` | INT | Cantidad recogida |
| `estado` | VARCHAR(20) | PENDING/COMPLETED |

---

## 🎯 Beneficios

### 1. **Menos Redundancia**
- **Antes:** 8 campos duplicados por cada línea de orden
- **Ahora:** 0 campos duplicados, todo via FKs

### 2. **Actualizaciones Centralizadas**
```python
# Cambiar el nombre de un producto afecta TODAS las órdenes automáticamente
product.nombre_producto = "Nuevo Nombre"
db.commit()
# ✅ Todas las órdenes muestran el nuevo nombre
```

### 3. **Queries Más Eficientes**
```python
# Antes: Full scan en order_lines
orders = db.query(OrderLine).filter(OrderLine.descripcion_producto.like('%Polo%'))

# Ahora: Index scan en product_references
orders = db.query(OrderLine).join(ProductReference).filter(
    ProductReference.nombre_producto.like('%Polo%')
)
```

### 4. **Datos Siempre Actualizados**
```python
# Los endpoints automáticamente obtienen datos actuales
order = get_order_detail(1)
# ✅ Usa product.nombre_producto (siempre actualizado)
# ✅ Usa location.codigo_ubicacion (siempre actualizado)
```

---

## 🔧 Endpoints Actualizados

Todos estos endpoints **ya están actualizados** para usar relaciones:

### ✅ GET /api/v1/orders/{id}
```python
# Obtiene datos desde las relaciones
for line in order.order_lines:
    nombre = line.product_reference.nombre_producto
    ubicacion = line.product_location.codigo_ubicacion
```

### ✅ POST /api/v1/orders/{id}/optimize-picking-route
```python
# Usa relaciones para optimizar rutas
for line in order.order_lines:
    product = line.product_reference
    location = line.product_location
    # Agrupa por pasillo, ordena por prioridad
```

### ✅ GET /api/v1/orders/{id}/stock-validation
```python
# Valida stock desde ubicación real
for line in order.order_lines:
    stock_actual = line.product_location.stock_actual
    stock_necesario = line.cantidad_solicitada
```

---

## 📝 Compatibilidad con ETL

El ETL (`etl_import_orders.py`) **ya está actualizado**:

```python
# Al importar órdenes, vincula automáticamente
order_line = OrderLine(
    order_id=order.id,
    product_reference_id=product.id,  # ✅ Vincula con catálogo
    product_location_id=location.id,  # ✅ Vincula con ubicación
    ean=line_data.get("ean"),         # ✅ Solo EAN
    cantidad_solicitada=cantidad
)
```

---

## ⚠️ Notas Importantes

### 1. **Backup Recomendado**
```sql
-- Antes de aplicar
BACKUP DATABASE tu_database TO DISK = 'backup_pre_normalization.bak'
```

### 2. **Órdenes Históricas**
Las órdenes antiguas pueden tener:
- `product_reference_id = NULL` (no vinculadas)
- Los endpoints manejan esto con: `if product else "Desconocido"`

### 3. **Migración Idempotente**
Puedes ejecutar las migraciones múltiples veces sin problemas:
```sql
IF NOT EXISTS (SELECT * FROM ...) BEGIN
    ALTER TABLE ...
END
```

---

## 🐛 Troubleshooting

### Error: "Invalid column name 'descripcion_producto'"

**Causa:** La API no se reinició después de la migración.

**Solución:**
```bash
# Detener API (Ctrl+C)
uvicorn src.main:app --reload
```

### Error: "No hay productos en el catálogo"

**Causa:** No se ejecutó `seed_products.py`

**Solución:**
```bash
python seed_products.py --force
```

### Error: "Foreign key constraint failed"

**Causa:** Orden referencia producto que no existe

**Solución:**
```bash
# Recrear órdenes limpias
python recreate_orders_with_products.py
```

---

## 📚 Archivos Modificados

### Modificados
- ✅ `src/adapters/secondary/database/orm.py`
  - `ProductReference`: +2 campos
  - `OrderLine`: -8 campos
- ✅ `src/adapters/primary/api/order_router.py`
  - Todos los endpoints usan relaciones
- ✅ `etl_import_orders.py`
  - Crea OrderLine sin campos redundantes
- ✅ `fixtures/product_fixtures.py`
  - Factory incluye nuevos campos

### Nuevos
- ✅ `migrations/002_normalize_order_lines.sql`
- ✅ `apply_normalization.py`
- ✅ `recreate_orders_with_products.py`
- ✅ `NORMALIZATION_COMPLETE.md` (este archivo)

---

## ✅ Checklist Final

Después de aplicar la normalización:

- [ ] ✅ Migraciones aplicadas sin errores
- [ ] ✅ Productos cargados (>3 productos)
- [ ] ✅ Órdenes recreadas (>5 órdenes)
- [ ] ✅ API reiniciada
- [ ] ✅ GET /api/v1/orders funciona
- [ ] ✅ GET /api/v1/orders/1 muestra productos
- [ ] ✅ POST /api/v1/orders/1/optimize-picking-route genera ruta
- [ ] ✅ GET /api/v1/orders/1/stock-validation valida stock
- [ ] ✅ `test_normalization.py` pasa 100%

---

## 🎉 ¡Listo!

Tu sistema ahora está **100% normalizado** y listo para producción.

**Próximos pasos:**
1. Importar órdenes reales con ETL
2. Monitorear performance
3. Ajustar índices si es necesario

---

**Versión:** 2.0.0  
**Fecha:** 2026-01-07  
**Estado:** ✅ Producción Ready
