"""Runtime hook for PyInstaller-built Qt apps.

This runtime hook adjusts the QT_PLUGIN_PATH or QCoreApplication library
paths to ensure bundled PySide6 plugins are found at runtime when the app is
extracted from a PyInstaller bundle.
"""

import os
import sys


def _add_qt_plugin_path():
    # When PyInstaller bundles the app, plugins are usually placed under
    # sys._MEIPASS / 'PySide6' / 'plugins'
    try:
        meipass = getattr(sys, "_MEIPASS", None)
        if not meipass:
            return
        plugin_dir = os.path.join(meipass, "PySide6", "plugins")
        if os.path.isdir(plugin_dir):
            # Prepend plugin dir so it takes precedence
            os.environ.setdefault(
                "QT_PLUGIN_PATH",
                plugin_dir + os.pathsep + os.environ.get("QT_PLUGIN_PATH", ""),
            )
    except Exception:
        pass


_add_qt_plugin_path()
