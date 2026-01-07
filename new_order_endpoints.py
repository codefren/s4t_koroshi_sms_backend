"""
Nuevos endpoints para optimización de rutas de picking y validación de stock.
AGREGAR AL FINAL de src/adapters/primary/api/order_router.py
"""

@router.post("/{order_id}/optimize-picking-route")
def optimize_picking_route(
    order_id: int,
    db: Session = Depends(get_db)
):
    """
    Optimiza la ruta de picking para una orden usando ubicaciones reales.
    
    **Algoritmo:**
    1. Agrupa líneas por pasillo
    2. Ordena por prioridad + altura dentro de cada pasillo
    3. Genera secuencia optimizada
    
    **Retorna:**
    - Ruta optimizada con secuencia de recogida
    - Pasillos a visitar
    - Tiempo estimado
    
    **Requiere:**
    - Líneas de orden vinculadas con product_locations
    """
    # Cargar orden con ubicaciones
    order = db.query(Order).options(
        joinedload(Order.order_lines).joinedload(OrderLine.product_location)
    ).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(
            status_code=404,
            detail=f"Orden con ID {order_id} no encontrada"
        )
    
    # Verificar que haya líneas
    if not order.order_lines:
        raise HTTPException(
            status_code=400,
            detail="La orden no tiene líneas de productos"
        )
    
    # Agrupar por pasillo
    lines_by_aisle: Dict[str, List[OrderLine]] = {}
    lines_without_location = []
    
    for line in order.order_lines:
        if line.product_location and line.product_location.activa:
            pasillo = line.product_location.pasillo
            if pasillo not in lines_by_aisle:
                lines_by_aisle[pasillo] = []
            lines_by_aisle[pasillo].append(line)
        else:
            lines_without_location.append({
                "line_id": line.id,
                "producto": line.descripcion_producto,
                "ubicacion_historica": line.ubicacion
            })
    
    # Generar ruta optimizada
    picking_route = []
    secuencia = 1
    
    # Ordenar pasillos alfabéticamente
    for pasillo in sorted(lines_by_aisle.keys()):
        lines = lines_by_aisle[pasillo]
        
        # Ordenar dentro del pasillo por:
        # 1. Prioridad (ascendente: 1 = alta prioridad primero)
        # 2. Altura (ascendente: niveles bajos primero)
        sorted_lines = sorted(
            lines,
            key=lambda x: (x.product_location.prioridad, x.product_location.altura)
        )
        
        for line in sorted_lines:
            loc = line.product_location
            picking_route.append({
                "secuencia": secuencia,
                "order_line_id": line.id,
                "producto": line.descripcion_producto,
                "cantidad": line.cantidad_solicitada,
                "ubicacion": loc.codigo_ubicacion,
                "pasillo": loc.pasillo,
                "lado": loc.lado,
                "altura": loc.altura,
                "prioridad": loc.prioridad,
                "stock_disponible": loc.stock_actual
            })
            secuencia += 1
    
    # Calcular tiempo estimado (1.5 min por item)
    tiempo_estimado = len(picking_route) * 1.5
    
    return {
        "order_id": order_id,
        "numero_orden": order.numero_orden,
        "total_stops": len(picking_route),
        "aisles_to_visit": sorted(lines_by_aisle.keys()),
        "estimated_time_minutes": round(tiempo_estimado, 1),
        "picking_route": picking_route,
        "warnings": {
            "lines_without_location": len(lines_without_location),
            "details": lines_without_location if lines_without_location else []
        }
    }


@router.get("/{order_id}/stock-validation")
def validate_order_stock(
    order_id: int,
    db: Session = Depends(get_db)
):
    """
    Valida si hay stock suficiente para completar la orden.
    
    **Verifica:**
    - Stock disponible vs cantidad solicitada
    - Ubicaciones activas
    - Productos vinculados al catálogo
    
    **Retorna:**
    - can_complete: bool (si se puede completar la orden)
    - validation_results: detalle por línea
    - summary: resumen de problemas encontrados
    """
    # Cargar orden con ubicaciones
    order = db.query(Order).options(
        joinedload(Order.order_lines).joinedload(OrderLine.product_location),
        joinedload(Order.order_lines).joinedload(OrderLine.product_reference)
    ).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(
            status_code=404,
            detail=f"Orden con ID {order_id} no encontrada"
        )
    
    validation_results = []
    has_issues = False
    issues_count = {
        "insufficient_stock": 0,
        "no_location": 0,
        "inactive_product": 0,
        "inactive_location": 0
    }
    
    for line in order.order_lines:
        result: Dict[str, Any] = {
            "order_line_id": line.id,
            "producto": line.descripcion_producto,
            "cantidad_solicitada": line.cantidad_solicitada,
            "issues": []
        }
        
        # Verificar si tiene ubicación vinculada
        if not line.product_location:
            result["issues"].append({
                "type": "no_location",
                "message": "No hay ubicación vinculada",
                "severity": "warning"
            })
            result["stock_disponible"] = None
            result["ubicacion"] = line.ubicacion  # histórica
            has_issues = True
            issues_count["no_location"] += 1
        else:
            loc = line.product_location
            result["stock_disponible"] = loc.stock_actual
            result["ubicacion"] = loc.codigo_ubicacion
            
            # Verificar stock suficiente
            if loc.stock_actual < line.cantidad_solicitada:
                result["issues"].append({
                    "type": "insufficient_stock",
                    "message": f"Stock insuficiente: {loc.stock_actual} disponible, {line.cantidad_solicitada} solicitado",
                    "severity": "error"
                })
                has_issues = True
                issues_count["insufficient_stock"] += 1
            
            # Verificar ubicación activa
            if not loc.activa:
                result["issues"].append({
                    "type": "inactive_location",
                    "message": "La ubicación está inactiva",
                    "severity": "warning"
                })
                has_issues = True
                issues_count["inactive_location"] += 1
        
        # Verificar si el producto está activo
        if line.product_reference and not line.product_reference.activo:
            result["issues"].append({
                "type": "inactive_product",
                "message": "El producto está inactivo en el catálogo",
                "severity": "warning"
            })
            has_issues = True
            issues_count["inactive_product"] += 1
        
        result["can_pick"] = len(result["issues"]) == 0
        validation_results.append(result)
    
    return {
        "order_id": order_id,
        "numero_orden": order.numero_orden,
        "can_complete": not has_issues,
        "total_lines": len(order.order_lines),
        "lines_with_issues": sum(1 for r in validation_results if not r["can_pick"]),
        "summary": {
            "insufficient_stock": issues_count["insufficient_stock"],
            "no_location": issues_count["no_location"],
            "inactive_product": issues_count["inactive_product"],
            "inactive_location": issues_count["inactive_location"]
        },
        "validation_results": validation_results
    }
