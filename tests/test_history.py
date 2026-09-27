"""Pruebas unitarias y de integración para el historial local de descargas de MintPlay."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

import pytest
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from mintplay.domain.models import (
    EstadoTrabajo,
    FaseTrabajo,
    OpcionesDescarga,
    RegistroHistorial,
    TipoMedio,
    TrabajoDescarga,
)
from mintplay.services.history_manager import GestorHistorial
from mintplay.services.output_paths import resolver_ruta_sin_colision
from mintplay.services.persistence import (
    NOMBRE_ARCHIVO_HISTORIAL,
    cargar_historial,
    guardar_historial,
    registrar_en_historial,
)
from mintplay.services.queue_manager import GestorCola
from mintplay.ui.history_dialog import DialogoHistorial
from mintplay.ui.i18n_manager import obtener_traductor
from mintplay.ui.main_window import VentanaPrincipal


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app  # type: ignore[return-value]


class ServicioDescargaSimulado:
    """Servicio falso rápido para probar la integración entre GestorCola e historial."""

    def __init__(self, fallar: bool = False) -> None:
        self.fallar = fallar

    def descargar(
        self,
        trabajo: TrabajoDescarga,
        cb_progreso: Callable[
            [float, Optional[int], Optional[int], Optional[float], Optional[int]], None
        ],
        cb_fase: Callable[[FaseTrabajo], None],
        es_cancelado: Callable[[], bool],
    ) -> Path:
        cb_fase(FaseTrabajo.PREPARANDO)
        if self.fallar:
            raise RuntimeError("Fallo simulado de red")
        cb_fase(FaseTrabajo.DESCARGANDO)
        cb_progreso(100.0, 2048, 2048, 4096.0, 0)
        cb_fase(FaseTrabajo.VERIFICANDO)

        dir_dest = Path(trabajo.destination_dir)
        dir_dest.mkdir(parents=True, exist_ok=True)
        nombre_base = trabajo.custom_name or "video_descargado"
        ruta_final = resolver_ruta_sin_colision(
            dir_dest, f"{nombre_base}.{trabajo.target_extension}"
        )
        ruta_final.write_bytes(b"datos_multimedia_verificados" * 100)
        trabajo.file_size = ruta_final.stat().st_size
        if trabajo.media_type == TipoMedio.VIDEO:
            trabajo.effective_quality = "1080p"

        cb_fase(FaseTrabajo.FINALIZADO)
        return ruta_final


def _crear_trabajo_completado(
    tmp_path: Path,
    job_id: str = "job-100",
    attempt: int = 1,
    titulo: str = "Concierto Acústico en Vivo",
    custom_name: str = "concierto_acustico",
    plataforma: str = "YouTube",
    tipo: TipoMedio = TipoMedio.VIDEO,
    ext: str = "mp4",
    calidad: str = "1080p",
    crear_archivo: bool = True,
) -> TrabajoDescarga:
    ruta_archivo = tmp_path / f"{custom_name}.{ext}"
    if crear_archivo:
        ruta_archivo.write_bytes(b"contenido_prueba_mintplay" * 200)
    tamano = ruta_archivo.stat().st_size if crear_archivo else 4096

    return TrabajoDescarga(
        id=job_id,
        url=f"https://www.youtube.com/watch?v={job_id}",
        display_title=titulo,
        custom_name=custom_name,
        platform_hint=plataforma,
        media_type=tipo,
        target_extension=ext,
        quality_choice=calidad,
        effective_quality="1080p" if tipo == TipoMedio.VIDEO else None,
        destination_dir=str(tmp_path),
        status=EstadoTrabajo.COMPLETADO,
        phase=FaseTrabajo.FINALIZADO,
        output_path=str(ruta_archivo),
        file_size=tamano,
        attempt=attempt,
    )


def test_persistencia_y_deduplicacion_historial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica que solo trabajos completados se persistan, sin duplicados por (job_id, attempt)."""
    monkeypatch.setattr(
        "mintplay.services.persistence.obtener_directorio_datos_usuario",
        lambda: tmp_path,
    )

    # 1. Un trabajo fallido o en espera NO debe registrarse
    trabajo_fallido = _crear_trabajo_completado(tmp_path, job_id="job-err")
    trabajo_fallido.status = EstadoTrabajo.ERROR
    assert registrar_en_historial(trabajo_fallido) is None
    assert cargar_historial() == []

    # 2. Un trabajo completado sí se registra y persiste en history.json
    trabajo_ok = _crear_trabajo_completado(tmp_path, job_id="job-1", attempt=1)
    reg1 = registrar_en_historial(trabajo_ok)
    assert reg1 is not None
    assert (tmp_path / NOMBRE_ARCHIVO_HISTORIAL).is_file()

    # 3. Registrar el mismo (job_id, attempt) otra vez actualiza sin duplicar
    reg1_dup = registrar_en_historial(trabajo_ok)
    assert reg1_dup is not None
    cargados = cargar_historial()
    assert len(cargados) == 1
    assert cargados[0].job_id == "job-1"
    assert cargados[0].attempt == 1
    assert cargados[0].final_filename == "concierto_acustico.mp4"

    # 4. Un segundo intento exitoso o un nuevo trabajo añade un registro más reciente primero
    time.sleep(0.01)
    trabajo_2 = _crear_trabajo_completado(
        tmp_path,
        job_id="job-2",
        attempt=2,
        titulo="Podcast Episodio 42",
        custom_name="podcast_ep42",
        plataforma="X / Twitter",
        tipo=TipoMedio.AUDIO,
        ext="mp3",
        calidad="320",
    )
    registrar_en_historial(trabajo_2)

    cargados = cargar_historial()
    assert len(cargados) == 2
    assert cargados[0].job_id == "job-2"
    assert cargados[1].job_id == "job-1"


def test_recuperacion_ante_history_json_corrupto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si history.json está corrupto, crea respaldo .broken y devuelve lista vacía sin crashear."""
    monkeypatch.setattr(
        "mintplay.services.persistence.obtener_directorio_datos_usuario",
        lambda: tmp_path,
    )

    ruta_hist = tmp_path / NOMBRE_ARCHIVO_HISTORIAL
    ruta_hist.write_text("{json_invalido: [1, 2", encoding="utf-8")

    registros = cargar_historial()
    assert registros == []

    respaldos = list(tmp_path.glob("history.broken.*"))
    assert len(respaldos) >= 1


def test_quitar_y_vaciar_no_borran_archivos_fisicos(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """«Quitar del historial» y «Vaciar historial» jamás deben eliminar los archivos descargados."""
    monkeypatch.setattr(
        "mintplay.services.persistence.obtener_directorio_datos_usuario",
        lambda: tmp_path,
    )

    t1 = _crear_trabajo_completado(
        tmp_path, job_id="job-a", custom_name="video_uno", crear_archivo=True
    )
    t2 = _crear_trabajo_completado(
        tmp_path, job_id="job-b", custom_name="video_dos", crear_archivo=True
    )
    archivo_1 = Path(t1.output_path or "")
    archivo_2 = Path(t2.output_path or "")
    assert archivo_1.is_file()
    assert archivo_2.is_file()

    gestor_hist = GestorHistorial(cargar_al_iniciar=False)
    reg_a = gestor_hist.registrar_trabajo_completado(t1)
    reg_b = gestor_hist.registrar_trabajo_completado(t2)
    assert reg_a is not None and reg_b is not None
    assert gestor_hist.total_registros == 2

    # Quitar un registro individual
    assert gestor_hist.quitar_registro(reg_a.id) is True
    assert gestor_hist.total_registros == 1
    assert archivo_1.is_file(), "El archivo físico 1 NO debe borrarse al quitar del historial"

    # Vaciar todo el historial
    gestor_hist.vaciar_historial()
    assert gestor_hist.total_registros == 0
    assert cargar_historial() == []
    assert archivo_1.is_file(), "El archivo físico 1 debe seguir intacto tras vaciar el historial"
    assert archivo_2.is_file(), "El archivo físico 2 debe seguir intacto tras vaciar el historial"


def test_estado_archivo_no_encontrado_y_acciones_en_dialogo(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica el estado 'Archivo no encontrado', copiar enlace, redescargar e idioma en vivo."""
    monkeypatch.setattr(
        "mintplay.services.persistence.obtener_directorio_datos_usuario",
        lambda: tmp_path,
    )

    traductor = obtener_traductor("es")
    traductor.cambiar_idioma("es")

    t_existente = _crear_trabajo_completado(
        tmp_path,
        job_id="job-ok",
        titulo="Documental Naturaleza 4K",
        custom_name="doc_naturaleza",
        plataforma="YouTube",
        tipo=TipoMedio.VIDEO,
        ext="mp4",
        calidad="1080p",
        crear_archivo=True,
    )
    time.sleep(0.01)
    t_faltante = _crear_trabajo_completado(
        tmp_path,
        job_id="job-missing",
        titulo="Canción Movida de Carpeta",
        custom_name="cancion_movida",
        plataforma="TikTok",
        tipo=TipoMedio.AUDIO,
        ext="mp3",
        calidad="320",
        crear_archivo=False,
    )

    gestor_hist = GestorHistorial(cargar_al_iniciar=False)
    reg_ok = gestor_hist.registrar_trabajo_completado(t_existente)
    reg_missing = gestor_hist.registrar_trabajo_completado(t_faltante)
    assert reg_ok is not None and reg_missing is not None

    dlg = DialogoHistorial(gestor_hist, tema_inicial="dark")
    dlg.show()
    qapp.processEvents()

    tarjetas = dlg.tarjetas_visibles
    assert reg_ok.id in tarjetas
    assert reg_missing.id in tarjetas

    card_ok = tarjetas[reg_ok.id]
    card_missing = tarjetas[reg_missing.id]

    # Verificar estado de archivo existente vs archivo faltante en español
    assert "Archivo disponible" in card_ok.lbl_estado_archivo.text()
    assert card_ok.btn_abrir_archivo.isEnabled() is True
    assert card_ok.btn_abrir_carpeta.isEnabled() is True

    assert card_missing.lbl_estado_archivo.text() == "Archivo no encontrado"
    assert card_missing.btn_abrir_archivo.isEnabled() is False
    # La carpeta tmp_path sí existe, por lo que Abrir carpeta sigue disponible
    assert card_missing.btn_abrir_carpeta.isEnabled() is True
    assert card_missing.btn_redescargar.isEnabled() is True
    assert card_missing.btn_quitar.isEnabled() is True

    # Si intentamos abrir el archivo faltante programáticamente, no lanza excepción y devuelve False
    assert card_missing.ejecutar_abrir_archivo() is False

    # Probar Copiar enlace
    assert card_ok.ejecutar_copiar_enlace() is True
    assert QGuiApplication.clipboard().text() == t_existente.url

    # Probar Volver a descargar
    redescargas_recibidas: list[tuple[OpcionesDescarga, str]] = []
    dlg.redescarga_solicitada.connect(
        lambda opc, plat: redescargas_recibidas.append((opc, plat))
    )
    card_missing.ejecutar_redescargar()
    assert len(redescargas_recibidas) == 1
    opc_recibida, plat_recibida = redescargas_recibidas[0]
    assert opc_recibida.url == t_faltante.url
    assert opc_recibida.custom_name == "cancion_movida"
    assert opc_recibida.media_type == TipoMedio.AUDIO
    assert opc_recibida.target_extension == "mp3"
    assert opc_recibida.quality_choice == "320"
    assert plat_recibida == "TikTok"

    # Probar búsqueda y cambio de idioma en vivo conservando el filtro
    dlg.txt_buscar.setText("Canción")
    qapp.processEvents()
    assert len(dlg.tarjetas_visibles) == 1
    assert reg_missing.id in dlg.tarjetas_visibles

    traductor.cambiar_idioma("en")
    qapp.processEvents()
    assert dlg.txt_buscar.text() == "Canción"
    card_missing_en = dlg.tarjetas_visibles[reg_missing.id]
    assert card_missing_en.lbl_estado_archivo.text() == "File not found"
    assert card_missing_en.btn_redescargar.text() == "Download again"

    traductor.cambiar_idioma("es")
    dlg.close()


def test_rendimiento_500_registros_busqueda_y_apertura(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica que abrir y filtrar 500 registros sea fluido gracias a la carga por lotes."""
    monkeypatch.setattr(
        "mintplay.services.persistence.obtener_directorio_datos_usuario",
        lambda: tmp_path,
    )

    ahora = time.time()
    registros_masivos = [
        RegistroHistorial(
            id=f"job-{i}:1",
            job_id=f"job-{i}",
            attempt=1,
            url=f"https://www.youtube.com/watch?v=vid{i}",
            title=f"Vídeo de prueba número {i}",
            custom_name=f"video_{i}",
            final_filename=f"video_{i}.mp4",
            output_path=str(tmp_path / f"video_{i}.mp4"),
            destination_dir=str(tmp_path),
            platform_hint="YouTube" if i % 2 == 0 else "Instagram",
            media_type=TipoMedio.VIDEO if i % 3 != 0 else TipoMedio.AUDIO,
            target_extension="mp4" if i % 3 != 0 else "mp3",
            quality_choice="1080p" if i % 3 != 0 else "320",
            completed_at=ahora - i,
            file_size=1024 * (i + 1),
        )
        for i in range(500)
    ]
    guardar_historial(registros_masivos)

    t0 = time.perf_counter()
    gestor_hist = GestorHistorial(cargar_al_iniciar=True)
    dlg = DialogoHistorial(gestor_hist, tema_inicial="dark")
    t_apertura_ms = (time.perf_counter() - t0) * 1000.0

    assert gestor_hist.total_registros == 500
    # Solo se instancia el primer lote (40 tarjetas), no las 500 de golpe
    assert len(dlg.tarjetas_visibles) == 40
    assert t_apertura_ms < 500.0

    t1 = time.perf_counter()
    dlg.txt_buscar.setText("499")
    t_busqueda_ms = (time.perf_counter() - t1) * 1000.0

    assert len(dlg.tarjetas_visibles) == 1
    assert "job-499:1" in dlg.tarjetas_visibles
    assert t_busqueda_ms < 150.0
    dlg.close()


def test_integracion_cola_a_historial_y_redescarga_sin_colision(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Al completarse un trabajo en GestorCola se añade al historial y permite redescargar sin sobrescribir."""
    monkeypatch.setattr(
        "mintplay.services.persistence.obtener_directorio_datos_usuario",
        lambda: tmp_path,
    )

    servicio = ServicioDescargaSimulado(fallar=False)
    gestor_cola = GestorCola(servicio)
    ventana = VentanaPrincipal(
        gestor_cola,
        {
            "idioma": "es",
            "tema": "dark",
            "directorio_descargas": str(tmp_path),
        },
    )

    opciones = OpcionesDescarga(
        url="https://www.youtube.com/watch?v=demo123",
        custom_name="demo_clip",
        media_type=TipoMedio.VIDEO,
        target_extension="mp4",
        quality_choice="1080p",
        destination_dir=str(tmp_path),
    )

    ventana._al_solicitar_descarga(opciones, "YouTube")

    # Esperar hasta que el worker complete la primera descarga
    limite = time.perf_counter() + 4.0
    while gestor_cola.historial.total_registros < 1 and time.perf_counter() < limite:
        qapp.processEvents()
        time.sleep(0.02)

    assert gestor_cola.historial.total_registros == 1
    primer_reg = gestor_cola.historial.registros[0]
    assert primer_reg.final_filename == "demo_clip.mp4"
    assert Path(primer_reg.output_path).is_file()

    # Abrir diálogo de historial desde la ventana principal y solicitar "Volver a descargar"
    dlg_hist = ventana._abrir_historial()
    qapp.processEvents()
    tarjeta = dlg_hist.tarjetas_visibles[primer_reg.id]

    # Forzar liberación del temporizador de retiro de 5s para que arranque de inmediato la redescarga
    gestor_cola._al_vencer_temporizador_finalizacion()
    tarjeta.ejecutar_redescargar()

    limite = time.perf_counter() + 4.0
    while gestor_cola.historial.total_registros < 2 and time.perf_counter() < limite:
        qapp.processEvents()
        time.sleep(0.02)

    assert gestor_cola.historial.total_registros == 2
    segundo_reg = gestor_cola.historial.registros[0]
    # Verifica que no sobrescribió demo_clip.mp4 sino que generó demo_clip (2).mp4
    assert segundo_reg.final_filename == "demo_clip (2).mp4"
    assert Path(primer_reg.output_path).is_file()
    assert Path(segundo_reg.output_path).is_file()

    dlg_hist.close()
    gestor_cola._trabajos.clear()
    ventana.close()
