"""Gestor en memoria y persistente del historial local de descargas de MintPlay."""

from __future__ import annotations

import logging
from typing import List, Optional

from PySide6.QtCore import QObject, Signal

from ..domain.models import EstadoTrabajo, RegistroHistorial, TipoMedio, TrabajoDescarga
from ..domain.platforms import PLATAFORMA_GENERICA, resolver_plataforma
from .persistence import (
    MAX_REGISTROS_HISTORIAL,
    cargar_historial,
    guardar_historial,
)

logger = logging.getLogger(__name__)


def _normalizar_plataforma_busqueda(platform_hint: str, url: str = "") -> str:
    """Devuelve variantes buscables del nombre de plataforma en español e inglés."""
    resuelta = resolver_plataforma(url=url, plataforma_actual=platform_hint)
    p = resuelta.strip().lower()
    if resuelta == PLATAFORMA_GENERICA or p in ("otro sitio", "other site", "generic", ""):
        return "otro sitio other site"
    if p == "x / twitter":
        return "x / twitter x twitter"
    return f"{p} {(platform_hint or '').strip().lower()}".strip()


class GestorHistorial(QObject):
    """Administra el historial de descargas completadas sin afectar los archivos físicos."""

    historial_cambiado = Signal()
    registro_anadido = Signal(str)
    registro_eliminado = Signal(str)
    historial_vaciado = Signal()

    def __init__(
        self,
        parent: Optional[QObject] = None,
        cargar_al_iniciar: bool = True,
    ):
        super().__init__(parent)
        self._registros: List[RegistroHistorial] = []
        if cargar_al_iniciar:
            self.recargar()

    def recargar(self) -> None:
        """Recarga los registros desde history.json."""
        try:
            self._registros = cargar_historial()
        except Exception as err:
            logger.warning("No se pudo cargar el historial al iniciar: %s", err)
            self._registros = []
        self.historial_cambiado.emit()

    def inicializar_con_registros(self, registros: List[RegistroHistorial]) -> None:
        """Establece la lista inicial de registros ordenada del más reciente al más antiguo."""
        vistos: dict[str, RegistroHistorial] = {}
        for reg in registros:
            clave = reg.clave_deduplicacion
            previo = vistos.get(clave)
            if previo is None or reg.completed_at >= previo.completed_at:
                vistos[clave] = reg

        self._registros = sorted(
            vistos.values(),
            key=lambda r: r.completed_at,
            reverse=True,
        )[:MAX_REGISTROS_HISTORIAL]
        self.historial_cambiado.emit()

    @property
    def registros(self) -> List[RegistroHistorial]:
        """Devuelve una copia ordenada de todos los registros (más reciente primero)."""
        return list(self._registros)

    @property
    def total_registros(self) -> int:
        """Cantidad total de registros almacenados actualmente."""
        return len(self._registros)

    def obtener_registro(self, id_registro: str) -> Optional[RegistroHistorial]:
        """Busca un registro por su ID o por su clave de deduplicación."""
        for r in self._registros:
            if r.id == id_registro or r.clave_deduplicacion == id_registro:
                return r
        return None

    def registrar_trabajo_completado(
        self,
        trabajo: TrabajoDescarga,
    ) -> Optional[RegistroHistorial]:
        """Registra o actualiza una descarga verificada que alcanzó el estado COMPLETADO."""
        if trabajo.status != EstadoTrabajo.COMPLETADO or not trabajo.output_path:
            return None

        nuevo = RegistroHistorial.desde_trabajo(trabajo)
        clave = nuevo.clave_deduplicacion

        # Deduplicación estricta por (job_id, attempt) o id
        self._registros = [
            r for r in self._registros if r.clave_deduplicacion != clave and r.id != nuevo.id
        ]
        self._registros.insert(0, nuevo)
        self._registros.sort(key=lambda r: r.completed_at, reverse=True)
        if len(self._registros) > MAX_REGISTROS_HISTORIAL:
            self._registros = self._registros[:MAX_REGISTROS_HISTORIAL]

        self._guardar()
        self.registro_anadido.emit(nuevo.id)
        self.historial_cambiado.emit()
        return nuevo

    def quitar_registro(self, id_registro: str) -> bool:
        """Elimina únicamente el registro del historial sin borrar el archivo físico en disco."""
        antes = len(self._registros)
        self._registros = [
            r
            for r in self._registros
            if r.id != id_registro and r.clave_deduplicacion != id_registro
        ]
        if len(self._registros) == antes:
            return False

        self._guardar()
        self.registro_eliminado.emit(id_registro)
        self.historial_cambiado.emit()
        return True

    def vaciar_historial(self) -> None:
        """Elimina todos los registros del historial conservando intactos los archivos descargados."""
        self._registros.clear()
        self._guardar()
        self.historial_vaciado.emit()
        self.historial_cambiado.emit()

    def buscar_y_filtrar(
        self,
        texto_busqueda: str = "",
        filtro_tipo: str = "all",
    ) -> List[RegistroHistorial]:
        """Filtra los registros en memoria por tipo de medio y coincidencia de texto sin tocar red."""
        consulta = (texto_busqueda or "").strip().lower()
        tipo_norm = (filtro_tipo or "all").strip().lower()

        resultado: List[RegistroHistorial] = []
        for r in self._registros:
            if tipo_norm == "video" and r.media_type != TipoMedio.VIDEO:
                continue
            if tipo_norm == "audio" and r.media_type != TipoMedio.AUDIO:
                continue

            if consulta:
                plat_buscable = _normalizar_plataforma_busqueda(r.platform_hint, r.url)
                campos = (
                    (r.title or "").lower(),
                    (r.final_filename or "").lower(),
                    (r.custom_name or "").lower(),
                    plat_buscable,
                )
                if not any(consulta in campo for campo in campos):
                    continue

            resultado.append(r)

        return resultado

    def _guardar(self) -> None:
        try:
            guardar_historial(self._registros)
        except Exception as err:
            logger.warning("No se pudo guardar el historial de descargas: %s", err)
