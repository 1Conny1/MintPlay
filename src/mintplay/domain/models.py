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


# Alias Job para mantener compatibilidad con el diseño original
Job = TrabajoDescarga
JobStatus = EstadoTrabajo
JobPhase = FaseTrabajo
DownloadOptions = OpcionesDescarga
