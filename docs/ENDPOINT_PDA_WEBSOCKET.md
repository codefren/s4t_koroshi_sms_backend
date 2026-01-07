# 📡 Planificación: Sistema PDA con WebSocket (Simplificado)

**Fecha:** 2026-01-07  
**Arquitectura:** Híbrida REST + WebSocket  
**Objetivo:** WebSocket SOLO para escaneo de productos en tiempo real

---

## 🏗️ Arquitectura Híbrida Simplificada

### REST API (Todo excepto escaneo)
```
GET   /api/v1/operators/{id}/orders                      ← Listar órdenes
GET   /api/v1/operators/{id}/orders/{id}/lines           ← Listar productos
POST  /api/v1/operators/{id}/orders/{id}/start-picking   ← Iniciar picking
POST  /api/v1/operators/{id}/orders/{id}/complete-picking← Completar picking
```

### WebSocket (SOLO escaneo de EAN) ⚡
```
WS    /ws/operators/{operator_id}              ← Conexión persistente

Único mensaje:
  → SCAN_PRODUCT       (Operario escanea EAN + ubicación)
  ← SCAN_CONFIRMED     (Server confirma y actualiza)
  ← SCAN_ERROR         (Server notifica error)
```

**🎯 Simplificación:**
- ✅ WebSocket SOLO para escanear productos
- ✅ Sin autenticación por token (solo operator_id)
- ✅ Resto de operaciones por HTTP REST
- ✅ Más simple de implementar y mantener

---

## 🔄 Flujo de Trabajo con WebSocket

┌──────────┐                    ┌──────────┐                ┌──────────┐
│   PDA    │                    │  Server  │                │    DB    │
└────┬─────┘                    └────┬─────┘                └────┬─────┘
     │                               │                           │
     │ 1. GET /operators/1/orders    │                           │
     │───────────────────────────────>│                           │
     │<───────────────────────────────│                           │
     │ [ORD1001, ORD1002, ORD1003]   │                           │
     │                               │                           │
     │ 2. WS Connect /ws/operators/1 │                           │
     │<==============================>│                           │
     │     Conexión WebSocket ⚡      │                           │
     │                               │                           │
     │ 3. Operario escanea EAN       │                           │
     │                               │                           │
     │ 4. WS: SCAN_PRODUCT           │                           │
     │ {                             │                           │
     │   "action": "scan_product",   │                           │
     │   "order_id": 123,            │                           │
     │   "ean": "8445962763983",     │                           │
     │   "ubicacion": "A-IZQ-12-H2"  │                           │
     │ }                             │                           │
     │==============================>│                           │
     │                               │ Buscar producto por EAN   │
     │                               │───────────────────────────>│
     │                               │<───────────────────────────│
     │                               │ Incrementar cantidad +1   │
     │                               │───────────────────────────>│
     │                               │<───────────────────────────│
     │                               │                           │
     │ 5. WS: SCAN_CONFIRMED         │                           │
     │ {                             │                           │
     │   "status": "success",        │                           │
     │   "producto": "Camisa polo",  │                           │
     │   "cantidad_actual": 1,       │                           │
     │   "cantidad_solicitada": 5,   │                           │
     │   "progreso": 20.0            │                           │
     │ }                             │                           │
     │<==============================│                           │
     │                               │                           │
     │ ✅ UI actualiza en tiempo real│                           │
     │                               │                           │
     │ 6. Repite 4-5 hasta completar │                           │
     │    (escanea 5 veces el EAN)   │                           │
     │                               │                           │
     │ 7. POST /orders/123/complete  │                           │
     │───────────────────────────────>│ UPDATE status=PICKED      │
     │<───────────────────────────────│───────────────────────────>│
     │ ✅ Orden completada          │<───────────────────────────│

---

## 📡 WebSocket Endpoint

### Conexión Simple (Sin Token)
```
WS /ws/operators/{operator_id}
```

**Ejemplo:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/operators/1');
```

**Sin autenticación:** Solo se requiere el `operator_id` en la URL. El server valida que el operario exista y esté activo.

---

## 📨 Mensajes WebSocket (Simplificado)

### Único Mensaje: SCAN_PRODUCT

**Propósito:** Registrar escaneo de EAN en tiempo real.  
**Efecto:** Incrementa cantidad servida en +1 para ese producto.

---

## 📤 Mensaje del Cliente (PDA → Server)

### SCAN_PRODUCT (Escanear producto)

**Cuando:** El operario escanea un código de barras EAN  
**Efecto:** Incrementa cantidad servida en +1 automáticamente

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
- `order_id` (int, requerido): ID de la orden activa
- `ean` (string, requerido): Código EAN escaneado
- `ubicacion` (string, opcional): Ubicación desde donde se escanea

**Validaciones server:**
- ✅ Operario tiene la orden asignada
- ✅ EAN existe en la orden
- ✅ Cantidad actual < cantidad_solicitada
- ✅ Orden en estado IN_PICKING

**Nota:** Iniciar/completar picking ahora se hace por HTTP REST, no por WebSocket.

---

## 📥 Mensajes del Server (Server → PDA)

### 1. SCAN_CONFIRMED (Escaneo confirmado) ✅

**Cuando:** El server confirmó el escaneo y actualizó la cantidad

```json
{
  "action": "scan_confirmed",
  "data": {
    "line_id": 456,
    "producto": "Camisa Polo M Rojo",
    "ean": "8445962763983",
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

**Campos:**
- `cantidad_actual`: Cantidad servida hasta ahora (se incrementó en +1)
- `cantidad_pendiente`: Cuánto falta por recoger
- `estado_linea`: `PENDING`, `PARTIAL`, `COMPLETED`
- `progreso_linea`: Porcentaje de completitud del item (cantidad_actual / solicitada * 100)
- `progreso_orden`: Info del progreso total de la orden

---

### 2. SCAN_ERROR (Error en escaneo) ❌

**Cuando:** El escaneo falló por alguna validación

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
- `EAN_NOT_IN_ORDER` - EAN no existe en la orden
- `MAX_QUANTITY_REACHED` - Ya se alcanzó la cantidad solicitada
- `ORDER_NOT_ASSIGNED` - Orden no asignada al operario
- `ORDER_WRONG_STATUS` - Orden no está en estado IN_PICKING
- `PRODUCT_NOT_FOUND` - Producto con ese EAN no existe
- `OPERATOR_NOT_FOUND` - Operario no existe

---

## 🔐 Validaciones (Sin Token)

### Validación Simple al Conectar
```python
# Server valida solo que el operario existe y está activo
operator = db.query(Operator).filter_by(id=operator_id).first()

if not operator:
    await websocket.close(code=4004, reason="Operario no encontrado")

if not operator.activo:
    await websocket.close(code=4003, reason="Operario inactivo")

// 2. O autenticar después de conectar
ws.send(JSON.stringify({
  action: 'authenticate',
  data: {
    operator_code: 'OP001',
    token: 'eyJhbGc...'
  }
}));

// 3. Server valida y responde
{
  "action": "authenticated",
  "data": {
    "operator_id": 1,
    "operator_name": "Juan Pérez",
    "session_id": "abc123"
  }
}
```

### Validaciones por Mensaje
```python
@websocket_manager.on_message("pick_item")
async def handle_pick_item(websocket, data):
    # 1. Validar sesión activa
    session = await get_session(websocket)
    if not session:
        await send_error(websocket, "SESSION_EXPIRED")
        return
    
    # 2. Validar operario asignado a orden
    order = await db.get_order(data['order_id'])
    if order.operator_id != session.operator_id:
        await send_error(websocket, "ORDER_NOT_ASSIGNED")
        return
    
    # 3. Validar EAN
    line = await db.get_order_line(data['line_id'])
    if line.ean != data.get('ean_escaneado'):
        await send_error(websocket, "EAN_MISMATCH")
        return
    
    # 4. Procesar picking
    await process_picking(line, data)
```

---

## 🛠️ Implementación con FastAPI

### 1. Instalación
```bash
pip install fastapi[all] websockets
```

### 2. WebSocket Manager
```python
# src/adapters/primary/websocket/manager.py

from typing import Dict, Set
from fastapi import WebSocket

class ConnectionManager:
    """Gestiona conexiones WebSocket de operarios."""
    
    def __init__(self):
        # Conexiones activas: {operator_id: Set[WebSocket]}
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        
        # Sesiones: {websocket: operator_id}
        self.sessions: Dict[WebSocket, int] = {}
    
    async def connect(self, websocket: WebSocket, operator_id: int):
        """Conecta un operario."""
        await websocket.accept()
        
        if operator_id not in self.active_connections:
            self.active_connections[operator_id] = set()
        
        self.active_connections[operator_id].add(websocket)
        self.sessions[websocket] = operator_id
    
    def disconnect(self, websocket: WebSocket):
        """Desconecta un operario."""
        operator_id = self.sessions.get(websocket)
        
        if operator_id and operator_id in self.active_connections:
            self.active_connections[operator_id].discard(websocket)
            
            if not self.active_connections[operator_id]:
                del self.active_connections[operator_id]
        
        if websocket in self.sessions:
            del self.sessions[websocket]
    
    async def send_personal_message(
        self, 
        message: dict, 
        websocket: WebSocket
    ):
        """Envía mensaje a un operario específico."""
        await websocket.send_json(message)
    
    async def broadcast_to_operator(
        self, 
        message: dict, 
        operator_id: int
    ):
        """Envía mensaje a todas las sesiones de un operario."""
        if operator_id in self.active_connections:
            for connection in self.active_connections[operator_id]:
                await connection.send_json(message)
    
    async def broadcast_to_all(self, message: dict):
        """Envía mensaje a todos los operarios conectados."""
        for connections in self.active_connections.values():
            for connection in connections:
                await connection.send_json(message)

manager = ConnectionManager()
```

---

### 3. WebSocket Endpoint
```python
# src/adapters/primary/websocket/operator_websocket.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime
import json

from .manager import manager
from ...secondary.database.config import get_db
from ...secondary.database.orm import Operator, Order, OrderLine

router = APIRouter()


@router.websocket("/ws/operators/{operator_id}")
async def operator_websocket_endpoint(
    websocket: WebSocket,
    operator_id: int,
    token: str = Query(None),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint para operarios.
    
    Maneja actualizaciones en tiempo real de picking.
    """
    
    # Validar operario
    operator = db.query(Operator).filter_by(id=operator_id).first()
    if not operator:
        await websocket.close(code=4004, reason="Operario no encontrado")
        return
    
    if not operator.activo:
        await websocket.close(code=4003, reason="Operario inactivo")
        return
    
    # TODO: Validar token
    # if not validate_token(token, operator_id):
    #     await websocket.close(code=4001, reason="Token inválido")
    #     return
    
    # Conectar
    await manager.connect(websocket, operator_id)
    
    # Enviar confirmación
    await manager.send_personal_message({
        "action": "connected",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "operator_id": operator_id,
            "operator_name": operator.nombre,
            "message": "Conexión establecida"
        }
    }, websocket)
    
    try:
        while True:
            # Recibir mensaje
            data = await websocket.receive_text()
            message = json.loads(data)
            
            action = message.get("action")
            
            # Procesar según acción
            if action == "ping":
                await handle_ping(websocket, message)
            
            elif action == "pick_item":
                await handle_pick_item(websocket, operator_id, message, db)
            
            elif action == "start_picking":
                await handle_start_picking(websocket, operator_id, message, db)
            
            elif action == "complete_order":
                await handle_complete_order(websocket, operator_id, message, db)
            
            elif action == "skip_item":
                await handle_skip_item(websocket, operator_id, message, db)
            
            elif action == "partial_pick":
                await handle_partial_pick(websocket, operator_id, message, db)
            
            else:
                await send_error(websocket, "UNKNOWN_ACTION", 
                                f"Acción desconocida: {action}")
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"Operario {operator_id} desconectado")
    
    except Exception as e:
        print(f"Error en WebSocket: {e}")
        manager.disconnect(websocket)
        await websocket.close(code=1011, reason="Error interno")


# ============================================================================
# HANDLERS
# ============================================================================

async def handle_ping(websocket: WebSocket, message: dict):
    """Responder a ping."""
    await manager.send_personal_message({
        "action": "pong",
        "timestamp": datetime.utcnow().isoformat()
    }, websocket)


async def handle_pick_item(
    websocket: WebSocket,
    operator_id: int,
    message: dict,
    db: Session
):
    """Procesar picking de item."""
    
    try:
        data = message.get("data", {})
        line_id = data.get("line_id")
        cantidad_recogida = data.get("cantidad_recogida")
        ean_escaneado = data.get("ean_escaneado")
        
        # 1. Obtener línea
        line = db.query(OrderLine).filter_by(id=line_id).first()
        if not line:
            await send_error(websocket, "LINE_NOT_FOUND", 
                           "Línea de orden no encontrada")
            return
        
        # 2. Validar asignación
        order = line.order
        if order.operator_id != operator_id:
            await send_error(websocket, "ORDER_NOT_ASSIGNED",
                           "Orden no asignada a este operario")
            return
        
        # 3. Validar estado de orden
        if order.status.codigo not in ["ASSIGNED", "IN_PICKING"]:
            await send_error(websocket, "ORDER_WRONG_STATUS",
                           f"Orden en estado {order.status.codigo}")
            return
        
        # 4. Validar EAN
        if ean_escaneado and line.ean != ean_escaneado:
            await send_error(websocket, "EAN_MISMATCH",
                           "EAN escaneado no coincide",
                           extra={
                               "ean_esperado": line.ean,
                               "ean_recibido": ean_escaneado
                           })
            return
        
        # 5. Validar cantidad
        if cantidad_recogida > line.cantidad_solicitada:
            await send_error(websocket, "INVALID_QUANTITY",
                           "Cantidad excede lo solicitado")
            return
        
        # 6. Actualizar cantidad
        line.cantidad_servida = cantidad_recogida
        
        # Actualizar estado de la línea
        if cantidad_recogida == line.cantidad_solicitada:
            line.estado = "COMPLETED"
        elif cantidad_recogida > 0:
            line.estado = "PARTIAL"
        
        # 7. Actualizar contadores de orden
        items_completados = db.query(OrderLine).filter(
            OrderLine.order_id == order.id,
            OrderLine.estado == "COMPLETED"
        ).count()
        
        order.items_completados = items_completados
        
        db.commit()
        
        # 8. Obtener siguiente producto
        siguiente = db.query(OrderLine).filter(
            OrderLine.order_id == order.id,
            OrderLine.estado == "PENDING"
        ).first()
        
        siguiente_data = None
        if siguiente and siguiente.product_reference:
            siguiente_data = {
                "line_id": siguiente.id,
                "producto": siguiente.product_reference.nombre_producto,
                "ubicacion": siguiente.product_location.codigo_ubicacion 
                            if siguiente.product_location else "Sin ubicación",
                "cantidad": siguiente.cantidad_solicitada,
                "ean": siguiente.ean
            }
        
        # 9. Enviar confirmación
        progreso = (order.items_completados / order.total_items * 100
                   if order.total_items > 0 else 0)
        
        await manager.send_personal_message({
            "action": "pick_confirmed",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "line_id": line_id,
                "estado_nuevo": line.estado,
                "cantidad_servida": line.cantidad_servida,
                "cantidad_solicitada": line.cantidad_solicitada,
                "progreso_orden": {
                    "order_id": order.id,
                    "total_items": order.total_items,
                    "items_completados": order.items_completados,
                    "progreso_porcentaje": round(progreso, 2)
                },
                "siguiente_producto": siguiente_data
            }
        }, websocket)
        
        # 10. Broadcast a supervisores
        await manager.broadcast_to_all({
            "action": "order_updated",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "order_id": order.id,
                "estado": order.status.codigo,
                "progreso_porcentaje": round(progreso, 2),
                "items_completados": order.items_completados,
                "updated_by": operator_id
            }
        })
    
    except Exception as e:
        print(f"Error en pick_item: {e}")
        await send_error(websocket, "INTERNAL_ERROR", str(e))
        db.rollback()


async def handle_start_picking(
    websocket: WebSocket,
    operator_id: int,
    message: dict,
    db: Session
):
    """Iniciar picking de orden."""
    # Implementar similar a handle_pick_item
    pass


async def handle_complete_order(
    websocket: WebSocket,
    operator_id: int,
    message: dict,
    db: Session
):
    """Completar orden."""
    # Implementar similar a handle_pick_item
    pass


async def handle_skip_item(
    websocket: WebSocket,
    operator_id: int,
    message: dict,
    db: Session
):
    """Saltar item."""
    # Implementar
    pass


async def handle_partial_pick(
    websocket: WebSocket,
    operator_id: int,
    message: dict,
    db: Session
):
    """Recogida parcial."""
    # Implementar
    pass


async def send_error(
    websocket: WebSocket,
    error_code: str,
    message: str,
    extra: dict = None
):
    """Enviar mensaje de error."""
    error_data = {
        "error_code": error_code,
        "message": message
    }
    
    if extra:
        error_data.update(extra)
    
    await manager.send_personal_message({
        "action": "error",
        "timestamp": datetime.utcnow().isoformat(),
        "data": error_data
    }, websocket)
```

---

### 4. Registrar en Main
```python
# src/main.py

from fastapi import FastAPI
from .adapters.primary.websocket import operator_websocket

app = FastAPI()

# Incluir WebSocket router
app.include_router(
    operator_websocket.router,
    tags=["WebSocket"]
)
```

---

## 🖥️ Cliente PDA (JavaScript/React)

```javascript
// useOperatorWebSocket.js

import { useEffect, useRef, useState } from 'react';

export const useOperatorWebSocket = (operatorId, token) => {
  const ws = useRef(null);
  const [connected, setConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  
  useEffect(() => {
    // Conectar
    ws.current = new WebSocket(
      `ws://localhost:8000/ws/operators/${operatorId}?token=${token}`
    );
    
    ws.current.onopen = () => {
      console.log('WebSocket conectado');
      setConnected(true);
    };
    
    ws.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      console.log('Mensaje recibido:', message);
      setLastMessage(message);
      
      // Manejar mensaje según acción
      handleMessage(message);
    };
    
    ws.current.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    ws.current.onclose = () => {
      console.log('WebSocket desconectado');
      setConnected(false);
    };
    
    // Cleanup
    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [operatorId, token]);
  
  // Enviar mensaje
  const sendMessage = (action, data) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({
        action,
        timestamp: new Date().toISOString(),
        data
      }));
    }
  };
  
  // Handlers
  const pickItem = (lineId, cantidad, ean) => {
    sendMessage('pick_item', {
      line_id: lineId,
      cantidad_recogida: cantidad,
      ean_escaneado: ean
    });
  };
  
  const startPicking = (orderId) => {
    sendMessage('start_picking', { order_id: orderId });
  };
  
  const completeOrder = (orderId) => {
    sendMessage('complete_order', { order_id: orderId });
  };
  
  return {
    connected,
    lastMessage,
    pickItem,
    startPicking,
    completeOrder,
    sendMessage
  };
};

// Componente de ejemplo
const PickingScreen = ({ operatorId, orderId }) => {
  const { connected, lastMessage, pickItem } = useOperatorWebSocket(
    operatorId,
    'token123'
  );
  
  const handleScan = (lineId, ean) => {
    pickItem(lineId, 5, ean);
  };
  
  useEffect(() => {
    if (lastMessage?.action === 'pick_confirmed') {
      alert('✓ Producto recogido!');
      // Actualizar UI
    }
    
    if (lastMessage?.action === 'error') {
      alert(`❌ Error: ${lastMessage.data.message}`);
    }
  }, [lastMessage]);
  
  return (
    <div>
      <h1>Picking - Orden {orderId}</h1>
      {connected ? '🟢 Conectado' : '🔴 Desconectado'}
      {/* ... resto de UI ... */}
    </div>
  );
};
```

---

## ✅ Ventajas de WebSocket

| Característica | REST | WebSocket |
|----------------|------|-----------|
| **Latencia** | 100-500ms | <50ms |
| **Conexiones** | Por request | Persistente |
| **Overhead** | Headers cada vez | Mínimo |
| **Tiempo real** | Polling necesario | Nativo |
| **Feedback instantáneo** | ❌ | ✅ |
| **Broadcast** | Difícil | Fácil |
| **Uso de red** | Alto | Bajo |

---

## 📊 Comparación de Arquitecturas

### REST Puro
```
Operario recoge 15 productos = 15 requests PUT
Tiempo total: ~7.5 segundos (15 × 500ms)
```

### WebSocket
```
Operario recoge 15 productos = 15 mensajes WS
Tiempo total: ~0.75 segundos (15 × 50ms)
```

**Mejora: 10x más rápido** ⚡

---

## 🔄 Keep-Alive y Reconexión

```javascript
// Cliente con reconexión automática

class WebSocketClient {
  constructor(url, operatorId) {
    this.url = url;
    this.operatorId = operatorId;
    this.ws = null;
    this.reconnectInterval = 5000; // 5 segundos
    this.pingInterval = 30000; // 30 segundos
    
    this.connect();
    this.startPing();
  }
  
  connect() {
    this.ws = new WebSocket(this.url);
    
    this.ws.onopen = () => {
      console.log('Conectado');
      this.reconnectAttempts = 0;
    };
    
    this.ws.onclose = () => {
      console.log('Desconectado, reconectando...');
      setTimeout(() => this.connect(), this.reconnectInterval);
    };
    
    this.ws.onerror = (error) => {
      console.error('Error:', error);
    };
    
    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      this.handleMessage(message);
    };
  }
  
  startPing() {
    setInterval(() => {
      if (this.ws.readyState === WebSocket.OPEN) {
        this.send({ action: 'ping' });
      }
    }, this.pingInterval);
  }
  
  send(data) {
    if (this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }
}
```

---

## 📝 Resumen

### Arquitectura Final

**GET (REST):**
- Lista de órdenes
- Detalle de productos
- Consultas sin cambios

**WebSocket:**
- Actualización de cantidades ⭐
- Inicio/fin de picking
- Notificaciones en tiempo real
- Feedback instantáneo

### Ventajas Clave
- ✅ **10x más rápido** que REST
- ✅ **Tiempo real** nativo
- ✅ **Menos uso de red**
- ✅ **Mejor UX** (feedback instantáneo)
- ✅ **Broadcast** a supervisores
- ✅ **Reconexión** automática

---

**Archivos a crear:**
- `src/adapters/primary/websocket/manager.py`
- `src/adapters/primary/websocket/operator_websocket.py`
- `src/adapters/primary/websocket/__init__.py`

**Siguiente paso:** Implementar WebSocket Manager y endpoint básico
