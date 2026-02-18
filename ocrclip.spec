# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec tuned for PySide6 applications.

This spec file attempts to collect PySide6 plugins and runtime data that are
commonly required for Qt applications (platform plugins, image formats, etc.).
If you need to customize the build (onefile vs onedir, UPX, additional
modules), edit this file or pass a different spec to PyInstaller.
"""

import os

from PyInstaller.utils.hooks import (
    collect_submodules,
    collect_data_files,
    collect_dynamic_libs,
    Tree,
)

# Collect a broad set of PySide6 internals to avoid missing modules at runtime.
hiddenimports = []
datas = []
binaries = []

try:
    hiddenimports += collect_submodules("PySide6")
    datas += collect_data_files("PySide6")
    binaries += collect_dynamic_libs("PySide6")
except Exception:
    pass

# PIL data and plugins
try:
    datas += collect_data_files("PIL")
except Exception:
    pass

# mss / screenshot helpers
try:
    datas += collect_data_files("mss")
except Exception:
    pass

# Torch/easyocr are optional heavyweight deps; include dynamic libs if present
try:
    binaries += collect_dynamic_libs("torch")
except Exception:
    pass

# Include Qt plugin trees (platforms, imageformats, styles, iconengines, etc.)
try:
    import PySide6.QtCore as QtCore

    qtpkg_dir = os.path.dirname(QtCore.__file__)
    plugins_dir = os.path.join(qtpkg_dir, "plugins")
    if os.path.isdir(plugins_dir):
        # include common plugin subdirs if present
        for sub in ("platforms", "imageformats", "styles", "iconengines", "platforminputcontexts"):
            subdir = os.path.join(plugins_dir, sub)
            if os.path.isdir(subdir):
                datas += Tree(subdir, prefix=os.path.join("PySide6", "plugins", sub))
except Exception:
    pass

# Add runtime hook that ensures bundled Qt plugins are found at runtime
runtime_hooks = []
rthook = os.path.join(os.path.dirname(__file__), "scripts", "pyi_rth_qt.py")
if os.path.exists(rthook):
    runtime_hooks.append(rthook)

block_cipher = None


a = Analysis(
    ["src/main.py"],
    pathex=[os.path.abspath(".")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=runtime_hooks,
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
