"""Persistencia atómica de configuración y cola de descargas."""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, List

from ..domain.models import EstadoTrabajo, TrabajoDescarga
from ..domain.states import marcar_interrumpido
from .runtime_paths import (
    obtener_directorio_datos_usuario,
    obtener_directorio_descargas_predeterminado,
)

logger = logging.getLogger(__name__)

NOMBRE_ARCHIVO_CONFIG = "settings.json"
NOMBRE_ARCHIVO_COLA = "queue.json"


def _escribir_json_atomico(ruta_destino: Path, datos: Any) -> None:
    """Escribe datos en JSON usando un archivo temporal y reemplazo atómico."""
    ruta_destino.parent.mkdir(parents=True, exist_ok=True)
    ruta_temporal = ruta_destino.with_suffix(f".tmp.{os.getpid()}")

    contenido = json.dumps(datos, ensure_ascii=False, indent=2)
    ruta_temporal.write_text(contenido, encoding="utf-8")

    try:
        os.replace(ruta_temporal, ruta_destino)
    except OSError as err:
        logger.error("Error al reemplazar atómicamente %s: %s", ruta_destino, err)
        if ruta_temporal.exists():
            ruta_temporal.unlink(missing_ok=True)
        raise


def _leer_json_seguro(ruta: Path, defecto: Any) -> Any:
    """Lee un archivo JSON; si está corrupto genera respaldo .broken y devuelve defecto."""
    if not ruta.exists():
        return defecto

    try:
        contenido = ruta.read_text(encoding="utf-8")
        if not contenido.strip():
            return defecto
        return json.loads(contenido)
    except Exception as err:
        logger.warning("Archivo JSON corrupto en %s (%s). Creando respaldo .broken", ruta, err)
        ruta_respaldo = ruta.with_suffix(f".broken.{int(time.time())}")
        try:
            shutil.copy2(ruta, ruta_respaldo)
        except OSError:
            pass
        return defecto


def obtener_configuracion_predeterminada() -> dict[str, Any]:
    """Genera la configuración inicial recomendada."""
    return {
        "idioma": "es",
        "tema": "dark",
        "directorio_descargas": str(obtener_directorio_descargas_predeterminado()),
    }


def cargar_configuracion() -> dict[str, Any]:
    """Carga los ajustes del usuario o devuelve valores por defecto."""
    ruta = obtener_directorio_datos_usuario() / NOMBRE_ARCHIVO_CONFIG
    config = _leer_json_seguro(ruta, obtener_configuracion_predeterminada())
    predeterminado = obtener_configuracion_predeterminada()

    # Asegurar que todas las claves requeridas existan
    for clave, valor in predeterminado.items():
        if clave not in config:
            config[clave] = valor

    return config


def guardar_configuracion(config: dict[str, Any]) -> None:
    """Guarda los ajustes del usuario de forma atómica."""
    ruta = obtener_directorio_datos_usuario() / NOMBRE_ARCHIVO_CONFIG
    _escribir_json_atomico(ruta, config)


def cargar_cola() -> List[TrabajoDescarga]:
    """Carga la cola guardada y marca como interrumpidos los trabajos activos pendientes."""
    ruta = obtener_directorio_datos_usuario() / NOMBRE_ARCHIVO_COLA
    datos = _leer_json_seguro(ruta, [])

    trabajos: List[TrabajoDescarga] = []
    if isinstance(datos, list):
        for item in datos:
            try:
                trabajo = TrabajoDescarga.desde_dict(item)
                # Si la aplicación se cerró abruptamente mientras estaba activo:
                if trabajo.status == EstadoTrabajo.ACTIVO:
                    marcar_interrumpido(trabajo)
                trabajos.append(trabajo)
            except Exception as err:
                logger.warning("Elemento de cola inválido ignorado: %s", err)

    return trabajos


def guardar_cola(trabajos: List[TrabajoDescarga]) -> None:
    """Guarda los trabajos activos, pendientes y con error/cancelados.

    Filtra los trabajos completados cuyo ciclo haya finalizado para no acumular basura.
    """
    ruta = obtener_directorio_datos_usuario() / NOMBRE_ARCHIVO_COLA
    datos = [t.a_dict() for t in trabajos]
    _escribir_json_atomico(ruta, datos)
