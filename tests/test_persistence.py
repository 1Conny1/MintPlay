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


def test_migracion_configuracion_antigua_y_recuperacion_paleta_invalida(tmp_path: Path):
    with patch("mintplay.services.persistence.obtener_directorio_datos_usuario", return_value=tmp_path):
        ruta_cfg = tmp_path / "settings.json"

        # 1. Configuración antigua: solo tiene "tema": "light" sin clave "paleta"
        ruta_cfg.write_text(
            json.dumps({"idioma": "es", "tema": "light", "directorio_descargas": str(tmp_path)}),
            encoding="utf-8",
        )
        cfg_migrada = cargar_configuracion()
        assert cfg_migrada["paleta"] == "mint"
        assert cfg_migrada["tema"] == "light"

        # 2. Paleta desconocida con modo válido -> recupera a "mint" manteniendo "light"
        ruta_cfg.write_text(
            json.dumps(
                {
                    "idioma": "en",
                    "paleta": "neon_inexistente",
                    "tema": "light",
                    "directorio_descargas": str(tmp_path),
                }
            ),
            encoding="utf-8",
        )
        cfg_paleta_invalida = cargar_configuracion()
        assert cfg_paleta_invalida["paleta"] == "mint"
        assert cfg_paleta_invalida["tema"] == "light"
        assert cfg_paleta_invalida["idioma"] == "en"

        # 3. Paleta válida ("ocean") con modo inválido -> mantiene "ocean" y recupera modo a "dark"
        ruta_cfg.write_text(
            json.dumps(
                {
                    "idioma": "es",
                    "paleta": "ocean",
                    "tema": "modo_invalido",
                    "directorio_descargas": str(tmp_path),
                }
            ),
            encoding="utf-8",
        )
        cfg_modo_invalido = cargar_configuracion()
        assert cfg_modo_invalido["paleta"] == "ocean"
        assert cfg_modo_invalido["tema"] == "dark"

        # 4. Guardar y recargar Sakura claro y Océano oscuro
        guardar_configuracion(
            {
                "idioma": "es",
                "paleta": "sakura",
                "tema": "light",
                "directorio_descargas": str(tmp_path),
            }
        )
        recargada_sakura = cargar_configuracion()
        assert recargada_sakura["paleta"] == "sakura"
        assert recargada_sakura["tema"] == "light"

        guardar_configuracion(
            {
                "idioma": "en",
                "paleta": "ocean",
                "tema": "dark",
                "directorio_descargas": str(tmp_path),
            }
        )
        recargada_ocean = cargar_configuracion()
        assert recargada_ocean["paleta"] == "ocean"
        assert recargada_ocean["tema"] == "dark"


def test_persistencia_opciones_separadas_video_audio_notificaciones_y_restablecimiento(
    tmp_path: Path,
):
    from mintplay.services.persistence import restablecer_opciones_descarga

    with patch(
        "mintplay.services.persistence.obtener_directorio_datos_usuario",
        return_value=tmp_path,
    ):
        carpeta_valida = tmp_path / "mis_descargas"
        carpeta_valida.mkdir()

        guardar_configuracion(
            {
                "idioma": "en",
                "paleta": "indigo",
                "tema": "light",
                "notificaciones_activas": False,
                "ultimo_tipo_medio": "audio",
                "video_formato": "mkv",
                "video_calidad": "720p",
                "audio_formato": "mp3",
                "audio_calidad": "256",
                "directorio_descargas": str(carpeta_valida),
                "url": "https://no-debe-guardarse.example/video",
                "custom_name": "secreto",
            }
        )

        cargada = cargar_configuracion()
        assert cargada["notificaciones_activas"] is False
        assert cargada["ultimo_tipo_medio"] == "audio"
        assert cargada["video_formato"] == "mkv"
        assert cargada["video_calidad"] == "720p"
        assert cargada["audio_formato"] == "mp3"
        assert cargada["audio_calidad"] == "256"
        assert cargada["directorio_descargas"] == str(carpeta_valida)
        assert "url" not in cargada
        assert "custom_name" not in cargada

        # Opciones antiguas o incompatibles + carpeta eliminada -> fallback seguro + marca de aviso
        carpeta_borrada = tmp_path / "carpeta_que_ya_no_existe"
        ruta_cfg = tmp_path / "settings.json"
        ruta_cfg.write_text(
            json.dumps(
                {
                    "idioma": "es",
                    "paleta": "sakura",
                    "tema": "dark",
                    "ultimo_tipo_medio": "tipo_invalido",
                    "video_formato": "mp4",
                    "video_calidad": "256",  # Bitrate de audio en formato de vídeo
                    "audio_formato": "wav",
                    "audio_calidad": "320",  # Bitrate MP3 en formato sin pérdida WAV
                    "directorio_descargas": str(carpeta_borrada),
                }
            ),
            encoding="utf-8",
        )
        recuperada = cargar_configuracion()
        assert recuperada["ultimo_tipo_medio"] == "video"
        assert recuperada["video_formato"] == "mp4"
        assert recuperada["video_calidad"] == "best"
        assert recuperada["audio_formato"] == "wav"
        assert recuperada["audio_calidad"] == "lossless"
        assert recuperada["carpeta_restaurada_por_invalida"] is True
        assert Path(recuperada["directorio_descargas"]).exists()

        # Restablecer opciones de descarga conserva idioma, paleta, tema y notificaciones
        restablecida = restablecer_opciones_descarga(
            {
                "idioma": "en",
                "paleta": "amber",
                "tema": "light",
                "notificaciones_activas": False,
                "ultimo_tipo_medio": "audio",
                "video_formato": "webm",
                "video_calidad": "480p",
                "audio_formato": "flac",
                "audio_calidad": "lossless",
                "directorio_descargas": str(carpeta_valida),
            }
        )
        assert restablecida["idioma"] == "en"
        assert restablecida["paleta"] == "amber"
        assert restablecida["tema"] == "light"
        assert restablecida["notificaciones_activas"] is False
        assert restablecida["ultimo_tipo_medio"] == "video"
        assert restablecida["video_formato"] == "mp4"
        assert restablecida["video_calidad"] == "best"
        assert restablecida["audio_formato"] == "mp3"
        assert restablecida["audio_calidad"] == "192"


