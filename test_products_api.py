#!/usr/bin/env python3
"""
Script de prueba para la API de productos.

Prueba todos los endpoints disponibles y verifica las respuestas.
"""

import requests
import json
from typing import Dict, Any

# Configuración
BASE_URL = "http://localhost:8000/api/v1/products"
HEADERS = {"Accept": "application/json"}


def print_section(title: str):
    """Imprime un separador de sección."""
    print("\n" + "=" * 70)
    print(f"   {title}")
    print("=" * 70 + "\n")


def print_response(response: requests.Response):
    """Imprime la respuesta de manera formateada."""
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Response:\n{json.dumps(data, indent=2, ensure_ascii=False)}")
    else:
        print(f"Error: {response.text}")


def test_list_products():
    """Test 1: Listar todos los productos."""
    print_section("TEST 1: Listar Todos los Productos")
    
    response = requests.get(BASE_URL, headers=HEADERS)
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Total productos: {data['total']}")
        print(f"✅ Página actual: {data['page']}")
        print(f"✅ Productos en página: {len(data['products'])}")
    
    return response.status_code == 200


def test_filter_active():
    """Test 2: Filtrar productos activos."""
    print_section("TEST 2: Filtrar Productos Activos (stock >= 50)")
    
    response = requests.get(f"{BASE_URL}?status=active", headers=HEADERS)
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Productos activos: {len(data['products'])}")
    
    return response.status_code == 200


def test_filter_low_stock():
    """Test 3: Filtrar productos con stock bajo."""
    print_section("TEST 3: Filtrar Productos con Stock Bajo (1-49)")
    
    response = requests.get(f"{BASE_URL}?status=low", headers=HEADERS)
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Productos con stock bajo: {len(data['products'])}")
    
    return response.status_code == 200


def test_filter_out_of_stock():
    """Test 4: Filtrar productos sin stock."""
    print_section("TEST 4: Filtrar Productos Sin Stock")
    
    response = requests.get(f"{BASE_URL}?status=out", headers=HEADERS)
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Productos sin stock: {len(data['products'])}")
    
    return response.status_code == 200


def test_search():
    """Test 5: Buscar productos."""
    print_section("TEST 5: Buscar Productos (término: 'camisa')")
    
    response = requests.get(f"{BASE_URL}?search=camisa", headers=HEADERS)
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Resultados encontrados: {len(data['products'])}")
        if data['products']:
            print(f"✅ Primer resultado: {data['products'][0]['name']}")
    
    return response.status_code == 200


def test_pagination():
    """Test 6: Paginación."""
    print_section("TEST 6: Paginación (página 1, 5 por página)")
    
    response = requests.get(f"{BASE_URL}?page=1&per_page=5", headers=HEADERS)
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Total: {data['total']}")
        print(f"✅ Páginas totales: {data['total_pages']}")
        print(f"✅ Productos en página: {len(data['products'])}")
    
    return response.status_code == 200


def test_get_product_detail(product_id: int = 1):
    """Test 7: Obtener detalle de producto."""
    print_section(f"TEST 7: Detalle de Producto (ID: {product_id})")
    
    response = requests.get(f"{BASE_URL}/{product_id}", headers=HEADERS)
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Producto: {data['name']}")
        print(f"✅ SKU: {data['sku']}")
        print(f"✅ Stock total: {data['stock']}")
        print(f"✅ Ubicaciones: {len(data['locations'])}")
        print(f"✅ Estado: {data['status']}")
    elif response.status_code == 404:
        print(f"\n⚠️  Producto con ID {product_id} no encontrado")
        return True  # No es error si no existe
    
    return response.status_code in [200, 404]


def test_get_product_locations(product_id: int = 1):
    """Test 8: Obtener ubicaciones de producto."""
    print_section(f"TEST 8: Ubicaciones de Producto (ID: {product_id})")
    
    response = requests.get(f"{BASE_URL}/{product_id}/locations", headers=HEADERS)
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Producto: {data['product_name']}")
        print(f"✅ Total ubicaciones: {data['total_locations']}")
        print(f"✅ Stock total: {data['total_stock']}")
        print(f"✅ Estado: {data['status']}")
        
        if data['locations']:
            print("\n📍 Ubicaciones:")
            for loc in data['locations']:
                print(f"   • {loc['code']} - Stock: {loc['stock_actual']} "
                      f"(mín: {loc['stock_minimo']}, prioridad: {loc['prioridad']})")
    elif response.status_code == 404:
        print(f"\n⚠️  Producto con ID {product_id} no encontrado")
        return True
    
    return response.status_code in [200, 404]


def test_get_stock_summary(product_id: int = 1):
    """Test 9: Obtener resumen de stock."""
    print_section(f"TEST 9: Resumen de Stock (ID: {product_id})")
    
    response = requests.get(f"{BASE_URL}/{product_id}/stock-summary", headers=HEADERS)
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Producto: {data['product_name']}")
        print(f"✅ Stock total: {data['total_stock']}")
        print(f"✅ Ubicaciones: {data['total_locations']}")
        print(f"✅ Ubicaciones con stock bajo: {data['low_stock_locations']}")
        print(f"✅ Necesita reposición: {'Sí' if data['needs_restock'] else 'No'}")
    elif response.status_code == 404:
        print(f"\n⚠️  Producto con ID {product_id} no encontrado")
        return True
    
    return response.status_code in [200, 404]


def test_combined_filters():
    """Test 10: Filtros combinados."""
    print_section("TEST 10: Búsqueda + Filtro + Paginación")
    
    response = requests.get(
        f"{BASE_URL}?search=polo&status=active&page=1&per_page=5",
        headers=HEADERS
    )
    print_response(response)
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Resultados con filtros combinados: {len(data['products'])}")
    
    return response.status_code == 200


def test_invalid_product():
    """Test 11: Producto inexistente."""
    print_section("TEST 11: Producto Inexistente (ID: 99999)")
    
    response = requests.get(f"{BASE_URL}/99999", headers=HEADERS)
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 404:
        print(f"Response: {response.json()}")
        print("\n✅ Error 404 manejado correctamente")
        return True
    else:
        print(f"❌ Se esperaba 404, se obtuvo {response.status_code}")
        return False


def run_all_tests():
    """Ejecuta todos los tests."""
    print("=" * 70)
    print("   TESTS DE API DE PRODUCTOS")
    print("=" * 70)
    print(f"\nBase URL: {BASE_URL}")
    print(f"Asegúrate de que el servidor esté corriendo en http://localhost:8000")
    print("\nPresiona Enter para continuar...")
    input()
    
    tests = [
        ("Listar productos", test_list_products),
        ("Filtrar activos", test_filter_active),
        ("Filtrar stock bajo", test_filter_low_stock),
        ("Filtrar sin stock", test_filter_out_of_stock),
        ("Búsqueda de texto", test_search),
        ("Paginación", test_pagination),
        ("Detalle de producto", test_get_product_detail),
        ("Ubicaciones de producto", test_get_product_locations),
        ("Resumen de stock", test_get_stock_summary),
        ("Filtros combinados", test_combined_filters),
        ("Producto inexistente", test_invalid_product),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except requests.exceptions.ConnectionError:
            print(f"\n❌ Error de conexión. ¿Está el servidor corriendo?")
            results.append((name, False))
            break
        except Exception as e:
            print(f"\n❌ Error inesperado: {e}")
            results.append((name, False))
    
    # Resumen
    print_section("RESUMEN DE TESTS")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\n{'=' * 70}")
    print(f"Tests ejecutados: {total}")
    print(f"Tests exitosos: {passed}")
    print(f"Tests fallidos: {total - passed}")
    print(f"Porcentaje: {(passed/total*100):.1f}%")
    print(f"{'=' * 70}")
    
    if passed == total:
        print("\n🎉 ¡Todos los tests pasaron!")
    else:
        print(f"\n⚠️  {total - passed} test(s) fallaron")
    
    return passed == total


if __name__ == "__main__":
    try:
        success = run_all_tests()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrumpidos por el usuario")
        exit(1)
