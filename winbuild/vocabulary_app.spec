# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller --onedir build spec for Vocabulary App (M20 Release Contract
§ 2.5). Invoke through winbuild/build.py, not directly with `pyinstaller`,
so the produced installer stays tied to a recorded source SHA and hash --
see that script's docstring for the full build chain.

Base distribution exclusions (§ 8.3): only what the desktop entry point
actually imports gets analyzed by PyInstaller's own dependency scan, but
`excludes` is a belt-and-suspenders block against picking up the
Streamlit-only dependency tree (pandas/numpy/pyarrow/altair/... --
requirements.txt, not requirements-desktop.txt) if anything in `src/`
ever imports it indirectly. `datas` bundles only the two Local Windows
Speech Provider PowerShell scripts (src.tts_providers._scripts_dir())
and the application icon -- no Kokoro/sherpa-onnx/Piper assets, no
personal databases, no dev tooling.
"""

from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).resolve().parent
PACKAGING_DIR = PROJECT_ROOT / "winbuild"

APP_NAME = "Vocabulary App"

STREAMLIT_ONLY_EXCLUDES = [
    "streamlit",
    "pandas",
    "numpy",
    "pyarrow",
    "altair",
    "pydeck",
    "watchdog",
    "pymupdf",
    "fitz",
]

a = Analysis(
    [str(PACKAGING_DIR / "desktop_entry.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        (str(PROJECT_ROOT / "assets" / "icons" / "vocabulary_app.ico"), "assets/icons"),
        (str(PROJECT_ROOT / "scripts" / "tts_list_voices.ps1"), "scripts"),
        (str(PROJECT_ROOT / "scripts" / "tts_windows_voice.ps1"), "scripts"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=STREAMLIT_ONLY_EXCLUDES,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
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
    icon=str(PROJECT_ROOT / "assets" / "icons" / "vocabulary_app.ico"),
    version=str(PACKAGING_DIR / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
