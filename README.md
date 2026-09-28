<div align="center">

# MintPlay

**Aplicación de escritorio nativa para la descarga, extracción y conversión de vídeo y audio**

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/UI-PySide6%20(Qt%206)-41CD52?style=flat-square&logo=qt&logoColor=white)](https://wiki.qt.io/Qt_for_Python)
[![yt-dlp](https://img.shields.io/badge/Motor-yt--dlp-FF0000?style=flat-square&logo=youtube&logoColor=white)](https://github.com/yt-dlp/yt-dlp)
[![Tests](https://img.shields.io/badge/Tests-55%20passed-168569?style=flat-square&logo=pytest&logoColor=white)](#pruebas-automatizadas)
[![Platform](https://img.shields.io/badge/Plataforma-Windows%20x64%20%7C%20Linux%20x64-0078D6?style=flat-square)](#requisitos-del-sistema)
[![License: MIT](https://img.shields.io/badge/Licencia-MIT-yellow.svg?style=flat-square)](LICENSE)

[Descripción General](#descripción-general) •
[Características Técnicas](#características-técnicas) •
[Binarios Externos y Límites de Git](#binarios-externos-y-límites-de-git) •
[Instalación y Puesta en Marcha](#instalación-y-puesta-en-marcha) •
[Compilación del Paquete Portable](#compilación-del-paquete-portable) •
[Arquitectura](#arquitectura-del-proyecto)

</div>

---

## Descripción General

**MintPlay** es una aplicación de escritorio multiplataforma (Windows y Linux) desarrollada en **Python** con **PySide6 (Qt 6)** y **yt-dlp**. Su objetivo es ofrecer una interfaz limpia, predecible y libre de fricción para descargar contenido multimedia en formatos compatibles o extraer pistas de audio sin pérdida, gestionando de forma aislada las herramientas de procesamiento (`FFmpeg`, `FFprobe` y `Node.js`).

El diseño prioriza la estabilidad operativa: ejecuta una única descarga activa a la vez mediante un orquestador FIFO en hilo dedicado, procesa los archivos en directorios temporales aislados (*staging*), valida la integridad de cada contenedor con `ffprobe` antes de moverlo a la carpeta del usuario y conserva el estado de la cola y las preferencias mediante escritura atómica en disco.

---

## Características Técnicas

### Motor de Descarga y Procesamiento
- **Ejecución secuencial controlada (concurrencia 1:1)**: Procesa una tarea activa a la vez para evitar bloqueos por tasa de peticiones (*rate-limiting*), corrupción de fragmentos o saturación de ancho de banda, permitiendo encolar nuevas URLs en cualquier momento.
- **Orden canónico de cola en tiempo real**: El panel de descargas mantiene siempre en la parte superior la tarea **Activa**, seguida de las recién **Completadas** (visibles durante 5 segundos con acceso rápido al archivo y carpeta), las tareas **En espera** en estricto orden FIFO y las tareas con **Error / Interrumpidas / Canceladas**.
- **Descarga atómica con área de *staging***: Los fragmentos temporales (`.part`, `.ytdl`) se descargan en un directorio temporal aislado por tarea. Solo tras superar la inspección técnica de `ffprobe` se traslada el archivo final a la carpeta de destino; cualquier cancelación limpia los residuos automáticamente.
- **Sanitización estricta de rutas y nombres**: Filtra caracteres ilegales en NTFS/ext4, secuencias de escape, puntos/espacios terminales y nombres reservados de Windows (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`), resolviendo colisiones de nombres mediante sufijos incrementales (`archivo (2).mp4`).
- **Detección unificada de plataforma**: Identifica de forma orientativa el origen del enlace desde el momento en que se pega en el formulario (YouTube, Facebook, Instagram, TikTok, X/Twitter, Twitch, Vimeo, SoundCloud, Dailymotion o enlace directo) y mantiene la misma etiqueta en la cola y en el historial.

### Experiencia de Usuario e Interfaz
- **Cinco paletas de color con modo Claro y Oscuro**: Incluye las paletas **Menta**, **Sakura**, **Índigo**, **Ámbar** y **Océano**, todas verificadas bajo relaciones de contraste **WCAG AA**. Permite elegir paleta y modo por separado en Ajustes o alternar entre claro y oscuro desde el encabezado sin interrumpir descargas.
- **Internacionalización reactiva (Español / Inglés)**: Cambio instantáneo de idioma en toda la interfaz, diálogos modales, estados de cola y notificaciones sin reiniciar la aplicación.
- **Memoria independiente de preferencias**: Recuerda por separado la última combinación de formato y calidad utilizada para **Vídeo** y para **Audio**, así como la última carpeta de destino válida (sin almacenar nunca URLs ni nombres personalizados previos en el formulario), con opción de restablecimiento en Ajustes.
- **Historial local persistente**: Almacena las descargas completadas en `history.json` con búsqueda instantánea por título o plataforma, comprobación en vivo de existencia del archivo físico, apertura directa de archivo/carpeta y copia de URL.
- **Notificaciones nativas del sistema**: Emite avisos en la bandeja del sistema al completarse o fallar una descarga. Por privacidad, las notificaciones nunca incluyen URLs ni rutas del sistema de archivos local, y pueden desactivarse desde Ajustes.

---

## Matriz de Formatos y Calidades

| Tipo de Medio | Contenedor / Formato | Calidades Disponibles | Política de Procesamiento (`format_policy.py`) |
| :--- | :--- | :--- | :--- |
| **Vídeo** | `MP4` | Mejor disponible, Hasta 1080p, Hasta 720p, Hasta 480p | Prioriza flujos H.264 (`avc1`) + AAC (`m4a`). Si el origen solo entrega VP9 o AV1, recodifica automáticamente a H.264/AAC para garantizar compatibilidad nativa en reproductores de Windows. |
| **Vídeo** | `MKV` | Mejor disponible, Hasta 1080p, Hasta 720p, Hasta 480p | *Remuxing* directo de los mejores flujos de vídeo y audio disponibles en contenedor Matroska sin pérdida por recodificación. |
| **Vídeo** | `WEBM` | Mejor disponible, Hasta 1080p, Hasta 720p, Hasta 480p | Prioriza flujos nativos VP9/AV1 y audio Opus en contenedor WebM. |
| **Audio** | `MP3` | `320 kbps`, `256 kbps`, `192 kbps` *(predeterminado)*, `128 kbps` | Extracción de pista de audio y codificación mediante FFmpeg (`libmp3lame`) a la tasa de bits seleccionada. |
| **Audio** | `M4A` | Calidad original | Extracción directa del flujo AAC nativo sin recodificación. |
| **Audio** | `FLAC` | Sin pérdida (*Lossless*) | Conversión a formato de compresión sin pérdida FLAC. |
| **Audio** | `WAV` | Sin pérdida (*PCM*) | Extracción a audio PCM sin comprimir. |

---

## Binarios Externos y Límites de Git

> [!IMPORTANT]
> **¿Por qué los binarios (`bin/*.exe`) y el paquete portable (`dist/`) no están incluidos en el repositorio Git?**
>
> GitHub aplica un **límite estricto de 100 MB por archivo** en cualquier `git push` estándar (`remote: error: GH001: Large files detected`). Los binarios estáticos utilizados por MintPlay en Windows superan dicho umbral:
>
> - `bin/ffmpeg.exe` (~100.5 MB)
> - `bin/ffprobe.exe` (~100.3 MB)
> - `bin/node.exe` (~89.2 MB)
> - `dist/MintPlay-windows-x64-v1.0.0.zip` (~271.5 MB)
>
> Por este motivo, tanto `bin/*.exe` como `dist/` están excluidos en [`.gitignore`](.gitignore). El repositorio contiene el **código fuente íntegro y los scripts de automatización** para ejecutar la aplicación o compilar localmente el paquete portable una vez colocados los binarios en la carpeta `bin/`.

### Archivos requeridos en `bin/` (Windows x64)

Antes de ejecutar MintPlay desde el código fuente o de compilar el ejecutable portable con PyInstaller, descarga y coloca estos tres archivos dentro del directorio [`bin/`](bin/) en la raíz del proyecto:

| Archivo | Función en MintPlay | Fuente Oficial Recomendada |
| :--- | :--- | :--- |
| **`ffmpeg.exe`** | *Remuxing* de contenedores, conversión de vídeo H.264 y extracción de audio. | [FFmpeg Builds (gyan.dev)](https://www.gyan.dev/ffmpeg/builds/) o [BtbN FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds/releases) (*release essentials / gpl x64*) |
| **`ffprobe.exe`** | Inspección técnica y validación post-descarga de flujos de audio/vídeo. | Incluido en el mismo paquete oficial de [FFmpeg](https://www.gyan.dev/ffmpeg/builds/) |
| **`node.exe`** | Runtime JavaScript autónomo requerido por `yt-dlp-ejs` para resolver desafíos de extracción de YouTube. | [Node.js Oficial (Windows Binary `.zip` x64)](https://nodejs.org/en/download) |

La carpeta `bin/` debe quedar exactamente con esta estructura:

```text
mintplay/
└── bin/
    ├── .gitkeep
    ├── ffmpeg.exe
    ├── ffprobe.exe
    └── node.exe
```

---

## Instalación y Puesta en Marcha

### Requisitos del Sistema
- **Sistema Operativo**: Windows 10 / 11 (x64) o Linux (x64).
- **Python**: `3.12` o superior (definido en [`pyproject.toml`](pyproject.toml)).
- **Binarios auxiliares**: `ffmpeg`, `ffprobe` y `node` ubicados en `bin/` (o accesibles en el `PATH` en entornos Linux).

### 1. Clonar el repositorio
```powershell
git clone https://github.com/1Conny1/MintPlay.git
cd MintPlay
```

### 2. Crear y activar el entorno virtual
En **Windows (PowerShell)**:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

En **Linux (Bash)**:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias fijadas
```powershell
pip install -r requirements-lock.txt
```

### 4. Verificar los binarios en `bin/` y ejecutar la aplicación
Una vez copiados `ffmpeg.exe`, `ffprobe.exe` y `node.exe` dentro de `bin/`, inicia MintPlay con:

```powershell
python -m mintplay
```
*(También puedes ejecutar `.\venv\Scripts\python.exe -m src.mintplay` sin activar previamente el entorno virtual).*

> **Verificación rápida**: Al abrir la interfaz, pulsa el icono de **Ajustes (⚙️)** en la esquina superior derecha. En la sección **Diagnóstico de herramientas**, comprueba que `FFmpeg`, `FFprobe` y `Motor JavaScript (Node.js)` aparezcan con estado disponible (`✓`).

---

## Compilación del Paquete Portable

Dado que el paquete compilado (`dist/`) no se almacena en el repositorio Git por su tamaño (~271 MB), el proyecto incluye scripts automatizados para construir localmente la distribución portable completa (ejecutable autónomo sin consola + binarios embebidos + licencias + archivo `.zip` / `.tar.gz`).

### Generar el portable en Windows
Asegúrate de tener `ffmpeg.exe`, `ffprobe.exe` y `node.exe` en `bin/` y ejecuta desde PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_windows.ps1
```

El script realizará automáticamente las siguientes etapas:
1. Validará la presencia de `ffmpeg.exe`, `ffprobe.exe` y `node.exe` en `bin/`.
2. Limpiará compilaciones previas en `build/` y `dist/`.
3. Ejecutará **PyInstaller** con la especificación [`packaging/MintPlay.spec`](packaging/MintPlay.spec).
4. Copiará los binarios auxiliares y los avisos de licencias ([`LICENSE`](LICENSE) y [`LICENSES/`](LICENSES/)).
5. Generará el directorio ejecutable y el archivo comprimido final:
   - Ejecutable directo: `dist/MintPlay/MintPlay.exe`
   - Paquete portable comprimido: `dist/MintPlay-windows-x64-v1.0.0.zip`

### Generar el portable en Linux
```bash
bash packaging/build_linux.sh
```
Generará el paquete portable en `dist/MintPlay-linux-x64-v1.0.0.tar.gz`.

Para validar el paquete generado en una máquina limpia sin dependencias preinstaladas, consulta la [Guía de Smoke Test](packaging/smoke_test.md).

---

## Pruebas Automatizadas

El proyecto cuenta con una suite de **55 pruebas automatizadas** con `pytest` que cubren la máquina de estados, políticas de formato, sanitización de rutas, persistencia atómica, historial de descargas, concurrencia FIFO con reintentos en vivo, cinco paletas de color (claro/oscuro), internacionalización (ES/EN) y notificaciones del sistema:

```powershell
.\venv\Scripts\python.exe -m pytest -v
```

---

## Arquitectura del Proyecto

El código fuente está organizado bajo una arquitectura en tres capas desacopladas (`domain`, `services` y `ui`):

```text
mintplay/
├── bin/                                # Binarios externos locales (excluidos de Git por límite >100 MB)
│   └── .gitkeep                        # Preserva el directorio en el control de versiones
├── LICENSES/
│   └── THIRD_PARTY_LICENSES.md         # Atribuciones y licencias de componentes de terceros
├── packaging/                          # Scripts y configuración de empaquetado portable
│   ├── MintPlay.spec                   # Especificación de PyInstaller (modo onedir, sin consola)
│   ├── launcher.py                     # Lanzador de entrada para el binario congelado
│   ├── build_windows.ps1               # Pipeline de compilación y compresión ZIP para Windows
│   ├── build_linux.sh                  # Pipeline de compilación tar.gz para Linux
│   └── smoke_test.md                   # Protocolo de verificación en entorno limpio
├── src/mintplay/                       # Paquete principal de la aplicación
│   ├── domain/                         # Capa de Dominio (sin dependencias de interfaz gráfica)
│   │   ├── models.py                   # Entidades de datos (TrabajoDescarga, OpcionesDescarga, Enums)
│   │   ├── states.py                   # Máquina de estados finitos y reglas de transición
│   │   ├── format_policy.py            # Matriz de compatibilidad y selectores de formato yt-dlp
│   │   └── platforms.py                # Reconocimiento unificado de plataformas por URL y extractor
│   ├── services/                       # Capa de Servicios e Infraestructura
│   │   ├── download_service.py         # Ejecución de yt-dlp, aislamiento en staging y callbacks
│   │   ├── queue_manager.py            # Orquestador FIFO en QThread y ordenamiento canónico
│   │   ├── history_manager.py          # Persistencia, deduplicación y consulta de history.json
│   │   ├── media_probe.py              # Inspección y verificación de contenedores con ffprobe
│   │   ├── diagnostics.py              # Detección de versiones de FFmpeg, FFprobe y Node.js
│   │   ├── output_paths.py             # Sanitización de nombres, rutas seguras y control de colisiones
│   │   ├── persistence.py              # Escritura atómica en APPDATA/ ~/.config y migración de ajustes
│   │   └── runtime_paths.py            # Resolución de rutas entre entorno de desarrollo y PyInstaller
│   ├── ui/                             # Capa de Presentación (PySide6 / Qt 6)
│   │   ├── main_window.py              # Ventana principal, geometría adaptativa y barra superior
│   │   ├── download_form.py            # Formulario de entrada, validación y memoria de opciones
│   │   ├── queue_panel.py              # Vista de cola con reordenamiento incremental de tarjetas
│   │   ├── job_card.py                 # Componente visual de tarea y acciones según estado
│   │   ├── history_dialog.py           # Diálogo de historial con filtrado en tiempo real
│   │   ├── settings_dialog.py          # Configuración de idioma, paleta, modo, avisos y diagnóstico
│   │   ├── notifications.py            # Gestor de notificaciones en bandeja del sistema
│   │   ├── i18n_manager.py             # Motor reactivo de traducciones (Español / Inglés)
│   │   └── theme.py                    # Generador de hojas de estilo QSS (5 paletas × 2 modos)
│   ├── assets/icons/                   # Iconos de aplicación y gráficos vectoriales SVG propios
│   ├── i18n/                           # Catálogos de textos bilingües (es.json, en.json)
│   ├── __init__.py
│   └── __main__.py                     # Punto de entrada principal
├── tests/                              # Suite de pruebas automatizadas (pytest)
│   ├── conftest.py                     # Configuración de entorno offscreen y fixture QApplication
│   ├── test_states.py                  # Pruebas de transiciones de estado
│   ├── test_format_policy.py           # Pruebas de políticas de formato y selectores
│   ├── test_output_paths.py            # Pruebas de sanitización de nombres y colisiones
│   ├── test_persistence.py             # Pruebas de persistencia atómica y preferencias
│   ├── test_history.py                 # Pruebas de historial y manejo de archivos ausentes
│   ├── test_queue_integration.py       # Pruebas de concurrencia 1:1, orden canónico y reintentos
│   ├── test_download_service.py        # Pruebas de staging, validación ffprobe y cancelación
│   └── test_ui.py                      # Pruebas integrales de interfaz, temas, idiomas y avisos
├── .gitignore                          # Reglas de exclusión (venv, build, dist, bin/*.exe)
├── pyproject.toml                      # Definición del paquete, dependencias y configuración pytest
├── requirements.txt                    # Dependencias base del proyecto
├── requirements-lock.txt               # Versiones exactas fijadas del entorno de referencia
├── LICENSE                             # Licencia MIT
└── README.md                           # Documentación del proyecto
```

---

## Almacenamiento de Datos del Usuario

MintPlay nunca modifica ni escribe archivos de estado dentro de la carpeta del ejecutable para preservar la portabilidad. Los datos de configuración y estado se guardan de forma atómica en el directorio estándar del perfil del usuario:

- **Windows**: `%APPDATA%\MintPlay\`
- **Linux**: `~/.config/mintplay/`

| Archivo | Contenido |
| :--- | :--- |
| `settings.json` | Idioma, paleta, modo claro/oscuro, estado de notificaciones, última carpeta válida y últimas opciones de vídeo/audio. |
| `queue.json` | Estado persistente de las tareas de la cola (las descargas activas al cerrar se marcan como *Interrumpidas* para permitir reintentarlas en el siguiente inicio). |
| `history.json` | Registro histórico local de descargas finalizadas. |
| `mintplay.log` | Registro técnico de eventos y diagnósticos de ejecución. |

---

## Licencia y Aviso de Uso Responsable

Este proyecto se distribuye bajo la **Licencia MIT**. Consulta el archivo [`LICENSE`](LICENSE) para el texto legal completo y [`LICENSES/THIRD_PARTY_LICENSES.md`](LICENSES/THIRD_PARTY_LICENSES.md) para las licencias de los componentes de terceros (`FFmpeg`, `yt-dlp`, `Node.js`, `PySide6` y `PyInstaller`).

MintPlay es una herramienta técnica concebida para la gestión de medios personales, creación de copias de seguridad de contenido propio y descarga de recursos publicados bajo licencias abiertas (*Creative Commons*, Dominio Público) o con autorización de sus titulares. El usuario es el único responsable de cumplir con las condiciones de servicio de las plataformas de origen y con la legislación de propiedad intelectual aplicable en su jurisdicción.
