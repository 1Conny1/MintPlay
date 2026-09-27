"""Reglas de formatos, calidades y configuración para el motor de descarga."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from .models import (
    CalidadAudio,
    CalidadVideo,
    FormatoAudio,
    FormatoVideo,
    TipoMedio,
)


# Opciones válidas de formatos según el tipo de medio
FORMATOS_POR_TIPO = {
    TipoMedio.VIDEO: [FormatoVideo.MP4.value, FormatoVideo.MKV.value, FormatoVideo.WEBM.value],
    TipoMedio.AUDIO: [
        FormatoAudio.MP3.value,
        FormatoAudio.M4A.value,
        FormatoAudio.FLAC.value,
        FormatoAudio.WAV.value,
    ],
}

# Opciones válidas de calidad según el formato elegido
CALIDADES_POR_FORMATO = {
    FormatoVideo.MP4.value: [
        CalidadVideo.MEJOR.value,
        CalidadVideo.P1080.value,
        CalidadVideo.P720.value,
        CalidadVideo.P480.value,
    ],
    FormatoVideo.MKV.value: [
        CalidadVideo.MEJOR.value,
        CalidadVideo.P1080.value,
        CalidadVideo.P720.value,
        CalidadVideo.P480.value,
    ],
    FormatoVideo.WEBM.value: [
        CalidadVideo.MEJOR.value,
        CalidadVideo.P1080.value,
        CalidadVideo.P720.value,
        CalidadVideo.P480.value,
    ],
    FormatoAudio.MP3.value: [
        CalidadAudio.KBPS_128.value,
        CalidadAudio.KBPS_192.value,
        CalidadAudio.KBPS_256.value,
        CalidadAudio.KBPS_320.value,
    ],
    FormatoAudio.M4A.value: [CalidadAudio.MEJOR.value],
    FormatoAudio.FLAC.value: [CalidadAudio.SIN_PERDIDA.value],
    FormatoAudio.WAV.value: [CalidadAudio.SIN_PERDIDA.value],
}

MAPA_ALTURAS_VIDEO = {
    CalidadVideo.MEJOR.value: None,
    CalidadVideo.P1080.value: 1080,
    CalidadVideo.P720.value: 720,
    CalidadVideo.P480.value: 480,
}


@dataclass
class ConfiguracionYtDlp:
    """Configuración resultante para pasar a yt-dlp."""

    format_selector: str
    postprocessors: List[dict[str, Any]]
    merge_output_format: Optional[str] = None
    requiere_recodificacion: bool = False
    aviso_usuario: Optional[str] = None


class ErrorFormatoNoAdecuado(ValueError):
    """Excepción cuando el medio no ofrece ningún formato compatible."""


def obtener_formato_predeterminado(tipo: TipoMedio) -> str:
    """Devuelve el formato por defecto para vídeo o audio."""
    return FormatoVideo.MP4.value if tipo == TipoMedio.VIDEO else FormatoAudio.MP3.value


def obtener_calidad_predeterminada(formato: str) -> str:
    """Devuelve la opción de calidad inicial según el formato."""
    if formato == FormatoAudio.MP3.value:
        return CalidadAudio.KBPS_192.value
    calidades = CALIDADES_POR_FORMATO.get(formato, [])
    return calidades[0] if calidades else "best"


def obtener_clave_ayuda_calidad(formato: str) -> str:
    """Devuelve la clave de traducción con la explicación técnica de calidad para el formato."""
    mapa = {
        FormatoAudio.MP3.value: "hint_quality_mp3",
        FormatoAudio.M4A.value: "hint_quality_m4a",
        FormatoAudio.FLAC.value: "hint_quality_lossless",
        FormatoAudio.WAV.value: "hint_quality_lossless",
        FormatoVideo.MP4.value: "hint_quality_video_mp4",
        FormatoVideo.MKV.value: "hint_quality_video_mkv",
        FormatoVideo.WEBM.value: "hint_quality_video_webm",
    }
    return mapa.get(formato, "hint_quality_video_mp4")


def es_selector_calidad_interactivo(formato: str) -> bool:
    """Indica si el formato admite elegir entre múltiples niveles de calidad o bitrate."""
    return formato not in (FormatoAudio.FLAC.value, FormatoAudio.WAV.value)


def resolver_limite_altura(calidad: str) -> Optional[int]:
    """Obtiene el límite superior de píxeles verticales si aplica."""
    return MAPA_ALTURAS_VIDEO.get(calidad)


def verificar_compatibilidad(
    tipo: TipoMedio, formato: str, calidad: str
) -> Tuple[bool, str, str]:
    """Verifica si la combinación es válida y devuelve versión saneada."""
    formatos_validos = FORMATOS_POR_TIPO.get(tipo, [])
    fmt_final = formato if formato in formatos_validos else formatos_validos[0]

    calidades_validas = CALIDADES_POR_FORMATO.get(fmt_final, ["best"])
    calidad_final = (
        calidad
        if calidad in calidades_validas
        else obtener_calidad_predeterminada(fmt_final)
    )

    es_valido = (fmt_final == formato) and (calidad_final == calidad)
    return es_valido, fmt_final, calidad_final


def inspeccionar_stream_mp4_h264(formats: list[dict[str, Any]]) -> bool:
    """Verifica si existe al menos una pista de vídeo codificada en H.264."""
    for f in formats:
        vcodec = f.get("vcodec", "")
        if vcodec and (vcodec.startswith("avc1") or vcodec.startswith("h264")):
            return True
    return False


def construir_configuracion_yt_dlp(
    tipo: TipoMedio,
    formato: str,
    calidad: str,
    metadatos: Optional[dict[str, Any]] = None,
) -> ConfiguracionYtDlp:
    """Construye los selectores de formato y posprocesadores adecuados para yt-dlp."""
    _, fmt, cal = verificar_compatibilidad(tipo, formato, calidad)

    postprocessors: List[dict[str, Any]] = []
    aviso: Optional[str] = None
    requiere_recodificacion = False

    if tipo == TipoMedio.VIDEO:
        limite_altura = resolver_limite_altura(cal)
        filtro_h = f"[height<={limite_altura}]" if limite_altura else ""

        if fmt == FormatoVideo.MP4.value:
            # Si inspeccionamos formatos y no hay avc1, se requerirá transcodificación o remux
            if metadatos and "formats" in metadatos:
                tiene_h264 = inspeccionar_stream_mp4_h264(metadatos["formats"])
                if not tiene_h264:
                    requiere_recodificacion = True
                    aviso = "La fuente no dispone de H.264 nativo; se convertirá para máxima compatibilidad MP4."

            # Selector preferente MP4 con fallback
            selector = (
                f"bestvideo{filtro_h}[ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo{filtro_h}+bestaudio/"
                f"best{filtro_h}/best"
            )
            merge_fmt = "mp4"

        elif fmt == FormatoVideo.MKV.value:
            selector = f"bestvideo{filtro_h}+bestaudio/best{filtro_h}/best"
            merge_fmt = "mkv"

        elif fmt == FormatoVideo.WEBM.value:
            selector = (
                f"bestvideo{filtro_h}[ext=webm]+bestaudio[ext=webm]/"
                f"bestvideo{filtro_h}+bestaudio/"
                f"best{filtro_h}/best"
            )
            merge_fmt = "webm"
        else:
            selector = f"bestvideo{filtro_h}+bestaudio/best{filtro_h}/best"
            merge_fmt = fmt

        return ConfiguracionYtDlp(
            format_selector=selector,
            postprocessors=postprocessors,
            merge_output_format=merge_fmt,
            requiere_recodificacion=requiere_recodificacion,
            aviso_usuario=aviso,
        )

    else:
        # Modo audio
        if fmt == FormatoAudio.MP3.value:
            selector = "bestaudio/best"
            bitrate = cal if cal in ("128", "192", "256", "320") else "192"
            postprocessors.append(
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": bitrate,
                }
            )
        elif fmt == FormatoAudio.M4A.value:
            selector = "bestaudio[ext=m4a]/bestaudio/best"
            postprocessors.append(
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                }
            )
        elif fmt == FormatoAudio.FLAC.value:
            selector = "bestaudio/best"
            postprocessors.append(
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "flac",
                }
            )
        elif fmt == FormatoAudio.WAV.value:
            selector = "bestaudio/best"
            postprocessors.append(
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "wav",
                }
            )
        else:
            selector = "bestaudio/best"
            postprocessors.append(
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": fmt,
                }
            )

        return ConfiguracionYtDlp(
            format_selector=selector,
            postprocessors=postprocessors,
            merge_output_format=None,
            requiere_recodificacion=False,
            aviso_usuario=None,
        )


def construir_config_ytdlp(
    tipo: TipoMedio,
    formato: str,
    calidad: str,
    metadatos: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Adaptador de conveniencia que devuelve el diccionario de configuración para yt-dlp."""
    cfg = construir_configuracion_yt_dlp(tipo, formato, calidad, metadatos)
    opciones: dict[str, Any] = {
        "format": cfg.format_selector,
        "postprocessors": cfg.postprocessors,
    }
    if cfg.merge_output_format:
        opciones["merge_output_format"] = cfg.merge_output_format
    return opciones
