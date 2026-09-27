"""Definición modular de cinco paletas de color (claro y oscuro), tokens semánticos e iconos SVG para MintPlay."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QIcon,
    QImage,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer

from ..services.runtime_paths import obtener_ruta_icono

PALETAS_IDS: Tuple[str, ...] = ("mint", "sakura", "indigo", "amber", "ocean")
MODOS_TEMA: Tuple[str, ...] = ("light", "dark")
PALETA_PREDETERMINADA = "mint"
MODO_PREDETERMINADO = "dark"


def normalizar_preferencias_tema(
    modo_o_tema: Optional[object] = None,
    paleta: Optional[object] = None,
) -> Tuple[str, str]:
    """Normaliza cualquier combinación de entrada (paleta, modo) o cadena heredada.

    Devuelve siempre una tupla válida ``(paleta_id, modo_id)`` donde:
    - ``paleta_id`` pertenece a ``PALETAS_IDS`` (por defecto ``'mint'``).
    - ``modo_id`` pertenece a ``MODOS_TEMA`` (por defecto ``'dark'``).
    """
    cand_modo = str(modo_o_tema).strip().lower() if isinstance(modo_o_tema, str) else ""
    cand_paleta = str(paleta).strip().lower() if isinstance(paleta, str) else ""

    # Soportar cadenas combinadas tipo "sakura:light", "ocean_dark" o "amber-light"
    for sep in (":", "_", "-"):
        if sep in cand_modo:
            partes = [p.strip() for p in cand_modo.split(sep, 1)]
            if len(partes) == 2:
                if partes[0] in PALETAS_IDS and partes[1] in MODOS_TEMA:
                    if not cand_paleta:
                        cand_paleta = partes[0]
                    cand_modo = partes[1]
                    break
                if partes[1] in PALETAS_IDS and partes[0] in MODOS_TEMA:
                    if not cand_paleta:
                        cand_paleta = partes[1]
                    cand_modo = partes[0]
                    break

    # Si se pasó el nombre de una paleta en el primer argumento y no se especificó paleta
    if cand_modo in PALETAS_IDS and not cand_paleta:
        cand_paleta = cand_modo
        cand_modo = MODO_PREDETERMINADO

    paleta_final = cand_paleta if cand_paleta in PALETAS_IDS else PALETA_PREDETERMINADA
    modo_final = cand_modo if cand_modo in MODOS_TEMA else MODO_PREDETERMINADO
    return paleta_final, modo_final


# Tokens semánticos invariantes por modo (éxito, espera, advertencia, error)
# Conservan su significado y contraste >= 4.5:1 en las cinco paletas.
_SEMANTICOS_POR_MODO: Dict[str, Dict[str, str]] = {
    "light": {
        "exito": "#157F46",
        "exito_fondo": "#E5F6EC",
        "exito_texto": "#0F5C32",
        "espera": "#475569",
        "espera_fondo": "#EEF2F6",
        "espera_texto": "#334155",
        "advertencia": "#B45309",
        "advertencia_fondo": "#FEF3C7",
        "advertencia_texto": "#78350F",
        "error": "#B82530",
        "error_hover": "#9E1E28",
        "error_fondo": "#FCECEE",
        "error_texto": "#85151E",
    },
    "dark": {
        "exito": "#48D585",
        "exito_fondo": "#163224",
        "exito_texto": "#9CF0BD",
        "espera": "#94A3B8",
        "espera_fondo": "#222B38",
        "espera_texto": "#CBD5E1",
        "advertencia": "#FBBF24",
        "advertencia_fondo": "#362712",
        "advertencia_texto": "#FDE68A",
        "error": "#E87676",
        "error_hover": "#F28B8B",
        "error_fondo": "#361B1E",
        "error_texto": "#FFD4D6",
    },
}


# Definición base de las 10 combinaciones (5 paletas x 2 modos)
_DEFINICIONES_PALETAS: Dict[Tuple[str, str], Dict[str, str]] = {
    ("mint", "light"): {
        "fondo": "#F5F8F3",
        "superficie": "#FFFFFF",
        "superficie_panel": "#FFFFFF",
        "elevada": "#EAF2EE",
        "superficie_tarjeta": "#FAFDFB",
        "superficie_tarjeta_activa": "#EFF8F4",
        "borde": "#CAD9D1",
        "borde_suave": "#DEE9E3",
        "texto": "#192C29",
        "secundario": "#50645D",
        "texto_tenue": "#526860",
        "texto_desactivado": "#8CA099",
        "acento": "#168569",
        "acento_hover": "#126E57",
        "acento_presionado": "#0E5946",
        "acento_texto_chip": "#116A53",
        "texto_acento": "#FFFFFF",
        "barra_progreso_fondo": "#DAE6DF",
        "separador": "#DAE5DE",
    },
    ("mint", "dark"): {
        "fondo": "#111A1A",
        "superficie": "#1B2827",
        "superficie_panel": "#1B2827",
        "elevada": "#253532",
        "superficie_tarjeta": "#1E2D2B",
        "superficie_tarjeta_activa": "#223632",
        "borde": "#2D4340",
        "borde_suave": "#223431",
        "texto": "#EEF4F0",
        "secundario": "#ADC3BA",
        "texto_tenue": "#9AB2A9",
        "texto_desactivado": "#657C75",
        "acento": "#79D6B4",
        "acento_hover": "#91E1C3",
        "acento_presionado": "#5FC29F",
        "acento_texto_chip": "#79D6B4",
        "texto_acento": "#11251F",
        "barra_progreso_fondo": "#283B38",
        "separador": "#253735",
    },
    ("sakura", "light"): {
        "fondo": "#FCF7F8",
        "superficie": "#FFFFFF",
        "superficie_panel": "#FFFFFF",
        "elevada": "#F8EDF0",
        "superficie_tarjeta": "#FEFBFC",
        "superficie_tarjeta_activa": "#FBF2F5",
        "borde": "#DFCDD3",
        "borde_suave": "#EDE0E4",
        "texto": "#34212A",
        "secundario": "#6D5962",
        "texto_tenue": "#6F5B64",
        "texto_desactivado": "#A39199",
        "acento": "#A83B64",
        "acento_hover": "#8F2F53",
        "acento_presionado": "#782544",
        "acento_texto_chip": "#963258",
        "texto_acento": "#FFFFFF",
        "barra_progreso_fondo": "#EBDCE1",
        "separador": "#EADBE0",
    },
    ("sakura", "dark"): {
        "fondo": "#1E171B",
        "superficie": "#2B2026",
        "superficie_panel": "#2B2026",
        "elevada": "#382831",
        "superficie_tarjeta": "#30242B",
        "superficie_tarjeta_activa": "#3B2A33",
        "borde": "#47353F",
        "borde_suave": "#372830",
        "texto": "#F7EDF1",
        "secundario": "#C7ABB7",
        "texto_tenue": "#B99CA8",
        "texto_desactivado": "#7E6771",
        "acento": "#E88CAA",
        "acento_hover": "#F0A1BB",
        "acento_presionado": "#D97596",
        "acento_texto_chip": "#E88CAA",
        "texto_acento": "#311722",
        "barra_progreso_fondo": "#412F39",
        "separador": "#3D2C35",
    },
    ("indigo", "light"): {
        "fondo": "#F6F7FC",
        "superficie": "#FFFFFF",
        "superficie_panel": "#FFFFFF",
        "elevada": "#ECEFFD",
        "superficie_tarjeta": "#FBFcff",
        "superficie_tarjeta_activa": "#F1F4FE",
        "borde": "#CED4E8",
        "borde_suave": "#E1E5F2",
        "texto": "#242840",
        "secundario": "#59617B",
        "texto_tenue": "#5B637D",
        "texto_desactivado": "#939AB2",
        "acento": "#465CC5",
        "acento_hover": "#3A4EB0",
        "acento_presionado": "#2F4096",
        "acento_texto_chip": "#3D52B5",
        "texto_acento": "#FFFFFF",
        "barra_progreso_fondo": "#DCE1F4",
        "separador": "#DBE0F2",
    },
    ("indigo", "dark"): {
        "fondo": "#141722",
        "superficie": "#202538",
        "superficie_panel": "#202538",
        "elevada": "#2B3149",
        "superficie_tarjeta": "#242A3F",
        "superficie_tarjeta_activa": "#2C334E",
        "borde": "#373F5C",
        "borde_suave": "#2A3047",
        "texto": "#F0F2FC",
        "secundario": "#B3BED6",
        "texto_tenue": "#A3AEC8",
        "texto_desactivado": "#6B748E",
        "acento": "#A7B4FF",
        "acento_hover": "#BCC6FF",
        "acento_presionado": "#8E9EF5",
        "acento_texto_chip": "#A7B4FF",
        "texto_acento": "#1E2340",
        "barra_progreso_fondo": "#313852",
        "separador": "#2E354E",
    },
    ("amber", "light"): {
        "fondo": "#FBF8F0",
        "superficie": "#FFFFFF",
        "superficie_panel": "#FFFFFF",
        "elevada": "#F5ECD9",
        "superficie_tarjeta": "#FEFCF8",
        "superficie_tarjeta_activa": "#FAF3E4",
        "borde": "#DDD1BA",
        "borde_suave": "#EAE1CF",
        "texto": "#342B20",
        "secundario": "#6E604C",
        "texto_tenue": "#70624E",
        "texto_desactivado": "#A39582",
        "acento": "#946018",
        "acento_hover": "#7D5012",
        "acento_presionado": "#66400D",
        "acento_texto_chip": "#7E5112",
        "texto_acento": "#FFFFFF",
        "barra_progreso_fondo": "#EAE0CC",
        "separador": "#E8DEC9",
    },
    ("amber", "dark"): {
        "fondo": "#1E1A14",
        "superficie": "#2C261C",
        "superficie_panel": "#2C261C",
        "elevada": "#3A3021",
        "superficie_tarjeta": "#312A1F",
        "superficie_tarjeta_activa": "#3C3223",
        "borde": "#4A3E2C",
        "borde_suave": "#382F21",
        "texto": "#FAF2E4",
        "secundario": "#C8B79A",
        "texto_tenue": "#B8A78A",
        "texto_desactivado": "#7D6F59",
        "acento": "#EFC079",
        "acento_hover": "#F5CE93",
        "acento_presionado": "#DFAD62",
        "acento_texto_chip": "#EFC079",
        "texto_acento": "#34230D",
        "barra_progreso_fondo": "#423726",
        "separador": "#3E3323",
    },
    ("ocean", "light"): {
        "fondo": "#F3F8FA",
        "superficie": "#FFFFFF",
        "superficie_panel": "#FFFFFF",
        "elevada": "#E8F2F6",
        "superficie_tarjeta": "#FAFCFD",
        "superficie_tarjeta_activa": "#EEF6F9",
        "borde": "#C8D9E0",
        "borde_suave": "#DCE8ED",
        "texto": "#1D3038",
        "secundario": "#536C75",
        "texto_tenue": "#556E77",
        "texto_desactivado": "#8BA0A8",
        "acento": "#167C9B",
        "acento_hover": "#116782",
        "acento_presionado": "#0D5369",
        "acento_texto_chip": "#11647D",
        "texto_acento": "#FFFFFF",
        "barra_progreso_fondo": "#D7E6EC",
        "separador": "#D6E5EB",
    },
    ("ocean", "dark"): {
        "fondo": "#101B20",
        "superficie": "#1B2A31",
        "superficie_panel": "#1B2A31",
        "elevada": "#243943",
        "superficie_tarjeta": "#1E2F37",
        "superficie_tarjeta_activa": "#233842",
        "borde": "#2E4652",
        "borde_suave": "#233640",
        "texto": "#EBF5F7",
        "secundario": "#ACC6CF",
        "texto_tenue": "#9AB5BF",
        "texto_desactivado": "#627B85",
        "acento": "#75C7DF",
        "acento_hover": "#8ED4E8",
        "acento_presionado": "#5BB4CE",
        "acento_texto_chip": "#75C7DF",
        "texto_acento": "#0F2B34",
        "barra_progreso_fondo": "#283E48",
        "separador": "#253A44",
    },
}


def _construir_diccionario_tokens() -> Dict[Tuple[str, str], Dict[str, str]]:
    resultado: Dict[Tuple[str, str], Dict[str, str]] = {}
    for (paleta_id, modo), base in _DEFINICIONES_PALETAS.items():
        sem = _SEMANTICOS_POR_MODO[modo]
        t_dict = dict(base)
        t_dict.update(sem)

        # Tokens derivados y alias de compatibilidad
        t_dict["superficie_elevada"] = base["elevada"]
        t_dict["hover"] = base["elevada"]
        t_dict["superficie_hover"] = base["elevada"]
        t_dict["seleccionado"] = base["elevada"]
        t_dict["foco"] = base["acento"]
        t_dict["borde_foco"] = base["acento"]
        t_dict["texto_secundario"] = base["secundario"]
        t_dict["acento_fondo"] = base["elevada"]
        t_dict["acento_menta"] = base["acento"]
        t_dict["acento_menta_hover"] = base["acento_hover"]
        t_dict["acento_menta_presionado"] = base["acento_presionado"]
        t_dict["acento_menta_fondo"] = base["elevada"]
        t_dict["texto_boton_acento"] = base["texto_acento"]
        t_dict["peligro"] = sem["error"]
        t_dict["peligro_hover"] = sem["error_hover"]
        t_dict["peligro_fondo"] = sem["error_fondo"]
        t_dict["peligro_texto"] = sem["error_texto"]
        resultado[(paleta_id, modo)] = t_dict
    return resultado


TOKENS_TEMAS: Dict[Tuple[str, str], Dict[str, str]] = _construir_diccionario_tokens()

# Diccionario indexado para compatibilidad con llamadas directas PALETAS["dark"] / PALETAS["light"]
PALETAS: Dict[str, Dict[str, str]] = {
    "dark": TOKENS_TEMAS[("mint", "dark")],
    "light": TOKENS_TEMAS[("mint", "light")],
    **{
        f"{paleta_id}:{modo}": tokens
        for (paleta_id, modo), tokens in TOKENS_TEMAS.items()
    },
}


def obtener_paleta(
    tema: str = MODO_PREDETERMINADO,
    paleta: Optional[str] = None,
) -> Dict[str, str]:
    """Devuelve el diccionario de tokens de diseño para la combinación `(paleta, modo)`."""
    paleta_id, modo_id = normalizar_preferencias_tema(tema, paleta)
    return TOKENS_TEMAS[(paleta_id, modo_id)]


def _luminancia_relativa_srgb(hex_color: str) -> float:
    limpio = hex_color.strip().lstrip("#")
    if len(limpio) == 3:
        limpio = "".join(c * 2 for c in limpio)
    r = int(limpio[0:2], 16) / 255.0
    g = int(limpio[2:4], 16) / 255.0
    b = int(limpio[4:6], 16) / 255.0

    def lin(canal: float) -> float:
        return canal / 12.92 if canal <= 0.04045 else ((canal + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def calcular_contraste_wcag(color_a: str, color_b: str) -> float:
    """Calcula la relación de contraste WCAG 2.1 entre dos colores hexadecimales."""
    lum_a = _luminancia_relativa_srgb(color_a)
    lum_b = _luminancia_relativa_srgb(color_b)
    mayor = max(lum_a, lum_b)
    menor = min(lum_a, lum_b)
    return (mayor + 0.05) / (menor + 0.05)


def _obtener_escala_pantalla() -> float:
    app = QGuiApplication.instance()
    if app is not None:
        pantalla = QGuiApplication.primaryScreen()
        if pantalla is not None:
            return max(2.0, float(pantalla.devicePixelRatio()))
    return 2.0


def crear_icono_muestra_paleta(
    paleta_id: str,
    modo: str = MODO_PREDETERMINADO,
    seleccionado: bool = False,
    tamano: int = 14,
) -> QIcon:
    """Crea un icono circular con la muestra de color acento de la paleta indicada."""
    tokens = obtener_paleta(modo, paleta_id)
    color_acento = QColor(tokens["acento"])
    color_anillo = (
        QColor(tokens["texto_acento"])
        if seleccionado
        else QColor(tokens["borde"])
    )

    escala = _obtener_escala_pantalla()
    px = int(tamano * escala)
    imagen = QImage(px, px, QImage.Format_ARGB32_Premultiplied)
    imagen.fill(Qt.transparent)

    pintor = QPainter(imagen)
    pintor.setRenderHint(QPainter.Antialiasing, True)

    margen = 1.6 * escala
    rect = QRectF(margen, margen, px - (margen * 2), px - (margen * 2))
    pintor.setBrush(color_acento)
    pen = QPen(color_anillo)
    pen.setWidthF((1.6 if seleccionado else 1.1) * escala)
    pintor.setPen(pen)
    pintor.drawEllipse(rect)

    if seleccionado:
        # Pequeño punto central de contraste para reforzar selección sin depender solo del color
        radio_punto = 2.0 * escala
        pintor.setPen(Qt.NoPen)
        pintor.setBrush(QColor(tokens["texto_acento"]))
        pintor.drawEllipse(QPointF(px / 2.0, px / 2.0), radio_punto, radio_punto)

    pintor.end()
    pixmap = QPixmap.fromImage(imagen)
    pixmap.setDevicePixelRatio(escala)
    return QIcon(pixmap)


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
    tema: str = MODO_PREDETERMINADO,
    tamano: int = 18,
    paleta: Optional[str] = None,
) -> QIcon:
    """Construye un QIcon vectorial nítido a partir de un SVG coloreado según paleta y modo."""
    tokens = obtener_paleta(tema, paleta)
    pixmap = renderizar_svg_pixmap(
        nombre_svg=nombre_svg,
        color_trazo=tokens["texto"],
        color_acento=tokens["acento"],
        ancho=tamano,
        alto=tamano,
    )
    return QIcon(pixmap)


def generar_hoja_estilos(
    tema: str = MODO_PREDETERMINADO,
    paleta: Optional[str] = None,
) -> str:
    """Genera la hoja de estilos Qt (QSS) completa a partir de los tokens de `(paleta, modo)`."""
    p = obtener_paleta(tema, paleta)

    return f"""
    * {{
        font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Inter', Roboto, sans-serif;
        font-size: 14px;
        color: {p["texto"]};
    }}

    QMainWindow, QDialog, QMessageBox {{
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
        background-color: {p["elevada"]};
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
        color: {p["error"]};
        font-size: 12px;
        font-weight: 500;
        background: transparent;
    }}

    /* Estado vacío de la cola e historial */
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
        selection-background-color: {p["acento"]};
        selection-color: {p["texto_acento"]};
    }}

    QLineEdit:hover, QComboBox:hover {{
        border-color: {p["texto_tenue"]};
    }}

    QLineEdit:focus, QComboBox:focus {{
        border: 1.5px solid {p["foco"]};
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
        selection-background-color: {p["acento"]};
        selection-color: {p["texto_acento"]};
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
        background-color: {p["hover"]};
        border-color: {p["foco"]};
    }}

    QPushButton:focus {{
        border: 1.5px solid {p["foco"]};
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
        color: {p["texto"]};
    }}

    QPushButton#btnBarraSuperior:hover {{
        background-color: {p["hover"]};
        border-color: {p["foco"]};
    }}

    QPushButton#btnPrimario {{
        background-color: {p["acento"]};
        color: {p["texto_acento"]};
        border: 1px solid {p["acento"]};
        border-radius: 8px;
        font-size: 14px;
        font-weight: 600;
        padding: 9px 18px;
    }}

    QPushButton#btnPrimario:hover {{
        background-color: {p["acento_hover"]};
        border-color: {p["acento_hover"]};
    }}

    QPushButton#btnPrimario:pressed {{
        background-color: {p["acento_presionado"]};
    }}

    QPushButton#btnAccionTarjeta {{
        padding: 4px 11px;
        font-size: 12px;
        font-weight: 500;
        border-radius: 6px;
    }}

    /* Chip de plataforma */
    QLabel#chipPlataforma {{
        background-color: {p["acento_fondo"]};
        border: 1px solid {p["borde"]};
        border-radius: 10px;
        padding: 3px 10px;
        font-size: 12px;
        font-weight: 600;
        color: {p["acento_texto_chip"]};
    }}

    QLabel#chipPlataformaTarjeta {{
        background-color: {p["elevada"]};
        border: 1px solid {p["borde"]};
        border-radius: 8px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 600;
        color: {p["acento_texto_chip"]};
    }}

    /* Tarjetas de cola */
    QFrame#tarjetaTrabajo {{
        background-color: {p["superficie_tarjeta"]};
        border: 1px solid {p["borde"]};
        border-radius: 10px;
    }}

    QFrame#tarjetaTrabajo[estado="active"] {{
        background-color: {p["superficie_tarjeta_activa"]};
        border: 1.5px solid {p["acento"]};
    }}

    QFrame#tarjetaTrabajo[estado="failed"], QFrame#tarjetaTrabajo[estado="interrupted"] {{
        border: 1px solid {p["error"]};
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
        background-color: {p["espera_fondo"]};
        color: {p["espera_texto"]};
    }}

    QLabel#estadoFase[rol="active"] {{
        background-color: {p["acento_fondo"]};
        color: {p["acento_texto_chip"]};
    }}

    QLabel#estadoFase[rol="completed"] {{
        background-color: {p["exito_fondo"]};
        color: {p["exito_texto"]};
    }}

    QLabel#estadoFase[rol="warning"] {{
        background-color: {p["advertencia_fondo"]};
        color: {p["advertencia_texto"]};
    }}

    QLabel#estadoFase[rol="error"] {{
        background-color: {p["error_fondo"]};
        color: {p["error_texto"]};
    }}

    QLabel#metricasTarjeta {{
        font-size: 12px;
        color: {p["texto_secundario"]};
        background: transparent;
    }}

    QLabel#resumenErrorTarjeta {{
        font-size: 12px;
        color: {p["error_texto"]};
        background-color: {p["error_fondo"]};
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
        border: 1px solid {p["error"]};
    }}

    QLabel#estadoArchivoHistorial {{
        font-size: 11px;
        font-weight: 600;
        padding: 2px 9px;
        border-radius: 9px;
        background-color: {p["exito_fondo"]};
        color: {p["exito_texto"]};
    }}

    QLabel#estadoArchivoHistorial[estado="missing"] {{
        background-color: {p["error_fondo"]};
        color: {p["error_texto"]};
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
        color: {p["error"]};
        border: 1px solid {p["borde"]};
        background-color: {p["superficie"]};
    }}

    QPushButton#btnVaciarHistorial:hover {{
        background-color: {p["error_fondo"]};
        border-color: {p["error"]};
        color: {p["error_texto"]};
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
        background-color: {p["acento"]};
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

    /* Selector segmentado accesible para Ajustes (Idioma y Apariencia) */
    QFrame#selectorSegmentado, QFrame#selectorPaleta {{
        background-color: {p["elevada"]};
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
        background-color: {p["superficie"]};
    }}

    QPushButton#btnSegmento:checked {{
        background-color: {p["acento"]};
        color: {p["texto_acento"]};
        border: 1px solid {p["acento"]};
        font-weight: 600;
    }}

    QPushButton#btnSegmento:focus {{
        border: 1.5px solid {p["foco"]};
    }}

    /* Botones de selección de paleta con muestra de color en Ajustes */
    QPushButton#btnPaleta {{
        background-color: {p["superficie"]};
        border: 1px solid {p["borde"]};
        border-radius: 7px;
        padding: 6px 10px;
        min-width: 78px;
        min-height: 26px;
        font-size: 13px;
        font-weight: 500;
        color: {p["texto"]};
    }}

    QPushButton#btnPaleta:hover {{
        background-color: {p["hover"]};
        border-color: {p["foco"]};
    }}

    QPushButton#btnPaleta:checked {{
        background-color: {p["acento"]};
        color: {p["texto_acento"]};
        border: 1.5px solid {p["acento"]};
        font-weight: 600;
    }}

    QPushButton#btnPaleta:focus {{
        border: 1.5px solid {p["foco"]};
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
        color: {p["acento_texto_chip"]};
    }}
    """
