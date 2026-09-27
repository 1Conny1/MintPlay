"""Diagnóstico del sistema y verificación de componentes esenciales."""

from __future__ import annotations

import logging
import platform
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

from .runtime_paths import obtener_ruta_ejecutable

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticoSistema:
    """Estado y versiones de los ejecutables y dependencias del sistema."""

    ffmpeg_disponible: bool = False
    ffmpeg_version: str = "No disponible"
    ffprobe_disponible: bool = False
    ffprobe_version: str = "No disponible"
    js_runtime_disponible: bool = False
    js_runtime_nombre: str = "No disponible"
    js_runtime_version: str = "No disponible"
    yt_dlp_ejs_disponible: bool = False
    yt_dlp_ejs_version: str = "No disponible"
    python_version: str = platform.python_version()
    sistema_operativo: str = f"{platform.system()} {platform.release()}"


def _obtener_primera_linea_proceso(args: list[str]) -> Optional[str]:
    """Ejecuta un comando con timeout breve para extraer la versión de salida."""
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        resultado = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
            check=False,
            creationflags=flags,
        )
        if resultado.returncode == 0 and resultado.stdout:
            return resultado.stdout.splitlines()[0].strip()
    except Exception:
        pass
    return None


def ejecutar_diagnostico() -> DiagnosticoSistema:
    """Verifica todos los binarios y módulos indispensables para MintPlay."""
    diag = DiagnosticoSistema()

    # ffmpeg
    ruta_ffmpeg = obtener_ruta_ejecutable("ffmpeg")
    if ruta_ffmpeg:
        linea = _obtener_primera_linea_proceso([str(ruta_ffmpeg), "-version"])
        if linea:
            diag.ffmpeg_disponible = True
            diag.ffmpeg_version = linea

    # ffprobe
    ruta_ffprobe = obtener_ruta_ejecutable("ffprobe")
    if ruta_ffprobe:
        linea = _obtener_primera_linea_proceso([str(ruta_ffprobe), "-version"])
        if linea:
            diag.ffprobe_disponible = True
            diag.ffprobe_version = linea

    # Motor JS (Node o Deno en bin/ o sistema)
    ruta_node = obtener_ruta_ejecutable("node")
    if ruta_node:
        linea = _obtener_primera_linea_proceso([str(ruta_node), "--version"])
        if linea:
            diag.js_runtime_disponible = True
            diag.js_runtime_nombre = "Node.js"
            diag.js_runtime_version = linea

    if not diag.js_runtime_disponible:
        ruta_deno = obtener_ruta_ejecutable("deno")
        if ruta_deno:
            linea = _obtener_primera_linea_proceso([str(ruta_deno), "--version"])
            if linea:
                diag.js_runtime_disponible = True
                diag.js_runtime_nombre = "Deno"
                diag.js_runtime_version = linea

    # yt-dlp-ejs solver
    try:
        import yt_dlp_ejs
        import yt_dlp_ejs.yt.solver

        diag.yt_dlp_ejs_disponible = True
        diag.yt_dlp_ejs_version = getattr(yt_dlp_ejs, "version", "disponible")
    except ImportError:
        diag.yt_dlp_ejs_disponible = False
        diag.yt_dlp_ejs_version = "No disponible"

    return diag
