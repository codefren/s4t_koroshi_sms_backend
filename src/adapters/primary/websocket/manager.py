"""
WebSocket Connection Manager para operarios de PDA.

Gestiona las conexiones WebSocket persistentes de los operarios
para recibir escaneos de productos en tiempo real.
"""

from typing import Dict
from fastapi import WebSocket


class ConnectionManager:
    """
    Gestor de conexiones WebSocket para operarios.
    
    Mantiene un diccionario simple: {codigo_operario: websocket}
    Cada operario puede tener una conexión activa a la vez.
    """
    
    def __init__(self):
        # Conexiones activas: {codigo_operario: WebSocket}
        self.connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, codigo_operario: str):
        """
        Conecta un operario al WebSocket.
        
        Args:
            websocket: Instancia de WebSocket
            codigo_operario: Código del operario (ej: OP001)
        """
        await websocket.accept()
        self.connections[codigo_operario] = websocket
        print(f"✅ Operario {codigo_operario} conectado al WebSocket")
    
    def disconnect(self, codigo_operario: str):
        """
        Desconecta un operario del WebSocket.
        
        Args:
            codigo_operario: Código del operario a desconectar
        """
        if codigo_operario in self.connections:
            del self.connections[codigo_operario]
            print(f"❌ Operario {codigo_operario} desconectado del WebSocket")
    
    async def send_message(self, codigo_operario: str, message: dict):
        """
        Envía un mensaje JSON a un operario específico.
        
        Args:
            codigo_operario: Código del operario
            message: Diccionario con el mensaje a enviar
        """
        if codigo_operario in self.connections:
            try:
                await self.connections[codigo_operario].send_json(message)
            except Exception as e:
                print(f"Error enviando mensaje a operario {codigo_operario}: {e}")
                # Si falla, desconectar
                self.disconnect(codigo_operario)
    
    def is_connected(self, codigo_operario: str) -> bool:
        """
        Verifica si un operario está conectado.
        
        Args:
            codigo_operario: Código del operario
            
        Returns:
            True si está conectado, False en caso contrario
        """
        return codigo_operario in self.connections


# Instancia global del manager
manager = ConnectionManager()
