"""Punto de entrada principal para ejecutar la aplicación MintPlay."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

if not __package__ and not getattr(sys, "frozen", False):
    _src_dir = str(Path(__file__).resolve().parent.parent)
    if _src_dir not in sys.path:
        sys.path.insert(0, _src_dir)

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from mintplay.domain.models import TrabajoDescarga
from mintplay.services.download_service import ServicioDescargaYtDlp
from mintplay.services.persistence import cargar_cola, cargar_configuracion
from mintplay.services.queue_manager import GestorCola
from mintplay.services.runtime_paths import (
    configurar_entorno_ejecucion,
    obtener_directorio_datos_usuario,
    obtener_ruta_icono,
)
from mintplay.ui.main_window import VentanaPrincipal


def configurar_logging() -> None:
    """Configura el registro de eventos en el directorio del usuario."""
    dir_usuario = obtener_directorio_datos_usuario()
    archivo_log = dir_usuario / "mintplay.log"

    handlers: list[logging.Handler] = [
        logging.FileHandler(str(archivo_log), encoding="utf-8"),
    ]
    if sys.stdout is not None:
        handlers.append(logging.StreamHandler(sys.stdout))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def main() -> int:
    """Función de arranque de MintPlay."""
    configurar_entorno_ejecucion()
    configurar_logging()
    logger = logging.getLogger("mintplay")
    logger.info("Iniciando MintPlay...")

    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        try:
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        except Exception:
            pass

    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        try:
            QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("MintPlay")
    app.setOrganizationName("MintPlay")

    # Icono de aplicación global
    ruta_ico = obtener_ruta_icono("app.png")
    if ruta_ico.exists():
        app.setWindowIcon(QIcon(str(ruta_ico)))

    # Cargar persistencia
    config = cargar_configuracion()
    trabajos_guardados = cargar_cola()

    servicio = ServicioDescargaYtDlp()
    gestor = GestorCola(servicio)
    gestor.inicializar_con_trabajos(trabajos_guardados)

    ventana = VentanaPrincipal(gestor, config)
    ventana.show()

    retorno = app.exec()
    gestor.cerrar()
    return retorno


if __name__ == "__main__":
    sys.exit(main())
