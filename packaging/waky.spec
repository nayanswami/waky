# PyInstaller spec for Waky. Build with: scripts\build_windows.ps1
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

datas = [("../assets", "assets")]
binaries = []
hiddenimports = ["pynput.keyboard._win32", "pynput.mouse._win32", "win32ctypes.core"]

# Packages that ship data files / native libs PyInstaller cannot discover by import alone.
for package in ("faster_whisper", "ctranslate2", "onnxruntime", "tokenizers", "av"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

hiddenimports += collect_submodules("keyring.backends")
for dist in ("keyring", "pywin32-ctypes", "huggingface_hub"):
    try:
        datas += copy_metadata(dist)
    except Exception:
        pass

a = Analysis(
    ["../main.py"],
    pathex=[".."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "pandas", "IPython", "pytest", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore", "PySide6.QtQuick", "PySide6.QtQml"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Waky",
    console=False,  # windowed: no terminal in the taskbar
    icon="../assets/waky.ico",
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Waky", upx=False)
