-- =====================================================
-- MIGRACIÓN: Normalización completa de order_lines
-- Fecha: 2026-01-07
-- Descripción: Elimina campos redundantes de order_lines
--              y agrega campos faltantes a product_references
-- =====================================================

-- ============================================================================
-- PARTE 1: Agregar campos faltantes a product_references
-- ============================================================================

-- Agregar campo 'color' (nombre corto del color)
IF NOT EXISTS (
    SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'product_references' AND COLUMN_NAME = 'color'
)
BEGIN
    ALTER TABLE product_references
    ADD color VARCHAR(100) NULL;
    PRINT '✅ Columna color agregada a product_references';
END
ELSE
BEGIN
    PRINT '⏭️  Columna color ya existe en product_references';
END
GO

-- Agregar campo 'posicion_talla' (para ordenamiento)
IF NOT EXISTS (
    SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'product_references' AND COLUMN_NAME = 'posicion_talla'
)
BEGIN
    ALTER TABLE product_references
    ADD posicion_talla VARCHAR(50) NULL;
    PRINT '✅ Columna posicion_talla agregada a product_references';
END
ELSE
BEGIN
    PRINT '⏭️  Columna posicion_talla ya existe en product_references';
END
GO

-- ============================================================================
-- PARTE 2: Copiar datos de order_lines a product_references (si es necesario)
-- ============================================================================

-- Actualizar product_references con datos de order_lines cuando están vacíos
UPDATE pr
SET 
    pr.color = COALESCE(pr.color, ol.color),
    pr.posicion_talla = COALESCE(pr.posicion_talla, ol.posicion_talla)
FROM product_references pr
INNER JOIN order_lines ol ON pr.id = ol.product_reference_id
WHERE pr.color IS NULL OR pr.posicion_talla IS NULL;

PRINT '✅ Datos copiados de order_lines a product_references';
GO

-- ============================================================================
-- PARTE 3: Eliminar columnas redundantes de order_lines
-- ============================================================================

-- Eliminar columna 'ubicacion'
IF EXISTS (
    SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'order_lines' AND COLUMN_NAME = 'ubicacion'
)
BEGIN
    ALTER TABLE order_lines DROP COLUMN ubicacion;
    PRINT '✅ Columna ubicacion eliminada de order_lines';
END
ELSE
BEGIN
    PRINT '⏭️  Columna ubicacion ya no existe en order_lines';
END
GO

-- Eliminar columna 'articulo'
IF EXISTS (
    SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'order_lines' AND COLUMN_NAME = 'articulo'
)
BEGIN
    ALTER TABLE order_lines DROP COLUMN articulo;
    PRINT '✅ Columna articulo eliminada de order_lines';
END
ELSE
BEGIN
    PRINT '⏭️  Columna articulo ya no existe en order_lines';
END
GO

-- Eliminar columna 'color'
IF EXISTS (
    SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'order_lines' AND COLUMN_NAME = 'color'
)
BEGIN
    ALTER TABLE order_lines DROP COLUMN color;
    PRINT '✅ Columna color eliminada de order_lines';
END
ELSE
BEGIN
    PRINT '⏭️  Columna color ya no existe en order_lines';
END
GO

-- Eliminar columna 'talla'
IF EXISTS (
    SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'order_lines' AND COLUMN_NAME = 'talla'
)
BEGIN
    ALTER TABLE order_lines DROP COLUMN talla;
    PRINT '✅ Columna talla eliminada de order_lines';
END
ELSE
BEGIN
    PRINT '⏭️  Columna talla ya no existe en order_lines';
END
GO

-- Eliminar columna 'posicion_talla'
IF EXISTS (
    SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'order_lines' AND COLUMN_NAME = 'posicion_talla'
)
BEGIN
    ALTER TABLE order_lines DROP COLUMN posicion_talla;
    PRINT '✅ Columna posicion_talla eliminada de order_lines';
END
ELSE
BEGIN
    PRINT '⏭️  Columna posicion_talla ya no existe en order_lines';
END
GO

-- Eliminar columna 'descripcion_producto'
IF EXISTS (
    SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'order_lines' AND COLUMN_NAME = 'descripcion_producto'
)
BEGIN
    ALTER TABLE order_lines DROP COLUMN descripcion_producto;
    PRINT '✅ Columna descripcion_producto eliminada de order_lines';
END
ELSE
BEGIN
    PRINT '⏭️  Columna descripcion_producto ya no existe en order_lines';
END
GO

-- Eliminar columna 'descripcion_color'
IF EXISTS (
    SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'order_lines' AND COLUMN_NAME = 'descripcion_color'
)
BEGIN
    ALTER TABLE order_lines DROP COLUMN descripcion_color;
    PRINT '✅ Columna descripcion_color eliminada de order_lines';
END
ELSE
BEGIN
    PRINT '⏭️  Columna descripcion_color ya no existe en order_lines';
END
GO

-- Eliminar columna 'temporada'
IF EXISTS (
    SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'order_lines' AND COLUMN_NAME = 'temporada'
)
BEGIN
    ALTER TABLE order_lines DROP COLUMN temporada;
    PRINT '✅ Columna temporada eliminada de order_lines';
END
ELSE
BEGIN
    PRINT '⏭️  Columna temporada ya no existe en order_lines';
END
GO

-- ============================================================================
-- VERIFICACIÓN FINAL
-- ============================================================================

PRINT '';
PRINT '========================================================';
PRINT '📊 VERIFICACIÓN DE MIGRACIÓN';
PRINT '========================================================';

-- Verificar product_references
PRINT '';
PRINT '✅ Columnas en product_references:';
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'product_references'
  AND COLUMN_NAME IN ('color', 'posicion_talla')
ORDER BY COLUMN_NAME;

-- Verificar order_lines
PRINT '';
PRINT '✅ Columnas restantes en order_lines:';
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'order_lines'
  AND COLUMN_NAME NOT IN ('id', 'order_id', 'created_at', 'updated_at')
ORDER BY COLUMN_NAME;

PRINT '';
PRINT '========================================================';
PRINT '✅ MIGRACIÓN COMPLETADA';
PRINT '========================================================';
PRINT '';
PRINT 'Cambios aplicados:';
PRINT '  ✅ product_references: +2 columnas (color, posicion_talla)';
PRINT '  ✅ order_lines: -8 columnas (normalizadas)';
PRINT '';
PRINT 'Próximos pasos:';
PRINT '  1. Reiniciar API: uvicorn src.main:app --reload';
PRINT '  2. Recrear órdenes: python recreate_orders_with_products.py';
PRINT '  3. Probar endpoints: http://localhost:8000/docs';
PRINT '';
GO
