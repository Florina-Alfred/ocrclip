"""PyInstaller hook to collect xcb related libraries on Linux.

Many PySide6 applications on Linux need xcb and its plugins (xcb-glx, xcb-icccm,
etc.) which are provided by system packages. This hook attempts to locate
common xcb libraries and include them in the binary distribution's `lib`
directory so the bundled app can run on systems missing those exact versions.
"""

import os
import glob
import shutil
from PyInstaller.utils.hooks import collect_dynamic_libs


def hook(hook_api):
    # Try to collect dynamic libs for Qt / xcb
    libs = []
    try:
        libs += collect_dynamic_libs("PySide6")
    except Exception:
        pass

    # Common xcb-related libs
    candidates = [
        "/usr/lib/x86_64-linux-gnu/libxcb.so*",
        "/usr/lib/libxcb.so*",
        "/usr/lib64/libxcb.so*",
        "/usr/lib/x86_64-linux-gnu/libxcb-*.so*",
    ]
    for pat in candidates:
        for path in glob.glob(pat):
            if os.path.isfile(path):
                libs.append((path, os.path.join("lib", os.path.basename(path))))

    for src, dest in libs:
        hook_api.add_binaries((src, dest))
