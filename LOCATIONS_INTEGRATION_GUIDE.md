# 📍 Guía de Integración - Gestión de Ubicaciones de Productos

Documentación completa para integrar los endpoints de ubicaciones de productos con el frontend React.

---

## 📋 Tabla de Contenidos

- [Datos Necesarios de la API](#-datos-necesarios-de-la-api)
- [Endpoints Disponibles](#-endpoints-disponibles)
- [Operaciones CRUD](#-operaciones-crud)
- [Mapeo de Campos UI ↔ API](#-mapeo-de-campos-ui--api)
- [Visualización de Stock](#-visualización-de-stock)
- [Implementación Frontend](#-implementación-frontend)
- [Ejemplos de Código](#-ejemplos-de-código)

---

## 🎯 Datos Necesarios de la API

### 1. Información del Producto

**Endpoint:** `GET /api/v1/products/{id}`

**Respuesta Actual:**

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
  "locations": [...],
  "status": "Activo",
  "statusClass": "active"
}
```

**Mapeo para el Frontend:**

```javascript
{
  id: response.id,                      // ID del producto
  sku: response.sku,                    // Referencia/SKU
  name: response.nombre_producto,       // Nombre del producto
  category: response.color_id,          // Color ID como categoría
  size: response.talla,                 // Talla
  image: response.image,                // Imagen (opcional, actualmente null)
  stock_total: response.stock,          // Stock total calculado
  status: response.status               // "Activo", "Stock Bajo", "Sin Stock"
}
```

---

### 2. Ubicaciones del Producto

**Endpoint:** `GET /api/v1/products/{id}/locations`

**Respuesta Actual:**

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
  ]
}
```

**Transformación para el Frontend:**

```javascript
{
  product_id: response.product_id,
  total_locations: response.total_locations,
  locations: response.locations.map(loc => ({
    location_id: loc.id,                           // ID único
    pasillo: loc.pasillo,                          // "A", "B3", etc.
    lado: loc.lado === "IZQUIERDA" ? "Izquierdo" : "Derecho",
    ubicacion: loc.code,                           // Código formateado completo
    zona: `Pasillo ${loc.pasillo}`,                // Derivado del pasillo
    altura: `Nivel ${loc.altura}`,                 // "Nivel 1", "Nivel 2", etc.
    stock_actual: loc.stock_actual,                // Stock en esta ubicación
    stock_max: loc.stock_actual + 20,              // Calculado o desde campo futuro
    stock_min: loc.stock_minimo,                   // Stock mínimo
    stock_percent: Math.round((loc.stock_actual / (loc.stock_actual + 20)) * 100),
    stock_status: loc.stock_actual >= loc.stock_minimo ? "good" : "low",
    prioridad: loc.prioridad,                      // 1-5 (1=alta, 5=baja)
    activa: loc.activa                             // true/false
  }))
}
```

---

## 🔌 Endpoints Disponibles

### Endpoints Existentes (Ya Implementados)

| Método | Endpoint | Descripción | Estado |
|--------|----------|-------------|--------|
| GET | `/api/v1/products` | Lista todos los productos | ✅ Listo |
| GET | `/api/v1/products/{id}` | Detalle de un producto | ✅ Listo |
| GET | `/api/v1/products/{id}/locations` | Ubicaciones de un producto | ✅ Listo |
| GET | `/api/v1/products/{id}/stock-summary` | Resumen de stock | ✅ Listo |

### Endpoints Necesarios (A Implementar)

| Método | Endpoint | Descripción | Estado |
|--------|----------|-------------|--------|
| POST | `/api/v1/products/{id}/locations` | Crear nueva ubicación | ✅ Implementado |
| PUT | `/api/v1/products/{product_id}/locations/{location_id}` | Actualizar ubicación | ⏳ Pendiente |
| DELETE | `/api/v1/products/{product_id}/locations/{location_id}` | Eliminar ubicación | ⏳ Pendiente |
| GET | `/api/v1/catalogs/pasillos` | Catálogo de pasillos | ⏳ Opcional |
| GET | `/api/v1/catalogs/zonas` | Catálogo de zonas | ⏳ Opcional |

---

## 🔄 Operaciones CRUD

### 1. ✅ LEER Ubicaciones (Implementado)

**Endpoint:** `GET /api/v1/products/{id}/locations`

```bash
curl -X GET "http://localhost:8000/api/v1/products/1/locations" \
  -H "Accept: application/json"
```

**Parámetros Query:**
- `include_inactive` (boolean): Incluir ubicaciones inactivas (default: false)

---

### 2. ✅ CREAR Nueva Ubicación (Implementado)

**Endpoint:** `POST /api/v1/products/{id}/locations`

**Request Body:**

```json
{
  "pasillo": "A",
  "lado": "IZQUIERDA",
  "ubicacion": "15",
  "altura": 2,
  "stock_minimo": 25,
  "stock_actual": 30,
  "prioridad": 3,
  "activa": true
}
```

**Validaciones:**
- `pasillo`: Requerido, max 10 caracteres
- `lado`: Requerido, valores: "IZQUIERDA" o "DERECHA"
- `ubicacion`: Requerido, max 20 caracteres
- `altura`: Requerido, rango 1-10
- `stock_minimo`: Opcional, >= 0
- `stock_actual`: Opcional, >= 0
- `prioridad`: Opcional, rango 1-5 (default: 3)
- `activa`: Opcional (default: true)

**Respuesta (201 Created):**

```json
{
  "id": 5,
  "product_id": 1,
  "pasillo": "A",
  "lado": "IZQUIERDA",
  "ubicacion": "15",
  "altura": 2,
  "stock_minimo": 25,
  "stock_actual": 30,
  "prioridad": 3,
  "activa": true,
  "codigo_ubicacion": "A-IZQUIERDA-15-2",
  "created_at": "2026-01-06T21:00:00.000000",
  "updated_at": "2026-01-06T21:00:00.000000"
}
```

**Código Frontend:**

```javascript
const createLocation = async (productId, locationData) => {
  const response = await fetch(
    `http://localhost:8000/api/v1/products/${productId}/locations`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(locationData)
    }
  );
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Error al crear ubicación');
  }
  
  return await response.json();
};
```

---

### 3. ⏳ ACTUALIZAR Ubicación (Pendiente)

**Endpoint:** `PUT /api/v1/products/{product_id}/locations/{location_id}`

**Request Body (todos los campos son opcionales):**

```json
{
  "pasillo": "B",
  "lado": "DERECHA",
  "ubicacion": "20",
  "altura": 3,
  "stock_minimo": 30,
  "stock_actual": 50,
  "prioridad": 2,
  "activa": true
}
```

**Respuesta Esperada (200 OK):**

```json
{
  "message": "Ubicación actualizada exitosamente",
  "location": {
    "id": 5,
    "code": "B-20, Der, B3-20",
    "pasillo": "B",
    "lado": "DERECHA",
    "ubicacion": "20",
    "altura": 3,
    "stock_actual": 50,
    "stock_minimo": 30,
    "prioridad": 2,
    "activa": true
  }
}
```

**Código Frontend:**

```javascript
const updateLocation = async (productId, locationId, updates) => {
  const response = await fetch(
    `http://localhost:8000/api/v1/products/${productId}/locations/${locationId}`,
    {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updates)
    }
  );
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Error al actualizar ubicación');
  }
  
  return await response.json();
};
```

---

### 4. ⏳ ELIMINAR Ubicación (Pendiente)

**Endpoint:** `DELETE /api/v1/products/{product_id}/locations/{location_id}`

**Respuesta Esperada (200 OK):**

```json
{
  "message": "Ubicación eliminada exitosamente",
  "location_id": 5
}
```

**Código Frontend:**

```javascript
const deleteLocation = async (productId, locationId) => {
  const response = await fetch(
    `http://localhost:8000/api/v1/products/${productId}/locations/${locationId}`,
    {
      method: 'DELETE'
    }
  );
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Error al eliminar ubicación');
  }
  
  return await response.json();
};
```

---

## 📊 Mapeo de Campos UI ↔ API

### Tabla de Mapeo Completa

| Campo en UI | Nombre en Código | Campo API | Tipo | Origen |
|------------|------------------|-----------|------|--------|
| Referencia | `product.sku` | `sku` | string | ProductReference.sku |
| Nombre de producto | `product.name` | `nombre_producto` | string | ProductReference.nombre_producto |
| Color ID | `product.category` | `color_id` | string | ProductReference.color_id |
| Talla | `product.size` | `talla` | string | ProductReference.talla |
| Pasillo | `location.pasillo` | `pasillo` | string | ProductLocation.pasillo |
| Lado | `location.lado` | `lado` | enum | ProductLocation.lado |
| Ubicación (Código) | `location.ubicacion` | `code` | string | Calculado |
| Zona | `location.zona` | - | string | Derivado de pasillo |
| Altura | `location.altura` | `altura` | number | ProductLocation.altura |
| Stock Actual | `location.stockActual` | `stock_actual` | number | ProductLocation.stock_actual |
| Stock Máximo | `location.stockMax` | - | number | A calcular/agregar |
| Stock Mínimo | `location.stockMin` | `stock_minimo` | number | ProductLocation.stock_minimo |
| Estado de Stock | `location.stockStatus` | - | enum | Calculado |
| Prioridad | `location.prioridad` | `prioridad` | number | ProductLocation.prioridad |
| Activa | `location.activa` | `activa` | boolean | ProductLocation.activa |

### Conversiones Necesarias

#### 1. Lado (API → Frontend)

```javascript
const convertirLado = (ladoAPI) => {
  return ladoAPI === "IZQUIERDA" ? "Izquierdo" : "Derecho";
};
```

#### 2. Lado (Frontend → API)

```javascript
const convertirLadoAPI = (ladoUI) => {
  return ladoUI === "Izquierdo" ? "IZQUIERDA" : "DERECHA";
};
```

#### 3. Altura (API → Frontend)

```javascript
const formatearAltura = (alturaNumero) => {
  return `Nivel ${alturaNumero}`;
};
```

#### 4. Altura (Frontend → API)

```javascript
const extraerAltura = (alturaTexto) => {
  // "Nivel 2" → 2
  return parseInt(alturaTexto.replace("Nivel ", ""));
};
```

#### 5. Zona (Derivar de Pasillo)

```javascript
const calcularZona = (pasillo) => {
  return `Pasillo ${pasillo}`;
};
```

#### 6. Stock Status (Calcular)

```javascript
const calcularStockStatus = (stockActual, stockMinimo) => {
  return stockActual >= stockMinimo ? "good" : "low";
};
```

#### 7. Stock Percent (Calcular)

```javascript
const calcularStockPercent = (stockActual, stockMaximo) => {
  if (stockMaximo === 0) return 0;
  return Math.round((stockActual / stockMaximo) * 100);
};
```

---

## 🎨 Visualización de Stock

### Estados de Stock

| Estado | Color | Gradiente | Condición |
|--------|-------|-----------|-----------|
| `good` | Verde | `linear-gradient(315deg, #2ECC71 64.64%, #27AE60 135.36%)` | `stock_actual >= stock_minimo` |
| `low` | Rojo | `linear-gradient(315deg, #E74C3C 64.64%, #C0392B 135.36%)` | `stock_actual < stock_minimo` |

### Función Helper para Colores

```javascript
const getStockColor = (status) => {
  const colors = {
    good: 'linear-gradient(315deg, #2ECC71 64.64%, #27AE60 135.36%)',
    low: 'linear-gradient(315deg, #E74C3C 64.64%, #C0392B 135.36%)'
  };
  return colors[status] || colors.good;
};
```

### Barra de Progreso de Stock

```jsx
<div className="stock-bar">
  <div 
    className="stock-fill"
    style={{
      width: `${location.stock_percent}%`,
      background: getStockColor(location.stock_status)
    }}
  />
</div>

<div className="stock-text">
  {location.stockActual} / {location.stockMax} unidades
</div>
```

---

## 💻 Implementación Frontend

### 1. Servicio de Ubicaciones

**Archivo:** `src/services/locationService.js`

```javascript
const API_BASE_URL = 'http://localhost:8000/api/v1';

export const locationService = {
  /**
   * Obtiene todas las ubicaciones de un producto
   */
  async getLocationsByProduct(productId, includeInactive = false) {
    const params = new URLSearchParams();
    if (includeInactive) {
      params.append('include_inactive', 'true');
    }
    
    const response = await fetch(
      `${API_BASE_URL}/products/${productId}/locations?${params}`
    );
    
    if (!response.ok) {
      throw new Error('Error al obtener ubicaciones');
    }
    
    const data = await response.json();
    
    // Transformar datos para el frontend
    return {
      product_id: data.product_id,
      total_locations: data.total_locations,
      locations: data.locations.map(loc => ({
        location_id: loc.id,
        pasillo: loc.pasillo,
        lado: loc.lado === "IZQUIERDA" ? "Izquierdo" : "Derecho",
        ubicacion: loc.code,
        zona: `Pasillo ${loc.pasillo}`,
        altura: `Nivel ${loc.altura}`,
        stock_actual: loc.stock_actual,
        stock_max: loc.stock_actual + 20, // TODO: Obtener de API
        stock_min: loc.stock_minimo,
        stock_percent: Math.round(
          (loc.stock_actual / (loc.stock_actual + 20)) * 100
        ),
        stock_status: loc.stock_actual >= loc.stock_minimo ? "good" : "low",
        prioridad: loc.prioridad,
        activa: loc.activa
      }))
    };
  },

  /**
   * Crea una nueva ubicación para un producto
   */
  async createLocation(productId, locationData) {
    // Transformar datos del frontend a formato API
    const apiData = {
      pasillo: locationData.pasillo,
      lado: locationData.lado === "Izquierdo" ? "IZQUIERDA" : "DERECHA",
      ubicacion: locationData.ubicacion,
      altura: parseInt(locationData.altura.replace("Nivel ", "")),
      stock_minimo: locationData.stock_min,
      stock_actual: locationData.stock_actual || 0,
      prioridad: locationData.prioridad || 3,
      activa: locationData.activa !== false
    };
    
    const response = await fetch(
      `${API_BASE_URL}/products/${productId}/locations`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(apiData)
      }
    );
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Error al crear ubicación');
    }
    
    return await response.json();
  },

  /**
   * Actualiza una ubicación existente
   */
  async updateLocation(productId, locationId, updates) {
    // Transformar solo los campos que cambiaron
    const apiUpdates = {};
    
    if (updates.pasillo) apiUpdates.pasillo = updates.pasillo;
    if (updates.lado) {
      apiUpdates.lado = updates.lado === "Izquierdo" ? "IZQUIERDA" : "DERECHA";
    }
    if (updates.ubicacion) apiUpdates.ubicacion = updates.ubicacion;
    if (updates.altura) {
      apiUpdates.altura = parseInt(updates.altura.replace("Nivel ", ""));
    }
    if (updates.stock_min !== undefined) apiUpdates.stock_minimo = updates.stock_min;
    if (updates.stock_actual !== undefined) apiUpdates.stock_actual = updates.stock_actual;
    if (updates.prioridad !== undefined) apiUpdates.prioridad = updates.prioridad;
    if (updates.activa !== undefined) apiUpdates.activa = updates.activa;
    
    const response = await fetch(
      `${API_BASE_URL}/products/${productId}/locations/${locationId}`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(apiUpdates)
      }
    );
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Error al actualizar ubicación');
    }
    
    return await response.json();
  },

  /**
   * Elimina una ubicación
   */
  async deleteLocation(productId, locationId) {
    const response = await fetch(
      `${API_BASE_URL}/products/${productId}/locations/${locationId}`,
      {
        method: 'DELETE'
      }
    );
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Error al eliminar ubicación');
    }
    
    return await response.json();
  }
};
```

---

### 2. Hook Personalizado

**Archivo:** `src/hooks/useLocations.js`

```javascript
import { useState, useEffect } from 'react';
import { locationService } from '../services/locationService';

export const useLocations = (productId) => {
  const [locations, setLocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [totalLocations, setTotalLocations] = useState(0);

  const fetchLocations = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await locationService.getLocationsByProduct(productId);
      setLocations(data.locations);
      setTotalLocations(data.total_locations);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (productId) {
      fetchLocations();
    }
  }, [productId]);

  const addLocation = async (locationData) => {
    try {
      setLoading(true);
      await locationService.createLocation(productId, locationData);
      await fetchLocations(); // Recargar lista
      return { success: true };
    } catch (err) {
      setError(err.message);
      return { success: false, error: err.message };
    } finally {
      setLoading(false);
    }
  };

  const updateLocation = async (locationId, updates) => {
    try {
      setLoading(true);
      await locationService.updateLocation(productId, locationId, updates);
      await fetchLocations(); // Recargar lista
      return { success: true };
    } catch (err) {
      setError(err.message);
      return { success: false, error: err.message };
    } finally {
      setLoading(false);
    }
  };

  const removeLocation = async (locationId) => {
    try {
      setLoading(true);
      await locationService.deleteLocation(productId, locationId);
      await fetchLocations(); // Recargar lista
      return { success: true };
    } catch (err) {
      setError(err.message);
      return { success: false, error: err.message };
    } finally {
      setLoading(false);
    }
  };

  return {
    locations,
    totalLocations,
    loading,
    error,
    addLocation,
    updateLocation,
    removeLocation,
    refresh: fetchLocations
  };
};
```

---

### 3. Componente de Gestión de Ubicaciones

**Ejemplo de uso en componente:**

```jsx
import React, { useState } from 'react';
import { useLocations } from '../hooks/useLocations';

function LocationManager({ product }) {
  const {
    locations,
    totalLocations,
    loading,
    error,
    addLocation,
    updateLocation,
    removeLocation
  } = useLocations(product.id);

  const [showAddModal, setShowAddModal] = useState(false);
  const [editingLocation, setEditingLocation] = useState(null);

  const handleAddLocation = async (formData) => {
    const result = await addLocation(formData);
    
    if (result.success) {
      setShowAddModal(false);
      alert('Ubicación creada exitosamente');
    } else {
      alert(`Error: ${result.error}`);
    }
  };

  const handleEditLocation = async (locationId, updates) => {
    const result = await updateLocation(locationId, updates);
    
    if (result.success) {
      setEditingLocation(null);
      alert('Ubicación actualizada exitosamente');
    } else {
      alert(`Error: ${result.error}`);
    }
  };

  const handleDeleteLocation = async (locationId) => {
    if (!confirm('¿Está seguro de eliminar esta ubicación?')) {
      return;
    }
    
    const result = await removeLocation(locationId);
    
    if (result.success) {
      alert('Ubicación eliminada exitosamente');
    } else {
      alert(`Error: ${result.error}`);
    }
  };

  if (loading) return <div>Cargando ubicaciones...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div className="location-manager">
      <div className="header">
        <h2>Ubicaciones ({totalLocations})</h2>
        <button onClick={() => setShowAddModal(true)}>
          Añadir Ubicación
        </button>
      </div>

      <div className="locations-grid">
        {locations.map(location => (
          <LocationCard
            key={location.location_id}
            location={location}
            onEdit={() => setEditingLocation(location)}
            onDelete={() => handleDeleteLocation(location.location_id)}
          />
        ))}
      </div>

      {showAddModal && (
        <AddLocationModal
          onSave={handleAddLocation}
          onClose={() => setShowAddModal(false)}
        />
      )}

      {editingLocation && (
        <EditLocationModal
          location={editingLocation}
          onSave={(updates) => handleEditLocation(editingLocation.location_id, updates)}
          onClose={() => setEditingLocation(null)}
        />
      )}
    </div>
  );
}
```

---

## 🔧 Validaciones de Formulario

### Validaciones Requeridas

```javascript
const validateLocationForm = (formData) => {
  const errors = {};

  // Pasillo (requerido)
  if (!formData.pasillo || formData.pasillo.trim() === '') {
    errors.pasillo = 'El pasillo es requerido';
  } else if (formData.pasillo.length > 10) {
    errors.pasillo = 'El pasillo no puede tener más de 10 caracteres';
  }

  // Lado (requerido)
  if (!formData.lado) {
    errors.lado = 'El lado es requerido';
  } else if (!['Izquierdo', 'Derecho'].includes(formData.lado)) {
    errors.lado = 'El lado debe ser Izquierdo o Derecho';
  }

  // Ubicación (requerida)
  if (!formData.ubicacion || formData.ubicacion.trim() === '') {
    errors.ubicacion = 'La ubicación es requerida';
  } else if (formData.ubicacion.length > 20) {
    errors.ubicacion = 'La ubicación no puede tener más de 20 caracteres';
  }

  // Altura (requerida)
  if (!formData.altura) {
    errors.altura = 'La altura es requerida';
  } else {
    const alturaNum = parseInt(formData.altura.replace('Nivel ', ''));
    if (isNaN(alturaNum) || alturaNum < 1 || alturaNum > 10) {
      errors.altura = 'La altura debe estar entre 1 y 10';
    }
  }

  // Stock mínimo
  if (formData.stock_min !== undefined && formData.stock_min < 0) {
    errors.stock_min = 'El stock mínimo no puede ser negativo';
  }

  // Stock actual
  if (formData.stock_actual !== undefined && formData.stock_actual < 0) {
    errors.stock_actual = 'El stock actual no puede ser negativo';
  }

  // Prioridad
  if (formData.prioridad !== undefined) {
    if (formData.prioridad < 1 || formData.prioridad > 5) {
      errors.prioridad = 'La prioridad debe estar entre 1 y 5';
    }
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors
  };
};
```

---

## 📱 Catálogos Opcionales

### Obtener Valores Únicos de la BD

Si decides implementar catálogos dinámicos, puedes agregar estos endpoints:

#### 1. Catálogo de Pasillos

**Endpoint:** `GET /api/v1/catalogs/pasillos`

```json
{
  "pasillos": ["A", "B", "B3", "C", "D", "E"]
}
```

#### 2. Catálogo de Alturas

**Endpoint:** `GET /api/v1/catalogs/alturas`

```json
{
  "alturas": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
}
```

#### 3. Implementación Temporal (Sin Backend)

Mientras tanto, puedes usar arrays estáticos:

```javascript
const PASILLOS_OPTIONS = ['A', 'B', 'B3', 'C', 'D', 'E', 'F', 'G', 'H'];
const LADOS_OPTIONS = ['Izquierdo', 'Derecho'];
const ALTURAS_OPTIONS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
const PRIORIDADES_OPTIONS = [
  { value: 1, label: 'Alta' },
  { value: 2, label: 'Media-Alta' },
  { value: 3, label: 'Media' },
  { value: 4, label: 'Media-Baja' },
  { value: 5, label: 'Baja' }
];
```

---

## ✅ Checklist de Implementación

### Backend

- [x] Endpoint POST `/products/{id}/locations` (Crear ubicación) ✅
- [ ] Endpoint PUT `/products/{product_id}/locations/{location_id}` (Actualizar)
- [ ] Endpoint DELETE `/products/{product_id}/locations/{location_id}` (Eliminar)
- [ ] Agregar campo `stock_max` a modelo ProductLocation
- [ ] Validaciones de negocio en endpoints
- [ ] Tests unitarios para nuevos endpoints
- [ ] Documentar en Swagger

### Frontend (A Implementar)

- [ ] Servicio `locationService.js`
- [ ] Hook `useLocations`
- [ ] Formulario de creación de ubicación
- [ ] Formulario de edición de ubicación
- [ ] Modal de confirmación para eliminar
- [ ] Convertir inputs a selectores reales
- [ ] Implementar validaciones de formulario
- [ ] Manejo de estados de loading
- [ ] Manejo de errores con mensajes claros
- [ ] Actualización automática de la lista después de operaciones

---

## 🚀 Próximos Pasos

### Fase 1: Backend (Prioridad Alta)

1. Implementar endpoint POST para crear ubicaciones
2. Implementar endpoint PUT para actualizar ubicaciones
3. Implementar endpoint DELETE para eliminar ubicaciones
4. Agregar tests para validar funcionamiento

### Fase 2: Frontend (Prioridad Alta)

1. Crear servicio de ubicaciones
2. Implementar hook personalizado
3. Conectar formulario de creación
4. Conectar formulario de edición
5. Implementar eliminación con confirmación

### Fase 3: Mejoras (Prioridad Media)

1. Agregar campo `stock_max` al modelo
2. Implementar catálogos dinámicos
3. Agregar búsqueda/filtrado de ubicaciones
4. Implementar ordenamiento personalizado
5. Agregar validaciones avanzadas

### Fase 4: Optimización (Prioridad Baja)

1. Cache de catálogos
2. Optimistic UI updates
3. Undo/Redo de operaciones
4. Exportar ubicaciones a Excel
5. Historial de cambios de ubicaciones

---

## 📚 Recursos Adicionales

- [PRODUCTS_API.md](./PRODUCTS_API.md) - Documentación completa de API
- [PRODUCTS_SYSTEM.md](./PRODUCTS_SYSTEM.md) - Documentación de modelos ORM
- [Swagger UI](http://localhost:8000/docs) - Documentación interactiva

---

**Última actualización:** 2026-01-06  
**Versión:** 1.0.0  
**Estado:** Endpoints de lectura implementados, CRUD pendiente
