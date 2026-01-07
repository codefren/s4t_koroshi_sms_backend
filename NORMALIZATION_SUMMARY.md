# 📋 Resumen Ejecutivo - Normalización de Órdenes

## 🎯 Objetivo

Vincular `order_lines` con `product_references` y `product_locations` para:
- ✅ Eliminar duplicación de datos
- ✅ Usar ubicaciones reales del almacén
- ✅ Optimizar rutas de picking
- ✅ Validar stock disponible en tiempo real

---

## 📊 Cambios en Base de Datos

### Agregar a `order_lines`:

```sql
-- Nueva FK a ProductReference
product_reference_id INT NULL  -- Nullable para órdenes históricas

-- Nueva FK a ProductLocation
product_location_id INT NULL   -- Nullable para órdenes históricas
```

**Mantener campos existentes:** ✅ (para histórico)

---

## 🔧 Endpoints a Modificar

### 1. 🔴 CRÍTICO - ETL de Importación

**Archivo:** `etl_import_orders.py`

**Función:** `_create_order_line_from_view()`

**Cambio:**
```python
# ANTES: Solo guardar datos desnormalizados
order_line = OrderLine(
    ean=view_row.ean,
    ubicacion=view_row.ubicacion,
    articulo=view_row.articulo,
    # ...
)

# DESPUÉS: Vincular con productos + guardar histórico
product = buscar_producto_por_ean_o_sku(view_row.ean, view_row.articulo)
location = buscar_mejor_ubicacion(product.id) if product else None

order_line = OrderLine(
    # Nuevas referencias
    product_reference_id=product.id if product else None,
    product_location_id=location.id if location else None,
    
    # Mantener histórico
    ean=view_row.ean,
    ubicacion=location.codigo_ubicacion if location else view_row.ubicacion,
    # ...
)
```

---

### 2. 🟡 IMPORTANTE - Detalle de Orden

**Archivo:** `src/adapters/primary/api/order_router.py`

**Endpoint:** `GET /api/v1/orders/{order_id}`

**Cambio:**
```python
# Agregar eager loading de relaciones
order = db.query(Order).options(
    joinedload(Order.order_lines).joinedload(OrderLine.product_reference),
    joinedload(Order.order_lines).joinedload(OrderLine.product_location)
).filter(Order.id == order_id).first()

# Incluir en respuesta:
for line in order.order_lines:
    product_detail = {
        # Histórico (lo que se pidió originalmente)
        "nombre": line.descripcion_producto,
        "ubicacion": line.ubicacion,
        
        # Actual (info actualizada del catálogo)
        "producto_activo": line.product_reference.activo if line.product_reference else None,
        "stock_disponible": line.product_location.stock_actual if line.product_location else None,
        "ubicacion_actual": line.product_location.codigo_ubicacion if line.product_location else None
    }
```

---

### 3. 🟢 NUEVO - Optimizar Ruta de Picking

**Archivo:** `src/adapters/primary/api/order_router.py`

**Endpoint:** `POST /api/v1/orders/{order_id}/optimize-picking-route`

**Implementar:**
```python
@router.post("/{order_id}/optimize-picking-route")
def optimize_picking_route(order_id: int, db: Session = Depends(get_db)):
    """
    Optimiza la ruta de picking usando ubicaciones reales.
    
    Algoritmo:
    1. Agrupar líneas por pasillo
    2. Ordenar por prioridad + altura dentro de cada pasillo
    3. Generar secuencia optimizada
    """
    order = db.query(Order).options(
        joinedload(Order.order_lines).joinedload(OrderLine.product_location)
    ).filter(Order.id == order_id).first()
    
    # Agrupar por pasillo
    lines_by_aisle = {}
    for line in order.order_lines:
        if line.product_location:
            pasillo = line.product_location.pasillo
            if pasillo not in lines_by_aisle:
                lines_by_aisle[pasillo] = []
            lines_by_aisle[pasillo].append(line)
    
    # Generar ruta optimizada
    picking_route = []
    secuencia = 1
    
    for pasillo in sorted(lines_by_aisle.keys()):
        lines = sorted(
            lines_by_aisle[pasillo],
            key=lambda x: (x.product_location.prioridad, x.product_location.altura)
        )
        
        for line in lines:
            picking_route.append({
                "secuencia": secuencia,
                "producto": line.descripcion_producto,
                "cantidad": line.cantidad_solicitada,
                "ubicacion": line.product_location.codigo_ubicacion,
                "pasillo": pasillo,
                "prioridad": line.product_location.prioridad
            })
            secuencia += 1
    
    return {
        "order_id": order_id,
        "picking_route": picking_route,
        "total_stops": len(picking_route),
        "aisles": list(lines_by_aisle.keys())
    }
```

---

### 4. 🟢 NUEVO - Validar Stock

**Archivo:** `src/adapters/primary/api/order_router.py`

**Endpoint:** `GET /api/v1/orders/{order_id}/stock-validation`

**Implementar:**
```python
@router.get("/{order_id}/stock-validation")
def validate_order_stock(order_id: int, db: Session = Depends(get_db)):
    """
    Valida si hay stock suficiente para completar la orden.
    """
    order = db.query(Order).options(
        joinedload(Order.order_lines).joinedload(OrderLine.product_location)
    ).filter(Order.id == order_id).first()
    
    validation_results = []
    has_issues = False
    
    for line in order.order_lines:
        if line.product_location:
            stock_ok = line.product_location.stock_actual >= line.cantidad_solicitada
            
            validation_results.append({
                "order_line_id": line.id,
                "producto": line.descripcion_producto,
                "cantidad_solicitada": line.cantidad_solicitada,
                "stock_disponible": line.product_location.stock_actual,
                "stock_suficiente": stock_ok,
                "ubicacion": line.product_location.codigo_ubicacion
            })
            
            if not stock_ok:
                has_issues = True
        else:
            validation_results.append({
                "order_line_id": line.id,
                "producto": line.descripcion_producto,
                "warning": "No hay ubicación vinculada"
            })
            has_issues = True
    
    return {
        "order_id": order_id,
        "can_complete": not has_issues,
        "validation_results": validation_results
    }
```

---

### 5. 🟢 NUEVO - Migración de Datos

**Archivo:** `migrate_orders_to_products.py` (nuevo)

**Endpoint:** `POST /api/v1/admin/migrate-orders-to-products`

**Implementar:**
```python
@router.post("/admin/migrate-orders-to-products")
def migrate_historical_orders(db: Session = Depends(get_db)):
    """
    Vincula order_lines históricas con product_references.
    
    Matching por:
    1. EAN (más confiable)
    2. SKU/articulo
    3. Nombre + talla + color
    """
    unlinked_lines = db.query(OrderLine).filter(
        OrderLine.product_reference_id == None
    ).all()
    
    matched = 0
    unmatched = []
    
    for line in unlinked_lines:
        product = None
        
        # Match por EAN
        if line.ean:
            product = db.query(ProductReference).filter(
                ProductReference.ean == line.ean
            ).first()
        
        # Match por SKU
        if not product and line.articulo:
            product = db.query(ProductReference).filter(
                ProductReference.sku == line.articulo
            ).first()
        
        if product:
            line.product_reference_id = product.id
            
            # Buscar mejor ubicación
            location = db.query(ProductLocation).filter(
                ProductLocation.product_id == product.id,
                ProductLocation.activa == True
            ).order_by(
                ProductLocation.prioridad.asc()
            ).first()
            
            if location:
                line.product_location_id = location.id
            
            matched += 1
        else:
            unmatched.append({
                "line_id": line.id,
                "ean": line.ean,
                "articulo": line.articulo
            })
    
    db.commit()
    
    return {
        "total_processed": len(unlinked_lines),
        "matched": matched,
        "unmatched": len(unmatched),
        "success_rate": f"{(matched/len(unlinked_lines)*100):.1f}%",
        "unmatched_details": unmatched[:10]  # Primeros 10
    }
```

---

## 📁 Archivos a Modificar

### ORM (Schema)
- ✏️ `src/adapters/secondary/database/orm.py`
  - Agregar `product_reference_id` a `OrderLine`
  - Agregar `product_location_id` a `OrderLine`
  - Agregar relationships

### ETL
- ✏️ `etl_import_orders.py`
  - Modificar `_create_order_line_from_view()`
  - Vincular con productos al importar

### API
- ✏️ `src/adapters/primary/api/order_router.py`
  - Modificar `GET /orders/{id}` (agregar info actualizada)
  - Crear `POST /orders/{id}/optimize-picking-route`
  - Crear `GET /orders/{id}/stock-validation`
  - Crear `POST /admin/migrate-orders-to-products`

### Scripts
- 📄 `migrate_orders_to_products.py` (nuevo)
  - Script standalone para migración manual

---

## ⚡ Orden de Implementación

### 1️⃣ Base de Datos (30 min)
```sql
-- Agregar columnas
ALTER TABLE order_lines ADD COLUMN product_reference_id INT NULL;
ALTER TABLE order_lines ADD COLUMN product_location_id INT NULL;

-- Agregar FKs
ALTER TABLE order_lines ADD CONSTRAINT fk_order_lines_product_reference...
ALTER TABLE order_lines ADD CONSTRAINT fk_order_lines_product_location...

-- Índices
CREATE INDEX idx_order_lines_product_ref ON order_lines(product_reference_id);
CREATE INDEX idx_order_lines_product_loc ON order_lines(product_location_id);
```

### 2️⃣ ORM (15 min)
- Actualizar modelo `OrderLine` en `orm.py`
- Agregar relationships

### 3️⃣ Migración de Datos (1 hora)
- Crear script `migrate_orders_to_products.py`
- Ejecutar migración
- Validar resultados

### 4️⃣ ETL (45 min)
- Modificar `etl_import_orders.py`
- Probar con datos reales

### 5️⃣ Endpoints (2 horas)
- Modificar `GET /orders/{id}`
- Crear endpoint de optimización
- Crear endpoint de validación

---

## ✅ Validación Post-Implementación

```sql
-- 1. ¿Cuántas order_lines están vinculadas?
SELECT 
  COUNT(*) as total,
  COUNT(product_reference_id) as con_producto,
  COUNT(product_location_id) as con_ubicacion,
  ROUND(COUNT(product_reference_id) * 100.0 / COUNT(*), 1) as porcentaje_vinculado
FROM order_lines;

-- 2. ¿Qué órdenes NO están vinculadas?
SELECT ol.id, ol.ean, ol.articulo, ol.descripcion_producto
FROM order_lines ol
WHERE ol.product_reference_id IS NULL
LIMIT 20;

-- 3. ¿Hay diferencias entre histórico y actual?
SELECT 
  ol.id,
  ol.descripcion_producto as nombre_historico,
  pr.nombre_producto as nombre_actual,
  ol.ubicacion as ubicacion_historica,
  pl.codigo_ubicacion as ubicacion_actual
FROM order_lines ol
LEFT JOIN product_references pr ON ol.product_reference_id = pr.id
LEFT JOIN product_locations pl ON ol.product_location_id = pl.id
WHERE ol.descripcion_producto != pr.nombre_producto
   OR ol.ubicacion != pl.codigo_ubicacion
LIMIT 20;
```

---

## 📊 Impacto Esperado

### Performance
- ⬆️ Optimización de rutas: **20-30% más eficiente**
- ⬇️ Tiempo de picking por orden: **reducción de 2-3 minutos**
- ✅ Validación de stock en tiempo real

### Datos
- ✅ Eliminación de duplicación
- ✅ Info de productos siempre actualizada
- ✅ Trazabilidad de cambios (histórico vs actual)

### Operaciones
- ✅ Alertas de stock insuficiente
- ✅ Sugerencia de ubicaciones alternativas
- ✅ Detección de productos descatalogados

---

## ⚠️ Riesgos y Mitigación

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Migración falla | Baja | Alto | Backup completo + rollback plan |
| Performance degradado | Media | Medio | Índices optimizados + monitoring |
| Productos no matchean | Alta | Bajo | Vincular manualmente + alertas |
| Breaking changes en API | Baja | Alto | Cambios son aditivos (no breaking) |

---

## 📅 Timeline Estimado

- **Desarrollo:** 1-2 días
- **Testing:** 1 día
- **Migración de datos:** 2-4 horas
- **Deploy:** 1 hora
- **Validación post-deploy:** 2 horas

**Total:** ~3-4 días

---

**Estado:** ✅ Listo para Implementar  
**Prioridad:** 🔴 Alta  
**Complejidad:** Media  
**ROI:** Alto (optimización de picking + validación de stock)
