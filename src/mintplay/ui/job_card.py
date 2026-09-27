"""Componente visual para representar una tarjeta individual de trabajo en la cola."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QFontMetrics, QPaintEvent, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..domain.models import EstadoTrabajo, FaseTrabajo, TrabajoDescarga
from .download_form import traducir_etiqueta_calidad, traducir_plataforma
from .i18n_manager import t


def formatear_tamano(bytes_cant: Optional[int]) -> str:
    """Formatea bytes a formato legible (KB, MB, GB)."""
    if bytes_cant is None or bytes_cant <= 0:
        return ""
    tam = float(bytes_cant)
    for unidad in ("B", "KB", "MB", "GB"):
        if tam < 1024.0:
            return f"{tam:.1f} {unidad}"
        tam /= 1024.0
    return f"{tam:.1f} TB"


def formatear_velocidad(velocidad_bps: Optional[float]) -> str:
    """Formatea bytes/segundo a texto legible."""
    if not velocidad_bps or velocidad_bps <= 0:
        return ""
    vel = float(velocidad_bps)
    for unidad in ("B/s", "KB/s", "MB/s", "GB/s"):
        if vel < 1024.0:
            return f"{vel:.1f} {unidad}"
        vel /= 1024.0
    return f"{vel:.1f} TB/s"


def formatear_eta(segundos: Optional[int]) -> str:
    """Formatea segundos restantes a formato MM:SS."""
    if segundos is None or segundos < 0:
        return ""
    mins, segs = divmod(int(segundos), 60)
    horas, mins = divmod(mins, 60)
    if horas > 0:
        return f"{horas}h {mins:02d}m"
    return f"{mins:02d}:{segs:02d}"


def traducir_resumen_error(codigo_error: Optional[str]) -> str:
    """Devuelve un mensaje humano traducido según el código de error."""
    mapa = {
        "UNAVAILABLE_MEDIA": t("error_unavailable"),
        "PLAYLIST_NOT_SUPPORTED": t("error_playlist"),
        "PRIVATE_OR_RESTRICTED": t("error_private"),
        "NO_SUITABLE_FORMAT": t("error_no_format"),
        "NETWORK_ERROR": t("error_network"),
        "VERIFY_FAILED": t("error_verify"),
        "INTERRUPTED": t("error_interrupted"),
    }
    if codigo_error and codigo_error in mapa:
        return mapa[codigo_error]
    return t("error_generic")


class TarjetaTrabajo(QFrame):
    """Tarjeta interactiva que muestra el estado, progreso y acciones de un trabajo."""

    quitar_solicitado = Signal(str)
    cancelar_solicitado = Signal(str)
    reintentar_solicitado = Signal(str)
    primer_repintado = Signal(str)

    def __init__(self, trabajo: TrabajoDescarga, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.trabajo_id = trabajo.id
        self._output_path = trabajo.output_path
        self._destination_dir = trabajo.destination_dir
        self._error_code = trabajo.error_code
        self._error_detail = trabajo.error_detail
        self._titulo_completo = trabajo.display_title or trabajo.url
        self._ultimo_estado_qss: Optional[str] = None
        self._ultimo_rol_fase: Optional[str] = None
        self._pintado_notificado = False

        self.setObjectName("tarjetaTrabajo")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(14, 10, 14, 10)
        layout_principal.setSpacing(5)

        # Fila 1: Nombre/título primero y badge de estado a la derecha
        fila1 = QHBoxLayout()
        fila1.setSpacing(10)

        self.lbl_titulo = QLabel()
        self.lbl_titulo.setObjectName("tituloTarjeta")
        self.lbl_titulo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.lbl_fase = QLabel(t("status_queued"))
        self.lbl_fase.setObjectName("estadoFase")
        self.lbl_fase.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        fila1.addWidget(self.lbl_titulo, 1)
        fila1.addWidget(self.lbl_fase, 0, Qt.AlignRight | Qt.AlignTop)
        layout_principal.addLayout(fila1)

        # Fila 2: Plataforma · Tipo · Formato · Calidad traducida y carpeta resumida
        fila2 = QHBoxLayout()
        fila2.setSpacing(8)

        self.lbl_plataforma = QLabel()
        self.lbl_plataforma.setObjectName("chipPlataformaTarjeta")

        self.lbl_info_tecnica = QLabel()
        self.lbl_info_tecnica.setObjectName("infoTecnicaTarjeta")

        self.lbl_destino = QLabel()
        self.lbl_destino.setObjectName("destinoTarjeta")
        self.lbl_destino.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        fila2.addWidget(self.lbl_plataforma)
        fila2.addWidget(self.lbl_info_tecnica)
        fila2.addStretch(1)
        fila2.addWidget(self.lbl_destino)
        layout_principal.addLayout(fila2)

        # Fila 3: Barra de progreso y métricas de transferencia (solo cuando aplica)
        self.barra_progreso = QProgressBar()
        self.barra_progreso.setTextVisible(False)
        self.barra_progreso.setRange(0, 100)
        self.barra_progreso.setValue(0)
        layout_principal.addWidget(self.barra_progreso)

        self.lbl_metricas = QLabel("")
        self.lbl_metricas.setObjectName("metricasTarjeta")
        self.lbl_metricas.setVisible(False)
        layout_principal.addWidget(self.lbl_metricas)

        # Fila 4: Resumen de error legible cuando falla o se interrumpe
        self.lbl_resumen_error = QLabel("")
        self.lbl_resumen_error.setObjectName("resumenErrorTarjeta")
        self.lbl_resumen_error.setWordWrap(True)
        self.lbl_resumen_error.setVisible(False)
        layout_principal.addWidget(self.lbl_resumen_error)

        # Fila 5: Botones de acción contextual
        self.layout_acciones = QHBoxLayout()
        self.layout_acciones.setContentsMargins(0, 2, 0, 0)
        self.layout_acciones.setSpacing(8)
        self.layout_acciones.addStretch(1)

        self.btn_detalles = QPushButton(t("btn_details"))
        self.btn_detalles.setObjectName("btnAccionTarjeta")
        self.btn_detalles.clicked.connect(self._mostrar_detalles)

        self.btn_abrir_archivo = QPushButton(t("btn_open_file"))
        self.btn_abrir_archivo.setObjectName("btnAccionTarjeta")
        self.btn_abrir_archivo.clicked.connect(self._abrir_archivo)

        self.btn_abrir_carpeta = QPushButton(t("btn_open_folder"))
        self.btn_abrir_carpeta.setObjectName("btnAccionTarjeta")
        self.btn_abrir_carpeta.clicked.connect(self._abrir_carpeta)

        self.btn_reintentar = QPushButton(t("btn_retry"))
        self.btn_reintentar.setObjectName("btnAccionTarjeta")
        self.btn_reintentar.clicked.connect(lambda: self.reintentar_solicitado.emit(self.trabajo_id))

        self.btn_cancelar = QPushButton(t("btn_cancel"))
        self.btn_cancelar.setObjectName("btnAccionTarjeta")
        self.btn_cancelar.clicked.connect(lambda: self.cancelar_solicitado.emit(self.trabajo_id))

        self.btn_quitar = QPushButton(t("btn_remove"))
        self.btn_quitar.setObjectName("btnAccionTarjeta")
        self.btn_quitar.clicked.connect(lambda: self.quitar_solicitado.emit(self.trabajo_id))

        self.layout_acciones.addWidget(self.btn_detalles)
        self.layout_acciones.addWidget(self.btn_abrir_archivo)
        self.layout_acciones.addWidget(self.btn_abrir_carpeta)
        self.layout_acciones.addWidget(self.btn_reintentar)
        self.layout_acciones.addWidget(self.btn_cancelar)
        self.layout_acciones.addWidget(self.btn_quitar)

        layout_principal.addLayout(self.layout_acciones)

        self.actualizar_datos(trabajo)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        if not self._pintado_notificado:
            self._pintado_notificado = True
            self.primer_repintado.emit(self.trabajo_id)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._aplicar_elision_titulo()

    def _aplicar_elision_titulo(self) -> None:
        ancho_disp = max(180, self.width() - 165)
        fm = QFontMetrics(self.lbl_titulo.font())
        elidido = fm.elidedText(self._titulo_completo, Qt.ElideRight, ancho_disp)
        self.lbl_titulo.setText(elidido)
        self.lbl_titulo.setToolTip(
            self._titulo_completo if elidido != self._titulo_completo else ""
        )

    def actualizar_datos(self, trabajo: TrabajoDescarga, posicion_cola: Optional[int] = None) -> None:
        """Actualiza los componentes visuales con los datos más recientes sin recalcular QSS en exceso."""
        self.trabajo_id = trabajo.id
        self._output_path = trabajo.output_path
        self._destination_dir = trabajo.destination_dir
        self._error_code = trabajo.error_code
        self._error_detail = trabajo.error_detail

        # Re-pulir QSS únicamente si cambió el estado semántico de la tarjeta
        estado_val = trabajo.status.value
        if estado_val != self._ultimo_estado_qss:
            self._ultimo_estado_qss = estado_val
            self.setProperty("estado", estado_val)
            self.style().unpolish(self)
            self.style().polish(self)

        rol_fase = self._calcular_rol_fase(trabajo)
        if rol_fase != self._ultimo_rol_fase:
            self._ultimo_rol_fase = rol_fase
            self.lbl_fase.setProperty("rol", rol_fase)
            self.lbl_fase.style().unpolish(self.lbl_fase)
            self.lbl_fase.style().polish(self.lbl_fase)

        # Título y plataforma traducida
        self._titulo_completo = trabajo.display_title or trabajo.url
        self._aplicar_elision_titulo()
        self.lbl_plataforma.setText(traducir_plataforma(trabajo.platform_hint))

        # Resumen técnico traducido (Vídeo/Audio · Formato · Calidad traducida)
        tipo_texto = t("type_video") if trabajo.media_type.value == "video" else t("type_audio")
        calidad_texto = traducir_etiqueta_calidad(trabajo.quality_choice)
        self.lbl_info_tecnica.setText(
            f"{tipo_texto} · {trabajo.target_extension.upper()} · {calidad_texto}"
        )

        # Destino resumido
        carpeta_corta = Path(trabajo.destination_dir).name or trabajo.destination_dir
        self.lbl_destino.setText(carpeta_corta)
        self.lbl_destino.setToolTip(trabajo.destination_dir)

        # Textos de fase y métricas
        texto_fase, texto_metricas = self._obtener_textos_estado(trabajo, posicion_cola)
        self.lbl_fase.setText(texto_fase)
        self.lbl_metricas.setText(texto_metricas)
        self.lbl_metricas.setVisible(bool(texto_metricas))

        # Resumen de error en estados fallidos o interrumpidos
        if trabajo.status in (EstadoTrabajo.ERROR, EstadoTrabajo.INTERRUMPIDO):
            self.lbl_resumen_error.setText(traducir_resumen_error(trabajo.error_code))
            self.lbl_resumen_error.setVisible(True)
        else:
            self.lbl_resumen_error.setVisible(False)

        # Barra de progreso visible solo en actividad o al completar
        if trabajo.status == EstadoTrabajo.COMPLETADO:
            self.barra_progreso.setRange(0, 100)
            self.barra_progreso.setValue(100)
            self.barra_progreso.setVisible(True)
        elif trabajo.status != EstadoTrabajo.ACTIVO:
            self.barra_progreso.setVisible(False)
        elif trabajo.phase in (
            FaseTrabajo.PREPARANDO,
            FaseTrabajo.PROCESANDO,
            FaseTrabajo.VERIFICANDO,
        ):
            if self.barra_progreso.minimum() != 0 or self.barra_progreso.maximum() != 0:
                self.barra_progreso.setRange(0, 0)
            self.barra_progreso.setVisible(True)
        elif trabajo.phase == FaseTrabajo.DESCARGANDO:
            if trabajo.progress > 0.0:
                if self.barra_progreso.maximum() != 100:
                    self.barra_progreso.setRange(0, 100)
                self.barra_progreso.setValue(int(trabajo.progress))
            else:
                if self.barra_progreso.maximum() != 0:
                    self.barra_progreso.setRange(0, 0)
            self.barra_progreso.setVisible(True)

        self._actualizar_textos_botones()
        self._actualizar_botones(trabajo)

    def _calcular_rol_fase(self, trabajo: TrabajoDescarga) -> str:
        if trabajo.status == EstadoTrabajo.COMPLETADO:
            return "completed"
        if trabajo.status in (EstadoTrabajo.ERROR, EstadoTrabajo.INTERRUMPIDO):
            return "error"
        if trabajo.status == EstadoTrabajo.ACTIVO:
            return "active"
        return "queued"

    def _obtener_textos_estado(
        self, trabajo: TrabajoDescarga, posicion_cola: Optional[int] = None
    ) -> tuple[str, str]:
        """Calcula las cadenas de fase y métricas secundarias."""
        if trabajo.status == EstadoTrabajo.COMPLETADO:
            return f"✓ {t('status_completed')}", ""

        if trabajo.status == EstadoTrabajo.ERROR:
            return t("status_failed"), ""

        if trabajo.status == EstadoTrabajo.CANCELADO:
            return t("status_cancelled"), ""

        if trabajo.status == EstadoTrabajo.INTERRUMPIDO:
            return t("status_interrupted"), ""

        if trabajo.phase == FaseTrabajo.EN_ESPERA:
            prefijo = f"#{posicion_cola} · " if posicion_cola and posicion_cola > 0 else ""
            return f"{prefijo}{t('status_queued')}", ""

        if trabajo.phase == FaseTrabajo.PREPARANDO:
            return t("status_preparing"), ""

        if trabajo.phase == FaseTrabajo.PROCESANDO:
            return t("status_postprocessing"), ""

        if trabajo.phase == FaseTrabajo.VERIFICANDO:
            return t("status_verifying"), ""

        if trabajo.phase == FaseTrabajo.DESCARGANDO:
            fase_txt = f"{t('status_downloading')} · {trabajo.progress:.0f}%"
            metricas = []
            if trabajo.downloaded_bytes and trabajo.total_bytes:
                metricas.append(
                    f"{formatear_tamano(trabajo.downloaded_bytes)} / {formatear_tamano(trabajo.total_bytes)}"
                )
            elif trabajo.downloaded_bytes:
                metricas.append(formatear_tamano(trabajo.downloaded_bytes))

            if trabajo.speed:
                metricas.append(formatear_velocidad(trabajo.speed))

            if trabajo.eta is not None:
                metricas.append(f"ETA {formatear_eta(trabajo.eta)}")

            return fase_txt, "  ·  ".join(metricas)

        return "", ""

    def _actualizar_textos_botones(self) -> None:
        self.btn_cancelar.setText(t("btn_cancel"))
        self.btn_quitar.setText(t("btn_remove"))
        self.btn_reintentar.setText(t("btn_retry"))
        self.btn_abrir_archivo.setText(t("btn_open_file"))
        self.btn_abrir_carpeta.setText(t("btn_open_folder"))
        self.btn_detalles.setText(t("btn_details"))

    def _actualizar_botones(self, trabajo: TrabajoDescarga) -> None:
        """Configura qué botones están visibles y activos según el estado del trabajo."""
        self.btn_detalles.setVisible(False)
        self.btn_abrir_archivo.setVisible(False)
        self.btn_abrir_carpeta.setVisible(False)
        self.btn_reintentar.setVisible(False)
        self.btn_cancelar.setVisible(False)
        self.btn_quitar.setVisible(False)

        if trabajo.status == EstadoTrabajo.EN_ESPERA:
            self.btn_quitar.setVisible(True)

        elif trabajo.status == EstadoTrabajo.ACTIVO:
            self.btn_cancelar.setVisible(True)
            if trabajo.phase in (FaseTrabajo.PROCESANDO, FaseTrabajo.VERIFICANDO):
                self.btn_cancelar.setEnabled(False)
                self.btn_cancelar.setToolTip(t("tooltip_finishing_file"))
            else:
                self.btn_cancelar.setEnabled(True)
                self.btn_cancelar.setToolTip("")

        elif trabajo.status == EstadoTrabajo.COMPLETADO:
            self.btn_abrir_archivo.setVisible(True)
            self.btn_abrir_carpeta.setVisible(True)

        elif trabajo.status in (
            EstadoTrabajo.ERROR,
            EstadoTrabajo.CANCELADO,
            EstadoTrabajo.INTERRUMPIDO,
        ):
            self.btn_reintentar.setVisible(True)
            self.btn_quitar.setVisible(True)
            if self._error_detail:
                self.btn_detalles.setVisible(True)

    def _abrir_archivo(self) -> None:
        if self._output_path and os.path.exists(self._output_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._output_path))

    def _abrir_carpeta(self) -> None:
        carpeta = self._destination_dir
        if self._output_path and os.path.exists(self._output_path):
            carpeta = str(Path(self._output_path).parent)
        if os.path.exists(carpeta):
            QDesktopServices.openUrl(QUrl.fromLocalFile(carpeta))

    def _mostrar_detalles(self) -> None:
        if self._error_detail:
            msg = QMessageBox(self)
            msg.setWindowTitle(t("btn_details"))
            msg.setText(self._error_detail)
            msg.setIcon(QMessageBox.Information)
            msg.exec()
