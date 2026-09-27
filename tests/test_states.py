"""Pruebas unitarias de estados y transiciones de trabajo."""

import pytest
from mintplay.domain.models import EstadoTrabajo, FaseTrabajo, TrabajoDescarga
from mintplay.domain.states import (
    TransicionInvalidaError,
    actualizar_fase_trabajo,
    marcar_interrumpido,
    reintentar_trabajo,
    validar_transicion_fase,
)


def test_transiciones_fase_validas():
    assert validar_transicion_fase(FaseTrabajo.EN_ESPERA, FaseTrabajo.PREPARANDO)
    assert validar_transicion_fase(FaseTrabajo.PREPARANDO, FaseTrabajo.DESCARGANDO)
    assert validar_transicion_fase(FaseTrabajo.DESCARGANDO, FaseTrabajo.PROCESANDO)
    assert validar_transicion_fase(FaseTrabajo.PROCESANDO, FaseTrabajo.VERIFICANDO)
    assert validar_transicion_fase(FaseTrabajo.VERIFICANDO, FaseTrabajo.FINALIZADO)
    assert validar_transicion_fase(FaseTrabajo.DESCARGANDO, FaseTrabajo.ERROR)
    assert validar_transicion_fase(FaseTrabajo.DESCARGANDO, FaseTrabajo.CANCELADO)


def test_transicion_invalida_lanza_error():
    assert not validar_transicion_fase(FaseTrabajo.EN_ESPERA, FaseTrabajo.FINALIZADO)
    trabajo = TrabajoDescarga()
    with pytest.raises(TransicionInvalidaError):
        actualizar_fase_trabajo(trabajo, FaseTrabajo.FINALIZADO)


def test_flujo_completo_exitoso():
    trabajo = TrabajoDescarga()
    assert trabajo.status == EstadoTrabajo.EN_ESPERA

    actualizar_fase_trabajo(trabajo, FaseTrabajo.PREPARANDO)
    assert trabajo.status == EstadoTrabajo.ACTIVO
    assert trabajo.phase == FaseTrabajo.PREPARANDO

    actualizar_fase_trabajo(trabajo, FaseTrabajo.DESCARGANDO)
    assert trabajo.status == EstadoTrabajo.ACTIVO

    actualizar_fase_trabajo(trabajo, FaseTrabajo.PROCESANDO)
    assert trabajo.status == EstadoTrabajo.ACTIVO

    actualizar_fase_trabajo(trabajo, FaseTrabajo.VERIFICANDO)
    assert trabajo.status == EstadoTrabajo.ACTIVO

    actualizar_fase_trabajo(trabajo, FaseTrabajo.FINALIZADO)
    assert trabajo.status == EstadoTrabajo.COMPLETADO
    assert trabajo.progress == 100.0
    assert trabajo.es_terminal


def test_marcar_interrumpido_en_activo():
    trabajo = TrabajoDescarga()
    actualizar_fase_trabajo(trabajo, FaseTrabajo.PREPARANDO)
    marcar_interrumpido(trabajo)

    assert trabajo.status == EstadoTrabajo.INTERRUMPIDO
    assert trabajo.error_code == "INTERRUPTED"


def test_reintentar_trabajo_reinicia_valores():
    trabajo = TrabajoDescarga()
    actualizar_fase_trabajo(trabajo, FaseTrabajo.PREPARANDO)
    actualizar_fase_trabajo(trabajo, FaseTrabajo.ERROR, error_code="NET_ERR", error_detail="Fallo")
    trabajo.progress = 45.0

    reintentar_trabajo(trabajo)
    assert trabajo.status == EstadoTrabajo.EN_ESPERA
    assert trabajo.phase == FaseTrabajo.EN_ESPERA
    assert trabajo.progress == 0.0
    assert trabajo.error_code is None
    assert trabajo.attempt == 2
