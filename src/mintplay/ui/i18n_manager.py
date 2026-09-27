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
