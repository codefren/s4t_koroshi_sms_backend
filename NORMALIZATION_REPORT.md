# 📊 Informe de Normalización - Orders y Products

Análisis y estrategia para normalizar los datos de órdenes con los nuevos modelos de productos y ubicaciones.

---

## 🔍 Situación Actual

### Problema Identificado

Los datos de productos están **duplicados** en dos sistemas:

#### Sistema 1: Órdenes (Desnormalizado)
**Tabla:** `order_lines`

```sql
- ean (código de barras)
- ubicacion (texto libre: "A-12-3")
- articulo (SKU)
- color ("Rojo", "Azul")
- talla ("M", "XL")
- descripcion_producto ("Camisa Polo...")
- descripcion_color ("Rojo Vino")
- temporada ("Verano 2024")
```

#### Sistema 2: Productos (Normalizado) ✅
**Tablas:** `product_references` + `product_locations`

```sql
-- product_references
- referencia (código único)
- sku
- nombre_producto
- color_id
- talla
- descripcion_color
- ean
- temporada
- activo

-- product_locations
- product_id (FK)
- pasillo
- lado (IZQUIERDA/DERECHA)
- ubicacion
- altura
- stock_actual
- stock_minimo
- prioridad (para picking)
- activa
```

---

## ❌ Problemas Actuales

### 1. **Duplicación de Datos**
- Los mismos productos se describen de forma diferente en órdenes y catálogo
- Cambios en el catálogo NO se reflejan en órdenes existentes

### 2. **Ubicaciones Obsoletas**
- `order_lines.ubicacion` es texto libre sin validación
- NO hay referencia a la ubicación real del almacén
- Si un producto cambia de ubicación, las órdenes antiguas tienen ubicación incorrecta

### 3. **Sin Optimización de Picking**
- NO se puede calcular la mejor ruta de picking
- NO se usa el campo `prioridad` de `product_locations`
- NO se puede validar si hay stock en la ubicación

### 4. **Inconsistencias**
- Puede haber órdenes con productos que YA NO EXISTEN en el catálogo
- NO hay forma de saber si el producto de una orden sigue activo

---

## ✅ Propuesta de Normalización

### Estrategia: **Híbrida (Normalización + Histórico)**

**Mantener datos desnormalizados** para auditoría e historial, pero **agregar referencias** a los modelos normalizados para operaciones actuales.

### Cambios en `order_lines`

```sql
ALTER TABLE order_lines ADD COLUMN:

-- Nuevas relaciones (NULLABLE para compatibilidad con datos históricos)
product_reference_id INT NULL REFERENCES product_references(id)
product_location_id INT NULL REFERENCES product_locations(id)

-- Mantener campos existentes para histórico
-- (ean, articulo, descripcion_producto, etc.) ✅ SE MANTIENEN
```

**Ventajas:**
- ✅ Órdenes históricas NO se rompen
- ✅ Nuevas órdenes usan el catálogo normalizado
- ✅ Se puede comparar datos históricos vs actuales
- ✅ Se puede optimizar picking con ubicaciones reales

---

## 📋 Plan de Migración

### Fase 1: Modificar Schema (Sin Breaking Changes)

#### 1.1 Agregar Columnas a `order_lines`

```sql
-- Agregar FK a ProductReference (nullable)
ALTER TABLE order_lines 
ADD COLUMN product_reference_id INT NULL;

ALTER TABLE order_lines 
ADD CONSTRAINT fk_order_lines_product_reference 
FOREIGN KEY (product_reference_id) 
REFERENCES product_references(id) 
ON DELETE SET NULL;

-- Agregar FK a ProductLocation (nullable)
ALTER TABLE order_lines 
ADD COLUMN product_location_id INT NULL;

ALTER TABLE order_lines 
ADD CONSTRAINT fk_order_lines_product_location 
FOREIGN KEY (product_location_id) 
REFERENCES product_locations(id) 
ON DELETE SET NULL;

-- Índices para performance
CREATE INDEX idx_order_lines_product_ref 
ON order_lines(product_reference_id);

CREATE INDEX idx_order_lines_product_loc 
ON order_lines(product_location_id);
```

#### 1.2 Actualizar Modelo ORM

```python
class OrderLine(Base):
    # ... campos existentes ...
    
    # === NUEVAS RELACIONES (Normalización) ===
    # Referencia al producto en el catálogo normalizado
    # NULL para órdenes históricas importadas antes de la normalización
    product_reference_id = Column(
        Integer, 
        ForeignKey("product_references.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )
    
    # Referencia a la ubicación específica del producto
    # NULL para órdenes históricas
    product_location_id = Column(
        Integer, 
        ForeignKey("product_locations.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )
    
    # Relationships
    product_reference = relationship("ProductReference", backref="order_lines")
    product_location = relationship("ProductLocation", backref="order_lines")
```

---

### Fase 2: Migrar Datos Existentes

#### 2.1 Script de Migración - Matching por EAN/SKU

**Archivo:** `migrate_orders_to_products.py`

```python
"""
Script para vincular order_lines existentes con product_references.

Estrategia:
1. Match por EAN (más confiable)
2. Si no hay match, intentar por SKU (articulo)
3. Registrar líneas que NO hacen match
"""

def migrate_order_lines_to_products(db: Session):
    """Vincula order_lines con product_references."""
    
    # Obtener todas las order_lines sin vincular
    unlinked_lines = db.query(OrderLine).filter(
        OrderLine.product_reference_id == None
    ).all()
    
    matched = 0
    unmatched = []
    
    for line in unlinked_lines:
        product = None
        
        # Estrategia 1: Match por EAN
        if line.ean:
            product = db.query(ProductReference).filter(
                ProductReference.ean == line.ean
            ).first()
        
        # Estrategia 2: Match por SKU
        if not product and line.articulo:
            product = db.query(ProductReference).filter(
                ProductReference.sku == line.articulo
            ).first()
        
        # Estrategia 3: Match por nombre + color + talla (menos confiable)
        if not product and line.descripcion_producto:
            product = db.query(ProductReference).filter(
                ProductReference.nombre_producto.like(f"%{line.descripcion_producto}%"),
                ProductReference.talla == line.talla,
                ProductReference.descripcion_color.like(f"%{line.color}%")
            ).first()
        
        if product:
            line.product_reference_id = product.id
            
            # Buscar mejor ubicación para este producto
            location = db.query(ProductLocation).filter(
                ProductLocation.product_id == product.id,
                ProductLocation.activa == True
            ).order_by(
                ProductLocation.prioridad.asc(),
                ProductLocation.stock_actual.desc()
            ).first()
            
            if location:
                line.product_location_id = location.id
            
            matched += 1
        else:
            unmatched.append({
                "order_line_id": line.id,
                "ean": line.ean,
                "articulo": line.articulo,
                "descripcion": line.descripcion_producto
            })
    
    db.commit()
    
    return {
        "total_lines": len(unlinked_lines),
        "matched": matched,
        "unmatched": len(unmatched),
        "unmatched_details": unmatched
    }
```

---

### Fase 3: Modificar Endpoints

#### 3.1 ETL de Importación (`etl_import_orders.py`)

**CAMBIO CRÍTICO:** Al importar nuevas órdenes desde la VIEW, vincular automáticamente con productos.

```python
def _create_order_line_from_view(view_row, order_id, db):
    """Crea OrderLine vinculándola con ProductReference si existe."""
    
    # Buscar producto en catálogo por EAN o SKU
    product = None
    if view_row.ean:
        product = db.query(ProductReference).filter(
            ProductReference.ean == view_row.ean
        ).first()
    
    if not product and view_row.articulo:
        product = db.query(ProductReference).filter(
            ProductReference.sku == view_row.articulo
        ).first()
    
    # Buscar ubicación del producto (prioridad + stock)
    location = None
    if product:
        location = db.query(ProductLocation).filter(
            ProductLocation.product_id == product.id,
            ProductLocation.activa == True
        ).order_by(
            ProductLocation.prioridad.asc(),
            ProductLocation.stock_actual.desc()
        ).first()
    
    # Crear OrderLine con referencias Y datos desnormalizados
    order_line = OrderLine(
        order_id=order_id,
        
        # === REFERENCIAS NORMALIZADAS ===
        product_reference_id=product.id if product else None,
        product_location_id=location.id if location else None,
        
        # === DATOS DESNORMALIZADOS (histórico) ===
        ean=view_row.ean,
        ubicacion=location.codigo_ubicacion if location else view_row.ubicacion,
        articulo=view_row.articulo,
        color=view_row.color,
        talla=view_row.talla,
        descripcion_producto=view_row.descripcion_producto,
        descripcion_color=view_row.descripcion_color,
        temporada=view_row.temporada,
        cantidad_solicitada=view_row.cantidad
    )
    
    return order_line
```

---

#### 3.2 Endpoint de Detalle de Orden (`order_router.py`)

**Modificar** `GET /api/v1/orders/{order_id}` para incluir info actualizada del producto:

```python
@router.get("/{order_id}", response_model=OrderDetailFull)
def get_order_detail(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).options(
        joinedload(Order.order_lines).joinedload(OrderLine.product_reference),
        joinedload(Order.order_lines).joinedload(OrderLine.product_location)
    ).filter(Order.id == order_id).first()
    
    # ...
    
    products = []
    for line in order.order_lines:
        product_data = {
            # Datos históricos (desnormalizados)
            "nombre": line.descripcion_producto,
            "color": line.descripcion_color,
            "talla": line.talla,
            "ubicacion": line.ubicacion,
            "ean": line.ean,
            "sku": line.articulo,
            
            # Datos actuales (si existe referencia)
            "producto_actual": None,
            "ubicacion_actual": None,
            "stock_disponible": None
        }
        
        # Si hay referencia al producto, agregar info actualizada
        if line.product_reference:
            product_data["producto_actual"] = {
                "id": line.product_reference.id,
                "nombre": line.product_reference.nombre_producto,
                "activo": line.product_reference.activo,
                "cambio_detectado": line.descripcion_producto != line.product_reference.nombre_producto
            }
        
        # Si hay referencia a ubicación, agregar info actualizada
        if line.product_location:
            product_data["ubicacion_actual"] = {
                "id": line.product_location.id,
                "codigo": line.product_location.codigo_ubicacion,
                "stock_actual": line.product_location.stock_actual,
                "prioridad": line.product_location.prioridad,
                "cambio_detectado": line.ubicacion != line.product_location.codigo_ubicacion
            }
            product_data["stock_disponible"] = line.product_location.stock_actual
        
        products.append(product_data)
```

---

#### 3.3 NUEVO Endpoint: Optimizar Ruta de Picking

```python
@router.post("/{order_id}/optimize-picking-route")
def optimize_picking_route(order_id: int, db: Session = Depends(get_db)):
    """
    Optimiza la ruta de picking para una orden.
    
    Usa las ubicaciones reales (product_locations) para:
    1. Agrupar por pasillo
    2. Ordenar por prioridad
    3. Minimizar distancia recorrida
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
    
    # Ordenar dentro de cada pasillo por prioridad y altura
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
                "order_line_id": line.id,
                "producto": line.descripcion_producto,
                "cantidad": line.cantidad_solicitada,
                "ubicacion": line.product_location.codigo_ubicacion,
                "pasillo": line.product_location.pasillo,
                "lado": line.product_location.lado,
                "altura": line.product_location.altura,
                "prioridad": line.product_location.prioridad
            })
            secuencia += 1
    
    return {
        "order_id": order_id,
        "total_stops": len(picking_route),
        "aisles_to_visit": list(lines_by_aisle.keys()),
        "picking_route": picking_route,
        "estimated_time_minutes": len(picking_route) * 1.5  # 1.5 min por item
    }
```

---

## 📊 Comparativa: Antes vs Después

### ANTES (Desnormalizado)

```json
{
  "order_line": {
    "id": 123,
    "descripcion_producto": "Camisa Polo Roja",
    "ubicacion": "A-12-3",
    "cantidad": 5,
    "ean": "8445962763983"
  }
}
```

**Problemas:**
- ❌ Si el producto cambia de ubicación → dato obsoleto
- ❌ No se puede optimizar ruta de picking
- ❌ No se valida stock disponible
- ❌ Ubicación es texto libre (sin validación)

---

### DESPUÉS (Normalizado + Histórico)

```json
{
  "order_line": {
    "id": 123,
    
    // Datos históricos (lo que se pidió originalmente)
    "descripcion_producto": "Camisa Polo Roja",
    "ubicacion": "A-12-3",
    "cantidad": 5,
    "ean": "8445962763983",
    
    // Referencias a catálogo normalizado
    "product_reference_id": 1,
    "product_location_id": 5,
    
    // Info actualizada del producto
    "producto_actual": {
      "id": 1,
      "nombre": "Camisa Polo Manga Corta",
      "activo": true,
      "cambio_detectado": true  // Nombre cambió
    },
    
    // Info actualizada de ubicación
    "ubicacion_actual": {
      "codigo": "A-12, Izq, A2-12",
      "stock_actual": 45,
      "prioridad": 1,
      "cambio_detectado": false  // Ubicación NO cambió
    },
    
    "stock_disponible": 45
  }
}
```

**Ventajas:**
- ✅ Mantiene histórico original
- ✅ Muestra info actualizada del producto
- ✅ Detecta cambios (nombre, ubicación, etc.)
- ✅ Valida stock disponible en tiempo real
- ✅ Permite optimizar rutas de picking

---

## 🔄 Endpoints a Modificar/Crear

### Modificar (Breaking Changes Mínimos)

| Endpoint | Cambio | Prioridad |
|----------|--------|-----------|
| `POST /api/v1/etl/import-orders` | Vincular con productos al importar | 🔴 Alta |
| `GET /api/v1/orders/{id}` | Agregar info actualizada de productos | 🟡 Media |
| `GET /api/v1/orders` | Opcional: filtrar por producto | 🟢 Baja |

### Crear (Nuevos)

| Endpoint | Descripción | Prioridad |
|----------|-------------|-----------|
| `POST /api/v1/orders/{id}/optimize-picking-route` | Optimizar ruta de picking | 🔴 Alta |
| `POST /api/v1/orders/migrate-to-products` | Migrar órdenes históricas | 🟡 Media |
| `GET /api/v1/orders/{id}/stock-validation` | Validar stock disponible | 🟢 Baja |

---

## ⚠️ Consideraciones Importantes

### 1. **Compatibilidad con Histórico**
- ✅ Las columnas FK son NULLABLE
- ✅ Órdenes antiguas siguen funcionando
- ✅ Se puede comparar histórico vs actual

### 2. **Performance**
- ✅ Agregar índices en FKs nuevas
- ✅ Usar `joinedload` para evitar N+1 queries
- ⚠️ Migración de datos puede tardar (hacer en horario no pico)

### 3. **Validación de Stock**
- ⚠️ ¿Qué pasa si `stock_actual` < `cantidad_solicitada`?
- Opciones:
  - Alertar al operario
  - Sugerir ubicación alternativa
  - Permitir picking parcial

### 4. **Productos Descatalogados**
- ⚠️ ¿Qué pasa si `product_reference.activo = false`?
- Opciones:
  - Permitir orden (usar datos históricos)
  - Alertar al supervisor
  - Cancelar línea automáticamente

---

## 📅 Roadmap de Implementación

### Semana 1: Schema y Migración
- [ ] Agregar columnas FK a `order_lines`
- [ ] Actualizar modelo ORM
- [ ] Crear script de migración
- [ ] Ejecutar migración en DEV
- [ ] Validar integridad de datos

### Semana 2: Modificar ETL
- [ ] Actualizar `etl_import_orders.py`
- [ ] Vincular automáticamente con productos
- [ ] Probar importación con datos reales
- [ ] Validar que órdenes nuevas tienen FK

### Semana 3: Endpoints
- [ ] Modificar `GET /orders/{id}` (agregar info actualizada)
- [ ] Crear `POST /orders/{id}/optimize-picking-route`
- [ ] Crear endpoint de validación de stock
- [ ] Documentar cambios en API

### Semana 4: Testing y Producción
- [ ] Tests unitarios e integración
- [ ] Validar en staging
- [ ] Ejecutar migración en PROD
- [ ] Monitorear performance

---

## ✅ Checklist Pre-Migración

- [ ] **Backup completo** de la base de datos
- [ ] **Validar** que todos los productos están en `product_references`
- [ ] **Validar** que todas las ubicaciones están en `product_locations`
- [ ] **Probar** script de migración en copia de PROD
- [ ] **Documentar** proceso de rollback
- [ ] **Notificar** a usuarios de cambios en API
- [ ] **Preparar** queries de validación post-migración

---

## 📈 Métricas de Éxito

1. **% de órdenes vinculadas:** > 95% de `order_lines` con `product_reference_id`
2. **% de ubicaciones actualizadas:** > 90% con `product_location_id`
3. **Performance:** Tiempos de respuesta < 200ms en `GET /orders/{id}`
4. **Optimización:** Rutas de picking 20-30% más eficientes

---

**Fecha del informe:** 2026-01-07  
**Estado:** Propuesta Pendiente de Aprobación  
**Impacto:** Alto - Requiere Migración de Datos
