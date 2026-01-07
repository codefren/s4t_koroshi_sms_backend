# 🧪 Guía de Tests y Fixtures

Documentación completa de los fixtures disponibles y cómo usarlos en tests.

## 📋 Tabla de Contenidos

- [Instalación](#-instalación)
- [Ejecutar Tests](#-ejecutar-tests)
- [Fixtures Disponibles](#-fixtures-disponibles)
- [Ejemplos de Uso](#-ejemplos-de-uso)
- [Mejores Prácticas](#-mejores-prácticas)

---

## 📦 Instalación

### 1. Instalar pytest

```bash
cd /home/efrenoscar/Project/s4t_koroshi_sms_backend
source src/venv/bin/activate  # Activar entorno virtual
pip install pytest pytest-cov
```

### 2. Verificar instalación

```bash
pytest --version
```

---

## 🚀 Ejecutar Tests

### Ejecutar todos los tests

```bash
pytest tests/ -v
```

### Ejecutar tests de un archivo específico

```bash
pytest tests/test_product_models.py -v
```

### Ejecutar un test específico

```bash
pytest tests/test_product_models.py::TestProductReferenceCreation::test_create_product_with_minimal_data -v
```

### Ejecutar tests con cobertura

```bash
pytest tests/ --cov=src --cov-report=html
```

### Ejecutar tests en modo verbose con output

```bash
pytest tests/ -v -s
```

---

## 🎯 Fixtures Disponibles

### Fixtures de Base de Datos

#### `test_db_engine`
- **Scope**: function (se crea/destruye en cada test)
- **Descripción**: Engine de SQLite en memoria
- **Uso**: Base para otros fixtures

```python
def test_example(test_db_engine):
    # Engine disponible para usar
    pass
```

#### `test_db_session`
- **Scope**: function
- **Descripción**: Sesión de BD con rollback automático
- **Uso**: Para interactuar con la base de datos en tests

```python
def test_example(test_db_session):
    product = ProductReference(...)
    test_db_session.add(product)
    test_db_session.commit()
```

---

### Fixtures de Productos

#### `sample_product_data`
- **Tipo**: dict
- **Descripción**: Datos de ejemplo para crear un producto
- **Uso**: Para crear productos en tests

```python
def test_example(sample_product_data):
    # sample_product_data = {
    #     "referencia": "A1B2C3",
    #     "nombre_producto": "Camisa Polo Manga Corta",
    #     ...
    # }
    product = ProductReference(**sample_product_data)
```

#### `sample_product`
- **Tipo**: ProductReference (ORM)
- **Descripción**: Producto creado y guardado en BD
- **Uso**: Cuando necesitas un producto ya existente

```python
def test_example(test_db_session, sample_product):
    # Producto ya existe en BD
    assert sample_product.id is not None
    assert sample_product.referencia == "A1B2C3"
```

#### `multiple_products`
- **Tipo**: List[ProductReference]
- **Descripción**: 4 productos diferentes (3 activos, 1 inactivo)
- **Uso**: Para tests de queries y filtros

```python
def test_example(test_db_session, multiple_products):
    # 4 productos disponibles
    assert len(multiple_products) == 4
    
    # Consultar solo activos
    active = [p for p in multiple_products if p.activo]
    assert len(active) == 3
```

**Productos incluidos:**
1. Camisa Polo Roja M (A1B2C3) - Activo
2. Pantalón Vaquero Azul 32 (D4E5F6) - Activo
3. Camisa Polo Azul Marino L (7G8H9I) - Activo
4. Producto Inactivo (ABC123) - Inactivo

---

### Fixtures de Ubicaciones

#### `sample_location_data`
- **Tipo**: dict
- **Descripción**: Datos de ejemplo para crear una ubicación
- **Uso**: Para crear ubicaciones manualmente

```python
def test_example(sample_location_data):
    # sample_location_data = {
    #     "pasillo": "A",
    #     "lado": "IZQUIERDA",
    #     "ubicacion": "12",
    #     "altura": 2,
    #     ...
    # }
```

#### `sample_location`
- **Tipo**: ProductLocation (ORM)
- **Descripción**: Ubicación creada y guardada en BD
- **Uso**: Cuando necesitas una ubicación existente

```python
def test_example(test_db_session, sample_location):
    # Ubicación ya existe en BD
    assert sample_location.id is not None
    assert sample_location.codigo_ubicacion == "A-IZQUIERDA-12-2"
```

#### `multiple_locations`
- **Tipo**: List[ProductLocation]
- **Descripción**: 3 ubicaciones para un producto
- **Uso**: Para tests de múltiples ubicaciones

```python
def test_example(test_db_session, multiple_locations):
    # 3 ubicaciones disponibles
    assert len(multiple_locations) == 3
    
    # Todas del mismo producto
    product_id = multiple_locations[0].product_id
    assert all(loc.product_id == product_id for loc in multiple_locations)
```

**Ubicaciones incluidas:**
1. Pasillo A, Izquierda, Pos 12, Altura 2 (Stock: 45/10)
2. Pasillo B3, Derecha, Pos 05, Altura 1 (Stock: 12/5)
3. Pasillo C, Izquierda, Pos 08, Altura 3 (Stock: 23/8)

#### `product_with_multiple_locations`
- **Tipo**: ProductReference (con 4 ubicaciones)
- **Descripción**: Producto con múltiples ubicaciones en diferentes estados
- **Uso**: Para tests de relaciones y alertas

```python
def test_example(test_db_session, product_with_multiple_locations):
    # Producto con 4 ubicaciones
    assert len(product_with_multiple_locations.locations) == 4
    
    # Iterar ubicaciones
    for location in product_with_multiple_locations.locations:
        print(f"{location.codigo_ubicacion}: Stock {location.stock_actual}")
```

**Ubicaciones incluidas:**
1. Pasillo A, Izquierda, Altura 2 - Stock: 45/10 ✅
2. Pasillo B3, Derecha, Altura 1 - Stock: 12/5 ✅
3. Pasillo C, Izquierda, Altura 3 - Stock: 3/8 ⚠️ (Stock bajo)
4. Pasillo D, Derecha, Altura 4 - Stock: 0/5, Inactiva ❌

#### `locations_with_low_stock`
- **Tipo**: List[ProductLocation]
- **Descripción**: 3 ubicaciones con stock bajo (para alertas)
- **Uso**: Para testear sistema de alertas

```python
def test_example(test_db_session, locations_with_low_stock):
    # Todas tienen stock bajo
    for loc in locations_with_low_stock:
        assert loc.stock_actual < loc.stock_minimo
```

---

### Fixtures de Datos Pydantic

#### `product_create_data`
- **Tipo**: dict
- **Descripción**: Datos válidos para ProductReferenceCreate
- **Uso**: Para testear validaciones de creación

```python
from src.core.domain.models import ProductReferenceCreate

def test_example(product_create_data):
    product = ProductReferenceCreate(**product_create_data)
    assert product.referencia == "AAABBB"
```

#### `product_update_data`
- **Tipo**: dict
- **Descripción**: Datos válidos para ProductReferenceUpdate
- **Uso**: Para testear validaciones de actualización

```python
from src.core.domain.models import ProductReferenceUpdate

def test_example(product_update_data):
    update = ProductReferenceUpdate(**product_update_data)
    assert update.nombre_producto == "Updated Product Name"
```

#### `location_create_data`
- **Tipo**: dict
- **Descripción**: Datos válidos para ProductLocationCreate

#### `location_update_data`
- **Tipo**: dict
- **Descripción**: Datos válidos para ProductLocationUpdate

---

### Fixtures de Validación

#### `invalid_product_data`
- **Tipo**: List[dict]
- **Descripción**: 3 casos de datos inválidos
- **Uso**: Para testear validaciones

```python
from pydantic import ValidationError
from src.core.domain.models import ProductReferenceCreate

def test_example(invalid_product_data):
    for invalid_data in invalid_product_data:
        with pytest.raises(ValidationError):
            ProductReferenceCreate(**invalid_data)
```

**Casos incluidos:**
1. Referencia no hexadecimal ("ZZZZZ")
2. Referencia vacía ("")
3. Nombre vacío ("")

#### `invalid_location_data`
- **Tipo**: List[dict]
- **Descripción**: 3 casos de ubicaciones inválidas
- **Uso**: Para testear validaciones de ubicaciones

**Casos incluidos:**
1. Altura = 0 (debe ser >= 1)
2. Altura = 11 (debe ser <= 10)
3. Stock negativo

---

### Fixtures Auxiliares

#### `current_datetime`
- **Tipo**: datetime
- **Descripción**: Fecha/hora actual UTC

#### `sample_operator`
- **Tipo**: Operator (ORM)
- **Descripción**: Operario de ejemplo
- **Uso**: Para tests integrados con operarios

```python
def test_example(test_db_session, sample_operator):
    assert sample_operator.codigo_operario == "OP001"
```

---

## 💡 Ejemplos de Uso

### Ejemplo 1: Test Simple de Creación

```python
def test_create_simple_product(test_db_session):
    """Crear un producto simple."""
    product = ProductReference(
        referencia="TEST01",
        nombre_producto="Test Product",
        color_id="001",
        talla="M"
    )
    
    test_db_session.add(product)
    test_db_session.commit()
    
    assert product.id is not None
    assert product.activo is True
```

### Ejemplo 2: Test con Fixture de Producto

```python
def test_update_product_name(test_db_session, sample_product):
    """Actualizar nombre usando fixture."""
    sample_product.nombre_producto = "Nuevo Nombre"
    test_db_session.commit()
    
    test_db_session.refresh(sample_product)
    assert sample_product.nombre_producto == "Nuevo Nombre"
```

### Ejemplo 3: Test de Relaciones

```python
def test_product_locations(test_db_session, product_with_multiple_locations):
    """Verificar relaciones producto-ubicaciones."""
    # Producto tiene 4 ubicaciones
    assert len(product_with_multiple_locations.locations) == 4
    
    # Todas las ubicaciones apuntan al mismo producto
    for location in product_with_multiple_locations.locations:
        assert location.product_id == product_with_multiple_locations.id
```

### Ejemplo 4: Test de Alertas de Stock

```python
def test_low_stock_alerts(test_db_session, locations_with_low_stock):
    """Encontrar ubicaciones con stock bajo."""
    # Todas las ubicaciones del fixture tienen stock bajo
    for loc in locations_with_low_stock:
        assert loc.stock_actual < loc.stock_minimo
    
    # Consultar desde BD
    alerts = test_db_session.query(ProductLocation).filter(
        ProductLocation.stock_actual < ProductLocation.stock_minimo
    ).all()
    
    assert len(alerts) == 3
```

### Ejemplo 5: Test de Validación Pydantic

```python
from pydantic import ValidationError
from src.core.domain.models import ProductReferenceCreate

def test_invalid_referencia(invalid_product_data):
    """Validar que referencia no hexadecimal falle."""
    invalid_data = invalid_product_data[0]  # Primera entrada (no hex)
    
    with pytest.raises(ValidationError) as exc_info:
        ProductReferenceCreate(**invalid_data)
    
    assert "referencia" in str(exc_info.value)
```

### Ejemplo 6: Test de Queries Complejas

```python
from sqlalchemy import func

def test_stock_total_por_producto(test_db_session, product_with_multiple_locations):
    """Calcular stock total sumando todas las ubicaciones."""
    total_stock = test_db_session.query(
        func.sum(ProductLocation.stock_actual)
    ).filter(
        ProductLocation.product_id == product_with_multiple_locations.id,
        ProductLocation.activa == True
    ).scalar()
    
    # 45 + 12 + 3 = 60 (ubicación inactiva no cuenta)
    assert total_stock == 60
```

---

## ✅ Mejores Prácticas

### 1. Usar el fixture mínimo necesario

```python
# ❌ MAL: Usar fixture complejo cuando no se necesita
def test_count_products(test_db_session, product_with_multiple_locations):
    count = test_db_session.query(ProductReference).count()
    assert count == 1

# ✅ BIEN: Usar fixture simple
def test_count_products(test_db_session, sample_product):
    count = test_db_session.query(ProductReference).count()
    assert count == 1
```

### 2. No modificar fixtures compartidos

```python
# ❌ MAL: Modificar fixture directamente
def test_deactivate(test_db_session, sample_product):
    sample_product.activo = False  # Modifica el fixture
    test_db_session.commit()

# ✅ BIEN: Crear copia o usar fixture diseñado para modificarse
def test_deactivate(test_db_session, sample_product):
    # El fixture está diseñado para ser modificado en el test
    # Y se hace rollback automático después
    sample_product.activo = False
    test_db_session.commit()
    assert sample_product.activo is False
```

### 3. Nombrar tests descriptivamente

```python
# ❌ MAL
def test_1(test_db_session):
    pass

# ✅ BIEN
def test_create_product_with_valid_hexadecimal_referencia(test_db_session):
    pass
```

### 4. Usar clases para agrupar tests relacionados

```python
class TestProductCreation:
    """Tests relacionados con creación de productos."""
    
    def test_create_with_minimal_data(self, test_db_session):
        pass
    
    def test_create_with_complete_data(self, test_db_session):
        pass
```

### 5. Testear un concepto por test

```python
# ❌ MAL: Test hace muchas cosas
def test_product_operations(test_db_session):
    product = ProductReference(...)
    test_db_session.add(product)  # Crear
    product.nombre = "New"  # Actualizar
    test_db_session.delete(product)  # Eliminar
    # Demasiadas responsabilidades

# ✅ BIEN: Tests separados
def test_create_product(test_db_session):
    product = ProductReference(...)
    test_db_session.add(product)
    assert product.id is not None

def test_update_product(test_db_session, sample_product):
    sample_product.nombre = "New"
    test_db_session.commit()
    assert sample_product.nombre == "New"
```

---

## 📊 Cobertura de Tests

Los tests actuales cubren:

- ✅ Creación de productos (mínimos y completos)
- ✅ Constraints únicos (referencia)
- ✅ Valores por defecto
- ✅ Queries simples y complejas
- ✅ Actualización de productos
- ✅ Creación de ubicaciones
- ✅ Propiedad `codigo_ubicacion`
- ✅ Relaciones One-to-Many
- ✅ Cascade delete
- ✅ Gestión de stock
- ✅ Alertas de stock bajo
- ✅ Validaciones Pydantic
- ✅ Edge cases

---

## 🚀 Comandos Útiles

```bash
# Ejecutar todos los tests
pytest tests/ -v

# Solo tests de productos
pytest tests/test_product_models.py -v

# Tests de una clase específica
pytest tests/test_product_models.py::TestProductReferenceCreation -v

# Test específico
pytest tests/test_product_models.py::TestProductReferenceCreation::test_create_product_with_minimal_data -v

# Con cobertura
pytest tests/ --cov=src --cov-report=html

# Ver output de prints
pytest tests/ -v -s

# Modo watch (requiere pytest-watch)
ptw tests/

# Ejecutar solo tests que fallaron la última vez
pytest tests/ --lf

# Parar en el primer fallo
pytest tests/ -x
```

---

## 📚 Recursos

- **Pytest**: https://docs.pytest.org/
- **SQLAlchemy**: https://docs.sqlalchemy.org/
- **Pydantic**: https://docs.pydantic.dev/

---

**Última actualización:** 2026-01-05  
**Tests totales:** 40+  
**Fixtures disponibles:** 15+
