"""Motor de descarga real basado en yt-dlp con aislamiento de staging y hooks."""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import yt_dlp
from ..domain.format_policy import construir_config_ytdlp
from ..domain.models import FaseTrabajo, TipoMedio, TrabajoDescarga
from .media_probe import verificar_archivo_multimedia
from .output_paths import (
    crear_directorio_staging,
    limpiar_directorio_staging,
    resolver_ruta_sin_colision,
)
from .runtime_paths import obtener_directorio_binarios, obtener_ruta_ejecutable

logger = logging.getLogger(__name__)

# Límite de frecuencia de actualización de progreso hacia la UI (~8 Hz)
INTERVALO_MIN_PROGRESO_S = 0.125


class CancelacionDescargaException(Exception):
    """Excepción lanzada cuando el usuario cancela activamente una descarga."""


class LoggerYtDlp:
    """Redirige los mensajes de yt-dlp al sistema de logging sin saturar la consola."""

    def __init__(self, trabajo_id: str):
        self.trabajo_id = trabajo_id

    def debug(self, msg: str) -> None:
        logger.debug("[%s] yt-dlp: %s", self.trabajo_id, msg)

    def info(self, msg: str) -> None:
        logger.info("[%s] yt-dlp: %s", self.trabajo_id, msg)

    def warning(self, msg: str) -> None:
        logger.warning("[%s] yt-dlp: %s", self.trabajo_id, msg)

    def error(self, msg: str) -> None:
        logger.error("[%s] yt-dlp: %s", self.trabajo_id, msg)


def clasificar_codigo_error(mensaje: str) -> str:
    """Clasifica el mensaje de excepción en un código de error estable para i18n."""
    msg = mensaje.lower()
    if "unavailable" in msg or "removed" in msg or "deleted" in msg or "not exist" in msg:
        return "UNAVAILABLE_MEDIA"
    if "private" in msg or "sign in" in msg or "members-only" in msg or "age-restricted" in msg:
        return "PRIVATE_OR_RESTRICTED"
    if "playlist" in msg:
        return "PLAYLIST_NOT_SUPPORTED"
    if "requested format is not available" in msg or "no video formats" in msg:
        return "NO_SUITABLE_FORMAT"
    if "timed out" in msg or "connection" in msg or "network" in msg or "getaddrinfo" in msg:
        return "NETWORK_ERROR"
    if "verificación multimedia" in msg or "ffprobe" in msg:
        return "VERIFY_FAILED"
    return "DOWNLOAD_ERROR"


class ServicioDescargaYtDlp:
    """Servicio encargado de ejecutar la descarga real con yt-dlp."""

    def __init__(self) -> None:
        self._dir_bin = obtener_directorio_binarios()

    def descargar(
        self,
        trabajo: TrabajoDescarga,
        cb_progreso: Callable[[float, Optional[int], Optional[int], Optional[float], Optional[float]], None],
        cb_fase: Callable[[FaseTrabajo], None],
        es_cancelado: Callable[[], bool],
    ) -> Path:
        """Descarga un recurso multimedia en un directorio de staging aislado."""
        if es_cancelado():
            raise CancelacionDescargaException("Descarga cancelada antes de iniciar")

        fase_actual = FaseTrabajo.PREPARANDO
        cb_fase(fase_actual)

        dir_destino_final = Path(trabajo.destination_dir)
        dir_destino_final.mkdir(parents=True, exist_ok=True)

        dir_staging = crear_directorio_staging(trabajo.id, dir_destino_final)

        try:
            # 1. Configuración de formatos según política
            opciones_ytdlp = construir_config_ytdlp(
                tipo=trabajo.media_type,
                formato=trabajo.target_extension,
                calidad=trabajo.quality_choice,
            )

            # Plantilla de salida en el staging
            nombre_base = trabajo.custom_name if trabajo.custom_name else "%(title)s"
            plantilla_salida = str(dir_staging / f"{nombre_base}.%(ext)s")

            ultimo_emit_progreso = 0.0

            def emitir_fase_unica(nueva_fase: FaseTrabajo) -> None:
                nonlocal fase_actual
                if fase_actual != nueva_fase:
                    fase_actual = nueva_fase
                    cb_fase(nueva_fase)

            def actualizar_metadatos_tempranos(info_dict: Optional[Dict[str, Any]]) -> None:
                if not info_dict or not isinstance(info_dict, dict):
                    return
                titulo = info_dict.get("title")
                if titulo:
                    if not trabajo.display_title or (
                        trabajo.display_title == trabajo.url and not trabajo.custom_name
                    ):
                        trabajo.display_title = str(titulo)
                extractor = info_dict.get("extractor_key")
                if extractor and trabajo.platform_hint in ("", "Otro sitio", "Other site"):
                    trabajo.platform_hint = str(extractor)

            # 2. Hook de progreso con limitador de frecuencia (throttling ~8 Hz)
            def hook_progreso(d: Dict[str, Any]) -> None:
                nonlocal ultimo_emit_progreso
                if es_cancelado():
                    raise CancelacionDescargaException("Descarga cancelada por el usuario")

                actualizar_metadatos_tempranos(d.get("info_dict"))

                estado = d.get("status")
                if estado == "downloading":
                    emitir_fase_unica(FaseTrabajo.DESCARGANDO)
                    ahora = time.perf_counter()
                    total = d.get("total_bytes") or d.get("total_bytes_estimate")
                    descargado = d.get("downloaded_bytes", 0)
                    velocidad = d.get("speed")
                    eta = d.get("eta")

                    progreso = 0.0
                    if total and total > 0:
                        progreso = min(100.0, (descargado / total) * 100.0)

                    es_final_stream = total is not None and descargado >= total
                    if (
                        ultimo_emit_progreso == 0.0
                        or (ahora - ultimo_emit_progreso) >= INTERVALO_MIN_PROGRESO_S
                        or es_final_stream
                    ):
                        ultimo_emit_progreso = ahora
                        cb_progreso(progreso, descargado, total, velocidad, eta)

            # 3. Hook de postprocesador
            def hook_postproceso(d: Dict[str, Any]) -> None:
                if es_cancelado():
                    raise CancelacionDescargaException("Cancelado durante el procesamiento")
                actualizar_metadatos_tempranos(d.get("info_dict"))
                emitir_fase_unica(FaseTrabajo.PROCESANDO)

            # Configuración maestra para yt-dlp
            ydl_opts: Dict[str, Any] = {
                "format": opciones_ytdlp["format"],
                "outtmpl": plantilla_salida,
                "ffmpeg_location": str(self._dir_bin),
                "logger": LoggerYtDlp(trabajo.id),
                "progress_hooks": [hook_progreso],
                "postprocessor_hooks": [hook_postproceso],
                "noplaylist": True,
                "quiet": True,
                "no_warnings": False,
                "updatetime": False,
                "overwrites": True,
                "windowsfilenames": True,
                "restrictfilenames": False,
            }

            if "merge_output_format" in opciones_ytdlp:
                ydl_opts["merge_output_format"] = opciones_ytdlp["merge_output_format"]

            if "postprocessors" in opciones_ytdlp and opciones_ytdlp["postprocessors"]:
                ydl_opts["postprocessors"] = opciones_ytdlp["postprocessors"]

            # 4. Habilitar explícitamente Node.js con la ruta empaquetada
            ruta_node = obtener_ruta_ejecutable("node")
            if ruta_node and ruta_node.exists():
                ydl_opts["js_runtimes"] = {
                    "node": {"path": str(ruta_node.resolve())}
                }
                logger.info(
                    "[%s] Runtime Node.js configurado explícitamente en yt-dlp: %s",
                    trabajo.id,
                    ruta_node,
                )
            else:
                logger.warning(
                    "[%s] No se encontró node.exe en el directorio bin (%s)",
                    trabajo.id,
                    self._dir_bin,
                )

            # 5. Comprobar disponibilidad de yt-dlp-ejs solver
            try:
                import yt_dlp_ejs
                import yt_dlp_ejs.yt.solver

                logger.info("[%s] yt-dlp-ejs solver disponible para extracción dinámica.", trabajo.id)
            except ImportError:
                logger.warning("[%s] yt-dlp-ejs no importable en el entorno actual.", trabajo.id)

            # 6. Ejecución con yt-dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(trabajo.url, download=True)
                if not info:
                    raise RuntimeError("No se pudo obtener información del medio")

                actualizar_metadatos_tempranos(info)

            if es_cancelado():
                raise CancelacionDescargaException("Descarga cancelada al finalizar")

            # 7. Localizar archivo generado en staging
            archivos_generados = [
                f
                for f in dir_staging.iterdir()
                if f.is_file() and not f.name.endswith(".part") and not f.name.endswith(".ytdl")
            ]
            if not archivos_generados:
                raise FileNotFoundError("yt-dlp finalizó pero no se generó ningún archivo en el staging")

            archivo_temporal = archivos_generados[0]

            # 8. Fase de verificación con ffprobe
            emitir_fase_unica(FaseTrabajo.VERIFICANDO)
            verificacion = verificar_archivo_multimedia(archivo_temporal, trabajo.media_type)
            if not verificacion.es_valido:
                err_verif = RuntimeError(f"Fallo de verificación multimedia: {verificacion.mensaje}")
                setattr(err_verif, "error_code", "VERIFY_FAILED")
                raise err_verif

            # 9. Mover de forma segura y atómica al destino final sin colisión
            nombre_final = archivo_temporal.name
            ruta_destino = resolver_ruta_sin_colision(dir_destino_final, nombre_final)

            shutil.move(str(archivo_temporal), str(ruta_destino))
            emitir_fase_unica(FaseTrabajo.FINALIZADO)
            return ruta_destino

        except CancelacionDescargaException:
            cb_fase(FaseTrabajo.CANCELADO)
            raise
        except Exception as err:
            if not hasattr(err, "error_code"):
                setattr(err, "error_code", clasificar_codigo_error(str(err)))
            logger.error("Error en proceso de descarga %s: %s", trabajo.id, err)
            cb_fase(FaseTrabajo.ERROR)
            raise
        finally:
            limpiar_directorio_staging(dir_staging)
