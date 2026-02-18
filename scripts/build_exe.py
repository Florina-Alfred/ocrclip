#!/usr/bin/env python3
"""Build helper for creating executables with PyInstaller.

This script runs PyInstaller with recommended options for PySide6-based GUI
apps and collects common runtime data files. It is a lightweight helper that
wraps the `pyinstaller` invocation and provides a few convenience flags.

Example:
  python3 scripts/build_exe.py --onefile --name ocrclip --include-easyocr

Notes:
- For large dependencies like torch/easyocr prefer to build on a machine with
  enough disk space and memory. Consider excluding torch from the single-file
  build and shipping it separately if packaging fails.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from typing import List


def find_pyinstaller() -> List[str]:
    """Return command prefix to run PyInstaller (sys.executable -m PyInstaller).

    Using `python -m PyInstaller` is more reliable than calling the `pyinstaller`
    binary directly because it runs from the active Python interpreter.
    """
    return [sys.executable, "-m", "PyInstaller"]


def build_command(args: argparse.Namespace) -> List[str]:
    cmd = find_pyinstaller()
    cmd += ["--noconfirm", f"--name={args.name}"]
    cmd += ["--onefile"] if args.onefile else ["--onedir"]
    cmd += ["--windowed"] if args.windowed else ["--console"]

    # Collect common data for Qt and imaging libraries
    cmd += ["--collect-all", "PySide6"]
    cmd += ["--collect-all", "mss"]
    cmd += ["--collect-all", "PIL"]

    if args.include_easyocr:
        cmd += ["--collect-all", "easyocr"]
        logging.warning(
            "Including easyocr in the bundle may produce a very large binary"
        )
    if args.include_torch:
        cmd += ["--collect-all", "torch"]
        logging.warning(
            "Including torch in the bundle is resource heavy; prefer system install"
        )

    if args.clean:
        cmd.append("--clean")

    if args.distpath:
        cmd.append(f"--distpath={args.distpath}")
    if args.workpath:
        cmd.append(f"--workpath={args.workpath}")
    if args.specpath:
        cmd.append(f"--specpath={args.specpath}")

    if args.noupdate:
        cmd.append("--noupx")

    if args.extra_args:
        # allow passing arbitrary extra args as a string
        cmd += args.extra_args.split()

    cmd.append("src/main.py")
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(prog="build_exe.py")
    parser.add_argument("--name", default="ocrclip", help="Name for the built binary")
    parser.add_argument(
        "--onefile", action="store_true", default=True, help="Create one-file bundle"
    )
    parser.add_argument(
        "--windowed", action="store_true", default=True, help="Windowed (no console)"
    )
    parser.add_argument(
        "--include-easyocr", action="store_true", help="Collect easyocr into the bundle"
    )
    parser.add_argument(
        "--include-torch", action="store_true", help="Collect torch into the bundle"
    )
    parser.add_argument(
        "--clean", action="store_true", help="Run PyInstaller with --clean"
    )
    parser.add_argument(
        "--noupx",
        dest="noupdate",
        action="store_true",
        help="Disable UPX compression (useful if UPX not installed)",
    )
    parser.add_argument("--distpath", help="PyInstaller --distpath")
    parser.add_argument("--workpath", help="PyInstaller --workpath")
    parser.add_argument("--specpath", help="PyInstaller --specpath")
    parser.add_argument(
        "--extra-args",
        dest="extra_args",
        help="Extra args passed to pyinstaller",
        default="",
    )

    args = parser.parse_args()

    # Basic checks
    try:
        import PyInstaller  # type: ignore
    except Exception:
        if shutil.which("pyinstaller") is None:
            logging.error(
                "PyInstaller not found. Install with `pip install pyinstaller` or use the pyproject dev extras."
            )
            return 2

    cmd = build_command(args)
    logging.info("Running PyInstaller: %s", " ".join(cmd))
    result = subprocess.run(cmd)
    return result.returncode


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s"
    )
    raise SystemExit(main())
