"""Diálogo y tarjetas del historial local de descargas de MintPlay."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QDesktopServices,
    QFontMetrics,
    QGuiApplication,
    QResizeEvent,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..domain.models import OpcionesDescarga, RegistroHistorial
from ..services.history_manager import GestorHistorial
from .download_form import traducir_etiqueta_calidad, traducir_plataforma
from .i18n_manager import confirmar_accion_si_no, obtener_traductor, t
from .job_card import formatear_tamano
from .theme import generar_hoja_estilos, obtener_paleta, renderizar_svg_pixmap

LOTE_RENDER_HISTORIAL = 40


def formatear_fecha_historial(timestamp: float) -> str:
    """Formatea una marca de tiempo UNIX a fecha y hora local legible (YYYY-MM-DD HH:MM)."""
    if not timestamp or timestamp <= 0:
        return ""
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):
        return ""


def comprobar_existencia_registro(registro: RegistroHistorial) -> tuple[bool, bool, str]:
    """Comprueba en tiempo real si existen el archivo final y su carpeta contenedora.

    Devuelve (existe_archivo, existe_carpeta, ruta_carpeta_efectiva).
    """
    existe_archivo = False
    ruta_salida = (registro.output_path or "").strip()
    if ruta_salida:
        try:
            p_archivo = Path(ruta_salida)
            existe_archivo = p_archivo.is_file()
        except OSError:
            existe_archivo = False

    carpeta_efectiva = (registro.destination_dir or "").strip()
    if ruta_salida:
        try:
            padre = str(Path(ruta_salida).parent)
            if padre and padre != ".":
                carpeta_efectiva = padre
        except OSError:
            pass

    existe_carpeta = False
    if carpeta_efectiva:
        try:
            existe_carpeta = Path(carpeta_efectiva).is_dir()
        except OSError:
            existe_carpeta = False

    return existe_archivo, existe_carpeta, carpeta_efectiva


class TarjetaHistorial(QFrame):
    """Tarjeta individual para un registro del historial de descargas."""

    quitar_solicitado = Signal(str)
    redescargar_solicitado = Signal(str)
    enlace_copiado = Signal(str)

    def __init__(self, registro: RegistroHistorial, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.registro = registro
        self.registro_id = registro.id
        self._titulo_completo = ""
        self._ultimo_estado_qss: Optional[str] = None
        self._copiado_feedback_activo = False

        self.setObjectName("tarjetaHistorial")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        # Fila 1: Nombre de archivo o título a la izquierda + estado del archivo a la derecha
        fila1 = QHBoxLayout()
        fila1.setSpacing(10)

        self.lbl_titulo = QLabel()
        self.lbl_titulo.setObjectName("tituloTarjeta")
        self.lbl_titulo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.lbl_estado_archivo = QLabel()
        self.lbl_estado_archivo.setObjectName("estadoArchivoHistorial")
        self.lbl_estado_archivo.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        fila1.addWidget(self.lbl_titulo, 1)
        fila1.addWidget(self.lbl_estado_archivo, 0, Qt.AlignRight | Qt.AlignTop)
        layout.addLayout(fila1)

        # Fila 2: Plataforma · Tipo · Formato · Calidad | Fecha · Tamaño · Carpeta
        fila2 = QHBoxLayout()
        fila2.setSpacing(8)

        self.lbl_plataforma = QLabel()
        self.lbl_plataforma.setObjectName("chipPlataformaTarjeta")

        self.lbl_info_tecnica = QLabel()
        self.lbl_info_tecnica.setObjectName("infoTecnicaTarjeta")

        self.lbl_fecha_tamano = QLabel()
        self.lbl_fecha_tamano.setObjectName("fechaTamanoHistorial")

        self.lbl_destino = QLabel()
        self.lbl_destino.setObjectName("destinoTarjeta")
        self.lbl_destino.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        fila2.addWidget(self.lbl_plataforma)
        fila2.addWidget(self.lbl_info_tecnica)
        fila2.addStretch(1)
        fila2.addWidget(self.lbl_fecha_tamano)
        fila2.addWidget(self.lbl_destino)
        layout.addLayout(fila2)

        # Fila 3: Botones de acción por registro
        fila_acciones = QHBoxLayout()
        fila_acciones.setContentsMargins(0, 2, 0, 0)
        fila_acciones.setSpacing(6)
        fila_acciones.addStretch(1)

        self.btn_abrir_archivo = QPushButton()
        self.btn_abrir_archivo.setObjectName("btnAccionTarjeta")
        self.btn_abrir_archivo.setCursor(Qt.PointingHandCursor)
        self.btn_abrir_archivo.clicked.connect(self.ejecutar_abrir_archivo)

        self.btn_abrir_carpeta = QPushButton()
        self.btn_abrir_carpeta.setObjectName("btnAccionTarjeta")
        self.btn_abrir_carpeta.setCursor(Qt.PointingHandCursor)
        self.btn_abrir_carpeta.clicked.connect(self.ejecutar_abrir_carpeta)

        self.btn_copiar_enlace = QPushButton()
        self.btn_copiar_enlace.setObjectName("btnAccionTarjeta")
        self.btn_copiar_enlace.setCursor(Qt.PointingHandCursor)
        self.btn_copiar_enlace.clicked.connect(self.ejecutar_copiar_enlace)

        self.btn_redescargar = QPushButton()
        self.btn_redescargar.setObjectName("btnAccionTarjeta")
        self.btn_redescargar.setCursor(Qt.PointingHandCursor)
        self.btn_redescargar.clicked.connect(self.ejecutar_redescargar)

        self.btn_quitar = QPushButton()
        self.btn_quitar.setObjectName("btnAccionTarjeta")
        self.btn_quitar.setCursor(Qt.PointingHandCursor)
        self.btn_quitar.clicked.connect(
            lambda: self.quitar_solicitado.emit(self.registro_id)
        )

        fila_acciones.addWidget(self.btn_abrir_archivo)
        fila_acciones.addWidget(self.btn_abrir_carpeta)
        fila_acciones.addWidget(self.btn_copiar_enlace)
        fila_acciones.addWidget(self.btn_redescargar)
        fila_acciones.addWidget(self.btn_quitar)
        layout.addLayout(fila_acciones)

        self.actualizar_datos(registro)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._aplicar_elision_titulo()

    def _aplicar_elision_titulo(self) -> None:
        ancho_disp = max(180, self.width() - 185)
        fm = QFontMetrics(self.lbl_titulo.font())
        elidido = fm.elidedText(self._titulo_completo, Qt.ElideRight, ancho_disp)
        self.lbl_titulo.setText(elidido)

        partes_tooltip = []
        if self.registro.title:
            partes_tooltip.append(self.registro.title)
        if (
            self.registro.final_filename
            and self.registro.final_filename != self.registro.title
        ):
            partes_tooltip.append(self.registro.final_filename)
        if self.registro.output_path:
            partes_tooltip.append(self.registro.output_path)
        self.lbl_titulo.setToolTip("\n".join(partes_tooltip))

    def actualizar_datos(self, registro: Optional[RegistroHistorial] = None) -> None:
        """Actualiza textos, metadatos y disponibilidad física del archivo en disco."""
        if registro is not None:
            self.registro = registro
            self.registro_id = registro.id

        reg = self.registro
        existe_archivo, existe_carpeta, carpeta_efectiva = comprobar_existencia_registro(reg)
        estado_qss = "available" if existe_archivo else "missing"

        if estado_qss != self._ultimo_estado_qss:
            self._ultimo_estado_qss = estado_qss
            self.setProperty("estado_archivo", estado_qss)
            self.style().unpolish(self)
            self.style().polish(self)

            self.lbl_estado_archivo.setProperty("estado", estado_qss)
            self.lbl_estado_archivo.style().unpolish(self.lbl_estado_archivo)
            self.lbl_estado_archivo.style().polish(self.lbl_estado_archivo)

        # Nombre final o título resuelto
        self._titulo_completo = (
            reg.final_filename or reg.title or reg.custom_name or reg.url
        )
        self._aplicar_elision_titulo()

        # Badge de disponibilidad del archivo
        if existe_archivo:
            self.lbl_estado_archivo.setText(t("history_status_available"))
            self.lbl_estado_archivo.setToolTip(reg.output_path)
        else:
            self.lbl_estado_archivo.setText(t("history_status_missing"))
            self.lbl_estado_archivo.setToolTip(t("history_tooltip_missing_file"))

        # Plataforma traducida
        self.lbl_plataforma.setText(traducir_plataforma(reg.platform_hint, reg.url))

        # Resumen técnico: Vídeo/Audio · Formato · Calidad (y calidad efectiva si difiere)
        tipo_texto = (
            t("type_video") if reg.media_type.value == "video" else t("type_audio")
        )
        calidad_texto = traducir_etiqueta_calidad(reg.quality_choice)
        if (
            reg.effective_quality
            and reg.effective_quality.lower() != reg.quality_choice.lower()
        ):
            calidad_texto = f"{calidad_texto} ({reg.effective_quality})"
        self.lbl_info_tecnica.setText(
            f"{tipo_texto} · {reg.target_extension.upper()} · {calidad_texto}"
        )

        # Fecha y tamaño
        partes_meta = []
        tamano_txt = formatear_tamano(reg.file_size)
        if tamano_txt:
            partes_meta.append(tamano_txt)
        fecha_txt = formatear_fecha_historial(reg.completed_at)
        if fecha_txt:
            partes_meta.append(fecha_txt)
        self.lbl_fecha_tamano.setText(" · ".join(partes_meta))

        # Carpeta resumida
        carpeta_corta = (
            Path(carpeta_efectiva).name if carpeta_efectiva else ""
        ) or carpeta_efectiva
        self.lbl_destino.setText(f"📁 {carpeta_corta}" if carpeta_corta else "")
        self.lbl_destino.setToolTip(carpeta_efectiva)

        # Textos y estados de botones
        self.btn_abrir_archivo.setText(t("btn_open_file"))
        self.btn_abrir_archivo.setEnabled(existe_archivo)
        self.btn_abrir_archivo.setToolTip(
            reg.output_path if existe_archivo else t("history_tooltip_missing_file")
        )

        self.btn_abrir_carpeta.setText(t("btn_open_folder"))
        self.btn_abrir_carpeta.setEnabled(existe_carpeta)
        self.btn_abrir_carpeta.setToolTip(
            carpeta_efectiva if existe_carpeta else t("history_tooltip_missing_folder")
        )

        if not self._copiado_feedback_activo:
            self.btn_copiar_enlace.setText(t("history_btn_copy_link"))
        self.btn_copiar_enlace.setEnabled(bool(reg.url))

        self.btn_redescargar.setText(t("history_btn_redownload"))
        self.btn_redescargar.setEnabled(bool(reg.url))

        self.btn_quitar.setText(t("history_btn_remove"))

    def ejecutar_abrir_archivo(self) -> bool:
        """Verifica en vivo que el archivo exista antes de abrirlo con el sistema operativo."""
        existe_archivo, _, _ = comprobar_existencia_registro(self.registro)
        if not existe_archivo:
            self.actualizar_datos()
            return False
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.registro.output_path))
        return True

    def ejecutar_abrir_carpeta(self) -> bool:
        """Verifica en vivo que la carpeta exista antes de abrirla en el explorador."""
        _, existe_carpeta, carpeta_efectiva = comprobar_existencia_registro(self.registro)
        if not existe_carpeta or not carpeta_efectiva:
            self.actualizar_datos()
            return False
        QDesktopServices.openUrl(QUrl.fromLocalFile(carpeta_efectiva))
        return True

    def ejecutar_copiar_enlace(self) -> bool:
        """Copia el enlace original al portapapeles de forma explícita sin exponerlo en logs."""
        if not self.registro.url:
            return False
        portapapeles = QGuiApplication.clipboard()
        if portapapeles is not None:
            portapapeles.setText(self.registro.url)
        self._copiado_feedback_activo = True
        self.btn_copiar_enlace.setText(f"✓ {t('history_btn_copied')}")
        self.enlace_copiado.emit(self.registro_id)
        QTimer.singleShot(1500, self._restaurar_texto_copiar)
        return True

    def _restaurar_texto_copiar(self) -> None:
        self._copiado_feedback_activo = False
        self.btn_copiar_enlace.setText(t("history_btn_copy_link"))

    def ejecutar_redescargar(self) -> None:
        """Solicita volver a encolar este recurso con sus opciones guardadas."""
        if not self.registro.url:
            return
        self.redescargar_solicitado.emit(self.registro_id)


class DialogoHistorial(QDialog):
    """Ventana secundaria de historial de descargas con búsqueda, filtro y carga por lotes."""

    redescarga_solicitada = Signal(OpcionesDescarga, str)

    def __init__(
        self,
        gestor_historial: GestorHistorial,
        parent: Optional[QWidget] = None,
        tema_inicial: str = "dark",
        paleta_inicial: str = "mint",
    ):
        super().__init__(parent)
        self.gestor_historial = gestor_historial
        self._tema_actual = tema_inicial
        self._paleta_actual = paleta_inicial
        self._traductor = obtener_traductor()

        self._tarjetas: Dict[str, TarjetaHistorial] = {}
        self._resultados_filtrados: List[RegistroHistorial] = []
        self._cantidad_renderizada = 0

        self.setWindowTitle(t("history_title"))
        self.setMinimumSize(780, 520)
        self.resize(860, 580)

        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(20, 18, 20, 18)
        layout_raiz.setSpacing(14)

        # Encabezado: Título + subtítulo a la izquierda, contador + Vaciar historial a la derecha
        fila_encabezado = QHBoxLayout()
        fila_encabezado.setSpacing(12)

        col_titulos = QVBoxLayout()
        col_titulos.setSpacing(2)

        self.lbl_titulo = QLabel(t("history_title"))
        self.lbl_titulo.setObjectName("tituloPrincipal")

        self.lbl_subtitulo = QLabel(t("history_subtitle"))
        self.lbl_subtitulo.setObjectName("subtituloPrincipal")

        col_titulos.addWidget(self.lbl_titulo)
        col_titulos.addWidget(self.lbl_subtitulo)
        fila_encabezado.addLayout(col_titulos, 1)

        self.lbl_contador = QLabel()
        self.lbl_contador.setObjectName("badgeContadorCola")
        fila_encabezado.addWidget(self.lbl_contador, 0, Qt.AlignVCenter)

        self.btn_vaciar = QPushButton(t("history_btn_clear_all"))
        self.btn_vaciar.setObjectName("btnVaciarHistorial")
        self.btn_vaciar.setCursor(Qt.PointingHandCursor)
        self.btn_vaciar.clicked.connect(lambda: self.vaciar_historial_confirmado(confirmar=True))
        fila_encabezado.addWidget(self.btn_vaciar, 0, Qt.AlignVCenter)

        layout_raiz.addLayout(fila_encabezado)

        # Panel contenedor principal (mismo estilo de superficie que panelCola)
        self.panel_contenedor = QFrame(self)
        self.panel_contenedor.setObjectName("panelHistorial")
        layout_panel = QVBoxLayout(self.panel_contenedor)
        layout_panel.setContentsMargins(16, 14, 16, 14)
        layout_panel.setSpacing(12)

        # Barra de búsqueda y filtro por tipo
        fila_controles = QHBoxLayout()
        fila_controles.setSpacing(10)

        self.txt_buscar = QLineEdit()
        self.txt_buscar.setPlaceholderText(t("history_search_placeholder"))
        self.txt_buscar.setClearButtonEnabled(True)
        self.txt_buscar.textChanged.connect(self._al_cambiar_busqueda_o_filtro)

        self.cmb_filtro_tipo = QComboBox()
        self.cmb_filtro_tipo.setMinimumWidth(155)
        self._poblar_combo_filtro("all")
        self.cmb_filtro_tipo.currentIndexChanged.connect(self._al_cambiar_busqueda_o_filtro)

        fila_controles.addWidget(self.txt_buscar, 1)
        fila_controles.addWidget(self.cmb_filtro_tipo, 0)
        layout_panel.addLayout(fila_controles)

        # Stack: vista vacía vs lista con scroll
        self.stack = QStackedWidget()

        # Página 0: Estado vacío / sin coincidencias
        self.vista_vacia = QWidget()
        self.vista_vacia.setObjectName("contenedorVacio")
        layout_vacio = QVBoxLayout(self.vista_vacia)
        layout_vacio.setContentsMargins(32, 36, 32, 36)
        layout_vacio.setSpacing(10)
        layout_vacio.setAlignment(Qt.AlignCenter)

        self.lbl_icono_vacio = QLabel()
        self.lbl_icono_vacio.setAlignment(Qt.AlignCenter)
        self.lbl_icono_vacio.setFixedSize(72, 72)

        self.lbl_vacio_titulo = QLabel(t("history_empty_title"))
        self.lbl_vacio_titulo.setObjectName("tituloVacio")
        self.lbl_vacio_titulo.setAlignment(Qt.AlignCenter)
        self.lbl_vacio_titulo.setWordWrap(True)

        self.lbl_vacio_desc = QLabel(t("history_empty_desc"))
        self.lbl_vacio_desc.setObjectName("descripcionVacio")
        self.lbl_vacio_desc.setAlignment(Qt.AlignCenter)
        self.lbl_vacio_desc.setWordWrap(True)
        self.lbl_vacio_desc.setMaximumWidth(380)

        layout_vacio.addWidget(self.lbl_icono_vacio, 0, Qt.AlignHCenter)
        layout_vacio.addSpacing(4)
        layout_vacio.addWidget(self.lbl_vacio_titulo, 0, Qt.AlignHCenter)
        layout_vacio.addWidget(self.lbl_vacio_desc, 0, Qt.AlignHCenter)

        # Página 1: Área de desplazamiento con tarjetas
        self.area_scroll = QScrollArea()
        self.area_scroll.setWidgetResizable(True)
        self.area_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.area_scroll.verticalScrollBar().valueChanged.connect(self._al_desplazar_scroll)

        self.contenedor_tarjetas = QWidget()
        self.contenedor_tarjetas.setObjectName("contenedorListaTarjetas")
        self.layout_tarjetas = QVBoxLayout(self.contenedor_tarjetas)
        self.layout_tarjetas.setContentsMargins(0, 2, 4, 2)
        self.layout_tarjetas.setSpacing(8)
        self.layout_tarjetas.addStretch(1)

        self.area_scroll.setWidget(self.contenedor_tarjetas)

        self.stack.addWidget(self.vista_vacia)
        self.stack.addWidget(self.area_scroll)
        layout_panel.addWidget(self.stack, 1)

        layout_raiz.addWidget(self.panel_contenedor, 1)

        # Conexiones reactivas
        self.gestor_historial.historial_cambiado.connect(self.refrescar_vista)
        self._traductor.idioma_cambiado.connect(self.retraducir)

        self.actualizar_tema(self._tema_actual, self._paleta_actual)
        self.refrescar_vista()

    def showEvent(self, event: QShowEvent) -> None:
        """Al mostrarse, revalida la existencia de los archivos visibles en disco."""
        super().showEvent(event)
        self.revalidar_existencia_archivos()

    def _poblar_combo_filtro(self, filtro_seleccionado: str = "all") -> None:
        self.cmb_filtro_tipo.blockSignals(True)
        self.cmb_filtro_tipo.clear()
        opciones = [
            ("all", t("history_filter_all")),
            ("video", t("history_filter_video")),
            ("audio", t("history_filter_audio")),
        ]
        idx_sel = 0
        for i, (clave, etiqueta) in enumerate(opciones):
            self.cmb_filtro_tipo.addItem(etiqueta, clave)
            if clave == filtro_seleccionado:
                idx_sel = i
        self.cmb_filtro_tipo.setCurrentIndex(idx_sel)
        self.cmb_filtro_tipo.blockSignals(False)

    def filtro_tipo_actual(self) -> str:
        """Devuelve el filtro de tipo seleccionado ('all', 'video' o 'audio')."""
        dato = self.cmb_filtro_tipo.currentData()
        return str(dato) if dato else "all"

    def texto_busqueda_actual(self) -> str:
        """Devuelve el texto de búsqueda actual."""
        return self.txt_buscar.text()

    def actualizar_tema(self, tema: str, paleta: Optional[str] = None) -> None:
        """Aplica la paleta y hoja de estilos del tema actual sin perder el estado de la vista."""
        self._tema_actual = tema
        if paleta is not None:
            self._paleta_actual = paleta
        self.setStyleSheet(generar_hoja_estilos(self._tema_actual, self._paleta_actual))
        tokens = obtener_paleta(self._tema_actual, self._paleta_actual)
        pixmap = renderizar_svg_pixmap(
            nombre_svg="history.svg",
            color_trazo=tokens["texto_tenue"],
            color_acento=tokens["acento"],
            ancho=72,
            alto=72,
        )
        self.lbl_icono_vacio.setPixmap(pixmap)

    def retraducir(self, *_args: object) -> None:
        """Actualiza todos los textos traducibles conservando búsqueda, filtro y scroll."""
        pos_scroll = self.area_scroll.verticalScrollBar().value()
        filtro_actual = self.filtro_tipo_actual()

        self.setWindowTitle(t("history_title"))
        self.lbl_titulo.setText(t("history_title"))
        self.lbl_subtitulo.setText(t("history_subtitle"))
        self.btn_vaciar.setText(t("history_btn_clear_all"))
        self.txt_buscar.setPlaceholderText(t("history_search_placeholder"))
        self._poblar_combo_filtro(filtro_actual)

        for tarjeta in self._tarjetas.values():
            tarjeta.actualizar_datos()

        self._actualizar_encabezado_y_estado_vacio()
        self.area_scroll.verticalScrollBar().setValue(pos_scroll)

    def revalidar_existencia_archivos(self) -> None:
        """Comprueba si los archivos de las tarjetas renderizadas siguen existiendo en disco."""
        for tarjeta in self._tarjetas.values():
            tarjeta.actualizar_datos()

    def _al_cambiar_busqueda_o_filtro(self, *_args: object) -> None:
        self.refrescar_vista(conservar_scroll=False)

    def refrescar_vista(self, conservar_scroll: bool = True) -> None:
        """Filtra en memoria y reconstruye el lote visible de tarjetas con fluidez."""
        pos_scroll = (
            self.area_scroll.verticalScrollBar().value() if conservar_scroll else 0
        )

        self._resultados_filtrados = self.gestor_historial.buscar_y_filtrar(
            texto_busqueda=self.texto_busqueda_actual(),
            filtro_tipo=self.filtro_tipo_actual(),
        )

        self._limpiar_tarjetas_renderizadas()
        self._cargar_siguiente_lote()
        self._actualizar_encabezado_y_estado_vacio()

        if conservar_scroll and pos_scroll > 0:
            self.area_scroll.verticalScrollBar().setValue(pos_scroll)

    def _limpiar_tarjetas_renderizadas(self) -> None:
        for tarjeta in self._tarjetas.values():
            self.layout_tarjetas.removeWidget(tarjeta)
            tarjeta.deleteLater()
        self._tarjetas.clear()
        self._cantidad_renderizada = 0

    def _cargar_siguiente_lote(self) -> None:
        total_filtrado = len(self._resultados_filtrados)
        if self._cantidad_renderizada >= total_filtrado:
            return

        inicio = self._cantidad_renderizada
        fin = min(inicio + LOTE_RENDER_HISTORIAL, total_filtrado)

        for idx in range(inicio, fin):
            reg = self._resultados_filtrados[idx]
            tarjeta = TarjetaHistorial(reg, self.contenedor_tarjetas)
            tarjeta.quitar_solicitado.connect(self._al_quitar_registro)
            tarjeta.redescargar_solicitado.connect(self._al_redescargar_registro)
            # Insertar antes del stretch final
            pos_insercion = max(0, self.layout_tarjetas.count() - 1)
            self.layout_tarjetas.insertWidget(pos_insercion, tarjeta)
            self._tarjetas[reg.id] = tarjeta

        self._cantidad_renderizada = fin

    def _al_desplazar_scroll(self, valor: int) -> None:
        barra = self.area_scroll.verticalScrollBar()
        if barra.maximum() > 0 and valor >= (barra.maximum() - 160):
            self._cargar_siguiente_lote()

    def _actualizar_encabezado_y_estado_vacio(self) -> None:
        total_global = self.gestor_historial.total_registros
        total_filtrado = len(self._resultados_filtrados)

        self.btn_vaciar.setEnabled(total_global > 0)

        hay_filtro_activo = bool(self.texto_busqueda_actual().strip()) or (
            self.filtro_tipo_actual() != "all"
        )

        if hay_filtro_activo and total_global > 0:
            self.lbl_contador.setText(
                f"{total_filtrado} / {total_global} {t('history_count_many')}"
            )
        elif total_global == 0:
            self.lbl_contador.setText(t("history_count_zero"))
        elif total_global == 1:
            self.lbl_contador.setText(t("history_count_one"))
        else:
            self.lbl_contador.setText(
                f"{total_global} {t('history_count_many')}"
            )

        if total_global == 0:
            self.lbl_vacio_titulo.setText(t("history_empty_title"))
            self.lbl_vacio_desc.setText(t("history_empty_desc"))
            self.stack.setCurrentWidget(self.vista_vacia)
        elif total_filtrado == 0:
            self.lbl_vacio_titulo.setText(t("history_no_results_title"))
            self.lbl_vacio_desc.setText(t("history_no_results_desc"))
            self.stack.setCurrentWidget(self.vista_vacia)
        else:
            self.stack.setCurrentWidget(self.area_scroll)

    def _al_quitar_registro(self, id_registro: str) -> None:
        """Elimina solo el registro del historial sin borrar el archivo físico."""
        self.gestor_historial.quitar_registro(id_registro)

    def _al_redescargar_registro(self, id_registro: str) -> None:
        """Crea un nuevo trabajo en la cola reutilizando las opciones originales del registro."""
        registro = self.gestor_historial.obtener_registro(id_registro)
        if not registro or not registro.url:
            return
        opciones = registro.a_opciones_descarga()
        self.redescarga_solicitada.emit(opciones, registro.platform_hint)

    def vaciar_historial_confirmado(self, confirmar: bool = True) -> bool:
        """Pide confirmación explícita con botones Sí/No (o Yes/No) y vacía únicamente los registros."""
        if self.gestor_historial.total_registros == 0:
            return False

        if confirmar:
            confirmado = confirmar_accion_si_no(
                self,
                t("confirm_clear_history_title"),
                t("confirm_clear_history_message"),
            )
            if not confirmado:
                return False

        self.gestor_historial.vaciar_historial()
        return True

    @property
    def tarjetas_visibles(self) -> Dict[str, TarjetaHistorial]:
        """Devuelve el diccionario de tarjetas actualmente instanciadas en la vista."""
        return dict(self._tarjetas)
