# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec tuned for PySide6 applications.

This spec file attempts to collect PySide6 plugins and runtime data that are
commonly required for Qt applications (platform plugins, image formats, etc.).
If you need to customize the build (onefile vs onedir, UPX, additional
modules), edit this file or pass a different spec to PyInstaller.
"""
import os

try:
    from PyInstaller.utils.hooks import collect_submodules, collect_data_files, Tree
except Exception:
    # When run inside PyInstaller these helpers are available; if not, fall
    # back to minimal behavior — PyInstaller will still process the spec.
    def collect_submodules(pkg):
        return []

    def collect_data_files(pkg):
        return []

    def Tree(path, prefix=None):
        return []


hiddenimports = []
datas = []

try:
    hiddenimports += collect_submodules("PySide6")
    datas += collect_data_files("PySide6")
except Exception:
    pass

try:
    datas += collect_data_files("PIL")
except Exception:
    pass

try:
    datas += collect_data_files("mss")
except Exception:
    pass

# Include Qt plugins (platforms, imageformats, styles) when available
try:
    import PySide6.QtCore as QtCore

    qt_plugins_dir = os.path.join(os.path.dirname(QtCore.__file__), "plugins")
    if os.path.isdir(qt_plugins_dir):
        datas += Tree(qt_plugins_dir, prefix=os.path.join("PySide6", "plugins"))
except Exception:
    pass


block_cipher = None


a = Analysis([
    "src/main.py",
],
    pathex=[os.path.abspath(".")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ocrclip",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="ocrclip",
)
