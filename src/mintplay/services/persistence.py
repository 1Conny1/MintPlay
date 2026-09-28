"""Persistencia atómica de configuración y cola de descargas."""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, List, Optional

from ..domain.format_policy import verificar_compatibilidad
from ..domain.models import EstadoTrabajo, RegistroHistorial, TipoMedio, TrabajoDescarga
from ..domain.states import marcar_interrumpido, ordenar_trabajos_canonicamente
from .runtime_paths import (
    obtener_directorio_datos_usuario,
    obtener_directorio_descargas_predeterminado,
)

logger = logging.getLogger(__name__)

NOMBRE_ARCHIVO_CONFIG = "settings.json"
NOMBRE_ARCHIVO_COLA = "queue.json"
NOMBRE_ARCHIVO_HISTORIAL = "history.json"
MAX_REGISTROS_HISTORIAL = 1000


def _respaldar_archivo_corrupto(ruta: Path, motivo: str) -> None:
    """Crea una copia .broken.<timestamp> de un archivo de estado inválido."""
    logger.warning("Archivo de estado inválido en %s (%s). Creando respaldo .broken", ruta.name, motivo)
    ruta_respaldo = ruta.with_suffix(f".broken.{int(time.time())}")
    try:
        shutil.copy2(ruta, ruta_respaldo)
    except OSError:
        pass


def _escribir_json_atomico(ruta_destino: Path, datos: Any) -> None:
    """Escribe datos en JSON usando un archivo temporal y reemplazo atómico."""
    ruta_destino.parent.mkdir(parents=True, exist_ok=True)
    ruta_temporal = ruta_destino.with_suffix(f".tmp.{os.getpid()}")

    contenido = json.dumps(datos, ensure_ascii=False, indent=2)
    ruta_temporal.write_text(contenido, encoding="utf-8")

    try:
        os.replace(ruta_temporal, ruta_destino)
    except OSError as err:
        logger.error("Error al reemplazar atómicamente %s: %s", ruta_destino.name, err)
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
        _respaldar_archivo_corrupto(ruta, str(err))
        return defecto


PALETAS_VALIDAS = ("mint", "sakura", "indigo", "amber", "ocean")
MODOS_TEMA_VALIDOS = ("light", "dark")
IDIOMAS_VALIDOS = ("es", "en")
TIPOS_MEDIO_VALIDOS = ("video", "audio")


def es_carpeta_destino_valida(ruta_str: str) -> bool:
    """Comprueba que la carpeta exista en disco y tenga permiso de escritura."""
    if not ruta_str or not isinstance(ruta_str, str):
        return False
    try:
        p = Path(ruta_str.strip())
        return p.exists() and p.is_dir() and os.access(str(p), os.W_OK)
    except OSError:
        return False


def normalizar_configuracion_usuario(
    config: dict[str, Any],
    verificar_carpeta_en_disco: bool = False,
) -> dict[str, Any]:
    """Normaliza y migra la configuración de idioma, paleta, modo, notificaciones y opciones de descarga.

    - Si una configuración antigua solo tiene `tema` ('light'/'dark'), conserva ese modo
      y asigna la paleta predeterminada ('mint').
    - Valida formato y calidad por separado para vídeo y audio con `verificar_compatibilidad`.
    - Nunca persiste ni restaura URL ni nombre de archivo personalizado.
    - Si `verificar_carpeta_en_disco` es True y la carpeta guardada ya no existe o no es escribible,
      restaura la carpeta predeterminada segura y marca `carpeta_restaurada_por_invalida = True`.
    """
    predeterminado = obtener_configuracion_predeterminada()
    if not isinstance(config, dict):
        return predeterminado

    # Eliminar cualquier rastro accidental de URL o nombre de archivo
    config.pop("url", None)
    config.pop("custom_name", None)

    # 1. Idioma
    idioma_raw = config.get("idioma")
    idioma = (
        idioma_raw.strip().lower()
        if isinstance(idioma_raw, str) and idioma_raw.strip().lower() in IDIOMAS_VALIDOS
        else predeterminado["idioma"]
    )

    # 2. Paleta y modo (con migración de configuraciones antiguas)
    paleta_raw = config.get("paleta")
    tema_raw = config.get("tema")
    if tema_raw is None:
        tema_raw = config.get("modo_tema", config.get("modo"))

    cand_paleta = paleta_raw.strip().lower() if isinstance(paleta_raw, str) else ""
    cand_modo = tema_raw.strip().lower() if isinstance(tema_raw, str) else ""

    for sep in (":", "_", "-"):
        if sep in cand_modo:
            partes = [p.strip() for p in cand_modo.split(sep, 1)]
            if len(partes) == 2:
                if partes[0] in PALETAS_VALIDAS and partes[1] in MODOS_TEMA_VALIDOS:
                    if not cand_paleta:
                        cand_paleta = partes[0]
                    cand_modo = partes[1]
                    break
                if partes[1] in PALETAS_VALIDAS and partes[0] in MODOS_TEMA_VALIDOS:
                    if not cand_paleta:
                        cand_paleta = partes[1]
                    cand_modo = partes[0]
                    break

    if cand_modo in PALETAS_VALIDAS and not cand_paleta:
        cand_paleta = cand_modo
        cand_modo = predeterminado["tema"]

    paleta = cand_paleta if cand_paleta in PALETAS_VALIDAS else predeterminado["paleta"]
    modo = cand_modo if cand_modo in MODOS_TEMA_VALIDOS else predeterminado["tema"]

    # 3. Notificaciones de descargas (activadas por defecto)
    notif_raw = config.get("notificaciones_activas", predeterminado["notificaciones_activas"])
    notificaciones_activas = (
        notif_raw if isinstance(notif_raw, bool) else predeterminado["notificaciones_activas"]
    )

    # 4. Últimas opciones de descarga separadas para vídeo y audio
    tipo_raw = config.get("ultimo_tipo_medio")
    ultimo_tipo_medio = (
        tipo_raw.strip().lower()
        if isinstance(tipo_raw, str) and tipo_raw.strip().lower() in TIPOS_MEDIO_VALIDOS
        else predeterminado["ultimo_tipo_medio"]
    )

    v_fmt_raw = config.get("video_formato")
    v_cal_raw = config.get("video_calidad")
    _, video_formato, video_calidad = verificar_compatibilidad(
        TipoMedio.VIDEO,
        v_fmt_raw.strip().lower() if isinstance(v_fmt_raw, str) else predeterminado["video_formato"],
        v_cal_raw.strip().lower() if isinstance(v_cal_raw, str) else predeterminado["video_calidad"],
    )

    a_fmt_raw = config.get("audio_formato")
    a_cal_raw = config.get("audio_calidad")
    _, audio_formato, audio_calidad = verificar_compatibilidad(
        TipoMedio.AUDIO,
        a_fmt_raw.strip().lower() if isinstance(a_fmt_raw, str) else predeterminado["audio_formato"],
        a_cal_raw.strip().lower() if isinstance(a_cal_raw, str) else predeterminado["audio_calidad"],
    )

    # 5. Directorio de descargas
    dir_raw = config.get("directorio_descargas")
    tenia_dir_explicito = isinstance(dir_raw, str) and bool(dir_raw.strip())
    directorio = (
        dir_raw.strip()
        if tenia_dir_explicito
        else predeterminado["directorio_descargas"]
    )
    carpeta_restaurada = bool(config.get("carpeta_restaurada_por_invalida", False))
    if verificar_carpeta_en_disco and tenia_dir_explicito:
        if not es_carpeta_destino_valida(directorio):
            directorio = predeterminado["directorio_descargas"]
            carpeta_restaurada = True

    config["idioma"] = idioma
    config["paleta"] = paleta
    config["tema"] = modo
    config["notificaciones_activas"] = notificaciones_activas
    config["ultimo_tipo_medio"] = ultimo_tipo_medio
    config["video_formato"] = video_formato
    config["video_calidad"] = video_calidad
    config["audio_formato"] = audio_formato
    config["audio_calidad"] = audio_calidad
    config["directorio_descargas"] = directorio
    if carpeta_restaurada:
        config["carpeta_restaurada_por_invalida"] = True
    else:
        config.pop("carpeta_restaurada_por_invalida", None)
    return config


def restablecer_opciones_descarga(config: dict[str, Any]) -> dict[str, Any]:
    """Restablece únicamente las preferencias de descarga y carpeta sin alterar idioma, tema ni cola."""
    predeterminado = obtener_configuracion_predeterminada()
    config["ultimo_tipo_medio"] = predeterminado["ultimo_tipo_medio"]
    config["video_formato"] = predeterminado["video_formato"]
    config["video_calidad"] = predeterminado["video_calidad"]
    config["audio_formato"] = predeterminado["audio_formato"]
    config["audio_calidad"] = predeterminado["audio_calidad"]
    config["directorio_descargas"] = predeterminado["directorio_descargas"]
    config.pop("carpeta_restaurada_por_invalida", None)
    return normalizar_configuracion_usuario(config)


def obtener_configuracion_predeterminada() -> dict[str, Any]:
    """Genera la configuración inicial recomendada (Menta oscuro en español)."""
    return {
        "idioma": "es",
        "paleta": "mint",
        "tema": "dark",
        "notificaciones_activas": True,
        "ultimo_tipo_medio": "video",
        "video_formato": "mp4",
        "video_calidad": "best",
        "audio_formato": "mp3",
        "audio_calidad": "192",
        "directorio_descargas": str(obtener_directorio_descargas_predeterminado()),
    }


def cargar_configuracion() -> dict[str, Any]:
    """Carga los ajustes del usuario, migrando versiones previas y saneando valores inválidos."""
    ruta = obtener_directorio_datos_usuario() / NOMBRE_ARCHIVO_CONFIG
    config = _leer_json_seguro(ruta, obtener_configuracion_predeterminada())
    if not isinstance(config, dict):
        _respaldar_archivo_corrupto(ruta, "La raíz de configuración no es un objeto JSON")
        config = obtener_configuracion_predeterminada()

    return normalizar_configuracion_usuario(config, verificar_carpeta_en_disco=True)


def guardar_configuracion(config: dict[str, Any]) -> None:
    """Guarda los ajustes del usuario de forma atómica tras normalizar preferencias."""
    ruta = obtener_directorio_datos_usuario() / NOMBRE_ARCHIVO_CONFIG
    copia = dict(config)
    copia.pop("carpeta_restaurada_por_invalida", None)
    normalizado = normalizar_configuracion_usuario(copia, verificar_carpeta_en_disco=False)
    normalizado.pop("carpeta_restaurada_por_invalida", None)
    config.update(normalizado)
    _escribir_json_atomico(ruta, normalizado)


def cargar_cola() -> List[TrabajoDescarga]:
    """Carga la cola guardada, marca interrumpidos los activos y aplica el orden canónico."""
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
    elif ruta.exists():
        _respaldar_archivo_corrupto(ruta, "La raíz de queue.json no es una lista")

    return ordenar_trabajos_canonicamente(trabajos)


def guardar_cola(trabajos: List[TrabajoDescarga]) -> None:
    """Guarda los trabajos activos, pendientes y con error/cancelados en su orden canónico."""
    ruta = obtener_directorio_datos_usuario() / NOMBRE_ARCHIVO_COLA
    ordenados = ordenar_trabajos_canonicamente(trabajos)
    datos = [t.a_dict() for t in ordenados]
    _escribir_json_atomico(ruta, datos)


def cargar_historial() -> List[RegistroHistorial]:
    """Carga el historial local de descargas completadas ordenadas de más reciente a más antigua."""
    ruta = obtener_directorio_datos_usuario() / NOMBRE_ARCHIVO_HISTORIAL
    if not ruta.exists():
        return []

    centinela = object()
    datos = _leer_json_seguro(ruta, centinela)
    if datos is centinela:
        return []

    if not isinstance(datos, list):
        _respaldar_archivo_corrupto(ruta, "La raíz de history.json no es una lista")
        return []

    registros_por_clave: dict[str, RegistroHistorial] = {}
    for item in datos:
        try:
            reg = RegistroHistorial.desde_dict(item)
            clave = reg.clave_deduplicacion
            existente = registros_por_clave.get(clave)
            if existente is None or reg.completed_at >= existente.completed_at:
                registros_por_clave[clave] = reg
        except Exception as err:
            logger.warning("Registro de historial inválido ignorado: %s", err)

    registros = sorted(
        registros_por_clave.values(),
        key=lambda r: r.completed_at,
        reverse=True,
    )
    return registros[:MAX_REGISTROS_HISTORIAL]


def guardar_historial(registros: List[RegistroHistorial]) -> None:
    """Guarda de forma atómica hasta MAX_REGISTROS_HISTORIAL entradas en history.json."""
    ruta = obtener_directorio_datos_usuario() / NOMBRE_ARCHIVO_HISTORIAL
    ordenados = sorted(registros, key=lambda r: r.completed_at, reverse=True)[:MAX_REGISTROS_HISTORIAL]
    datos = [r.a_dict() for r in ordenados]
    _escribir_json_atomico(ruta, datos)


def registrar_en_historial(trabajo: TrabajoDescarga) -> Optional[RegistroHistorial]:
    """Registra o actualiza una descarga completada en history.json sin duplicar."""
    if trabajo.status != EstadoTrabajo.COMPLETADO or not trabajo.output_path:
        return None

    actuales = cargar_historial()
    nuevo = RegistroHistorial.desde_trabajo(trabajo)
    clave = nuevo.clave_deduplicacion
    filtrados = [r for r in actuales if r.clave_deduplicacion != clave and r.id != nuevo.id]
    filtrados.insert(0, nuevo)
    guardar_historial(filtrados[:MAX_REGISTROS_HISTORIAL])
    return nuevo

