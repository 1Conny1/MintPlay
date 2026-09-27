"""Definición y aplicación de temas visuales claro y oscuro e iconos SVG para MintPlay."""

from __future__ import annotations

from typing import Dict

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from ..services.runtime_paths import obtener_ruta_icono

PALETAS: Dict[str, Dict[str, str]] = {
    "dark": {
        "fondo": "#111A1A",
        "superficie_panel": "#162221",
        "superficie": "#1B2827",
        "superficie_hover": "#233533",
        "superficie_tarjeta": "#1C2B29",
        "superficie_tarjeta_activa": "#1E312E",
        "borde": "#2A3F3C",
        "borde_suave": "#213331",
        "borde_foco": "#79D6B4",
        "texto": "#EEF4F0",
        "texto_secundario": "#B6C8C1",
        "texto_tenue": "#8FA69E",
        "texto_desactivado": "#637A73",
        "acento_menta": "#79D6B4",
        "acento_menta_hover": "#92E2C5",
        "acento_menta_presionado": "#5FC29F",
        "acento_menta_fondo": "#1E3B34",
        "texto_boton_acento": "#0B1715",
        "peligro": "#D66868",
        "peligro_hover": "#E27C7C",
        "peligro_fondo": "#321D1F",
        "peligro_texto": "#FFD6D6",
        "exito": "#79D6B4",
        "exito_fondo": "#1B3830",
        "barra_progreso_fondo": "#253836",
        "separador": "#223432",
    },
    "light": {
        "fondo": "#F5F8F3",
        "superficie_panel": "#FFFFFF",
        "superficie": "#F9FBF8",
        "superficie_hover": "#EDF3EE",
        "superficie_tarjeta": "#FBFCFA",
        "superficie_tarjeta_activa": "#F2F9F6",
        "borde": "#CFDCD4",
        "borde_suave": "#E0EAE4",
        "borde_foco": "#168569",
        "texto": "#192C29",
        "texto_secundario": "#435B54",
        "texto_tenue": "#5E7770",
        "texto_desactivado": "#93A69F",
        "acento_menta": "#168569",
        "acento_menta_hover": "#1B9A7A",
        "acento_menta_presionado": "#116B54",
        "acento_menta_fondo": "#E3F4EE",
        "texto_boton_acento": "#FFFFFF",
        "peligro": "#B33640",
        "peligro_hover": "#C84550",
        "peligro_fondo": "#FDEEEF",
        "peligro_texto": "#8C1D28",
        "exito": "#168569",
        "exito_fondo": "#E3F4EE",
        "barra_progreso_fondo": "#DCE7E0",
        "separador": "#DCE6DF",
    },
}


def obtener_paleta(tema: str = "dark") -> Dict[str, str]:
    """Devuelve el diccionario de colores del tema activo."""
    return PALETAS.get(tema, PALETAS["dark"])


def _obtener_escala_pantalla() -> float:
    app = QGuiApplication.instance()
    if app is not None:
        pantalla = QGuiApplication.primaryScreen()
        if pantalla is not None:
            return max(2.0, float(pantalla.devicePixelRatio()))
    return 2.0


def renderizar_svg_pixmap(
    nombre_svg: str,
    color_trazo: str,
    color_acento: str = "#79D6B4",
    ancho: int = 24,
    alto: int = 24,
) -> QPixmap:
    """Renderiza un archivo SVG de recursos aplicando los colores del tema en alta densidad."""
    ruta = obtener_ruta_icono(nombre_svg)
    escala = _obtener_escala_pantalla()
    w_px = int(ancho * escala)
    h_px = int(alto * escala)

    imagen = QImage(w_px, h_px, QImage.Format_ARGB32_Premultiplied)
    imagen.fill(Qt.transparent)

    if ruta.exists():
        try:
            svg_texto = ruta.read_text(encoding="utf-8")
            svg_coloreado = (
                svg_texto.replace("currentColor", color_trazo)
                .replace("accentColor", color_acento)
            )
            datos = QByteArray(svg_coloreado.encode("utf-8"))
            renderer = QSvgRenderer(datos)
            if renderer.isValid():
                pintor = QPainter(imagen)
                pintor.setRenderHint(QPainter.Antialiasing, True)
                pintor.setRenderHint(QPainter.SmoothPixmapTransform, True)
                renderer.render(pintor, QRectF(0, 0, w_px, h_px))
                pintor.end()
        except Exception:
            pass

    pixmap = QPixmap.fromImage(imagen)
    pixmap.setDevicePixelRatio(escala)
    return pixmap


def cargar_icono_svg(
    nombre_svg: str,
    tema: str = "dark",
    tamano: int = 18,
) -> QIcon:
    """Construye un QIcon vectorial nítido a partir de un SVG coloreado según el tema."""
    paleta = obtener_paleta(tema)
    pixmap = renderizar_svg_pixmap(
        nombre_svg=nombre_svg,
        color_trazo=paleta["texto"],
        color_acento=paleta["acento_menta"],
        ancho=tamano,
        alto=tamano,
    )
    return QIcon(pixmap)


def generar_hoja_estilos(tema: str = "dark") -> str:
    """Genera la hoja de estilos Qt (QSS) completa según la paleta del tema."""
    p = obtener_paleta(tema)

    return f"""
    * {{
        font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Inter', Roboto, sans-serif;
        font-size: 14px;
        color: {p["texto"]};
    }}

    QMainWindow, QDialog {{
        background-color: {p["fondo"]};
    }}

    /* Superficies principales de los dos paneles y del historial */
    QFrame#panelFormulario, QFrame#panelCola, QFrame#panelHistorial, QWidget#panelFormulario, QWidget#panelCola {{
        background-color: {p["superficie_panel"]};
        border: 1px solid {p["borde"]};
        border-radius: 12px;
    }}

    /* Encabezados y jerarquía tipográfica */
    QLabel#tituloPrincipal {{
        font-size: 20px;
        font-weight: 600;
        letter-spacing: -0.3px;
        color: {p["texto"]};
        background: transparent;
    }}

    QLabel#subtituloPrincipal {{
        font-size: 13px;
        color: {p["texto_secundario"]};
        background: transparent;
    }}

    QLabel#tituloSeccion {{
        font-size: 16px;
        font-weight: 600;
        color: {p["texto"]};
        background: transparent;
    }}

    QLabel#badgeContadorCola {{
        background-color: {p["superficie"]};
        border: 1px solid {p["borde"]};
        border-radius: 11px;
        padding: 3px 10px;
        font-size: 12px;
        font-weight: 600;
        color: {p["texto_secundario"]};
    }}

    QLabel#etiquetaCampo {{
        font-weight: 600;
        font-size: 13px;
        color: {p["texto"]};
        background: transparent;
    }}

    QLabel#etiquetaAyuda {{
        font-size: 12px;
        color: {p["texto_secundario"]};
        background: transparent;
    }}

    QLabel#etiquetaError {{
        color: {p["peligro"]};
        font-size: 12px;
        font-weight: 500;
        background: transparent;
    }}

    /* Estado vacío de la cola */
    QWidget#contenedorVacio {{
        background: transparent;
    }}

    QLabel#tituloVacio {{
        font-size: 15px;
        font-weight: 600;
        color: {p["texto"]};
        background: transparent;
    }}

    QLabel#descripcionVacio {{
        font-size: 13px;
        color: {p["texto_secundario"]};
        background: transparent;
    }}

    /* Cajas de texto y desplegables */
    QLineEdit, QComboBox {{
        background-color: {p["superficie"]};
        border: 1px solid {p["borde"]};
        border-radius: 7px;
        padding: 7px 11px;
        min-height: 20px;
        font-size: 14px;
        color: {p["texto"]};
        selection-background-color: {p["acento_menta"]};
        selection-color: {p["texto_boton_acento"]};
    }}

    QLineEdit:hover, QComboBox:hover {{
        border-color: {p["texto_tenue"]};
    }}

    QLineEdit:focus, QComboBox:focus {{
        border: 1.5px solid {p["borde_foco"]};
        background-color: {p["superficie_panel"]};
    }}

    QLineEdit:disabled, QComboBox:disabled {{
        color: {p["texto_desactivado"]};
        background-color: {p["fondo"]};
        border-color: {p["borde_suave"]};
    }}

    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 26px;
        border-left: none;
    }}

    QComboBox QAbstractItemView {{
        background-color: {p["superficie_panel"]};
        border: 1px solid {p["borde"]};
        border-radius: 7px;
        selection-background-color: {p["acento_menta"]};
        selection-color: {p["texto_boton_acento"]};
        padding: 4px;
        outline: none;
    }}

    /* Botones */
    QPushButton {{
        background-color: {p["superficie"]};
        border: 1px solid {p["borde"]};
        border-radius: 7px;
        padding: 7px 14px;
        font-size: 13px;
        font-weight: 500;
        color: {p["texto"]};
    }}

    QPushButton:hover {{
        background-color: {p["superficie_hover"]};
        border-color: {p["borde_foco"]};
    }}

    QPushButton:focus {{
        border: 1.5px solid {p["borde_foco"]};
    }}

    QPushButton:pressed {{
        background-color: {p["separador"]};
    }}

    QPushButton:disabled {{
        color: {p["texto_desactivado"]};
        background-color: {p["fondo"]};
        border-color: {p["borde_suave"]};
    }}

    QPushButton#btnBarraSuperior {{
        background-color: {p["superficie_panel"]};
        border: 1px solid {p["borde"]};
        border-radius: 8px;
        padding: 6px 10px;
        font-size: 13px;
        font-weight: 600;
    }}

    QPushButton#btnBarraSuperior:hover {{
        background-color: {p["superficie_hover"]};
        border-color: {p["borde_foco"]};
    }}

    QPushButton#btnPrimario {{
        background-color: {p["acento_menta"]};
        color: {p["texto_boton_acento"]};
        border: 1px solid {p["acento_menta"]};
        border-radius: 8px;
        font-size: 14px;
        font-weight: 600;
        padding: 9px 18px;
    }}

    QPushButton#btnPrimario:hover {{
        background-color: {p["acento_menta_hover"]};
        border-color: {p["acento_menta_hover"]};
    }}

    QPushButton#btnPrimario:pressed {{
        background-color: {p["acento_menta_presionado"]};
    }}

    QPushButton#btnAccionTarjeta {{
        padding: 4px 11px;
        font-size: 12px;
        font-weight: 500;
        border-radius: 6px;
    }}

    /* Chip de plataforma */
    QLabel#chipPlataforma {{
        background-color: {p["acento_menta_fondo"]};
        border: 1px solid {p["borde"]};
        border-radius: 10px;
        padding: 3px 10px;
        font-size: 12px;
        font-weight: 600;
        color: {p["acento_menta"]};
    }}

    QLabel#chipPlataformaTarjeta {{
        background-color: {p["superficie"]};
        border: 1px solid {p["borde"]};
        border-radius: 8px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 600;
        color: {p["acento_menta"]};
    }}

    /* Tarjetas de cola */
    QFrame#tarjetaTrabajo {{
        background-color: {p["superficie_tarjeta"]};
        border: 1px solid {p["borde"]};
        border-radius: 10px;
    }}

    QFrame#tarjetaTrabajo[estado="active"] {{
        background-color: {p["superficie_tarjeta_activa"]};
        border: 1.5px solid {p["acento_menta"]};
    }}

    QFrame#tarjetaTrabajo[estado="failed"], QFrame#tarjetaTrabajo[estado="interrupted"] {{
        border: 1px solid {p["peligro"]};
    }}

    QFrame#tarjetaTrabajo[estado="completed"] {{
        border: 1px solid {p["exito"]};
    }}

    QLabel#tituloTarjeta {{
        font-size: 14px;
        font-weight: 600;
        color: {p["texto"]};
        background: transparent;
    }}

    QLabel#infoTecnicaTarjeta {{
        font-size: 12px;
        color: {p["texto_secundario"]};
        background: transparent;
    }}

    QLabel#destinoTarjeta {{
        font-size: 12px;
        color: {p["texto_tenue"]};
        background: transparent;
    }}

    QLabel#estadoFase {{
        font-size: 12px;
        font-weight: 600;
        padding: 2px 9px;
        border-radius: 9px;
        background-color: {p["superficie"]};
        color: {p["texto_secundario"]};
    }}

    QLabel#estadoFase[rol="active"] {{
        background-color: {p["acento_menta_fondo"]};
        color: {p["acento_menta"]};
    }}

    QLabel#estadoFase[rol="completed"] {{
        background-color: {p["exito_fondo"]};
        color: {p["exito"]};
    }}

    QLabel#estadoFase[rol="error"] {{
        background-color: {p["peligro_fondo"]};
        color: {p["peligro_texto"]};
    }}

    QLabel#metricasTarjeta {{
        font-size: 12px;
        color: {p["texto_secundario"]};
        background: transparent;
    }}

    QLabel#resumenErrorTarjeta {{
        font-size: 12px;
        color: {p["peligro_texto"]};
        background-color: {p["peligro_fondo"]};
        border-radius: 6px;
        padding: 5px 8px;
    }}

    /* Tarjetas y controles del historial de descargas */
    QFrame#tarjetaHistorial {{
        background-color: {p["superficie_tarjeta"]};
        border: 1px solid {p["borde"]};
        border-radius: 10px;
    }}

    QFrame#tarjetaHistorial[estado_archivo="missing"] {{
        border: 1px solid {p["peligro"]};
    }}

    QLabel#estadoArchivoHistorial {{
        font-size: 11px;
        font-weight: 600;
        padding: 2px 9px;
        border-radius: 9px;
        background-color: {p["exito_fondo"]};
        color: {p["exito"]};
    }}

    QLabel#estadoArchivoHistorial[estado="missing"] {{
        background-color: {p["peligro_fondo"]};
        color: {p["peligro_texto"]};
    }}

    QLabel#fechaTamanoHistorial {{
        font-size: 12px;
        color: {p["texto_secundario"]};
        background: transparent;
    }}

    QPushButton#btnVaciarHistorial {{
        padding: 6px 13px;
        font-size: 12px;
        font-weight: 600;
        border-radius: 7px;
        color: {p["peligro"]};
        border: 1px solid {p["borde"]};
        background-color: {p["superficie"]};
    }}

    QPushButton#btnVaciarHistorial:hover {{
        background-color: {p["peligro_fondo"]};
        border-color: {p["peligro"]};
        color: {p["peligro_texto"]};
    }}

    QPushButton#btnVaciarHistorial:disabled {{
        color: {p["texto_desactivado"]};
        background-color: {p["fondo"]};
        border-color: {p["borde_suave"]};
    }}

    /* Barra de progreso */
    QProgressBar {{
        background-color: {p["barra_progreso_fondo"]};
        border: none;
        border-radius: 4px;
        min-height: 7px;
        max-height: 7px;
        text-align: center;
    }}

    QProgressBar::chunk {{
        background-color: {p["acento_menta"]};
        border-radius: 4px;
    }}

    /* Scrollbars limpios */
    QScrollArea {{
        border: none;
        background-color: transparent;
    }}

    QWidget#contenedorListaTarjetas {{
        background-color: transparent;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 2px 0px;
    }}

    QScrollBar::handle:vertical {{
        background: {p["borde"]};
        border-radius: 4px;
        min-height: 28px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {p["texto_tenue"]};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    /* Separador discreto */
    QFrame#separadorColumnas {{
        background-color: transparent;
        max-width: 1px;
        min-width: 1px;
        border: none;
    }}

    /* Selector segmentado accesible para Ajustes (Idioma y Tema) */
    QFrame#selectorSegmentado {{
        background-color: {p["superficie"]};
        border: 1px solid {p["borde"]};
        border-radius: 8px;
        padding: 2px;
    }}

    QPushButton#btnSegmento {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: 6px;
        padding: 6px 16px;
        min-width: 96px;
        min-height: 24px;
        font-size: 13px;
        font-weight: 500;
        color: {p["texto_secundario"]};
    }}

    QPushButton#btnSegmento:hover {{
        color: {p["texto"]};
        background-color: {p["superficie_hover"]};
    }}

    QPushButton#btnSegmento:checked {{
        background-color: {p["acento_menta"]};
        color: {p["texto_boton_acento"]};
        border: 1px solid {p["acento_menta"]};
        font-weight: 600;
    }}

    QPushButton#btnSegmento:focus {{
        border: 1.5px solid {p["borde_foco"]};
    }}

    /* Grupos en diálogo de ajustes */
    QGroupBox {{
        font-weight: 600;
        font-size: 13px;
        border: 1px solid {p["borde"]};
        border-radius: 8px;
        margin-top: 10px;
        padding-top: 10px;
        background-color: {p["superficie_panel"]};
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: {p["texto"]};
    }}

    /* Pestañas para modo compacto */
    QTabWidget::pane {{
        border: 1px solid {p["borde"]};
        border-radius: 10px;
        background-color: {p["superficie_panel"]};
    }}

    QTabBar::tab {{
        background-color: {p["superficie"]};
        border: 1px solid {p["borde"]};
        padding: 8px 16px;
        margin-right: 4px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        color: {p["texto_secundario"]};
    }}

    QTabBar::tab:selected {{
        background-color: {p["superficie_panel"]};
        border-bottom-color: {p["superficie_panel"]};
        font-weight: 600;
        color: {p["acento_menta"]};
    }}
    """
