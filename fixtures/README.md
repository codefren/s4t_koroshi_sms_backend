# 🏭 Sistema de Fixtures - Productos y Ubicaciones

Sistema de factories y fixtures para inicializar la base de datos con datos de productos y ubicaciones, similar al patrón usado en `init_order_system.py`.

## 📋 Tabla de Contenidos

- [Instalación](#-instalación)
- [Uso Rápido](#-uso-rápido)
- [Factories Disponibles](#-factories-disponibles)
- [Script de Seeding](#-script-de-seeding)
- [Ejemplos de Uso](#-ejemplos-de-uso)
- [Mejores Prácticas](#-mejores-prácticas)

---

## 🚀 Instalación

No requiere instalación adicional. Las fixtures están listas para usar.

---

## ⚡ Uso Rápido

### 1. Cargar Datos de Ejemplo

```bash
python seed_products.py
```

**Resultado:**
- 5 productos con 7 ubicaciones
- Productos de diferentes categorías (camisas, pantalones, sudaderas, chaquetas)
- Diferentes configuraciones de stock

### 2. Ver Estadísticas

```bash
python seed_products.py --stats
```

### 3. Recargar Datos (Eliminar y Recrear)

```bash
python seed_products.py --force
```

### 4. Cargar Escenarios de Prueba

```bash
python seed_products.py --scenario test
```

**Incluye:**
- Producto con stock bajo (3 ubicaciones)
- Producto con 6 ubicaciones
- 3 productos inactivos

### 5. Limpiar Base de Datos

```bash
python seed_products.py --scenario clear
```

---

## 🏭 Factories Disponibles

### Factories Básicas

#### `create_product()`

Crea un producto individual.

```python
from fixtures.product_fixtures import create_product

product = create_product(
    session,
    referencia="A1B2C3",
    nombre_producto="Camisa Polo",
    color_id="000001",
    talla="M",
    descripcion_color="Rojo",
    ean="8445962763983",
    sku="2523HA02",
    temporada="Verano 2024",
    activo=True,
    commit=True  # Hace commit automáticamente
)
```

**Parámetros:**
- **Requeridos**: `referencia`, `nombre_producto`, `color_id`, `talla`
- **Opcionales**: `descripcion_color`, `ean`, `sku`, `temporada`, `activo`
- **commit**: Si `True`, hace commit automático

#### `create_location()`

Crea una ubicación para un producto.

```python
from fixtures.product_fixtures import create_location

location = create_location(
    session,
    product=product,
    pasillo="A",
    lado="IZQUIERDA",
    ubicacion="12",
    altura=2,
    stock_minimo=10,
    stock_actual=45,
    activa=True,
    commit=True
)
```

**Parámetros:**
- **Requeridos**: `product`, `pasillo`, `lado`, `ubicacion`, `altura`
- **Opcionales**: `stock_minimo`, `stock_actual`, `activa`
- **commit**: Si `True`, hace commit automático

#### `create_product_with_locations()`

Crea un producto con múltiples ubicaciones en una sola operación.

```python
from fixtures.product_fixtures import create_product_with_locations

product = create_product_with_locations(
    session,
    product_data={
        "referencia": "ABC123",
        "nombre_producto": "Test Product",
        "color_id": "001",
        "talla": "M"
    },
    locations_data=[
        {"pasillo": "A", "lado": "IZQUIERDA", "ubicacion": "12", "altura": 2, "stock_actual": 45},
        {"pasillo": "B", "lado": "DERECHA", "ubicacion": "05", "altura": 1, "stock_actual": 12}
    ],
    commit=True
)
```

---

### Factories de Datos Semilla

#### `create_sample_products()`

Crea 5 productos de ejemplo con ubicaciones.

```python
from fixtures.product_fixtures import create_sample_products

products = create_sample_products(session, force=False)
# force=True elimina productos existentes primero
```

**Productos incluidos:**

1. **Camisa Polo Roja M** (A1B2C3)
   - 2 ubicaciones: Pasillo A y B3
   
2. **Pantalón Vaquero Azul 32** (D4E5F6)
   - 1 ubicación: Pasillo C
   
3. **Camisa Polo Azul Marino L** (7G8H9I)
   - 2 ubicaciones: Pasillo A y D
   
4. **Sudadera Negra XL** (1A2B3C)
   - 1 ubicación: Pasillo B (stock bajo ⚠️)
   
5. **Chaqueta Verde M** (FF00AA)
   - 2 ubicaciones: Pasillo E

#### `get_sample_products_data()`

Obtiene los datos sin crear en BD (útil para inspección).

```python
from fixtures.product_fixtures import get_sample_products_data

data = get_sample_products_data()
# Retorna lista de diccionarios con estructura product + locations
```

---

### Factories Especializadas

#### `create_low_stock_scenario()`

Crea un producto con 3 ubicaciones con stock bajo.

```python
from fixtures.product_fixtures import create_low_stock_scenario

locations = create_low_stock_scenario(session)

# Resultado:
# - Ubicación 1: Stock 5/20 (necesita 15) ⚠️
# - Ubicación 2: Stock 3/15 (necesita 12) ⚠️
# - Ubicación 3: Stock 0/10 (necesita 10) ⚠️
```

**Uso:** Testing de sistema de alertas de stock.

#### `create_multi_location_product()`

Crea un producto con múltiples ubicaciones distribuidas.

```python
from fixtures.product_fixtures import create_multi_location_product

product = create_multi_location_product(session, num_locations=8)

# Resultado: Producto con 8 ubicaciones en diferentes pasillos/alturas
```

**Uso:** Testing de queries complejas y rendimiento.

#### `create_inactive_products()`

Crea productos inactivos (descontinuados).

```python
from fixtures.product_fixtures import create_inactive_products

inactive_products = create_inactive_products(session, count=5)

# Resultado: 5 productos con activo=False
```

**Uso:** Testing de filtros y soft delete.

---

### Utilidades

#### `clear_all_products()`

Elimina todos los productos y ubicaciones.

```python
from fixtures.product_fixtures import clear_all_products

count = clear_all_products(session)
print(f"Eliminados {count} productos")
```

#### `get_product_stats()`

Obtiene estadísticas de la base de datos.

```python
from fixtures.product_fixtures import get_product_stats

stats = get_product_stats(session)

print(f"Total productos: {stats['total_products']}")
print(f"Activos: {stats['active_products']}")
print(f"Ubicaciones: {stats['total_locations']}")
print(f"Stock bajo: {stats['low_stock_locations']}")
print(f"Stock total: {stats['total_stock']}")
```

---

## 🎯 Script de Seeding

### Comandos Disponibles

```bash
# Cargar datos de ejemplo (5 productos)
python seed_products.py

# Forzar recarga (elimina datos existentes)
python seed_products.py --force

# Solo estadísticas
python seed_products.py --stats

# Cargar solo escenarios de prueba
python seed_products.py --scenario test

# Cargar todo (ejemplo + test)
python seed_products.py --scenario all

# Limpiar base de datos
python seed_products.py --scenario clear
```

### Salida del Script

```
======================================================================
   SEED DE DATOS - Sistema de Productos y Ubicaciones
======================================================================
🔧 Verificando tablas...
✅ Tablas verificadas:
   - product_references
   - product_locations

📦 Cargando datos de productos...
✅ 5 productos creados exitosamente
   • A1B2C3 - Camisa Polo Manga Corta
     └─ 2 ubicaciones
   • D4E5F6 - Pantalón Vaquero Slim
     └─ 1 ubicaciones
   ...

📊 Estadísticas de la base de datos:

   📦 Productos:
      • Total: 5
      • Activos: 5
      • Inactivos: 0

   📍 Ubicaciones:
      • Total: 7
      • Activas: 7
      • Inactivas: 0

   ⚠️  Alertas:
      • Stock bajo: 1 ubicaciones

   📈 Stock:
      • Total: 151 unidades

======================================================================
✅ Seed completado exitosamente
======================================================================
```

---

## 💡 Ejemplos de Uso

### Ejemplo 1: Script de Desarrollo

```python
#!/usr/bin/env python3
"""Script para resetear DB de desarrollo."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sqlalchemy.orm import sessionmaker
from src.adapters.secondary.database.config import engine
from fixtures.product_fixtures import create_sample_products, clear_all_products

Session = sessionmaker(bind=engine)
session = Session()

# Limpiar
print("Limpiando DB...")
clear_all_products(session)

# Cargar datos
print("Cargando datos...")
products = create_sample_products(session)

print(f"✅ {len(products)} productos creados")
session.close()
```

### Ejemplo 2: Testing con Factories

```python
import pytest
from fixtures.product_fixtures import create_product, create_location

def test_create_product_with_location(test_db_session):
    # Usar factory para crear producto
    product = create_product(
        test_db_session,
        referencia="TEST01",
        nombre_producto="Test Product",
        color_id="001",
        talla="M",
        commit=True
    )
    
    # Crear ubicación
    location = create_location(
        test_db_session,
        product=product,
        pasillo="A",
        lado="IZQUIERDA",
        ubicacion="99",
        altura=1,
        stock_actual=50,
        commit=True
    )
    
    assert location.codigo_ubicacion == "A-IZQUIERDA-99-1"
    assert location.product_id == product.id
```

### Ejemplo 3: Crear Datos Personalizados

```python
from fixtures.product_fixtures import create_product_with_locations

# Definir estructura
custom_products = [
    {
        "product": {
            "referencia": "CUSTOM1",
            "nombre_producto": "Mi Producto",
            "color_id": "999",
            "talla": "XXL"
        },
        "locations": [
            {"pasillo": "Z", "lado": "IZQUIERDA", "ubicacion": "01", "altura": 1},
            {"pasillo": "Z", "lado": "DERECHA", "ubicacion": "01", "altura": 1}
        ]
    }
]

# Crear
for item in custom_products:
    product = create_product_with_locations(
        session,
        product_data=item["product"],
        locations_data=item["locations"]
    )
    print(f"Creado: {product.referencia}")
```

### Ejemplo 4: Integración con Tests de Pytest

```python
# En conftest.py
import pytest
from fixtures.product_fixtures import create_sample_products

@pytest.fixture(scope="session")
def seeded_db_session(test_db_session):
    """Sesión con datos semilla cargados."""
    create_sample_products(test_db_session)
    yield test_db_session
    test_db_session.rollback()

# En test_*.py
def test_query_products(seeded_db_session):
    products = seeded_db_session.query(ProductReference).all()
    assert len(products) == 5
```

---

## ✅ Mejores Prácticas

### 1. Usar Fixtures en Lugar de Datos Hardcodeados

```python
# ❌ MAL
product = ProductReference(
    referencia="A1B2C3",
    nombre_producto="Camisa",
    color_id="001",
    talla="M"
)
session.add(product)
session.commit()

# ✅ BIEN
from fixtures.product_fixtures import create_product

product = create_product(
    session,
    referencia="A1B2C3",
    nombre_producto="Camisa",
    color_id="001",
    talla="M",
    commit=True
)
```

### 2. Usar `commit=False` para Transacciones Atómicas

```python
# Crear múltiples productos en una transacción
products = []
for data in products_data:
    product = create_product(session, **data, commit=False)
    products.append(product)

# Commit una sola vez
session.commit()
```

### 3. Verificar Antes de Cargar

```python
existing = session.query(ProductReference).count()
if existing > 0:
    print(f"Ya existen {existing} productos")
    # Decidir qué hacer
```

### 4. Usar Escenarios Específicos en Tests

```python
from fixtures.product_fixtures import create_low_stock_scenario

def test_low_stock_alerts(test_db_session):
    # Crear escenario específico
    locations = create_low_stock_scenario(test_db_session)
    
    # Testear lógica de alertas
    alerts = find_low_stock_locations(test_db_session)
    assert len(alerts) == len(locations)
```

---

## 🔄 Flujo de Trabajo Recomendado

### Desarrollo

```bash
# 1. Resetear DB de desarrollo
python seed_products.py --scenario clear
python seed_products.py --force

# 2. Trabajar en features...

# 3. Ver estadísticas
python seed_products.py --stats

# 4. Agregar escenarios de prueba si necesitas
python seed_products.py --scenario test
```

### Testing

```python
# tests/conftest.py
from fixtures.product_fixtures import create_sample_products

@pytest.fixture
def populated_db(test_db_session):
    create_sample_products(test_db_session)
    return test_db_session
```

### Staging/Producción

```bash
# Solo cargar datos necesarios
python seed_products.py  # Datos mínimos

# O crear script personalizado
python scripts/seed_production.py
```

---

## 📊 Comparación con init_order_system.py

| Característica | init_order_system.py | seed_products.py |
|----------------|---------------------|------------------|
| **Patrón** | Seed directo | Factories + Seed |
| **Reutilización** | Baja | Alta |
| **Tests** | No integrado | Diseñado para tests |
| **Flexibilidad** | Media | Alta |
| **Escenarios** | Fijo | Múltiples |
| **CLI** | Básico | Avanzado |

---

## 🚀 Próximos Pasos

1. ✅ Ejecutar seed: `python seed_products.py`
2. ✅ Verificar datos: `python seed_products.py --stats`
3. ⏳ Crear endpoints API para productos
4. ⏳ Integrar con sistema de órdenes
5. ⏳ Dashboard de stock

---

## 📚 Archivos Relacionados

- `fixtures/product_fixtures.py` - Factories y utilidades
- `seed_products.py` - Script CLI de seeding
- `init_product_system.py` - Script original (legacy)
- `tests/conftest.py` - Fixtures para pytest

---

**Última actualización:** 2026-01-05  
**Versión:** 1.0.0  
**Patrón:** Factory Pattern + Seed Data
