# Licencias de Terceros y Componentes Distribuidos

MintPlay incorpora o se apoya en los siguientes proyectos y bibliotecas de código abierto:

---

## 1. FFmpeg y FFprobe
- **Proyecto**: [FFmpeg](https://ffmpeg.org/)
- **Licencia**: GNU General Public License v3.0 (GPLv3) o LGPLv2.1+ según la compilación.
- **Uso en MintPlay**: Se distribuyen binarios precompilados estáticos (`bin/ffmpeg.exe`, `bin/ffprobe.exe`) para remuxing, transcodificación a MP4 y extracción de pistas de audio a MP3/FLAC/WAV/M4A.

---

## 2. yt-dlp
- **Proyecto**: [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- **Licencia**: The Unlicense (Dominio Público).
- **Uso en MintPlay**: Biblioteca central para extracción de metadatos y orquestación de descargas multimedia.

---

## 3. Node.js (Runtime JavaScript Standalone)
- **Proyecto**: [Node.js](https://nodejs.org/)
- **Licencia**: Licencia MIT / Node.js Contributors.
- **Uso en MintPlay**: Motor JavaScript empaquetado en `bin/node.exe` para interpretar los desafíos y scripts dinámicos de extracción de YouTube a través del plugin `yt-dlp-ejs` sin requerir software instalado en la máquina anfitriona.

---

## 4. yt-dlp-ejs
- **Proyecto**: [yt-dlp-ejs](https://github.com/yt-dlp/yt-dlp-ejs)
- **Licencia**: Licencia The Unlicense / MIT.
- **Uso en MintPlay**: Plugin oficial de yt-dlp para ejecución segura de JavaScript de extracción.

---

## 5. PySide6 (Qt para Python)
- **Proyecto**: [Qt / PySide6](https://wiki.qt.io/Qt_for_Python)
- **Licencia**: GNU Lesser General Public License v3 (LGPLv3).
- **Uso en MintPlay**: Marco de trabajo gráfico para la interfaz de usuario de escritorio.

---

## 6. PyInstaller
- **Proyecto**: [PyInstaller](https://pyinstaller.org/)
- **Licencia**: GPLv2 con excepción especial para software empaquetado (permite distribuir aplicaciones comerciales o de código libre sin imponer GPL al código propio).
