# 📦 API de Productos - Documentación Completa

API REST para gestionar productos y ubicaciones del almacén, diseñada específicamente para el componente `Products.jsx` del frontend React.

## 📋 Tabla de Contenidos

- [Endpoints Disponibles](#-endpoints-disponibles)
- [Modelos de Datos](#-modelos-de-datos)
- [Ejemplos de Uso](#-ejemplos-de-uso)
- [Filtros y Búsquedas](#-filtros-y-búsquedas)
- [Estados de Productos](#-estados-de-productos)
- [Formato de Ubicaciones](#-formato-de-ubicaciones)

---

## 🚀 Endpoints Disponibles

### Base URL
```
http://localhost:8000/api/v1/products
```

### Resumen de Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/products` | Lista productos con paginación y filtros |
| GET | `/products/{id}` | Detalle completo de un producto |
| GET | `/products/{id}/locations` | Todas las ubicaciones de un producto |
| GET | `/products/{id}/stock-summary` | Resumen rápido de stock |

---

## 📡 1. Listar Productos

### `GET /api/v1/products`

Lista productos con soporte para filtros, búsqueda y paginación.

#### Parámetros Query

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `status` | string | `all` | Filtrar por estado: `all`, `active`, `low`, `out` |
| `search` | string | `null` | Buscar en nombre, SKU, categoría o referencia |
| `page` | integer | `1` | Número de página (≥ 1) |
| `per_page` | integer | `20` | Productos por página (1-100) |

#### Ejemplo de Request

```bash
# Listar todos los productos (primera página)
GET /api/v1/products

# Filtrar productos activos (stock >= 50)
GET /api/v1/products?status=active

# Buscar productos por texto
GET /api/v1/products?search=camisa

# Productos con stock bajo + paginación
GET /api/v1/products?status=low&page=2&per_page=10

# Búsqueda combinada
GET /api/v1/products?search=polo&status=active&page=1&per_page=20
```

#### Respuesta

```json
{
  "total": 5,
  "page": 1,
  "per_page": 20,
  "total_pages": 1,
  "products": [
    {
      "id": 1,
      "sku": "2523HA02",
      "name": "Camisa Polo Manga Corta",
      "category": "Rojo",
      "image": null,
      "locations": [
        {
          "code": "A-12, Izq, A2-12",
          "isMore": false,
          "stock": 45
        },
        {
          "code": "B3-05, Der, B31-05",
          "isMore": false,
          "stock": 12
        }
      ],
      "stock": 57,
      "status": "Activo",
      "statusClass": "active"
    },
    {
      "id": 4,
      "sku": "2525SW01",
      "name": "Sudadera con Capucha",
      "category": "Negro",
      "image": null,
      "locations": [
        {
          "code": "B-20, Izq, B4-20",
          "isMore": false,
          "stock": 5
        }
      ],
      "stock": 5,
      "status": "Stock Bajo",
      "statusClass": "low-stock"
    }
  ]
}
```

#### Códigos de Respuesta

| Código | Descripción |
|--------|-------------|
| 200 | OK - Lista de productos retornada exitosamente |
| 400 | Bad Request - Parámetros inválidos |
| 500 | Internal Server Error |

---

## 📄 2. Detalle de Producto

### `GET /api/v1/products/{product_id}`

Obtiene información completa de un producto específico, incluyendo todas sus ubicaciones.

#### Parámetros Path

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `product_id` | integer | ID del producto |

#### Ejemplo de Request

```bash
GET /api/v1/products/1
```

#### Respuesta

```json
{
  "id": 1,
  "referencia": "A1B2C3",
  "sku": "2523HA02",
  "nombre_producto": "Camisa Polo Manga Corta",
  "name": "Camisa Polo Manga Corta",
  "color_id": "000001",
  "descripcion_color": "Rojo",
  "category": "Rojo",
  "talla": "M",
  "ean": "8445962763983",
  "temporada": "Verano 2024",
  "activo": true,
  "stock": 57,
  "locations": [
    {
      "id": 1,
      "code": "A-12, Izq, A2-12",
      "pasillo": "A",
      "lado": "IZQUIERDA",
      "ubicacion": "12",
      "altura": 2,
      "stock_actual": 45,
      "stock_minimo": 10,
      "prioridad": 3,
      "activa": true
    },
    {
      "id": 2,
      "code": "B3-05, Der, B31-05",
      "pasillo": "B3",
      "lado": "DERECHA",
      "ubicacion": "05",
      "altura": 1,
      "stock_actual": 12,
      "stock_minimo": 5,
      "prioridad": 3,
      "activa": true
    }
  ],
  "status": "Activo",
  "statusClass": "active"
}
```

#### Códigos de Respuesta

| Código | Descripción |
|--------|-------------|
| 200 | OK - Producto encontrado |
| 404 | Not Found - Producto no existe |
| 500 | Internal Server Error |

---

## 📍 3. Ubicaciones de Producto

### `GET /api/v1/products/{product_id}/locations`

Obtiene todas las ubicaciones de un producto con información detallada de stock.

#### Parámetros Path

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `product_id` | integer | ID del producto |

#### Parámetros Query

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `include_inactive` | boolean | `false` | Incluir ubicaciones inactivas |

#### Ejemplo de Request

```bash
# Solo ubicaciones activas
GET /api/v1/products/1/locations

# Incluir ubicaciones inactivas
GET /api/v1/products/1/locations?include_inactive=true
```

#### Respuesta

```json
{
  "product_id": 1,
  "product_name": "Camisa Polo Manga Corta",
  "product_sku": "2523HA02",
  "locations": [
    {
      "id": 1,
      "code": "A-12, Izq, A2-12",
      "pasillo": "A",
      "lado": "IZQUIERDA",
      "ubicacion": "12",
      "altura": 2,
      "stock_actual": 45,
      "stock_minimo": 10,
      "prioridad": 3,
      "activa": true
    },
    {
      "id": 2,
      "code": "B3-05, Der, B31-05",
      "pasillo": "B3",
      "lado": "DERECHA",
      "ubicacion": "05",
      "altura": 1,
      "stock_actual": 12,
      "stock_minimo": 5,
      "prioridad": 3,
      "activa": true
    }
  ],
  "total_locations": 2,
  "total_stock": 57,
  "status": "Activo",
  "status_class": "active"
}
```

#### Códigos de Respuesta

| Código | Descripción |
|--------|-------------|
| 200 | OK - Ubicaciones retornadas |
| 404 | Not Found - Producto no existe |
| 500 | Internal Server Error |

---

## 📊 4. Resumen de Stock

### `GET /api/v1/products/{product_id}/stock-summary`

Obtiene un resumen rápido del stock de un producto, útil para verificaciones rápidas y alertas.

#### Ejemplo de Request

```bash
GET /api/v1/products/1/stock-summary
```

#### Respuesta

```json
{
  "product_id": 1,
  "product_name": "Camisa Polo Manga Corta",
  "sku": "2523HA02",
  "total_stock": 57,
  "total_locations": 2,
  "low_stock_locations": 0,
  "status": "Activo",
  "status_class": "active",
  "needs_restock": false,
  "locations_summary": [
    {
      "code": "A-12, Izq, A2-12",
      "stock": 45,
      "needs_restock": false
    },
    {
      "code": "B3-05, Der, B31-05",
      "stock": 12,
      "needs_restock": false
    }
  ]
}
```

---

## 📋 Modelos de Datos

### ProductListItem (Lista)

```typescript
{
  id: number,                    // ID único
  sku: string,                   // Código SKU
  name: string,                  // Nombre del producto
  category: string,              // Categoría (color/tipo)
  image: string | null,          // URL de imagen (opcional)
  locations: LocationItem[],     // Max 2-3 + indicador
  stock: number,                 // Stock total
  status: string,                // "Activo", "Stock Bajo", "Sin Stock"
  statusClass: string            // "active", "low-stock", "out-of-stock"
}
```

### LocationItem

```typescript
{
  code: string,                  // Formato: "B-08, Der, C2-08"
  isMore: boolean,               // true si es "+X más"
  stock?: number                 // Stock en esta ubicación (opcional)
}
```

### ProductDetail (Detalle Completo)

```typescript
{
  id: number,
  referencia: string,            // Código hexadecimal interno
  sku: string,
  nombre_producto: string,
  name: string,                  // Alias de nombre_producto
  color_id: string,
  descripcion_color: string,
  category: string,              // Alias de descripcion_color
  talla: string,
  ean: string,
  temporada: string,
  activo: boolean,
  stock: number,
  locations: ProductLocationDetail[],
  status: string,
  statusClass: string
}
```

### ProductLocationDetail

```typescript
{
  id: number,
  code: string,                  // Código formateado
  pasillo: string,
  lado: string,
  ubicacion: string,
  altura: number,
  stock_actual: number,
  stock_minimo: number,
  prioridad: number,             // 1-5 (1=alta, 5=baja)
  activa: boolean
}
```

---

## 🔍 Filtros y Búsquedas

### Filtros por Estado

| Valor | Descripción | Condición |
|-------|-------------|-----------|
| `all` | Todos los productos | Sin filtro |
| `active` | Stock normal | stock >= 50 |
| `low` | Stock bajo | 1 <= stock < 50 |
| `out` | Sin stock | stock = 0 |

### Búsqueda de Texto

La búsqueda busca en los siguientes campos (case-insensitive):
- `nombre_producto` - Nombre del producto
- `sku` - Código SKU
- `descripcion_color` - Categoría/Color
- `referencia` - Código hexadecimal interno

**Ejemplo:**
```bash
# Busca "polo" en todos los campos
GET /api/v1/products?search=polo

# Resultado: Encuentra "Camisa Polo Manga Corta"
```

---

## 🎨 Estados de Productos

Los estados se calculan automáticamente basándose en el stock total:

| Estado | Status Text | Status Class | Condición | Color |
|--------|------------|--------------|-----------|-------|
| Activo | "Activo" | "active" | stock >= 50 | 🟢 Verde |
| Stock Bajo | "Stock Bajo" | "low-stock" | 1 <= stock < 50 | 🟡 Amarillo |
| Sin Stock | "Sin Stock" | "out-of-stock" | stock = 0 | 🔴 Rojo |

### Cálculo de Stock Total

El stock total se calcula **sumando el `stock_actual` de todas las ubicaciones activas** del producto:

```python
total_stock = sum(loc.stock_actual for loc in product.locations if loc.activa)
```

---

## 📍 Formato de Ubicaciones

### Formato del Código

```
[Pasillo]-[Posición], [Lado], [Estante]-[Nivel]
```

**Ejemplos:**
- `"A-12, Izq, A2-12"` - Pasillo A, posición 12, lado izquierdo, estante A2 nivel 12
- `"B3-05, Der, B31-05"` - Pasillo B3, posición 05, lado derecho, estante B31 nivel 05
- `"C-08, Izq, C3-08"` - Pasillo C, posición 08, lado izquierdo, estante C3 nivel 08

### Componentes del Código

| Campo | Descripción | Ejemplos |
|-------|-------------|----------|
| Pasillo | Identificador del pasillo | A, B, C, B3, D4 |
| Posición | Número de posición | 08, 12, 20 |
| Lado | IZQUIERDA o DERECHA | Izq, Der |
| Estante | Pasillo + altura | A2, B31, C3 |
| Nivel | Número de nivel | 08, 12, 20 |

### Indicador "+X más"

Cuando un producto tiene más de 2-3 ubicaciones, las adicionales se agrupan:

```json
{
  "locations": [
    { "code": "A-12, Izq, A2-12", "isMore": false },
    { "code": "B3-05, Der, B31-05", "isMore": false },
    { "code": "+2 más", "isMore": true }
  ]
}
```

---

## 🧪 Ejemplos de Uso Completos

### Ejemplo 1: Obtener Productos Activos

```bash
curl -X GET "http://localhost:8000/api/v1/products?status=active" \
  -H "Accept: application/json"
```

### Ejemplo 2: Buscar Camisas

```bash
curl -X GET "http://localhost:8000/api/v1/products?search=camisa" \
  -H "Accept: application/json"
```

### Ejemplo 3: Productos con Stock Bajo (Paginado)

```bash
curl -X GET "http://localhost:8000/api/v1/products?status=low&page=1&per_page=10" \
  -H "Accept: application/json"
```

### Ejemplo 4: Detalle de Producto

```bash
curl -X GET "http://localhost:8000/api/v1/products/1" \
  -H "Accept: application/json"
```

### Ejemplo 5: Todas las Ubicaciones

```bash
curl -X GET "http://localhost:8000/api/v1/products/1/locations" \
  -H "Accept: application/json"
```

### Ejemplo 6: Resumen de Stock

```bash
curl -X GET "http://localhost:8000/api/v1/products/1/stock-summary" \
  -H "Accept: application/json"
```

---

## 🔗 Integración con Frontend React

### Fetch API - Lista de Productos

```javascript
const fetchProducts = async (status = 'all', search = '', page = 1) => {
  const params = new URLSearchParams({
    status,
    page,
    per_page: 20
  });
  
  if (search) {
    params.append('search', search);
  }
  
  const response = await fetch(
    `http://localhost:8000/api/v1/products?${params}`
  );
  const data = await response.json();
  return data;
};

// Uso
const { products, total, total_pages } = await fetchProducts('active', 'camisa', 1);
```

### Fetch API - Detalle de Producto

```javascript
const fetchProductDetail = async (productId) => {
  const response = await fetch(
    `http://localhost:8000/api/v1/products/${productId}`
  );
  const product = await response.json();
  return product;
};
```

### React Hook Personalizado

```javascript
import { useState, useEffect } from 'react';

export const useProducts = (status = 'all', search = '', page = 1) => {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pagination, setPagination] = useState({});
  
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const params = new URLSearchParams({ status, page, per_page: 20 });
        if (search) params.append('search', search);
        
        const response = await fetch(
          `http://localhost:8000/api/v1/products?${params}`
        );
        const data = await response.json();
        
        setProducts(data.products);
        setPagination({
          total: data.total,
          page: data.page,
          perPage: data.per_page,
          totalPages: data.total_pages
        });
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, [status, search, page]);
  
  return { products, loading, error, pagination };
};
```

---

## 📝 Notas Técnicas

### Performance

- **Eager Loading**: Las ubicaciones se cargan con `joinedload()` para evitar N+1 queries
- **Índices**: La tabla tiene índices en campos clave (pasillo, lado, stock)
- **Paginación**: Por defecto 20 productos por página, máximo 100

### Limitaciones Actuales

- ❌ **Imágenes**: Actualmente no hay soporte para imágenes (retorna `null`)
- ⚠️ **Filtro de Estado**: Se aplica en memoria, para mejor performance considerar columna calculada
- 💡 **Categoría**: Se usa `descripcion_color` como categoría temporalmente

### Mejoras Futuras

1. ✅ Agregar soporte para imágenes de productos
2. ✅ Optimizar filtro de estado con columna calculada o vista materializada
3. ✅ Agregar endpoint para actualizar stock
4. ✅ Implementar cache con Redis
5. ✅ Agregar webhooks para notificaciones de stock bajo

---

## 🆘 Troubleshooting

### Problema: "Product not found"

```json
{
  "detail": "Producto con ID 999 no encontrado"
}
```

**Solución**: Verificar que el ID del producto existe en la base de datos.

### Problema: No retorna productos

**Posibles causas:**
1. Base de datos vacía - Ejecutar `python seed_products.py`
2. Filtro muy restrictivo - Probar con `status=all`
3. Búsqueda sin resultados - Verificar términos de búsqueda

### Problema: Stock incorrecto

El stock se calcula sumando todas las ubicaciones activas. Verificar:
1. Ubicaciones marcadas como `activa=true`
2. Campo `stock_actual` actualizado correctamente

---

**Última actualización:** 2026-01-05  
**Versión API:** 1.0.0  
**Documentación Swagger:** http://localhost:8000/docs
