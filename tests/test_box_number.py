"""
Tests for Box Number Registration System.

Tests cover:
- New box number registration
- Duplicate box number handling (idempotent)
- Validation errors
- Special characters handling
"""
import pytest
from sqlalchemy.orm import Session

from src.adapters.secondary.database.orm import APIMatricula
from src.api_service.schemas import RegisterBoxNumberRequest
from src.api_service.service import register_box_number


class TestBoxNumberRegistration:
    """Test suite for box number registration"""
    
    def test_register_box_number_new(self, test_db: Session):
        """Test: Register a new box number"""
        request = RegisterBoxNumberRequest(box_number="BOX-12345")
        
        result = register_box_number(request, test_db)
        
        # Verify response
        assert result.status == "success"
        assert result.box_number == "BOX-12345"
        assert "registered successfully" in result.message
        
        # Verify database record
        db_record = test_db.query(APIMatricula).filter(
            APIMatricula.box_number == "BOX-12345"
        ).first()
        
        assert db_record is not None
        assert db_record.box_number == "BOX-12345"
        assert db_record.status == "PENDING"
        assert db_record.error_detail is None
        assert db_record.created_at is not None
        assert db_record.updated_at is not None
    
    def test_register_box_number_duplicate(self, test_db: Session):
        """Test: Register same box number twice should raise 409 Conflict error"""
        from fastapi import HTTPException
        
        # First registration
        request1 = RegisterBoxNumberRequest(box_number="BOX-DUPLICATE")
        result1 = register_box_number(request1, test_db)
        
        assert result1.status == "success"
        
        # Second registration (duplicate) - should raise HTTPException 409
        request2 = RegisterBoxNumberRequest(box_number="BOX-DUPLICATE")
        
        with pytest.raises(HTTPException) as exc_info:
            register_box_number(request2, test_db)
        
        # Verify error details
        assert exc_info.value.status_code == 409
        assert "already been verified" in exc_info.value.detail.lower()
        assert "BOX-DUPLICATE" in exc_info.value.detail
        
        # Verify only one record exists in database
        all_records = test_db.query(APIMatricula).filter(
            APIMatricula.box_number == "BOX-DUPLICATE"
        ).all()
        assert len(all_records) == 1
    
    def test_register_box_number_validation_errors(self, test_db: Session):
        """Test: Validation errors for invalid box numbers"""
        from pydantic import ValidationError
        
        # Test 1: Empty box_number
        with pytest.raises(ValidationError) as exc_info:
            RegisterBoxNumberRequest(box_number="")
        assert "box_number" in str(exc_info.value).lower()
        
        # Test 2: Box number too long (> 20 chars)
        with pytest.raises(ValidationError) as exc_info:
            RegisterBoxNumberRequest(box_number="BOX-123456789012345678901")  # 26 chars
        assert "box_number" in str(exc_info.value).lower()
        
        # Test 3: Missing box_number field
        with pytest.raises(ValidationError):
            RegisterBoxNumberRequest()
    
    def test_register_box_number_special_characters(self, test_db: Session):
        """Test: Box numbers with special characters are allowed"""
        test_cases = [
            "BOX-001",
            "BOX_002",
            "BOX.003",
            "BOX#004",
            "BOX@005",
            "ABC-XYZ-123",
            "12345",
            "MIX_CHARS-#123",
        ]
        
        for box_num in test_cases:
            if len(box_num) <= 20:  # Within max length
                request = RegisterBoxNumberRequest(box_number=box_num)
                result = register_box_number(request, test_db)
                
                assert result.status == "success"
                assert result.box_number == box_num
                
                # Verify in database
                db_record = test_db.query(APIMatricula).filter(
                    APIMatricula.box_number == box_num
                ).first()
                assert db_record is not None
    
    def test_register_box_number_existing_with_different_status(self, test_db: Session):
        """Test: Register box number that exists with SYNCHRONIZED status should raise 409"""
        from fastapi import HTTPException
        
        # Create existing record with SYNCHRONIZED status
        existing = APIMatricula(
            box_number="BOX-SYNCHRONIZED",
            status="SYNCHRONIZED",
            error_detail=None
        )
        test_db.add(existing)
        test_db.commit()
        
        # Try to register again - should raise HTTPException 409
        request = RegisterBoxNumberRequest(box_number="BOX-SYNCHRONIZED")
        
        with pytest.raises(HTTPException) as exc_info:
            register_box_number(request, test_db)
        
        # Verify error details
        assert exc_info.value.status_code == 409
        assert "already been verified" in exc_info.value.detail.lower()
        
        # Verify status hasn't changed (still SYNCHRONIZED)
        db_record = test_db.query(APIMatricula).filter(
            APIMatricula.box_number == "BOX-SYNCHRONIZED"
        ).first()
        assert db_record.status == "SYNCHRONIZED"
    
    def test_register_box_number_max_length(self, test_db: Session):
        """Test: Box number at exactly max length (20 chars)"""
        # Exactly 20 characters
        max_length_box = "12345678901234567890"
        assert len(max_length_box) == 20
        
        request = RegisterBoxNumberRequest(box_number=max_length_box)
        result = register_box_number(request, test_db)
        
        assert result.status == "success"
        assert result.box_number == max_length_box
        
        # Verify in database
        db_record = test_db.query(APIMatricula).filter(
            APIMatricula.box_number == max_length_box
        ).first()
        assert db_record is not None
