# MintPlay 🍃

**MintPlay** es una aplicación de escritorio nativa, moderna y portable para Windows y Linux diseñada para la descarga y conversión de vídeo y audio desde plataformas web y enlaces directos.

Construida con **Python 3**, **PySide6 (Qt6)** y el motor de extracción **yt-dlp**, MintPlay combina una interfaz intuitiva inspirada en la estética japonesa (tonos menta y sobrios) con una arquitectura modular por capas orientada a la robustez, concurrencia segura y portabilidad total sin requerir dependencias preinstaladas en el sistema operativo anfitrión.

---

## 🌟 Características Principales

- **Portabilidad Absoluta**: Incluye sus propios binarios estáticos de **FFmpeg**, **FFprobe** y un runtime **Node.js** embebido para resolver los desafíos de JavaScript de YouTube mediante `yt-dlp-ejs`. No requiere instalar Python, FFmpeg ni Node.js en la máquina del usuario.
- **Concurrencia Controlada (1 a 1)**: Orquestador FIFO estricto. Procesa una única descarga a la vez para evitar bloqueos por tasa de peticiones (rate-limiting) y congestión de disco o ancho de banda, permitiendo encolar nuevas URLs en cualquier momento.
- **Regla de 5 Segundos**: Una vez finalizada una descarga con éxito, la tarjeta permanece 5 segundos en pantalla con accesos directos para *Abrir archivo* y *Abrir carpeta* antes de retirarse automáticamente e iniciar la siguiente tarea.
- **Soporte Bilingüe en Caliente**: Interfaz disponible en **Español** e **Inglés**, intercambiable dinámicamente sin reiniciar la aplicación ni interrumpir la cola.
- **Temas Claro y Oscuro**: Paleta de colores "viento japonés" con acentos menta `#79D6B4` y verde esmeralda `#168569`.
- **Adaptabilidad de Pantalla**: Geometría fija calculada sobre el espacio de pantalla disponible (`QScreen.availableGeometry()`), con margen de seguridad perimetral de 32 px y modo compacto con pestañas en resoluciones reducidas (menores a 880×640 px).
- **Manejo Robusto de Nombres de Archivo**: Sanitización estricta para sistemas de archivos Windows/Linux, protección contra dispositivos reservados (`CON`, `PRN`, `AUX`, `NUL`), eliminación de secuencias de escape y resolución automática de colisiones (`nombre (2).ext`).
- **Descargas Atómicas con Staging**: Cada descarga se procesa en una carpeta de aislamiento temporal y se valida con `ffprobe` antes de trasladarla al destino final. Si una descarga se interrumpe o cancela, se limpia el área de trabajo sin dejar archivos huérfanos incompletos.
- **Persistencia Segura**: Guardado atómico de la cola y la configuración mediante escritura temporal y reemplazo directo (`os.replace`), con recuperación ante fallos y copias de respaldo `.broken`.
- **Diálogo de Diagnóstico**: Verificación en tiempo real del estado de los binarios auxiliares (FFmpeg, FFprobe, motor JS) y aviso de uso responsable.

---

## 📐 Arquitectura del Proyecto

El código fuente sigue el principio de separación de responsabilidades y bajo acoplamiento:

```text
mintplay/
├── bin/                                # Binarios embebidos autónomos
│   ├── ffmpeg.exe                      # Remuxing y transcodificación de vídeo/audio
│   ├── ffprobe.exe                     # Inspección de contenedores y flujos
│   └── node.exe                        # Runtime JS autónomo para scripts de YouTube
├── packaging/                          # Automatización de empaquetado y distribución
│   ├── MintPlay.spec                   # Especificación de PyInstaller
│   ├── build_windows.ps1               # Generador del ZIP portable de Windows
│   ├── build_linux.sh                  # Generador del paquete tar.gz para Linux
│   └── smoke_test.md                   # Guía de verificación en entorno limpio
├── src/mintplay/                       # Código fuente de la aplicación
│   ├── domain/                         # Capa de Dominio (pura, sin dependencias de GUI)
│   │   ├── models.py                   # Entidades (TrabajoDescarga, OpcionesDescarga, Enums)
│   │   ├── states.py                   # Máquina de estados finitos y transiciones
│   │   └── format_policy.py            # Reglas de compatibilidad y selectores yt-dlp
│   ├── services/                       # Capa de Servicios y Lógica de Negocio
│   │   ├── download_service.py         # Motor de descarga con yt-dlp y staging
│   │   ├── queue_manager.py            # Orquestador FIFO en hilo de fondo (QThread)
│   │   ├── media_probe.py              # Validación e inspección técnica con ffprobe
│   │   ├── diagnostics.py              # Comprobación de herramientas y versiones
│   │   ├── output_paths.py             # Sanitización, colisiones y rutas de salida
│   │   ├── persistence.py              # Almacenamiento atómico en APPDATA
│   │   └── runtime_paths.py            # Resolución dinámica de rutas dev/portable
│   ├── ui/                             # Capa de Presentación (PySide6 / Qt)
│   │   ├── main_window.py              # Ventana principal y gestión de pantalla
│   │   ├── download_form.py            # Formulario de entrada y selectores dependientes
│   │   ├── queue_panel.py              # Panel de lista de tarjetas y scroll
│   │   ├── job_card.py                 # Componente de tarjeta de trabajo con estados
│   │   ├── settings_dialog.py          # Modal de configuración y diagnóstico
│   │   ├── i18n_manager.py             # Gestor reactivo de traducciones
│   │   └── theme.py                    # Generador de hojas de estilo QSS
│   ├── assets/icons/                   # Recursos visuales (SVG, PNG, ICO)
│   ├── i18n/                           # Catálogos de cadenas (es.json, en.json)
│   └── __main__.py                     # Punto de entrada de la aplicación
├── tests/                              # Suite de pruebas automatizadas con pytest
│   ├── conftest.py                     # Fixture compartida de QApplication
│   ├── test_states.py                  # Pruebas de la máquina de estados
│   ├── test_format_policy.py           # Pruebas de selectores y compatibilidad
│   ├── test_output_paths.py            # Pruebas de sanitización y colisiones
│   ├── test_persistence.py             # Pruebas de persistencia atómica y tolerancia a fallos
│   ├── test_queue_integration.py       # Pruebas de cola FIFO y concurrencia 1
│   ├── test_download_service.py        # Pruebas del motor yt-dlp y cancelación
│   └── test_ui.py                      # Pruebas de componentes de interfaz y traducción
├── pyproject.toml                      # Metadatos del paquete y configuración de herramientas
├── requirements-lock.txt               # Versiones exactas probadas de dependencias
├── LICENSE                             # Licencia MIT del proyecto
└── README.md                           # Documentación principal en español
```

---

## 🎛️ Matriz de Formatos y Calidades

MintPlay valida en tiempo real las combinaciones de formatos y calidades ofrecidas:

| Tipo | Formato | Opciones de Calidad | Comportamiento del Motor |
| :--- | :--- | :--- | :--- |
| **Vídeo** | **MP4** | Mejor calidad, 1080p, 720p, 480p | Prioriza vídeo H.264 (`avc1`) y audio AAC (`m4a`). Si el origen solo ofrece VP9/AV1, transcodifica de forma transparente a H.264 para garantizar compatibilidad con reproductores de Windows. |
| **Vídeo** | **MKV** | Mejor calidad, 1080p, 720p, 480p | Remuxing directo del mejor flujo de vídeo y audio sin pérdida por recodificación. |
| **Vídeo** | **WEBM** | Mejor calidad, 1080p, 720p, 480p | Prioriza flujos nativos VP9/Opus en contenedor WebM. |
| **Audio** | **MP3** | 320 kbps, 256 kbps, 192 kbps, 128 kbps | Extracción y codificación a bitrate constante/variable mediante FFmpeg con `libmp3lame`. |
| **Audio** | **M4A** | Calidad original | Extracción directa del flujo AAC nativo sin recodificar. |
| **Audio** | **FLAC** | Sin pérdida (Lossless) | Conversión a compresión sin pérdida FLAC de alta fidelidad. |
| **Audio** | **WAV** | Sin pérdida (PCM) | Extracción de audio PCM no comprimido. |

---

## 🚀 Instalación y Ejecución en Desarrollo

### Requisitos Previos
- Python 3.10 o superior (probado exhaustivamente en Python 3.14).
- Sistema Operativo: Windows 10/11 o Linux x64.

### 1. Clonar el repositorio y preparar el entorno virtual
```bash
git clone <url-del-repositorio> mintplay
cd mintplay

# Crear el entorno virtual
python -m venv venv

# Activar el entorno virtual
# En Windows PowerShell:
.\venv\Scripts\Activate.ps1
# En Linux:
source venv/bin/activate
```

### 2. Instalar dependencias
```bash
pip install -r requirements-lock.txt
```

### 3. Ejecutar la aplicación
```bash
python -m src.mintplay
# o con el paquete en PYTHONPATH:
python -m mintplay
```

---

## 🧪 Ejecución de Pruebas Automatizadas

MintPlay cuenta con una suite integral de 32 pruebas que cubren lógica de dominio, políticas de formato, seguridad en rutas, persistencia atómica, concurrencia en cola, componentes visuales e integración del motor de descargas:

```bash
# Ejecutar toda la suite con pytest
.\venv\Scripts\python.exe -m pytest -v
```

---

## 📦 Construcción del Paquete Portable

MintPlay ofrece scripts de compilación automatizados que empaquetan la aplicación en modo directorio (`onedir`), incluyen los binarios requeridos (`bin/ffmpeg.exe`, `bin/ffprobe.exe`, `bin/node.exe`) y generan el archivo comprimido final listo para ser distribuido.

### Construir para Windows:
Abre PowerShell y ejecuta:
```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_windows.ps1
```
El script generará el archivo:
```text
dist/MintPlay-windows-x64-v1.0.0.zip
```

### Construir para Linux:
En una terminal bash:
```bash
bash packaging/build_linux.sh
```
El script generará:
```text
dist/MintPlay-linux-x64-v1.0.0.tar.gz
```

Para una verificación paso a paso en una máquina limpia sin software instalado, consulta la [Guía de Smoke Test](file:///C:/WorkSpace/mintplay/packaging/smoke_test.md).

---

## 📖 Guía de Uso Rápido

1. **Añadir una descarga**:
   - Pega la URL del vídeo o audio en el campo superior. La aplicación identificará automáticamente la plataforma orientativa.
   - Si lo deseas, introduce un **Nombre personalizado** (el sistema sanitizará automáticamente cualquier carácter especial no admitido).
   - Selecciona el **Tipo** (Vídeo o Audio). El selector de formato y calidad se actualizará para ofrecer solo opciones válidas.
   - Selecciona la **Carpeta de destino** deseada (por defecto tu carpeta personal de Descargas).
   - Haz clic en **Añadir a la cola** (o presiona Enter). El formulario se restablecerá de inmediato permitiéndote ingresar el siguiente enlace.

2. **Seguimiento del progreso**:
   - La tarea se añadirá al panel derecho en estado *En espera*.
   - El motor iniciará la descarga en estricto orden de llegada (FIFO).
   - Durante la descarga verás el progreso porcentual, tamaño transferido, velocidad en tiempo real y tiempo estimado restante (ETA).
   - Al finalizar, la tarjeta mostrará un indicador de éxito durante 5 segundos con accesos directos para abrir el archivo o abrir la carpeta contenedora.

3. **Configuración y Diagnóstico**:
   - Pulsa el botón del engranaje en la cabecera para abrir los ajustes.
   - Puedes cambiar el idioma entre Español e Inglés al instante.
   - Puedes alternar entre Tema Claro y Oscuro.
   - El panel de diagnóstico te indicará si las herramientas auxiliares se encuentran operativas.

---

## ⚖️ Aviso Legal y Uso Responsable

MintPlay ha sido concebida como una herramienta técnica para la gestión de medios personales, creación de copias de seguridad de contenido propio y acceso a material publicado bajo licencias libres (Creative Commons, Dominio Público) o con autorización explícita de sus legítimos titulares.

El usuario es el único responsable del uso que haga de este software, debiendo cumplir en todo momento con las condiciones de servicio de las plataformas visitadas y la legislación de propiedad intelectual aplicable en su jurisdicción.
