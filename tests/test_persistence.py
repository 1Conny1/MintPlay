"""Pruebas de persistencia atómica y tolerancia a fallos."""

import json
from pathlib import Path
from unittest.mock import patch

from mintplay.domain.models import EstadoTrabajo, FaseTrabajo, TrabajoDescarga
from mintplay.services.persistence import (
    cargar_cola,
    cargar_configuracion,
    guardar_cola,
    guardar_configuracion,
)


def test_guardar_y_cargar_configuracion(tmp_path: Path):
    with patch("mintplay.services.persistence.obtener_directorio_datos_usuario", return_value=tmp_path):
        config_inicial = cargar_configuracion()
        assert config_inicial["idioma"] == "es"
        assert config_inicial["tema"] == "dark"

        config_inicial["idioma"] = "en"
        config_inicial["tema"] = "light"
        guardar_configuracion(config_inicial)

        config_recargada = cargar_configuracion()
        assert config_recargada["idioma"] == "en"
        assert config_recargada["tema"] == "light"


def test_guardar_y_cargar_cola(tmp_path: Path):
    with patch("mintplay.services.persistence.obtener_directorio_datos_usuario", return_value=tmp_path):
        trabajo1 = TrabajoDescarga(url="https://ejemplo.com/1", display_title="Video 1")
        trabajo2 = TrabajoDescarga(url="https://ejemplo.com/2", display_title="Video 2")
        guardar_cola([trabajo1, trabajo2])

        cargados = cargar_cola()
        assert len(cargados) == 2
        assert cargados[0].url == "https://ejemplo.com/1"
        assert cargados[1].url == "https://ejemplo.com/2"


def test_recuperacion_interrumpido_al_cargar(tmp_path: Path):
    with patch("mintplay.services.persistence.obtener_directorio_datos_usuario", return_value=tmp_path):
        trabajo_activo = TrabajoDescarga(
            url="https://ejemplo.com/activo",
            status=EstadoTrabajo.ACTIVO,
            phase=FaseTrabajo.DESCARGANDO,
        )
        guardar_cola([trabajo_activo])

        recuperados = cargar_cola()
        assert len(recuperados) == 1
        assert recuperados[0].status == EstadoTrabajo.INTERRUMPIDO
        assert recuperados[0].error_code == "INTERRUPTED"


def test_tolerancia_archivo_corrupto(tmp_path: Path):
    with patch("mintplay.services.persistence.obtener_directorio_datos_usuario", return_value=tmp_path):
        ruta_cola = tmp_path / "queue.json"
        ruta_cola.write_text("{archivo_corrupto_invalido: 123", encoding="utf-8")

        cola = cargar_cola()
        assert cola == []

        archivos_broken = list(tmp_path.glob("queue.broken.*"))
        assert len(archivos_broken) == 1
