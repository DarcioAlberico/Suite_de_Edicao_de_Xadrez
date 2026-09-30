# -*- mode: python ; coding: utf-8 -*-
# A sonda congelada do WebEngine (Editor HTML/CSS, H1, tarefa 3b): o PyQt6 do pacote no
# `_internal\` -- o núcleo que o `Caissa.exe` leva (QtCore, QtGui, QtWidgets) -- e **nada** do
# WebEngine, que vem de `runtime\webengine\` (`sonda_webengine.py --instalar`). O PyMuPDF vai
# junto: sem o componente, a sonda desenha pela reserva.
#
# Construir (o PyInstaller do `.venv-pack`, o mesmo do `build_windows.py`; a saída é ignorada):
#
#     & $PACK -m PyInstaller packaging\sonda_webengine.spec --noconfirm `
#         --distpath build\sonda_webengine\dist --workpath build\sonda_webengine\work
from pathlib import Path

PASTA = Path(SPECPATH)  # noqa: F821 - o PyInstaller define

FORA_DO_PACOTE = [
    # O WebEngine e o Qt que só ele usa: o componente os traz.
    "PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineWidgets", "PyQt6.QtWebEngineQuick",
    "PyQt6.QtWebChannel", "PyQt6.QtNetwork", "PyQt6.QtPrintSupport", "PyQt6.QtQuick",
    "PyQt6.QtQml", "PyQt6.QtQuickWidgets", "PyQt6.QtPositioning", "PyQt6.QtOpenGL",
    # O resto do produto que a sonda não usa.
    "torch", "tkinter", "matplotlib", "cv2", "PIL",
]

a = Analysis(  # noqa: F821 - o PyInstaller define
    [str(PASTA / "sonda_webengine.py")],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=["PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets", "pymupdf", "pefile"],
    hookspath=[],
    runtime_hooks=[],
    excludes=FORA_DO_PACOTE,
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz, a.scripts, [], exclude_binaries=True, name="sonda_webengine", console=True,
    upx=False, strip=False)
coll = COLLECT(  # noqa: F821
    exe, a.binaries, a.datas, strip=False, upx=False, name="sonda_webengine")
