"""Runtime hook to ensure bundled 'lib' directory is on the dynamic loader path.

This hook is intended to be bundled into PyInstaller builds and run early in
process startup. It will prepend a bundled `lib` directory (if present) to
LD_LIBRARY_PATH (Linux) or DYLD_LIBRARY_PATH (macOS) so shared libraries copied
into that folder can be found at runtime.
"""

import os
import sys


def _add_lib_path():
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        libdir = os.path.join(meipass, "lib")
        if os.path.isdir(libdir):
            if sys.platform == "darwin":
                env_key = "DYLD_LIBRARY_PATH"
            else:
                env_key = "LD_LIBRARY_PATH"
            os.environ[env_key] = libdir + os.pathsep + os.environ.get(env_key, "")
            # also add to PATH on Windows when running under Wine
            os.environ["PATH"] = libdir + os.pathsep + os.environ.get("PATH", "")


_add_lib_path()
