"""Gestor de cola de descargas con orquestación FIFO, señales Qt y telemetría de tiempos."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot

from ..domain.models import EstadoTrabajo, FaseTrabajo, TrabajoDescarga
from ..domain.states import (
    actualizar_fase_trabajo,
    ordenar_trabajos_canonicamente,
    reintentar_trabajo,
)
from .history_manager import GestorHistorial
from .persistence import guardar_cola

logger = logging.getLogger(__name__)


@dataclass
class MetricasEncolado:
    """Mediciones monotónicas (perf_counter) del ciclo de alta y arranque de un trabajo."""

    trabajo_id: str
    t_clic: float = field(default_factory=time.perf_counter)
    t_objeto_creado: float = 0.0
    t_tarjeta_insertada: float = 0.0
    t_tarjeta_visible: float = 0.0
    t_inicio_metadatos: float = 0.0
    t_inicio_descarga: float = 0.0
    en_hilo_ui_worker: bool = False

    def resumen_ms(self) -> Dict[str, float]:
        """Devuelve los tiempos relativos al clic inicial en milisegundos."""
        base = self.t_clic
        res: Dict[str, float] = {}
        if self.t_objeto_creado > 0:
            res["creacion_objeto_ms"] = round((self.t_objeto_creado - base) * 1000.0, 2)
        if self.t_tarjeta_insertada > 0:
            res["insercion_tarjeta_ms"] = round((self.t_tarjeta_insertada - base) * 1000.0, 2)
        if self.t_tarjeta_visible > 0:
            res["tarjeta_visible_ms"] = round((self.t_tarjeta_visible - base) * 1000.0, 2)
        if self.t_inicio_metadatos > 0:
            res["inicio_metadatos_ms"] = round((self.t_inicio_metadatos - base) * 1000.0, 2)
        if self.t_inicio_descarga > 0:
            res["inicio_descarga_ms"] = round((self.t_inicio_descarga - base) * 1000.0, 2)
        return res


class TrabajadorDescarga(QObject):
    """Objeto ejecutor en segundo plano que corre dentro de un QThread dedicado."""

    progreso_actualizado = Signal(str, float, object, object, object, object)
    # id_trabajo, progreso, bytes_descargados, bytes_totales, velocidad, eta
    fase_cambiada = Signal(str, str)
    # id_trabajo, nombre_fase
    _interno_finalizado = Signal(str, str)
    finalizado = Signal(str, str)
    # id_trabajo, ruta_salida
    _interno_fallido = Signal(str, str, str)
    fallido = Signal(str, str, str)
    # id_trabajo, codigo_error, detalle_error
    _interno_cancelado = Signal(str)
    cancelado = Signal(str)
    # id_trabajo
    metadatos_iniciados = Signal(str, float, bool)
    # id_trabajo, perf_counter, es_mismo_hilo_principal

    def __init__(self, servicio_descarga: Any, hilo_principal: Optional[QThread] = None):
        super().__init__()
        self.servicio = servicio_descarga
        self._hilo_principal = hilo_principal
        self._cancelado = False
        self._id_actual: Optional[str] = None

    @Slot(object)
    def procesar(self, trabajo: TrabajoDescarga) -> None:
        """Punto de entrada invocado en el QThread trabajador para ejecutar la descarga."""
        self._cancelado = False
        self._id_actual = trabajo.id

        es_hilo_ui = (
            self._hilo_principal is not None
            and QThread.currentThread() == self._hilo_principal
        )
        self.metadatos_iniciados.emit(trabajo.id, time.perf_counter(), es_hilo_ui)

        def cb_progreso(
            prog: float,
            dl_bytes: Optional[int],
            total_bytes: Optional[int],
            speed: Optional[float],
            eta: Optional[int],
        ) -> None:
            if not self._cancelado:
                self.progreso_actualizado.emit(
                    trabajo.id, prog, dl_bytes, total_bytes, speed, eta
                )

        def cb_fase(fase: FaseTrabajo) -> None:
            if not self._cancelado:
                self.fase_cambiada.emit(trabajo.id, fase.value)

        def es_cancelado() -> bool:
            return self._cancelado

        try:
            ruta_final = self.servicio.descargar(trabajo, cb_progreso, cb_fase, es_cancelado)
            if self._cancelado:
                self._interno_cancelado.emit(trabajo.id)
            else:
                self._interno_finalizado.emit(trabajo.id, str(ruta_final))
        except Exception as err:
            if self._cancelado:
                self._interno_cancelado.emit(trabajo.id)
            else:
                logger.exception("Error al procesar descarga: %s", err)
                cod = getattr(err, "error_code", "DOWNLOAD_ERROR")
                self._interno_fallido.emit(trabajo.id, str(cod), str(err))

    def cancelar(self) -> None:
        """Solicita la detención inmediata y limpia del trabajo en curso."""
        self._cancelado = True
        if hasattr(self.servicio, "cancelar"):
            self.servicio.cancelar()


class GestorCola(QObject):
    """Orquestador FIFO de descargas.

    Controla la concurrencia estricta de 1 descarga simultánea, la persistencia,
    el temporizador asíncrono de 5 segundos tras completar y la emisión de señales Qt hacia la UI.
    """

    trabajo_anadido = Signal(str)
    trabajo_actualizado = Signal(str)
    trabajo_eliminado = Signal(str)
    orden_cambiado = Signal()
    conteo_cambiado = Signal(int, int, int, int)  # total, en_espera, completados, errores
    trabajo_completado_notificable = Signal(object)
    trabajo_fallido_notificable = Signal(object)
    _iniciar_en_worker = Signal(object)

    def __init__(
        self,
        servicio_descarga: Any,
        parent: Optional[QObject] = None,
        gestor_historial: Optional[GestorHistorial] = None,
    ):
        super().__init__(parent)
        self.servicio = servicio_descarga
        self.historial: GestorHistorial = (
            gestor_historial if gestor_historial is not None else GestorHistorial(self)
        )
        self._trabajos: List[TrabajoDescarga] = []
        self._id_trabajo_activo: Optional[str] = None
        self._temporizador_finalizacion = QTimer(self)
        self._temporizador_finalizacion.setSingleShot(True)
        self._temporizador_finalizacion.timeout.connect(self._al_vencer_temporizador_finalizacion)
        self._id_en_espera_retiro: Optional[str] = None
        self._guardado_pendiente = False
        self.metricas: Dict[str, MetricasEncolado] = {}

        # Preparación de hilo y trabajador fuera del hilo gráfico
        hilo_ui = QThread.currentThread()
        self._thread = QThread(self)
        self._worker = TrabajadorDescarga(self.servicio, hilo_principal=hilo_ui)
        self._worker.moveToThread(self._thread)

        # Conexión encolada explícita hacia el hilo trabajador
        self._iniciar_en_worker.connect(self._worker.procesar, Qt.QueuedConnection)

        # Conexiones de retorno desde el hilo trabajador hacia el coordinador en el hilo principal
        self._worker.metadatos_iniciados.connect(self._al_iniciar_metadatos)
        self._worker.progreso_actualizado.connect(self._al_progreso_recibido)
        self._worker.fase_cambiada.connect(self._a_fase_recibida)
        self._worker._interno_finalizado.connect(self._al_trabajo_finalizado)
        self._worker._interno_fallido.connect(self._al_trabajo_fallido)
        self._worker._interno_cancelado.connect(self._al_trabajo_cancelado)

        self._thread.start()

    def _reordenar_trabajos(self, emitir_senal: bool = True) -> bool:
        """Aplica el orden canónico a la lista interna y emite orden_cambiado si hubo reubicación."""
        ids_antes = [t.id for t in self._trabajos]
        self._trabajos = ordenar_trabajos_canonicamente(self._trabajos)
        ids_despues = [t.id for t in self._trabajos]
        cambio = ids_antes != ids_despues
        if cambio and emitir_senal:
            self.orden_cambiado.emit()
        return cambio

    def inicializar_con_trabajos(self, trabajos_guardados: List[TrabajoDescarga]) -> None:
        """Carga la lista inicial de trabajos desde persistencia en orden canónico."""
        self._trabajos = ordenar_trabajos_canonicamente(list(trabajos_guardados))
        self.orden_cambiado.emit()
        self._emitir_cambio_conteo()

    @property
    def trabajos(self) -> List[TrabajoDescarga]:
        """Devuelve una copia de la lista de trabajos actuales en orden canónico."""
        return list(self._trabajos)

    def obtener_trabajo(self, id_trabajo: str) -> Optional[TrabajoDescarga]:
        """Busca un trabajo por su identificador único."""
        for t in self._trabajos:
            if t.id == id_trabajo:
                return t
        return None

    def registrar_inicio_clic(
        self,
        id_trabajo: str,
        t_clic: float,
        t_objeto_creado: float,
    ) -> None:
        """Registra las marcas de tiempo iniciales desde el clic en el formulario."""
        self.metricas[id_trabajo] = MetricasEncolado(
            trabajo_id=id_trabajo,
            t_clic=t_clic,
            t_objeto_creado=t_objeto_creado,
        )

    def registrar_tarjeta_insertada(self, id_trabajo: str) -> None:
        """Registra el instante en que el widget de tarjeta se inserta en el panel."""
        m = self.metricas.get(id_trabajo)
        if m and m.t_tarjeta_insertada == 0.0:
            m.t_tarjeta_insertada = time.perf_counter()

    def registrar_tarjeta_visible(self, id_trabajo: str) -> None:
        """Registra el instante del primer repintado real (paintEvent) de la tarjeta."""
        m = self.metricas.get(id_trabajo)
        if m and m.t_tarjeta_visible == 0.0:
            m.t_tarjeta_visible = time.perf_counter()
            logger.info(
                "[Telemetría UI] Tarjeta %s visible en %.2f ms (inserción: %.2f ms)",
                id_trabajo,
                (m.t_tarjeta_visible - m.t_clic) * 1000.0,
                (m.t_tarjeta_insertada - m.t_clic) * 1000.0 if m.t_tarjeta_insertada else 0.0,
            )

    def anadir_trabajo(self, trabajo: TrabajoDescarga) -> None:
        """Añade un trabajo en estado En espera a la UI de inmediato y programa persistencia/ejecución."""
        ahora = time.perf_counter()
        if trabajo.id not in self.metricas:
            self.metricas[trabajo.id] = MetricasEncolado(
                trabajo_id=trabajo.id,
                t_clic=ahora,
                t_objeto_creado=ahora,
            )

        self._trabajos.append(trabajo)
        self._reordenar_trabajos(emitir_senal=False)
        # 1. Notificar a la UI de inmediato con estado EN_ESPERA antes de tocar disco o red
        self.trabajo_anadido.emit(trabajo.id)
        self.orden_cambiado.emit()
        self._emitir_cambio_conteo()

        # 2. Persistir y despachar al hilo trabajador sin bloquear el alta visual
        self._guardar()
        self._procesar_siguiente()

    def quitar_trabajo(self, id_trabajo: str) -> None:
        """Elimina un trabajo que no esté en ejecución activa."""
        if self._id_trabajo_activo == id_trabajo:
            self.cancelar_trabajo(id_trabajo)
            return

        trabajo = self.obtener_trabajo(id_trabajo)
        if trabajo:
            if self._id_en_espera_retiro == id_trabajo:
                self._temporizador_finalizacion.stop()
                self._id_en_espera_retiro = None

            self._trabajos.remove(trabajo)
            self._reordenar_trabajos(emitir_senal=False)
            self._guardar()
            self.trabajo_eliminado.emit(id_trabajo)
            self.orden_cambiado.emit()
            self._emitir_cambio_conteo()
            self._procesar_siguiente()

    def cancelar_trabajo(self, id_trabajo: str) -> None:
        """Cancela un trabajo, deteniendo el worker si es el que se está descargando."""
        trabajo = self.obtener_trabajo(id_trabajo)
        if not trabajo:
            return

        if self._id_trabajo_activo == id_trabajo:
            self._worker.cancelar()
        elif trabajo.status == EstadoTrabajo.EN_ESPERA:
            actualizar_fase_trabajo(trabajo, FaseTrabajo.CANCELADO)
            self._reordenar_trabajos()
            self._guardar()
            self.trabajo_actualizado.emit(id_trabajo)
            self._emitir_cambio_conteo()

    def reintentar_trabajo(self, id_trabajo: str) -> None:
        """Reinicia un trabajo fallido, cancelado o interrumpido colocándolo al final de las pendientes."""
        trabajo = self.obtener_trabajo(id_trabajo)
        if not trabajo:
            return
        if trabajo.status not in (
            EstadoTrabajo.ERROR,
            EstadoTrabajo.CANCELADO,
            EstadoTrabajo.INTERRUMPIDO,
        ):
            return

        # Reubicar al final antes de cambiar a EN_ESPERA para que quede al final del grupo FIFO pendiente
        self._trabajos.remove(trabajo)
        self._trabajos.append(trabajo)
        reintentar_trabajo(trabajo)
        self._reordenar_trabajos()
        self._guardar()
        self.trabajo_actualizado.emit(id_trabajo)
        self.orden_cambiado.emit()
        self._emitir_cambio_conteo()
        self._procesar_siguiente()

    def _procesar_siguiente(self) -> None:
        """Verifica si es posible iniciar el siguiente trabajo en espera en el QThread trabajador."""
        if self._id_trabajo_activo is not None or self._id_en_espera_retiro is not None:
            return

        siguiente = None
        for t in self._trabajos:
            if t.status == EstadoTrabajo.EN_ESPERA:
                siguiente = t
                break

        if not siguiente:
            return

        self._id_trabajo_activo = siguiente.id
        actualizar_fase_trabajo(siguiente, FaseTrabajo.PREPARANDO)
        self._reordenar_trabajos()
        self._guardar()
        self.trabajo_actualizado.emit(siguiente.id)
        self.orden_cambiado.emit()
        self._emitir_cambio_conteo()

        # Emitir señal con conexión encolada (Qt.QueuedConnection) hacia self._thread
        self._iniciar_en_worker.emit(siguiente)

    def _al_iniciar_metadatos(self, id_trabajo: str, t_inicio: float, es_hilo_ui: bool) -> None:
        m = self.metricas.get(id_trabajo)
        if m:
            m.t_inicio_metadatos = t_inicio
            m.en_hilo_ui_worker = es_hilo_ui
            logger.info(
                "[Telemetría Worker] Trabajo %s inició metadatos en %.2f ms (en_hilo_ui=%s)",
                id_trabajo,
                (t_inicio - m.t_clic) * 1000.0,
                es_hilo_ui,
            )

    def _al_progreso_recibido(
        self,
        id_trabajo: str,
        prog: float,
        dl_bytes: Optional[int],
        total_bytes: Optional[int],
        speed: Optional[float],
        eta: Optional[int],
    ) -> None:
        trabajo = self.obtener_trabajo(id_trabajo)
        if not trabajo:
            return
        m = self.metricas.get(id_trabajo)
        if m and m.t_inicio_descarga == 0.0:
            m.t_inicio_descarga = time.perf_counter()

        trabajo.progress = prog
        trabajo.downloaded_bytes = dl_bytes
        trabajo.total_bytes = total_bytes
        trabajo.speed = speed
        trabajo.eta = eta
        self.trabajo_actualizado.emit(id_trabajo)

    def _a_fase_recibida(self, id_trabajo: str, fase_str: str) -> None:
        trabajo = self.obtener_trabajo(id_trabajo)
        if not trabajo:
            return
        fase = FaseTrabajo(fase_str)
        if fase == FaseTrabajo.DESCARGANDO:
            m = self.metricas.get(id_trabajo)
            if m and m.t_inicio_descarga == 0.0:
                m.t_inicio_descarga = time.perf_counter()

        if trabajo.phase == fase:
            return

        actualizar_fase_trabajo(trabajo, fase)
        self._reordenar_trabajos()
        self._guardar()
        self.trabajo_actualizado.emit(id_trabajo)

    def _al_trabajo_finalizado(self, id_trabajo: str, ruta_salida: str) -> None:
        trabajo = self.obtener_trabajo(id_trabajo)
        self._id_trabajo_activo = None

        if trabajo:
            actualizar_fase_trabajo(trabajo, FaseTrabajo.FINALIZADO)
            trabajo.output_path = ruta_salida
            self._reordenar_trabajos()
            self.historial.registrar_trabajo_completado(trabajo)
            self._guardar()
            self.trabajo_actualizado.emit(id_trabajo)
            self.orden_cambiado.emit()
            self._emitir_cambio_conteo()
            self.trabajo_completado_notificable.emit(trabajo)

            self._id_en_espera_retiro = id_trabajo
            self._temporizador_finalizacion.start(5000)

        self._worker.finalizado.emit(id_trabajo, ruta_salida)

    def _al_vencer_temporizador_finalizacion(self) -> None:
        """Al expirar los 5 segundos asíncronos, retira la tarjeta completada y arranca la siguiente."""
        id_a_retirar = self._id_en_espera_retiro
        self._id_en_espera_retiro = None

        if id_a_retirar:
            trabajo = self.obtener_trabajo(id_a_retirar)
            if trabajo and trabajo.status == EstadoTrabajo.COMPLETADO:
                self._trabajos.remove(trabajo)
                self._reordenar_trabajos(emitir_senal=False)
                self._guardar()
                self.trabajo_eliminado.emit(id_a_retirar)
                self.orden_cambiado.emit()
                self._emitir_cambio_conteo()

        self._procesar_siguiente()

    def _al_trabajo_fallido(self, id_trabajo: str, codigo: str, detalle: str) -> None:
        trabajo = self.obtener_trabajo(id_trabajo)
        self._id_trabajo_activo = None

        if trabajo:
            actualizar_fase_trabajo(trabajo, FaseTrabajo.ERROR, error_code=codigo, error_detail=detalle)
            self._reordenar_trabajos()
            self._guardar()
            self.trabajo_actualizado.emit(id_trabajo)
            self.orden_cambiado.emit()
            self._emitir_cambio_conteo()
            self.trabajo_fallido_notificable.emit(trabajo)

        self._worker.fallido.emit(id_trabajo, codigo, detalle)
        self._procesar_siguiente()

    def _al_trabajo_cancelado(self, id_trabajo: str) -> None:
        trabajo = self.obtener_trabajo(id_trabajo)
        self._id_trabajo_activo = None

        if trabajo:
            actualizar_fase_trabajo(trabajo, FaseTrabajo.CANCELADO)
            self._reordenar_trabajos()
            self._guardar()
            self.trabajo_actualizado.emit(id_trabajo)
            self.orden_cambiado.emit()
            self._emitir_cambio_conteo()

        self._worker.cancelado.emit(id_trabajo)
        self._procesar_siguiente()

    def _guardar(self) -> None:
        try:
            guardar_cola(self._trabajos)
        except Exception as err:
            logger.warning("No se pudo guardar la cola: %s", err)

    def obtener_conteo_actual(self) -> tuple[int, int, int, int]:
        """Calcula (total, en_espera, completados, errores)."""
        total = len(self._trabajos)
        espera = sum(1 for t in self._trabajos if t.status == EstadoTrabajo.EN_ESPERA)
        completos = sum(1 for t in self._trabajos if t.status == EstadoTrabajo.COMPLETADO)
        errores = sum(
            1
            for t in self._trabajos
            if t.status in (EstadoTrabajo.ERROR, EstadoTrabajo.INTERRUMPIDO, EstadoTrabajo.CANCELADO)
        )
        return total, espera, completos, errores

    def _emitir_cambio_conteo(self) -> None:
        total, espera, completos, errores = self.obtener_conteo_actual()
        self.conteo_cambiado.emit(total, espera, completos, errores)

    def cerrar(self) -> None:
        """Detiene de forma limpia los hilos y temporizadores."""
        self._temporizador_finalizacion.stop()
        if self._worker:
            self._worker.cancelar()
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3000)
