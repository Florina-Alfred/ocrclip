#!/usr/bin/env python3
"""Simple preflight diagnostic for OCRClip.

Exit code 0 if basic environment looks usable, non-zero otherwise.

This is intended to be a quick local check (and usable in CI) to report
availability of key runtime pieces: PySide6, mss, platform helpers (grim/maim),
and easyocr. It prints JSON-like output to stdout.
"""

from __future__ import annotations

import json
import shutil
import sys
import importlib


def which(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def check_module(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


def main() -> int:
    checks = {
        "pyside6": check_module("PySide6"),
        "mss": check_module("mss"),
        "pillow": check_module("PIL"),
        "easyocr": check_module("easyocr"),
        "pynput": check_module("pynput"),
        "grim": which("grim"),
        "maim": which("maim"),
        "screencapture": which("screencapture"),
        "import": which("import"),
    }

    print(json.dumps(checks, indent=2))

    # Consider success when PySide6 is present and at least one capture backend
    # is available (mss or one of the CLI tools)
    capture_ok = (
        checks["mss"]
        or checks["grim"]
        or checks["maim"]
        or checks["screencapture"]
        or checks["import"]
    )
    ok = checks["pyside6"] and capture_ok
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
