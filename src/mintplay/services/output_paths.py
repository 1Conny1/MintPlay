"""Sanitización de nombres de archivo, resolución de colisiones y rutas temporales."""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path
from typing import Optional, Set, Union

# Caracteres no permitidos en Windows: < > : " / \ | ? * y caracteres de control (0-31)
CARACTERES_PROHIBIDOS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Nombres de dispositivos reservados en Windows (independiente de mayúsculas/minúsculas)
NOMBRES_RESERVADOS_WINDOWS: Set[str] = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

LONGITUD_MAXIMA_NOMBRE_BASE = 180


def sanitizar_nombre_archivo(nombre_sugerido: str, reemplazo: str = "_") -> str:
    """Sanea un nombre de archivo para compatibilidad estricta con Windows y Linux.

    - Normaliza caracteres Unicode.
    - Elimina caracteres prohibidos y secuencias de escape de ruta.
    - Protege nombres reservados de Windows.
    - Quita espacios y puntos terminales.
    - Recorta la longitud sin romper codificación.
    """
    if not nombre_sugerido:
        return "medio"

    # Normalización Unicode
    texto = unicodedata.normalize("NFC", nombre_sugerido.strip())

    # Prevenir ataques de recorrido de directorios
    texto = os.path.basename(texto)

    # Reemplazar caracteres prohibidos
    texto = CARACTERES_PROHIBIDOS.sub(reemplazo, texto)

    # Reemplazar múltiples espacios o guiones consecutivos
    texto = re.sub(r"\s+", " ", texto).strip()

    # Quitar puntos o espacios al final (inválidos en nombres de archivo de Windows)
    texto = texto.rstrip(". ")

    if not texto:
        texto = "medio"

    # Verificar si el nombre base coincide con un dispositivo reservado de Windows
    parte_base = texto.split(".")[0].upper()
    if parte_base in NOMBRES_RESERVADOS_WINDOWS:
        texto = f"_{texto}"

    # Limitar longitud respetando extensión si tiene
    if len(texto) > LONGITUD_MAXIMA_NOMBRE_BASE:
        partes = texto.rsplit(".", 1)
        if len(partes) == 2 and len(partes[1]) <= 10:
            nombre_raiz, ext = partes
            texto = f"{nombre_raiz[:LONGITUD_MAXIMA_NOMBRE_BASE - len(ext) - 1].rstrip('. ') }.{ext}"
        else:
            texto = texto[:LONGITUD_MAXIMA_NOMBRE_BASE].rstrip(". ")

    return texto or "medio"


def resolver_ruta_sin_colision(
    directorio: Path, nombre_base: str, extension: Optional[str] = None
) -> Path:
    """Calcula una ruta en el directorio que no colisione con archivos existentes.

    Genera secuencias tipo 'nombre (2).ext', 'nombre (3).ext' si el archivo ya existe.
    """
    if extension is None:
        partes = nombre_base.rsplit(".", 1)
        if len(partes) == 2 and len(partes[1]) <= 10:
            nombre_limpio = partes[0]
            ext_limpia = partes[1]
        else:
            nombre_limpio = nombre_base
            ext_limpia = ""
    else:
        ext_limpia = extension.lstrip(".")
        nombre_limpio = nombre_base

    nombre_saneado = sanitizar_nombre_archivo(nombre_limpio)
    if ext_limpia and nombre_saneado.lower().endswith(f".{ext_limpia.lower()}"):
        nombre_saneado = nombre_saneado[: -(len(ext_limpia) + 1)].rstrip(". ")

    sufijo_ext = f".{ext_limpia}" if ext_limpia else ""
    candidato = directorio / f"{nombre_saneado}{sufijo_ext}"
    contador = 2

    while candidato.exists():
        candidato = directorio / f"{nombre_saneado} ({contador}){sufijo_ext}"
        contador += 1

    return candidato


def obtener_directorio_staging_trabajo(directorio_destino: Path, id_trabajo: str) -> Path:
    """Devuelve un directorio temporal de trabajo para descargas parciales."""
    staging = directorio_destino / ".mintplay_staging" / id_trabajo
    staging.mkdir(parents=True, exist_ok=True)
    return staging


def crear_directorio_staging(id_trabajo: str, directorio_base: Optional[Path] = None) -> Path:
    """Crea y devuelve un directorio de staging para un trabajo específico."""
    if directorio_base is None:
        from .runtime_paths import obtener_directorio_datos_usuario

        directorio_base = obtener_directorio_datos_usuario()
    return obtener_directorio_staging_trabajo(directorio_base, id_trabajo)


def limpiar_directorio_staging(objetivo: Union[Path, str], directorio_base: Optional[Path] = None) -> None:
    """Elimina los archivos temporales y el directorio de staging de un trabajo."""
    if isinstance(objetivo, str):
        if directorio_base is None:
            from .runtime_paths import obtener_directorio_datos_usuario

            directorio_base = obtener_directorio_datos_usuario()
        directorio_staging = directorio_base / ".mintplay_staging" / objetivo
    else:
        directorio_staging = objetivo

    if not directorio_staging.exists():
        return

    try:
        for elemento in directorio_staging.iterdir():
            if elemento.is_file():
                elemento.unlink(missing_ok=True)
            elif elemento.is_dir():
                limpiar_directorio_staging(elemento)
        directorio_staging.rmdir()
    except OSError:
        pass
