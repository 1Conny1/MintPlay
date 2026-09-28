"""Formulario de entrada de descargas para MintPlay."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from PySide6.QtCore import Qt, QUrl, Signal
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
    verificar_compatibilidad,
)
from ..domain.models import (
    FormatoAudio,
    OpcionesDescarga,
    TipoMedio,
)
from ..domain.platforms import (
    PLATAFORMA_GENERICA,
    detectar_plataforma_por_url,
    extraer_host_normalizado,
    resolver_plataforma,
)
from ..services.output_paths import sanitizar_nombre_archivo
from ..services.persistence import (
    es_carpeta_destino_valida,
    normalizar_configuracion_usuario,
)
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


def traducir_plataforma(plataforma: str, url: str = "") -> str:
    """Normaliza y traduce el indicador de sitio usando la lógica centralizada de plataformas."""
    resuelta = resolver_plataforma(url=url, plataforma_actual=plataforma)
    if resuelta == PLATAFORMA_GENERICA:
        return t("other_site")
    return resuelta


def estimar_plataforma_url(url: str) -> str:
    """Identifica de forma inmediata y centralizada la plataforma según el dominio/subdominio de la URL."""
    host = extraer_host_normalizado(url)
    if not host:
        return t("waiting_url")

    plataforma = detectar_plataforma_por_url(url)
    if plataforma:
        return plataforma

    return t("other_site")


class FormularioDescarga(QFrame):
    """Panel con los campos para configurar y añadir una nueva descarga."""

    descarga_solicitada = Signal(object, str)  # OpcionesDescarga, plataforma_estimada

    def __init__(
        self,
        directorio_predeterminado: str,
        parent: Optional[QWidget] = None,
        config_inicial: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(parent)
        self.setObjectName("panelFormulario")
        self._directorio_destino = directorio_predeterminado
        self._tipo_actual: TipoMedio = TipoMedio.VIDEO
        self._clave_error_carpeta: Optional[str] = None
        self._preferencias_por_tipo: Dict[TipoMedio, Dict[str, str]] = {
            TipoMedio.VIDEO: {
                "formato": obtener_formato_predeterminado(TipoMedio.VIDEO),
                "calidad": obtener_calidad_predeterminada(
                    obtener_formato_predeterminado(TipoMedio.VIDEO)
                ),
            },
            TipoMedio.AUDIO: {
                "formato": obtener_formato_predeterminado(TipoMedio.AUDIO),
                "calidad": obtener_calidad_predeterminada(
                    obtener_formato_predeterminado(TipoMedio.AUDIO)
                ),
            },
        }

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
        self.cmb_calidad.currentIndexChanged.connect(self._al_cambiar_calidad)
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

        # Fila 6: Botón principal Descargar / Download
        self.btn_anadir = QPushButton(t("btn_add_to_queue"))
        self.btn_anadir.setObjectName("btnPrimario")
        self.btn_anadir.setToolTip(t("tooltip_download_btn"))
        self.btn_anadir.setAccessibleName(t("btn_add_to_queue"))
        self.btn_anadir.setCursor(Qt.PointingHandCursor)
        self.btn_anadir.clicked.connect(self._al_pulsar_anadir)
        layout.addWidget(self.btn_anadir)

        # Inicializar listas dependientes y preferencias recordadas
        if config_inicial is not None:
            self.aplicar_preferencias_desde_config(config_inicial)
        elif not es_carpeta_destino_valida(self._directorio_destino):
            cfg_norm = normalizar_configuracion_usuario(
                {"directorio_descargas": self._directorio_destino}
            )
            self.aplicar_preferencias_desde_config(cfg_norm)
        else:
            self._poblar_formatos(
                TipoMedio.VIDEO,
                preservar_formato=self._preferencias_por_tipo[TipoMedio.VIDEO]["formato"],
                preservar_calidad=self._preferencias_por_tipo[TipoMedio.VIDEO]["calidad"],
            )

        obtener_traductor().idioma_cambiado.connect(self.actualizar_textos_idioma)

    def _guardar_seleccion_actual_en_memoria(self) -> None:
        """Registra en memoria el formato y calidad vigentes del tipo de medio actual si son compatibles."""
        formato = self.cmb_formato.currentData()
        calidad = self.cmb_calidad.currentData()
        if (
            formato
            and calidad
            and verificar_compatibilidad(self._tipo_actual, str(formato), str(calidad))
        ):
            self._preferencias_por_tipo[self._tipo_actual] = {
                "formato": str(formato),
                "calidad": str(calidad),
            }

    def _al_cambiar_url(self, texto: str) -> None:
        self.lbl_error_url.setVisible(False)
        self.lbl_chip.setText(estimar_plataforma_url(texto))

    def _al_cambiar_tipo(self) -> None:
        tipo_val = self.cmb_tipo.currentData()
        if not tipo_val:
            return
        self._guardar_seleccion_actual_en_memoria()
        nuevo_tipo = TipoMedio(tipo_val)
        self._tipo_actual = nuevo_tipo
        pref = self._preferencias_por_tipo.get(nuevo_tipo, {})
        self._poblar_formatos(
            nuevo_tipo,
            preservar_formato=pref.get("formato"),
            preservar_calidad=pref.get("calidad"),
        )

    def _poblar_formatos(
        self,
        tipo: TipoMedio,
        preservar_formato: Optional[str] = None,
        preservar_calidad: Optional[str] = None,
    ) -> None:
        self.cmb_formato.blockSignals(True)
        self.cmb_formato.clear()
        formatos = FORMATOS_POR_TIPO.get(tipo, [])
        for fmt in formatos:
            self.cmb_formato.addItem(fmt.upper(), fmt)

        objetivo = (
            preservar_formato
            if preservar_formato in formatos
            else obtener_formato_predeterminado(tipo)
        )
        idx = self.cmb_formato.findData(objetivo)
        if idx >= 0:
            self.cmb_formato.setCurrentIndex(idx)
        self.cmb_formato.blockSignals(False)

        formato_elegido = self.cmb_formato.currentData()
        calidad_candidata = (
            preservar_calidad
            if preservar_calidad is not None
            else self._preferencias_por_tipo.get(tipo, {}).get("calidad")
        )
        self._poblar_calidades(formato_elegido, preservar_calidad=calidad_candidata)

    def _al_cambiar_formato(self) -> None:
        formato = self.cmb_formato.currentData()
        if formato:
            calidad_previa = self._preferencias_por_tipo.get(self._tipo_actual, {}).get(
                "calidad"
            )
            self._poblar_calidades(formato, preservar_calidad=calidad_previa)

    def _al_cambiar_calidad(self) -> None:
        self._guardar_seleccion_actual_en_memoria()

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
        self._guardar_seleccion_actual_en_memoria()

    def _traducir_etiqueta_calidad(self, cal: str) -> str:
        return traducir_etiqueta_calidad(cal)

    def _mostrar_error_o_aviso_carpeta(self, clave_i18n: str) -> None:
        self._clave_error_carpeta = clave_i18n
        self.lbl_error_carpeta.setText(t(clave_i18n))
        self.lbl_error_carpeta.setVisible(True)

    def _ocultar_error_carpeta(self) -> None:
        self._clave_error_carpeta = None
        self.lbl_error_carpeta.setVisible(False)

    def _seleccionar_carpeta(self) -> None:
        carpeta = QFileDialog.getExistingDirectory(
            self,
            t("folder_label"),
            self._directorio_destino,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if carpeta:
            self.establecer_directorio_destino(carpeta)

    def establecer_directorio_destino(
        self, carpeta: str, mostrar_aviso_restauracion: bool = False
    ) -> None:
        self._directorio_destino = carpeta
        self.txt_carpeta.setText(carpeta)
        self.txt_carpeta.setToolTip(carpeta)
        if mostrar_aviso_restauracion:
            self._mostrar_error_o_aviso_carpeta("folder_warning_reset")
        else:
            self._ocultar_error_carpeta()

    def aplicar_preferencias_desde_config(self, config: Dict[str, Any]) -> None:
        """Restaura el tipo de medio, las opciones por separado de vídeo y audio y la carpeta válida."""
        carpeta_cruda = config.get("directorio_descargas")
        habia_carpeta_invalida = bool(config.get("carpeta_restaurada_por_invalida", False))
        if (
            isinstance(carpeta_cruda, str)
            and carpeta_cruda.strip()
            and not es_carpeta_destino_valida(carpeta_cruda.strip())
        ):
            habia_carpeta_invalida = True

        cfg = normalizar_configuracion_usuario(dict(config))
        self._preferencias_por_tipo[TipoMedio.VIDEO] = {
            "formato": str(cfg["video_formato"]),
            "calidad": str(cfg["video_calidad"]),
        }
        self._preferencias_por_tipo[TipoMedio.AUDIO] = {
            "formato": str(cfg["audio_formato"]),
            "calidad": str(cfg["audio_calidad"]),
        }

        tipo_guardado = (
            TipoMedio.AUDIO
            if cfg.get("ultimo_tipo_medio") == TipoMedio.AUDIO.value
            else TipoMedio.VIDEO
        )
        self._tipo_actual = tipo_guardado

        self.cmb_tipo.blockSignals(True)
        idx_tipo = self.cmb_tipo.findData(tipo_guardado.value)
        if idx_tipo >= 0:
            self.cmb_tipo.setCurrentIndex(idx_tipo)
        self.cmb_tipo.blockSignals(False)

        pref_activa = self._preferencias_por_tipo[tipo_guardado]
        self._poblar_formatos(
            tipo_guardado,
            preservar_formato=pref_activa["formato"],
            preservar_calidad=pref_activa["calidad"],
        )

        self.establecer_directorio_destino(
            str(cfg["directorio_descargas"]),
            mostrar_aviso_restauracion=habia_carpeta_invalida,
        )
        # Nunca restaurar URL ni nombre personalizado
        self.txt_url.clear()
        self.txt_nombre.clear()
        self.lbl_error_url.setVisible(False)
        self.lbl_chip.setText(t("waiting_url"))

    def restablecer_opciones_predeterminadas(
        self, directorio_predeterminado: Optional[str] = None
    ) -> Dict[str, Any]:
        """Restablece en el formulario el tipo de medio, formatos, calidades y carpeta predeterminados."""
        cfg_base: Dict[str, Any] = {}
        if directorio_predeterminado:
            cfg_base["directorio_descargas"] = directorio_predeterminado
        cfg_limpia = normalizar_configuracion_usuario(cfg_base)
        self.aplicar_preferencias_desde_config(cfg_limpia)
        return self.exportar_preferencias_descarga()

    def exportar_preferencias_descarga(self) -> Dict[str, Any]:
        """Exporta el estado actual de preferencias de descarga (sin URL ni nombre de archivo)."""
        self._guardar_seleccion_actual_en_memoria()
        carpeta_exportada = self._directorio_destino
        if not es_carpeta_destino_valida(carpeta_exportada):
            carpeta_exportada = normalizar_configuracion_usuario({})["directorio_descargas"]
        return {
            "ultimo_tipo_medio": self._tipo_actual.value,
            "video_formato": self._preferencias_por_tipo[TipoMedio.VIDEO]["formato"],
            "video_calidad": self._preferencias_por_tipo[TipoMedio.VIDEO]["calidad"],
            "audio_formato": self._preferencias_por_tipo[TipoMedio.AUDIO]["formato"],
            "audio_calidad": self._preferencias_por_tipo[TipoMedio.AUDIO]["calidad"],
            "directorio_descargas": carpeta_exportada,
        }

    def _abrir_carpeta(self) -> None:
        if os.path.exists(self._directorio_destino):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._directorio_destino))

    def _al_pulsar_anadir(self) -> None:
        url = self.txt_url.text().strip()
        self.lbl_error_url.setVisible(False)
        self._ocultar_error_carpeta()

        # Validación sintáctica de URL
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            self.lbl_error_url.setText(t("url_error_invalid"))
            self.lbl_error_url.setVisible(True)
            self.txt_url.setFocus()
            return

        # Validación de carpeta de destino
        destino = Path(self._directorio_destino)
        if not destino.exists() or not os.access(str(destino), os.W_OK):
            self._mostrar_error_o_aviso_carpeta("folder_error_invalid")
            return

        # Saneamiento del nombre opcional
        nombre_ingresado = self.txt_nombre.text().strip()
        nombre_saneado = sanitizar_nombre_archivo(nombre_ingresado) if nombre_ingresado else ""

        tipo = TipoMedio(self.cmb_tipo.currentData())
        formato = self.cmb_formato.currentData()
        calidad = self.cmb_calidad.currentData()
        self._tipo_actual = tipo
        self._guardar_seleccion_actual_en_memoria()
        plataforma = resolver_plataforma(url=url)

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
        self.btn_anadir.setToolTip(t("tooltip_download_btn"))
        self.btn_anadir.setAccessibleName(t("btn_add_to_queue"))

        if not self.lbl_error_url.isHidden():
            self.lbl_error_url.setText(t("url_error_invalid"))
        if not self.lbl_error_carpeta.isHidden():
            clave_err = self._clave_error_carpeta or "folder_error_invalid"
            self.lbl_error_carpeta.setText(t(clave_err))

        # Actualizar textos del combo tipo bloqueando señales para no reiniciar formato/calidad
        self.cmb_tipo.blockSignals(True)
        self.cmb_tipo.setItemText(0, t("type_video"))
        self.cmb_tipo.setItemText(1, t("type_audio"))
        self.cmb_tipo.blockSignals(False)

        formato_actual = self.cmb_formato.currentData()
        calidad_actual = self.cmb_calidad.currentData()
        self._poblar_calidades(formato_actual, preservar_calidad=calidad_actual)
        self.lbl_chip.setText(estimar_plataforma_url(self.txt_url.text()))
