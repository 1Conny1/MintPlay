"""Gestor de notificaciones del sistema para eventos terminales de descarga en MintPlay."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set, Tuple

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QSystemTrayIcon, QWidget

from ..domain.models import EstadoTrabajo, FaseTrabajo, TrabajoDescarga
from ..services.runtime_paths import obtener_ruta_icono
from .download_form import traducir_plataforma
from .i18n_manager import obtener_traductor, t

logger = logging.getLogger(__name__)

_PATRON_URL = re.compile(r"https?://\S+", re.IGNORECASE)
_PATRON_RUTA_WIN = re.compile(r"[A-Za-z]:\\[^\s]+")
_PATRON_RUTA_POSIX = re.compile(r"(?:/Users/|/home/)[^\s]+")


def limpiar_texto_sensible_notificacion(texto: str) -> str:
    """Elimina URLs completas y rutas de directorios personales de un texto de notificación."""
    limpio = _PATRON_URL.sub("", texto or "")
    limpio = _PATRON_RUTA_WIN.sub("", limpio)
    limpio = _PATRON_RUTA_POSIX.sub("", limpio)
    limpio = re.sub(r"\s+", " ", limpio).strip(" -·•\t\r\n")
    return limpio


def truncar_legible(texto: str, max_len: int = 58) -> str:
    """Trunca un nombre de trabajo de forma legible sin cortar palabras bruscamente cuando es posible."""
    limpio = re.sub(r"\s+", " ", (texto or "").strip())
    if len(limpio) <= max_len:
        return limpio
    recorte = limpio[: max_len - 1].rstrip()
    ultimo_espacio = recorte.rfind(" ")
    if ultimo_espacio >= max(16, (max_len // 2)):
        recorte = recorte[:ultimo_espacio].rstrip(" .,-_·")
    return f"{recorte}…"


def formatear_nombre_notificacion(trabajo: TrabajoDescarga, max_len: int = 58) -> str:
    """Obtiene un nombre breve, legible y libre de URLs o rutas personales para el aviso."""
    candidatos: list[str] = []
    if trabajo.custom_name and trabajo.custom_name.strip():
        candidatos.append(trabajo.custom_name.strip())
    titulo_job = getattr(trabajo, "display_title", "") or getattr(trabajo, "title", "")
    if titulo_job and titulo_job.strip():
        titulo = titulo_job.strip()
        if not titulo.lower().startswith(("http://", "https://")):
            candidatos.append(titulo)
    if trabajo.output_path and trabajo.output_path.strip():
        try:
            nombre_archivo = Path(trabajo.output_path).name
            if nombre_archivo:
                candidatos.append(nombre_archivo)
        except Exception:
            pass

    for cand in candidatos:
        limpio = limpiar_texto_sensible_notificacion(cand)
        if limpio:
            return truncar_legible(limpio, max_len=max_len)

    plat_hint = getattr(trabajo, "platform_hint", "") or getattr(trabajo, "platform", "")
    plataforma = traducir_plataforma(plat_hint, trabajo.url)
    formato = (trabajo.target_extension or "").upper()
    respaldo = f"{plataforma} ({formato})" if formato else plataforma
    return truncar_legible(respaldo, max_len=max_len)


@dataclass(frozen=True)
class RegistroNotificacion:
    """Representa un aviso terminal procesado por el gestor de notificaciones."""

    trabajo_id: str
    attempt: int
    estado: str
    titulo: str
    mensaje: str
    idioma: str
    ventana_en_segundo_plano: bool
    enviada_sistema: bool


class GestorNotificaciones(QObject):
    """Gestiona los avisos del sistema al completar o fallar una descarga sin bloquear la UI."""

    notificacion_emitida = Signal(object)  # RegistroNotificacion

    def __init__(
        self,
        ventana_principal: Optional[QWidget] = None,
        activas: bool = True,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent or ventana_principal)
        self._ventana = ventana_principal
        self._activas = bool(activas)
        self._claves_notificadas: Set[Tuple[str, int, str]] = set()
        self.historial_notificaciones: List[RegistroNotificacion] = []
        self._tray: Optional[QSystemTrayIcon] = None
        self._inicializar_bandeja_si_disponible()

    def _es_entorno_offscreen(self) -> bool:
        return os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"

    def _inicializar_bandeja_si_disponible(self) -> None:
        """Prepara QSystemTrayIcon de manera segura sin exigir minimizar a la bandeja."""
        if self._tray is not None or self._es_entorno_offscreen():
            return
        try:
            if not QSystemTrayIcon.isSystemTrayAvailable():
                return
            tray = QSystemTrayIcon(self)
            ruta_ico = obtener_ruta_icono("app.png")
            if ruta_ico.exists():
                tray.setIcon(QIcon(str(ruta_ico)))
            elif self._ventana is not None and not self._ventana.windowIcon().isNull():
                tray.setIcon(self._ventana.windowIcon())
            tray.setToolTip(t("app_name"))
            tray.messageClicked.connect(self.enfocar_ventana_principal)
            tray.activated.connect(self._al_activar_icono_bandeja)
            self._tray = tray
        except Exception as err:
            logger.debug("Área de notificaciones del sistema no disponible: %s", err)
            self._tray = None

    @property
    def activas(self) -> bool:
        """Indica si las notificaciones de descargas están habilitadas."""
        return self._activas

    def establecer_activas(self, activas: bool) -> None:
        """Activa o desactiva el envío de notificaciones del sistema en caliente."""
        self._activas = bool(activas)
        if not self._activas and self._tray is not None:
            try:
                self._tray.hide()
            except Exception:
                pass

    def _ventana_en_segundo_plano(self) -> bool:
        if self._ventana is None:
            return True
        return (
            self._ventana.isMinimized()
            or not self._ventana.isActiveWindow()
            or not self._ventana.isVisible()
        )

    def enfocar_ventana_principal(self) -> None:
        """Restaura y trae al frente la ventana principal de MintPlay al pulsar el aviso."""
        if self._ventana is None:
            return
        try:
            if self._ventana.isMinimized():
                self._ventana.showNormal()
            elif not self._ventana.isVisible():
                self._ventana.show()
            self._ventana.raise_()
            self._ventana.activateWindow()
        except Exception as err:
            logger.debug("No se pudo enfocar la ventana principal desde el aviso: %s", err)

    def _al_activar_icono_bandeja(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.Trigger,
            QSystemTrayIcon.DoubleClick,
        ):
            self.enfocar_ventana_principal()

    def notificar_completado(
        self, trabajo: Optional[TrabajoDescarga]
    ) -> Optional[RegistroNotificacion]:
        """Emite un aviso cuando el trabajo alcanza COMPLETED tras conversión y verificación."""
        if trabajo is None:
            return None
        if (
            trabajo.status != EstadoTrabajo.COMPLETADO
            or trabajo.phase != FaseTrabajo.FINALIZADO
        ):
            return None
        if not self._activas:
            return None

        clave = (trabajo.id, int(trabajo.attempt), trabajo.status.value)
        if clave in self._claves_notificadas:
            return None
        self._claves_notificadas.add(clave)

        nombre = formatear_nombre_notificacion(trabajo)
        formato = (trabajo.target_extension or "").upper()
        titulo = t("notif_completed_title")
        mensaje = t("notif_completed_body").format(name=nombre, format=formato)
        return self._registrar_y_enviar(
            trabajo=trabajo,
            titulo=titulo,
            mensaje=mensaje,
            es_error=False,
        )

    def notificar_fallido(
        self, trabajo: Optional[TrabajoDescarga]
    ) -> Optional[RegistroNotificacion]:
        """Emite un aviso cuando el trabajo termina en estado FAILED (nunca en cancelación)."""
        if trabajo is None:
            return None
        if trabajo.status != EstadoTrabajo.ERROR or trabajo.phase != FaseTrabajo.ERROR:
            return None
        if not self._activas:
            return None

        clave = (trabajo.id, int(trabajo.attempt), trabajo.status.value)
        if clave in self._claves_notificadas:
            return None
        self._claves_notificadas.add(clave)

        nombre = formatear_nombre_notificacion(trabajo)
        titulo = t("notif_failed_title")
        mensaje = t("notif_failed_body").format(name=nombre)
        return self._registrar_y_enviar(
            trabajo=trabajo,
            titulo=titulo,
            mensaje=mensaje,
            es_error=True,
        )

    def _registrar_y_enviar(
        self,
        trabajo: TrabajoDescarga,
        titulo: str,
        mensaje: str,
        es_error: bool,
    ) -> RegistroNotificacion:
        en_segundo_plano = self._ventana_en_segundo_plano()
        enviada_sistema = self._mostrar_aviso_sistema(
            titulo=titulo,
            mensaje=mensaje,
            es_error=es_error,
        )
        registro = RegistroNotificacion(
            trabajo_id=trabajo.id,
            attempt=int(trabajo.attempt),
            estado=trabajo.status.value,
            titulo=titulo,
            mensaje=mensaje,
            idioma=obtener_traductor().idioma,
            ventana_en_segundo_plano=en_segundo_plano,
            enviada_sistema=enviada_sistema,
        )
        self.historial_notificaciones.append(registro)
        self.notificacion_emitida.emit(registro)
        return registro

    def _mostrar_aviso_sistema(
        self,
        titulo: str,
        mensaje: str,
        es_error: bool = False,
    ) -> bool:
        """Envía el mensaje al área de notificaciones del sistema si está disponible, sin lanzar errores."""
        if self._es_entorno_offscreen():
            return False
        try:
            self._inicializar_bandeja_si_disponible()
            if self._tray is None or not QSystemTrayIcon.supportsMessages():
                return False
            if not self._tray.isVisible():
                self._tray.show()
            icono = (
                QSystemTrayIcon.Warning
                if es_error
                else QSystemTrayIcon.Information
            )
            self._tray.showMessage(titulo, mensaje, icono, 5000)
            return True
        except Exception as err:
            logger.debug("No se pudo mostrar notificación del sistema: %s", err)
            return False

    def cerrar(self) -> None:
        """Oculta limpiamente el icono de bandeja al cerrar la aplicación."""
        if self._tray is not None:
            try:
                self._tray.hide()
            except Exception:
                pass
