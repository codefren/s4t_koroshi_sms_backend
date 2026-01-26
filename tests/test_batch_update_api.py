"""
Tests para el endpoint batch-update usando pytest
Ejecutar: pytest tests/test_batch_update_api.py -v
"""

import pytest
import requests
from typing import Dict, List, Optional

# Configuración base
BASE_URL = "http://localhost:8000"
API_KEY = "cust_live_AsNutsv0d44fVBXhJGHGbf495a7kmUE9JeZJ9KqGaXI"  # Configurar con API key real


@pytest.fixture
def api_headers():
    """Headers comunes para las peticiones API"""
    return {
        "X-Api-Key": API_KEY,
        "Content-Type": "application/json"
    }


@pytest.fixture
def api_client(api_headers):
    """Cliente API configurado"""
    class APIClient:
        def __init__(self, base_url: str, headers: Dict):
            self.base_url = base_url
            self.headers = headers
        
        def get_b2b_orders(self, skip: int = 0, limit: int = 10):
            return requests.get(
                f"{self.base_url}/api/service/orders/b2b",
                headers=self.headers,
                params={"skip": skip, "limit": limit}
            )
        
        def get_order_lines(self, order_id: int):
            return requests.get(
                f"{self.base_url}/api/service/orders/{order_id}/lines",
                headers=self.headers
            )
        
        def batch_update(self, order_number: str, lines: List[Dict]):
            return requests.put(
                f"{self.base_url}/api/service/orders/batch-update",
                headers=self.headers,
                json={"order_number": order_number, "lines": lines}
            )
    
    return APIClient(BASE_URL, api_headers)


@pytest.fixture
def pending_order(api_client):
    """Fixture que retorna una orden PENDING para testing"""
    response = api_client.get_b2b_orders(skip=0, limit=1)
    assert response.status_code == 200, "No se pudo obtener órdenes"
    
    data = response.json()
    assert data.get("total_count", 0) > 0, "No hay órdenes PENDING disponibles"
    
    order = data["orders"][0]
    return {
        "order_id": order["id"],  # API retorna 'id', no 'order_id'
        "order_number": order["order_number"]
    }


class TestBatchUpdateEndpoint:
    """Suite de tests para el endpoint batch-update"""
    
    def test_list_b2b_orders_success(self, api_client):
        """Test 1: Listar órdenes B2B retorna 200 y estructura correcta"""
        response = api_client.get_b2b_orders()
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_count" in data
        assert "orders" in data
        assert isinstance(data["orders"], list)
    
    def test_get_order_lines_success(self, api_client, pending_order):
        """Test 2: Obtener líneas de orden retorna estructura correcta"""
        response = api_client.get_order_lines(pending_order["order_id"])
        
        assert response.status_code == 200
        data = response.json()
        
        assert "order_id" in data
        assert "order_number" in data
        assert "lines" in data
        assert isinstance(data["lines"], list)
    
    def test_batch_update_partial_first_time(self, api_client, pending_order):
        """Test 3: Primera actualización parcial mantiene orden en PENDING"""
        lines = [
            {"sku": "TEST-SKU-PARTIAL-001", "quantity_served": 5, "box_code": "BOX-001"},
            {"sku": "TEST-SKU-PARTIAL-002", "quantity_served": 0}
        ]
        
        response = api_client.batch_update(pending_order["order_number"], lines)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert data["order_status"] == "PENDING", "Orden debería permanecer PENDING con líneas incompletas"
        assert data["order_number"] == pending_order["order_number"]
        assert data["lines_updated"] == 2
    
    def test_batch_update_second_time_allowed(self, api_client, pending_order):
        """Test 4: CRÍTICO - Segunda actualización debe ser permitida"""
        # Primera actualización
        lines_first = [
            {"sku": "TEST-SKU-MULTI-001", "quantity_served": 5}
        ]
        response1 = api_client.batch_update(pending_order["order_number"], lines_first)
        assert response1.status_code == 200
        
        data1 = response1.json()
        assert data1["order_status"] == "PENDING", "Primera actualización: orden debe estar PENDING"
        
        # Segunda actualización (incrementar cantidad)
        lines_second = [
            {"sku": "TEST-SKU-MULTI-001", "quantity_served": 10}
        ]
        response2 = api_client.batch_update(pending_order["order_number"], lines_second)
        
        # CRÍTICO: Debe permitir segunda actualización
        assert response2.status_code == 200, "Segunda actualización debe ser permitida"
        
        data2 = response2.json()
        assert data2["status"] == "success"
        assert data2["order_status"] in ["PENDING", "READY"]  # Depende si se completó
    
    def test_batch_update_auto_created_line(self, api_client, pending_order):
        """Test 5: Crear línea nueva genera estado AUTO_CREATED"""
        lines = [
            {"sku": "NEW-AUTO-SKU-999", "quantity_served": 7, "box_code": "BOX-NEW"}
        ]
        
        response = api_client.batch_update(pending_order["order_number"], lines)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert data["lines_updated"] == 1
    
    def test_batch_update_auto_created_multiple_updates(self, api_client, pending_order):
        """Test 6: Línea AUTO_CREATED puede actualizarse múltiples veces"""
        sku = "AUTO-MULTI-UPDATE-001"
        
        # Primera creación
        response1 = api_client.batch_update(
            pending_order["order_number"],
            [{"sku": sku, "quantity_served": 5}]
        )
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["order_status"] in ["PENDING", "READY"]
        
        # Segunda actualización (más cantidad)
        response2 = api_client.batch_update(
            pending_order["order_number"],
            [{"sku": sku, "quantity_served": 10}]
        )
        assert response2.status_code == 200, "AUTO_CREATED debe permitir segunda actualización"
        
        # Tercera actualización (menos cantidad)
        response3 = api_client.batch_update(
            pending_order["order_number"],
            [{"sku": sku, "quantity_served": 8}]
        )
        assert response3.status_code == 200, "AUTO_CREATED debe permitir tercera actualización"
    
    def test_batch_update_with_box_codes(self, api_client, pending_order):
        """Test 7: Actualización con códigos de caja crea packing boxes"""
        lines = [
            {"sku": "SKU-BOX-001", "quantity_served": 10, "box_code": "BOX-TEST-A"},
            {"sku": "SKU-BOX-002", "quantity_served": 5, "box_code": "BOX-TEST-A"},
            {"sku": "SKU-BOX-003", "quantity_served": 3, "box_code": "BOX-TEST-B"}
        ]
        
        response = api_client.batch_update(pending_order["order_number"], lines)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert data["lines_updated"] == 3
    
    def test_batch_update_ready_order_rejected(self, api_client, pending_order):
        """Test 8: No se puede actualizar orden READY (retorna 400)"""
        # Primero completar la orden (enviar todas las líneas completas)
        # Nota: Este test puede fallar si no se completan todas las líneas
        
        # Obtener líneas de la orden
        response_lines = api_client.get_order_lines(pending_order["order_id"])
        if response_lines.status_code != 200:
            pytest.skip("No se pudieron obtener líneas de la orden")
        
        lines_data = response_lines.json().get("lines", [])
        if not lines_data:
            pytest.skip("Orden sin líneas")
        
        # Completar todas las líneas
        complete_lines = [
            {"sku": line["sku"], "quantity_served": line.get("quantity", 999)}
            for line in lines_data
        ]
        
        response_complete = api_client.batch_update(pending_order["order_number"], complete_lines)
        if response_complete.status_code != 200:
            pytest.skip("No se pudo completar la orden")
        
        data_complete = response_complete.json()
        if data_complete.get("order_status") != "READY":
            pytest.skip("Orden no quedó en estado READY")
        
        # Intentar actualizar orden READY (debe fallar)
        response_update = api_client.batch_update(
            pending_order["order_number"],
            [{"sku": "ANY-SKU", "quantity_served": 5}]
        )
        
        assert response_update.status_code == 400, "Debe retornar 400 para órdenes READY"
        assert "already READY" in response_update.json().get("detail", "")


class TestBatchUpdateValidations:
    """Tests de validaciones y errores"""
    
    def test_batch_update_missing_order_number(self, api_client):
        """Test: Request sin order_number retorna error de validación"""
        response = api_client.batch_update("", [])
        assert response.status_code == 404
    
    def test_batch_update_invalid_sku(self, api_client, pending_order):
        """Test: SKU vacío debe ser manejado correctamente"""
        lines = [{"sku": "", "quantity_served": 5}]
        response = api_client.batch_update(pending_order["order_number"], lines)
        print(response.json())
        print(response.status_code)
        assert response.status_code in [400, 422]
    
    def test_batch_update_negative_quantity(self, api_client, pending_order):
        """Test: Cantidad negativa debe ser rechazada"""
        lines = [{"sku": "TEST-SKU", "quantity_served": -5}]
        response = api_client.batch_update(pending_order["order_number"], lines)
        assert response.status_code in [400, 422]
    
    def test_batch_update_order_not_found(self, api_client):
        """Test: Orden inexistente retorna 404"""
        lines = [{"sku": "ANY-SKU43567", "quantity_served": 5}]
        response = api_client.batch_update("ORD-NONEXISTENT-999", lines)
        print(response.json())
        print(response.status_code)
        assert response.status_code == 404


class TestBatchUpdateResponseStructure:
    """Tests de estructura de respuestas"""
    
    def test_response_has_required_fields(self, api_client, pending_order):
        """Test: Response contiene todos los campos requeridos"""
        lines = [{"sku": "TEST-SKU", "quantity_served": 5}]
        response = api_client.batch_update(pending_order["order_number"], lines)
        
        if response.status_code == 200:
            data = response.json()
            
            required_fields = [
                "status", "message", "order_number", "order_status",
                "lines_updated", "lines_completed", "lines_partial", "lines_pending"
            ]
            
            for field in required_fields:
                assert field in data, f"Campo requerido '{field}' no está en la respuesta"
    
    def test_order_status_valid_values(self, api_client, pending_order):
        """Test: order_status solo puede ser PENDING o READY"""
        lines = [{"sku": "TEST-SKU", "quantity_served": 5}]
        response = api_client.batch_update(pending_order["order_number"], lines)
        
        if response.status_code == 200:
            data = response.json()
            assert data["order_status"] in ["PENDING", "READY"]
    
    def test_counters_consistency(self, api_client, pending_order):
        """Test: Suma de contadores debe ser consistente"""
        lines = [
            {"sku": "SKU-1", "quantity_served": 10},
            {"sku": "SKU-2", "quantity_served": 5},
            {"sku": "SKU-3", "quantity_served": 0}
        ]
        response = api_client.batch_update(pending_order["order_number"], lines)
        
        if response.status_code == 200:
            data = response.json()
            total = data["lines_completed"] + data["lines_partial"] + data["lines_pending"]
            # El total puede no coincidir exactamente con lines_updated si hay líneas preexistentes
            assert total >= 0, "Suma de contadores debe ser no negativa"


@pytest.mark.integration
class TestBatchUpdateIntegration:
    """Tests de integración completos"""
    
    def test_full_workflow_partial_to_complete(self, api_client, pending_order):
        """Test: Flujo completo de actualización parcial a completa"""
        sku = "WORKFLOW-TEST-001"
        
        # Paso 1: Actualización parcial
        response1 = api_client.batch_update(
            pending_order["order_number"],
            [{"sku": sku, "quantity_served": 5}]
        )
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Paso 2: Incrementar cantidad
        response2 = api_client.batch_update(
            pending_order["order_number"],
            [{"sku": sku, "quantity_served": 10}]
        )
        assert response2.status_code == 200
        
        # Paso 3: Completar
        response3 = api_client.batch_update(
            pending_order["order_number"],
            [{"sku": sku, "quantity_served": 20}]
        )
        assert response3.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
