"""
WebSocket para actualizaciones en tiempo real de órdenes.

Permite a los clientes frontend suscribirse a cambios en órdenes
sin necesidad de hacer polling constante.
"""

from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
import json


class OrdersConnectionManager:
    """
    Gestor de conexiones WebSocket para actualizaciones de órdenes.
    
    Los clientes se suscriben y reciben actualizaciones cuando:
    - Se crea una nueva orden
    - Cambia el estado de una orden
    - Se asigna un operario
    - Se completa el picking
    """
    
    def __init__(self):
        # Set de conexiones activas
        self.connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """Conecta un cliente al WebSocket de órdenes."""
        await websocket.accept()
        self.connections.add(websocket)
        print(f"✅ Cliente conectado a orders WebSocket (total: {len(self.connections)})")
    
    def disconnect(self, websocket: WebSocket):
        """Desconecta un cliente del WebSocket."""
        self.connections.discard(websocket)
        print(f"❌ Cliente desconectado de orders WebSocket (total: {len(self.connections)})")
    
    async def broadcast_order_update(self, event_type: str, order_data: dict):
        """
        Envía actualización de orden a todos los clientes conectados.
        
        Args:
            event_type: Tipo de evento (order_created, order_updated, status_changed, etc.)
            order_data: Datos de la orden
        """
        message = {
            "type": event_type,
            "data": order_data
        }
        
        disconnected = []
        for connection in self.connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error enviando actualización a cliente: {e}")
                disconnected.append(connection)
        
        # Limpiar conexiones caídas
        for connection in disconnected:
            self.disconnect(connection)


# Instancia global del manager
orders_manager = OrdersConnectionManager()
