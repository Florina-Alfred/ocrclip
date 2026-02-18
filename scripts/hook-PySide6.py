"""PyInstaller hook for PySide6 with platform-specific additions.

This custom hook is intended to be discovered via PyInstaller's
--additional-hooks-dir or when the spec sets hookspath to include the
`scripts/` directory. It collects PySide6 data and attempts to include
common native libraries that are frequently missing on target systems
(notably libxcb and friends on Debian/Ubuntu and VC runtimes on Windows).
"""

import glob
import os
import sys
from PyInstaller.utils.hooks import (
    collect_submodules,
    collect_data_files,
    collect_dynamic_libs,
    Tree,
)


# Collect Python-side resources
hiddenimports = collect_submodules("PySide6")
datas = collect_data_files("PySide6")
binaries = collect_dynamic_libs("PySide6")


# Include plugin directories (platforms, imageformats, styles)
try:
    import PySide6

    pyside_dir = os.path.dirname(PySide6.__file__)
    plugins_dir = os.path.join(pyside_dir, "plugins")
    if os.path.isdir(plugins_dir):
        for sub in (
            "platforms",
            "imageformats",
            "styles",
            "iconengines",
            "platforminputcontexts",
        ):
            subdir = os.path.join(plugins_dir, sub)
            if os.path.isdir(subdir):
                datas += Tree(subdir, prefix=os.path.join("PySide6", "plugins", sub))
except Exception:
    pass


# Platform specific native libs to include (best-effort)
if sys.platform.startswith("linux"):
    # Debian/Ubuntu common library locations
    patterns = [
        "/usr/lib/x86_64-linux-gnu/libxcb*.so*",
        "/lib/x86_64-linux-gnu/libxcb*.so*",
        "/usr/lib/x86_64-linux-gnu/libX11*.so*",
        "/lib/x86_64-linux-gnu/libX11*.so*",
        "/usr/lib/x86_64-linux-gnu/libxkbcommon*.so*",
        "/usr/lib/x86_64-linux-gnu/libGL*.so*",
        "/usr/lib/x86_64-linux-gnu/libXrandr*.so*",
        "/usr/lib/x86_64-linux-gnu/libXrender*.so*",
        "/usr/lib/x86_64-linux-gnu/libXcursor*.so*",
        "/usr/lib/x86_64-linux-gnu/libXfixes*.so*",
        "/usr/lib/x86_64-linux-gnu/libXext*.so*",
        "/usr/lib/x86_64-linux-gnu/libxcb-*",
        "/usr/lib/libxcb*.so*",
        "/usr/lib64/libxcb*.so*",
    ]
    for pat in patterns:
        for f in glob.glob(pat):
            if os.path.isfile(f):
                # place under lib/ in the distribution
                binaries.append((f, os.path.join("lib", os.path.basename(f))))

if sys.platform.startswith("win"):
    # Windows: include common VC runtime DLLs if available (best-effort)
    system_root = os.environ.get("SystemRoot", r"C:\\Windows")
    candidates = [
        os.path.join(system_root, "System32", "vcruntime*.dll"),
        os.path.join(system_root, "System32", "msvcp*.dll"),
        os.path.join(system_root, "System32", "api-ms-win-crt-*.dll"),
    ]
    for pat in candidates:
        for f in glob.glob(pat):
            if os.path.isfile(f):
                binaries.append((f, os.path.join("lib", os.path.basename(f))))
