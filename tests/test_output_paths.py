"""Pruebas de sanitización de nombres y resolución de colisiones."""

import os
from pathlib import Path

from mintplay.domain.models import TipoMedio
from mintplay.services.output_paths import (
    limpiar_directorio_staging,
    obtener_directorio_staging_trabajo,
    resolver_ruta_sin_colision,
    sanitizar_nombre_archivo,
)


def test_sanitizar_caracteres_prohibidos():
    entrada = 'Video: "Genial" / Especial * <2026>? | Si'
    salida = sanitizar_nombre_archivo(entrada)
    assert ":" not in salida
    assert '"' not in salida
    assert "/" not in salida
    assert "*" not in salida
    assert "<" not in salida
    assert ">" not in salida
    assert "?" not in salida
    assert "|" not in salida


def test_sanitizar_dispositivos_reservados_windows():
    assert sanitizar_nombre_archivo("con") == "_con"
    assert sanitizar_nombre_archivo("AUX.mp4") == "_AUX.mp4"
    assert sanitizar_nombre_archivo("nul") == "_nul"
    assert sanitizar_nombre_archivo("com1") == "_com1"


def test_sanitizar_puntos_y_espacios_terminales():
    salida = sanitizar_nombre_archivo("mi_archivo...   ")
    assert not salida.endswith(".")
    assert not salida.endswith(" ")
    assert salida == "mi_archivo"


def test_sanitizar_escape_directorios():
    salida = sanitizar_nombre_archivo("../../etc/passwd")
    assert "/" not in salida
    assert ".." not in salida
    assert salida == "passwd"


def test_resolver_ruta_sin_colision(tmp_path: Path):
    nombre = "mi_video"
    ext = "mp4"

    # Primer archivo
    ruta1 = resolver_ruta_sin_colision(tmp_path, nombre, ext)
    assert ruta1.name == "mi_video.mp4"
    ruta1.touch()

    # Segunda colisión
    ruta2 = resolver_ruta_sin_colision(tmp_path, nombre, ext)
    assert ruta2.name == "mi_video (2).mp4"
    ruta2.touch()

    # Tercera colisión
    ruta3 = resolver_ruta_sin_colision(tmp_path, nombre, ext)
    assert ruta3.name == "mi_video (3).mp4"


def test_staging_creacion_y_limpieza(tmp_path: Path):
    staging = obtener_directorio_staging_trabajo(tmp_path, "job-12345")
    assert staging.exists()
    assert staging.is_dir()

    archivo_temp = staging / "temp.part"
    archivo_temp.write_text("datos")

    limpiar_directorio_staging(staging)
    assert not staging.exists()
