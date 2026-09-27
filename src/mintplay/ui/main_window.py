"""Ventana principal de MintPlay con soporte bilingüe, iconos SVG propios, temas y tamaño adaptativo."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QCloseEvent, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..domain.models import EstadoTrabajo, OpcionesDescarga, TrabajoDescarga
from ..services.persistence import guardar_configuracion
from ..services.queue_manager import GestorCola
from ..services.runtime_paths import obtener_ruta_icono
from .download_form import FormularioDescarga
from .history_dialog import DialogoHistorial
from .i18n_manager import GestorTraduccion, confirmar_accion_si_no, obtener_traductor, t
from .queue_panel import PanelCola
from .settings_dialog import DialogoAjustes
from .theme import cargar_icono_svg, generar_hoja_estilos

logger = logging.getLogger(__name__)


class VentanaPrincipal(QMainWindow):
    """Ventana principal de escritorio para MintPlay."""

    def __init__(
        self,
        gestor_cola: GestorCola,
        configuracion: Dict[str, Any],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.gestor = gestor_cola
        self.config = configuracion
        self._dialogo_historial: Optional[DialogoHistorial] = None
        self._dialogo_ajustes: Optional[DialogoAjustes] = None
        self.traductor: GestorTraduccion = obtener_traductor(self.config.get("idioma", "es"))
        self.traductor.cambiar_idioma(self.config.get("idioma", "es"))

        self.setWindowTitle(t("app_name"))
        self._configurar_icono()

        # Widget central y layout
        self.widget_central = QWidget(self)
        self.setCentralWidget(self.widget_central)
        self.layout_raiz = QVBoxLayout(self.widget_central)
        self.layout_raiz.setContentsMargins(22, 16, 22, 20)
        self.layout_raiz.setSpacing(14)

        # Encabezado compacto con iconos SVG coherentes
        self._construir_encabezado()

        # Contenedor de contenido (dos superficies o pestañas según resolución)
        self.contenedor_contenido = QWidget()
        self.layout_contenido = QHBoxLayout(self.contenedor_contenido)
        self.layout_contenido.setContentsMargins(0, 0, 0, 0)
        self.layout_contenido.setSpacing(14)

        # Paneles principales
        tema_inicial = self.config.get("tema", "dark")
        dir_descargas = self.config.get("directorio_descargas", str(Path.home() / "Downloads"))
        self.formulario = FormularioDescarga(dir_descargas, self)
        self.panel_cola = PanelCola(self.gestor, self, tema_inicial=tema_inicial)

        self.formulario.descarga_solicitada.connect(self._al_solicitar_descarga)

        # Divisor discreto entre superficies
        self.separador = QFrame()
        self.separador.setObjectName("separadorColumnas")
        self.separador.setFrameShape(QFrame.NoFrame)

        # Construir estructura
        self._es_modo_compacto = False
        self._tabs_compactas: Optional[QTabWidget] = None
        self._montar_distribucion()

        self.layout_raiz.addWidget(self.contenedor_contenido, 1)

        # Aplicar estilo e iconos vectoriales iniciales
        self._aplicar_tema(tema_inicial)

        # Conectar cambio de idioma
        self.traductor.idioma_cambiado.connect(self._al_cambiar_idioma)

        # Adaptación fija de pantalla
        self._adaptar_dimensiones_a_pantalla()

    def _configurar_icono(self) -> None:
        ruta_ico = obtener_ruta_icono("app.png")
        if ruta_ico.exists():
            self.setWindowIcon(QIcon(str(ruta_ico)))

    def _construir_encabezado(self) -> None:
        fila_encabezado = QHBoxLayout()
        fila_encabezado.setSpacing(10)

        col_marca = QVBoxLayout()
        col_marca.setSpacing(1)

        self.lbl_marca = QLabel(t("app_name"))
        self.lbl_marca.setObjectName("tituloPrincipal")

        self.lbl_subtitulo = QLabel(t("app_subtitle"))
        self.lbl_subtitulo.setObjectName("subtituloPrincipal")

        col_marca.addWidget(self.lbl_marca)
        col_marca.addWidget(self.lbl_subtitulo)
        fila_encabezado.addLayout(col_marca)

        fila_encabezado.addStretch(1)

        # Acceso discreto al historial local de descargas con icono SVG propio (history.svg)
        self.btn_historial = QPushButton(f" {t('btn_history')}")
        self.btn_historial.setObjectName("btnBarraSuperior")
        self.btn_historial.setToolTip(t("tooltip_history"))
        self.btn_historial.setAccessibleName(t("history_title"))
        self.btn_historial.setFixedHeight(36)
        self.btn_historial.setIconSize(QSize(16, 16))
        self.btn_historial.setCursor(Qt.PointingHandCursor)
        self.btn_historial.clicked.connect(self._abrir_historial)
        fila_encabezado.addWidget(self.btn_historial)

        # Selector de idioma rápido sincronizado con Ajustes (muestra el idioma activo: Español / English)
        etiqueta_idioma = (
            t("settings_lang_es") if self.traductor.idioma == "es" else t("settings_lang_en")
        )
        self.btn_idioma = QPushButton(etiqueta_idioma)
        self.btn_idioma.setObjectName("btnBarraSuperior")
        self.btn_idioma.setToolTip(t("tooltip_switch_lang"))
        self.btn_idioma.setAccessibleName(t("tooltip_switch_lang"))
        self.btn_idioma.setFixedHeight(36)
        self.btn_idioma.setMinimumWidth(78)
        self.btn_idioma.setCursor(Qt.PointingHandCursor)
        self.btn_idioma.clicked.connect(self._alternar_idioma)
        fila_encabezado.addWidget(self.btn_idioma)

        # Conmutador de tema con iconos SVG propios (sun.svg / moon.svg)
        self.btn_tema = QPushButton("")
        self.btn_tema.setObjectName("btnBarraSuperior")
        self.btn_tema.setFixedSize(40, 36)
        self.btn_tema.setIconSize(QSize(18, 18))
        self.btn_tema.setCursor(Qt.PointingHandCursor)
        self.btn_tema.clicked.connect(self._alternar_tema)
        fila_encabezado.addWidget(self.btn_tema)

        # Botón de ajustes con icono SVG propio (settings.svg)
        self.btn_ajustes = QPushButton("")
        self.btn_ajustes.setObjectName("btnBarraSuperior")
        self.btn_ajustes.setToolTip(t("tooltip_settings"))
        self.btn_ajustes.setAccessibleName(t("settings_title"))
        self.btn_ajustes.setFixedSize(40, 36)
        self.btn_ajustes.setIconSize(QSize(18, 18))
        self.btn_ajustes.setCursor(Qt.PointingHandCursor)
        self.btn_ajustes.clicked.connect(self._abrir_ajustes)
        fila_encabezado.addWidget(self.btn_ajustes)

        self.layout_raiz.addLayout(fila_encabezado)

    def _actualizar_iconos_barra_superior(self, tema: str) -> None:
        """Asigna los iconos SVG vectoriales de historial, sol, luna y ajustes según el tema."""
        es_oscuro = tema == "dark"
        svg_tema = "sun.svg" if es_oscuro else "moon.svg"
        tooltip_tema = t("tooltip_theme_to_light") if es_oscuro else t("tooltip_theme_to_dark")

        self.btn_historial.setText(f" {t('btn_history')}")
        self.btn_historial.setIcon(cargar_icono_svg("history.svg", tema=tema, tamano=16))
        self.btn_historial.setToolTip(t("tooltip_history"))
        self.btn_historial.setAccessibleName(t("history_title"))

        self.btn_tema.setText("")
        self.btn_tema.setIcon(cargar_icono_svg(svg_tema, tema=tema, tamano=18))
        self.btn_tema.setToolTip(tooltip_tema)
        self.btn_tema.setAccessibleName(tooltip_tema)

        self.btn_ajustes.setText("")
        self.btn_ajustes.setIcon(cargar_icono_svg("settings.svg", tema=tema, tamano=18))
        self.btn_ajustes.setToolTip(t("tooltip_settings"))
        self.btn_ajustes.setAccessibleName(t("settings_title"))

    def _montar_distribucion(self) -> None:
        """Monta la vista en dos paneles proporcionados o en pestañas si la pantalla es reducida."""
        while self.layout_contenido.count():
            item = self.layout_contenido.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        if self._es_modo_compacto:
            self._tabs_compactas = QTabWidget()
            self._tabs_compactas.addTab(self.formulario, t("tab_add"))
            self._tabs_compactas.addTab(self.panel_cola, t("tab_queue"))
            self.layout_contenido.addWidget(self._tabs_compactas)
        else:
            self._tabs_compactas = None
            # Distribución porcentual: formulario 42%, cola 58%
            self.layout_contenido.addWidget(self.formulario, 42)
            self.layout_contenido.addWidget(self.panel_cola, 58)

    def _adaptar_dimensiones_a_pantalla(self) -> None:
        """Calcula el tamaño fijo óptimo respetando los límites de la pantalla disponible."""
        pantalla = QGuiApplication.primaryScreen()
        if not pantalla:
            self.setFixedSize(1060, 680)
            return

        geom: QRect = pantalla.availableGeometry()
        margen = 32
        ancho_disp = geom.width() - (margen * 2)
        alto_disp = geom.height() - (margen * 2)

        debe_ser_compacto = (ancho_disp < 880) or (alto_disp < 640)
        if debe_ser_compacto != self._es_modo_compacto:
            self._es_modo_compacto = debe_ser_compacto
            self._montar_distribucion()

        ancho_ideal = 760 if self._es_modo_compacto else 1060
        alto_ideal = 580 if self._es_modo_compacto else 680

        ancho_final = min(ancho_ideal, ancho_disp)
        alto_final = min(alto_ideal, alto_disp)

        self.setFixedSize(ancho_final, alto_final)

        x = geom.x() + (geom.width() - ancho_final) // 2
        y = geom.y() + (geom.height() - alto_final) // 2
        self.move(x, y)

    def _al_solicitar_descarga(self, opciones: OpcionesDescarga, plataforma: str) -> None:
        """Crea el trabajo a partir de las opciones inmutables y lo añade de inmediato a la cola."""
        t_clic = time.perf_counter()
        trabajo = TrabajoDescarga.desde_opciones(opciones, plataforma=plataforma)
        t_creado = time.perf_counter()
        self.gestor.registrar_inicio_clic(trabajo.id, t_clic=t_clic, t_objeto_creado=t_creado)
        self.gestor.anadir_trabajo(trabajo)

    def _alternar_idioma(self) -> None:
        nuevo = "en" if self.traductor.idioma == "es" else "es"
        self.traductor.cambiar_idioma(nuevo)
        self.config["idioma"] = nuevo
        guardar_configuracion(self.config)

    def _al_cambiar_idioma(self, nuevo_idioma: str) -> None:
        self.config["idioma"] = nuevo_idioma
        self.setWindowTitle(t("app_name"))
        self.lbl_marca.setText(t("app_name"))
        self.lbl_subtitulo.setText(t("app_subtitle"))
        self.btn_idioma.setText(
            t("settings_lang_es") if nuevo_idioma == "es" else t("settings_lang_en")
        )
        self.btn_idioma.setToolTip(t("tooltip_switch_lang"))
        self.btn_idioma.setAccessibleName(t("tooltip_switch_lang"))
        self._actualizar_iconos_barra_superior(self.config.get("tema", "dark"))

        if self._tabs_compactas:
            self._tabs_compactas.setTabText(0, t("tab_add"))
            self._tabs_compactas.setTabText(1, t("tab_queue"))

    def _alternar_tema(self) -> None:
        tema_actual = self.config.get("tema", "dark")
        nuevo_tema = "light" if tema_actual == "dark" else "dark"
        self.config["tema"] = nuevo_tema
        self._aplicar_tema(nuevo_tema)
        guardar_configuracion(self.config)

    def _aplicar_tema(self, tema: str) -> None:
        self.setStyleSheet(generar_hoja_estilos(tema))
        self._actualizar_iconos_barra_superior(tema)
        self.panel_cola.actualizar_tema(tema)
        if self._dialogo_historial is not None:
            self._dialogo_historial.actualizar_tema(tema)
        if self._dialogo_ajustes is not None:
            self._dialogo_ajustes.actualizar_tema(tema)

    def _abrir_historial(self) -> DialogoHistorial:
        """Abre o enfoca la ventana secundaria del historial local de descargas."""
        tema_actual = self.config.get("tema", "dark")
        if self._dialogo_historial is None:
            self._dialogo_historial = DialogoHistorial(
                self.gestor.historial,
                self,
                tema_inicial=tema_actual,
            )
            self._dialogo_historial.redescarga_solicitada.connect(
                self._al_solicitar_descarga
            )
        else:
            self._dialogo_historial.actualizar_tema(tema_actual)
            self._dialogo_historial.revalidar_existencia_archivos()

        self._dialogo_historial.show()
        self._dialogo_historial.raise_()
        self._dialogo_historial.activateWindow()
        return self._dialogo_historial

    def _abrir_ajustes(self) -> None:
        dlg = DialogoAjustes(self.config, self)
        self._dialogo_ajustes = dlg
        dlg.configuracion_guardada.connect(self._al_actualizar_ajustes)
        try:
            dlg.exec()
        finally:
            self._dialogo_ajustes = None

    def _al_actualizar_ajustes(self, nuevos_ajustes: Dict[str, Any]) -> None:
        idioma_anterior = self.config.get("idioma")
        tema_anterior = self.config.get("tema")
        self.config = dict(nuevos_ajustes)
        guardar_configuracion(self.config)

        nuevo_idioma = self.config.get("idioma", "es")
        if nuevo_idioma != idioma_anterior or self.traductor.idioma != nuevo_idioma:
            self.traductor.cambiar_idioma(nuevo_idioma)
        else:
            self._al_cambiar_idioma(nuevo_idioma)

        nuevo_tema = self.config.get("tema", "dark")
        if nuevo_tema != tema_anterior:
            self._aplicar_tema(nuevo_tema)

        if "directorio_descargas" in self.config:
            self.formulario.establecer_directorio_destino(self.config["directorio_descargas"])

    def closeEvent(self, event: QCloseEvent) -> None:
        """Controla el cierre de la ventana protegiendo descargas en curso con confirmación traducida."""
        trabajos_activos = [t for t in self.gestor.trabajos if t.status == EstadoTrabajo.ACTIVO]
        if trabajos_activos:
            confirmado = confirmar_accion_si_no(
                self,
                t("confirm_exit_title"),
                t("confirm_exit_message"),
            )
            if not confirmado:
                event.ignore()
                return

        self.gestor.cerrar()
        event.accept()
