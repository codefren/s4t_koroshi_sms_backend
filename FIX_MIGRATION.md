# 🔧 SOLUCIÓN: Error de Columnas Faltantes

## ❌ Problema

```
Invalid column name 'product_reference_id'
Invalid column name 'product_location_id'
```

**Causa:** Las columnas fueron agregadas al modelo ORM pero **NO se ejecutó la migración SQL** en la base de datos.

---

## ✅ Solución Rápida (3 minutos)

### Paso 1: Ejecutar Migración

```bash
python run_migration.py
```

Esto creará las columnas en SQL Server:
- `product_reference_id` (INT NULL)
- `product_location_id` (INT NULL)
- Índices para performance
- Foreign keys

### Paso 2: Reiniciar API

```bash
# Detener API (Ctrl+C)

# Reiniciar
uvicorn src.main:app --reload
```

### Paso 3: Verificar

```bash
# Probar endpoint
curl http://localhost:8000/api/v1/orders/11

# Debería funcionar ahora ✅
```

---

## 📋 Alternativa: Ejecutar SQL Manualmente

Si prefieres ejecutar el SQL directamente en SQL Server:

```sql
-- 1. Agregar columnas
ALTER TABLE order_lines
ADD product_reference_id INT NULL;

ALTER TABLE order_lines
ADD product_location_id INT NULL;

-- 2. Crear índices
CREATE INDEX idx_order_lines_product_ref 
ON order_lines(product_reference_id);

CREATE INDEX idx_order_lines_product_loc 
ON order_lines(product_location_id);

-- 3. Agregar Foreign Keys
ALTER TABLE order_lines
ADD CONSTRAINT fk_order_lines_product_reference 
FOREIGN KEY (product_reference_id) 
REFERENCES product_references(id)
ON DELETE SET NULL;

ALTER TABLE order_lines
ADD CONSTRAINT fk_order_lines_product_location 
FOREIGN KEY (product_location_id) 
REFERENCES product_locations(id)
ON DELETE SET NULL;
```

---

## 🔍 Verificar que Funcionó

```bash
# Verificar columnas existen
python run_migration.py --verify-only

# Debería mostrar:
# ✅ Verificación exitosa - Columnas encontradas:
#    - product_reference_id (int, nullable=YES)
#    - product_location_id (int, nullable=YES)
```

---

## ⚡ Flujo Completo

```bash
# 1. Migrar BD
python run_migration.py

# 2. Reiniciar API
uvicorn src.main:app --reload

# 3. (Opcional) Vincular datos históricos
python migrate_orders_to_products.py

# 4. Probar
curl http://localhost:8000/api/v1/orders/11
curl -X POST http://localhost:8000/api/v1/orders/11/optimize-picking-route
```

---

## 📊 Qué Hace la Migración

| Antes | Después |
|-------|---------|
| `order_lines` sin FKs | `order_lines` con `product_reference_id` y `product_location_id` |
| Endpoints fallan | Endpoints funcionan ✅ |
| Sin vinculación | Datos vinculados automáticamente |

---

## ⚠️ Notas Importantes

1. **Las columnas son NULL:** Compatible con datos históricos
2. **No hay data loss:** Solo se agregan columnas nuevas
3. **Rollback automático:** Si hay error, no se modifica nada
4. **Backup recomendado:** Siempre buena práctica antes de migrar

---

## 🐛 Si Aún Hay Problemas

### Problema: "Permission denied"

**Solución:** Asegúrate que el usuario de BD tenga permisos:

```sql
GRANT ALTER ON SCHEMA::dbo TO tu_usuario;
```

### Problema: "Table product_references not found"

**Solución:** Primero ejecuta:

```bash
python init_product_system.py
```

### Problema: "API sigue fallando"

**Solución:** 

1. Verificar migración: `python run_migration.py --verify-only`
2. Revisar que API se reinició
3. Verificar conexión: `python check_db.py`

---

## ✅ Estado Final Esperado

Después de migrar, todos estos endpoints deben funcionar:

- ✅ `GET /api/v1/orders` → Lista órdenes
- ✅ `GET /api/v1/orders/{id}` → Detalle de orden
- ✅ `POST /api/v1/orders/{id}/optimize-picking-route` → Optimizar ruta
- ✅ `GET /api/v1/orders/{id}/stock-validation` → Validar stock

---

**Tiempo estimado:** 3-5 minutos  
**Dificultad:** Fácil  
**Riesgo:** Bajo (columnas nullable, rollback automático)
