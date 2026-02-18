"""Hook to ensure VC runtime manifest and MSVC dependencies are collected.

Windows builds often fail at runtime because the target system doesn't have
the correct Visual C++ redistributable. This hook attempts to gather the
relevant MSVC runtime DLLs into the bundled `lib` directory when available.
"""

import os
import glob
from PyInstaller.utils.hooks import add_data_file


def hook(hook_api):
    # Look for common MSVC runtime DLL patterns in system directories
    candidates = [
        os.path.join(
            os.environ.get("SystemRoot", "C:\\Windows"), "System32", "vcruntime*.dll"
        ),
        os.path.join(
            os.environ.get("SystemRoot", "C:\\Windows"), "System32", "msvcp*.dll"
        ),
    ]
    for pat in candidates:
        for path in glob.glob(pat):
            if os.path.isfile(path):
                hook_api.add_binaries(
                    (path, os.path.join("lib", os.path.basename(path)))
                )
