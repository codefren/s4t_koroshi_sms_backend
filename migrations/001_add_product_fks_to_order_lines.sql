-- =====================================================
-- MIGRACIÓN: Agregar FKs de productos a order_lines
-- Fecha: 2026-01-07
-- Descripción: Normalización de órdenes con productos
-- =====================================================

-- Paso 1: Agregar columnas (nullable para compatibilidad)
ALTER TABLE order_lines
ADD product_reference_id INT NULL;

ALTER TABLE order_lines
ADD product_location_id INT NULL;

-- Paso 2: Crear índices para performance
CREATE INDEX idx_order_lines_product_ref 
ON order_lines(product_reference_id);

CREATE INDEX idx_order_lines_product_loc 
ON order_lines(product_location_id);

-- Paso 3: Agregar Foreign Keys (con NO ACTION para evitar cascadas múltiples)
ALTER TABLE order_lines
ADD CONSTRAINT fk_order_lines_product_reference 
FOREIGN KEY (product_reference_id) 
REFERENCES product_references(id)
ON DELETE NO ACTION;

ALTER TABLE order_lines
ADD CONSTRAINT fk_order_lines_product_location 
FOREIGN KEY (product_location_id) 
REFERENCES product_locations(id)
ON DELETE NO ACTION;

-- Verificar que se crearon correctamente
SELECT 
    COLUMN_NAME, 
    DATA_TYPE, 
    IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'order_lines'
  AND COLUMN_NAME IN ('product_reference_id', 'product_location_id');

PRINT '✅ Migración completada: FKs agregadas a order_lines';
