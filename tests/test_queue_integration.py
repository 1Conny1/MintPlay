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


class ServicioInerteCola:
    """Servicio sin ejecución automática en hilo para probar transiciones deterministas de cola y vista."""

    def __init__(self):
        self.llamadas_descargar = []

    def descargar(self, trabajo: TrabajoDescarga, cb_progreso, cb_fase, es_cancelado) -> Path:
        self.llamadas_descargar.append((trabajo.id, trabajo.attempt))
        time.sleep(0.05)
        return Path(f"{trabajo.destination_dir}/{trabajo.id}.mp4")

    def cancelar(self):
        pass


def test_secuencia_a_falla_b_descarga_reintentar_a_mantiene_b_arriba_y_a_espera(
    qapp, tmp_path: Path
):
    """Reproduce el caso exacto: A falla, B empieza a descargarse y se pulsa Reintentar en A."""
    from mintplay.services.persistence import cargar_cola
    from mintplay.ui.i18n_manager import obtener_traductor
    from mintplay.ui.queue_panel import PanelCola

    with patch(
        "mintplay.services.persistence.obtener_directorio_datos_usuario",
        return_value=tmp_path,
    ):
        obtener_traductor("es").cambiar_idioma("es")
        gestor = GestorCola(ServicioInerteCola())
        # Desconectar disparo real al QThread para controlar paso a paso las señales del worker
        gestor._iniciar_en_worker.disconnect(gestor._worker.procesar)
        inicios_worker = []
        gestor._iniciar_en_worker.connect(lambda job: inicios_worker.append((job.id, job.attempt)))

        panel = PanelCola(gestor)

        trabajo_a = TrabajoDescarga(
            id="job_A",
            url="https://www.youtube.com/watch?v=videoA",
            display_title="Vídeo A (Falla primero)",
            platform_hint="YouTube",
            destination_dir=str(tmp_path),
        )
        trabajo_b = TrabajoDescarga(
            id="job_B",
            url="https://www.youtube.com/watch?v=videoB",
            display_title="Vídeo B (Descarga activa)",
            platform_hint="YouTube",
            destination_dir=str(tmp_path),
        )

        # 1. Encolar A y B: A arranca como ACTIVO (índice 0) y B queda EN_ESPERA (índice 1)
        gestor.anadir_trabajo(trabajo_a)
        gestor.anadir_trabajo(trabajo_b)

        assert [t.id for t in gestor.trabajos] == ["job_A", "job_B"]
        assert panel.obtener_ids_tarjetas_visuales() == ["job_A", "job_B"]
        assert trabajo_a.status == EstadoTrabajo.ACTIVO
        assert trabajo_b.status == EstadoTrabajo.EN_ESPERA
        assert inicios_worker == [("job_A", 1)]

        card_a_ref = panel._tarjetas["job_A"]
        card_b_ref = panel._tarjetas["job_B"]

        # 2. A falla -> B empieza a descargarse inmediatamente y pasa arriba (índice 0); A baja (índice 1)
        gestor._al_trabajo_fallido("job_A", "NETWORK_ERROR", "Connection reset")
        gestor._a_fase_recibida("job_B", FaseTrabajo.DESCARGANDO.value)
        gestor._al_progreso_recibido("job_B", 35.0, 35000, 100000, 51200.0, 3)

        assert trabajo_b.status == EstadoTrabajo.ACTIVO
        assert trabajo_b.phase == FaseTrabajo.DESCARGANDO
        assert trabajo_a.status == EstadoTrabajo.ERROR
        assert [t.id for t in gestor.trabajos] == ["job_B", "job_A"]
        assert panel.obtener_ids_tarjetas_visuales() == ["job_B", "job_A"]
        assert inicios_worker == [("job_A", 1), ("job_B", 1)]

        # 3. Mientras B descarga, el usuario pulsa «Reintentar» en A
        card_a_ref.btn_reintentar.click()

        # Verificar que B sigue ACTIVO en primer lugar sin reiniciarse ni lanzar una segunda descarga
        assert trabajo_b.status == EstadoTrabajo.ACTIVO
        assert trabajo_b.phase == FaseTrabajo.DESCARGANDO
        assert trabajo_b.attempt == 1
        assert trabajo_b.progress == 35.0
        assert inicios_worker == [("job_A", 1), ("job_B", 1)]

        # Verificar que A limpió métricas del intento anterior, pasó a EN_ESPERA y está debajo de B
        assert trabajo_a.status == EstadoTrabajo.EN_ESPERA
        assert trabajo_a.phase == FaseTrabajo.EN_ESPERA
        assert trabajo_a.attempt == 2
        assert trabajo_a.progress == 0.0
        assert trabajo_a.error_code is None
        assert trabajo_a.error_detail is None
        assert [t.id for t in gestor.trabajos] == ["job_B", "job_A"]
        assert panel.obtener_ids_tarjetas_visuales() == ["job_B", "job_A"]
        assert "#1" in card_a_ref.lbl_fase.text()

        # 4. Nuevos ticks de progreso de B no recrean widgets ni alteran el orden
        gestor._al_progreso_recibido("job_B", 70.0, 70000, 100000, 51200.0, 1)
        assert panel._tarjetas["job_A"] is card_a_ref
        assert panel._tarjetas["job_B"] is card_b_ref
        assert panel.obtener_ids_tarjetas_visuales() == ["job_B", "job_A"]
        assert card_b_ref.barra_progreso.value() == 70

        # 5. Al terminar B (tras procesar y verificar) y vencer su confirmación de 5s, A inicia su segundo intento y sube al índice 0
        gestor._a_fase_recibida("job_B", FaseTrabajo.PROCESANDO.value)
        gestor._a_fase_recibida("job_B", FaseTrabajo.VERIFICANDO.value)
        gestor._al_trabajo_finalizado("job_B", str(tmp_path / "videoB.mp4"))
        assert trabajo_b.status == EstadoTrabajo.COMPLETADO
        gestor._temporizador_finalizacion.stop()
        gestor._al_vencer_temporizador_finalizacion()

        assert [t.id for t in gestor.trabajos] == ["job_A"]
        assert panel.obtener_ids_tarjetas_visuales() == ["job_A"]
        assert trabajo_a.status == EstadoTrabajo.ACTIVO
        assert inicios_worker == [("job_A", 1), ("job_B", 1), ("job_A", 2)]

        # Verificar también que la cola persistida respeta el orden canónico
        cola_disco = cargar_cola()
        assert [t.id for t in cola_disco] == ["job_A"]

        gestor.cerrar()


def test_reintento_con_pendientes_previas_y_multiples_errores_respeta_fifo(
    qapp, tmp_path: Path
):
    """Verifica que reintentar con tareas pendientes previas coloca la tarea al final de EN_ESPERA."""
    from mintplay.ui.queue_panel import PanelCola

    with patch(
        "mintplay.services.persistence.obtener_directorio_datos_usuario",
        return_value=tmp_path,
    ):
        gestor = GestorCola(ServicioInerteCola())
        gestor._iniciar_en_worker.disconnect(gestor._worker.procesar)
        panel = PanelCola(gestor)

        t_a = TrabajoDescarga(
            id="A",
            url="https://ejemplo.com/a",
            display_title="Tarea A",
            status=EstadoTrabajo.ERROR,
            phase=FaseTrabajo.ERROR,
            error_code="NETWORK_ERROR",
            destination_dir=str(tmp_path),
        )
        t_b = TrabajoDescarga(
            id="B",
            url="https://ejemplo.com/b",
            display_title="Tarea B",
            status=EstadoTrabajo.ACTIVO,
            phase=FaseTrabajo.DESCARGANDO,
            destination_dir=str(tmp_path),
        )
        t_c = TrabajoDescarga(
            id="C",
            url="https://ejemplo.com/c",
            display_title="Tarea C",
            status=EstadoTrabajo.EN_ESPERA,
            phase=FaseTrabajo.EN_ESPERA,
            destination_dir=str(tmp_path),
        )
        t_d = TrabajoDescarga(
            id="D",
            url="https://ejemplo.com/d",
            display_title="Tarea D",
            status=EstadoTrabajo.ERROR,
            phase=FaseTrabajo.ERROR,
            error_code="NETWORK_ERROR",
            destination_dir=str(tmp_path),
        )

        # Aunque se inicialicen en orden desordenado [A(ERROR), B(ACTIVO), D(ERROR), C(EN_ESPERA)],
        # el modelo y la vista aplican el orden canónico: [B(ACTIVO), C(EN_ESPERA), A(ERROR), D(ERROR)]
        gestor._id_trabajo_activo = "B"
        gestor.inicializar_con_trabajos([t_a, t_b, t_d, t_c])
        for t_item in gestor.trabajos:
            panel._al_anadir_trabajo(t_item.id)

        assert [t.id for t in gestor.trabajos] == ["B", "C", "A", "D"]
        assert panel.obtener_ids_tarjetas_visuales() == ["B", "C", "A", "D"]
        assert "#1" in panel._tarjetas["C"].lbl_fase.text()

        # Al pulsar Reintentar en A mientras B está activa y C espera:
        # A debe pasar al final de EN_ESPERA (detrás de C) y antes del error restante D
        gestor.reintentar_trabajo("A")
        assert [t.id for t in gestor.trabajos] == ["B", "C", "A", "D"]
        assert panel.obtener_ids_tarjetas_visuales() == ["B", "C", "A", "D"]
        assert "#1" in panel._tarjetas["C"].lbl_fase.text()
        assert "#2" in panel._tarjetas["A"].lbl_fase.text()

        # Caso sin tarea activa ni pendientes previas: quitar C (en espera), luego quitar B -> A arranca y falla
        gestor.quitar_trabajo("C")
        gestor._id_trabajo_activo = None
        t_b.status = EstadoTrabajo.COMPLETADO
        gestor.quitar_trabajo("B")
        # Ahora A inició (PREPARANDO) al quitarse B, y luego falla
        assert t_a.status == EstadoTrabajo.ACTIVO
        gestor._al_trabajo_fallido("A", "NETWORK_ERROR", "Fallo")

        assert [t.id for t in gestor.trabajos] == ["A", "D"]
        assert t_a.status == EstadoTrabajo.ERROR
        assert t_d.status == EstadoTrabajo.ERROR

        # Al reintentar D (que estaba en segundo lugar) cuando no hay activas ni pendientes previas,
        # D pasa a ACTIVO y sube inmediatamente al primer lugar por encima de A(ERROR)
        gestor.reintentar_trabajo("D")
        assert t_d.status == EstadoTrabajo.ACTIVO
        assert [t.id for t in gestor.trabajos] == ["D", "A"]
        assert panel.obtener_ids_tarjetas_visuales() == ["D", "A"]

        gestor.cerrar()

