#!/usr/bin/env python3
"""Debug helper: capture a screen region and write it to /tmp for inspection.

Usage:
  ./scripts/debug_capture.py LEFT TOP WIDTH HEIGHT
  ./scripts/debug_capture.py           # will try to auto-center a small region

This script uses the same `capture.capture_region` function as the app so
it helps verify which backend is active and whether captures return valid
PNG bytes on your system.
"""

import sys
import os

from PIL import Image

try:
    from src import capture
except Exception as e:
    print("Failed to import capture module:", e, file=sys.stderr)
    raise


def auto_center_region():
    # Try Qt first (if running in a graphical session)
    try:
        from PySide6 import QtWidgets, QtGui

        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        screen = QtGui.QGuiApplication.primaryScreen()
        geom = screen.geometry()
        w = min(400, geom.width())
        h = min(300, geom.height())
        left = geom.left() + (geom.width() - w) // 2
        top = geom.top() + (geom.height() - h) // 2
        return left, top, w, h
    except Exception:
        pass

    # Fallback to mss if available
    try:
        import mss

        with mss.mss() as sct:
            mon = sct.monitors[0]
            w = min(400, mon["width"])
            h = min(300, mon["height"])
            left = mon["left"] + (mon["width"] - w) // 2
            top = mon["top"] + (mon["height"] - h) // 2
            return left, top, w, h
    except Exception:
        pass

    raise RuntimeError("Could not determine screen geometry; please pass coordinates")


def main():
    if len(sys.argv) >= 5:
        left = int(sys.argv[1])
        top = int(sys.argv[2])
        width = int(sys.argv[3])
        height = int(sys.argv[4])
    else:
        left, top, width, height = auto_center_region()

    print(f"Capturing region: left={left} top={top} width={width} height={height}")
    try:
        data = capture.capture_region(left, top, width, height)
    except Exception as e:
        print("capture_region raised:", e, file=sys.stderr)
        raise

    out = "/tmp/ocrclip_debug_capture.png"
    with open(out, "wb") as fh:
        fh.write(data)
    print("Wrote:", out, "size:", os.path.getsize(out))


if __name__ == "__main__":
    main()
