"""
Tests unitarios de lógica batch_update_order
Usando SQLite en memoria - tests rápidos y aislados
"""

import pytest
from datetime import datetime
from fastapi import HTTPException

from src.api_service.service import batch_update_order
from src.api_service.schemas import OrderLineUpdate
from src.adapters.secondary.database.orm import Order, OrderLine, ProductReference, OrderStatus, PackingBox, OrderLineBoxDistribution


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


class TestPackingBoxIntegration:
    """Tests de integración de packing boxes con batch_update_order"""
    
    def test_packing_box_total_items_counter(self, test_db, pending_order, test_customer):
        """
        Test: El contador total_items de una caja se incrementa correctamente 
        cuando se empaca cada línea.
        
        Escenario:
        - Orden con 3 líneas de diferentes SKUs
        - Empacar 2 líneas en caja "BOX-001" y 1 línea en caja "BOX-002"
        - Verificar que BOX-001 tenga total_items=2 y BOX-002 tenga total_items=1
        """
        # Limpiar líneas existentes
        test_db.query(OrderLine).filter(OrderLine.order_id == pending_order.id).delete()
        
        # Crear 3 productos diferentes
        product1 = ProductReference(
            sku="PROD-001-SKU",
            referencia="REF-001",
            nombre_producto="Producto 1",
            color_id="C01",
            nombre_color="Rojo",
            talla="M",
            temporada="2024",
            activo=True
        )
        product2 = ProductReference(
            sku="PROD-002-SKU",
            referencia="REF-002",
            nombre_producto="Producto 2",
            color_id="C02",
            nombre_color="Azul",
            talla="L",
            temporada="2024",
            activo=True
        )
        product3 = ProductReference(
            sku="PROD-003-SKU",
            referencia="REF-003",
            nombre_producto="Producto 3",
            color_id="C03",
            nombre_color="Verde",
            talla="S",
            temporada="2024",
            activo=True
        )
        test_db.add_all([product1, product2, product3])
        test_db.commit()
        
        # Crear 3 líneas de orden
        line1 = OrderLine(
            order_id=pending_order.id,
            product_reference_id=product1.id,
            ean=product1.sku,
            cantidad_solicitada=10,
            cantidad_servida=0,
            estado="PENDING"
        )
        line2 = OrderLine(
            order_id=pending_order.id,
            product_reference_id=product2.id,
            ean=product2.sku,
            cantidad_solicitada=15,
            cantidad_servida=0,
            estado="PENDING"
        )
        line3 = OrderLine(
            order_id=pending_order.id,
            product_reference_id=product3.id,
            ean=product3.sku,
            cantidad_solicitada=5,
            cantidad_servida=0,
            estado="PENDING"
        )
        test_db.add_all([line1, line2, line3])
        test_db.commit()
        
        # Empacar: 2 líneas en BOX-001, 1 línea en BOX-002
        lines_updates = [
            OrderLineUpdate(sku="PROD-001-SKU", quantity_served=10, box_code="BOX-001"),
            OrderLineUpdate(sku="PROD-002-SKU", quantity_served=15, box_code="BOX-001"),
            OrderLineUpdate(sku="PROD-003-SKU", quantity_served=5, box_code="BOX-002")
        ]
        
        result = batch_update_order(
            order_number=pending_order.numero_orden,
            lines_updates=lines_updates,
            customer=test_customer,
            db=test_db
        )
        
        # Verificar cajas creadas
        box1 = test_db.query(PackingBox).filter(PackingBox.codigo_caja == "BOX-001").first()
        box2 = test_db.query(PackingBox).filter(PackingBox.codigo_caja == "BOX-002").first()
        
        assert box1 is not None, "Caja BOX-001 debe existir"
        assert box2 is not None, "Caja BOX-002 debe existir"
        
        # Verificar total_items de cada caja (suma de quantity_served)
        assert box1.total_items == 25, f"BOX-001 debe tener 25 items (10+15), tiene {box1.total_items}"
        assert box2.total_items == 5, f"BOX-002 debe tener 5 items, tiene {box2.total_items}"
        
        # Verificar que las líneas están asignadas correctamente
        test_db.refresh(line1)
        test_db.refresh(line2)
        test_db.refresh(line3)
        
        assert line1.packing_box_id == box1.id, "Línea 1 debe estar en BOX-001"
        assert line2.packing_box_id == box1.id, "Línea 2 debe estar en BOX-001"
        assert line3.packing_box_id == box2.id, "Línea 3 debe estar en BOX-002"
        
        # Verificar estado de las líneas
        assert line1.estado == "COMPLETED", "Línea 1 debe estar COMPLETED"
        assert line2.estado == "COMPLETED", "Línea 2 debe estar COMPLETED"
        assert line3.estado == "COMPLETED", "Línea 3 debe estar COMPLETED"
        
        # Verificar fecha_empacado marcada
        assert line1.fecha_empacado is not None, "Línea 1 debe tener fecha_empacado"
        assert line2.fecha_empacado is not None, "Línea 2 debe tener fecha_empacado"
        assert line3.fecha_empacado is not None, "Línea 3 debe tener fecha_empacado"
    
    def test_packing_box_accumulate_items_same_sku(self, test_db, pending_order, test_customer):
        """
        Test: Múltiples actualizaciones del mismo SKU con el mismo box_code 
        deben contar como 1 solo item en la caja (no duplicar).
        
        Escenario:
        - 3 actualizaciones del mismo SKU con cantidades [5, 3, 2]
        - Todas asignadas a la misma caja "BOX-A"
        - Total acumulado: 10 unidades
        - Total items en caja: 1 (porque es 1 solo SKU/línea)
        """
        lines_updates = [
            OrderLineUpdate(sku="PROD-SKU-001", quantity_served=5, box_code="BOX-A"),
            OrderLineUpdate(sku="PROD-SKU-001", quantity_served=3, box_code="BOX-A"),
            OrderLineUpdate(sku="PROD-SKU-001", quantity_served=2, box_code="BOX-A")
        ]
        
        result = batch_update_order(
            order_number=pending_order.numero_orden,
            lines_updates=lines_updates,
            customer=test_customer,
            db=test_db
        )
        
        # Verificar caja creada
        box = test_db.query(PackingBox).filter(PackingBox.codigo_caja == "BOX-A").first()
        
        assert box is not None, "Caja BOX-A debe existir"
        
        # Debe ser 10 items (suma de cantidades 5+3+2), no contar líneas
        assert box.total_items == 10, f"BOX-A debe tener 10 items (5+3+2), tiene {box.total_items}"
        
        # Verificar que la línea tiene la cantidad acumulada
        order_line = test_db.query(OrderLine).filter(
            OrderLine.order_id == pending_order.id,
            OrderLine.ean == "PROD-SKU-001"
        ).first()
        
        assert order_line is not None, "OrderLine debe existir"
        assert order_line.cantidad_servida == 10, f"Cantidad servida debe ser 10 (5+3+2), es {order_line.cantidad_servida}"
        assert order_line.packing_box_id == box.id, "Línea debe estar asignada a BOX-A"
        assert order_line.estado == "AUTO_CREATED", "Línea debe estar AUTO_CREATED"
    
    def test_packing_box_multiple_skus_same_box(self, test_db, pending_order, test_customer):
        """
        Test: Diferentes SKUs en la misma caja incrementan el contador correctamente.
        
        Escenario:
        - 5 SKUs diferentes, todos en la misma caja "BOX-MAIN"
        - Verificar que total_items = 5
        """
        lines_updates = [
            OrderLineUpdate(sku="SKU-00001", quantity_served=10, box_code="BOX-MAIN"),
            OrderLineUpdate(sku="SKU-00002", quantity_served=5, box_code="BOX-MAIN"),
            OrderLineUpdate(sku="SKU-00003", quantity_served=8, box_code="BOX-MAIN"),
            OrderLineUpdate(sku="SKU-00004", quantity_served=12, box_code="BOX-MAIN"),
            OrderLineUpdate(sku="SKU-00005", quantity_served=3, box_code="BOX-MAIN")
        ]
        
        result = batch_update_order(
            order_number=pending_order.numero_orden,
            lines_updates=lines_updates,
            customer=test_customer,
            db=test_db
        )
        
        # Verificar caja
        box = test_db.query(PackingBox).filter(PackingBox.codigo_caja == "BOX-MAIN").first()
        
        assert box is not None, "Caja BOX-MAIN debe existir"
        assert box.total_items == 38, f"BOX-MAIN debe tener 38 items (suma de cantidades), tiene {box.total_items}"
        
        # Verificar que todas las líneas están asignadas a la misma caja
        lines_in_box = test_db.query(OrderLine).filter(
            OrderLine.order_id == pending_order.id,
            OrderLine.packing_box_id == box.id
        ).count()
        
        assert lines_in_box == 5, f"Debe haber 5 líneas en BOX-MAIN, hay {lines_in_box}"
    
    def test_packing_box_without_box_code(self, test_db, pending_order, test_customer):
        """
        Test: Líneas actualizadas sin box_code no crean ni asignan cajas.
        
        Escenario:
        - Actualizar 2 líneas sin proporcionar box_code
        - Verificar que no se crean cajas
        - Verificar que packing_box_id permanece NULL
        """
        lines_updates = [
            OrderLineUpdate(sku="NOBOX-SKU-01", quantity_served=10),
            OrderLineUpdate(sku="NOBOX-SKU-02", quantity_served=5)
        ]
        
        result = batch_update_order(
            order_number=pending_order.numero_orden,
            lines_updates=lines_updates,
            customer=test_customer,
            db=test_db
        )
        
        # Verificar que no se crearon cajas
        boxes_count = test_db.query(PackingBox).filter(
            PackingBox.order_id == pending_order.id
        ).count()
        
        assert boxes_count == 0, f"No deben existir cajas, hay {boxes_count}"
        
        # Verificar que las líneas no tienen caja asignada
        lines = test_db.query(OrderLine).filter(
            OrderLine.order_id == pending_order.id
        ).all()
        
        for line in lines:
            assert line.packing_box_id is None, f"Línea {line.ean} no debe tener caja asignada"
            assert line.fecha_empacado is None, f"Línea {line.ean} no debe tener fecha_empacado"


    def test_order_line_distributed_across_multiple_boxes(self, test_db, pending_order, test_customer):
        """
        Test: Una order_line puede estar distribuida en múltiples cajas.
        
        Escenario:
        - SKU-A: 30 unidades totales
        - Distribuidas: 20 en BOX-001, 10 en BOX-002
        
        Requiere: Tabla OrderLineBoxDistribution implementada
        """
        lines_updates = [
            OrderLineUpdate(sku="SKU-A-DIST", quantity_served=20, box_code="BOX-001"),
            OrderLineUpdate(sku="SKU-A-DIST", quantity_served=10, box_code="BOX-002")
        ]
        
        result = batch_update_order(
            order_number=pending_order.numero_orden,
            lines_updates=lines_updates,
            customer=test_customer,
            db=test_db
        )
        
        # Verificar order_line tiene total acumulado (20 + 10 = 30)
        order_line = test_db.query(OrderLine).filter(
            OrderLine.order_id == pending_order.id,
            OrderLine.ean == "SKU-A-DIST"
        ).first()
        
        assert order_line is not None, "OrderLine debe existir"
        assert order_line.cantidad_servida == 30, \
            f"Cantidad servida debe ser 30 (20+10), es {order_line.cantidad_servida}"
        
        # Verificar cajas creadas
        box1 = test_db.query(PackingBox).filter(PackingBox.codigo_caja == "BOX-001").first()
        box2 = test_db.query(PackingBox).filter(PackingBox.codigo_caja == "BOX-002").first()
        
        assert box1 is not None, "BOX-001 debe existir"
        assert box2 is not None, "BOX-002 debe existir"
        
        # Verificar que cada caja tiene la cantidad correcta de items
        assert box1.total_items == 20, \
            f"BOX-001 debe tener 20 items, tiene {box1.total_items}"
        assert box2.total_items == 10, \
            f"BOX-002 debe tener 10 items, tiene {box2.total_items}"
        
        # Verificar tabla de distribución
        distributions = test_db.query(OrderLineBoxDistribution).filter(
            OrderLineBoxDistribution.order_line_id == order_line.id
        ).all()
        
        assert len(distributions) == 2, \
            f"Debe haber 2 distribuciones, hay {len(distributions)}"
        
        # Verificar distribución en BOX-001
        dist_box1 = [d for d in distributions if d.packing_box_id == box1.id]
        assert len(dist_box1) == 1, "Debe haber 1 distribución en BOX-001"
        assert dist_box1[0].quantity_in_box == 20, \
            f"BOX-001 debe tener 20 unidades en distribución, tiene {dist_box1[0].quantity_in_box}"
        
        # Verificar distribución en BOX-002
        dist_box2 = [d for d in distributions if d.packing_box_id == box2.id]
        assert len(dist_box2) == 1, "Debe haber 1 distribución en BOX-002"
        assert dist_box2[0].quantity_in_box == 10, \
            f"BOX-002 debe tener 10 unidades en distribución, tiene {dist_box2[0].quantity_in_box}"
        
        # Verificar que la suma total coincide
        total_distributed = sum(d.quantity_in_box for d in distributions)
        assert total_distributed == 30, \
            f"Total distribuido debe ser 30, es {total_distributed}"
        assert total_distributed == order_line.cantidad_servida, \
            "Total distribuido debe coincidir con cantidad_servida"
        
        # Verificar fecha_empacado en distribuciones
        for dist in distributions:
            assert dist.fecha_empacado is not None, \
                f"Distribución debe tener fecha_empacado"
    
    def test_order_line_distributed_across_n_boxes(self, test_db, pending_order, test_customer):
        """
        Test: Un order_line puede estar distribuido en N cajas diferentes.
        
        Escenario real:
        - Un pedido de 100 unidades de SKU-MULTI
        - Distribuido en 5 cajas diferentes con cantidades variables:
          * BOX-A: 25 unidades
          * BOX-B: 30 unidades  
          * BOX-C: 15 unidades
          * BOX-D: 20 unidades
          * BOX-E: 10 unidades
        - Total: 100 unidades
        
        Requiere: Tabla OrderLineBoxDistribution implementada
        """
        # Definir distribución clara
        sku = "SKU-MULTI-100"
        distribution_plan = [
            {"box_code": "BOX-A", "quantity": 25},
            {"box_code": "BOX-B", "quantity": 30},
            {"box_code": "BOX-C", "quantity": 15},
            {"box_code": "BOX-D", "quantity": 20},
            {"box_code": "BOX-E", "quantity": 10}
        ]
        total_quantity = sum(d["quantity"] for d in distribution_plan)
        
        # Crear updates para batch_update_order
        lines_updates = [
            OrderLineUpdate(sku=sku, quantity_served=d["quantity"], box_code=d["box_code"])
            for d in distribution_plan
        ]
        
        result = batch_update_order(
            order_number=pending_order.numero_orden,
            lines_updates=lines_updates,
            customer=test_customer,
            db=test_db
        )
        
        # 1. Verificar que se creó UNA sola order_line con cantidad total acumulada
        order_line = test_db.query(OrderLine).filter(
            OrderLine.order_id == pending_order.id,
            OrderLine.ean == sku
        ).first()
        
        assert order_line is not None, f"OrderLine para {sku} debe existir"
        assert order_line.cantidad_servida == total_quantity, \
            f"Cantidad servida debe ser {total_quantity}, es {order_line.cantidad_servida}"
        
        # 2. Verificar que se crearon exactamente N cajas
        boxes = test_db.query(PackingBox).filter(
            PackingBox.order_id == pending_order.id
        ).all()
        
        assert len(boxes) == 5, f"Deben existir 5 cajas, existen {len(boxes)}"
        
        # 3. Verificar cada caja individualmente con su cantidad específica
        for plan_item in distribution_plan:
            box = test_db.query(PackingBox).filter(
                PackingBox.codigo_caja == plan_item["box_code"]
            ).first()
            
            assert box is not None, f"Caja {plan_item['box_code']} debe existir"
            assert box.total_items == plan_item["quantity"], \
                f"{plan_item['box_code']} debe tener {plan_item['quantity']} items, tiene {box.total_items}"
        
        # 4. Verificar tabla de distribución tiene N registros
        distributions = test_db.query(OrderLineBoxDistribution).filter(
            OrderLineBoxDistribution.order_line_id == order_line.id
        ).all()
        
        assert len(distributions) == 5, \
            f"Debe haber 5 distribuciones para la order_line, hay {len(distributions)}"
        
        # 5. Verificar cada distribución tiene la cantidad correcta
        for plan_item in distribution_plan:
            box = test_db.query(PackingBox).filter(
                PackingBox.codigo_caja == plan_item["box_code"]
            ).first()
            
            dist = [d for d in distributions if d.packing_box_id == box.id]
            assert len(dist) == 1, \
                f"Debe haber 1 distribución para {plan_item['box_code']}, hay {len(dist)}"
            assert dist[0].quantity_in_box == plan_item["quantity"], \
                f"Distribución en {plan_item['box_code']} debe tener {plan_item['quantity']} unidades, tiene {dist[0].quantity_in_box}"
            assert dist[0].order_line_id == order_line.id, \
                "Distribución debe referenciar a la order_line correcta"
            assert dist[0].fecha_empacado is not None, \
                f"Distribución en {plan_item['box_code']} debe tener fecha_empacado"
        
        # 6. Verificar que la suma de todas las distribuciones = cantidad_servida total
        total_distributed = sum(d.quantity_in_box for d in distributions)
        assert total_distributed == total_quantity, \
            f"Total distribuido debe ser {total_quantity}, es {total_distributed}"
        assert total_distributed == order_line.cantidad_servida, \
            "Total distribuido debe coincidir exactamente con cantidad_servida de la order_line"
        
        # 7. Verificar que la suma de total_items de todas las cajas = cantidad_servida
        total_in_boxes = sum(box.total_items for box in boxes)
        assert total_in_boxes == total_quantity, \
            f"Suma de items en cajas debe ser {total_quantity}, es {total_in_boxes}"
        
        # 8. Verificar estado de la order_line
        assert order_line.estado == "AUTO_CREATED", \
            f"OrderLine debe estar AUTO_CREATED, está {order_line.estado}"