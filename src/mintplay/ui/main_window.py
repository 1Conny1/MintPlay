"""Ventana principal de MintPlay con soporte bilingüe, iconos SVG propios, temas y tamaño adaptativo."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import QRect, QSize, Qt, Signal
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
from ..services.persistence import (
    es_carpeta_destino_valida,
    guardar_configuracion,
    normalizar_configuracion_usuario,
    restablecer_opciones_descarga,
)
from ..services.queue_manager import GestorCola
from ..services.runtime_paths import obtener_ruta_icono
from .download_form import FormularioDescarga
from .history_dialog import DialogoHistorial
from .i18n_manager import GestorTraduccion, confirmar_accion_si_no, obtener_traductor, t
from .notifications import GestorNotificaciones
from .queue_panel import PanelCola
from .settings_dialog import DialogoAjustes
from .theme import (
    cargar_icono_svg,
    generar_hoja_estilos,
    normalizar_preferencias_tema,
)

logger = logging.getLogger(__name__)


class VentanaPrincipal(QMainWindow):
    """Ventana principal de escritorio para MintPlay."""

    tema_cambiado = Signal(str, str)  # (modo, paleta)

    def __init__(
        self,
        gestor_cola: GestorCola,
        configuracion: Dict[str, Any],
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.gestor = gestor_cola
        carpeta_cruda = configuracion.get("directorio_descargas")
        carpeta_fue_restaurada = bool(
            configuracion.get("carpeta_restaurada_por_invalida", False)
        )
        if (
            isinstance(carpeta_cruda, str)
            and carpeta_cruda.strip()
            and not es_carpeta_destino_valida(carpeta_cruda.strip())
        ):
            carpeta_fue_restaurada = True

        self.config = normalizar_configuracion_usuario(configuracion)
        if carpeta_fue_restaurada:
            self.config["carpeta_restaurada_por_invalida"] = True

        self._dialogo_historial: Optional[DialogoHistorial] = None
        self._dialogo_ajustes: Optional[DialogoAjustes] = None
        self.traductor: GestorTraduccion = obtener_traductor(self.config.get("idioma", "es"))
        self.traductor.cambiar_idioma(self.config.get("idioma", "es"))

        self.setWindowTitle(t("app_name"))
        self._configurar_icono()

        # Gestor de notificaciones del sistema conectado a transiciones terminales verificadas
        self.notificaciones = GestorNotificaciones(
            self,
            activas=bool(self.config.get("notificaciones_activas", True)),
        )
        self.gestor.trabajo_completado_notificable.connect(
            self.notificaciones.notificar_completado
        )
        self.gestor.trabajo_fallido_notificable.connect(
            self.notificaciones.notificar_fallido
        )

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
        paleta_inicial = self.config.get("paleta", "mint")
        dir_descargas = self.config.get("directorio_descargas", str(Path.home() / "Downloads"))
        self.formulario = FormularioDescarga(
            dir_descargas,
            self,
            config_inicial=self.config,
        )
        self.panel_cola = PanelCola(
            self.gestor,
            self,
            tema_inicial=tema_inicial,
            paleta_inicial=paleta_inicial,
        )

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

        # Aplicar estilo e iconos vectoriales iniciales (paleta + modo)
        self._aplicar_tema(tema_inicial, paleta_inicial)

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

        # Conmutador de modo claro/oscuro con iconos SVG propios (sun.svg / moon.svg)
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

    def _actualizar_iconos_barra_superior(
        self,
        tema: str,
        paleta: Optional[str] = None,
    ) -> None:
        """Asigna los iconos SVG vectoriales de historial, sol, luna y ajustes según paleta y modo."""
        paleta_norm, modo_norm = normalizar_preferencias_tema(
            tema,
            paleta or self.config.get("paleta", "mint"),
        )
        es_oscuro = modo_norm == "dark"
        svg_tema = "sun.svg" if es_oscuro else "moon.svg"
        tooltip_tema = t("tooltip_theme_to_light") if es_oscuro else t("tooltip_theme_to_dark")

        self.btn_historial.setText(f" {t('btn_history')}")
        self.btn_historial.setIcon(
            cargar_icono_svg("history.svg", tema=modo_norm, tamano=16, paleta=paleta_norm)
        )
        self.btn_historial.setToolTip(t("tooltip_history"))
        self.btn_historial.setAccessibleName(t("history_title"))

        self.btn_tema.setText("")
        self.btn_tema.setIcon(
            cargar_icono_svg(svg_tema, tema=modo_norm, tamano=18, paleta=paleta_norm)
        )
        self.btn_tema.setToolTip(tooltip_tema)
        self.btn_tema.setAccessibleName(tooltip_tema)

        self.btn_ajustes.setText("")
        self.btn_ajustes.setIcon(
            cargar_icono_svg("settings.svg", tema=modo_norm, tamano=18, paleta=paleta_norm)
        )
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

    def _sincronizar_preferencias_formulario_en_config(self) -> None:
        """Sincroniza en memoria las opciones actuales de vídeo, audio y carpeta desde el formulario."""
        prefs = self.formulario.exportar_preferencias_descarga()
        self.config.update(prefs)

    def _al_solicitar_descarga(self, opciones: OpcionesDescarga, plataforma: str) -> None:
        """Crea el trabajo a partir de las opciones inmutables, lo añade a la cola y persiste las opciones usadas."""
        t_clic = time.perf_counter()
        trabajo = TrabajoDescarga.desde_opciones(opciones, plataforma=plataforma)
        t_creado = time.perf_counter()
        self.gestor.registrar_inicio_clic(trabajo.id, t_clic=t_clic, t_objeto_creado=t_creado)
        # 1. Insertar primero en la cola para no retrasar el alta visual ni el primer repintado
        self.gestor.anadir_trabajo(trabajo)
        # 2. Guardar las opciones vigentes del formulario y la carpeta válida
        self._sincronizar_preferencias_formulario_en_config()
        guardar_configuracion(self.config)

    def restablecer_opciones_descarga(self) -> None:
        """Restablece las opciones del formulario y su configuración a los valores predeterminados."""
        self.config = restablecer_opciones_descarga(self.config)
        self.formulario.aplicar_preferencias_desde_config(self.config)
        guardar_configuracion(self.config)

    def _alternar_idioma(self) -> None:
        nuevo = "en" if self.traductor.idioma == "es" else "es"
        self.traductor.cambiar_idioma(nuevo)
        self.config["idioma"] = nuevo
        self._sincronizar_preferencias_formulario_en_config()
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
        self._actualizar_iconos_barra_superior(
            self.config.get("tema", "dark"),
            self.config.get("paleta", "mint"),
        )

        if self._tabs_compactas:
            self._tabs_compactas.setTabText(0, t("tab_add"))
            self._tabs_compactas.setTabText(1, t("tab_queue"))

    def _alternar_tema(self) -> None:
        """Alterna únicamente el modo (light/dark) conservando la paleta de color elegida."""
        tema_actual = self.config.get("tema", "dark")
        paleta_actual = self.config.get("paleta", "mint")
        nuevo_tema = "light" if tema_actual == "dark" else "dark"
        self.config["tema"] = nuevo_tema
        self._aplicar_tema(nuevo_tema, paleta_actual)
        self._sincronizar_preferencias_formulario_en_config()
        guardar_configuracion(self.config)

    def cambiar_paleta(self, nueva_paleta: str) -> None:
        """Cambia la paleta de color conservando el modo actual y persiste."""
        modo_actual = self.config.get("tema", "dark")
        self._aplicar_tema(modo_actual, nueva_paleta)
        self._sincronizar_preferencias_formulario_en_config()
        guardar_configuracion(self.config)

    def cambiar_modo_tema(self, nuevo_modo: str) -> None:
        """Cambia el modo claro/oscuro conservando la paleta actual y persiste."""
        paleta_actual = self.config.get("paleta", "mint")
        self._aplicar_tema(nuevo_modo, paleta_actual)
        self._sincronizar_preferencias_formulario_en_config()
        guardar_configuracion(self.config)

    def _aplicar_tema(self, tema: str, paleta: Optional[str] = None) -> None:
        paleta_norm, modo_norm = normalizar_preferencias_tema(
            tema,
            paleta if paleta is not None else self.config.get("paleta", "mint"),
        )
        self.config["paleta"] = paleta_norm
        self.config["tema"] = modo_norm
        self.setStyleSheet(generar_hoja_estilos(modo_norm, paleta_norm))
        self._actualizar_iconos_barra_superior(modo_norm, paleta_norm)
        self.panel_cola.actualizar_tema(modo_norm, paleta_norm)
        if self._dialogo_historial is not None:
            self._dialogo_historial.actualizar_tema(modo_norm, paleta_norm)
        if self._dialogo_ajustes is not None:
            self._dialogo_ajustes.actualizar_tema(modo_norm, paleta_norm)
        self.tema_cambiado.emit(modo_norm, paleta_norm)

    def _abrir_historial(self) -> DialogoHistorial:
        """Abre o enfoca la ventana secundaria del historial local de descargas."""
        tema_actual = self.config.get("tema", "dark")
        paleta_actual = self.config.get("paleta", "mint")
        if self._dialogo_historial is None:
            self._dialogo_historial = DialogoHistorial(
                self.gestor.historial,
                self,
                tema_inicial=tema_actual,
                paleta_inicial=paleta_actual,
            )
            self._dialogo_historial.redescarga_solicitada.connect(
                self._al_solicitar_descarga
            )
        else:
            self._dialogo_historial.actualizar_tema(tema_actual, paleta_actual)
            self._dialogo_historial.revalidar_existencia_archivos()

        self._dialogo_historial.show()
        self._dialogo_historial.raise_()
        self._dialogo_historial.activateWindow()
        return self._dialogo_historial

    def _abrir_ajustes(self) -> None:
        self._sincronizar_preferencias_formulario_en_config()
        dlg = DialogoAjustes(self.config, self)
        self._dialogo_ajustes = dlg
        dlg.restablecer_opciones_solicitado.connect(self.restablecer_opciones_descarga)
        dlg.configuracion_guardada.connect(self._al_actualizar_ajustes)
        try:
            dlg.exec()
        finally:
            self._dialogo_ajustes = None

    def _al_actualizar_ajustes(self, nuevos_ajustes: Dict[str, Any]) -> None:
        idioma_anterior = self.config.get("idioma")
        tema_anterior = self.config.get("tema")
        paleta_anterior = self.config.get("paleta")
        self.config = normalizar_configuracion_usuario(dict(nuevos_ajustes))
        self.notificaciones.establecer_activas(
            bool(self.config.get("notificaciones_activas", True))
        )
        guardar_configuracion(self.config)

        nuevo_idioma = self.config.get("idioma", "es")
        if nuevo_idioma != idioma_anterior or self.traductor.idioma != nuevo_idioma:
            self.traductor.cambiar_idioma(nuevo_idioma)
        else:
            self._al_cambiar_idioma(nuevo_idioma)

        nuevo_tema = self.config.get("tema", "dark")
        nueva_paleta = self.config.get("paleta", "mint")
        if nuevo_tema != tema_anterior or nueva_paleta != paleta_anterior:
            self._aplicar_tema(nuevo_tema, nueva_paleta)

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

        self._sincronizar_preferencias_formulario_en_config()
        guardar_configuracion(self.config)
        self.notificaciones.cerrar()
        self.gestor.cerrar()
        event.accept()
