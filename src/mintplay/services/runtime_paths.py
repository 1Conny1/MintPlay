"""Gestión de rutas de recursos, ejecutables y almacenamiento del usuario.

Resuelve ubicaciones transparentemente en entorno de desarrollo y en la
distribución congelada de PyInstaller (portable).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional


def es_congelado() -> bool:
    """Indica si el código se ejecuta desde un paquete empaquetado por PyInstaller."""
    return getattr(sys, "frozen", False)


def obtener_directorio_base() -> Path:
    """Devuelve el directorio base del código o del paquete distribuido."""
    if es_congelado():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent.parent


def obtener_directorio_bin() -> Path:
    """Devuelve la ruta a la carpeta con los binarios de FFmpeg, FFprobe y JS."""
    if es_congelado():
        carpeta_app = Path(sys.executable).resolve().parent
        # 1. Carpeta bin junto al ejecutable
        bin_dir = carpeta_app / "bin"
        if bin_dir.exists():
            return bin_dir
        # 2. Carpeta bin dentro de _internal
        internal_bin = carpeta_app / "_internal" / "bin"
        if internal_bin.exists():
            return internal_bin
        # 3. Fallback a _MEIPASS
        if hasattr(sys, "_MEIPASS"):
            meipass_bin = Path(sys._MEIPASS) / "bin"
            if meipass_bin.exists():
                return meipass_bin
        return bin_dir

    return obtener_directorio_base() / "bin"


obtener_directorio_binarios = obtener_directorio_bin


def obtener_ruta_ejecutable(nombre: str) -> Optional[Path]:
    """Busca un ejecutable auxiliar en el directorio bin interno."""
    ext = ".exe" if sys.platform == "win32" else ""
    nombre_con_ext = nombre if nombre.lower().endswith(ext) else f"{nombre}{ext}"
    ruta = obtener_directorio_bin() / nombre_con_ext
    if ruta.exists():
        return ruta
    return None


def obtener_directorio_recursos() -> Path:
    """Devuelve la ruta donde se alojan los recursos (i18n, iconos, etc.)."""
    if es_congelado():
        carpeta_app = Path(sys.executable).resolve().parent
        # 1. En PyInstaller onedir moderno, los datas están dentro de _internal/src/mintplay
        internal_src = carpeta_app / "_internal" / "src" / "mintplay"
        if internal_src.exists():
            return internal_src
        internal = carpeta_app / "_internal"
        if (internal / "i18n").exists():
            return internal
        if hasattr(sys, "_MEIPASS"):
            meipass_src = Path(sys._MEIPASS) / "src" / "mintplay"
            if meipass_src.exists():
                return meipass_src
            return Path(sys._MEIPASS)
        return carpeta_app

    return Path(__file__).resolve().parent.parent


def obtener_ruta_i18n(codigo_idioma: str) -> Path:
    """Devuelve la ruta al archivo de traducción JSON."""
    return obtener_directorio_recursos() / "i18n" / f"{codigo_idioma}.json"


def obtener_ruta_icono(nombre: str = "app.png") -> Path:
    """Devuelve la ruta al icono de la aplicación."""
    return obtener_directorio_recursos() / "assets" / "icons" / nombre


def obtener_directorio_datos_usuario() -> Path:
    """Devuelve la carpeta persistente para configuración, cola y logs del usuario.

    Nunca escribe en _MEIPASS ni junto al ejecutable para garantizar
    portabilidad limpia en perfiles de usuario.
    """
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA")
        if app_data:
            directorio = Path(app_data) / "MintPlay"
        else:
            directorio = Path.home() / ".mintplay"
    else:
        directorio = Path.home() / ".config" / "mintplay"

    directorio.mkdir(parents=True, exist_ok=True)
    return directorio


def obtener_directorio_descargas_predeterminado() -> Path:
    """Devuelve la carpeta Descargas estándar del sistema."""
    if sys.platform == "win32":
        userprofile = os.environ.get("USERPROFILE")
        if userprofile:
            descargas = Path(userprofile) / "Downloads"
            if descargas.exists():
                return descargas
    descargas = Path.home() / "Downloads"
    if descargas.exists():
        return descargas
    return Path.home()


def configurar_entorno_ejecucion() -> None:
    """Inyecta el directorio bin al PATH del proceso.

    Garantiza que yt-dlp, FFmpeg y el motor JS se encuentren automáticamente
    sin depender de instalaciones del sistema operativo anfitrión.
    """
    bin_dir = str(obtener_directorio_bin())
    path_actual = os.environ.get("PATH", "")
    if bin_dir not in path_actual:
        os.environ["PATH"] = bin_dir + os.pathsep + path_actual
