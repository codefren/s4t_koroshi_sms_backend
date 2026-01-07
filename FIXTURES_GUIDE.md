# 🎯 Guía Completa del Sistema de Fixtures

Sistema completo de fixtures y seeding para inicializar la base de datos con datos de productos y ubicaciones.

## 📊 Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                     BASE DE DATOS                            │
│  (SQLite/PostgreSQL)                                         │
│                                                              │
│  ┌──────────────┐         ┌───────────────┐               │
│  │  products    │  1────< │  locations    │               │
│  │  _references │         │               │               │
│  └──────────────┘         └───────────────┘               │
└─────────────────────────────────────────────────────────────┘
                    ▲                ▲
                    │                │
        ┌───────────┴────────┬───────┴────────────┐
        │                    │                     │
┌───────┴────────┐  ┌────────┴─────────┐  ┌──────┴──────┐
│   FIXTURES     │  │  SCRIPT SEEDING   │  │    TESTS    │
│   (Factories)  │  │  seed_products.py │  │  conftest.py│
│                │  │                   │  │             │
│ • create_*()   │  │ CLI Interface:    │  │ Fixtures:   │
│ • get_*_data() │  │ --force           │  │ • test_db   │
│ • clear_*()    │  │ --scenario        │  │ • sample_*  │
│ • stats()      │  │ --stats           │  │ • multiple_*│
└────────────────┘  └───────────────────┘  └─────────────┘
     ▲                      ▲                      ▲
     │                      │                      │
     └──────────────────────┴──────────────────────┘
              PATRÓN: FACTORY + SEED DATA
```

---

## 🗂️ Estructura de Archivos

```
s4t_koroshi_sms_backend/
│
├── fixtures/                          # 🏭 Módulo de Fixtures
│   ├── __init__.py
│   ├── product_fixtures.py           # Factories de productos/ubicaciones
│   └── README.md                     # Documentación de fixtures
│
├── tests/                            # 🧪 Tests
│   ├── __init__.py
│   ├── conftest.py                   # Fixtures de pytest (integra fixtures/)
│   ├── test_product_models.py        # Tests usando fixtures
│   └── README.md                     # Guía de tests
│
├── src/                              # 📦 Código fuente
│   ├── adapters/secondary/database/
│   │   ├── orm.py                    # Modelos ProductReference, ProductLocation
│   │   └── config.py                 # Configuración de BD
│   └── core/domain/
│       └── models.py                 # Modelos Pydantic
│
├── seed_products.py                  # 🌱 Script CLI de seeding
├── init_product_system.py            # 📝 Script original (legacy)
├── FIXTURES_GUIDE.md                 # 📚 Esta guía
├── PRODUCTS_SYSTEM.md                # 📖 Documentación de modelos
└── run_tests.sh                      # 🧪 Script para ejecutar tests
```

---

## 🚀 Flujos de Uso

### Flujo 1: Inicializar Base de Datos (Desarrollo)

```bash
# Paso 1: Crear tablas y cargar datos
python seed_products.py

# Paso 2: Verificar
python seed_products.py --stats

# Resultado:
# - 5 productos creados
# - 7 ubicaciones creadas
# - Base de datos lista para desarrollo
```

**Cuándo usar:** Cuando empiezas a trabajar o reseteas tu entorno local.

---

### Flujo 2: Desarrollo con Datos Limpios

```bash
# Limpiar DB
python seed_products.py --scenario clear

# Recargar datos
python seed_products.py --force

# O en un solo paso
python seed_products.py --force --scenario all
```

**Cuándo usar:** Cuando quieres empezar desde cero o tus datos están corruptos.

---

### Flujo 3: Testing Automatizado

```bash
# Ejecutar todos los tests (usa fixtures automáticamente)
pytest tests/ -v

# Tests usan fixtures de conftest.py que integran fixtures/
```

**Qué sucede:**
1. `pytest` carga `tests/conftest.py`
2. `conftest.py` define fixtures usando `fixtures/product_fixtures.py`
3. Tests usan fixtures como `sample_product`, `multiple_locations`, etc.
4. Base de datos en memoria (SQLite) se crea y destruye automáticamente

---

### Flujo 4: Crear Datos Personalizados (Programático)

```python
# mi_script.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sqlalchemy.orm import sessionmaker
from src.adapters.secondary.database.config import engine
from fixtures.product_fixtures import create_product, create_location

Session = sessionmaker(bind=engine)
session = Session()

# Crear producto
product = create_product(
    session,
    referencia="CUSTOM",
    nombre_producto="Mi Producto Custom",
    color_id="999",
    talla="XXL",
    commit=True
)

# Crear ubicación
location = create_location(
    session,
    product=product,
    pasillo="Z",
    lado="IZQUIERDA",
    ubicacion="99",
    altura=5,
    stock_actual=100,
    commit=True
)

print(f"✅ Creado: {product.referencia} en {location.codigo_ubicacion}")
session.close()
```

---

## 🏭 Factories Disponibles

### Quick Reference

| Factory | Propósito | Uso |
|---------|-----------|-----|
| `create_product()` | Crear 1 producto | Básico |
| `create_location()` | Crear 1 ubicación | Básico |
| `create_product_with_locations()` | Producto + N ubicaciones | Conveniente |
| `create_sample_products()` | 5 productos ejemplo | Seeding |
| `create_low_stock_scenario()` | Testing alertas | Tests |
| `create_multi_location_product()` | Testing performance | Tests |
| `create_inactive_products()` | Testing filtros | Tests |
| `clear_all_products()` | Limpiar BD | Utilidad |
| `get_product_stats()` | Estadísticas | Diagnóstico |

---

## 🎯 Casos de Uso Comunes

### Caso 1: Resetear DB de Desarrollo Rápidamente

```bash
python seed_products.py --force
```

### Caso 2: Solo Ver Estadísticas

```bash
python seed_products.py --stats
```

### Caso 3: Cargar Escenarios de Prueba Adicionales

```bash
# Cargar datos normales + escenarios de prueba
python seed_products.py --scenario all
```

### Caso 4: Testear con Datos Específicos

```python
# tests/test_my_feature.py
def test_my_feature(test_db_session):
    from fixtures.product_fixtures import create_low_stock_scenario
    
    # Crear escenario específico
    locations = create_low_stock_scenario(test_db_session)
    
    # Tu lógica de test
    alerts = my_alert_system(test_db_session)
    assert len(alerts) == 3
```

### Caso 5: Fixture Reutilizable en Tests

```python
# tests/conftest.py (ya incluido)
@pytest.fixture
def populated_db_session(test_db_session):
    from fixtures.product_fixtures import create_sample_products
    create_sample_products(test_db_session)
    return test_db_session

# tests/test_*.py
def test_query(populated_db_session):
    # BD ya tiene 5 productos
    products = populated_db_session.query(ProductReference).all()
    assert len(products) == 5
```

---

## 📊 Datos de Ejemplo Incluidos

### Productos Creados por `seed_products.py`

| Referencia | Producto | Color | Talla | Ubicaciones | Stock Total |
|------------|----------|-------|-------|-------------|-------------|
| A1B2C3 | Camisa Polo Manga Corta | Rojo (000001) | M | 2 | 57 |
| D4E5F6 | Pantalón Vaquero Slim | Azul (000010) | 32 | 1 | 23 |
| 7G8H9I | Camisa Polo Manga Corta | Azul (000002) | L | 2 | 46 |
| 1A2B3C | Sudadera con Capucha | Negro (000003) | XL | 1 | 5 ⚠️ |
| FF00AA | Chaqueta Deportiva | Verde (000005) | M | 2 | 55 |

**Total: 5 productos, 7 ubicaciones, 186 unidades**

### Ubicaciones por Pasillo

| Pasillo | Lado | Productos | Stock Total |
|---------|------|-----------|-------------|
| A | Izquierda | 1 | 45 |
| A | Derecha | 1 | 38 |
| B | Izquierda | 1 | 5 |
| B3 | Derecha | 1 | 12 |
| C | Izquierda | 1 | 23 |
| D | Izquierda | 1 | 8 |
| E | Derecha | 1 | 55 |

---

## 🧪 Integración con Tests

### Fixtures Disponibles en Tests (conftest.py)

#### Fixtures de Base de Datos

- `test_db_engine` - Engine SQLite en memoria
- `test_db_session` - Sesión con rollback automático

#### Fixtures de Productos (Individuales)

- `sample_product_data` - Datos de ejemplo (dict)
- `sample_product` - Producto creado en BD
- `multiple_products` - 4 productos (3 activos, 1 inactivo)

#### Fixtures de Ubicaciones (Individuales)

- `sample_location_data` - Datos de ejemplo (dict)
- `sample_location` - Ubicación creada en BD
- `multiple_locations` - 3 ubicaciones para un producto
- `product_with_multiple_locations` - Producto con 4 ubicaciones
- `locations_with_low_stock` - 3 ubicaciones con stock bajo

#### Fixtures de Seeding (Integradas)

- `populated_db_session` - BD con 5 productos de ejemplo
- `seeded_with_test_scenarios` - BD con ejemplo + escenarios de prueba

#### Fixtures de Validación

- `invalid_product_data` - Casos de error para testing
- `invalid_location_data` - Casos de error para ubicaciones

### Ejemplo de Test Completo

```python
import pytest
from src.adapters.secondary.database.orm import ProductReference

class TestProductQueries:
    """Tests usando fixtures integradas."""
    
    def test_count_all_products(self, populated_db_session):
        """Test con BD pre-poblada."""
        count = populated_db_session.query(ProductReference).count()
        assert count == 5  # 5 productos de ejemplo
    
    def test_filter_active_products(self, populated_db_session):
        """Filtrar solo activos."""
        active = populated_db_session.query(ProductReference).filter_by(
            activo=True
        ).all()
        assert len(active) == 5  # Todos son activos
    
    def test_low_stock_alerts(self, seeded_with_test_scenarios):
        """Test con escenarios de prueba."""
        from sqlalchemy import and_
        
        low_stock = seeded_with_test_scenarios.query(ProductLocation).filter(
            ProductLocation.stock_actual < ProductLocation.stock_minimo,
            ProductLocation.activa == True
        ).all()
        
        # Debe haber alertas de:
        # - Producto de ejemplo (Sudadera: 5/12)
        # - Escenario low-stock (3 ubicaciones)
        assert len(low_stock) >= 4
```

---

## 🔄 Comparación: Legacy vs Nuevo Sistema

| Aspecto | init_product_system.py (Legacy) | fixtures/ + seed_products.py (Nuevo) |
|---------|--------------------------------|-------------------------------------|
| **Estructura** | Script monolítico | Modular (fixtures + CLI) |
| **Reutilización** | Baja | Alta (factories) |
| **Testing** | No integrado | Totalmente integrado |
| **CLI** | Básico (input manual) | Avanzado (argumentos) |
| **Escenarios** | Solo datos ejemplo | Múltiples escenarios |
| **Flexibilidad** | Baja | Alta (composable) |
| **Mantenibilidad** | Media | Alta |
| **Tests** | No | Sí (40+ tests) |

**Recomendación:** Usar el nuevo sistema para desarrollo activo. Mantener legacy solo como referencia.

---

## 📚 Referencias Rápidas

### Comandos Esenciales

```bash
# Inicializar BD
python seed_products.py

# Limpiar y recargar
python seed_products.py --force

# Ver estadísticas
python seed_products.py --stats

# Ejecutar tests
pytest tests/ -v

# Tests con cobertura
pytest tests/ --cov=src
```

### Importaciones Comunes

```python
# Para scripts de seeding
from fixtures.product_fixtures import (
    create_product,
    create_location,
    create_sample_products
)

# Para tests
import pytest
from fixtures.product_fixtures import create_low_stock_scenario
```

---

## 🎓 Mejores Prácticas

### ✅ DO - Hacer

1. Usar factories en lugar de crear modelos manualmente
2. Usar `commit=False` para transacciones atómicas
3. Verificar datos existentes antes de cargar
4. Usar escenarios específicos en tests
5. Documentar fixtures custom

### ❌ DON'T - No Hacer

1. No hardcodear datos en tests
2. No usar fixtures pesadas para tests simples
3. No modificar fixtures compartidas sin documentar
4. No mezclar datos de prueba con datos reales
5. No ignorar errores de seeding

---

## 🚀 Próximos Pasos

1. ✅ Fixtures creadas y documentadas
2. ✅ Sistema de seeding implementado
3. ✅ Tests integrados
4. ⏳ Crear endpoints API para productos
5. ⏳ Dashboard de gestión de stock
6. ⏳ Sistema de alertas automático

---

## 🆘 Troubleshooting

### Problema: "Ya existen productos"

```bash
# Solución: Forzar recarga
python seed_products.py --force
```

### Problema: Tests fallan con "no table"

```bash
# Solución: Las tablas se crean automáticamente en tests
# Verifica que test_db_engine esté en conftest.py
```

### Problema: "ModuleNotFoundError: No module named 'fixtures'"

```python
# Solución: Agregar path al inicio del script
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
```

---

**Última actualización:** 2026-01-05  
**Autor:** Sistema SMS Backend  
**Patrón:** Factory Pattern + Seed Data + Test Fixtures
