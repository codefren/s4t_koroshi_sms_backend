# 📦 Sistema de Gestión de Productos y Ubicaciones

Documentación completa de los modelos de productos y sus ubicaciones en el almacén.

## 📋 Tabla de Contenidos

- [Introducción](#-introducción)
- [Arquitectura de Datos](#-arquitectura-de-datos)
- [Modelo ProductReference](#-modelo-productreference)
- [Modelo ProductLocation](#-modelo-productlocation)
- [Relaciones](#-relaciones)
- [Índices y Optimizaciones](#-índices-y-optimizaciones)
- [Casos de Uso](#-casos-de-uso)
- [Inicialización](#-inicialización)
- [Ejemplos de Consultas](#-ejemplos-de-consultas)

---

## 🎯 Introducción

El sistema de gestión de productos permite:
- ✅ **Catálogo centralizado** de productos con referencia hexadecimal única
- ✅ **Multi-ubicación** - Un producto puede estar en múltiples lugares del almacén
- ✅ **Gestión de stock** por ubicación con alertas de stock mínimo
- ✅ **Optimización de picking** mediante priorización de ubicaciones
- ✅ **Trazabilidad completa** con información detallada de cada producto

---

## 🏗️ Arquitectura de Datos

```
┌─────────────────────────────┐
│   ProductReference          │
│  (Producto Maestro)         │
│                             │
│  - referencia (HEX único)   │
│  - nombre_producto          │
│  - color_id                 │
│  - talla                    │
│  - ean, sku, precio         │
└──────────────┬──────────────┘
               │
               │ One-to-Many
               │
               ▼
┌──────────────────────────────┐
│   ProductLocation            │
│  (Ubicación Física)          │
│                              │
│  - pasillo (alfanumérico)    │
│  - lado (IZQ/DER)           │
│  - ubicacion                 │
│  - altura (1-10)            │
│  - stock_minimo              │
│  - stock_actual              │
│  - prioridad (1-5)          │
└──────────────────────────────┘
```

### Ejemplo Real

```
ProductReference #1: "Camisa Polo Roja M"
├─ Referencia: A1B2C3
├─ Color ID: 000001
├─ Talla: M
└─ Ubicaciones:
   ├─ ProductLocation #1: Pasillo A, Izquierda, Pos 12, Altura 2
   │  └─ Stock: 45 unidades (mínimo: 10) ✅
   ├─ ProductLocation #2: Pasillo B3, Derecha, Pos 05, Altura 1
   │  └─ Stock: 12 unidades (mínimo: 5) ✅
   └─ ProductLocation #3: Pasillo D, Izquierda, Pos 20, Altura 3
      └─ Stock: 3 unidades (mínimo: 5) ⚠️ ALERTA
```

---

## 📦 Modelo ProductReference

Catálogo maestro de productos del almacén.

### Campos Principales

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `id` | Integer | ID interno auto-generado | 1, 2, 3 |
| `referencia` | String(50) | **Código hexadecimal único** | `A1B2C3`, `FF00AA` |
| `nombre_producto` | String(200) | Nombre descriptivo | "Camisa Polo Manga Corta" |
| `color_id` | String(50) | ID del color | `000001`, `RED` |
| `talla` | String(20) | Talla | `M`, `L`, `42` |

### Campos Opcionales

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `descripcion_color` | String(100) | Descripción del color ("Rojo", "Azul Marino") |
| `ean` | String(50) | Código de barras EAN |
| `sku` | String(100) | SKU o código interno |
| `descripcion_completa` | Text | Descripción extendida |
| `precio_unitario` | Float | Precio de referencia |
| `peso_gramos` | Integer | Peso en gramos |
| `temporada` | String(50) | Temporada del producto |
| `activo` | Boolean | Si está activo en catálogo |

### Restricciones

- ✅ `referencia` debe ser **única** en toda la tabla
- ✅ `referencia` debe contener **solo caracteres hexadecimales** [0-9A-Fa-f]
- ✅ `nombre_producto`, `color_id`, `talla` son **requeridos**
- ✅ Valores numéricos (precio, peso) deben ser **no negativos**

### Índices

```sql
-- Índice único en referencia
CREATE UNIQUE INDEX ON product_references(referencia);

-- Índice para búsquedas por color y talla
CREATE INDEX idx_color_talla ON product_references(color_id, talla);

-- Índice para autocomplete de nombres
CREATE INDEX idx_nombre_producto ON product_references(nombre_producto);

-- Índice compuesto para búsquedas frecuentes
CREATE INDEX idx_nombre_color_talla ON product_references(nombre_producto, color_id, talla);

-- Índice para productos activos
CREATE INDEX idx_activo ON product_references(activo);
```

### Ejemplo de Registro

```json
{
  "id": 1,
  "referencia": "A1B2C3",
  "nombre_producto": "Camisa Polo Manga Corta",
  "color_id": "000001",
  "talla": "M",
  "descripcion_color": "Rojo",
  "ean": "8445962763983",
  "sku": "2523HA02",
  "descripcion_completa": "Camisa polo de algodón 100%, manga corta, cuello con botones",
  "precio_unitario": 29.99,
  "peso_gramos": 250,
  "temporada": "Verano 2024",
  "activo": true,
  "created_at": "2026-01-05T21:00:00",
  "updated_at": "2026-01-05T21:00:00"
}
```

---

## 📍 Modelo ProductLocation

Ubicaciones físicas de productos en el almacén.

### Estructura de Ubicación

Una ubicación se compone de **4 elementos principales**:

```
PASILLO  +  LADO  +  UBICACION  +  ALTURA
   ↓         ↓          ↓           ↓
   A    +   IZQ   +     12     +    2
        ↓
   Código: A-IZQ-12-H2
```

### Campos Principales

| Campo | Tipo | Descripción | Ejemplos |
|-------|------|-------------|----------|
| `id` | Integer | ID interno | 1, 2, 3 |
| `product_id` | Integer FK | Referencia al producto | 1 |
| `pasillo` | String(10) | Identificador del pasillo | `A`, `B1`, `C3` |
| `lado` | String(20) | Lado del pasillo | `IZQUIERDA`, `DERECHA`, `IZQ`, `DER` |
| `ubicacion` | String(20) | Posición específica | `12`, `05`, `A3` |
| `altura` | Integer | Nivel vertical (1-10) | `1`, `2`, `3` |

### Campos de Gestión de Stock

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `stock_minimo` | Integer | Stock mínimo para alerta (default: 0) |
| `stock_actual` | Integer | Stock actual en esta ubicación (default: 0) |

### Campos Adicionales

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `codigo_ubicacion` | String(50) | Código completo generado (`A-IZQ-12-H2`) |
| `prioridad` | Integer | Prioridad para picking: 1=alta, 5=baja (default: 3) |
| `activa` | Boolean | Si la ubicación está disponible (default: true) |
| `notas` | Text | Notas sobre la ubicación |

### Restricciones

- ✅ No puede haber **ubicaciones duplicadas** para el mismo producto
  ```sql
  UNIQUE(product_id, pasillo, lado, ubicacion, altura)
  ```
- ✅ `altura` debe estar entre **1 y 10**
- ✅ `prioridad` debe estar entre **1 y 5**
- ✅ `stock_minimo` y `stock_actual` no pueden ser negativos

### Índices

```sql
-- Índice en product_id para joins rápidos
CREATE INDEX ON product_locations(product_id);

-- Índice por pasillo
CREATE INDEX idx_pasillo ON product_locations(pasillo);

-- Índice compuesto para ubicación completa
CREATE INDEX idx_ubicacion_completa ON product_locations(pasillo, lado, ubicacion, altura);

-- Índice para alertas de stock bajo
CREATE INDEX idx_stock_bajo ON product_locations(stock_actual, stock_minimo);

-- Índice para ubicaciones activas con prioridad
CREATE INDEX idx_activa_prioridad ON product_locations(activa, prioridad);
```

### Ejemplo de Registro

```json
{
  "id": 1,
  "product_id": 1,
  "pasillo": "A",
  "lado": "IZQUIERDA",
  "ubicacion": "12",
  "altura": 2,
  "stock_minimo": 10,
  "stock_actual": 45,
  "codigo_ubicacion": "A-IZQ-12-H2",
  "prioridad": 1,
  "activa": true,
  "notas": "Zona de alta rotación - fácil acceso",
  "created_at": "2026-01-05T21:00:00",
  "updated_at": "2026-01-05T21:00:00"
}
```

---

## 🔗 Relaciones

### ProductReference → ProductLocation (One-to-Many)

Un producto puede estar en **múltiples ubicaciones**:

```python
# Desde ProductReference
product = session.query(ProductReference).filter_by(referencia="A1B2C3").first()
print(f"Ubicaciones de {product.nombre_producto}:")
for location in product.locations:
    print(f"  - {location.codigo_ubicacion}: Stock {location.stock_actual}")

# Desde ProductLocation
location = session.query(ProductLocation).filter_by(codigo_ubicacion="A-IZQ-12-H2").first()
print(f"Producto en esta ubicación: {location.product.nombre_producto}")
```

### Cascade Behavior

- **DELETE CASCADE**: Si eliminas un producto, se eliminan todas sus ubicaciones
- **NO ACTION** en consultas: Las ubicaciones no pueden existir sin producto

```python
# Al eliminar un producto
session.delete(product)
session.commit()
# ↓ Automáticamente elimina todas sus ubicaciones
```

---

## ⚡ Índices y Optimizaciones

### Búsquedas Optimizadas

1. **Por referencia hexadecimal** (O(log n))
   ```sql
   SELECT * FROM product_references WHERE referencia = 'A1B2C3';
   ```

2. **Por color y talla** (O(log n))
   ```sql
   SELECT * FROM product_references WHERE color_id = '000001' AND talla = 'M';
   ```

3. **Por ubicación completa** (O(log n))
   ```sql
   SELECT * FROM product_locations 
   WHERE pasillo = 'A' AND lado = 'IZQUIERDA' 
     AND ubicacion = '12' AND altura = 2;
   ```

4. **Alertas de stock bajo** (O(n) con filtro eficiente)
   ```sql
   SELECT * FROM product_locations 
   WHERE stock_actual < stock_minimo AND activa = true;
   ```

---

## 💡 Casos de Uso

### Caso 1: Crear Producto con Múltiples Ubicaciones

```python
from src.adapters.secondary.database.orm import ProductReference, ProductLocation

# Crear producto
producto = ProductReference(
    referencia="A1B2C3",
    nombre_producto="Camisa Polo Manga Corta",
    color_id="000001",
    talla="M",
    descripcion_color="Rojo",
    activo=True
)

# Agregar ubicaciones
ubicacion1 = ProductLocation(
    product=producto,
    pasillo="A",
    lado="IZQUIERDA",
    ubicacion="12",
    altura=2,
    stock_minimo=10,
    stock_actual=45,
    codigo_ubicacion="A-IZQ-12-H2",
    prioridad=1,
    activa=True
)

ubicacion2 = ProductLocation(
    product=producto,
    pasillo="B3",
    lado="DERECHA",
    ubicacion="05",
    altura=1,
    stock_minimo=5,
    stock_actual=12,
    codigo_ubicacion="B3-DER-05-H1",
    prioridad=2,
    activa=True
)

session.add(producto)  # Cascade agrega las ubicaciones automáticamente
session.commit()
```

### Caso 2: Buscar Producto por Referencia y Ver Ubicaciones

```python
producto = session.query(ProductReference).filter(
    ProductReference.referencia == "A1B2C3"
).first()

if producto:
    print(f"Producto: {producto.nombre_producto}")
    print(f"Total ubicaciones: {len(producto.locations)}")
    
    for loc in producto.locations:
        status = "✅" if loc.stock_actual >= loc.stock_minimo else "⚠️"
        print(f"{status} {loc.codigo_ubicacion}: {loc.stock_actual} unidades")
```

### Caso 3: Encontrar Ubicaciones con Stock Bajo

```python
from sqlalchemy import and_

alertas = session.query(ProductLocation).join(ProductReference).filter(
    and_(
        ProductLocation.stock_actual < ProductLocation.stock_minimo,
        ProductLocation.activa == True,
        ProductReference.activo == True
    )
).all()

for alerta in alertas:
    print(f"⚠️  ALERTA: {alerta.product.nombre_producto}")
    print(f"   Ubicación: {alerta.codigo_ubicacion}")
    print(f"   Stock: {alerta.stock_actual}/{alerta.stock_minimo}")
```

### Caso 4: Optimizar Ruta de Picking

```python
# Obtener ubicaciones ordenadas por prioridad y altura
ubicaciones = session.query(ProductLocation).filter(
    ProductLocation.activa == True
).order_by(
    ProductLocation.prioridad.asc(),  # Primero las de alta prioridad
    ProductLocation.altura.asc()       # Luego las más bajas (fácil acceso)
).all()

for loc in ubicaciones:
    print(f"Prioridad {loc.prioridad} - {loc.codigo_ubicacion}")
```

---

## 🚀 Inicialización

### Crear Tablas

```bash
python init_product_system.py
```

El script:
1. ✅ Crea las tablas `product_references` y `product_locations`
2. ✅ Opcionalmente carga 3 productos de ejemplo con 5 ubicaciones
3. ✅ Verifica la integridad del sistema

### Verificar Creación

```python
from sqlalchemy import inspect
from src.adapters.secondary.database.config import engine

inspector = inspect(engine)

# Verificar que las tablas existen
tables = inspector.get_table_names()
print("product_references" in tables)  # True
print("product_locations" in tables)   # True
```

---

## 📝 Ejemplos de Consultas

### Consultas SQL Directas

#### 1. Listar productos con todas sus ubicaciones

```sql
SELECT 
    pr.referencia,
    pr.nombre_producto,
    pr.color_id,
    pr.talla,
    pl.codigo_ubicacion,
    pl.stock_actual,
    pl.stock_minimo
FROM product_references pr
LEFT JOIN product_locations pl ON pr.id = pl.product_id
WHERE pr.activo = true
ORDER BY pr.nombre_producto, pl.prioridad;
```

#### 2. Stock total por producto (suma de todas las ubicaciones)

```sql
SELECT 
    pr.referencia,
    pr.nombre_producto,
    COUNT(pl.id) as num_ubicaciones,
    SUM(pl.stock_actual) as stock_total,
    SUM(pl.stock_minimo) as stock_minimo_total
FROM product_references pr
LEFT JOIN product_locations pl ON pr.id = pl.product_id
WHERE pl.activa = true
GROUP BY pr.id, pr.referencia, pr.nombre_producto
ORDER BY stock_total DESC;
```

#### 3. Ubicaciones que requieren reposición

```sql
SELECT 
    pr.nombre_producto,
    pr.referencia,
    pl.codigo_ubicacion,
    pl.stock_actual,
    pl.stock_minimo,
    (pl.stock_minimo - pl.stock_actual) as necesita_reponer
FROM product_locations pl
JOIN product_references pr ON pl.product_id = pr.id
WHERE pl.stock_actual < pl.stock_minimo
  AND pl.activa = true
ORDER BY necesita_reponer DESC;
```

#### 4. Productos por pasillo

```sql
SELECT 
    pl.pasillo,
    COUNT(DISTINCT pr.id) as num_productos,
    SUM(pl.stock_actual) as stock_total
FROM product_locations pl
JOIN product_references pr ON pl.product_id = pr.id
WHERE pl.activa = true
GROUP BY pl.pasillo
ORDER BY pl.pasillo;
```

### Consultas con SQLAlchemy

#### 1. Productos con más de una ubicación

```python
from sqlalchemy import func

productos_multi_ubicacion = session.query(
    ProductReference,
    func.count(ProductLocation.id).label('num_ubicaciones')
).join(ProductLocation).group_by(
    ProductReference.id
).having(
    func.count(ProductLocation.id) > 1
).all()

for producto, count in productos_multi_ubicacion:
    print(f"{producto.nombre_producto}: {count} ubicaciones")
```

#### 2. Ubicaciones por altura

```python
ubicaciones_por_altura = session.query(
    ProductLocation.altura,
    func.count(ProductLocation.id).label('total')
).group_by(
    ProductLocation.altura
).order_by(
    ProductLocation.altura
).all()

for altura, total in ubicaciones_por_altura:
    print(f"Altura {altura}: {total} ubicaciones")
```

---

## 🎯 Próximos Pasos

1. ✅ **Modelos creados** - ProductReference y ProductLocation
2. ✅ **Script de inicialización** - init_product_system.py
3. ⏳ **Crear endpoints API** - CRUD completo para productos
4. ⏳ **Integrar con orders** - Relacionar products con order_lines
5. ⏳ **Dashboard de stock** - Visualización de alertas y reportes
6. ⏳ **Optimización de rutas** - Algoritmo de picking eficiente

---

## 📚 Referencias

- **Archivo ORM**: `src/adapters/secondary/database/orm.py` (líneas 488-687)
- **Modelos Pydantic**: `src/core/domain/models.py` (líneas 349-508)
- **Script Init**: `init_product_system.py`
- **Base de datos**: SQLite/PostgreSQL compatible

---

**Última actualización:** 2026-01-05  
**Autor:** Sistema SMS Backend  
**Versión:** 1.0.0
