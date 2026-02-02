"""
Tests for Stock Movement Registration System.

Tests cover:
- Single SKU registration with existing product
- Multiple unique SKUs registration
- Duplicate SKU accumulation
- Auto-creation of missing products
- Mixed existing and new products
- Validation errors
"""
import pytest
from sqlalchemy.orm import Session

from src.adapters.secondary.database.orm import ProductReference, APIStockHistorico
from src.api_service.schemas import RegisterStockRequest, StockLineItem
from src.api_service.service import register_stock


class TestStockMovements:
    """Test suite for stock movement registration"""
    
    def test_register_stock_single_sku_existing_product(self, test_db: Session):
        """Test: Register stock for a single SKU that already exists in catalog"""
        # Create existing product
        product = ProductReference(
            sku="TEST-SKU-001",
            referencia="TEST001",
            nombre_producto="Test Product 1",
            color_id="001",
            nombre_color="Red",
            talla="M",
            posicion_talla=1,
            activo=True
        )
        test_db.add(product)
        test_db.commit()
        
        # Register stock movement
        request = RegisterStockRequest(
            origin="WAREHOUSE1",
            destinity="STORE1",
            stock_line=[
                StockLineItem(sku="TEST-SKU-001", quantity=50)
            ]
        )
        
        result = register_stock(request, test_db)
        
        # Verify response
        assert result.status == "success"
        assert result.total_lines_received == 1
        assert result.unique_skus_processed == 1
        assert result.products_auto_created == 0
        assert result.records_created == 1
        
        # Verify database record
        stock_record = test_db.query(APIStockHistorico).filter(
            APIStockHistorico.product_reference_id == product.id
        ).first()
        
        assert stock_record is not None
        assert stock_record.quantity == 50
        assert stock_record.origin == "WAREHOUSE1"
        assert stock_record.destinity == "STORE1"
        assert stock_record.status == "PENDING"
        assert stock_record.product_reference.sku == "TEST-SKU-001"
    
    def test_register_stock_multiple_unique_skus(self, test_db: Session):
        """Test: Register stock for multiple different SKUs"""
        # Create existing products
        products = [
            ProductReference(
                sku=f"TEST-SKU-{i:03d}",
                referencia=f"TEST{i:03d}",
                nombre_producto=f"Test Product {i}",
                color_id="001",
                talla="M",
                posicion_talla=i,
                activo=True
            )
            for i in range(1, 4)
        ]
        for product in products:
            test_db.add(product)
        test_db.commit()
        
        # Register stock movements
        request = RegisterStockRequest(
            origin="WAREHOUSE2",
            destinity="STORE2",
            stock_line=[
                StockLineItem(sku="TEST-SKU-001", quantity=10),
                StockLineItem(sku="TEST-SKU-002", quantity=20),
                StockLineItem(sku="TEST-SKU-003", quantity=30)
            ]
        )
        
        result = register_stock(request, test_db)
        
        # Verify response
        assert result.status == "success"
        assert result.total_lines_received == 3
        assert result.unique_skus_processed == 3
        assert result.products_auto_created == 0
        assert result.records_created == 3
        
        # Verify database records
        stock_records = test_db.query(APIStockHistorico).all()
        assert len(stock_records) == 3
        
        quantities = sorted([r.quantity for r in stock_records])
        assert quantities == [10, 20, 30]
    
    def test_register_stock_duplicate_skus_accumulation(self, test_db: Session):
        """Test: Duplicate SKUs in request should accumulate quantities"""
        # Create existing product
        product = ProductReference(
            sku="TEST-SKU-DUP",
            referencia="TESTDUP",
            nombre_producto="Duplicate Test Product",
            color_id="001",
            talla="L",
            posicion_talla=1,
            activo=True
        )
        test_db.add(product)
        test_db.commit()
        
        # Register stock with duplicate SKU
        request = RegisterStockRequest(
            origin="WAREHOUSE3",
            destinity="STORE3",
            stock_line=[
                StockLineItem(sku="TEST-SKU-DUP", quantity=10),
                StockLineItem(sku="TEST-SKU-DUP", quantity=15),
                StockLineItem(sku="TEST-SKU-DUP", quantity=25)
            ]
        )
        
        result = register_stock(request, test_db)
        
        # Verify response
        assert result.status == "success"
        assert result.total_lines_received == 3
        assert result.unique_skus_processed == 1  # Only 1 unique SKU
        assert result.products_auto_created == 0
        assert result.records_created == 1  # Only 1 record created
        
        # Verify accumulated quantity
        stock_record = test_db.query(APIStockHistorico).filter(
            APIStockHistorico.product_reference_id == product.id
        ).first()
        
        assert stock_record is not None
        assert stock_record.quantity == 50  # 10 + 15 + 25 = 50
    
    def test_register_stock_auto_create_product(self, test_db: Session):
        """Test: Auto-create product when SKU doesn't exist"""
        # Register stock for non-existent SKU
        request = RegisterStockRequest(
            origin="WAREHOUSE4",
            destinity="STORE4",
            stock_line=[
                StockLineItem(sku="NEW-SKU-AUTO", quantity=100)
            ]
        )
        
        result = register_stock(request, test_db)
        
        # Verify response
        assert result.status == "success"
        assert result.total_lines_received == 1
        assert result.unique_skus_processed == 1
        assert result.products_auto_created == 1  # Product was auto-created
        assert result.records_created == 1
        
        # Verify auto-created product
        product = test_db.query(ProductReference).filter(
            ProductReference.sku == "NEW-SKU-AUTO"
        ).first()
        
        assert product is not None
        assert product.nombre_producto == "AUTO-NEW-SKU-AUTO"
        assert product.referencia == "AUTO-NEW-SKU-AUTO"
        assert product.color_id == "AUTO"
        assert product.talla == "N/A"
        assert product.posicion_talla == 0
        assert product.temporada == "AUTO_CREATED"
        assert product.activo is True
        
        # Verify stock record
        stock_record = test_db.query(APIStockHistorico).filter(
            APIStockHistorico.product_reference_id == product.id
        ).first()
        
        assert stock_record is not None
        assert stock_record.quantity == 100
    
    def test_register_stock_mixed_existing_and_new_products(self, test_db: Session):
        """Test: Register stock with mix of existing and new products"""
        # Create 2 existing products
        existing_products = [
            ProductReference(
                sku="EXISTING-001",
                referencia="EX001",
                nombre_producto="Existing Product 1",
                color_id="001",
                talla="S",
                posicion_talla=1,
                activo=True
            ),
            ProductReference(
                sku="EXISTING-002",
                referencia="EX002",
                nombre_producto="Existing Product 2",
                color_id="002",
                talla="M",
                posicion_talla=2,
                activo=True
            )
        ]
        for product in existing_products:
            test_db.add(product)
        test_db.commit()
        
        # Register stock with 2 existing + 2 new SKUs
        request = RegisterStockRequest(
            origin="WAREHOUSE5",
            destinity="STORE5",
            stock_line=[
                StockLineItem(sku="EXISTING-001", quantity=10),
                StockLineItem(sku="NEW-AUTO-001", quantity=20),
                StockLineItem(sku="EXISTING-002", quantity=30),
                StockLineItem(sku="NEW-AUTO-002", quantity=40)
            ]
        )
        
        result = register_stock(request, test_db)
        
        # Verify response
        assert result.status == "success"
        assert result.total_lines_received == 4
        assert result.unique_skus_processed == 4
        assert result.products_auto_created == 2  # 2 new products created
        assert result.records_created == 4
        
        # Verify all products exist
        all_products = test_db.query(ProductReference).all()
        skus = [p.sku for p in all_products]
        assert "EXISTING-001" in skus
        assert "EXISTING-002" in skus
        assert "NEW-AUTO-001" in skus
        assert "NEW-AUTO-002" in skus
        
        # Verify stock records
        stock_records = test_db.query(APIStockHistorico).all()
        assert len(stock_records) == 4
    
    def test_register_stock_validation_errors(self, test_db: Session):
        """Test: Validation errors for invalid requests"""
        from pydantic import ValidationError
        
        # Test 1: origin too long (> 10 chars)
        with pytest.raises(ValidationError) as exc_info:
            RegisterStockRequest(
                origin="WAREHOUSE123456",  # 15 chars, exceeds 10
                destinity="STORE1",
                stock_line=[StockLineItem(sku="TEST", quantity=10)]
            )
        assert "origin" in str(exc_info.value).lower()
        
        # Test 2: destinity too long (> 10 chars)
        with pytest.raises(ValidationError) as exc_info:
            RegisterStockRequest(
                origin="WAREHOUSE1",
                destinity="STORE12345678",  # 14 chars, exceeds 10
                stock_line=[StockLineItem(sku="TEST", quantity=10)]
            )
        assert "destinity" in str(exc_info.value).lower()
        
        # Test 3: empty stock_line
        with pytest.raises(ValidationError) as exc_info:
            RegisterStockRequest(
                origin="WAREHOUSE1",
                destinity="STORE1",
                stock_line=[]  # Empty list
            )
        assert "stock_line" in str(exc_info.value).lower()
        
        # Test 4: quantity <= 0
        with pytest.raises(ValidationError) as exc_info:
            RegisterStockRequest(
                origin="WAREHOUSE1",
                destinity="STORE1",
                stock_line=[StockLineItem(sku="TEST", quantity=0)]  # Zero quantity
            )
        assert "quantity" in str(exc_info.value).lower()
        
        # Test 5: negative quantity
        with pytest.raises(ValidationError) as exc_info:
            RegisterStockRequest(
                origin="WAREHOUSE1",
                destinity="STORE1",
                stock_line=[StockLineItem(sku="TEST", quantity=-10)]  # Negative
            )
        assert "quantity" in str(exc_info.value).lower()
