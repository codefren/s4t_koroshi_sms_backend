"""
Cliente de prueba para el WebSocket de PDA.

Simula un dispositivo PDA escaneando productos.

Uso:
    python test_websocket_client.py <codigo_operario> <numero_orden> <ean>

Ejemplo:
    python test_websocket_client.py OP001 ORD1001 8445962763983
"""

import asyncio
import json
import sys
import websockets


async def test_scan_product(codigo_operario: str, numero_orden: str, ean: str):
    """
    Prueba el escaneo de un producto via WebSocket.
    
    Args:
        codigo_operario: Código del operario (ej: OP001)
        numero_orden: Número de orden (ej: ORD1001, 1111087088)
        ean: Código EAN del producto
    """
    uri = f"ws://localhost:8000/ws/operators/{codigo_operario}"
    
    print(f"🔌 Conectando al WebSocket: {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Conexión establecida\n")
            
            # Esperar mensaje de confirmación de conexión
            response = await websocket.recv()
            data = json.loads(response)
            print("📨 Respuesta del servidor:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print()
            
            # Enviar escaneo de producto
            scan_message = {
                "action": "scan_product",
                "data": {
                    "numero_orden": numero_orden,
                    "ean": ean,
                    "ubicacion": "A-IZQ-12-H2"
                }
            }
            
            print("📤 Enviando escaneo:")
            print(json.dumps(scan_message, indent=2, ensure_ascii=False))
            print()
            
            await websocket.send(json.dumps(scan_message))
            
            # Esperar respuesta
            response = await websocket.recv()
            data = json.loads(response)
            
            print("📨 Respuesta del servidor:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print()
            
            if data.get("action") == "scan_confirmed":
                print("✅ Escaneo exitoso!")
                progreso = data["data"]["progreso_orden"]
                print(f"   📊 Progreso: {progreso['items_completados']}/{progreso['total_items']} items ({progreso['progreso_porcentaje']}%)")
                print(f"   📦 Producto: {data['data']['producto']}")
                print(f"   🔢 Cantidad: {data['data']['cantidad_actual']}/{data['data']['cantidad_solicitada']}")
            elif data.get("action") == "scan_error":
                print("❌ Error en el escaneo:")
                print(f"   Código: {data['data']['error_code']}")
                print(f"   Mensaje: {data['data']['message']}")
    
    except websockets.exceptions.ConnectionClosed as e:
        print(f"❌ Conexión cerrada: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


async def interactive_mode(codigo_operario: str, numero_orden: str):
    """
    Modo interactivo para escanear múltiples productos.
    
    Args:
        codigo_operario: Código del operario (ej: OP001)
        numero_orden: Número de orden (ej: ORD1001, 1111087088)
    """
    uri = f"ws://localhost:8000/ws/operators/{codigo_operario}"
    
    print(f"🔌 Conectando al WebSocket: {uri}")
    print("📱 Modo interactivo - Escribe EAN y presiona Enter (o 'q' para salir)\n")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Conexión establecida\n")
            
            # Esperar mensaje de confirmación
            response = await websocket.recv()
            data = json.loads(response)
            print(f"👤 {data['data']['message']}\n")
            
            while True:
                # Leer EAN desde la consola
                ean = input("🔍 Escanea EAN (o 'q' para salir): ").strip()
                
                if ean.lower() == 'q':
                    print("👋 Saliendo...")
                    break
                
                if not ean:
                    continue
                
                # Enviar escaneo
                scan_message = {
                    "action": "scan_product",
                    "data": {
                        "numero_orden": numero_orden,
                        "ean": ean,
                        "ubicacion": "A-IZQ-12-H2"
                    }
                }
                
                await websocket.send(json.dumps(scan_message))
                
                # Esperar respuesta
                response = await websocket.recv()
                data = json.loads(response)
                
                if data.get("action") == "scan_confirmed":
                    info = data["data"]
                    print(f"   ✅ {info['mensaje']}")
                    print(f"   📦 {info['producto']}")
                    print(f"   🔢 {info['cantidad_actual']}/{info['cantidad_solicitada']}")
                    progreso = info['progreso_orden']
                    print(f"   📊 Orden: {progreso['items_completados']}/{progreso['total_items']} ({progreso['progreso_porcentaje']}%)")
                    print()
                elif data.get("action") == "scan_error":
                    print(f"   ❌ {data['data']['message']}")
                    print()
    
    except websockets.exceptions.ConnectionClosed:
        print("❌ Conexión cerrada por el servidor")
    except KeyboardInterrupt:
        print("\n👋 Desconectado por el usuario")
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """Función principal."""
    if len(sys.argv) < 2:
        print("Uso:")
        print("  Modo simple:      python test_websocket_client.py <codigo_operario> <numero_orden> <ean>")
        print("  Modo interactivo: python test_websocket_client.py <codigo_operario> <numero_orden>")
        print()
        print("Ejemplo:")
        print("  python test_websocket_client.py OP001 ORD1001 8445962763983")
        print("  python test_websocket_client.py OP001 1111087088")
        sys.exit(1)
    
    codigo_operario = sys.argv[1]
    
    if len(sys.argv) >= 3:
        numero_orden = sys.argv[2]
        
        if len(sys.argv) >= 4:
            # Modo simple: un solo escaneo
            ean = sys.argv[3]
            asyncio.run(test_scan_product(codigo_operario, numero_orden, ean))
        else:
            # Modo interactivo
            asyncio.run(interactive_mode(codigo_operario, numero_orden))
    else:
        print("❌ Falta el número de orden")
        sys.exit(1)


if __name__ == "__main__":
    main()
