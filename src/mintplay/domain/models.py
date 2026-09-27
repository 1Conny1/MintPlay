"""Modelos del dominio de descargas de MintPlay.

Define las entidades inmutables y estructuras de datos para representar
trabajos de descarga, estados, fases y opciones seleccionadas.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class EstadoTrabajo(str, Enum):
    """Estados del ciclo de vida de un trabajo en la cola."""

    EN_ESPERA = "queued"
    ACTIVO = "active"
    COMPLETADO = "completed"
    ERROR = "failed"
    CANCELADO = "cancelled"
    INTERRUMPIDO = "interrupted"

    # Alias en inglés para compatibilidad
    QUEUED = EN_ESPERA
    ACTIVE = ACTIVO
    COMPLETED = COMPLETADO
    FAILED = ERROR
    CANCELLED = CANCELADO
    INTERRUPTED = INTERRUMPIDO


class FaseTrabajo(str, Enum):
    """Fases granulares durante el procesamiento de un trabajo activo."""

    EN_ESPERA = "queued"
    PREPARANDO = "preparing"
    DESCARGANDO = "downloading"
    PROCESANDO = "postprocessing"
    VERIFICANDO = "verifying"
    FINALIZADO = "completed"
    ERROR = "failed"
    CANCELADO = "cancelled"

    # Alias en inglés
    QUEUED = EN_ESPERA
    PREPARING = PREPARANDO
    DOWNLOADING = DESCARGANDO
    POSTPROCESSING = PROCESANDO
    VERIFYING = VERIFICANDO
    COMPLETED = FINALIZADO
    FAILED = ERROR
    CANCELLED = CANCELADO


class TipoMedio(str, Enum):
    """Tipo principal de medio a obtener."""

    VIDEO = "video"
    AUDIO = "audio"


class FormatoVideo(str, Enum):
    """Formatos de contenedor admitidos para vídeo."""

    MP4 = "mp4"
    MKV = "mkv"
    WEBM = "webm"


class FormatoAudio(str, Enum):
    """Formatos de audio admitidos."""

    MP3 = "mp3"
    M4A = "m4a"
    FLAC = "flac"
    WAV = "wav"


class CalidadVideo(str, Enum):
    """Opciones de resolución y calidad para vídeo."""

    MEJOR = "best"
    P1080 = "1080p"
    P720 = "720p"
    P480 = "480p"


class CalidadAudio(str, Enum):
    """Opciones de tasa de bits y calidad para audio."""

    MEJOR = "original"
    KBPS_320 = "320"
    KBPS_256 = "256"
    KBPS_192 = "192"
    KBPS_128 = "128"
    SIN_PERDIDA = "lossless"


@dataclass(frozen=True)
class OpcionesDescarga:
    """Configuración inmutable seleccionada por el usuario para una tarea."""

    url: str
    custom_name: str
    media_type: TipoMedio
    target_extension: str
    quality_choice: str
    destination_dir: str

    def a_dict(self) -> dict[str, Any]:
        """Serializa las opciones a un diccionario."""
        return {
            "url": self.url,
            "custom_name": self.custom_name,
            "media_type": self.media_type.value,
            "target_extension": self.target_extension,
            "quality_choice": self.quality_choice,
            "destination_dir": self.destination_dir,
        }

    @classmethod
    def desde_dict(cls, data: dict[str, Any]) -> OpcionesDescarga:
        """Construye las opciones a partir de un diccionario."""
        return cls(
            url=data["url"],
            custom_name=data.get("custom_name", ""),
            media_type=TipoMedio(data["media_type"]),
            target_extension=data["target_extension"],
            quality_choice=data["quality_choice"],
            destination_dir=data["destination_dir"],
        )


@dataclass
class TrabajoDescarga:
    """Representa una tarea de descarga en la cola de MintPlay."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    url: str = ""
    display_title: str = ""
    custom_name: str = ""
    platform_hint: str = "Otro sitio"
    media_type: TipoMedio = TipoMedio.VIDEO
    target_extension: str = "mp4"
    quality_choice: str = "best"
    destination_dir: str = ""

    # Estado y avance
    status: EstadoTrabajo = EstadoTrabajo.EN_ESPERA
    phase: FaseTrabajo = FaseTrabajo.EN_ESPERA
    progress: float = 0.0  # 0.0 a 100.0
    downloaded_bytes: Optional[int] = None
    total_bytes: Optional[int] = None
    speed: Optional[float] = None
    eta: Optional[int] = None

    # Resultados y diagnóstico
    output_path: Optional[str] = None
    effective_quality: Optional[str] = None
    file_size: Optional[int] = None
    error_code: Optional[str] = None
    error_detail: Optional[str] = None
    attempt: int = 1

    @property
    def es_terminal(self) -> bool:
        """Indica si el trabajo ha llegado a un estado final."""
        return self.status in (
            EstadoTrabajo.COMPLETADO,
            EstadoTrabajo.ERROR,
            EstadoTrabajo.CANCELADO,
            EstadoTrabajo.INTERRUMPIDO,
        )

    def a_dict(self) -> dict[str, Any]:
        """Serializa el trabajo a un formato almacenable en JSON."""
        return {
            "id": self.id,
            "created_at": self.created_at,
            "url": self.url,
            "display_title": self.display_title,
            "custom_name": self.custom_name,
            "platform_hint": self.platform_hint,
            "media_type": self.media_type.value,
            "target_extension": self.target_extension,
            "quality_choice": self.quality_choice,
            "destination_dir": self.destination_dir,
            "status": self.status.value,
            "phase": self.phase.value,
            "progress": self.progress,
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "speed": self.speed,
            "eta": self.eta,
            "output_path": self.output_path,
            "effective_quality": self.effective_quality,
            "file_size": self.file_size,
            "error_code": self.error_code,
            "error_detail": self.error_detail,
            "attempt": self.attempt,
        }

    @classmethod
    def desde_dict(cls, data: dict[str, Any]) -> TrabajoDescarga:
        """Crea una instancia restaurada desde un diccionario."""
        return cls(
            id=data["id"],
            created_at=data.get("created_at", time.time()),
            url=data.get("url", ""),
            display_title=data.get("display_title", ""),
            custom_name=data.get("custom_name", ""),
            platform_hint=data.get("platform_hint", "Otro sitio"),
            media_type=TipoMedio(data.get("media_type", "video")),
            target_extension=data.get("target_extension", "mp4"),
            quality_choice=data.get("quality_choice", "best"),
            destination_dir=data.get("destination_dir", ""),
            status=EstadoTrabajo(data.get("status", "queued")),
            phase=FaseTrabajo(data.get("phase", "queued")),
            progress=float(data.get("progress", 0.0)),
            downloaded_bytes=data.get("downloaded_bytes"),
            total_bytes=data.get("total_bytes"),
            speed=data.get("speed"),
            eta=data.get("eta"),
            output_path=data.get("output_path"),
            effective_quality=data.get("effective_quality"),
            file_size=data.get("file_size"),
            error_code=data.get("error_code"),
            error_detail=data.get("error_detail"),
            attempt=data.get("attempt", 1),
        )

    @classmethod
    def desde_opciones(cls, opciones: OpcionesDescarga, plataforma: str = "Otro sitio") -> TrabajoDescarga:
        """Crea un nuevo trabajo en espera a partir de opciones inmutables."""
        nombre_mostrado = opciones.custom_name.strip() if opciones.custom_name.strip() else opciones.url
        return cls(
            url=opciones.url,
            display_title=nombre_mostrado,
            custom_name=opciones.custom_name.strip(),
            platform_hint=plataforma,
            media_type=opciones.media_type,
            target_extension=opciones.target_extension,
            quality_choice=opciones.quality_choice,
            destination_dir=opciones.destination_dir,
            status=EstadoTrabajo.EN_ESPERA,
            phase=FaseTrabajo.EN_ESPERA,
        )


@dataclass
class RegistroHistorial:
    """Representa una descarga completada y verificada en el historial local."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = ""
    attempt: int = 1
    url: str = ""
    title: str = ""
    custom_name: str = ""
    final_filename: str = ""
    output_path: str = ""
    destination_dir: str = ""
    platform_hint: str = "Otro sitio"
    media_type: TipoMedio = TipoMedio.VIDEO
    target_extension: str = "mp4"
    quality_choice: str = "best"
    effective_quality: Optional[str] = None
    completed_at: float = field(default_factory=time.time)
    file_size: Optional[int] = None

    @property
    def clave_deduplicacion(self) -> str:
        """Identificador estable por trabajo e intento para evitar duplicados."""
        if self.job_id:
            return f"{self.job_id}:{self.attempt}"
        return self.id

    def a_dict(self) -> dict[str, Any]:
        """Serializa el registro de historial a JSON."""
        return {
            "id": self.id,
            "job_id": self.job_id,
            "attempt": self.attempt,
            "url": self.url,
            "title": self.title,
            "custom_name": self.custom_name,
            "final_filename": self.final_filename,
            "output_path": self.output_path,
            "destination_dir": self.destination_dir,
            "platform_hint": self.platform_hint,
            "media_type": self.media_type.value,
            "target_extension": self.target_extension,
            "quality_choice": self.quality_choice,
            "effective_quality": self.effective_quality,
            "completed_at": self.completed_at,
            "file_size": self.file_size,
        }

    @classmethod
    def desde_dict(cls, data: dict[str, Any]) -> RegistroHistorial:
        """Restaura un registro de historial validando su estructura mínima."""
        if not isinstance(data, dict):
            raise ValueError("El registro de historial debe ser un objeto JSON")

        job_id = str(data.get("job_id") or data.get("id") or "").strip()
        if not job_id:
            raise ValueError("Registro de historial sin identificador")

        attempt = int(data.get("attempt", 1))
        rec_id = str(data.get("id") or f"{job_id}:{attempt}")
        url = str(data.get("url") or "").strip()
        output_path = str(data.get("output_path") or "").strip()
        final_filename = str(data.get("final_filename") or "").strip()
        if not final_filename and output_path:
            from pathlib import Path

            final_filename = Path(output_path).name

        title = str(data.get("title") or final_filename or url).strip()
        if not title and not output_path and not url:
            raise ValueError("Registro de historial incompleto")

        destination_dir = str(data.get("destination_dir") or "").strip()
        if not destination_dir and output_path:
            from pathlib import Path

            destination_dir = str(Path(output_path).parent)

        file_size_raw = data.get("file_size")
        file_size = int(file_size_raw) if file_size_raw is not None else None

        return cls(
            id=rec_id,
            job_id=job_id,
            attempt=attempt,
            url=url,
            title=title,
            custom_name=str(data.get("custom_name") or ""),
            final_filename=final_filename,
            output_path=output_path,
            destination_dir=destination_dir,
            platform_hint=str(data.get("platform_hint") or "Otro sitio"),
            media_type=TipoMedio(data.get("media_type", "video")),
            target_extension=str(data.get("target_extension") or "mp4"),
            quality_choice=str(data.get("quality_choice") or "best"),
            effective_quality=data.get("effective_quality"),
            completed_at=float(data.get("completed_at", time.time())),
            file_size=file_size,
        )

    @classmethod
    def desde_trabajo(
        cls,
        trabajo: TrabajoDescarga,
        completed_at: Optional[float] = None,
    ) -> RegistroHistorial:
        """Construye un registro de historial a partir de un TrabajoDescarga completado."""
        from pathlib import Path

        ruta_salida = trabajo.output_path or ""
        p_salida = Path(ruta_salida) if ruta_salida else None
        nombre_final = p_salida.name if p_salida and p_salida.name else (trabajo.custom_name or trabajo.display_title)
        dir_destino = trabajo.destination_dir
        if not dir_destino and p_salida:
            dir_destino = str(p_salida.parent)

        tamano = trabajo.file_size
        if tamano is None and p_salida and p_salida.is_file():
            try:
                tamano = p_salida.stat().st_size
            except OSError:
                tamano = None
        if tamano is None:
            tamano = trabajo.total_bytes or trabajo.downloaded_bytes

        titulo = trabajo.display_title or trabajo.custom_name or nombre_final or trabajo.url
        instante = completed_at if completed_at is not None else time.time()

        return cls(
            id=f"{trabajo.id}:{trabajo.attempt}",
            job_id=trabajo.id,
            attempt=trabajo.attempt,
            url=trabajo.url,
            title=titulo,
            custom_name=trabajo.custom_name,
            final_filename=nombre_final,
            output_path=ruta_salida,
            destination_dir=dir_destino,
            platform_hint=trabajo.platform_hint or "Otro sitio",
            media_type=trabajo.media_type,
            target_extension=trabajo.target_extension,
            quality_choice=trabajo.quality_choice,
            effective_quality=trabajo.effective_quality,
            completed_at=instante,
            file_size=tamano,
        )

    def a_opciones_descarga(self) -> OpcionesDescarga:
        """Reconstruye las OpcionesDescarga originales para volver a encolar la tarea."""
        return OpcionesDescarga(
            url=self.url,
            custom_name=self.custom_name,
            media_type=self.media_type,
            target_extension=self.target_extension,
            quality_choice=self.quality_choice,
            destination_dir=self.destination_dir,
        )


# Alias Job para mantener compatibilidad con el diseño original
Job = TrabajoDescarga
JobStatus = EstadoTrabajo
JobPhase = FaseTrabajo
DownloadOptions = OpcionesDescarga
HistoryEntry = RegistroHistorial

