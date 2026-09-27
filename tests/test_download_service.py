"""Pruebas unitarias y de integración del servicio de descargas yt-dlp."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yt_dlp
from mintplay.domain.models import (
    EstadoTrabajo,
    FaseTrabajo,
    OpcionesDescarga,
    TipoMedio,
    TrabajoDescarga,
)
from mintplay.services.download_service import (
    CancelacionDescargaException,
    ServicioDescargaYtDlp,
)
from mintplay.services.media_probe import ResultadoVerificacion


def test_servicio_descarga_cancela_antes_de_iniciar(tmp_path: Path):
    servicio = ServicioDescargaYtDlp()
    trabajo = TrabajoDescarga(url="https://ejemplo.com/test", destination_dir=str(tmp_path))

    with pytest.raises(CancelacionDescargaException):
        servicio.descargar(
            trabajo=trabajo,
            cb_progreso=lambda *args: None,
            cb_fase=lambda *args: None,
            es_cancelado=lambda: True,
        )


def test_servicio_descarga_orquesta_staging_y_verificacion(tmp_path: Path):
    servicio = ServicioDescargaYtDlp()
    trabajo = TrabajoDescarga(
        url="https://ejemplo.com/test",
        destination_dir=str(tmp_path),
        custom_name="VideoPrueba",
    )

    fases_observadas = []

    def mock_extract_info(self, url, download=True):
        from mintplay.services.output_paths import crear_directorio_staging

        dir_stg = crear_directorio_staging(trabajo.id, tmp_path)
        dummy_file = dir_stg / "VideoPrueba.mp4"
        dummy_file.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"datos_dummy" * 50)
        return {"title": "Titulo Remoto", "extractor_key": "Generic"}

    mock_verificacion = ResultadoVerificacion(
        es_valido=True,
        tiene_audio=True,
        tiene_video=True,
        tamano_bytes=1000,
        mensaje="OK",
    )

    with patch.object(yt_dlp.YoutubeDL, "extract_info", new=mock_extract_info), \
         patch("mintplay.services.download_service.verificar_archivo_multimedia", return_value=mock_verificacion):

        ruta_final = servicio.descargar(
            trabajo=trabajo,
            cb_progreso=lambda *args: None,
            cb_fase=lambda f: fases_observadas.append(f),
            es_cancelado=lambda: False,
        )

        assert ruta_final.exists()
        assert ruta_final.name == "VideoPrueba.mp4"
        assert ruta_final.parent == tmp_path
        assert FaseTrabajo.PREPARANDO in fases_observadas
        assert FaseTrabajo.VERIFICANDO in fases_observadas
        assert trabajo.display_title == "Titulo Remoto"


def test_servicio_descarga_falla_si_verificacion_ffprobe_invalida(tmp_path: Path):
    servicio = ServicioDescargaYtDlp()
    trabajo = TrabajoDescarga(
        url="https://ejemplo.com/test_corrupto",
        destination_dir=str(tmp_path),
        custom_name="VideoCorrupto",
    )

    def mock_extract_info(self, url, download=True):
        from mintplay.services.output_paths import crear_directorio_staging

        dir_stg = crear_directorio_staging(trabajo.id, tmp_path)
        dummy_file = dir_stg / "VideoCorrupto.mp4"
        dummy_file.write_bytes(b"basura")
        return {"title": "Video Corrupto"}

    mock_verificacion = ResultadoVerificacion(
        es_valido=False,
        tiene_audio=False,
        tiene_video=False,
        tamano_bytes=6,
        mensaje="El archivo no contiene flujos válidos de video",
    )

    with patch.object(yt_dlp.YoutubeDL, "extract_info", new=mock_extract_info), \
         patch("mintplay.services.download_service.verificar_archivo_multimedia", return_value=mock_verificacion):

        with pytest.raises(RuntimeError, match="Fallo de verificación multimedia"):
            servicio.descargar(
                trabajo=trabajo,
                cb_progreso=lambda *args: None,
                cb_fase=lambda *args: None,
                es_cancelado=lambda: False,
            )
