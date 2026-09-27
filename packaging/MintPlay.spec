# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys
import importlib.util

block_cipher = None
BASE_DIR = Path.cwd()

# Archivos de datos adicionales: traducciones e iconos
datas = [
    (str(BASE_DIR / "src" / "mintplay" / "i18n" / "*.json"), "src/mintplay/i18n"),
    (str(BASE_DIR / "src" / "mintplay" / "assets" / "icons" / "*.*"), "src/mintplay/assets/icons"),
]

# Incluir assets JavaScript de yt-dlp-ejs solver
try:
    spec_ejs = importlib.util.find_spec("yt_dlp_ejs")
    if spec_ejs and spec_ejs.origin:
        dir_ejs = Path(spec_ejs.origin).parent
        datas.append((str(dir_ejs / "yt" / "solver" / "*.js"), "yt_dlp_ejs/yt/solver"))
except Exception:
    pass

# Binarios auxiliares: FFmpeg, FFprobe y runtime Node.js
binaries = [
    (str(BASE_DIR / "bin" / "ffmpeg.exe"), "bin"),
    (str(BASE_DIR / "bin" / "ffprobe.exe"), "bin"),
    (str(BASE_DIR / "bin" / "node.exe"), "bin"),
]

hidden_imports = [
    "yt_dlp",
    "yt_dlp.extractor",
    "yt_dlp.extractor._extractors",
    "yt_dlp.extractor.youtube",
    "yt_dlp.extractor.youtube.jsc",
    "yt_dlp.extractor.youtube.jsc._builtin.ejs",
    "yt_dlp.extractor.youtube.jsc._builtin.node",
    "yt_dlp.utils._jsruntime",
    "yt_dlp_ejs",
    "yt_dlp_ejs.yt",
    "yt_dlp_ejs.yt.solver",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtSvg",
    "mintplay",
    "mintplay.__main__",
]

a = Analysis(
    [str(BASE_DIR / "packaging" / "launcher.py")],
    pathex=[str(BASE_DIR / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "test", "pydoc"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MintPlay",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(BASE_DIR / "src" / "mintplay" / "assets" / "icons" / "app.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MintPlay",
)
