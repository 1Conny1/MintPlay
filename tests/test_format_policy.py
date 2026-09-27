"""Pruebas de la matriz de formatos y reglas de compatibilidad."""

from mintplay.domain.format_policy import (
    CALIDADES_POR_FORMATO,
    FORMATOS_POR_TIPO,
    construir_configuracion_yt_dlp,
    es_selector_calidad_interactivo,
    obtener_calidad_predeterminada,
    obtener_clave_ayuda_calidad,
    verificar_compatibilidad,
)
from mintplay.domain.models import CalidadAudio, CalidadVideo, FormatoAudio, FormatoVideo, TipoMedio


def test_formatos_disponibles_por_tipo():
    assert "mp4" in FORMATOS_POR_TIPO[TipoMedio.VIDEO]
    assert "mkv" in FORMATOS_POR_TIPO[TipoMedio.VIDEO]
    assert "webm" in FORMATOS_POR_TIPO[TipoMedio.VIDEO]

    assert "mp3" in FORMATOS_POR_TIPO[TipoMedio.AUDIO]
    assert "m4a" in FORMATOS_POR_TIPO[TipoMedio.AUDIO]
    assert "flac" in FORMATOS_POR_TIPO[TipoMedio.AUDIO]
    assert "wav" in FORMATOS_POR_TIPO[TipoMedio.AUDIO]


def test_verificar_compatibilidad_reajusta_incompatibles():
    # Si pedimos MP4 pero tipo Audio, debe reajustar a MP3 y su calidad predeterminada 192
    es_valido, fmt, cal = verificar_compatibilidad(TipoMedio.AUDIO, "mp4", "1080p")
    assert not es_valido
    assert fmt == "mp3"
    assert cal == "192"

    # Si pedimos MP3 pero tipo Video, debe reajustar a MP4
    es_valido, fmt, cal = verificar_compatibilidad(TipoMedio.VIDEO, "mp3", "320")
    assert not es_valido
    assert fmt == "mp4"
    assert cal == "best"


def test_mp3_bitrates_ordenados_y_predeterminado_192():
    assert CALIDADES_POR_FORMATO["mp3"] == ["128", "192", "256", "320"]
    assert obtener_calidad_predeterminada("mp3") == "192"
    assert obtener_clave_ayuda_calidad("mp3") == "hint_quality_mp3"
    assert es_selector_calidad_interactivo("mp3") is True


def test_formatos_sin_perdida_desactivan_selector_bitrate():
    assert es_selector_calidad_interactivo("flac") is False
    assert es_selector_calidad_interactivo("wav") is False
    assert obtener_clave_ayuda_calidad("flac") == "hint_quality_lossless"
    assert obtener_clave_ayuda_calidad("wav") == "hint_quality_lossless"
    assert es_selector_calidad_interactivo("m4a") is True
    assert obtener_clave_ayuda_calidad("m4a") == "hint_quality_m4a"


def test_construir_config_video_mp4_1080p():
    config = construir_configuracion_yt_dlp(TipoMedio.VIDEO, "mp4", "1080p")
    assert "height<=1080" in config.format_selector
    assert config.merge_output_format == "mp4"


def test_construir_config_audio_mp3_320():
    config = construir_configuracion_yt_dlp(TipoMedio.AUDIO, "mp3", "320")
    assert "bestaudio" in config.format_selector
    assert len(config.postprocessors) == 1
    assert config.postprocessors[0]["preferredcodec"] == "mp3"
    assert config.postprocessors[0]["preferredquality"] == "320"


def test_deteccion_transcodificacion_mp4_si_no_hay_h264():
    metadatos_sin_h264 = {
        "formats": [
            {"format_id": "1", "vcodec": "vp09.00.51.08.01", "acodec": "none"},
            {"format_id": "2", "vcodec": "none", "acodec": "opus"},
        ]
    }
    config = construir_configuracion_yt_dlp(
        TipoMedio.VIDEO, "mp4", "best", metadatos=metadatos_sin_h264
    )
    assert config.requiere_recodificacion is True
    assert config.aviso_usuario is not None
