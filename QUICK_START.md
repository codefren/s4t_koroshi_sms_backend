# 🚀 Quick Start - Sistema de Gestión de Órdenes y Productos

Guía rápida para comenzar a usar el sistema con la nueva funcionalidad de normalización.

---

## 📋 Requisitos Previos

- Python 3.8+
- PostgreSQL o SQL Server
- pip instalado

---

## ⚡ Inicio Rápido (5 minutos)

### 1. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 2. Configurar Base de Datos

Edita `.env` o configura las variables de entorno:

```env
DATABASE_URL=postgresql://user:password@localhost/dbname
```

### 3. Inicializar Sistema

```bash
# Inicializar sistema de productos
python init_product_system.py

# Inicializar sistema de órdenes
python init_order_system.py

# Cargar datos de ejemplo (opcional)
python seed_products.py
```

### 4. Iniciar API

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Verificar Instalación

```bash
# Ejecutar validaciones
python test_normalization.py

# Abrir documentación interactiva
# http://localhost:8000/docs
```

---

## 🎯 Flujo de Uso Típico

### A. Gestión de Productos

```bash
# 1. Ver productos disponibles
curl http://localhost:8000/api/v1/products

# 2. Ver ubicaciones de un producto
curl http://localhost:8000/api/v1/products/1/locations

# 3. Crear nueva ubicación
curl -X POST http://localhost:8000/api/v1/products/1/locations \
  -H "Content-Type: application/json" \
  -d '{
    "pasillo": "A",
    "lado": "IZQUIERDA",
    "ubicacion": "12",
    "altura": 2,
    "stock_actual": 50,
    "prioridad": 1
  }'
```

### B. Importar Órdenes

```bash
# Importar desde VIEW (automáticamente vincula con productos)
python etl_import_orders.py
```

**Resultado:** Órdenes importadas y vinculadas con productos/ubicaciones automáticamente.

### C. Optimizar Picking

```bash
# Generar ruta optimizada para una orden
curl -X POST http://localhost:8000/api/v1/orders/1/optimize-picking-route
```

**Respuesta:**
```json
{
  "picking_route": [
    {
      "secuencia": 1,
      "producto": "Camisa Polo",
      "ubicacion": "A-12, Izq, A2-12",
      "pasillo": "A",
      "prioridad": 1
    }
  ],
  "estimated_time_minutes": 15.0
}
```

### D. Validar Stock

```bash
# Verificar si hay stock suficiente
curl http://localhost:8000/api/v1/orders/1/stock-validation
```

**Respuesta:**
```json
{
  "can_complete": true,
  "summary": {
    "insufficient_stock": 0,
    "no_location": 0
  }
}
```

---

## 🔧 Comandos Útiles

### Migración de Datos Históricos

```bash
# Ver qué pasaría (dry run)
python migrate_orders_to_products.py --dry-run

# Ejecutar migración real
python migrate_orders_to_products.py --report

# Solo validar estado actual
python migrate_orders_to_products.py --validate
```

### Verificación del Sistema

```bash
# Verificar base de datos
python check_db.py

# Verificar sistema de órdenes
python check_order_system.py

# Validar implementación completa
python test_normalization.py
```

### ETL y Carga de Datos

```bash
# Importar órdenes desde VIEW
python etl_import_orders.py

# Cargar productos de ejemplo
python seed_products.py

# Verificar fixtures
python verify_fixtures.py
```

---

## 📚 Endpoints Principales

### Productos

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/products` | Lista todos los productos |
| GET | `/api/v1/products/{id}` | Detalle de un producto |
| GET | `/api/v1/products/{id}/locations` | Ubicaciones del producto |
| POST | `/api/v1/products/{id}/locations` | Crear ubicación ✅ |
| GET | `/api/v1/products/{id}/stock-summary` | Resumen de stock |

### Órdenes

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/orders` | Lista órdenes |
| GET | `/api/v1/orders/{id}` | Detalle de orden (mejorado) ✅ |
| POST | `/api/v1/orders/{id}/optimize-picking-route` | Optimizar ruta ✅ NUEVO |
| GET | `/api/v1/orders/{id}/stock-validation` | Validar stock ✅ NUEVO |
| PUT | `/api/v1/orders/{id}/assign-operator` | Asignar operario |
| PUT | `/api/v1/orders/{id}/status` | Cambiar estado |

### Operarios

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/operators` | Lista operarios |
| GET | `/api/v1/operators/{id}` | Detalle de operario |

---

## 📊 Casos de Uso

### 1. Crear Producto con Ubicaciones

```python
import requests

# Crear producto
product = requests.post('http://localhost:8000/api/v1/products', json={
    "referencia": "POLO001",
    "sku": "2523HA02",
    "nombre_producto": "Camisa Polo Manga Corta",
    "ean": "8445962763983"
})

product_id = product.json()['id']

# Agregar ubicación principal
requests.post(f'http://localhost:8000/api/v1/products/{product_id}/locations', json={
    "pasillo": "A",
    "lado": "IZQUIERDA",
    "ubicacion": "12",
    "altura": 2,
    "stock_actual": 50,
    "prioridad": 1  # Alta prioridad
})

# Agregar ubicación secundaria
requests.post(f'http://localhost:8000/api/v1/products/{product_id}/locations', json={
    "pasillo": "B",
    "lado": "DERECHA",
    "ubicacion": "08",
    "altura": 3,
    "stock_actual": 25,
    "prioridad": 3  # Media prioridad
})
```

### 2. Importar y Procesar Orden

```python
# 1. Importar órdenes (ETL)
import subprocess
subprocess.run(['python', 'etl_import_orders.py'])

# 2. Obtener orden
order = requests.get('http://localhost:8000/api/v1/orders/1').json()

# 3. Validar stock
validation = requests.get('http://localhost:8000/api/v1/orders/1/stock-validation').json()

if validation['can_complete']:
    # 4. Optimizar ruta
    route = requests.post('http://localhost:8000/api/v1/orders/1/optimize-picking-route').json()
    
    # 5. Asignar operario
    requests.put('http://localhost:8000/api/v1/orders/1/assign-operator', json={
        "operator_id": 1
    })
    
    print(f"Ruta optimizada: {len(route['picking_route'])} paradas")
    print(f"Tiempo estimado: {route['estimated_time_minutes']} minutos")
else:
    print("⚠️ Stock insuficiente:", validation['summary'])
```

### 3. Dashboard de Picking (Ejemplo)

```python
# Obtener órdenes pendientes
orders = requests.get('http://localhost:8000/api/v1/orders?estado_codigo=ASSIGNED').json()

for order in orders:
    # Optimizar ruta
    route = requests.post(
        f'http://localhost:8000/api/v1/orders/{order["id"]}/optimize-picking-route'
    ).json()
    
    print(f"Orden {order['numero_orden']}:")
    print(f"  - Pasillos: {route['aisles_to_visit']}")
    print(f"  - Tiempo: {route['estimated_time_minutes']} min")
    print(f"  - Paradas: {route['total_stops']}")
```

---

## 🐛 Troubleshooting

### Problema: "API no responde"

```bash
# Verificar que la API está corriendo
curl http://localhost:8000/health

# Si no responde, iniciar:
uvicorn src.main:app --reload
```

### Problema: "Órdenes no se vinculan con productos"

```bash
# Verificar que hay productos en la BD
python check_db.py

# Ejecutar migración
python migrate_orders_to_products.py --report
```

### Problema: "Error de base de datos"

```bash
# Verificar conexión
python check_db.py

# Reinicializar si es necesario
python init_product_system.py
python init_order_system.py
```

---

## 📖 Documentación Completa

- **Sistema de Productos:** `PRODUCTS_SYSTEM.md`
- **Sistema de Órdenes:** `ORDERS_SYSTEM_README.md`
- **Normalización:** `NORMALIZATION_REPORT.md`
- **Implementación:** `IMPLEMENTATION_COMPLETE.md`
- **API Completa:** `API_ENDPOINTS.md`
- **Swagger UI:** http://localhost:8000/docs

---

## 🎯 Métricas de Éxito

Después de implementar, deberías ver:

✅ **>90%** de órdenes vinculadas con productos  
✅ **20-30%** reducción en tiempo de picking  
✅ **0** errores de stock insuficiente (con validación)  
✅ **<200ms** tiempo de respuesta en endpoints  

---

## 🆘 Soporte

Si encuentras problemas:

1. Revisa logs: `src/logs/app.log`
2. Ejecuta validación: `python test_normalization.py`
3. Consulta documentación en `/docs`
4. Revisa `IMPLEMENTATION_COMPLETE.md`

---

**Versión:** 1.0.0  
**Última actualización:** 2026-01-07  
**Estado:** ✅ Producción Ready
