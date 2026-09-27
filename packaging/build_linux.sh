#!/usr/bin/env bash
set -euo pipefail

echo "========================================================"
echo "  Construyendo MintPlay Distribución (Linux)            "
echo "========================================================"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

PYTHON_BIN="python3"
if [ -f "$ROOT_DIR/venv/bin/python" ]; then
    PYTHON_BIN="$ROOT_DIR/venv/bin/python"
fi

echo "[1/4] Limpiando carpetas de compilación..."
rm -rf build/ dist/MintPlay dist/MintPlay-linux-x64-v1.0.0.tar.gz

echo "[2/4] Ejecutando PyInstaller..."
"$PYTHON_BIN" -m PyInstaller --clean --noconfirm packaging/MintPlay.spec

echo "[3/4] Copiando licencias..."
cp LICENSE dist/MintPlay/
cp -r LICENSES dist/MintPlay/

echo "[4/4] Empaquetando tar.gz portable..."
tar -czf dist/MintPlay-linux-x64-v1.0.0.tar.gz -C dist MintPlay

echo "========================================================"
echo "  ¡Paquete generado en dist/MintPlay-linux-x64-v1.0.0.tar.gz!"
echo "========================================================"
