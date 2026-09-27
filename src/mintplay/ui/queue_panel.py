"""Panel que contiene la lista desplazable de tarjetas de descarga y estado vacío ilustrado."""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..domain.models import EstadoTrabajo, TrabajoDescarga
from ..services.queue_manager import GestorCola
from .i18n_manager import obtener_traductor, t
from .job_card import TarjetaTrabajo
from .theme import obtener_paleta, renderizar_svg_pixmap


class PanelCola(QFrame):
    """Panel visual que gestiona y muestra la lista de descargas activas y en espera."""

    def __init__(
        self,
        gestor_cola: GestorCola,
        parent: Optional[QWidget] = None,
        tema_inicial: str = "dark",
        paleta_inicial: str = "mint",
    ):
        super().__init__(parent)
        self.setObjectName("panelCola")
        self.gestor = gestor_cola
        self._tema_actual = tema_inicial
        self._paleta_actual = paleta_inicial
        self._tarjetas: Dict[str, TarjetaTrabajo] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Encabezado con título y badge contador
        fila_encabezado = QHBoxLayout()
        fila_encabezado.setSpacing(10)

        self.lbl_titulo = QLabel(t("queue_title"))
        self.lbl_titulo.setObjectName("tituloSeccion")

        self.lbl_contador = QLabel(t("queue_count_zero"))
        self.lbl_contador.setObjectName("badgeContadorCola")

        fila_encabezado.addWidget(self.lbl_titulo)
        fila_encabezado.addStretch(1)
        fila_encabezado.addWidget(self.lbl_contador)
        layout.addLayout(fila_encabezado)

        # Stack para alternar limpiamente entre estado vacío centrado y lista desplazable
        self.stack_cola = QStackedWidget(self)

        # Página 0: Estado vacío centrado que jamás se corta en 800x600 ni al 150 %
        self.widget_vacio = QWidget()
        self.widget_vacio.setObjectName("contenedorVacio")
        layout_vacio = QVBoxLayout(self.widget_vacio)
        layout_vacio.setContentsMargins(24, 24, 24, 24)
        layout_vacio.setSpacing(10)

        layout_vacio.addStretch(1)

        self.lbl_vacio_icono = QLabel()
        self.lbl_vacio_icono.setAlignment(Qt.AlignCenter)
        layout_vacio.addWidget(self.lbl_vacio_icono, 0, Qt.AlignCenter)

        self.lbl_vacio_titulo = QLabel(t("queue_empty_title"))
        self.lbl_vacio_titulo.setObjectName("tituloVacio")
        self.lbl_vacio_titulo.setAlignment(Qt.AlignCenter)
        self.lbl_vacio_titulo.setWordWrap(True)
        layout_vacio.addWidget(self.lbl_vacio_titulo)

        self.lbl_vacio_desc = QLabel(t("queue_empty_desc"))
        self.lbl_vacio_desc.setObjectName("descripcionVacio")
        self.lbl_vacio_desc.setAlignment(Qt.AlignCenter)
        self.lbl_vacio_desc.setWordWrap(True)
        self.lbl_vacio_desc.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout_vacio.addWidget(self.lbl_vacio_desc)

        layout_vacio.addStretch(1)

        # Página 1: Contenedor desplazable de tarjetas
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.contenedor_tarjetas = QWidget()
        self.contenedor_tarjetas.setObjectName("contenedorListaTarjetas")
        self.layout_lista = QVBoxLayout(self.contenedor_tarjetas)
        self.layout_lista.setContentsMargins(0, 2, 10, 2)
        self.layout_lista.setSpacing(10)
        self.layout_lista.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.contenedor_tarjetas)

        self.stack_cola.addWidget(self.widget_vacio)
        self.stack_cola.addWidget(self.scroll_area)
        layout.addWidget(self.stack_cola, 1)

        # Renderizar ilustración SVG inicial
        self.actualizar_tema(self._tema_actual, self._paleta_actual)

        # Conectar señales del gestor
        self.gestor.trabajo_anadido.connect(self._al_anadir_trabajo)
        self.gestor.trabajo_actualizado.connect(self._al_actualizar_trabajo)
        self.gestor.trabajo_eliminado.connect(self._al_eliminar_trabajo)
        self.gestor.conteo_cambiado.connect(self._al_cambiar_conteo)

        obtener_traductor().idioma_cambiado.connect(self.actualizar_textos_idioma)

        # Cargar trabajos existentes
        for trabajo in self.gestor.trabajos:
            self._crear_tarjeta(trabajo)
        self._recalcular_posiciones_espera()
        self._actualizar_visibilidad_vacio()
        total, espera, completos, errores = self.gestor.obtener_conteo_actual()
        self._al_cambiar_conteo(total, espera, completos, errores)

    def actualizar_tema(self, tema: str, paleta: Optional[str] = None) -> None:
        """Actualiza la ilustración SVG del estado vacío con la paleta y modo activos."""
        self._tema_actual = tema
        if paleta is not None:
            self._paleta_actual = paleta
        tokens = obtener_paleta(tema, self._paleta_actual)
        pixmap = renderizar_svg_pixmap(
            nombre_svg="empty-wind.svg",
            color_trazo=tokens["texto_secundario"],
            color_acento=tokens["acento"],
            ancho=124,
            alto=76,
        )
        self.lbl_vacio_icono.setPixmap(pixmap)

    def _calcular_posicion_espera(self, id_trabajo: str) -> Optional[int]:
        pos = 1
        for t_item in self.gestor.trabajos:
            if t_item.status == EstadoTrabajo.EN_ESPERA:
                if t_item.id == id_trabajo:
                    return pos
                pos += 1
        return None

    def _recalcular_posiciones_espera(self) -> None:
        pos = 1
        for t_item in self.gestor.trabajos:
            if t_item.status == EstadoTrabajo.EN_ESPERA:
                tarjeta = self._tarjetas.get(t_item.id)
                if tarjeta:
                    tarjeta.actualizar_datos(t_item, posicion_cola=pos)
                pos += 1

    def _crear_tarjeta(self, trabajo: TrabajoDescarga) -> TarjetaTrabajo:
        tarjeta = TarjetaTrabajo(trabajo, self.contenedor_tarjetas)
        tarjeta.quitar_solicitado.connect(self.gestor.quitar_trabajo)
        tarjeta.cancelar_solicitado.connect(self.gestor.cancelar_trabajo)
        tarjeta.reintentar_solicitado.connect(self.gestor.reintentar_trabajo)
        tarjeta.primer_repintado.connect(self.gestor.registrar_tarjeta_visible)

        self._tarjetas[trabajo.id] = tarjeta
        self.layout_lista.addWidget(tarjeta)
        self.gestor.registrar_tarjeta_insertada(trabajo.id)
        self._actualizar_visibilidad_vacio()
        return tarjeta

    def _al_anadir_trabajo(self, id_trabajo: str) -> None:
        trabajo = self.gestor.obtener_trabajo(id_trabajo)
        if trabajo and id_trabajo not in self._tarjetas:
            tarjeta = self._crear_tarjeta(trabajo)
            pos = self._calcular_posicion_espera(id_trabajo)
            tarjeta.actualizar_datos(trabajo, posicion_cola=pos)

    def _al_actualizar_trabajo(self, id_trabajo: str) -> None:
        trabajo = self.gestor.obtener_trabajo(id_trabajo)
        if not trabajo:
            return
        tarjeta = self._tarjetas.get(id_trabajo)
        pos = self._calcular_posicion_espera(id_trabajo)
        if tarjeta:
            tarjeta.actualizar_datos(trabajo, posicion_cola=pos)
        else:
            nueva = self._crear_tarjeta(trabajo)
            nueva.actualizar_datos(trabajo, posicion_cola=pos)
        self._recalcular_posiciones_espera()

    def _al_eliminar_trabajo(self, id_trabajo: str) -> None:
        tarjeta = self._tarjetas.pop(id_trabajo, None)
        if tarjeta:
            self.layout_lista.removeWidget(tarjeta)
            tarjeta.deleteLater()
        self._recalcular_posiciones_espera()
        self._actualizar_visibilidad_vacio()

    def _al_cambiar_conteo(
        self, total: int, espera: int, completados: int, errores: int
    ) -> None:
        if total == 0:
            self.lbl_contador.setText(t("queue_count_zero"))
            return

        activos = max(0, total - espera - completados - errores)
        partes = [str(total)]
        detalles = []
        if activos > 0:
            detalles.append(t("queue_count_active"))
        if espera > 0:
            detalles.append(f"{espera} {t('status_queued').lower()}")
        if errores > 0:
            detalles.append(f"{errores} {t('status_failed').lower()}")

        if detalles:
            self.lbl_contador.setText(f"{total}  ·  {', '.join(detalles)}")
        else:
            self.lbl_contador.setText(f"({total})")

    def _actualizar_visibilidad_vacio(self) -> None:
        tiene_tarjetas = len(self._tarjetas) > 0
        if tiene_tarjetas:
            self.stack_cola.setCurrentWidget(self.scroll_area)
        else:
            self.stack_cola.setCurrentWidget(self.widget_vacio)

    def actualizar_textos_idioma(self) -> None:
        """Refresca etiquetas, contadores y tarjetas existentes preservando el scroll."""
        valor_scroll = self.scroll_area.verticalScrollBar().value()

        self.lbl_titulo.setText(t("queue_title"))
        self.lbl_vacio_titulo.setText(t("queue_empty_title"))
        self.lbl_vacio_desc.setText(t("queue_empty_desc"))

        total, espera, completos, errores = self.gestor.obtener_conteo_actual()
        self._al_cambiar_conteo(total, espera, completos, errores)

        for t_id, tarjeta in self._tarjetas.items():
            trabajo = self.gestor.obtener_trabajo(t_id)
            if trabajo:
                pos = self._calcular_posicion_espera(t_id)
                tarjeta.actualizar_datos(trabajo, posicion_cola=pos)

        self.scroll_area.verticalScrollBar().setValue(valor_scroll)
