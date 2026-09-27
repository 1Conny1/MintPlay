"""Diálogo de configuración, diagnóstico y preferencias de MintPlay."""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import QSize, Qt, QTimer, Signal
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
from ..services.persistence import normalizar_configuracion_usuario
from .i18n_manager import obtener_traductor, t
from .theme import (
    MODOS_TEMA,
    PALETAS_IDS,
    crear_icono_muestra_paleta,
    generar_hoja_estilos,
    normalizar_preferencias_tema,
)

_CACHE_DIAGNOSTICO: Optional[DiagnosticoSistema] = None

_CLAVES_I18N_PALETA: Dict[str, str] = {
    "mint": "settings_palette_mint",
    "sakura": "settings_palette_sakura",
    "indigo": "settings_palette_indigo",
    "amber": "settings_palette_amber",
    "ocean": "settings_palette_ocean",
}


class DialogoAjustes(QDialog):
    """Diálogo de preferencias con selección de idioma, paleta de color y modo claro/oscuro en caliente."""

    configuracion_guardada = Signal(dict)

    def __init__(self, config_actual: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._config = normalizar_configuracion_usuario(dict(config_actual))
        self._traductor = obtener_traductor(self._config.get("idioma", "es"))

        self.setWindowTitle(t("settings_title"))
        self.setMinimumWidth(560)
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

        # 2. Paleta de color: 5 identidades con muestra pequeña de acento
        bloque_paleta = QVBoxLayout()
        bloque_paleta.setSpacing(6)
        self.lbl_paleta = QLabel(t("settings_palette"))
        self.lbl_paleta.setObjectName("etiquetaCampo")
        bloque_paleta.addWidget(self.lbl_paleta)

        self.marco_paleta = QFrame(self)
        self.marco_paleta.setObjectName("selectorPaleta")
        layout_seg_paleta = QHBoxLayout(self.marco_paleta)
        layout_seg_paleta.setContentsMargins(4, 4, 4, 4)
        layout_seg_paleta.setSpacing(6)

        self.grupo_botones_paleta = QButtonGroup(self)
        self.grupo_botones_paleta.setExclusive(True)
        self.botones_paleta: Dict[str, QPushButton] = {}

        for paleta_id in PALETAS_IDS:
            clave_i18n = _CLAVES_I18N_PALETA[paleta_id]
            btn = QPushButton(t(clave_i18n))
            btn.setObjectName("btnPaleta")
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.StrongFocus)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setIconSize(QSize(14, 14))
            btn.setAccessibleName(t(clave_i18n))
            btn.clicked.connect(
                lambda _checked=False, pid=paleta_id: self.seleccionar_paleta(pid)
            )
            self.grupo_botones_paleta.addButton(btn)
            self.botones_paleta[paleta_id] = btn
            setattr(self, f"btn_paleta_{paleta_id}", btn)
            layout_seg_paleta.addWidget(btn, 1)

        bloque_paleta.addWidget(self.marco_paleta)
        layout_gen.addLayout(bloque_paleta)

        # 3. Apariencia (modo claro / oscuro): Control segmentado inequívoco [Claro | Oscuro]
        fila_tema = QHBoxLayout()
        fila_tema.setSpacing(12)
        self.lbl_tema = QLabel(t("settings_appearance"))
        self.lbl_tema.setObjectName("etiquetaCampo")

        self.marco_tema = QFrame(self)
        self.marco_tema.setObjectName("selectorSegmentado")
        layout_seg_tema = QHBoxLayout(self.marco_tema)
        layout_seg_tema.setContentsMargins(3, 3, 3, 3)
        layout_seg_tema.setSpacing(4)

        self.btn_tema_claro = QPushButton(t("settings_theme_light"))
        self.btn_tema_claro.setObjectName("btnSegmento")
        self.btn_tema_claro.setCheckable(True)
        self.btn_tema_claro.setFocusPolicy(Qt.StrongFocus)
        self.btn_tema_claro.setCursor(Qt.PointingHandCursor)
        self.btn_tema_claro.setAccessibleName(t("settings_theme_light"))

        self.btn_tema_oscuro = QPushButton(t("settings_theme_dark"))
        self.btn_tema_oscuro.setObjectName("btnSegmento")
        self.btn_tema_oscuro.setCheckable(True)
        self.btn_tema_oscuro.setFocusPolicy(Qt.StrongFocus)
        self.btn_tema_oscuro.setCursor(Qt.PointingHandCursor)
        self.btn_tema_oscuro.setAccessibleName(t("settings_theme_dark"))

        self.grupo_botones_tema = QButtonGroup(self)
        self.grupo_botones_tema.setExclusive(True)
        self.grupo_botones_tema.addButton(self.btn_tema_claro)
        self.grupo_botones_tema.addButton(self.btn_tema_oscuro)

        layout_seg_tema.addWidget(self.btn_tema_claro)
        layout_seg_tema.addWidget(self.btn_tema_oscuro)

        fila_tema.addWidget(self.lbl_tema)
        fila_tema.addStretch(1)
        fila_tema.addWidget(self.marco_tema)
        layout_gen.addLayout(fila_tema)

        # 4. Carpeta predeterminada
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

        # Botón inferior: Cerrar / Close (las preferencias se aplican al instante)
        fila_botones = QHBoxLayout()
        fila_botones.addStretch(1)

        self.btn_cerrar = QPushButton(t("btn_close"))
        self.btn_cerrar.setObjectName("btnPrimario")
        self.btn_cerrar.setCursor(Qt.PointingHandCursor)
        self.btn_cerrar.clicked.connect(self._al_guardar_y_cerrar)
        fila_botones.addWidget(self.btn_cerrar)

        layout.addLayout(fila_botones)

        # Estado inicial de controles
        self._sincronizar_controles_desde_config()
        self.actualizar_tema(
            self._config.get("tema", "dark"),
            self._config.get("paleta", "mint"),
        )

        # Conexiones de aplicación inmediata
        self.btn_idioma_es.clicked.connect(lambda: self.seleccionar_idioma("es"))
        self.btn_idioma_en.clicked.connect(lambda: self.seleccionar_idioma("en"))
        self.btn_tema_claro.clicked.connect(lambda: self.seleccionar_tema("light"))
        self.btn_tema_oscuro.clicked.connect(lambda: self.seleccionar_tema("dark"))

        # Sincronización bidireccional si el idioma o el modo cambian desde el encabezado
        self._traductor.idioma_cambiado.connect(self._al_cambiar_idioma_externo)
        if parent is not None and hasattr(parent, "tema_cambiado"):
            parent.tema_cambiado.connect(self.actualizar_tema)

        QTimer.singleShot(0, self._cargar_diagnostico)

    def _sincronizar_controles_desde_config(self) -> None:
        idioma = self._config.get("idioma", "es")
        paleta, modo = normalizar_preferencias_tema(
            self._config.get("tema", "dark"),
            self._config.get("paleta", "mint"),
        )
        self._config["paleta"] = paleta
        self._config["tema"] = modo

        self.btn_idioma_es.blockSignals(True)
        self.btn_idioma_en.blockSignals(True)
        self.btn_idioma_es.setChecked(idioma == "es")
        self.btn_idioma_en.setChecked(idioma == "en")
        self.btn_idioma_es.blockSignals(False)
        self.btn_idioma_en.blockSignals(False)

        self.btn_tema_claro.blockSignals(True)
        self.btn_tema_oscuro.blockSignals(True)
        self.btn_tema_claro.setChecked(modo == "light")
        self.btn_tema_oscuro.setChecked(modo == "dark")
        self.btn_tema_claro.blockSignals(False)
        self.btn_tema_oscuro.blockSignals(False)

        for pid, btn in self.botones_paleta.items():
            es_sel = pid == paleta
            btn.blockSignals(True)
            btn.setChecked(es_sel)
            btn.setIcon(crear_icono_muestra_paleta(pid, modo=modo, seleccionado=es_sel))
            btn.blockSignals(False)

    def seleccionar_idioma(self, nuevo_idioma: str) -> None:
        """Aplica el cambio de idioma al instante sin alterar la paleta ni el modo."""
        if nuevo_idioma not in ("es", "en"):
            return
        self._config["idioma"] = nuevo_idioma
        self._sincronizar_controles_desde_config()
        self._traductor.cambiar_idioma(nuevo_idioma)
        self.retraducir()
        self.configuracion_guardada.emit(dict(self._config))

    def seleccionar_paleta(self, nueva_paleta: str) -> None:
        """Aplica el cambio de paleta de color al instante conservando el modo claro/oscuro."""
        if nueva_paleta not in PALETAS_IDS:
            return
        self._config["paleta"] = nueva_paleta
        modo_actual = self._config.get("tema", "dark")
        self.actualizar_tema(modo_actual, nueva_paleta)
        self.configuracion_guardada.emit(dict(self._config))

    def seleccionar_tema(self, nuevo_modo: str) -> None:
        """Aplica el cambio de modo (light/dark) al instante conservando la paleta activa."""
        if nuevo_modo not in MODOS_TEMA:
            return
        self._config["tema"] = nuevo_modo
        paleta_actual = self._config.get("paleta", "mint")
        self.actualizar_tema(nuevo_modo, paleta_actual)
        self.configuracion_guardada.emit(dict(self._config))

    seleccionar_modo = seleccionar_tema

    def actualizar_tema(self, tema: str, paleta: Optional[str] = None) -> None:
        """Actualiza la hoja de estilos y muestras del diálogo de ajustes según paleta y modo."""
        paleta_norm, modo_norm = normalizar_preferencias_tema(
            tema,
            paleta if paleta is not None else self._config.get("paleta", "mint"),
        )
        self._config["paleta"] = paleta_norm
        self._config["tema"] = modo_norm
        self._sincronizar_controles_desde_config()
        self.setStyleSheet(generar_hoja_estilos(modo_norm, paleta_norm))

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
        self.lbl_paleta.setText(t("settings_palette"))
        for pid, btn in self.botones_paleta.items():
            etiqueta = t(_CLAVES_I18N_PALETA[pid])
            btn.setText(etiqueta)
            btn.setAccessibleName(etiqueta)
        self.lbl_tema.setText(t("settings_appearance"))
        self.btn_tema_claro.setText(t("settings_theme_light"))
        self.btn_tema_claro.setAccessibleName(t("settings_theme_light"))
        self.btn_tema_oscuro.setText(t("settings_theme_dark"))
        self.btn_tema_oscuro.setAccessibleName(t("settings_theme_dark"))
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
