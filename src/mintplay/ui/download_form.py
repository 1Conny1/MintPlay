"""Formulario de entrada de descargas para MintPlay."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..domain.format_policy import (
    CALIDADES_POR_FORMATO,
    FORMATOS_POR_TIPO,
    es_selector_calidad_interactivo,
    obtener_calidad_predeterminada,
    obtener_clave_ayuda_calidad,
    obtener_formato_predeterminado,
)
from ..domain.models import (
    FormatoAudio,
    OpcionesDescarga,
    TipoMedio,
)
from ..services.output_paths import sanitizar_nombre_archivo
from .i18n_manager import obtener_traductor, t


def traducir_etiqueta_calidad(cal: str) -> str:
    """Devuelve la etiqueta traducida y técnicamente precisa para una opción de calidad."""
    mapa = {
        "best": t("quality_best"),
        "1080p": t("quality_1080p"),
        "720p": t("quality_720p"),
        "480p": t("quality_480p"),
        "original": t("quality_original"),
        "lossless": t("quality_lossless"),
        "320": f"320 {t('quality_kbps')}",
        "256": f"256 {t('quality_kbps')}",
        "192": f"192 {t('quality_kbps')}",
        "128": f"128 {t('quality_kbps')}",
    }
    return mapa.get(cal, cal)


def traducir_plataforma(plataforma: str) -> str:
    """Normaliza y traduce el indicador de sitio cuando es genérico."""
    if not plataforma or plataforma in ("Otro sitio", "Other site", "Generic"):
        return t("other_site")
    return plataforma


def estimar_plataforma_url(url: str) -> str:
    """Identifica de forma orientativa la plataforma según el nombre de host."""
    url_limpia = url.strip().lower()
    if not url_limpia or not (
        url_limpia.startswith("http://") or url_limpia.startswith("https://")
    ):
        return t("waiting_url")

    try:
        host = urlparse(url_limpia).netloc.lower()
    except Exception:
        return t("other_site")

    if any(k in host for k in ("youtube.com", "youtu.be")):
        return "YouTube"
    if "vimeo.com" in host:
        return "Vimeo"
    if "soundcloud.com" in host:
        return "SoundCloud"
    if "tiktok.com" in host:
        return "TikTok"
    if any(k in host for k in ("twitter.com", "x.com")):
        return "X / Twitter"
    if "instagram.com" in host:
        return "Instagram"
    if "reddit.com" in host:
        return "Reddit"
    if "twitch.tv" in host:
        return "Twitch"

    return t("other_site")


class FormularioDescarga(QFrame):
    """Panel con los campos para configurar y añadir una nueva descarga."""

    descarga_solicitada = Signal(object, str)  # OpcionesDescarga, plataforma_estimada

    def __init__(self, directorio_predeterminado: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("panelFormulario")
        self._directorio_destino = directorio_predeterminado

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(11)

        # Fila 1: URL y chip de plataforma
        fila_cabecera_url = QHBoxLayout()
        self.lbl_url = QLabel(t("url_label"))
        self.lbl_url.setObjectName("etiquetaCampo")
        self.lbl_chip = QLabel(t("waiting_url"))
        self.lbl_chip.setObjectName("chipPlataforma")
        fila_cabecera_url.addWidget(self.lbl_url)
        fila_cabecera_url.addStretch(1)
        fila_cabecera_url.addWidget(self.lbl_chip)
        layout.addLayout(fila_cabecera_url)

        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText(t("url_placeholder"))
        self.txt_url.textChanged.connect(self._al_cambiar_url)
        self.txt_url.returnPressed.connect(self._al_pulsar_anadir)
        layout.addWidget(self.txt_url)

        self.lbl_error_url = QLabel("")
        self.lbl_error_url.setObjectName("etiquetaError")
        self.lbl_error_url.setWordWrap(True)
        self.lbl_error_url.setVisible(False)
        layout.addWidget(self.lbl_error_url)

        # Fila 2: Nombre de archivo opcional
        self.lbl_nombre = QLabel(t("name_label"))
        self.lbl_nombre.setObjectName("etiquetaCampo")
        layout.addWidget(self.lbl_nombre)

        self.txt_nombre = QLineEdit()
        self.txt_nombre.setPlaceholderText(t("name_placeholder"))
        layout.addWidget(self.txt_nombre)

        # Fila 3: Tipo de medio y Formato
        fila_tipo_formato = QHBoxLayout()
        fila_tipo_formato.setSpacing(12)

        col_tipo = QVBoxLayout()
        col_tipo.setSpacing(5)
        self.lbl_tipo = QLabel(t("type_label"))
        self.lbl_tipo.setObjectName("etiquetaCampo")
        self.cmb_tipo = QComboBox()
        self.cmb_tipo.addItem(t("type_video"), TipoMedio.VIDEO.value)
        self.cmb_tipo.addItem(t("type_audio"), TipoMedio.AUDIO.value)
        self.cmb_tipo.currentIndexChanged.connect(self._al_cambiar_tipo)
        col_tipo.addWidget(self.lbl_tipo)
        col_tipo.addWidget(self.cmb_tipo)

        col_formato = QVBoxLayout()
        col_formato.setSpacing(5)
        self.lbl_formato = QLabel(t("format_label"))
        self.lbl_formato.setObjectName("etiquetaCampo")
        self.cmb_formato = QComboBox()
        self.cmb_formato.currentIndexChanged.connect(self._al_cambiar_formato)
        col_formato.addWidget(self.lbl_formato)
        col_formato.addWidget(self.cmb_formato)

        fila_tipo_formato.addLayout(col_tipo, 1)
        fila_tipo_formato.addLayout(col_formato, 1)
        layout.addLayout(fila_tipo_formato)

        # Fila 4: Calidad / Bitrate y nota técnica aclaratoria
        col_calidad = QVBoxLayout()
        col_calidad.setSpacing(4)
        self.lbl_calidad = QLabel(t("quality_label"))
        self.lbl_calidad.setObjectName("etiquetaCampo")
        self.cmb_calidad = QComboBox()
        self.lbl_ayuda_calidad = QLabel("")
        self.lbl_ayuda_calidad.setObjectName("etiquetaAyuda")
        self.lbl_ayuda_calidad.setWordWrap(True)

        col_calidad.addWidget(self.lbl_calidad)
        col_calidad.addWidget(self.cmb_calidad)
        col_calidad.addWidget(self.lbl_ayuda_calidad)
        layout.addLayout(col_calidad)

        # Fila 5: Carpeta de destino
        self.lbl_carpeta = QLabel(t("folder_label"))
        self.lbl_carpeta.setObjectName("etiquetaCampo")
        layout.addWidget(self.lbl_carpeta)

        fila_carpeta = QHBoxLayout()
        fila_carpeta.setSpacing(8)

        self.txt_carpeta = QLineEdit(self._directorio_destino)
        self.txt_carpeta.setReadOnly(True)
        self.txt_carpeta.setToolTip(self._directorio_destino)

        self.btn_examinar = QPushButton(t("btn_browse"))
        self.btn_examinar.clicked.connect(self._seleccionar_carpeta)

        self.btn_abrir_carpeta = QPushButton(t("btn_open_folder"))
        self.btn_abrir_carpeta.clicked.connect(self._abrir_carpeta)

        fila_carpeta.addWidget(self.txt_carpeta, 1)
        fila_carpeta.addWidget(self.btn_examinar)
        fila_carpeta.addWidget(self.btn_abrir_carpeta)
        layout.addLayout(fila_carpeta)

        self.lbl_error_carpeta = QLabel("")
        self.lbl_error_carpeta.setObjectName("etiquetaError")
        self.lbl_error_carpeta.setWordWrap(True)
        self.lbl_error_carpeta.setVisible(False)
        layout.addWidget(self.lbl_error_carpeta)

        layout.addStretch(1)

        # Fila 6: Botón principal Añadir a la cola
        self.btn_anadir = QPushButton(t("btn_add_to_queue"))
        self.btn_anadir.setObjectName("btnPrimario")
        self.btn_anadir.setCursor(Qt.PointingHandCursor)
        self.btn_anadir.clicked.connect(self._al_pulsar_anadir)
        layout.addWidget(self.btn_anadir)

        # Inicializar listas dependientes
        self._poblar_formatos(TipoMedio.VIDEO)
        obtener_traductor().idioma_cambiado.connect(self.actualizar_textos_idioma)

    def _al_cambiar_url(self, texto: str) -> None:
        self.lbl_error_url.setVisible(False)
        self.lbl_chip.setText(estimar_plataforma_url(texto))

    def _al_cambiar_tipo(self) -> None:
        tipo_val = self.cmb_tipo.currentData()
        if not tipo_val:
            return
        tipo = TipoMedio(tipo_val)
        self._poblar_formatos(tipo)

    def _poblar_formatos(self, tipo: TipoMedio, preservar_formato: Optional[str] = None) -> None:
        self.cmb_formato.blockSignals(True)
        self.cmb_formato.clear()
        formatos = FORMATOS_POR_TIPO.get(tipo, [])
        for fmt in formatos:
            self.cmb_formato.addItem(fmt.upper(), fmt)

        objetivo = preservar_formato if preservar_formato in formatos else obtener_formato_predeterminado(tipo)
        idx = self.cmb_formato.findData(objetivo)
        if idx >= 0:
            self.cmb_formato.setCurrentIndex(idx)
        self.cmb_formato.blockSignals(False)

        self._poblar_calidades(self.cmb_formato.currentData())

    def _al_cambiar_formato(self) -> None:
        formato = self.cmb_formato.currentData()
        if formato:
            self._poblar_calidades(formato)

    def _actualizar_etiqueta_y_ayuda_calidad(self, formato: str) -> None:
        tipo_val = self.cmb_tipo.currentData()
        if tipo_val == TipoMedio.VIDEO.value:
            self.lbl_calidad.setText(t("quality_label"))
        elif formato == FormatoAudio.MP3.value:
            self.lbl_calidad.setText(t("quality_bitrate_label"))
        else:
            self.lbl_calidad.setText(t("quality_audio_mode_label"))

        clave_ayuda = obtener_clave_ayuda_calidad(formato)
        self.lbl_ayuda_calidad.setText(t(clave_ayuda))
        self.cmb_calidad.setEnabled(es_selector_calidad_interactivo(formato))

    def _poblar_calidades(
        self, formato: str, preservar_calidad: Optional[str] = None
    ) -> None:
        if not formato:
            return
        self.cmb_calidad.blockSignals(True)
        self.cmb_calidad.clear()
        calidades = CALIDADES_POR_FORMATO.get(formato, ["best"])

        for cal in calidades:
            etiqueta = self._traducir_etiqueta_calidad(cal)
            self.cmb_calidad.addItem(etiqueta, cal)

        objetivo = (
            preservar_calidad
            if preservar_calidad in calidades
            else obtener_calidad_predeterminada(formato)
        )
        idx = self.cmb_calidad.findData(objetivo)
        if idx >= 0:
            self.cmb_calidad.setCurrentIndex(idx)

        self.cmb_calidad.blockSignals(False)
        self._actualizar_etiqueta_y_ayuda_calidad(formato)

    def _traducir_etiqueta_calidad(self, cal: str) -> str:
        return traducir_etiqueta_calidad(cal)

    def _seleccionar_carpeta(self) -> None:
        carpeta = QFileDialog.getExistingDirectory(
            self,
            t("folder_label"),
            self._directorio_destino,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if carpeta:
            self.establecer_directorio_destino(carpeta)

    def establecer_directorio_destino(self, carpeta: str) -> None:
        self._directorio_destino = carpeta
        self.txt_carpeta.setText(carpeta)
        self.txt_carpeta.setToolTip(carpeta)
        self.lbl_error_carpeta.setVisible(False)

    def _abrir_carpeta(self) -> None:
        if os.path.exists(self._directorio_destino):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._directorio_destino))

    def _al_pulsar_anadir(self) -> None:
        url = self.txt_url.text().strip()
        self.lbl_error_url.setVisible(False)
        self.lbl_error_carpeta.setVisible(False)

        # Validación sintáctica de URL
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            self.lbl_error_url.setText(t("url_error_invalid"))
            self.lbl_error_url.setVisible(True)
            self.txt_url.setFocus()
            return

        # Validación de carpeta de destino
        destino = Path(self._directorio_destino)
        if not destino.exists() or not os.access(str(destino), os.W_OK):
            self.lbl_error_carpeta.setText(t("folder_error_invalid"))
            self.lbl_error_carpeta.setVisible(True)
            return

        # Saneamiento del nombre opcional
        nombre_ingresado = self.txt_nombre.text().strip()
        nombre_saneado = sanitizar_nombre_archivo(nombre_ingresado) if nombre_ingresado else ""

        tipo = TipoMedio(self.cmb_tipo.currentData())
        formato = self.cmb_formato.currentData()
        calidad = self.cmb_calidad.currentData()
        plataforma = estimar_plataforma_url(url)

        opciones = OpcionesDescarga(
            url=url,
            custom_name=nombre_saneado,
            media_type=tipo,
            target_extension=formato,
            quality_choice=calidad,
            destination_dir=str(destino),
        )

        # Limpiar campos de entrada de inmediato antes o al emitir para respuesta instantánea
        self.txt_url.clear()
        self.txt_nombre.clear()
        self.lbl_chip.setText(t("waiting_url"))
        self.txt_url.setFocus()

        # Emitir señal con copia inmutable
        self.descarga_solicitada.emit(opciones, plataforma)

    def actualizar_textos_idioma(self) -> None:
        """Refresca todas las etiquetas cuando cambia el idioma preservando selección y texto."""
        self.lbl_url.setText(t("url_label"))
        self.txt_url.setPlaceholderText(t("url_placeholder"))
        self.lbl_nombre.setText(t("name_label"))
        self.txt_nombre.setPlaceholderText(t("name_placeholder"))
        self.lbl_tipo.setText(t("type_label"))
        self.lbl_formato.setText(t("format_label"))
        self.lbl_carpeta.setText(t("folder_label"))
        self.btn_examinar.setText(t("btn_browse"))
        self.btn_abrir_carpeta.setText(t("btn_open_folder"))
        self.btn_anadir.setText(t("btn_add_to_queue"))

        if not self.lbl_error_url.isHidden():
            self.lbl_error_url.setText(t("url_error_invalid"))
        if not self.lbl_error_carpeta.isHidden():
            self.lbl_error_carpeta.setText(t("folder_error_invalid"))

        # Actualizar textos del combo tipo bloqueando señales para no reiniciar formato/calidad
        self.cmb_tipo.blockSignals(True)
        self.cmb_tipo.setItemText(0, t("type_video"))
        self.cmb_tipo.setItemText(1, t("type_audio"))
        self.cmb_tipo.blockSignals(False)

        formato_actual = self.cmb_formato.currentData()
        calidad_actual = self.cmb_calidad.currentData()
        self._poblar_calidades(formato_actual, preservar_calidad=calidad_actual)
        self.lbl_chip.setText(estimar_plataforma_url(self.txt_url.text()))
