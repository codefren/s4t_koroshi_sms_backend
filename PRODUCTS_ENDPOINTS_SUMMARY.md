# 🚀 Resumen Rápido - API de Productos

Sistema completo de endpoints REST para productos y ubicaciones, diseñado para el frontend React.

## ✅ Archivos Creados

### 1. **Modelos Pydantic** (`src/core/domain/product_api_models.py`)
- ✅ `ProductListItem` - Modelo para listado
- ✅ `ProductDetail` - Modelo para detalle completo
- ✅ `ProductLocationsResponse` - Modelo para ubicaciones
- ✅ `LocationItem` - Modelo para ubicaciones individuales
- ✅ `ProductListResponse` - Respuesta paginada
- ✅ Funciones helper: `calculate_product_status()`, `format_location_code()`

### 2. **Router API** (`src/adapters/primary/api/product_router.py`)
4 endpoints implementados:
- ✅ `GET /api/v1/products` - Lista con filtros y búsqueda
- ✅ `GET /api/v1/products/{id}` - Detalle de producto
- ✅ `GET /api/v1/products/{id}/locations` - Todas las ubicaciones
- ✅ `GET /api/v1/products/{id}/stock-summary` - Resumen de stock

### 3. **Integración** (`src/main.py`)
- ✅ Router registrado en FastAPI
- ✅ CORS configurado
- ✅ Documentación Swagger disponible

### 4. **Documentación**
- ✅ `PRODUCTS_API.md` - Documentación completa (800+ líneas)
- ✅ `test_products_api.py` - Script de pruebas (11 tests)
- ✅ Este resumen

### 5. **Modelo ORM Actualizado**
- ✅ Campo `prioridad` restaurado en `ProductLocation`
- ✅ Compatible con SQL Server existente

---

## 🎯 Endpoints Disponibles

```
BASE: http://localhost:8000/api/v1/products
```

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/products` | GET | Lista productos con filtros |
| `/products?status=active` | GET | Solo productos activos |
| `/products?search=camisa` | GET | Búsqueda de texto |
| `/products/{id}` | GET | Detalle completo |
| `/products/{id}/locations` | GET | Todas las ubicaciones |
| `/products/{id}/stock-summary` | GET | Resumen rápido |

---

## 🔥 Quick Start

### 1. Cargar Datos (Si la BD está vacía)

```bash
python seed_products.py
```

### 2. Iniciar Servidor

```bash
cd src
uvicorn main:app --reload
```

### 3. Probar Endpoints

```bash
# Opción 1: Script de tests
python test_products_api.py

# Opción 2: Swagger UI
# Abrir http://localhost:8000/docs

# Opción 3: Curl manual
curl http://localhost:8000/api/v1/products
```

---

## 📊 Ejemplo de Respuesta

### Lista de Productos

```bash
GET /api/v1/products?status=active&page=1&per_page=5
```

```json
{
  "total": 5,
  "page": 1,
  "per_page": 5,
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
    }
  ]
}
```

---

## 🎨 Características Implementadas

### ✅ Filtros de Estado
- **all** - Todos los productos
- **active** - Stock >= 50 (verde)
- **low** - Stock 1-49 (amarillo)
- **out** - Stock = 0 (rojo)

### ✅ Búsqueda Inteligente
Busca en:
- Nombre del producto
- SKU
- Categoría (descripción_color)
- Referencia (código hexadecimal)

### ✅ Paginación
- Parámetros: `page`, `per_page`
- Rango: 1-100 productos por página
- Default: 20 por página

### ✅ Formato de Ubicaciones
```
"A-12, Izq, A2-12"
[Pasillo]-[Pos], [Lado], [Estante]-[Nivel]
```

### ✅ Indicador "+X más"
Cuando hay más de 2 ubicaciones:
```json
[
  { "code": "A-12, Izq, A2-12", "isMore": false },
  { "code": "B3-05, Der, B31-05", "isMore": false },
  { "code": "+3 más", "isMore": true }
]
```

### ✅ Cálculo Automático de Estados

| Stock | Estado | Clase CSS |
|-------|--------|-----------|
| >= 50 | "Activo" | "active" |
| 1-49 | "Stock Bajo" | "low-stock" |
| 0 | "Sin Stock" | "out-of-stock" |

---

## 🧪 Testing

### Script Automático

```bash
python test_products_api.py
```

Tests incluidos:
1. ✅ Listar productos
2. ✅ Filtrar activos
3. ✅ Filtrar stock bajo
4. ✅ Filtrar sin stock
5. ✅ Búsqueda de texto
6. ✅ Paginación
7. ✅ Detalle de producto
8. ✅ Ubicaciones de producto
9. ✅ Resumen de stock
10. ✅ Filtros combinados
11. ✅ Producto inexistente (404)

### Tests Manuales (Swagger)

1. Abrir http://localhost:8000/docs
2. Expandir `/api/v1/products`
3. Probar cada endpoint
4. Ver respuestas en tiempo real

---

## 🔗 Integración con Frontend React

### Hook Personalizado

```javascript
// useProducts.js
import { useState, useEffect } from 'react';

export const useProducts = (status = 'all', search = '', page = 1) => {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
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
          totalPages: data.total_pages
        });
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, [status, search, page]);
  
  return { products, loading, pagination };
};
```

### Uso en Componente

```javascript
// Products.jsx
import { useProducts } from './hooks/useProducts';

function Products() {
  const [status, setStatus] = useState('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  
  const { products, loading, pagination } = useProducts(status, search, page);
  
  if (loading) return <div>Cargando...</div>;
  
  return (
    <div>
      {products.map(product => (
        <ProductCard key={product.id} product={product} />
      ))}
    </div>
  );
}
```

---

## 📝 Mapeo de Campos

| Frontend (Products.jsx) | Backend (API) | Origen |
|------------------------|---------------|--------|
| `id` | `id` | ProductReference.id |
| `sku` | `sku` | ProductReference.sku |
| `name` | `name` | ProductReference.nombre_producto |
| `category` | `category` | ProductReference.descripcion_color |
| `image` | `image` | null (TODO) |
| `locations[]` | `locations[]` | Calculado + formateado |
| `stock` | `stock` | Suma de stock_actual |
| `status` | `status` | Calculado automáticamente |
| `statusClass` | `statusClass` | Calculado automáticamente |

---

## 🚧 TODO / Mejoras Futuras

### Próximas Implementaciones

- [ ] Soporte para imágenes de productos
- [ ] Endpoint para actualizar stock
- [ ] Webhooks para alertas de stock bajo
- [ ] Cache con Redis
- [ ] Exportar a Excel/CSV
- [ ] Historial de cambios de stock
- [ ] API de estadísticas agregadas
- [ ] Filtro por múltiples categorías
- [ ] Ordenamiento personalizado

### Optimizaciones

- [ ] Agregar columna `stock_total` calculada
- [ ] Mover filtro de estado a SQL
- [ ] Índice full-text para búsqueda
- [ ] Implementar rate limiting
- [ ] Comprimir respuestas grandes

---

## 📚 Documentación Relacionada

1. **PRODUCTS_API.md** - Documentación completa de API (leer primero)
2. **PRODUCTS_SYSTEM.md** - Documentación de modelos ORM
3. **FIXTURES_GUIDE.md** - Guía de fixtures para seeding
4. **API_ENDPOINTS.md** - Documentación de otros endpoints (órdenes)

---

## 🆘 Troubleshooting

### El servidor no inicia

```bash
# Verificar que estás en el directorio correcto
cd src

# Activar entorno virtual
source venv/bin/activate

# Instalar dependencias si faltan
pip install fastapi uvicorn sqlalchemy pydantic

# Iniciar servidor
uvicorn main:app --reload
```

### No hay productos

```bash
# Cargar datos de ejemplo
python seed_products.py

# Verificar que se cargaron
python seed_products.py --stats
```

### Error "Module not found"

```bash
# Asegúrate de ejecutar desde el directorio raíz
cd /home/efrenoscar/Project/s4t_koroshi_sms_backend

# Verifica la estructura
ls -la src/adapters/primary/api/
```

### CORS Error en Frontend

El backend ya tiene CORS configurado para:
- `http://localhost:5173` (Vite)
- `http://localhost:3000` (Create React App)

Si usas otro puerto, agrégalo en `main.py`:
```python
allow_origins=["http://localhost:5173", "http://localhost:TU_PUERTO"]
```

---

## ✅ Checklist de Implementación Completa

### Backend
- [x] Modelos Pydantic creados
- [x] Router implementado
- [x] Integrado en FastAPI
- [x] CORS configurado
- [x] Documentación Swagger
- [x] Tests creados

### Modelos ORM
- [x] Campo `prioridad` restaurado
- [x] Compatible con SQL Server
- [x] Índices optimizados

### Datos de Ejemplo
- [x] Fixtures implementadas
- [x] Script de seeding
- [x] 5 productos de ejemplo

### Documentación
- [x] API completa documentada
- [x] Ejemplos de uso
- [x] Integración con React
- [x] Este resumen

---

## 🎉 ¡Listo para Usar!

### Comandos Rápidos

```bash
# 1. Cargar datos (primera vez)
python seed_products.py

# 2. Iniciar servidor
cd src && uvicorn main:app --reload

# 3. Probar API
python test_products_api.py

# 4. Ver documentación
# Abrir http://localhost:8000/docs

# 5. Probar desde frontend
# curl http://localhost:8000/api/v1/products
```

---

**¡Los endpoints están listos para ser consumidos por el frontend React!** 🚀

**Última actualización:** 2026-01-05  
**Versión:** 1.0.0  
**Autor:** Sistema SMS Backend
