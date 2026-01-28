"""
Tests unitarios de lógica batch_update_order
Usando SQLite en memoria - tests rápidos y aislados
"""

import pytest
from datetime import datetime
from fastapi import HTTPException

from src.api_service.service import batch_update_order
from src.api_service.schemas import OrderLineUpdate
from src.adapters.secondary.database.orm import Order, OrderLine, ProductReference, OrderStatus


class TestBatchUpdateLogic:
    """Tests unitarios de la función batch_update_order"""
    
    def test_first_update_marks_fecha_fin_picking(self, test_db, pending_order, test_customer):
        """Test: Primera actualización marca fecha_fin_picking"""
        # Verificar que orden no tiene fecha_fin_picking
        assert pending_order.fecha_fin_picking is None
        
        # Realizar actualización
        lines_updates = [
            OrderLineUpdate(sku="FIRST-UPDATE-SKU", quantity_served=5)
        ]
        
        result = batch_update_order(
            order_number=pending_order.numero_orden,
            lines_updates=lines_updates,
            customer=test_customer,
            db=test_db
        )
        
        # Verificar que fecha_fin_picking fue marcada
        test_db.refresh(pending_order)
        assert pending_order.fecha_fin_picking is not None
        assert result.status == "success"
    
    def test_second_update_rejected_with_403(self, test_db, updated_order, test_customer):
        """Test: Segunda actualización es rechazada con 403 Forbidden"""
        # Orden ya tiene fecha_fin_picking marcada
        assert updated_order.fecha_fin_picking is not None
        
        # Intentar segunda actualización
        lines_updates = [
            OrderLineUpdate(sku="SECOND-UPDATE-SKU", quantity_served=3)
        ]
        
        # Debe lanzar HTTPException con código 403
        with pytest.raises(HTTPException) as exc_info:
            batch_update_order(
                order_number=updated_order.numero_orden,
                lines_updates=lines_updates,
                customer=test_customer,
                db=test_db
            )
        
        assert exc_info.value.status_code == 403
        assert "already been updated" in exc_info.value.detail
    
    def test_ready_order_rejected_with_400(self, test_db, ready_order, test_customer):
        """Test: Orden READY rechazada con 400 Bad Request"""
        # Orden está en estado READY
        ready_status = test_db.query(OrderStatus).filter_by(codigo="READY").first()
        assert ready_order.status_id == ready_status.id
        
        lines_updates = [
            OrderLineUpdate(sku="ANY-SKU-12345678", quantity_served=1)
        ]
        
        # Debe lanzar HTTPException con código 400
        with pytest.raises(HTTPException) as exc_info:
            batch_update_order(
                order_number=ready_order.numero_orden,
                lines_updates=lines_updates,
                customer=test_customer,
                db=test_db
            )
        
        assert exc_info.value.status_code == 400
        assert "already READY" in exc_info.value.detail
    
    def test_auto_create_product_reference(self, test_db, pending_order, test_customer):
        """Test: Crea ProductReference AUTO_CREATED si SKU no existe"""
        new_sku = "NEW-PRODUCT-SKU-001"
        
        # Verificar que SKU no existe
        existing = test_db.query(ProductReference).filter_by(sku=new_sku).first()
        assert existing is None
        
        # Actualizar con SKU nuevo
        lines_updates = [
            OrderLineUpdate(sku=new_sku, quantity_served=7)
        ]
        
        result = batch_update_order(
            order_number=pending_order.numero_orden,
            lines_updates=lines_updates,
            customer=test_customer,
            db=test_db
        )
        
        # Verificar que ProductReference fue creado
        created_product = test_db.query(ProductReference).filter_by(sku=new_sku).first()
        assert created_product is not None
        assert created_product.temporada == "AUTO_CREATED"
        assert created_product.nombre_producto == f"AUTO CREATED - {new_sku}"
        assert result.status == "success"
    
    def test_auto_create_order_line_with_quantity(self, test_db, pending_order, test_customer):
        """Test: Crea OrderLine AUTO_CREATED cuando quantity_served > 0"""
        new_sku = "NEW-LINE-SKU-001"
        quantity = 10
        
        lines_updates = [
            OrderLineUpdate(sku=new_sku, quantity_served=quantity)
        ]
        
        result = batch_update_order(
            order_number=pending_order.numero_orden,
            lines_updates=lines_updates,
            customer=test_customer,
            db=test_db
        )
        
        # Verificar OrderLine creada
        created_line = test_db.query(OrderLine).filter(
            OrderLine.order_id == pending_order.id,
            OrderLine.ean == new_sku
        ).first()
        
        assert created_line is not None
        assert created_line.estado == "AUTO_CREATED"
        assert created_line.cantidad_solicitada == quantity
        assert created_line.cantidad_servida == quantity
        assert result.lines_completed == 1
    
    def test_auto_create_order_line_with_zero_quantity(self, test_db, pending_order, test_customer):
        """Test: Crea OrderLine PENDING cuando quantity_served = 0"""
        new_sku = "NEW-LINE-SKU-ZERO"
        
        lines_updates = [
            OrderLineUpdate(sku=new_sku, quantity_served=0)
        ]
        
        result = batch_update_order(
            order_number=pending_order.numero_orden,
            lines_updates=lines_updates,
            customer=test_customer,
            db=test_db
        )
        
        # Verificar OrderLine creada con estado PENDING
        created_line = test_db.query(OrderLine).filter(
            OrderLine.order_id == pending_order.id,
            OrderLine.ean == new_sku
        ).first()
        
        assert created_line is not None
        assert created_line.estado == "PENDING"
        assert created_line.cantidad_solicitada == 1
        assert created_line.cantidad_servida == 0
        assert result.lines_pending == 1
    
    def test_order_status_remains_pending_with_incomplete_lines(self, test_db, pending_order, test_customer, sample_product):
        """Test: Orden permanece PENDING si hay líneas incompletas"""
        # Agregar producto existente a la orden
        line = OrderLine(
            order_id=pending_order.id,
            product_reference_id=sample_product.id,
            ean=sample_product.sku,
            cantidad_solicitada=20,
            cantidad_servida=0,
            estado="PENDING"
        )
        test_db.add(line)
        test_db.commit()
        
        # Actualizar parcialmente
        lines_updates = [
            OrderLineUpdate(sku=sample_product.sku, quantity_served=10)
        ]
        
        result = batch_update_order(
            order_number=pending_order.numero_orden,
            lines_updates=lines_updates,
            customer=test_customer,
            db=test_db
        )
        
        # Orden debe permanecer PENDING
        assert result.order_status == "PENDING"
        assert result.lines_partial == 1
    
    def test_order_status_ready_when_all_lines_complete(self, test_db, pending_order, test_customer, sample_product):
        """Test: Orden cambia a READY cuando todas las líneas están completas"""
        # Limpiar líneas existentes
        test_db.query(OrderLine).filter(OrderLine.order_id == pending_order.id).delete()
        
        # Agregar una sola línea
        line = OrderLine(
            order_id=pending_order.id,
            product_reference_id=sample_product.id,
            ean=sample_product.sku,
            cantidad_solicitada=10,
            cantidad_servida=0,
            estado="PENDING"
        )
        test_db.add(line)
        test_db.commit()
        
        # Completar la línea
        lines_updates = [
            OrderLineUpdate(sku=sample_product.sku, quantity_served=10)
        ]
        
        result = batch_update_order(
            order_number=pending_order.numero_orden,
            lines_updates=lines_updates,
            customer=test_customer,
            db=test_db
        )
        
        # Orden debe cambiar a READY
        assert result.order_status == "READY"
        assert result.lines_completed == 1
        assert result.lines_pending == 0
        assert result.lines_partial == 0
    
    def test_order_not_found_raises_404(self, test_db, test_customer):
        """Test: Orden inexistente lanza 404"""
        lines_updates = [
            OrderLineUpdate(sku="ANY-SKU-12345678", quantity_served=5)
        ]
        
        with pytest.raises(HTTPException) as exc_info:
            batch_update_order(
                order_number="NONEXISTENT-ORDER",
                lines_updates=lines_updates,
                customer=test_customer,
                db=test_db
            )
        
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail
    
    def test_response_structure(self, test_db, pending_order, test_customer):
        """Test: Response contiene todos los campos requeridos"""
        lines_updates = [
            OrderLineUpdate(sku="RESPONSE-TEST-SKU", quantity_served=5)
        ]
        
        result = batch_update_order(
            order_number=pending_order.numero_orden,
            lines_updates=lines_updates,
            customer=test_customer,
            db=test_db
        )
        
        # Verificar campos requeridos
        assert hasattr(result, "status")
        assert hasattr(result, "message")
        assert hasattr(result, "order_number")
        assert hasattr(result, "order_status")
        assert hasattr(result, "lines_updated")
        assert hasattr(result, "lines_completed")
        assert hasattr(result, "lines_partial")
        assert hasattr(result, "lines_pending")
        
        assert result.status == "success"
        assert result.order_number == pending_order.numero_orden
        assert result.order_status in ["PENDING", "READY"]


class TestBatchUpdateValidations:
    """Tests de validaciones de entrada"""
    
    def test_sku_minimum_length_validation(self, test_db, pending_order, test_customer):
        """Test: SKU debe tener mínimo 8 caracteres (validado en schema)"""
        # Esta validación se hace en el schema Pydantic
        # Aquí verificamos que SKUs válidos (>=8 chars) funcionan
        lines_updates = [
            OrderLineUpdate(sku="VALID-SK", quantity_served=5)  # Exactamente 8
        ]
        
        result = batch_update_order(
            order_number=pending_order.numero_orden,
            lines_updates=lines_updates,
            customer=test_customer,
            db=test_db
        )
        
        assert result.status == "success"
    
    def test_negative_quantity_validation(self):
        """Test: Cantidad negativa rechazada en schema"""
        # Pydantic valida quantity_served >= 0
        with pytest.raises(Exception):  # ValidationError de Pydantic
            OrderLineUpdate(sku="TEST-SKU-12345678", quantity_served=-5)
    
    def test_multiple_lines_update(self, test_db, pending_order, test_customer):
        """Test: Actualización de múltiples líneas en un solo batch"""
        lines_updates = [
            OrderLineUpdate(sku="MULTI-SKU-001", quantity_served=10),
            OrderLineUpdate(sku="MULTI-SKU-002", quantity_served=5),
            OrderLineUpdate(sku="MULTI-SKU-003", quantity_served=0),
        ]
        
        result = batch_update_order(
            order_number=pending_order.numero_orden,
            lines_updates=lines_updates,
            customer=test_customer,
            db=test_db
        )
        
        assert result.lines_updated == 3
        assert result.lines_completed == 2  # SKU-001 y SKU-002
        assert result.lines_pending == 1    # SKU-003
    
    def test_cumulative_quantity_served_for_same_sku(self, test_db, pending_order, test_customer, sample_product):
        """
        Test: Cantidad servida debe acumularse cuando múltiples updates del mismo SKU 
        se envían en una sola llamada a batch_update_order.
        
        Restricción: Una orden solo tiene UN order_line por SKU.
        
        Escenario:
        - Orden con 1 línea: SKU "TEST-SKU", solicitado: 30, servido: 0
        - Batch update con 3 entradas del mismo SKU: [10, 5, 5]
        - Resultado esperado: cantidad_servida = 20 (10+5+5 acumulado), estado = PARTIAL
        """
        # Limpiar líneas existentes
        test_db.query(OrderLine).filter(OrderLine.order_id == pending_order.id).delete()
        
        # Crear UNA sola línea con cantidad solicitada = 30
        order_line = OrderLine(
            order_id=pending_order.id,
            product_reference_id=sample_product.id,
            ean=sample_product.sku,
            cantidad_solicitada=30,
            cantidad_servida=0,
            estado="PENDING"
        )
        test_db.add(order_line)
        test_db.commit()
        test_db.refresh(order_line)
        
        # Actualizar con MÚLTIPLES entradas del mismo SKU en una sola llamada
        lines_updates = [
            OrderLineUpdate(sku=sample_product.sku, quantity_served=10),
            OrderLineUpdate(sku=sample_product.sku, quantity_served=5),
            OrderLineUpdate(sku=sample_product.sku, quantity_served=5)
        ]
        
        result = batch_update_order(
            order_number=pending_order.numero_orden,
            lines_updates=lines_updates,
            customer=test_customer,
            db=test_db
        )
        
        # Refrescar línea desde DB
        test_db.refresh(order_line)
        
        # Verificar acumulación correcta: 10 + 5 + 5 = 20
        assert order_line.cantidad_servida == 20, \
            f"Línea debe tener 20 servido (10+5+5), tiene {order_line.cantidad_servida}"
        assert order_line.estado == "PARTIAL", \
            f"Línea debe estar PARTIAL (20/30), está {order_line.estado}"
        
        # Verificar contadores del resultado
        assert result.lines_updated == 3, "Debe reportar 3 líneas actualizadas"
        assert result.lines_partial == 1, "Debe haber 1 línea parcial"
        assert result.order_status == "PENDING", "Orden debe permanecer PENDING"
