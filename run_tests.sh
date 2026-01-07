#!/bin/bash

# Script para ejecutar tests del proyecto
# Uso: ./run_tests.sh

set -e

echo "======================================================================"
echo "   EJECUTANDO TESTS - Sistema de Productos y Ubicaciones"
echo "======================================================================"

# Activar entorno virtual si existe
if [ -d "src/venv" ]; then
    echo "🔧 Activando entorno virtual..."
    source src/venv/bin/activate
fi

# Verificar que pytest está instalado
if ! command -v pytest &> /dev/null; then
    echo "⚠️  pytest no encontrado. Instalando..."
    pip install pytest pytest-cov
fi

echo ""
echo "📊 Ejecutando tests..."
echo ""

# Ejecutar tests con verbose y cobertura
pytest tests/ -v --cov=src/adapters/secondary/database/orm --cov=src/core/domain/models --cov-report=term-missing

echo ""
echo "======================================================================"
echo "✅ Tests completados"
echo "======================================================================"
echo ""
echo "📚 Comandos útiles:"
echo "  - Ver solo tests de productos:     pytest tests/test_product_models.py -v"
echo "  - Ver test específico:            pytest tests/test_product_models.py::test_nombre -v"
echo "  - Generar reporte HTML:           pytest tests/ --cov-report=html"
echo "  - Ver fixtures disponibles:        pytest --fixtures tests/"
echo ""
