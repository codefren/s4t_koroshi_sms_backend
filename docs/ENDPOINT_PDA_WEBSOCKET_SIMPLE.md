# 📡 WebSocket para PDA - Versión Simplificada

**Fecha:** 2026-01-12 (Actualizado)  
**Versión:** 2.0 - Con Sistema de Cajas de Embalaje

---

## 🎯 Resumen Ultra-Rápido

**WebSocket se usa ÚNICAMENTE para:** Escanear códigos EAN  
**Todo lo demás:** HTTP REST  
**Autenticación:** Solo codigo_operario (sin tokens)  
**Nuevo:** Sistema de cajas de embalaje automático integrado

---

## 🏗️ Arquitectura

### REST API (Control de flujo y cajas)
```
# Workflow Principal
POST  /api/v1/orders/{id}/start-picking     ← Iniciar picking + Crea Caja #1 automáticamente
POST  /api/v1/orders/{id}/complete-picking  ← Completar picking + Cierra caja activa

# Gestión de Cajas (Durante el picking)
POST  /api/v1/packing-boxes/orders/{id}/boxes        ← Abrir nueva caja
PUT   /api/v1/packing-boxes/{box_id}/close           ← Cerrar caja llena
GET   /api/v1/packing-boxes/orders/{id}/boxes        ← Listar cajas de la orden

# Empaque de Items (Automático al escanear)
PUT   /api/v1/packing-boxes/order-lines/{id}/pack    ← Empacar item en caja activa

# Consultas
GET   /api/v1/operators/{codigo}/orders              ← Listar órdenes asignadas
GET   /api/v1/operators/{codigo}/orders/{id}/lines   ← Listar productos de orden
```

### WebSocket (SOLO escaneo)
```
WS /ws/operators/{codigo_operario}

Único flujo:
  1. Operario escanea EAN → Envía SCAN_PRODUCT
  2. Server incrementa cantidad +1 → Responde SCAN_CONFIRMED
  3. Repetir hasta completar
```

---

## 🔄 Flujo Completo de Trabajo (Con Cajas de Embalaje)

```
1. GET /operators/OP001/orders
   → [ORD1001, ORD1002]

2. POST /api/v1/orders/123/start-picking
   → Estado: IN_PICKING ✓
   → Caja #1 creada automáticamente (ORD-123-BOX-001) ✓
   → Caja activa: Caja #1

3. GET /operators/OP001/orders/123/lines
   → 15 productos para recoger

4. WS Connect ws://localhost:8000/ws/operators/OP001
   → Conectado ✓

5. LOOP: Para cada producto (escanear hasta completar):
   
   Operario escanea → PDA envía:
   {
     "action": "scan_product",
     "data": {
       "order_id": 123,
       "ean": "8445962763983",
       "ubicacion": "A-IZQ-12-H2"
     }
   }
   
   Server responde:
   {
     "action": "scan_confirmed",
     "data": {
       "producto": "Camisa Polo M Rojo",
       "cantidad_actual": 3,      ← Incrementado +1
       "cantidad_solicitada": 5,
       "cantidad_pendiente": 2,
       "progreso_linea": 60.0,
       "progreso_orden": {
         "total_items": 15,
         "items_completados": 8,
         "progreso_porcentaje": 53.33
       }
     }
   }
   
   ✅ Item automáticamente empacado en Caja #1

6. [OPCIONAL] Si la Caja #1 se llena:
   
   PUT /api/v1/packing-boxes/{box_id}/close
   Body: {"peso_kg": 5.5, "dimensiones": "40x30x20"}
   → Caja #1 cerrada ✓
   
   POST /api/v1/packing-boxes/orders/123/boxes
   → Caja #2 abierta (ORD-123-BOX-002) ✓
   → Caja activa: Caja #2
   
   Continuar escaneando → Items se empaquetan en Caja #2

7. POST /api/v1/orders/123/complete-picking
   → Estado: PICKED ✓
   → Caja activa cerrada automáticamente ✓
   → Total cajas: 2 ✓
```

---

## 📡 Conexión WebSocket

### Conectar (Sin Token)
```javascript
const operadorCodigo = 'OP001';  // Código del operario
const ws = new WebSocket(`ws://localhost:8000/ws/operators/${operadorCodigo}`);

ws.onopen = () => {
  console.log('Conectado ✓');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Respuesta:', message);
};
```

**Validación server:** Solo verifica que `codigo_operario` existe y está activo.

---

## 📤 Mensaje del Cliente: SCAN_PRODUCT

### Enviar escaneo
```javascript
function escanearProducto(orderId, ean, ubicacion) {
  ws.send(JSON.stringify({
    action: 'scan_product',
    data: {
      order_id: orderId,
      ean: ean,
      ubicacion: ubicacion  // Opcional
    }
  }));
}

// Ejemplo de uso
escanearProducto(123, '8445962763983', 'A-IZQ-12-H2');
```

### Estructura del mensaje
```json
{
  "action": "scan_product",
  "data": {
    "order_id": 123,
    "ean": "8445962763983",
    "ubicacion": "A-IZQ-12-H2"
  }
}
```

**Parámetros:**
- `order_id` (int, requerido*): ID numérico de la orden activa
- `numero_orden` (string, requerido*): Número de orden (ej: "ORD1000") - alternativa a `order_id`
- `ean` (string, requerido): Código EAN escaneado
- `ubicacion` (string, opcional): Ubicación desde donde se escanea

**Nota:** Debes enviar `order_id` O `numero_orden` (no ambos). Se recomienda usar `order_id`.

**Efectos automáticos:**
1. Incrementa `cantidad_servida` en +1 para ese EAN
2. 🎁 **NUEVO:** Empaca automáticamente el item en la caja activa
3. Actualiza `total_items` de la caja
4. Registra `fecha_empacado` del item

---

## 📥 Respuestas del Server

### 1. SCAN_CONFIRMED ✅ (Éxito)

```json
{
  "action": "scan_confirmed",
  "data": {
    "line_id": 456,
    "producto": "Camisa Polo M Rojo",
    "ean": "8445962763983",
    "ubicacion": "A-IZQ-12-H2",
    
    "cantidad_actual": 3,
    "cantidad_solicitada": 5,
    "cantidad_pendiente": 2,
    
    "progreso_linea": 60.0,
    "estado_linea": "PARTIAL",
    
    "progreso_orden": {
      "total_items": 15,
      "items_completados": 8,
      "progreso_porcentaje": 53.33
    },
    
    "mensaje": "✅ Producto escaneado correctamente"
  }
}
```

**Estados de línea:**
- `PENDING`: No se ha recogido nada
- `PARTIAL`: Recogido parcialmente (cantidad_actual < solicitada)
- `COMPLETED`: Completado (cantidad_actual == solicitada)

---

### 2. SCAN_ERROR ❌ (Error)

```json
{
  "action": "scan_error",
  "data": {
    "error_code": "EAN_NOT_IN_ORDER",
    "message": "El EAN escaneado no pertenece a esta orden",
    "ean_escaneado": "9999999999999",
    "order_id": 123,
    "can_retry": true
  }
}
```

**Códigos de error:**
| Código | Descripción |
|--------|-------------|
| `EAN_NOT_IN_ORDER` | EAN no existe en la orden |
| `MAX_QUANTITY_REACHED` | Ya se completó la cantidad solicitada |
| `ORDER_NOT_ASSIGNED` | Orden no asignada al operario |
| `ORDER_WRONG_STATUS` | Orden no está en IN_PICKING |
| `OPERATOR_NOT_FOUND` | Operario no existe |

---

## 🛠️ Implementación FastAPI (Simplificada)

### 1. WebSocket Manager
```python
# src/adapters/primary/websocket/manager.py

from typing import Dict
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # {operator_id: websocket}
        self.connections: Dict[int, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, operator_id: int):
        await websocket.accept()
        self.connections[operator_id] = websocket
    
    def disconnect(self, operator_id: int):
        if operator_id in self.connections:
            del self.connections[operator_id]
    
    async def send_message(self, operator_id: int, message: dict):
        if operator_id in self.connections:
            await self.connections[operator_id].send_json(message)

manager = ConnectionManager()
```

---

### 2. WebSocket Endpoint
```python
# src/adapters/primary/websocket/operator_websocket.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from .manager import manager
from ...secondary.database.config import get_db
from ...secondary.database.orm import Operator, Order, OrderLine

router = APIRouter()


@router.websocket("/ws/operators/{operator_id}")
async def operator_websocket(
    websocket: WebSocket,
    operator_id: int,
    db: Session = Depends(get_db)
):
    # 1. Validar operario
    operator = db.query(Operator).filter_by(id=operator_id).first()
    if not operator or not operator.activo:
        await websocket.close(code=4004, reason="Operario no encontrado")
        return
    
    # 2. Conectar
    await manager.connect(websocket, operator_id)
    
    try:
        while True:
            # 3. Recibir mensaje
            data = await websocket.receive_json()
            
            if data.get('action') == 'scan_product':
                await handle_scan_product(
                    websocket, 
                    operator_id, 
                    data['data'], 
                    db
                )
    
    except WebSocketDisconnect:
        manager.disconnect(operator_id)


async def handle_scan_product(
    websocket: WebSocket,
    operator_id: int,
    data: dict,
    db: Session
):
    """Procesar escaneo de producto."""
    try:
        order_id = data['order_id']
        ean = data['ean']
        ubicacion = data.get('ubicacion')
        
        # 1. Validar orden asignada al operario
        order = db.query(Order).filter_by(id=order_id).first()
        if not order:
            await send_error(websocket, "ORDER_NOT_FOUND", "Orden no encontrada")
            return
        
        if order.operator_id != operator_id:
            await send_error(websocket, "ORDER_NOT_ASSIGNED", 
                           "Orden no asignada a este operario")
            return
        
        if order.status.codigo != "IN_PICKING":
            await send_error(websocket, "ORDER_WRONG_STATUS",
                           f"Orden en estado {order.status.codigo}")
            return
        
        # 2. Buscar producto por EAN
        line = db.query(OrderLine).filter(
            OrderLine.order_id == order_id,
            OrderLine.ean == ean
        ).first()
        
        if not line:
            await send_error(websocket, "EAN_NOT_IN_ORDER",
                           "EAN no pertenece a esta orden")
            return
        
        # 3. Validar cantidad
        if line.cantidad_servida >= line.cantidad_solicitada:
            await send_error(websocket, "MAX_QUANTITY_REACHED",
                           "Ya se completó la cantidad solicitada")
            return
        
        # 4. Incrementar cantidad +1
        line.cantidad_servida += 1
        
        # 5. Actualizar estado de línea
        if line.cantidad_servida == line.cantidad_solicitada:
            line.estado = "COMPLETED"
        elif line.cantidad_servida > 0:
            line.estado = "PARTIAL"
        
        # 6. Actualizar contadores de orden
        items_completados = db.query(OrderLine).filter(
            OrderLine.order_id == order_id,
            OrderLine.estado == "COMPLETED"
        ).count()
        
        order.items_completados = items_completados
        
        db.commit()
        
        # 7. Calcular progreso
        progreso_linea = (line.cantidad_servida / line.cantidad_solicitada * 100
                         if line.cantidad_solicitada > 0 else 0)
        
        progreso_orden = (order.items_completados / order.total_items * 100
                         if order.total_items > 0 else 0)
        
        # 8. Enviar confirmación
        await manager.send_message(operator_id, {
            "action": "scan_confirmed",
            "data": {
                "line_id": line.id,
                "producto": line.product_reference.nombre_producto 
                           if line.product_reference else "Producto",
                "ean": ean,
                "ubicacion": ubicacion,
                "cantidad_actual": line.cantidad_servida,
                "cantidad_solicitada": line.cantidad_solicitada,
                "cantidad_pendiente": line.cantidad_solicitada - line.cantidad_servida,
                "progreso_linea": round(progreso_linea, 2),
                "estado_linea": line.estado,
                "progreso_orden": {
                    "total_items": order.total_items,
                    "items_completados": order.items_completados,
                    "progreso_porcentaje": round(progreso_orden, 2)
                },
                "mensaje": "✅ Producto escaneado correctamente"
            }
        })
    
    except Exception as e:
        print(f"Error en scan_product: {e}")
        await send_error(websocket, "INTERNAL_ERROR", str(e))
        db.rollback()


async def send_error(websocket: WebSocket, error_code: str, message: str):
    """Enviar error al cliente."""
    await websocket.send_json({
        "action": "scan_error",
        "data": {
            "error_code": error_code,
            "message": message,
            "can_retry": True
        }
    })
```

---

### 3. Registrar en Main
```python
# src/main.py

from fastapi import FastAPI
from .adapters.primary.websocket import operator_websocket

app = FastAPI()

# Incluir WebSocket router
app.include_router(operator_websocket.router, tags=["WebSocket"])
```

---

## 🖥️ Cliente JavaScript Completo

```javascript
// useOperatorWebSocket.js

class OperatorWebSocket {
  constructor(operadorCodigo) {
    this.operadorCodigo = operadorCodigo;  // Ej: "OP001", "OP002"
    this.ws = null;
    this.onScanConfirmed = null;
    this.onScanError = null;
    this.connect();
  }
  
  connect() {
    this.ws = new WebSocket(
      `ws://localhost:8000/ws/operators/${this.operadorCodigo}`
    );
    
    this.ws.onopen = () => {
      console.log('✅ WebSocket conectado');
    };
    
    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      if (message.action === 'scan_confirmed' && this.onScanConfirmed) {
        this.onScanConfirmed(message.data);
      }
      
      if (message.action === 'scan_error' && this.onScanError) {
        this.onScanError(message.data);
      }
    };
    
    this.ws.onerror = (error) => {
      console.error('❌ WebSocket error:', error);
    };
    
    this.ws.onclose = () => {
      console.log('🔴 WebSocket desconectado');
      // Reconectar después de 3 segundos
      setTimeout(() => this.connect(), 3000);
    };
  }
  
  scanProduct(orderId, ean, ubicacion = null) {
    if (this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        action: 'scan_product',
        data: {
          order_id: orderId,
          ean: ean,
          ubicacion: ubicacion
        }
      }));
    } else {
      console.error('WebSocket no está conectado');
    }
  }
  
  disconnect() {
    if (this.ws) {
      this.ws.close();
    }
  }
}

// Uso en React/Vue
const operatorWS = new OperatorWebSocket('OP001');  // Usar código del operario

operatorWS.onScanConfirmed = (data) => {
  console.log('✅ Escaneado:', data);
  // Actualizar UI con progreso
  updateProgress(data.progreso_orden.progreso_porcentaje);
  
  // Mostrar mensaje
  showToast(data.mensaje);
  
  // Reproducir sonido
  playBeep();
};

operatorWS.onScanError = (data) => {
  console.error('❌ Error:', data.message);
  showAlert(data.message);
  playErrorSound();
};

// Cuando escanea
function onBarcodeScanned(ean) {
  operatorWS.scanProduct(currentOrderId, ean, currentLocation);
}
```

---

## ✅ Resumen de Endpoints

### Workflow Principal
| Operación | Método | Endpoint |
|-----------|--------|----------|
| **Listar órdenes** | GET | `/api/v1/operators/{codigo}/orders` |
| **Ver productos** | GET | `/api/v1/operators/{codigo}/orders/{id}/lines` |
| **Iniciar picking** | POST | `/api/v1/orders/{id}/start-picking` 🎁 |
| **Escanear producto** | WS | `/ws/operators/{codigo}` ⚡ |
| **Completar picking** | POST | `/api/v1/orders/{id}/complete-picking` 🎁 |

🎁 = Crea/cierra cajas automáticamente

### Gestión de Cajas (Opcional)
| Operación | Método | Endpoint |
|-----------|--------|----------|
| **Abrir nueva caja** | POST | `/api/v1/packing-boxes/orders/{id}/boxes` |
| **Cerrar caja** | PUT | `/api/v1/packing-boxes/{box_id}/close` |
| **Listar cajas** | GET | `/api/v1/packing-boxes/orders/{id}/boxes` |
| **Ver caja + items** | GET | `/api/v1/packing-boxes/{box_id}` |
| **Empacar item** | PUT | `/api/v1/packing-boxes/order-lines/{line_id}/pack` |

---

## 📦 Sistema de Cajas de Embalaje (Nuevo en v2.0)

### ¿Qué es?
Sistema automático de gestión de cajas físicas durante el proceso de picking.

### ¿Cómo funciona?

1. **Al iniciar picking** → Se crea automáticamente **Caja #1** (estado: OPEN)
   - Código: `ORD-123-BOX-001` (escaneable)
   - Todos los items escaneados se empaquetan aquí

2. **Durante el picking** → Cada item escaneado:
   - Se empaca automáticamente en la caja activa
   - Se registra `fecha_empacado`
   - Se incrementa `total_items` de la caja

3. **Si la caja se llena** → El operario puede:
   - Cerrar Caja #1 (registrar peso y dimensiones)
   - Abrir Caja #2 automáticamente
   - Continuar escaneando items → van a Caja #2

4. **Al completar picking** → El sistema:
   - Cierra automáticamente la caja activa
   - Valida que todos los items estén empacados
   - Registra total de cajas utilizadas

### Ventajas
- 📦 **Trazabilidad:** Cada item sabe en qué caja está
- 📊 **Estadísticas:** Peso y dimensiones por caja
- 🔍 **Códigos escaneables:** Cada caja tiene código único
- ⚙️ **Automático:** El PDA no necesita gestionar cajas manualmente
- 📝 **Auditoría:** Historial completo de apertura/cierre

### Reglas
- ⚠️ Solo **1 caja OPEN** por orden a la vez
- ⚠️ Todos los items deben estar empacados antes de completar
- ✅ Puede haber **múltiples cajas** por orden (1, 2, 3... N)

### Endpoints Principales
```javascript
// Abrir nueva caja manualmente (si la actual se llenó)
POST /api/v1/packing-boxes/orders/123/boxes
Body: {"notas": "Caja para items grandes"}

// Cerrar caja actual
PUT /api/v1/packing-boxes/456/close
Body: {
  "peso_kg": 5.5,
  "dimensiones": "40x30x20 cm",
  "notas": "Caja completa"
}

// Ver todas las cajas de la orden
GET /api/v1/packing-boxes/orders/123/boxes

// Ver detalle de una caja + items dentro
GET /api/v1/packing-boxes/456
```

**Documentación completa:** Ver `PACKING_BOXES_SYSTEM.md`

---

## 🎯 Ventajas de esta arquitectura

- ✅ **Simple:** Solo 1 mensaje WebSocket (SCAN_PRODUCT)
- ✅ **Sin tokens:** Solo codigo_operario
- ✅ **Rápido:** Feedback < 50ms
- ✅ **REST para control:** Iniciar/completar sigue siendo HTTP
- ✅ **Fácil de probar:** WebSocket solo para escaneo
- ✅ **Incremental +1:** Cada escaneo = +1 automático
- ✅ **Cajas automáticas:** Sistema de empaque integrado

---

## 📝 Próximos Pasos

```bash
# 1. Crear estructura
mkdir -p src/adapters/primary/websocket
touch src/adapters/primary/websocket/__init__.py
touch src/adapters/primary/websocket/manager.py
touch src/adapters/primary/websocket/operator_websocket.py

# 2. Copiar código de este documento

# 3. Instalar dependencia (si no está)
pip install websockets

# 4. Probar
# Conectar: ws://localhost:8000/ws/operators/OP001
# Enviar: {"action": "scan_product", "data": {"order_id": 1, "ean": "123"}}
```

---

## 📝 Cambios en esta Versión

### v2.0 (2026-01-12)
- ✅ Sistema de cajas de embalaje integrado
- ✅ Empaque automático de items al escanear
- ✅ Workflow automatizado: start-picking crea Caja #1
- ✅ Workflow automatizado: complete-picking cierra caja activa
- ✅ Gestión de múltiples cajas por orden
- ✅ Códigos de caja escaneables (únicos)
- ✅ Trazabilidad completa item-caja
- ✅ 14 nuevos endpoints para gestión de cajas

### v1.1 (2026-01-08)
- ✅ Usa codigo_operario en lugar de ID numérico
- ✅ Validación de operario al conectar

---

**Versión Actual:** 2.0 - Con Sistema de Cajas de Embalaje  
**Fecha:** 2026-01-12  
**Estado:** ✅ Actualizado y listo para producción  
**Documentación relacionada:** `PACKING_BOXES_SYSTEM.md`
