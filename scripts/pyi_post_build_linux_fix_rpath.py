"""Post-build helper to fixup rpaths on Linux for bundled shared libs.

Some Linux distributions require `patchelf` to adjust RPATHs in shared
objects so that they prefer the bundled `lib` directory. This script looks
for `patchelf` and, if present, adjusts binaries under `dist/ocrclip`.
"""

import os
import shutil
import subprocess
import sys


def main(dist_dir: str = "dist/ocrclip") -> int:
    patchelf = shutil.which("patchelf")
    if not patchelf:
        print("patchelf not found; skipping rpath fixup")
        return 0

    # walk .so files and adjust RPATH
    for root, _, files in os.walk(dist_dir):
        for f in files:
            if f.endswith(".so") or f.endswith(":lib"):
                path = os.path.join(root, f)
                try:
                    subprocess.check_call(
                        [patchelf, "--set-rpath", "$ORIGIN/../lib", path]
                    )
                except subprocess.CalledProcessError:
                    print("patchelf failed on", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
