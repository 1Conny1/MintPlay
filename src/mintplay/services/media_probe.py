"""Verificación de medios y codecs usando ffprobe."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

from ..domain.models import TipoMedio
from .runtime_paths import obtener_ruta_ejecutable

logger = logging.getLogger(__name__)


@dataclass
class ResultadoSonda:
    """Información extraída de un archivo mediante ffprobe."""

    valido: bool
    formato: str = ""
    duracion: float = 0.0
    tiene_video: bool = False
    tiene_audio: bool = False
    ancho: Optional[int] = None
    alto: Optional[int] = None
    codec_video: Optional[str] = None
    codec_audio: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ResultadoVerificacion:
    """Resultado estructurado de la verificación multimedia posterior a la descarga."""

    es_valido: bool
    tiene_audio: bool = False
    tiene_video: bool = False
    ancho: Optional[int] = None
    alto: Optional[int] = None
    tamano_bytes: int = 0
    mensaje: Optional[str] = None


def inspeccionar_archivo(ruta_archivo: Path) -> ResultadoSonda:
    """Ejecuta ffprobe para inspeccionar los contenedores y flujos del archivo."""
    if not ruta_archivo.exists():
        return ResultadoSonda(valido=False, error="El archivo no existe.")

    if ruta_archivo.stat().st_size == 0:
        return ResultadoSonda(valido=False, error="El archivo está vacío (0 bytes).")

    ejecutable_ffprobe = obtener_ruta_ejecutable("ffprobe")
    if not ejecutable_ffprobe:
        return ResultadoSonda(
            valido=False,
            error="No se encontró el ejecutable ffprobe en el directorio bin.",
        )

    cmd = [
        str(ejecutable_ffprobe),
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(ruta_archivo),
    ]

    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        resultado = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            check=False,
            creationflags=flags,
        )
    except subprocess.TimeoutExpired:
        return ResultadoSonda(valido=False, error="ffprobe tardó demasiado tiempo en responder.")
    except Exception as err:
        return ResultadoSonda(valido=False, error=f"Error al ejecutar ffprobe: {err}")

    if resultado.returncode != 0:
        return ResultadoSonda(
            valido=False,
            error=f"ffprobe no pudo analizar el archivo (código {resultado.returncode}).",
        )

    try:
        datos = json.loads(resultado.stdout)
    except json.JSONDecodeError:
        return ResultadoSonda(valido=False, error="Salida JSON inválida de ffprobe.")

    streams: List[dict[str, Any]] = datos.get("streams", [])
    formato_info: dict[str, Any] = datos.get("format", {})

    tiene_video = False
    tiene_audio = False
    ancho = None
    alto = None
    codec_video = None
    codec_audio = None

    for s in streams:
        tipo = s.get("codec_type")
        if tipo == "video" and not tiene_video:
            tiene_video = True
            codec_video = s.get("codec_name")
            ancho = s.get("width")
            alto = s.get("height")
        elif tipo == "audio" and not tiene_audio:
            tiene_audio = True
            codec_audio = s.get("codec_name")

    duracion_str = formato_info.get("duration", "0")
    try:
        duracion = float(duracion_str)
    except ValueError:
        duracion = 0.0

    return ResultadoSonda(
        valido=True,
        formato=formato_info.get("format_name", ""),
        duracion=duracion,
        tiene_video=tiene_video,
        tiene_audio=tiene_audio,
        ancho=ancho,
        alto=alto,
        codec_video=codec_video,
        codec_audio=codec_audio,
    )


def validar_archivo_descargado(ruta_archivo: Path, tipo_esperado: TipoMedio) -> tuple[bool, Optional[str]]:
    """Verifica que el archivo exista, tenga contenido y cumpla con el tipo de medio esperado."""
    sonda = inspeccionar_archivo(ruta_archivo)
    if not sonda.valido:
        return False, sonda.error

    if tipo_esperado == TipoMedio.VIDEO:
        if not sonda.tiene_video:
            return False, "El archivo generado no contiene flujo de vídeo."
    elif tipo_esperado == TipoMedio.AUDIO:
        if not sonda.tiene_audio:
            return False, "El archivo generado no contiene flujo de audio."

    return True, None


def verificar_archivo_multimedia(ruta_archivo: Path, tipo_esperado: TipoMedio) -> ResultadoVerificacion:
    """Verifica el archivo descargado y devuelve un objeto de resultado detallado."""
    tamano = ruta_archivo.stat().st_size if ruta_archivo.exists() else 0
    sonda = inspeccionar_archivo(ruta_archivo)
    if not sonda.valido:
        return ResultadoVerificacion(
            es_valido=False,
            tamano_bytes=tamano,
            mensaje=sonda.error,
        )

    error: Optional[str] = None
    if tipo_esperado == TipoMedio.VIDEO and not sonda.tiene_video:
        error = "El archivo generado no contiene flujo de vídeo."
    elif tipo_esperado == TipoMedio.AUDIO and not sonda.tiene_audio:
        error = "El archivo generado no contiene flujo de audio."

    valido = error is None
    return ResultadoVerificacion(
        es_valido=valido,
        tiene_audio=sonda.tiene_audio,
        tiene_video=sonda.tiene_video,
        ancho=sonda.ancho,
        alto=sonda.alto,
        tamano_bytes=tamano,
        mensaje=error if not valido else "Archivo verificado correctamente",
    )
