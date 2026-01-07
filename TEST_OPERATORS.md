# 🧪 Guía de Pruebas - Endpoints de Operarios

Ejemplos prácticos para probar todos los endpoints CRUD de operarios.

## 🚀 Iniciar el Servidor

```bash
cd /home/efrenoscar/Project/s4t_koroshi_sms_backend/src
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## ✅ Endpoints Implementados

### 1. **GET** - Listar Todos los Operarios

```bash
curl http://localhost:8000/api/v1/operators/
```

**Respuesta esperada:**
```json
[
  {
    "id": 1,
    "codigo_operario": "OP001",
    "nombre": "Juan Pérez",
    "activo": true,
    "created_at": "2025-12-30T03:00:00",
    "updated_at": "2025-12-30T03:00:00"
  }
]
```

### 2. **GET** - Listar Solo Operarios Activos

```bash
curl "http://localhost:8000/api/v1/operators/?activo=true"
```

### 3. **GET** - Obtener Detalle de un Operario

```bash
curl http://localhost:8000/api/v1/operators/1
```

---

## 🆕 **POST** - Crear Operario

### Crear Operario Activo

```bash
curl -X POST http://localhost:8000/api/v1/operators/ \
  -H "Content-Type: application/json" \
  -d '{
    "codigo_operario": "OP005",
    "nombre": "Efrenoscar Arnaude",
    "activo": true
  }'
```

**Respuesta exitosa (201):**
```json
{
  "id": 5,
  "codigo_operario": "OP005",
  "nombre": "Efrenoscar Arnaude",
  "activo": true,
  "created_at": "2026-01-05T14:10:00.123456",
  "updated_at": "2026-01-05T14:10:00.123456"
}
```

### Crear Operario Inactivo (Vacaciones)

```bash
curl -X POST http://localhost:8000/api/v1/operators/ \
  -H "Content-Type: application/json" \
  -d '{
    "codigo_operario": "OP006",
    "nombre": "María González",
    "activo": false
  }'
```

### Intentar Crear Operario con Código Duplicado (Error 400)

```bash
curl -X POST http://localhost:8000/api/v1/operators/ \
  -H "Content-Type: application/json" \
  -d '{
    "codigo_operario": "OP005",
    "nombre": "Pedro Sánchez",
    "activo": true
  }'
```

**Respuesta de error:**
```json
{
  "detail": "Ya existe un operario con el código 'OP005'"
}
```

---

## 🔄 **PUT** - Actualizar Operario

### Actualizar Nombre

```bash
curl -X PUT http://localhost:8000/api/v1/operators/5 \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Efrenoscar Arnaude García"
  }'
```

### Actualizar Nombre y Estado

```bash
curl -X PUT http://localhost:8000/api/v1/operators/5 \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Efrenoscar Arnaude",
    "activo": false
  }'
```

### Actualizar Solo Estado

```bash
curl -X PUT http://localhost:8000/api/v1/operators/5 \
  -H "Content-Type: application/json" \
  -d '{
    "activo": true
  }'
```

---

## 🔀 **PATCH** - Activar/Desactivar Operario (Toggle)

### Toggle Status - Cambiar de Activo a Inactivo (o viceversa)

```bash
curl -X PATCH http://localhost:8000/api/v1/operators/5/toggle-status
```

**Respuesta:**
```json
{
  "id": 5,
  "codigo_operario": "OP005",
  "nombre": "Efrenoscar Arnaude",
  "activo": false,  // Cambió de true a false
  "created_at": "2026-01-05T14:10:00.123456",
  "updated_at": "2026-01-05T14:15:00.789012"  // Actualizado
}
```

### Toggle Nuevamente - Reactivar

```bash
# Ejecutar el mismo comando nuevamente
curl -X PATCH http://localhost:8000/api/v1/operators/5/toggle-status
```

**Ahora `activo` vuelve a `true`**

---

## 🎯 Flujo Completo de Prueba

### Paso 1: Crear Nuevo Operario

```bash
curl -X POST http://localhost:8000/api/v1/operators/ \
  -H "Content-Type: application/json" \
  -d '{
    "codigo_operario": "OP999",
    "nombre": "Test Operario",
    "activo": true
  }'
```

### Paso 2: Verificar que Aparece en la Lista

```bash
curl "http://localhost:8000/api/v1/operators/?activo=true" | jq '.[] | select(.codigo_operario=="OP999")'
```

### Paso 3: Actualizar Información

```bash
curl -X PUT http://localhost:8000/api/v1/operators/999 \
  -H "Content-Type: application/json" \
  -d '{
    "nombre": "Test Operario (Actualizado)"
  }'
```

### Paso 4: Desactivar Temporalmente

```bash
curl -X PATCH http://localhost:8000/api/v1/operators/999/toggle-status
```

### Paso 5: Verificar Estado Inactivo

```bash
curl "http://localhost:8000/api/v1/operators/?activo=false" | jq '.[] | select(.codigo_operario=="OP999")'
```

### Paso 6: Reactivar

```bash
curl -X PATCH http://localhost:8000/api/v1/operators/999/toggle-status
```

---

## 🧑‍💻 Uso desde JavaScript/Frontend

### Crear Operario

```javascript
async function createOperator(operatorData) {
  try {
    const response = await fetch('http://localhost:8000/api/v1/operators/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(operatorData)
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }

    const newOperator = await response.json();
    console.log('✅ Operario creado:', newOperator);
    return newOperator;

  } catch (error) {
    console.error('❌ Error al crear operario:', error.message);
    alert(`Error: ${error.message}`);
    return null;
  }
}

// Ejemplo de uso
const result = await createOperator({
  codigo_operario: 'OP005',
  nombre: 'Efrenoscar Arnaude',
  activo: true
});
```

### Actualizar Operario

```javascript
async function updateOperator(operatorId, updates) {
  const response = await fetch(`http://localhost:8000/api/v1/operators/${operatorId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(updates)
  });

  if (!response.ok) {
    throw new Error('Error al actualizar operario');
  }

  return await response.json();
}

// Ejemplo de uso
await updateOperator(5, {
  nombre: 'Efrenoscar Arnaude García',
  activo: true
});
```

### Toggle Status

```javascript
async function toggleOperatorStatus(operatorId) {
  const response = await fetch(
    `http://localhost:8000/api/v1/operators/${operatorId}/toggle-status`,
    { method: 'PATCH' }
  );

  if (!response.ok) {
    throw new Error('Error al cambiar estado del operario');
  }

  return await response.json();
}

// Ejemplo de uso
const updated = await toggleOperatorStatus(5);
console.log(`Operario ahora está: ${updated.activo ? 'Activo' : 'Inactivo'}`);
```

---

## 🔍 Verificar en Swagger UI

Abre tu navegador en: http://localhost:8000/docs

Podrás ver todos los endpoints con interfaz interactiva:
- **POST** `/api/v1/operators/` - Botón "Try it out"
- **PUT** `/api/v1/operators/{operator_id}` - Botón "Try it out"
- **PATCH** `/api/v1/operators/{operator_id}/toggle-status` - Botón "Try it out"

---

## 🎉 Casos de Prueba Recomendados

### ✅ Casos Exitosos

- [ ] Crear operario con código nuevo
- [ ] Listar operarios (todos)
- [ ] Listar solo operarios activos
- [ ] Listar solo operarios inactivos
- [ ] Obtener detalle de operario específico
- [ ] Actualizar nombre de operario
- [ ] Actualizar estado de operario
- [ ] Toggle status (activar/desactivar)

### ❌ Casos de Error

- [ ] Crear operario con código duplicado → Error 400
- [ ] Obtener operario inexistente → Error 404
- [ ] Actualizar operario inexistente → Error 404
- [ ] Toggle status de operario inexistente → Error 404
- [ ] Crear operario sin nombre → Error 422
- [ ] Crear operario sin codigo_operario → Error 422

---

## 📊 Códigos de Respuesta

| Código | Descripción | Cuándo |
|--------|-------------|--------|
| 200 | OK | GET, PUT, PATCH exitosos |
| 201 | Created | POST exitoso |
| 400 | Bad Request | Código duplicado |
| 404 | Not Found | Operario no existe |
| 422 | Validation Error | Campos requeridos faltantes |

---

## 💾 Tu Request Original (Ahora Funciona)

```bash
curl -X POST http://localhost:8000/api/v1/operators/ \
  -H "Content-Type: application/json" \
  -d '{
    "codigo_operario": "OP0005",
    "nombre": "Efrenoscar Arnaude",
    "activo": true
  }'
```

**Antes:** ❌ 405 Method Not Allowed  
**Ahora:** ✅ 201 Created

---

**Documentación actualizada:** 2026-01-05  
**Estado:** ✅ Todos los endpoints CRUD funcionando
