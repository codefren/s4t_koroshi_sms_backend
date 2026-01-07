# 📍 Ejemplos de Uso - Crear Ubicaciones de Producto

Ejemplos prácticos para usar el endpoint `POST /api/v1/products/{id}/locations`

---

## 🚀 Endpoint

```
POST http://localhost:8000/api/v1/products/{product_id}/locations
```

---

## 📋 Ejemplos con cURL

### Ejemplo 1: Crear Ubicación Básica

```bash
curl -X POST "http://localhost:8000/api/v1/products/1/locations" \
  -H "Content-Type: application/json" \
  -d '{
    "pasillo": "A",
    "lado": "IZQUIERDA",
    "ubicacion": "12",
    "altura": 2
  }'
```

**Respuesta:**
```json
{
  "id": 1,
  "product_id": 1,
  "pasillo": "A",
  "lado": "IZQUIERDA",
  "ubicacion": "12",
  "altura": 2,
  "stock_minimo": 0,
  "stock_actual": 0,
  "prioridad": 3,
  "activa": true,
  "codigo_ubicacion": "A-IZQUIERDA-12-2",
  "created_at": "2026-01-06T21:00:00.000000",
  "updated_at": "2026-01-06T21:00:00.000000"
}
```

---

### Ejemplo 2: Crear Ubicación con Stock

```bash
curl -X POST "http://localhost:8000/api/v1/products/1/locations" \
  -H "Content-Type: application/json" \
  -d '{
    "pasillo": "B3",
    "lado": "DERECHA",
    "ubicacion": "05",
    "altura": 1,
    "stock_minimo": 10,
    "stock_actual": 45
  }'
```

**Respuesta:**
```json
{
  "id": 2,
  "product_id": 1,
  "pasillo": "B3",
  "lado": "DERECHA",
  "ubicacion": "05",
  "altura": 1,
  "stock_minimo": 10,
  "stock_actual": 45,
  "prioridad": 3,
  "activa": true,
  "codigo_ubicacion": "B3-DERECHA-05-1",
  "created_at": "2026-01-06T21:01:00.000000",
  "updated_at": "2026-01-06T21:01:00.000000"
}
```

---

### Ejemplo 3: Crear Ubicación con Prioridad Alta

```bash
curl -X POST "http://localhost:8000/api/v1/products/2/locations" \
  -H "Content-Type: application/json" \
  -d '{
    "pasillo": "C",
    "lado": "IZQUIERDA",
    "ubicacion": "08",
    "altura": 3,
    "stock_minimo": 20,
    "stock_actual": 50,
    "prioridad": 1,
    "activa": true
  }'
```

**Descripción:** Prioridad 1 = Alta (se usa primero para picking)

---

### Ejemplo 4: Crear Ubicación Inactiva

```bash
curl -X POST "http://localhost:8000/api/v1/products/2/locations" \
  -H "Content-Type: application/json" \
  -d '{
    "pasillo": "D",
    "lado": "DERECHA",
    "ubicacion": "20",
    "altura": 5,
    "stock_minimo": 5,
    "stock_actual": 8,
    "prioridad": 5,
    "activa": false
  }'
```

**Descripción:** Ubicación inactiva (mantenimiento o bloqueada), prioridad 5 = baja

---

### Ejemplo 5: Crear Múltiples Ubicaciones para un Producto

```bash
# Ubicación 1
curl -X POST "http://localhost:8000/api/v1/products/3/locations" \
  -H "Content-Type: application/json" \
  -d '{
    "pasillo": "A",
    "lado": "IZQUIERDA",
    "ubicacion": "10",
    "altura": 1,
    "stock_actual": 30,
    "prioridad": 1
  }'

# Ubicación 2
curl -X POST "http://localhost:8000/api/v1/products/3/locations" \
  -H "Content-Type: application/json" \
  -d '{
    "pasillo": "B",
    "lado": "DERECHA",
    "ubicacion": "15",
    "altura": 2,
    "stock_actual": 25,
    "prioridad": 2
  }'

# Ubicación 3 (backup/reserva)
curl -X POST "http://localhost:8000/api/v1/products/3/locations" \
  -H "Content-Type: application/json" \
  -d '{
    "pasillo": "C",
    "lado": "IZQUIERDA",
    "ubicacion": "20",
    "altura": 4,
    "stock_actual": 15,
    "prioridad": 3
  }'
```

**Uso:** Un producto con múltiples ubicaciones permite optimizar picking

---

## ❌ Ejemplos de Errores

### Error 1: Producto No Existe

```bash
curl -X POST "http://localhost:8000/api/v1/products/99999/locations" \
  -H "Content-Type: application/json" \
  -d '{
    "pasillo": "A",
    "lado": "IZQUIERDA",
    "ubicacion": "12",
    "altura": 2
  }'
```

**Respuesta (404):**
```json
{
  "detail": "Producto con ID 99999 no encontrado"
}
```

---

### Error 2: Lado Inválido

```bash
curl -X POST "http://localhost:8000/api/v1/products/1/locations" \
  -H "Content-Type: application/json" \
  -d '{
    "pasillo": "A",
    "lado": "CENTRO",
    "ubicacion": "12",
    "altura": 2
  }'
```

**Respuesta (400):**
```json
{
  "detail": "El lado debe ser 'IZQUIERDA' o 'DERECHA'"
}
```

---

### Error 3: Ubicación Duplicada

```bash
# Primera vez (OK)
curl -X POST "http://localhost:8000/api/v1/products/1/locations" \
  -H "Content-Type: application/json" \
  -d '{
    "pasillo": "A",
    "lado": "IZQUIERDA",
    "ubicacion": "12",
    "altura": 2
  }'

# Segunda vez (ERROR - ubicación duplicada)
curl -X POST "http://localhost:8000/api/v1/products/1/locations" \
  -H "Content-Type: application/json" \
  -d '{
    "pasillo": "A",
    "lado": "IZQUIERDA",
    "ubicacion": "12",
    "altura": 2
  }'
```

**Respuesta (400):**
```json
{
  "detail": "Ya existe una ubicación para este producto en A-IZQUIERDA-12-2"
}
```

---

### Error 4: Validación de Altura

```bash
curl -X POST "http://localhost:8000/api/v1/products/1/locations" \
  -H "Content-Type: application/json" \
  -d '{
    "pasillo": "A",
    "lado": "IZQUIERDA",
    "ubicacion": "12",
    "altura": 15
  }'
```

**Respuesta (422):**
```json
{
  "detail": [
    {
      "type": "less_than_equal",
      "loc": ["body", "altura"],
      "msg": "Input should be less than or equal to 10"
    }
  ]
}
```

---

### Error 5: Validación de Prioridad

```bash
curl -X POST "http://localhost:8000/api/v1/products/1/locations" \
  -H "Content-Type: application/json" \
  -d '{
    "pasillo": "A",
    "lado": "IZQUIERDA",
    "ubicacion": "12",
    "altura": 2,
    "prioridad": 10
  }'
```

**Respuesta (422):**
```json
{
  "detail": [
    {
      "type": "less_than_equal",
      "loc": ["body", "prioridad"],
      "msg": "Input should be less than or equal to 5"
    }
  ]
}
```

---

## 🔄 Verificar Ubicación Creada

Después de crear una ubicación, puedes verificarla con:

```bash
# Obtener todas las ubicaciones del producto
curl -X GET "http://localhost:8000/api/v1/products/1/locations"

# Obtener resumen de stock
curl -X GET "http://localhost:8000/api/v1/products/1/stock-summary"
```

---

## 📊 Flujo Completo de Uso

### 1. Verificar que el producto existe

```bash
curl -X GET "http://localhost:8000/api/v1/products/1"
```

### 2. Crear primera ubicación (prioridad alta)

```bash
curl -X POST "http://localhost:8000/api/v1/products/1/locations" \
  -H "Content-Type: application/json" \
  -d '{
    "pasillo": "A",
    "lado": "IZQUIERDA",
    "ubicacion": "12",
    "altura": 2,
    "stock_minimo": 10,
    "stock_actual": 45,
    "prioridad": 1
  }'
```

### 3. Crear segunda ubicación (prioridad media)

```bash
curl -X POST "http://localhost:8000/api/v1/products/1/locations" \
  -H "Content-Type: application/json" \
  -d '{
    "pasillo": "B3",
    "lado": "DERECHA",
    "ubicacion": "05",
    "altura": 1,
    "stock_minimo": 5,
    "stock_actual": 12,
    "prioridad": 3
  }'
```

### 4. Ver todas las ubicaciones creadas

```bash
curl -X GET "http://localhost:8000/api/v1/products/1/locations"
```

**Respuesta:**
```json
{
  "product_id": 1,
  "product_name": "Camisa Polo Manga Corta",
  "product_sku": "2523HA02",
  "total_locations": 2,
  "total_stock": 57,
  "status": "Activo",
  "status_class": "active",
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
      "prioridad": 1,
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
  ]
}
```

---

## 💡 Buenas Prácticas

### 1. **Usar Prioridades Estratégicamente**

- **Prioridad 1**: Ubicaciones de picking primarias (fácil acceso, alto rotación)
- **Prioridad 2-3**: Ubicaciones secundarias
- **Prioridad 4-5**: Ubicaciones de respaldo o difícil acceso

### 2. **Configurar Stock Mínimo**

Siempre establece `stock_minimo` para recibir alertas cuando se necesite reposición.

### 3. **Organizar por Pasillos**

Agrupa productos relacionados en el mismo pasillo para optimizar rutas de picking.

### 4. **Alturas Ergonómicas**

- **Altura 1-2**: Productos pesados o de alta rotación
- **Altura 3-4**: Productos medianos
- **Altura 5+**: Productos ligeros o baja rotación

---

## 🧪 Tests Automatizados

Puedes agregar estos tests a tu script de pruebas:

```python
def test_create_location():
    """Test crear ubicación básica"""
    response = requests.post(
        f"{BASE_URL}/products/1/locations",
        json={
            "pasillo": "A",
            "lado": "IZQUIERDA",
            "ubicacion": "12",
            "altura": 2
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["pasillo"] == "A"
    assert data["lado"] == "IZQUIERDA"
    assert "id" in data

def test_create_location_duplicate():
    """Test detectar ubicación duplicada"""
    # Crear primera vez
    requests.post(
        f"{BASE_URL}/products/1/locations",
        json={"pasillo": "A", "lado": "IZQUIERDA", "ubicacion": "12", "altura": 2}
    )
    
    # Intentar crear duplicado
    response = requests.post(
        f"{BASE_URL}/products/1/locations",
        json={"pasillo": "A", "lado": "IZQUIERDA", "ubicacion": "12", "altura": 2}
    )
    assert response.status_code == 400
```

---

**Última actualización:** 2026-01-06  
**Versión API:** 1.0.0  
**Endpoint:** `POST /api/v1/products/{id}/locations`
