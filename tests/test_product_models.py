"""
Tests para modelos de productos y ubicaciones.

Ejecutar tests:
    pytest tests/test_product_models.py -v
    pytest tests/test_product_models.py::test_nombre_especifico -v
    pytest tests/ -v  # Todos los tests
"""

import pytest
from sqlalchemy.exc import IntegrityError
from src.adapters.secondary.database.orm import ProductReference, ProductLocation


# ============================================================================
# TESTS DE CREACIÓN DE PRODUCTOS
# ============================================================================

class TestProductReferenceCreation:
    """Tests para creación de referencias de producto."""
    
    def test_create_product_with_minimal_data(self, test_db_session):
        """Test: Crear producto con datos mínimos requeridos."""
        product = ProductReference(
            referencia="AAA111",
            nombre_producto="Test Product",
            color_id="001",
            talla="M"
        )
        
        test_db_session.add(product)
        test_db_session.commit()
        
        assert product.id is not None
        assert product.referencia == "AAA111"
        assert product.activo is True  # Default value
        assert product.created_at is not None
        assert product.updated_at is not None
    
    def test_create_product_with_complete_data(self, test_db_session, sample_product_data):
        """Test: Crear producto con todos los datos."""
        product = ProductReference(**sample_product_data)
        
        test_db_session.add(product)
        test_db_session.commit()
        
        assert product.id is not None
        assert product.referencia == sample_product_data["referencia"]
        assert product.nombre_producto == sample_product_data["nombre_producto"]
        assert product.color_id == sample_product_data["color_id"]
        assert product.talla == sample_product_data["talla"]
        assert product.ean == sample_product_data["ean"]
        assert product.sku == sample_product_data["sku"]
    
    def test_unique_referencia_constraint(self, test_db_session, sample_product):
        """Test: La referencia debe ser única."""
        # Intentar crear otro producto con la misma referencia
        duplicate_product = ProductReference(
            referencia=sample_product.referencia,  # Misma referencia
            nombre_producto="Producto Duplicado",
            color_id="002",
            talla="L"
        )
        
        test_db_session.add(duplicate_product)
        
        with pytest.raises(IntegrityError):
            test_db_session.commit()
    
    def test_product_defaults(self, test_db_session):
        """Test: Valores por defecto del producto."""
        product = ProductReference(
            referencia="DEF456",
            nombre_producto="Default Test",
            color_id="001",
            talla="S"
        )
        
        test_db_session.add(product)
        test_db_session.commit()
        
        assert product.activo is True
        assert product.descripcion_color is None
        assert product.ean is None
        assert product.sku is None
        assert product.temporada is None


# ============================================================================
# TESTS DE CONSULTA DE PRODUCTOS
# ============================================================================

class TestProductReferenceQuery:
    """Tests para consultas de productos."""
    
    def test_query_product_by_referencia(self, test_db_session, sample_product):
        """Test: Buscar producto por referencia."""
        found = test_db_session.query(ProductReference).filter_by(
            referencia=sample_product.referencia
        ).first()
        
        assert found is not None
        assert found.id == sample_product.id
        assert found.referencia == sample_product.referencia
    
    def test_query_active_products(self, test_db_session, multiple_products):
        """Test: Filtrar solo productos activos."""
        active_products = test_db_session.query(ProductReference).filter_by(
            activo=True
        ).all()
        
        assert len(active_products) == 3  # 3 activos, 1 inactivo
        assert all(p.activo for p in active_products)
    
    def test_query_products_by_color_and_talla(self, test_db_session, multiple_products):
        """Test: Buscar productos por color y talla."""
        products = test_db_session.query(ProductReference).filter(
            ProductReference.color_id == "000001",
            ProductReference.talla == "M"
        ).all()
        
        assert len(products) == 1
        assert products[0].referencia == "A1B2C3"
    
    def test_query_products_by_nombre(self, test_db_session, multiple_products):
        """Test: Buscar productos por nombre (like)."""
        products = test_db_session.query(ProductReference).filter(
            ProductReference.nombre_producto.like("%Camisa Polo%")
        ).all()
        
        assert len(products) == 2
    
    def test_count_products(self, test_db_session, multiple_products):
        """Test: Contar productos."""
        total = test_db_session.query(ProductReference).count()
        active_count = test_db_session.query(ProductReference).filter_by(activo=True).count()
        
        assert total == 4
        assert active_count == 3


# ============================================================================
# TESTS DE ACTUALIZACIÓN DE PRODUCTOS
# ============================================================================

class TestProductReferenceUpdate:
    """Tests para actualización de productos."""
    
    def test_update_product_name(self, test_db_session, sample_product):
        """Test: Actualizar nombre del producto."""
        original_name = sample_product.nombre_producto
        new_name = "Nombre Actualizado"
        
        sample_product.nombre_producto = new_name
        test_db_session.commit()
        
        test_db_session.refresh(sample_product)
        assert sample_product.nombre_producto == new_name
        assert sample_product.nombre_producto != original_name
    
    def test_deactivate_product(self, test_db_session, sample_product):
        """Test: Desactivar producto."""
        assert sample_product.activo is True
        
        sample_product.activo = False
        test_db_session.commit()
        
        test_db_session.refresh(sample_product)
        assert sample_product.activo is False
    
    def test_update_timestamps(self, test_db_session, sample_product):
        """Test: updated_at se actualiza automáticamente."""
        original_updated_at = sample_product.updated_at
        
        # Modificar producto
        sample_product.descripcion_color = "Rojo Intenso"
        test_db_session.commit()
        test_db_session.refresh(sample_product)
        
        assert sample_product.updated_at >= original_updated_at


# ============================================================================
# TESTS DE UBICACIONES
# ============================================================================

class TestProductLocationCreation:
    """Tests para creación de ubicaciones."""
    
    def test_create_location_with_product(self, test_db_session, sample_product, sample_location_data):
        """Test: Crear ubicación asociada a un producto."""
        location = ProductLocation(
            product=sample_product,
            **sample_location_data
        )
        
        test_db_session.add(location)
        test_db_session.commit()
        
        assert location.id is not None
        assert location.product_id == sample_product.id
        assert location.pasillo == sample_location_data["pasillo"]
        assert location.lado == sample_location_data["lado"]
        assert location.ubicacion == sample_location_data["ubicacion"]
        assert location.altura == sample_location_data["altura"]
    
    def test_location_codigo_ubicacion_property(self, test_db_session, sample_location):
        """Test: Propiedad codigo_ubicacion se genera correctamente."""
        expected_code = f"{sample_location.pasillo}-{sample_location.lado}-{sample_location.ubicacion}-{sample_location.altura}"
        
        assert sample_location.codigo_ubicacion == expected_code
        assert sample_location.codigo_ubicacion == "A-IZQUIERDA-12-2"
    
    def test_unique_location_constraint(self, test_db_session, sample_location):
        """Test: No puede haber ubicaciones duplicadas para el mismo producto."""
        # Intentar crear ubicación duplicada
        duplicate = ProductLocation(
            product_id=sample_location.product_id,
            pasillo=sample_location.pasillo,
            lado=sample_location.lado,
            ubicacion=sample_location.ubicacion,
            altura=sample_location.altura,
            stock_minimo=5,
            stock_actual=10
        )
        
        test_db_session.add(duplicate)
        
        with pytest.raises(IntegrityError):
            test_db_session.commit()
    
    def test_location_defaults(self, test_db_session, sample_product):
        """Test: Valores por defecto de ubicación."""
        location = ProductLocation(
            product=sample_product,
            pasillo="Z",
            lado="DERECHA",
            ubicacion="99",
            altura=5
        )
        
        test_db_session.add(location)
        test_db_session.commit()
        
        assert location.stock_minimo == 0
        assert location.stock_actual == 0
        assert location.activa is True


# ============================================================================
# TESTS DE RELACIONES
# ============================================================================

class TestProductLocationRelationships:
    """Tests para relaciones entre productos y ubicaciones."""
    
    def test_product_has_locations(self, test_db_session, product_with_multiple_locations):
        """Test: Un producto puede tener múltiples ubicaciones."""
        assert len(product_with_multiple_locations.locations) == 4
        
        for location in product_with_multiple_locations.locations:
            assert location.product_id == product_with_multiple_locations.id
    
    def test_location_belongs_to_product(self, test_db_session, sample_location):
        """Test: Una ubicación pertenece a un producto."""
        assert sample_location.product is not None
        assert sample_location.product.id == sample_location.product_id
        assert sample_location.product.referencia == "A1B2C3"
    
    def test_cascade_delete(self, test_db_session, product_with_multiple_locations):
        """Test: Al eliminar producto se eliminan sus ubicaciones (cascade)."""
        product_id = product_with_multiple_locations.id
        num_locations = len(product_with_multiple_locations.locations)
        
        assert num_locations == 4
        
        # Eliminar producto
        test_db_session.delete(product_with_multiple_locations)
        test_db_session.commit()
        
        # Verificar que las ubicaciones también se eliminaron
        remaining_locations = test_db_session.query(ProductLocation).filter_by(
            product_id=product_id
        ).count()
        
        assert remaining_locations == 0
    
    def test_query_locations_by_product(self, test_db_session, multiple_locations):
        """Test: Consultar ubicaciones de un producto."""
        product_id = multiple_locations[0].product_id
        
        locations = test_db_session.query(ProductLocation).filter_by(
            product_id=product_id
        ).all()
        
        assert len(locations) == 3


# ============================================================================
# TESTS DE STOCK
# ============================================================================

class TestStockManagement:
    """Tests para gestión de stock."""
    
    def test_identify_low_stock_locations(self, test_db_session, locations_with_low_stock):
        """Test: Identificar ubicaciones con stock bajo."""
        low_stock = test_db_session.query(ProductLocation).filter(
            ProductLocation.stock_actual < ProductLocation.stock_minimo
        ).all()
        
        assert len(low_stock) == 3
        assert all(loc.stock_actual < loc.stock_minimo for loc in low_stock)
    
    def test_calculate_total_stock(self, test_db_session, product_with_multiple_locations):
        """Test: Calcular stock total de un producto (suma de ubicaciones)."""
        from sqlalchemy import func
        
        total_stock = test_db_session.query(
            func.sum(ProductLocation.stock_actual)
        ).filter(
            ProductLocation.product_id == product_with_multiple_locations.id,
            ProductLocation.activa == True
        ).scalar()
        
        # 45 + 12 + 3 = 60 (la cuarta ubicación está inactiva)
        assert total_stock == 60
    
    def test_update_stock(self, test_db_session, sample_location):
        """Test: Actualizar stock de una ubicación."""
        original_stock = sample_location.stock_actual
        new_stock = original_stock + 10
        
        sample_location.stock_actual = new_stock
        test_db_session.commit()
        
        test_db_session.refresh(sample_location)
        assert sample_location.stock_actual == new_stock


# ============================================================================
# TESTS DE BÚSQUEDAS COMPLEJAS
# ============================================================================

class TestComplexQueries:
    """Tests para consultas complejas."""
    
    def test_find_products_by_pasillo(self, test_db_session, product_with_multiple_locations):
        """Test: Encontrar productos en un pasillo específico."""
        products_in_pasillo_a = test_db_session.query(ProductReference).join(
            ProductLocation
        ).filter(
            ProductLocation.pasillo == "A"
        ).distinct().all()
        
        assert len(products_in_pasillo_a) == 1
        assert products_in_pasillo_a[0].id == product_with_multiple_locations.id
    
    def test_find_active_locations_with_stock(self, test_db_session, product_with_multiple_locations):
        """Test: Encontrar ubicaciones activas con stock disponible."""
        locations = test_db_session.query(ProductLocation).filter(
            ProductLocation.activa == True,
            ProductLocation.stock_actual > 0
        ).all()
        
        assert len(locations) == 3  # 3 activas con stock, 1 inactiva
    
    def test_group_locations_by_altura(self, test_db_session, product_with_multiple_locations):
        """Test: Agrupar ubicaciones por altura."""
        from sqlalchemy import func
        
        results = test_db_session.query(
            ProductLocation.altura,
            func.count(ProductLocation.id).label('total')
        ).group_by(
            ProductLocation.altura
        ).all()
        
        assert len(results) == 4  # Alturas: 1, 2, 3, 4
        
        # Verificar que cada altura tiene 1 ubicación
        for altura, total in results:
            assert total == 1
    
    def test_find_products_with_multiple_locations(self, test_db_session, product_with_multiple_locations):
        """Test: Encontrar productos con múltiples ubicaciones."""
        from sqlalchemy import func
        
        products = test_db_session.query(
            ProductReference,
            func.count(ProductLocation.id).label('num_locations')
        ).join(ProductLocation).group_by(
            ProductReference.id
        ).having(
            func.count(ProductLocation.id) > 2
        ).all()
        
        assert len(products) == 1
        assert products[0][0].id == product_with_multiple_locations.id
        assert products[0][1] == 4  # 4 ubicaciones


# ============================================================================
# TESTS DE VALIDACIONES (con Pydantic)
# ============================================================================

class TestPydanticValidations:
    """Tests para validaciones de modelos Pydantic."""
    
    def test_valid_hexadecimal_referencia(self, product_create_data):
        """Test: Referencia hexadecimal válida."""
        from src.core.domain.models import ProductReferenceCreate
        
        product = ProductReferenceCreate(**product_create_data)
        assert product.referencia == "AAABBB"
    
    def test_invalid_hexadecimal_referencia(self):
        """Test: Referencia no hexadecimal debe fallar."""
        from src.core.domain.models import ProductReferenceCreate
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError) as exc_info:
            ProductReferenceCreate(
                referencia="ZZZZZ",  # Z no es hexadecimal
                nombre_producto="Test",
                color_id="001",
                talla="M"
            )
        
        assert "referencia" in str(exc_info.value)
    
    def test_location_altura_range(self):
        """Test: Altura debe estar entre 1 y 10."""
        from src.core.domain.models import ProductLocationCreate
        from pydantic import ValidationError
        
        # Altura válida
        location = ProductLocationCreate(
            product_id=1,
            pasillo="A",
            lado="IZQUIERDA",
            ubicacion="12",
            altura=5  # Válido
        )
        assert location.altura == 5
        
        # Altura inválida (menor que 1)
        with pytest.raises(ValidationError):
            ProductLocationCreate(
                product_id=1,
                pasillo="A",
                lado="IZQUIERDA",
                ubicacion="12",
                altura=0  # Inválido
            )
        
        # Altura inválida (mayor que 10)
        with pytest.raises(ValidationError):
            ProductLocationCreate(
                product_id=1,
                pasillo="A",
                lado="IZQUIERDA",
                ubicacion="12",
                altura=11  # Inválido
            )


# ============================================================================
# TESTS DE PERFORMANCE / EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Tests para casos límite y edge cases."""
    
    def test_product_with_no_locations(self, test_db_session, sample_product):
        """Test: Producto sin ubicaciones."""
        assert len(sample_product.locations) == 0
    
    def test_empty_optional_fields(self, test_db_session):
        """Test: Campos opcionales vacíos."""
        product = ProductReference(
            referencia="EMPTY1",
            nombre_producto="Empty Fields Test",
            color_id="001",
            talla="M",
            descripcion_color=None,
            ean=None,
            sku=None,
            temporada=None
        )
        
        test_db_session.add(product)
        test_db_session.commit()
        
        assert product.id is not None
        assert product.descripcion_color is None
    
    def test_very_long_pasillo_name(self, test_db_session, sample_product):
        """Test: Nombre de pasillo muy largo (hasta el límite)."""
        location = ProductLocation(
            product=sample_product,
            pasillo="ABCD123456",  # 10 caracteres (máximo)
            lado="IZQUIERDA",
            ubicacion="99",
            altura=1
        )
        
        test_db_session.add(location)
        test_db_session.commit()
        
        assert location.pasillo == "ABCD123456"
