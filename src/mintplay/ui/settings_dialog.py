"""Diálogo de configuración, diagnóstico y preferencias de MintPlay."""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..services.diagnostics import DiagnosticoSistema, ejecutar_diagnostico
from .i18n_manager import t

_CACHE_DIAGNOSTICO: Optional[DiagnosticoSistema] = None


class DialogoAjustes(QDialog):
    """Diálogo modal para cambiar tema, idioma, carpeta y verificar componentes."""

    configuracion_guardada = Signal(dict)

    def __init__(self, config_actual: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(t("settings_title"))
        self.setMinimumWidth(500)
        self.setModal(True)

        self._config = dict(config_actual)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Grupo: Preferencias generales
        self.grupo_general = QGroupBox(t("settings_title"))
        layout_gen = QVBoxLayout(self.grupo_general)
        layout_gen.setSpacing(12)

        # Idioma
        fila_idioma = QHBoxLayout()
        self.lbl_idioma = QLabel(t("settings_language"))
        self.cmb_idioma = QComboBox()
        self.cmb_idioma.addItem("Español (es)", "es")
        self.cmb_idioma.addItem("English (en)", "en")
        idx_lang = self.cmb_idioma.findData(self._config.get("idioma", "es"))
        if idx_lang >= 0:
            self.cmb_idioma.setCurrentIndex(idx_lang)
        fila_idioma.addWidget(self.lbl_idioma)
        fila_idioma.addStretch(1)
        fila_idioma.addWidget(self.cmb_idioma)
        layout_gen.addLayout(fila_idioma)

        # Tema
        fila_tema = QHBoxLayout()
        self.lbl_tema = QLabel(t("settings_theme"))
        self.cmb_tema = QComboBox()
        self.cmb_tema.addItem(t("settings_theme_dark"), "dark")
        self.cmb_tema.addItem(t("settings_theme_light"), "light")
        idx_tema = self.cmb_tema.findData(self._config.get("tema", "dark"))
        if idx_tema >= 0:
            self.cmb_tema.setCurrentIndex(idx_tema)
        fila_tema.addWidget(self.lbl_tema)
        fila_tema.addStretch(1)
        fila_tema.addWidget(self.cmb_tema)
        layout_gen.addLayout(fila_tema)

        # Carpeta predeterminada
        self.lbl_carpeta = QLabel(t("settings_default_folder"))
        layout_gen.addWidget(self.lbl_carpeta)

        fila_carpeta = QHBoxLayout()
        self.txt_carpeta = QLineEdit(self._config.get("directorio_descargas", ""))
        self.txt_carpeta.setReadOnly(True)
        self.btn_examinar = QPushButton(t("btn_browse"))
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

        # Botones inferiores
        fila_botones = QHBoxLayout()
        fila_botones.addStretch(1)

        self.btn_cerrar = QPushButton(t("btn_close"))
        self.btn_cerrar.setObjectName("btnPrimario")
        self.btn_cerrar.clicked.connect(self._al_guardar_y_cerrar)
        fila_botones.addWidget(self.btn_cerrar)

        layout.addLayout(fila_botones)

        QTimer.singleShot(0, self._cargar_diagnostico)

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

    def _al_guardar_y_cerrar(self) -> None:
        self._config["idioma"] = self.cmb_idioma.currentData()
        self._config["tema"] = self.cmb_tema.currentData()
        self._config["directorio_descargas"] = self.txt_carpeta.text()
        self.configuracion_guardada.connect
        self.configuracion_guardada.emit(self._config)
        self.accept()
