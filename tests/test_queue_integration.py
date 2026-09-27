"""Pruebas de integración de la cola de descargas con servicio simulado y telemetría de hilo."""

import time
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QEventLoop, QThread, QTimer
from mintplay.domain.models import (
    EstadoTrabajo,
    FaseTrabajo,
    OpcionesDescarga,
    TipoMedio,
    TrabajoDescarga,
)
from mintplay.services.queue_manager import GestorCola


class ServicioDescargaSimulado:
    """Simulador de motor de descargas sin red para pruebas controladas."""

    def __init__(self, duracion_paso: float = 0.05, deberia_fallar: bool = False):
        self.duracion_paso = duracion_paso
        self.deberia_fallar = deberia_fallar
        self._cancelado = False
        self.hilos_ejecucion = []

    def descargar(self, trabajo: TrabajoDescarga, cb_progreso, cb_fase, es_cancelado) -> Path:
        self.hilos_ejecucion.append(QThread.currentThread())
        if es_cancelado():
            return Path("cancelado")

        cb_fase(FaseTrabajo.PREPARANDO)
        time.sleep(self.duracion_paso)

        if es_cancelado():
            return Path("cancelado")

        if self.deberia_fallar:
            raise RuntimeError("Fallo simulado de red o formato")

        cb_fase(FaseTrabajo.DESCARGANDO)
        for p in (25.0, 50.0, 75.0, 99.0):
            if es_cancelado():
                return Path("cancelado")
            cb_progreso(p, int(p * 1024), 102400, 10240.0, 2)
            time.sleep(self.duracion_paso)

        cb_fase(FaseTrabajo.PROCESANDO)
        time.sleep(self.duracion_paso)

        cb_fase(FaseTrabajo.VERIFICANDO)
        time.sleep(self.duracion_paso)

        return Path(f"{trabajo.destination_dir}/{trabajo.id}.mp4")

    def cancelar(self):
        self._cancelado = True


def test_trabajo_cambia_de_estado_con_servicio_simulado(qapp, tmp_path: Path):
    with patch("mintplay.services.persistence.obtener_directorio_datos_usuario", return_value=tmp_path):
        hilo_ui = QThread.currentThread()
        servicio = ServicioDescargaSimulado(duracion_paso=0.01)
        gestor = GestorCola(servicio)

        opciones = OpcionesDescarga(
            url="https://ejemplo.com/video1",
            custom_name="Video de Prueba",
            media_type=TipoMedio.VIDEO,
            target_extension="mp4",
            quality_choice="best",
            destination_dir=str(tmp_path),
        )
        trabajo = TrabajoDescarga.desde_opciones(opciones)

        estados_observados = []

        def al_actualizar(id_t):
            t = gestor.obtener_trabajo(id_t)
            if t:
                estados_observados.append((t.status, t.phase, t.progress))

        gestor.trabajo_actualizado.connect(al_actualizar)
        gestor.anadir_trabajo(trabajo)

        # Esperar a que el hilo complete
        loop = QEventLoop()
        gestor._worker.finalizado.connect(lambda *args: loop.quit())
        QTimer.singleShot(3000, loop.quit)  # Timeout de seguridad
        loop.exec()

        t_final = gestor.obtener_trabajo(trabajo.id)
        assert t_final is not None
        assert t_final.status == EstadoTrabajo.COMPLETADO
        assert t_final.phase == FaseTrabajo.FINALIZADO
        assert t_final.progress == 100.0

        # Confirmar que el servicio corrió en el QThread secundario y NO en el hilo gráfico
        assert len(servicio.hilos_ejecucion) == 1
        assert servicio.hilos_ejecucion[0] != hilo_ui
        assert gestor.metricas[trabajo.id].en_hilo_ui_worker is False

        fases = [e[1] for e in estados_observados]
        assert FaseTrabajo.PREPARANDO in fases
        assert FaseTrabajo.DESCARGANDO in fases
        assert FaseTrabajo.PROCESANDO in fases
        assert FaseTrabajo.VERIFICANDO in fases

        gestor.cerrar()


def test_cola_fifo_y_concurrencia_uno(qapp, tmp_path: Path):
    with patch("mintplay.services.persistence.obtener_directorio_datos_usuario", return_value=tmp_path):
        servicio = ServicioDescargaSimulado(duracion_paso=0.02)
        gestor = GestorCola(servicio)
        gestor._temporizador_finalizacion.setInterval(50)

        t1 = TrabajoDescarga(url="https://ejemplo.com/1", destination_dir=str(tmp_path))
        t2 = TrabajoDescarga(url="https://ejemplo.com/2", destination_dir=str(tmp_path))

        gestor.anadir_trabajo(t1)
        gestor.anadir_trabajo(t2)

        assert t1.status in (EstadoTrabajo.ACTIVO, EstadoTrabajo.EN_ESPERA)
        assert t2.status == EstadoTrabajo.EN_ESPERA

        gestor.cerrar()


def test_encolar_cinco_trabajos_rapido_bajo_150ms_durante_descarga(qapp, tmp_path: Path):
    """Verifica que añadir 5 enlaces seguidos durante una descarga activa es inmediato (<150 ms)."""
    with patch("mintplay.services.persistence.obtener_directorio_datos_usuario", return_value=tmp_path):
        servicio = ServicioDescargaSimulado(duracion_paso=0.15)
        gestor = GestorCola(servicio)

        t_inicio = time.perf_counter()
        ids = []
        for i in range(5):
            t_job = TrabajoDescarga(
                url=f"https://ejemplo.com/video_{i}",
                display_title=f"Vídeo {i}",
                destination_dir=str(tmp_path),
            )
            ids.append(t_job.id)
            gestor.anadir_trabajo(t_job)

        duracion_total_ms = (time.perf_counter() - t_inicio) * 1000.0
        # Los 5 trabajos juntos deben encolarse en mucho menos de 150 ms sin esperar al worker
        assert duracion_total_ms < 150.0
        assert len(gestor.trabajos) == 5
        assert gestor.obtener_trabajo(ids[0]).status == EstadoTrabajo.ACTIVO
        for id_pendiente in ids[1:]:
            assert gestor.obtener_trabajo(id_pendiente).status == EstadoTrabajo.EN_ESPERA

        gestor.cerrar()
