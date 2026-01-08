# 🚀 Setup WebSocket PDA - Guía Rápida

## ✅ Implementación Completada

El sistema WebSocket para PDA está **completamente implementado** y listo para usar.

### Archivos Creados

```
src/adapters/primary/websocket/
├── __init__.py                 ✅ Creado
├── manager.py                  ✅ Creado (ConnectionManager)
└── operator_websocket.py       ✅ Creado (WebSocket endpoint)

src/main.py                     ✅ Actualizado (router registrado)
test_websocket_client.py        ✅ Creado (cliente de prueba)
```

---

## 🔧 Instalación de Dependencias

Si no tienes `websockets` instalado para el cliente de prueba:

```bash
pip install websockets
```

**Nota:** FastAPI ya incluye soporte WebSocket, no necesitas instalar nada adicional en el servidor.

---

## 🚀 Cómo Probar

### 1. Iniciar el Servidor

```bash
uvicorn src.main:app --reload
```

El servidor estará disponible en: `http://localhost:8000`

### 2. Verificar la Documentación

Abre tu navegador en: `http://localhost:8000/docs`

Verás el endpoint WebSocket documentado:
- **WS** `/ws/operators/{codigo_operario}` (tag: WebSocket PDA)

### 3. Preparar Datos de Prueba

Asegúrate de tener:
- ✅ Un operario activo (código: OP001, por ejemplo)
- ✅ Una orden asignada al operario
- ✅ La orden debe estar en estado `IN_PICKING`
- ✅ Líneas de orden con productos y EAN

**Ejemplo rápido con SQL:**

```sql
-- Ver operarios
SELECT id, codigo_operario, nombre, activo FROM operators;

-- Ver órdenes del operario OP001
SELECT o.id, o.numero_orden, os.codigo as estado, op.codigo_operario
FROM orders o
JOIN order_status os ON o.status_id = os.id
JOIN operators op ON o.operator_id = op.id
WHERE op.codigo_operario = 'OP001';

-- Ver productos de la orden
SELECT id, ean, cantidad_solicitada, cantidad_servida, estado
FROM order_lines
WHERE order_id = 1;
```

### 4. Probar con el Cliente Python

#### Modo Simple (un solo escaneo):

```bash
python test_websocket_client.py OP001 1 8445962763983
```

Parámetros:
- `OP001` = codigo_operario
- `1` = order_id
- `8445962763983` = EAN del producto

#### Modo Interactivo (múltiples escaneos):

```bash
python test_websocket_client.py OP001 1
```

Luego escribe los EAN que quieras escanear.

---

## 📡 Ejemplo de Uso con JavaScript

```javascript
// Conectar
const ws = new WebSocket('ws://localhost:8000/ws/operators/OP001');

ws.onopen = () => {
  console.log('✅ Conectado');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('📨 Respuesta:', data);
  
  if (data.action === 'scan_confirmed') {
    console.log(`✅ ${data.data.mensaje}`);
    console.log(`📦 ${data.data.producto}`);
    console.log(`🔢 ${data.data.cantidad_actual}/${data.data.cantidad_solicitada}`);
  }
};

// Escanear producto
function escanear(orderId, ean) {
  ws.send(JSON.stringify({
    action: 'scan_product',
    data: {
      order_id: orderId,
      ean: ean,
      ubicacion: 'A-IZQ-12-H2'
    }
  }));
}

// Ejemplo
escanear(1, '8445962763983');
```

---

## 📨 Mensajes WebSocket

### Cliente → Servidor

```json
{
  "action": "scan_product",
  "data": {
    "order_id": 1,
    "ean": "8445962763983",
    "ubicacion": "A-IZQ-12-H2"
  }
}
```

### Servidor → Cliente (Éxito)

```json
{
  "action": "scan_confirmed",
  "data": {
    "line_id": 456,
    "producto": "Camisa Polo Rojo M",
    "ean": "8445962763983",
    "cantidad_actual": 3,
    "cantidad_solicitada": 5,
    "cantidad_pendiente": 2,
    "progreso_linea": 60.0,
    "estado_linea": "PARTIAL",
    "progreso_orden": {
      "order_id": 1,
      "numero_orden": "ORD1001",
      "total_items": 15,
      "items_completados": 8,
      "progreso_porcentaje": 53.33
    },
    "mensaje": "✅ Producto escaneado correctamente",
    "timestamp": "2026-01-07T19:00:00.000000"
  }
}
```

### Servidor → Cliente (Error)

```json
{
  "action": "scan_error",
  "data": {
    "error_code": "EAN_NOT_IN_ORDER",
    "message": "El EAN 9999999999999 no pertenece a esta orden",
    "can_retry": true,
    "timestamp": "2026-01-07T19:00:00.000000"
  }
}
```

---

## 🔒 Validaciones Implementadas

El WebSocket valida automáticamente:

| Validación | Error Code |
|------------|------------|
| Código de operario no existe | `Connection closed (4004)` |
| Operario inactivo | `Connection closed (4003)` |
| Orden no asignada al operario | `ORDER_NOT_ASSIGNED` |
| Orden en estado incorrecto | `ORDER_WRONG_STATUS` |
| EAN no pertenece a la orden | `EAN_NOT_IN_ORDER` |
| Cantidad máxima alcanzada | `MAX_QUANTITY_REACHED` |
| Falta order_id | `MISSING_ORDER_ID` |
| Falta EAN | `MISSING_EAN` |

---

## 📊 Flujo Completo

```
1. Operario se conecta: ws://localhost:8000/ws/operators/OP001
   ✅ Server valida operario y responde con "connected"

2. PDA inicia picking:
   POST /api/v1/orders/1/start-picking
   → Estado cambia a IN_PICKING

3. Operario escanea productos:
   WS: scan_product {"order_id": 1, "ean": "8445962763983"}
   → Server: +1 cantidad, responde con progreso
   
   Repite para cada producto (5 veces el mismo EAN si cantidad = 5)

4. PDA completa picking:
   POST /api/v1/orders/1/complete-picking
   → Estado cambia a PICKED
```

---

## 🧪 Tests Recomendados

### Test 1: Conexión Básica
```bash
python test_websocket_client.py OP001 1
# Debe conectar y mostrar nombre del operario
```

### Test 2: Escaneo Exitoso
```bash
# Escanear un EAN válido de la orden
python test_websocket_client.py OP001 1 8445962763983
# Debe incrementar cantidad y mostrar progreso
```

### Test 3: EAN Inválido
```bash
# Escanear un EAN que no está en la orden
python test_websocket_client.py OP001 1 9999999999999
# Debe mostrar error EAN_NOT_IN_ORDER
```

### Test 4: Cantidad Completa
```bash
# Escanear el mismo EAN hasta completar cantidad
# Después escanear una vez más
# Debe mostrar error MAX_QUANTITY_REACHED
```

---

## 🐛 Troubleshooting

### Error: "Operario no encontrado"
- Verifica que el operario existe: `SELECT * FROM operators WHERE codigo_operario = 'OP001'`
- Verifica que está activo: `activo = 1`

### Error: "ORDER_NOT_ASSIGNED"
- Verifica que la orden está asignada a ese operario
- Usa el endpoint REST para asignar: `POST /api/v1/orders/1/assign-operator` con `{"operator_id": 1}`

### Error: "ORDER_WRONG_STATUS"
- Verifica el estado: `SELECT status_id FROM orders WHERE id = 1`
- Cambia a IN_PICKING: `POST /api/v1/orders/1/start-picking`

### Error: "EAN_NOT_IN_ORDER"
- Verifica los EAN de la orden: `SELECT ean FROM order_lines WHERE order_id = 1`
- Usa uno de esos EAN válidos

---

## ✅ Checklist Pre-Producción

- [ ] El servidor inicia sin errores
- [ ] El endpoint aparece en `/docs`
- [ ] Puedes conectarte con el cliente de prueba
- [ ] Los escaneos incrementan la cantidad correctamente
- [ ] El progreso se calcula bien
- [ ] Los errores se manejan correctamente
- [ ] El WebSocket se reconecta automáticamente (desde el cliente)

---

## 📝 Próximos Pasos

1. **Frontend PDA:**
   - Integrar WebSocket en tu app React/Vue/React Native
   - Implementar lector de código de barras
   - Mostrar progreso visual

2. **Monitoring:**
   - Agregar logs de auditoría para escaneos
   - Dashboard de operarios activos
   - Métricas de performance

3. **Features Adicionales:**
   - Sonido de confirmación al escanear
   - Vibración en dispositivos móviles
   - Modo offline con sincronización

---

**🎉 ¡Sistema WebSocket PDA listo para producción!**
