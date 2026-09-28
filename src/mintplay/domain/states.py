"""Gestor y reglas de transición de estados para los trabajos de MintPlay."""

from __future__ import annotations

from typing import Iterable, List, Set

from .models import EstadoTrabajo, FaseTrabajo, TrabajoDescarga


def prioridad_orden_cola(trabajo: TrabajoDescarga) -> int:
    """Devuelve la prioridad de orden visual y de modelo para un trabajo en la cola.

    0: Activo (PREPARING / DOWNLOADING / POSTPROCESSING / VERIFYING) — siempre arriba.
    1: Completado (durante su ventana de confirmación de 5 segundos).
    2: En espera (QUEUED) — en orden estricto FIFO.
    3: Fallido, interrumpido o cancelado — debajo de los activos y en espera.
    """
    if trabajo.status == EstadoTrabajo.ACTIVO or trabajo.phase in (
        FaseTrabajo.PREPARANDO,
        FaseTrabajo.DESCARGANDO,
        FaseTrabajo.PROCESANDO,
        FaseTrabajo.VERIFICANDO,
    ):
        return 0
    if trabajo.status == EstadoTrabajo.COMPLETADO or trabajo.phase == FaseTrabajo.FINALIZADO:
        return 1
    if trabajo.status == EstadoTrabajo.EN_ESPERA:
        return 2
    return 3


def ordenar_trabajos_canonicamente(
    trabajos: Iterable[TrabajoDescarga],
) -> List[TrabajoDescarga]:
    """Ordena establemente los trabajos según `prioridad_orden_cola` preservando el orden FIFO dentro de cada grupo."""
    return sorted(trabajos, key=prioridad_orden_cola)


class TransicionInvalidaError(ValueError):
    """Excepción al intentar una transición no permitida."""


# Matriz de transiciones válidas de fases
TRANSICIONES_FASES: dict[FaseTrabajo, Set[FaseTrabajo]] = {
    FaseTrabajo.EN_ESPERA: {FaseTrabajo.PREPARANDO, FaseTrabajo.CANCELADO},
    FaseTrabajo.PREPARANDO: {
        FaseTrabajo.DESCARGANDO,
        FaseTrabajo.PROCESANDO,  # Para flujos directos o extracciones rápidas
        FaseTrabajo.ERROR,
        FaseTrabajo.CANCELADO,
    },
    FaseTrabajo.DESCARGANDO: {
        FaseTrabajo.PROCESANDO,
        FaseTrabajo.VERIFICANDO,
        FaseTrabajo.ERROR,
        FaseTrabajo.CANCELADO,
    },
    FaseTrabajo.PROCESANDO: {
        FaseTrabajo.DESCARGANDO,
        FaseTrabajo.VERIFICANDO,
        FaseTrabajo.ERROR,
        FaseTrabajo.CANCELADO,
    },
    FaseTrabajo.VERIFICANDO: {
        FaseTrabajo.FINALIZADO,
        FaseTrabajo.ERROR,
        FaseTrabajo.CANCELADO,
    },
    FaseTrabajo.FINALIZADO: set(),
    FaseTrabajo.ERROR: {FaseTrabajo.EN_ESPERA},  # Mediante reintento
    FaseTrabajo.CANCELADO: {FaseTrabajo.EN_ESPERA},  # Mediante reintento
}


def validar_transicion_fase(fase_actual: FaseTrabajo, nueva_fase: FaseTrabajo) -> bool:
    """Comprueba si una transición de fase es legal."""
    if fase_actual == nueva_fase:
        return True
    return nueva_fase in TRANSICIONES_FASES.get(fase_actual, set())


def actualizar_fase_trabajo(
    trabajo: TrabajoDescarga,
    nueva_fase: FaseTrabajo,
    error_code: str | None = None,
    error_detail: str | None = None,
) -> None:
    """Aplica un cambio de fase a un trabajo respetando las reglas de estado."""
    if not validar_transicion_fase(trabajo.phase, nueva_fase):
        raise TransicionInvalidaError(
            f"No se permite transicionar de {trabajo.phase.value} a {nueva_fase.value}"
        )

    trabajo.phase = nueva_fase

    if nueva_fase == FaseTrabajo.FINALIZADO:
        trabajo.status = EstadoTrabajo.COMPLETADO
        trabajo.progress = 100.0
    elif nueva_fase == FaseTrabajo.ERROR:
        trabajo.status = EstadoTrabajo.ERROR
        trabajo.error_code = error_code
        trabajo.error_detail = error_detail
    elif nueva_fase == FaseTrabajo.CANCELADO:
        trabajo.status = EstadoTrabajo.CANCELADO
    elif nueva_fase in (
        FaseTrabajo.PREPARANDO,
        FaseTrabajo.DESCARGANDO,
        FaseTrabajo.PROCESANDO,
        FaseTrabajo.VERIFICANDO,
    ):
        trabajo.status = EstadoTrabajo.ACTIVO


def marcar_interrumpido(trabajo: TrabajoDescarga) -> None:
    """Marca como interrumpido un trabajo que quedó en ejecución al cerrar la app."""
    if trabajo.status == EstadoTrabajo.ACTIVO or trabajo.phase in (
        FaseTrabajo.PREPARANDO,
        FaseTrabajo.DESCARGANDO,
        FaseTrabajo.PROCESANDO,
        FaseTrabajo.VERIFICANDO,
    ):
        trabajo.status = EstadoTrabajo.INTERRUMPIDO
        trabajo.phase = FaseTrabajo.ERROR
        trabajo.error_code = "INTERRUPTED"
        trabajo.error_detail = "La aplicación se cerró durante la descarga."


def reintentar_trabajo(trabajo: TrabajoDescarga) -> None:
    """Prepara un trabajo fallido, cancelado o interrumpido para un nuevo intento."""
    if trabajo.status not in (
        EstadoTrabajo.ERROR,
        EstadoTrabajo.CANCELADO,
        EstadoTrabajo.INTERRUMPIDO,
    ):
        raise TransicionInvalidaError(
            f"Solo se pueden reintentar trabajos terminales fallidos, no {trabajo.status.value}"
        )

    trabajo.status = EstadoTrabajo.EN_ESPERA
    trabajo.phase = FaseTrabajo.EN_ESPERA
    trabajo.progress = 0.0
    trabajo.downloaded_bytes = None
    trabajo.total_bytes = None
    trabajo.speed = None
    trabajo.eta = None
    trabajo.output_path = None
    trabajo.error_code = None
    trabajo.error_detail = None
    trabajo.attempt += 1
