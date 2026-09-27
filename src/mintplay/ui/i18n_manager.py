"""Gestor de internacionalización y traducciones para MintPlay."""

from __future__ import annotations

import json
import logging
from typing import Dict, Optional

from PySide6.QtCore import QObject, Signal

from ..services.runtime_paths import obtener_ruta_i18n

logger = logging.getLogger(__name__)


class GestorTraduccion(QObject):
    """Mantiene el catálogo de cadenas y emite señales ante cambios de idioma."""

    idioma_cambiado = Signal(str)

    def __init__(self, idioma_inicial: str = "es"):
        super().__init__()
        self._idioma = idioma_inicial
        self._catalogo: Dict[str, str] = {}
        self._cargar_catalogo(idioma_inicial)

    @property
    def idioma(self) -> str:
        return self._idioma

    def _cargar_catalogo(self, codigo: str) -> None:
        ruta = obtener_ruta_i18n(codigo)
        if not ruta.exists():
            # Fallback a español si no se encuentra
            ruta = obtener_ruta_i18n("es")

        try:
            contenido = ruta.read_text(encoding="utf-8")
            self._catalogo = json.loads(contenido)
            self._idioma = codigo
        except Exception as err:
            logger.warning("No se pudo cargar el archivo de idioma %s: %s", ruta, err)
            self._catalogo = {}

    def cambiar_idioma(self, nuevo_idioma: str) -> None:
        """Cambia el idioma activo y emite la señal de actualización."""
        if nuevo_idioma != self._idioma:
            self._cargar_catalogo(nuevo_idioma)
            self.idioma_cambiado.emit(self._idioma)

    def texto(self, clave: str, defecto: Optional[str] = None) -> str:
        """Devuelve el texto traducido para la clave solicitada."""
        return self._catalogo.get(clave, defecto if defecto is not None else clave)


# Instancia global accesible por todos los widgets
_instancia_traductor: Optional[GestorTraduccion] = None


def obtener_traductor(idioma_inicial: str = "es") -> GestorTraduccion:
    """Devuelve el traductor singleton."""
    global _instancia_traductor
    if _instancia_traductor is None:
        _instancia_traductor = GestorTraduccion(idioma_inicial)
    return _instancia_traductor


def t(clave: str, defecto: Optional[str] = None) -> str:
    """Función rápida para traducir una clave."""
    return obtener_traductor().texto(clave, defecto)


def crear_cuadro_confirmacion_si_no(
    parent: Optional[object],
    titulo: str,
    mensaje: str,
) -> tuple[object, object, object]:
    """Construye un QMessageBox con botones explícitos 'Sí'/'No' o 'Yes'/'No' según el idioma activo.

    El botón predeterminado y de escape es siempre 'No' para evitar acciones destructivas accidentales.
    Devuelve (cuadro, btn_si, btn_no).
    """
    from PySide6.QtWidgets import QMessageBox, QWidget

    widget_padre = parent if isinstance(parent, QWidget) else None
    cuadro = QMessageBox(widget_padre)
    if widget_padre is not None and widget_padre.styleSheet():
        cuadro.setStyleSheet(widget_padre.styleSheet())
    cuadro.setIcon(QMessageBox.Question)
    cuadro.setWindowTitle(titulo)
    cuadro.setText(mensaje)

    btn_si = cuadro.addButton(t("btn_yes"), QMessageBox.YesRole)
    btn_no = cuadro.addButton(t("btn_no"), QMessageBox.NoRole)
    btn_si.setObjectName("btnConfirmarSi")
    btn_no.setObjectName("btnConfirmarNo")

    cuadro.setDefaultButton(btn_no)
    cuadro.setEscapeButton(btn_no)
    return cuadro, btn_si, btn_no


def confirmar_accion_si_no(
    parent: Optional[object],
    titulo: str,
    mensaje: str,
) -> bool:
    """Muestra un diálogo modal de confirmación traducido y devuelve True solo si se pulsa Sí/Yes."""
    cuadro, btn_si, _btn_no = crear_cuadro_confirmacion_si_no(parent, titulo, mensaje)
    cuadro.exec()
    return cuadro.clickedButton() == btn_si

