# MintPlay 🍃

**MintPlay** es una aplicación de escritorio nativa, moderna y portable para Windows y Linux diseñada para la descarga y conversión de vídeo y audio desde plataformas web y enlaces directos.

Construida con **Python 3**, **PySide6 (Qt 6)** y el motor de extracción **yt-dlp**, MintPlay combina una interfaz cuidada con cinco paletas de color inspiradas en una estética limpia y sobria, junto con una arquitectura modular por capas orientada a la robustez, concurrencia segura y portabilidad total.

---

## 🌟 Características Principales

- **Distribución Portable Todo en Uno**: El paquete compilado (`.zip` / `.tar.gz`) incluye sus propios binarios estáticos de **FFmpeg**, **FFprobe** y un runtime **Node.js** autónomo para resolver desafíos de JavaScript en YouTube mediante `yt-dlp-ejs`, sin requerir instalaciones previas en el sistema anfitrión.
- **Concurrencia Controlada (1 a 1) y Orden Canónico de Cola**: Procesa una única descarga activa a la vez para evitar bloqueos por límite de peticiones (*rate-limiting*) y saturación de red o disco. La vista de cola prioriza siempre arriba la descarga activa, seguida de las recién completadas, las pendientes en estricto orden FIFO y las tareas con error o canceladas.
- **Regla de 5 Segundos al Completar**: Al finalizar una descarga verificada, la tarjeta permanece visible durante 5 segundos con accesos directos para **Abrir archivo** y **Abrir carpeta** antes de retirarse automáticamente de la cola activa.
- **Historial Local Persistente**: Registro automático de descargas completadas (`history.json`) con búsqueda instantánea por título o plataforma, verificación en vivo de la existencia del archivo en disco, apertura directa de archivo/carpeta y copia de enlace.
- **Notificaciones Nativas del Sistema**: Avisos discretos en la bandeja del sistema cuando una descarga se completa o falla, diseñados con privacidad por defecto (sin exponer URLs ni rutas locales del usuario) y con opción para activarlos o desactivarlos desde Ajustes.
- **Memoria Inteligente de Preferencias**: Recuerda por separado las últimas opciones de formato y calidad elegidas para **Vídeo** y para **Audio**, así como la última carpeta de destino válida, incluyendo un botón en Ajustes para restablecer los valores predeterminados en cualquier momento.
- **Cinco Paletas de Color con Modo Claro y Oscuro**: Incluye las paletas **Menta**, **Sakura**, **Índigo**, **Ámbar** y **Océano**, cada una disponible en modo claro y oscuro con contraste verificado (WCAG AA). El botón de sol/luna del encabezado alterna rápidamente entre claro y oscuro conservando la paleta activa.
- **Soporte Bilingüe en Caliente (ES / EN)**: Interfaz completa en **Español** e **Inglés**, intercambiable al instante desde el encabezado o desde Ajustes sin reiniciar la aplicación ni interrumpir descargas en curso.
- **Descargas Atómicas con Staging y Validación `ffprobe`**: Cada tarea se procesa en un directorio temporal aislado y se verifica con `ffprobe` antes de moverse a la carpeta final. Si una descarga se cancela o interrumpe, el área temporal se limpia sin dejar archivos incompletos.
- **Sanitización y Resolución de Colisiones de Nombres**: Limpieza automática de caracteres no válidos en Windows/Linux, bloqueo de nombres de dispositivos reservados (`CON`, `PRN`, `AUX`, `NUL`) y numeración incremental automática (`nombre (2).ext`) para no sobrescribir archivos existentes.

---

## 📥 Uso Rápido (Usuario Final vs. Código Fuente)

### Opción A: Usar la versión portable (Recomendado para usuarios finales)
Si solo deseas utilizar la aplicación en Windows sin instalar Python ni configurar dependencias:

1. Ve a la sección **Releases** del repositorio y descarga el paquete `MintPlay-windows-x64-v1.0.0.zip`.
2. Descomprime el archivo ZIP en cualquier carpeta de tu equipo.
3. Ejecuta **`MintPlay.exe`**.
   > El paquete portable de Releases **ya incluye integrados** `ffmpeg.exe`, `ffprobe.exe` y `node.exe` dentro de su estructura interna.

### Opción B: Clonar el repositorio (Desarrollo y compilación desde fuente)

> [!IMPORTANT]
> **¿Por qué los binarios de `bin/` no están subidos directamente al repositorio Git?**
>
> Los ejecutables estáticos requeridos para Windows (`ffmpeg.exe` ~100.5 MB, `ffprobe.exe` ~100.3 MB y `node.exe` ~89.2 MB) superan el **límite estricto de 100 MB por archivo de GitHub** (`GH001: Large files detected`). Por esta razón, [`bin/*.exe`](.gitignore) y la carpeta `dist/` están excluidos del control de versiones mediante `.gitignore`.
>
> Cuando clones el repositorio para ejecutar MintPlay desde código fuente o generar el ejecutable con PyInstaller, debes colocar esos tres binarios dentro de la carpeta [`bin/`](bin/) en la raíz del proyecto.

---

## 📐 Arquitectura del Proyecto

El código fuente sigue una arquitectura modular con separación estricta entre dominio, servicios e interfaz gráfica:

```text
mintplay/
├── bin/                                # Binarios autónomos locales (excluidos de Git por tamaño >100 MB)
│   ├── .gitkeep                        # Mantiene la carpeta en el repositorio
│   ├── ffmpeg.exe                      # Remuxing y transcodificación de vídeo/audio
│   ├── ffprobe.exe                     # Inspección y validación de contenedores y flujos
│   └── node.exe                        # Runtime JS autónomo para desafíos de YouTube (yt-dlp-ejs)
├── packaging/                          # Automatización de empaquetado y distribución
│   ├── MintPlay.spec                   # Especificación de compilación para PyInstaller
│   ├── launcher.py                     # Punto de entrada para el ejecutable congelado
│   ├── build_windows.ps1               # Generador del paquete y ZIP portable en Windows
│   ├── build_linux.sh                  # Generador del paquete tar.gz portable en Linux
│   └── smoke_test.md                   # Guía de verificación en entorno limpio
├── src/mintplay/                       # Código fuente principal
│   ├── domain/                         # Capa de Dominio (lógica pura, sin dependencias de GUI)
│   │   ├── models.py                   # Entidades (TrabajoDescarga, OpcionesDescarga, Enums)
│   │   ├── states.py                   # Máquina de estados finitos y transiciones válidas
│   │   └── format_policy.py            # Políticas de formatos, calidades y selectores yt-dlp
│   ├── services/                       # Capa de Servicios y Orquestación
│   │   ├── download_service.py         # Motor de descarga con yt-dlp, staging y progreso
│   │   ├── queue_manager.py            # Orquestador FIFO en hilo dedicado (QThread) y orden canónico
│   │   ├── history_service.py          # Persistencia y consulta del historial local de descargas
│   │   ├── media_probe.py              # Validación técnica post-descarga mediante ffprobe
│   │   ├── diagnostics.py              # Verificación en tiempo real de binarios y versiones
│   │   ├── output_paths.py             # Sanitización de nombres, colisiones y rutas seguras
│   │   ├── persistence.py              # Guardado atómico de configuración y cola en APPDATA
│   │   └── runtime_paths.py            # Resolución transparente de rutas en desarrollo y congelado
│   ├── ui/                             # Capa de Presentación (PySide6 / Qt 6)
│   │   ├── main_window.py              # Ventana principal, encabezado y coordinación de eventos
│   │   ├── download_form.py            # Formulario de descarga, detección de plataforma y preferencias
│   │   ├── queue_panel.py              # Panel de cola con actualización incremental sin parpadeos
│   │   ├── job_card.py                 # Tarjeta visual de tarea con estados y acciones contextuales
│   │   ├── history_dialog.py           # Diálogo modal de historial con filtro de búsqueda en vivo
│   │   ├── settings_dialog.py          # Diálogo de ajustes (idioma, paleta, modo, avisos, diagnóstico)
│   │   ├── notifications.py            # Gestor de notificaciones del sistema (QSystemTrayIcon)
│   │   ├── i18n_manager.py             # Gestor reactivo de internacionalización (ES/EN)
│   │   └── theme.py                    # Sistema de 5 paletas × 2 modos (claro/oscuro) y hojas QSS
│   ├── assets/icons/                   # Iconos de la aplicación y recursos vectoriales SVG
│   ├── i18n/                           # Catálogos de traducción (es.json, en.json)
│   └── __main__.py                     # Punto de entrada de ejecución con Python (-m mintplay)
├── tests/                              # Suite de 55 pruebas automatizadas con pytest
│   ├── conftest.py                     # Configuración y fixture compartida de QApplication
│   ├── test_states.py                  # Pruebas de la máquina de estados
│   ├── test_format_policy.py           # Pruebas de selectores y políticas de formato
│   ├── test_output_paths.py            # Pruebas de sanitización y resolución de colisiones
│   ├── test_persistence.py             # Pruebas de persistencia atómica, migración y preferencias
│   ├── test_history.py                 # Pruebas del historial local y deduplicación
│   ├── test_queue_integration.py       # Pruebas de cola FIFO, concurrencia 1 y reintentos en vivo
│   ├── test_download_service.py        # Pruebas del motor yt-dlp, staging y cancelación
│   └── test_ui.py                      # Pruebas integrales de interfaz, idiomas, paletas y avisos
├── pyproject.toml                      # Metadatos del proyecto y configuración de pytest
├── requirements-lock.txt               # Dependencias con versiones fijadas y verificadas
├── LICENSE                             # Licencia MIT del proyecto
└── README.md                           # Documentación principal
```

---

## 🎛️ Matriz de Formatos y Calidades

MintPlay ajusta dinámicamente las opciones disponibles según el tipo de medio seleccionado:

| Tipo | Formato | Opciones de Calidad | Comportamiento del Motor |
| :--- | :--- | :--- | :--- |
| **Vídeo** | **MP4** | Mejor disponible, Hasta 1080p, Hasta 720p, Hasta 480p | Prioriza vídeo H.264 (`avc1`) y audio AAC (`m4a`). Si el origen solo ofrece VP9/AV1, transcodifica de forma transparente a H.264 para máxima compatibilidad en Windows y reproductores estándar. |
| **Vídeo** | **MKV** | Mejor disponible, Hasta 1080p, Hasta 720p, Hasta 480p | Remuxing directo del mejor flujo de vídeo y audio dentro de contenedor Matroska sin pérdida por recodificación. |
| **Vídeo** | **WEBM** | Mejor disponible, Hasta 1080p, Hasta 720p, Hasta 480p | Prioriza flujos nativos VP9/AV1 + Opus en contenedor WebM. |
| **Audio** | **MP3** | 320 kbps, 256 kbps, 192 kbps *(por defecto)*, 128 kbps | Extracción de audio y codificación mediante FFmpeg (`libmp3lame`) al bitrate seleccionado. |
| **Audio** | **M4A** | Calidad original del flujo | Extracción directa del contenedor de audio AAC nativo sin recodificación innecesaria. |
| **Audio** | **FLAC** | Sin pérdida (*Lossless*) | Conversión a formato comprimido sin pérdida FLAC. |
| **Audio** | **WAV** | Sin pérdida (*PCM*) | Extracción a audio PCM sin comprimir. |

---

## 🛠️ Configuración del Entorno de Desarrollo

### Requisitos Previos
- **Python**: 3.10 o superior (probado en Python 3.14).
- **Sistema Operativo**: Windows 10/11 (x64) o Linux (x64).

### 1. Clonar el repositorio y crear el entorno virtual
```powershell
git clone https://github.com/1Conny1/MintPlay.git
cd MintPlay

# Crear entorno virtual
python -m venv venv

# Activar entorno virtual en Windows PowerShell
.\venv\Scripts\Activate.ps1

# (Alternativa en Linux/macOS)
# source venv/bin/activate
```

### 2. Instalar las dependencias de Python
```powershell
pip install -r requirements-lock.txt
```

### 3. Colocar los binarios requeridos en `bin/`
Dado que GitHub no permite alojar archivos individuales mayores a 100 MB en el historial estándar de Git, descarga y copia los siguientes tres ejecutables dentro de la carpeta `bin/` del proyecto antes de ejecutar o empaquetar en Windows:

1. **`ffmpeg.exe`** y **`ffprobe.exe`** (versión recomendada: *FFmpeg essentials/release build* de [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) o [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds/releases)).
2. **`node.exe`** (versión recomendada: binario oficial Windows x64 `node.exe` de [nodejs.org](https://nodejs.org/) LTS/Current).

Verifica que la carpeta `bin/` quede con esta estructura:
```text
bin/
├── .gitkeep
├── ffmpeg.exe
├── ffprobe.exe
└── node.exe
```

> **Consejo**: Una vez abierta la aplicación, puedes abrir **Ajustes (⚙️) → Diagnóstico del entorno** para comprobar que `yt-dlp`, `FFmpeg`, `FFprobe` y el motor JS (`Node.js`) aparecen en estado **Disponible**. En Linux, el script de empaquetado o el entorno pueden usar también los binarios instalados en el `PATH` del sistema si no se incluyen en `bin/`.

### 4. Ejecutar MintPlay desde el código fuente
```powershell
.\venv\Scripts\python.exe -m src.mintplay
```

---

## 🧪 Ejecución de Pruebas Automatizadas

MintPlay incluye una suite de **55 pruebas automatizadas** con `pytest` que validan la máquina de estados, políticas de formato, sanitización de rutas, persistencia atómica, historial de descargas, cola FIFO con reintentos en vivo, cinco paletas de color (claro/oscuro), soporte bilingüe (ES/EN) y notificaciones:

```powershell
.\venv\Scripts\python.exe -m pytest -v
```

---

## 📦 Construcción del Paquete Portable

El proyecto incluye scripts automatizados que validan la presencia de los binarios en `bin/`, ejecutan **PyInstaller** usando `packaging/MintPlay.spec`, copian las licencias y generan el archivo comprimido portable final listo para distribuir (por ejemplo, en **GitHub Releases**).

### Construir en Windows (PowerShell)
```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_windows.ps1
```
Al finalizar, se habrán generado:
- Carpeta ejecutable desempaquetada: `dist/MintPlay/MintPlay.exe`
- Archivo comprimido listo para distribución: `dist/MintPlay-windows-x64-v1.0.0.zip`

### Construir en Linux (Bash)
```bash
bash packaging/build_linux.sh
```
Generará el archivo:
- `dist/MintPlay-linux-x64-v1.0.0.tar.gz`

Para validar el paquete portable en un entorno limpio sin dependencias instaladas, consulta la [Guía de Smoke Test](packaging/smoke_test.md).

---

## ⚖️ Aviso Legal y Uso Responsable

MintPlay ha sido desarrollada como una herramienta técnica para la gestión de medios personales, creación de copias de seguridad de contenido propio y descarga de material publicado bajo licencias libres (*Creative Commons*, Dominio Público) o con autorización expresa de sus titulares.

El usuario es el único responsable del uso que realice de esta aplicación y del cumplimiento de los términos de servicio de cada plataforma y de la normativa de propiedad intelectual vigente en su jurisdicción.
