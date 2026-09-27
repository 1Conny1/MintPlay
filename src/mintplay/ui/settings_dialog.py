"""Diálogo de configuración, diagnóstico y preferencias de MintPlay."""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..services.diagnostics import DiagnosticoSistema, ejecutar_diagnostico
from .i18n_manager import obtener_traductor, t
from .theme import generar_hoja_estilos

_CACHE_DIAGNOSTICO: Optional[DiagnosticoSistema] = None


class DialogoAjustes(QDialog):
    """Diálogo de preferencias con selección segmentada clara y aplicación en caliente."""

    configuracion_guardada = Signal(dict)

    def __init__(self, config_actual: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._config = dict(config_actual)
        self._traductor = obtener_traductor(self._config.get("idioma", "es"))

        self.setWindowTitle(t("settings_title"))
        self.setMinimumWidth(520)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Grupo: Preferencias generales
        self.grupo_general = QGroupBox(t("settings_title"))
        layout_gen = QVBoxLayout(self.grupo_general)
        layout_gen.setSpacing(12)

        # 1. Idioma: Control segmentado accesible [Español | English]
        fila_idioma = QHBoxLayout()
        fila_idioma.setSpacing(12)
        self.lbl_idioma = QLabel(t("settings_language"))
        self.lbl_idioma.setObjectName("etiquetaCampo")

        self.marco_idioma = QFrame(self)
        self.marco_idioma.setObjectName("selectorSegmentado")
        layout_seg_idioma = QHBoxLayout(self.marco_idioma)
        layout_seg_idioma.setContentsMargins(3, 3, 3, 3)
        layout_seg_idioma.setSpacing(4)

        self.btn_idioma_es = QPushButton(t("settings_lang_es"))
        self.btn_idioma_es.setObjectName("btnSegmento")
        self.btn_idioma_es.setCheckable(True)
        self.btn_idioma_es.setFocusPolicy(Qt.StrongFocus)
        self.btn_idioma_es.setCursor(Qt.PointingHandCursor)
        self.btn_idioma_es.setAccessibleName("Español")

        self.btn_idioma_en = QPushButton(t("settings_lang_en"))
        self.btn_idioma_en.setObjectName("btnSegmento")
        self.btn_idioma_en.setCheckable(True)
        self.btn_idioma_en.setFocusPolicy(Qt.StrongFocus)
        self.btn_idioma_en.setCursor(Qt.PointingHandCursor)
        self.btn_idioma_en.setAccessibleName("English")

        self.grupo_botones_idioma = QButtonGroup(self)
        self.grupo_botones_idioma.setExclusive(True)
        self.grupo_botones_idioma.addButton(self.btn_idioma_es)
        self.grupo_botones_idioma.addButton(self.btn_idioma_en)

        layout_seg_idioma.addWidget(self.btn_idioma_es)
        layout_seg_idioma.addWidget(self.btn_idioma_en)

        fila_idioma.addWidget(self.lbl_idioma)
        fila_idioma.addStretch(1)
        fila_idioma.addWidget(self.marco_idioma)
        layout_gen.addLayout(fila_idioma)

        # 2. Tema visual: Control segmentado accesible [Oscuro | Claro]
        fila_tema = QHBoxLayout()
        fila_tema.setSpacing(12)
        self.lbl_tema = QLabel(t("settings_theme"))
        self.lbl_tema.setObjectName("etiquetaCampo")

        self.marco_tema = QFrame(self)
        self.marco_tema.setObjectName("selectorSegmentado")
        layout_seg_tema = QHBoxLayout(self.marco_tema)
        layout_seg_tema.setContentsMargins(3, 3, 3, 3)
        layout_seg_tema.setSpacing(4)

        self.btn_tema_oscuro = QPushButton(t("settings_theme_dark"))
        self.btn_tema_oscuro.setObjectName("btnSegmento")
        self.btn_tema_oscuro.setCheckable(True)
        self.btn_tema_oscuro.setFocusPolicy(Qt.StrongFocus)
        self.btn_tema_oscuro.setCursor(Qt.PointingHandCursor)

        self.btn_tema_claro = QPushButton(t("settings_theme_light"))
        self.btn_tema_claro.setObjectName("btnSegmento")
        self.btn_tema_claro.setCheckable(True)
        self.btn_tema_claro.setFocusPolicy(Qt.StrongFocus)
        self.btn_tema_claro.setCursor(Qt.PointingHandCursor)

        self.grupo_botones_tema = QButtonGroup(self)
        self.grupo_botones_tema.setExclusive(True)
        self.grupo_botones_tema.addButton(self.btn_tema_oscuro)
        self.grupo_botones_tema.addButton(self.btn_tema_claro)

        layout_seg_tema.addWidget(self.btn_tema_oscuro)
        layout_seg_tema.addWidget(self.btn_tema_claro)

        fila_tema.addWidget(self.lbl_tema)
        fila_tema.addStretch(1)
        fila_tema.addWidget(self.marco_tema)
        layout_gen.addLayout(fila_tema)

        # 3. Carpeta predeterminada
        self.lbl_carpeta = QLabel(t("settings_default_folder"))
        self.lbl_carpeta.setObjectName("etiquetaCampo")
        layout_gen.addWidget(self.lbl_carpeta)

        fila_carpeta = QHBoxLayout()
        self.txt_carpeta = QLineEdit(self._config.get("directorio_descargas", ""))
        self.txt_carpeta.setReadOnly(True)
        self.txt_carpeta.setToolTip(self._config.get("directorio_descargas", ""))
        self.btn_examinar = QPushButton(t("btn_browse"))
        self.btn_examinar.setCursor(Qt.PointingHandCursor)
        self.btn_examinar.clicked.connect(self._seleccionar_carpeta)
        fila_carpeta.addWidget(self.txt_carpeta, 1)
        fila_carpeta.addWidget(self.btn_examinar)
        layout_gen.addLayout(fila_carpeta)

        layout.addWidget(self.grupo_general)

        # Grupo: Diagnóstico de componentes
        self.grupo_diag = QGroupBox(t("settings_diagnostics"))
        layout_diag = QVBoxLayout(self.grupo_diag)
        layout_diag.setSpacing(6)

        self.lbl_diag_ffmpeg = QLabel(f"<b>{t('settings_ffmpeg')}</b> …")
        self.lbl_diag_ffprobe = QLabel(f"<b>{t('settings_ffprobe')}</b> …")
        self.lbl_diag_js = QLabel(f"<b>{t('settings_js_runtime')}</b> …")

        self.lbl_diag_ffmpeg.setObjectName("infoTecnicaTarjeta")
        self.lbl_diag_ffprobe.setObjectName("infoTecnicaTarjeta")
        self.lbl_diag_js.setObjectName("infoTecnicaTarjeta")

        layout_diag.addWidget(self.lbl_diag_ffmpeg)
        layout_diag.addWidget(self.lbl_diag_ffprobe)
        layout_diag.addWidget(self.lbl_diag_js)
        layout.addWidget(self.grupo_diag)

        # Grupo: Acerca de y uso responsable
        self.grupo_about = QGroupBox(t("settings_about"))
        layout_about = QVBoxLayout(self.grupo_about)

        self.lbl_disclaimer = QLabel(t("settings_disclaimer"))
        self.lbl_disclaimer.setObjectName("etiquetaAyuda")
        self.lbl_disclaimer.setWordWrap(True)
        layout_about.addWidget(self.lbl_disclaimer)
        layout.addWidget(self.grupo_about)

        # Botón inferior: Cerrar / Close (ya que las preferencias se aplican al instante)
        fila_botones = QHBoxLayout()
        fila_botones.addStretch(1)

        self.btn_cerrar = QPushButton(t("btn_close"))
        self.btn_cerrar.setObjectName("btnPrimario")
        self.btn_cerrar.setCursor(Qt.PointingHandCursor)
        self.btn_cerrar.clicked.connect(self._al_guardar_y_cerrar)
        fila_botones.addWidget(self.btn_cerrar)

        layout.addLayout(fila_botones)

        # Estado inicial de controles segmentados
        self._sincronizar_controles_desde_config()
        self.actualizar_tema(self._config.get("tema", "dark"))

        # Conexiones de aplicación inmediata
        self.btn_idioma_es.clicked.connect(lambda: self.seleccionar_idioma("es"))
        self.btn_idioma_en.clicked.connect(lambda: self.seleccionar_idioma("en"))
        self.btn_tema_oscuro.clicked.connect(lambda: self.seleccionar_tema("dark"))
        self.btn_tema_claro.clicked.connect(lambda: self.seleccionar_tema("light"))

        # Sincronización bidireccional si el idioma cambia desde el encabezado
        self._traductor.idioma_cambiado.connect(self._al_cambiar_idioma_externo)

        QTimer.singleShot(0, self._cargar_diagnostico)

    def _sincronizar_controles_desde_config(self) -> None:
        idioma = self._config.get("idioma", "es")
        tema = self._config.get("tema", "dark")

        self.btn_idioma_es.blockSignals(True)
        self.btn_idioma_en.blockSignals(True)
        self.btn_idioma_es.setChecked(idioma == "es")
        self.btn_idioma_en.setChecked(idioma == "en")
        self.btn_idioma_es.blockSignals(False)
        self.btn_idioma_en.blockSignals(False)

        self.btn_tema_oscuro.blockSignals(True)
        self.btn_tema_claro.blockSignals(True)
        self.btn_tema_oscuro.setChecked(tema == "dark")
        self.btn_tema_claro.setChecked(tema == "light")
        self.btn_tema_oscuro.blockSignals(False)
        self.btn_tema_claro.blockSignals(False)

    def seleccionar_idioma(self, nuevo_idioma: str) -> None:
        """Aplica el cambio de idioma al instante en toda la aplicación y persiste."""
        if nuevo_idioma not in ("es", "en"):
            return
        self._config["idioma"] = nuevo_idioma
        self._sincronizar_controles_desde_config()
        self._traductor.cambiar_idioma(nuevo_idioma)
        self.retraducir()
        self.configuracion_guardada.emit(dict(self._config))

    def seleccionar_tema(self, nuevo_tema: str) -> None:
        """Aplica el cambio de tema al instante en toda la aplicación y persiste."""
        if nuevo_tema not in ("dark", "light"):
            return
        self._config["tema"] = nuevo_tema
        self._sincronizar_controles_desde_config()
        self.actualizar_tema(nuevo_tema)
        self.configuracion_guardada.emit(dict(self._config))

    def actualizar_tema(self, tema: str) -> None:
        """Actualiza la hoja de estilos del diálogo de ajustes según el tema."""
        self._config["tema"] = tema
        self._sincronizar_controles_desde_config()
        self.setStyleSheet(generar_hoja_estilos(tema))

    def _al_cambiar_idioma_externo(self, nuevo_idioma: str) -> None:
        self._config["idioma"] = nuevo_idioma
        self._sincronizar_controles_desde_config()
        self.retraducir()

    def retraducir(self) -> None:
        """Actualiza todos los textos traducibles del diálogo de ajustes en vivo."""
        self.setWindowTitle(t("settings_title"))
        self.grupo_general.setTitle(t("settings_title"))
        self.lbl_idioma.setText(t("settings_language"))
        self.btn_idioma_es.setText(t("settings_lang_es"))
        self.btn_idioma_en.setText(t("settings_lang_en"))
        self.lbl_tema.setText(t("settings_theme"))
        self.btn_tema_oscuro.setText(t("settings_theme_dark"))
        self.btn_tema_claro.setText(t("settings_theme_light"))
        self.lbl_carpeta.setText(t("settings_default_folder"))
        self.btn_examinar.setText(t("btn_browse"))
        self.grupo_diag.setTitle(t("settings_diagnostics"))
        self.grupo_about.setTitle(t("settings_about"))
        self.lbl_disclaimer.setText(t("settings_disclaimer"))
        self.btn_cerrar.setText(t("btn_close"))
        self._cargar_diagnostico()

    def _cargar_diagnostico(self) -> None:
        global _CACHE_DIAGNOSTICO
        if _CACHE_DIAGNOSTICO is None:
            _CACHE_DIAGNOSTICO = ejecutar_diagnostico()
        diag = _CACHE_DIAGNOSTICO
        no_disp = t("settings_not_available")

        self.lbl_diag_ffmpeg.setText(
            f"<b>{t('settings_ffmpeg')}</b> "
            f"{'✓ ' + diag.ffmpeg_version if diag.ffmpeg_disponible else '✗ ' + no_disp}"
        )
        self.lbl_diag_ffprobe.setText(
            f"<b>{t('settings_ffprobe')}</b> "
            f"{'✓ ' + diag.ffprobe_version if diag.ffprobe_disponible else '✗ ' + no_disp}"
        )
        js_texto = (
            f"✓ {diag.js_runtime_nombre} {diag.js_runtime_version}"
            if diag.js_runtime_disponible
            else f"✗ {no_disp}"
        )
        self.lbl_diag_js.setText(f"<b>{t('settings_js_runtime')}</b> {js_texto}")

    def _seleccionar_carpeta(self) -> None:
        actual = self.txt_carpeta.text()
        carpeta = QFileDialog.getExistingDirectory(
            self,
            t("settings_default_folder"),
            actual,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if carpeta:
            self.txt_carpeta.setText(carpeta)
            self.txt_carpeta.setToolTip(carpeta)
            self._config["directorio_descargas"] = carpeta
            self.configuracion_guardada.emit(dict(self._config))

    def _al_guardar_y_cerrar(self) -> None:
        self._config["directorio_descargas"] = self.txt_carpeta.text()
        self.configuracion_guardada.emit(dict(self._config))
        self.accept()
