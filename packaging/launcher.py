"""Script lanzador de entrada para el ejecutable congelado de MintPlay (PyInstaller).

Importa `mintplay` como paquete completo para preservar la jerarquía de módulos
e importaciones relativas internas tanto en desarrollo como en el paquete congelado.
"""

from __future__ import annotations

import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    _src_dir = str(Path(__file__).resolve().parent.parent / "src")
    if _src_dir not in sys.path:
        sys.path.insert(0, _src_dir)

from mintplay.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
