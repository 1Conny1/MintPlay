# Guía de Prueba Rápida (Smoke Test) para MintPlay Portable

Esta guía detalla los pasos para verificar que la distribución portable de **MintPlay** es completamente autocontenida y funcional en un sistema Windows x64 limpio sin Python, FFmpeg ni Node.js instalados de antemano.

---

## 1. Requisitos Previos para el Entorno de Prueba
- Sistema Operativo: Windows 10 o Windows 11 (64 bits).
- No se requiere tener instalado Python.
- No se requiere tener FFmpeg ni FFprobe en las variables de entorno del sistema (`PATH`).
- No se requiere tener instalado Node.js por separado.
- Conexión activa a Internet (para descargar medios).

---

## 2. Preparación
1. Localiza el archivo empaquetado:
   ```text
   dist/MintPlay-windows-x64-v1.0.0.zip
   ```
2. Descomprime el archivo ZIP en una carpeta de tu preferencia (por ejemplo, en el Escritorio o en `C:\Pruebas\MintPlay`).
3. Comprueba la estructura descomprimida:
   - `MintPlay.exe` (ejecutable principal)
   - `bin/` conteniendo `ffmpeg.exe`, `ffprobe.exe` y `node.exe`
   - `LICENSE` y `LICENSES/`
   - Archivos de soporte de Qt y Python.

---

## 3. Ejecución y Verificación de Arranque
1. Haz **doble clic** en `MintPlay.exe`.
2. Verifica que:
   - No aparece ninguna ventana de consola negra (modo ventana puro).
   - Se abre la ventana principal de MintPlay con su icono de hoja menta.
   - El tamaño de la ventana es fijo y armonioso con tu pantalla (margen de 32 px en bordes).
   - El formulario de descarga se muestra a la izquierda y el panel de cola (vacío con ilustración/texto) a la derecha.

---

## 4. Verificación de Diagnóstico
1. Haz clic en el botón de ajustes (icono de engranaje ⚙ en la esquina superior derecha).
2. Revisa la sección **Diagnóstico de herramientas**:
   - `FFmpeg`: debe mostrar versión detectada en verde (✓).
   - `FFprobe`: debe mostrar versión detectada en verde (✓).
   - `Motor JavaScript (Node.js)`: debe mostrar versión detectada en verde (✓).
3. Cierra el diálogo de ajustes.

---

## 5. Prueba de Descarga de Vídeo (MP4)
1. Pega la siguiente URL pública de demostración en el campo de texto:
   ```text
   https://www.w3schools.com/html/mov_bbb.mp4
   ```
2. Observa cómo la etiqueta superior detecta orientativamente el origen.
3. Deja el selector en **Vídeo**, formato **MP4** y calidad **Mejor calidad disponible**.
4. En nombre personalizado escribe opcionalmente: `Prueba Video BBB`.
5. Haz clic en **Añadir a la cola**.
6. Observa la tarjeta en la columna derecha:
   - Estado inicial: "En espera" / "Preparando".
   - Progreso visual de porcentaje y métricas (velocidad, bytes descargados).
   - Cambio a "Procesando" y "Verificando".
   - Al finalizar con éxito, aparece la marca verde `✓ Completado` con los botones "Abrir archivo" y "Abrir carpeta".
7. Comprueba la regla de los 5 segundos:
   - Durante 5 segundos la tarjeta completada permanece accesible para que puedas abrir el archivo.
   - Tras 5 segundos, la tarjeta se retira limpiamente de la cola.
8. Verifica que en tu carpeta de Descargas (o la configurada) existe el archivo `Prueba Video BBB.mp4` y que se reproduce correctamente.

---

## 6. Prueba de Extracción de Audio (MP3)
1. Pega nuevamente la URL:
   ```text
   https://www.w3schools.com/html/mov_bbb.mp4
   ```
2. Cambia el selector a **Audio**.
3. Selecciona formato **MP3** y calidad **320 kbps**.
4. Haz clic en **Añadir a la cola**.
5. Observa el flujo de descarga, extracción con FFmpeg y verificación.
6. Comprueba que el archivo `.mp3` generado se reproduce con sonido claro en el reproductor predeterminado del sistema.

---

## 7. Prueba de Cancelación Inmediata
1. Añade una descarga y, mientras esté descargando, pulsa el botón **Cancelar**.
2. Verifica que la descarga se interrumpe de inmediato, no deja archivos temporales residuales en staging y pasa inmediatamente a la siguiente tarea si hubiera alguna en cola.
