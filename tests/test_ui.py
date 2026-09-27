"""Pruebas unitarias de los componentes de la interfaz de usuario, temas, iconos SVG e idiomas."""

from pathlib import Path
from unittest.mock import patch

from mintplay.domain.models import (
    EstadoTrabajo,
    FaseTrabajo,
    OpcionesDescarga,
    TipoMedio,
    TrabajoDescarga,
)
from mintplay.services.queue_manager import GestorCola
from mintplay.services.runtime_paths import obtener_ruta_icono
from mintplay.ui.download_form import (
    FormularioDescarga,
    estimar_plataforma_url,
    traducir_etiqueta_calidad,
)
from mintplay.ui.i18n_manager import obtener_traductor, t
from mintplay.ui.job_card import TarjetaTrabajo
from mintplay.ui.main_window import VentanaPrincipal
from mintplay.ui.theme import cargar_icono_svg, generar_hoja_estilos


class ServicioInerte:
    """Servicio de prueba que mantiene el trabajo activo sin bloquear."""

    def descargar(self, trabajo, cb_progreso, cb_fase, es_cancelado):
        import time

        cb_fase(FaseTrabajo.DESCARGANDO)
        cb_progreso(42.0, 42000, 100000, 5120.0, 10)
        for _ in range(20):
            if es_cancelado():
                break
            time.sleep(0.02)
        return Path(trabajo.destination_dir) / "out.mp4"


def test_estimar_plataforma_url():
    obtener_traductor("es").cambiar_idioma("es")
    assert estimar_plataforma_url("") == t("waiting_url")
    assert estimar_plataforma_url("invalid_url") == t("waiting_url")
    assert estimar_plataforma_url("https://www.youtube.com/watch?v=123") == "YouTube"
    assert estimar_plataforma_url("https://youtu.be/123") == "YouTube"
    assert estimar_plataforma_url("https://vimeo.com/12345") == "Vimeo"
    assert estimar_plataforma_url("https://soundcloud.com/artist/track") == "SoundCloud"
    assert estimar_plataforma_url("https://www.tiktok.com/@user/video/123") == "TikTok"
    assert estimar_plataforma_url("https://x.com/user/status/123") == "X / Twitter"
    assert estimar_plataforma_url("https://example.com/media.mp4") == "Otro sitio"


def test_formulario_validacion_url_invalida(qapp, tmp_path: Path):
    form = FormularioDescarga(str(tmp_path))
    form.txt_url.setText("esto no es una url")
    llamada = []
    form.descarga_solicitada.connect(lambda opts, plat: llamada.append(opts))

    form._al_pulsar_anadir()
    assert len(llamada) == 0
    assert not form.lbl_error_url.isHidden()


def test_formulario_emite_opciones_inmutables_y_se_limpia(qapp, tmp_path: Path):
    form = FormularioDescarga(str(tmp_path))
    form.txt_url.setText("https://ejemplo.com/video")
    form.txt_nombre.setText("Mi Video Personal")

    opciones_recibidas = []
    form.descarga_solicitada.connect(lambda opts, plat: opciones_recibidas.append((opts, plat)))

    form._al_pulsar_anadir()

    assert len(opciones_recibidas) == 1
    opts, plat = opciones_recibidas[0]
    assert opts.url == "https://ejemplo.com/video"
    assert opts.custom_name == "Mi Video Personal"
    assert opts.media_type == TipoMedio.VIDEO
    assert opts.target_extension == "mp4"

    # Verificar que el formulario se limpió para recibir el siguiente enlace
    assert form.txt_url.text() == ""
    assert form.txt_nombre.text() == ""


def test_cambio_tipo_medio_y_calidad_audio_sin_mejor_disponible(qapp, tmp_path: Path):
    obtener_traductor("es").cambiar_idioma("es")
    form = FormularioDescarga(str(tmp_path))

    # Cambiar a Audio (MP3 predeterminado)
    idx_audio = form.cmb_tipo.findData(TipoMedio.AUDIO.value)
    form.cmb_tipo.setCurrentIndex(idx_audio)

    assert form.cmb_formato.currentData() == "mp3"
    assert form.cmb_calidad.currentData() == "192"
    assert form.cmb_calidad.isEnabled() is True
    assert form.lbl_ayuda_calidad.text() == "La calidad final depende del audio original"

    # Ninguna opción de MP3 debe afirmar "mejor disponible"
    for i in range(form.cmb_calidad.count()):
        texto_item = form.cmb_calidad.itemText(i).lower()
        assert "mejor disponible" not in texto_item
        assert "best available" not in texto_item

    # Cambiar a FLAC: selector de bitrate desactivado con explicación sin pérdida
    idx_flac = form.cmb_formato.findData("flac")
    form.cmb_formato.setCurrentIndex(idx_flac)
    assert form.cmb_calidad.isEnabled() is False
    assert "conversión" in form.lbl_ayuda_calidad.text().lower()

    # Cambiar a M4A: selector activo con "Automática según la fuente"
    idx_m4a = form.cmb_formato.findData("m4a")
    form.cmb_formato.setCurrentIndex(idx_m4a)
    assert form.cmb_calidad.isEnabled() is True
    assert form.cmb_calidad.currentText() == "Automática según la fuente"

    # Cambiar de vuelta a Video
    idx_video = form.cmb_tipo.findData(TipoMedio.VIDEO.value)
    form.cmb_tipo.setCurrentIndex(idx_video)

    assert form.cmb_formato.currentData() == "mp4"
    assert form.cmb_calidad.isEnabled() is True
    assert form.cmb_calidad.currentText() == "Mejor disponible"


def test_tarjeta_actualiza_estado_y_botones(qapp, tmp_path: Path):
    obtener_traductor("es").cambiar_idioma("es")
    trabajo = TrabajoDescarga(url="https://ejemplo.com/video", display_title="Video Prueba")
    tarjeta = TarjetaTrabajo(trabajo)

    assert not tarjeta.btn_quitar.isHidden()
    assert tarjeta.btn_cancelar.isHidden()
    assert tarjeta.btn_abrir_archivo.isHidden()
    # En espera la barra de progreso permanece oculta para limpieza visual
    assert tarjeta.barra_progreso.isHidden()

    # Cambiar a activo
    trabajo.status = EstadoTrabajo.ACTIVO
    trabajo.phase = FaseTrabajo.DESCARGANDO
    tarjeta.actualizar_datos(trabajo)
    assert tarjeta.btn_quitar.isHidden()
    assert not tarjeta.btn_cancelar.isHidden()
    assert not tarjeta.barra_progreso.isHidden()

    # Cambiar a completado
    trabajo.status = EstadoTrabajo.COMPLETADO
    trabajo.phase = FaseTrabajo.FINALIZADO
    tarjeta.actualizar_datos(trabajo)
    assert not tarjeta.btn_abrir_archivo.isHidden()
    assert not tarjeta.btn_abrir_carpeta.isHidden()


def test_iconos_svg_propios_existen_y_renderizan(qapp):
    for nombre in ("sun.svg", "moon.svg", "settings.svg", "empty-wind.svg"):
        ruta = obtener_ruta_icono(nombre)
        assert ruta.exists(), f"Falta el icono SVG requerido: {nombre}"

    icono_sol = cargar_icono_svg("sun.svg", tema="dark")
    icono_luna = cargar_icono_svg("moon.svg", tema="light")
    assert not icono_sol.isNull()
    assert not icono_luna.isNull()


def test_cambio_idioma_es_en_es_preserva_datos_y_actualiza_tarjetas(qapp, tmp_path: Path):
    """Prueba ES -> EN -> ES con formulario lleno, descarga activa y tarjeta fallida."""
    with patch("mintplay.services.persistence.obtener_directorio_datos_usuario", return_value=tmp_path):
        obtener_traductor("es").cambiar_idioma("es")
        gestor = GestorCola(ServicioInerte())

        t_activo = TrabajoDescarga(
            url="https://www.youtube.com/watch?v=activo1",
            display_title="Concierto en Vivo",
            platform_hint="YouTube",
            media_type=TipoMedio.AUDIO,
            target_extension="mp3",
            quality_choice="256",
            destination_dir=str(tmp_path),
            status=EstadoTrabajo.ACTIVO,
            phase=FaseTrabajo.DESCARGANDO,
            progress=45.0,
        )
        t_fallido = TrabajoDescarga(
            url="https://ejemplo.com/roto",
            display_title="Enlace Caído",
            platform_hint="Otro sitio",
            media_type=TipoMedio.VIDEO,
            target_extension="mp4",
            quality_choice="best",
            destination_dir=str(tmp_path),
            status=EstadoTrabajo.ERROR,
            phase=FaseTrabajo.ERROR,
            error_code="UNAVAILABLE_MEDIA",
            error_detail="HTTP 404 Not Found",
        )
        gestor.inicializar_con_trabajos([t_activo, t_fallido])

        cfg = {"idioma": "es", "tema": "dark", "directorio_descargas": str(tmp_path)}
        ventana = VentanaPrincipal(gestor, cfg)

        # Rellenar formulario parcialmente y seleccionar Audio MP3 320
        ventana.formulario.txt_url.setText("https://vimeo.com/999888")
        ventana.formulario.txt_nombre.setText("Mi Borrador")
        ventana.formulario.cmb_tipo.setCurrentIndex(1)  # Audio
        idx_320 = ventana.formulario.cmb_calidad.findData("320")
        ventana.formulario.cmb_calidad.setCurrentIndex(idx_320)

        card_activa = ventana.panel_cola._tarjetas[t_activo.id]
        card_fallida = ventana.panel_cola._tarjetas[t_fallido.id]

        assert ventana.formulario.lbl_url.text() == "Dirección URL"
        assert ventana.formulario.lbl_ayuda_calidad.text() == "La calidad final depende del audio original"
        assert "Mejor disponible" in card_fallida.lbl_info_tecnica.text()
        assert card_activa.btn_cancelar.text() == "Cancelar"
        assert card_fallida.btn_reintentar.text() == "Reintentar"

        # Cambiar a EN
        ventana._alternar_idioma()
        assert ventana.traductor.idioma == "en"
        assert ventana.formulario.lbl_url.text() == "URL Address"
        assert ventana.formulario.lbl_nombre.text() == "File Name"
        assert ventana.formulario.lbl_ayuda_calidad.text() == "Final quality depends on the source audio"
        assert ventana.panel_cola.lbl_titulo.text() == "Download Queue"
        assert "Best available" in card_fallida.lbl_info_tecnica.text()
        assert card_fallida.lbl_plataforma.text() == "Other site"
        assert card_activa.btn_cancelar.text() == "Cancel"
        assert card_fallida.btn_reintentar.text() == "Retry"
        assert "unavailable" in card_fallida.lbl_resumen_error.text().lower()

        # Verificar que no se perdió ni URL ni nombre ni selección de formato/calidad
        assert ventana.formulario.txt_url.text() == "https://vimeo.com/999888"
        assert ventana.formulario.txt_nombre.text() == "Mi Borrador"
        assert ventana.formulario.cmb_tipo.currentData() == "audio"
        assert ventana.formulario.cmb_formato.currentData() == "mp3"
        assert ventana.formulario.cmb_calidad.currentData() == "320"

        # Cambiar de vuelta a ES
        ventana._alternar_idioma()
        assert ventana.traductor.idioma == "es"
        assert ventana.formulario.lbl_url.text() == "Dirección URL"
        assert "Mejor disponible" in card_fallida.lbl_info_tecnica.text()
        assert card_fallida.lbl_plataforma.text() == "Otro sitio"
        assert card_activa.btn_cancelar.text() == "Cancelar"
        assert ventana.formulario.cmb_calidad.currentData() == "320"

        gestor.cerrar()


def test_internacionalizacion_es_en():
    traductor = obtener_traductor("es")
    traductor.cambiar_idioma("es")
    assert t("type_video") == "Vídeo"

    traductor.cambiar_idioma("en")
    assert t("type_video") == "Video"

    traductor.cambiar_idioma("es")


def test_generar_hojas_estilo():
    qss_dark = generar_hoja_estilos("dark")
    assert "#111A1A" in qss_dark
    assert "#79D6B4" in qss_dark

    qss_light = generar_hoja_estilos("light")
    assert "#F5F8F3" in qss_light
    assert "#168569" in qss_light
