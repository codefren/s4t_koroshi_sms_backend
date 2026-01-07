# ✅ Endpoint POST - Crear Ubicaciones de Producto

## 🎯 Resumen Rápido

**Endpoint implementado:** ✅ `POST /api/v1/products/{product_id}/locations`

---

## 📝 Request Body

```json
{
  "pasillo": "A",              // Requerido: Identificador del pasillo
  "lado": "IZQUIERDA",         // Requerido: "IZQUIERDA" o "DERECHA"
  "ubicacion": "12",           // Requerido: Posición específica
  "altura": 2,                 // Requerido: Nivel 1-10
  "stock_minimo": 10,          // Opcional: Stock mínimo (default: 0)
  "stock_actual": 45,          // Opcional: Stock actual (default: 0)
  "prioridad": 3,              // Opcional: 1-5 (default: 3, 1=alta)
  "activa": true               // Opcional: true/false (default: true)
}
```

---

## ✅ Respuesta Exitosa (201)

```json
{
  "id": 5,
  "product_id": 1,
  "pasillo": "A",
  "lado": "IZQUIERDA",
  "ubicacion": "12",
  "altura": 2,
  "stock_minimo": 10,
  "stock_actual": 45,
  "prioridad": 3,
  "activa": true,
  "codigo_ubicacion": "A-IZQUIERDA-12-2",
  "created_at": "2026-01-06T21:00:00.000000",
  "updated_at": "2026-01-06T21:00:00.000000"
}
```

---

## 🚀 Ejemplo Rápido

```bash
curl -X POST "http://localhost:8000/api/v1/products/1/locations" \
  -H "Content-Type: application/json" \
  -d '{
    "pasillo": "A",
    "lado": "IZQUIERDA",
    "ubicacion": "12",
    "altura": 2,
    "stock_actual": 45,
    "stock_minimo": 10,
    "prioridad": 1
  }'
```

---

## ✅ Validaciones Implementadas

1. ✅ **Producto existe** - Error 404 si no existe
2. ✅ **Lado válido** - Solo "IZQUIERDA" o "DERECHA"
3. ✅ **Sin duplicados** - No permite ubicaciones duplicadas
4. ✅ **Altura válida** - Rango 1-10
5. ✅ **Prioridad válida** - Rango 1-5
6. ✅ **Stock positivo** - >= 0

---

## ❌ Errores Posibles

| Código | Error | Solución |
|--------|-------|----------|
| 404 | Producto no encontrado | Verificar que el product_id existe |
| 400 | Lado inválido | Usar "IZQUIERDA" o "DERECHA" |
| 400 | Ubicación duplicada | Ya existe esa ubicación para ese producto |
| 422 | Validación fallida | Revisar altura (1-10) y prioridad (1-5) |

---

## 📊 Campos del Modelo

### Campos Requeridos

| Campo | Tipo | Validación | Ejemplo |
|-------|------|------------|---------|
| `pasillo` | string | Max 10 chars | "A", "B3", "C" |
| `lado` | string | "IZQUIERDA"/"DERECHA" | "IZQUIERDA" |
| `ubicacion` | string | Max 20 chars | "12", "05" |
| `altura` | integer | 1-10 | 2 |

### Campos Opcionales

| Campo | Tipo | Default | Validación |
|-------|------|---------|------------|
| `stock_minimo` | integer | 0 | >= 0 |
| `stock_actual` | integer | 0 | >= 0 |
| `prioridad` | integer | 3 | 1-5 |
| `activa` | boolean | true | true/false |

---

## 🎨 Uso de Prioridad

```
1 = Alta      → Ubicación principal (fácil acceso)
2 = Media-Alta → Primera alternativa
3 = Media     → Default (ubicación estándar)
4 = Media-Baja → Segunda alternativa
5 = Baja      → Reserva o difícil acceso
```

---

## 📍 Código de Ubicación

El sistema genera automáticamente un `codigo_ubicacion`:

**Formato:** `{pasillo}-{lado}-{ubicacion}-{altura}`

**Ejemplos:**
- `A-IZQUIERDA-12-2`
- `B3-DERECHA-05-1`
- `C-IZQUIERDA-08-3`

---

## 🔄 Flujo Recomendado

1. **Verificar producto**
   ```bash
   GET /api/v1/products/1
   ```

2. **Crear ubicación principal** (prioridad 1)
   ```bash
   POST /api/v1/products/1/locations
   ```

3. **Crear ubicaciones secundarias** (prioridad 2-3)
   ```bash
   POST /api/v1/products/1/locations
   ```

4. **Verificar ubicaciones creadas**
   ```bash
   GET /api/v1/products/1/locations
   ```

---

## 📚 Archivos Relacionados

- **Documentación completa:** `LOCATIONS_INTEGRATION_GUIDE.md`
- **Ejemplos detallados:** `examples_create_location.md`
- **API general:** `PRODUCTS_API.md`
- **Código del endpoint:** `src/adapters/primary/api/product_router.py`

---

## 🧪 Probar en Swagger

1. Abrir http://localhost:8000/docs
2. Buscar `POST /api/v1/products/{product_id}/locations`
3. Click en "Try it out"
4. Ingresar `product_id` y el JSON
5. Click en "Execute"

---

**Estado:** ✅ Implementado y Funcionando  
**Última actualización:** 2026-01-06  
**Versión:** 1.0.0
