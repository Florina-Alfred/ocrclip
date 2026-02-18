"""Flexible screen capture backends.

Provides `capture_region(left, top, width, height) -> bytes` which returns PNG
bytes for the requested region. The function tries several backends in order:

- mss (fast, cross-platform)
- Qt `QScreen.grabWindow` (works when a QGuiApplication is present)
- macOS `screencapture` CLI
- Wayland: `grim`
- X11 / miscellaneous: `maim` or ImageMagick `import`

The module avoids hard failures; callers should handle `RuntimeError` to fall
back to alternative strategies or show a helpful message.
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import subprocess
import shutil
import logging
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)

try:
    # mss is optional; prefer it when available
    from mss import mss as _mss_ctx  # type: ignore

    _HAS_MSS = True
except Exception:
    _mss_ctx = None
    _HAS_MSS = False


def _mss_capture(left: int, top: int, width: int, height: int) -> bytes:
    if not _HAS_MSS:
        raise RuntimeError("mss_not_available")
    with _mss_ctx() as sct:
        monitor = {"left": left, "top": top, "width": width, "height": height}
        sct_img = sct.grab(monitor)
        try:
            img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
        except Exception:
            # fallback to buffer variation used by some mss builds
            img = Image.frombuffer("RGB", sct_img.size, sct_img.rgb, "raw", "RGB", 0, 1)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


def _qt_capture(left: int, top: int, width: int, height: int) -> bytes:
    try:
        from PySide6 import QtGui, QtCore

        screen = QtGui.QGuiApplication.primaryScreen()
        if screen is None:
            raise RuntimeError("no_qt_screen")
        pix = screen.grabWindow(0, left, top, width, height)
        buf = QtCore.QBuffer()
        buf.open(QtCore.QBuffer.ReadWrite)
        pix.save(buf, "PNG")
        return bytes(buf.data())
    except Exception as e:
        raise RuntimeError(f"qt_capture_failed: {e}") from e


def _cli_capture(cmd: list[str]) -> bytes:
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp_name = tmp.name
    tmp.close()
    try:
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with open(tmp_name, "rb") as fh:
            data = fh.read()
        return data
    finally:
        try:
            os.unlink(tmp_name)
        except Exception:
            pass


def _macos_capture(left: int, top: int, width: int, height: int) -> bytes:
    screencapture = shutil.which("screencapture")
    if not screencapture:
        raise RuntimeError("screencapture_missing")
    cmd = [screencapture, "-x", "-R", f"{left},{top},{width},{height}", "{out}"]
    # format the last argument later in _cli_capture
    cmd = [screencapture, "-x", "-R", f"{left},{top},{width},{height}", "{out}"]
    # Use _cli_capture with formatted command
    formatted = [
        screencapture,
        "-x",
        "-R",
        f"{left},{top},{width},{height}",
    ]
    # append out file - _cli_capture will add the filename placeholder
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp_name = tmp.name
    tmp.close()
    try:
        call = [screencapture, "-x", "-R", f"{left},{top},{width},{height}", tmp_name]
        subprocess.check_call(
            call, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        with open(tmp_name, "rb") as fh:
            data = fh.read()
        return data
    finally:
        try:
            os.unlink(tmp_name)
        except Exception:
            pass


def _grim_capture(left: int, top: int, width: int, height: int) -> bytes:
    grim = shutil.which("grim")
    if not grim:
        raise RuntimeError("grim_missing")
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp_name = tmp.name
    tmp.close()
    try:
        cmd = [grim, "-g", f"{left},{top} {width}x{height}", tmp_name]
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with open(tmp_name, "rb") as fh:
            data = fh.read()
        return data
    finally:
        try:
            os.unlink(tmp_name)
        except Exception:
            pass


def _maim_capture(left: int, top: int, width: int, height: int) -> bytes:
    maim = shutil.which("maim")
    if not maim:
        raise RuntimeError("maim_missing")
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp_name = tmp.name
    tmp.close()
    try:
        # maim expects geometry as WxH+X+Y
        geom = f"{width}x{height}+{left}+{top}"
        cmd = [maim, "-g", geom, tmp_name]
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with open(tmp_name, "rb") as fh:
            data = fh.read()
        return data
    finally:
        try:
            os.unlink(tmp_name)
        except Exception:
            pass


def _import_capture(left: int, top: int, width: int, height: int) -> bytes:
    # ImageMagick `import` fallback
    imp = shutil.which("import")
    if not imp:
        raise RuntimeError("import_missing")
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp_name = tmp.name
    tmp.close()
    try:
        geom = f"{width}x{height}+{left}+{top}"
        cmd = [imp, "-window", "root", "-crop", geom, tmp_name]
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with open(tmp_name, "rb") as fh:
            data = fh.read()
        return data
    finally:
        try:
            os.unlink(tmp_name)
        except Exception:
            pass


def capture_region(left: int, top: int, width: int, height: int) -> bytes:
    """Try several capture backends and return PNG bytes.

    Raises RuntimeError if no backend succeeds.
    """
    errors: list[str] = []

    # 1) try mss
    try:
        if _HAS_MSS:
            return _mss_capture(left, top, width, height)
    except Exception as e:
        logger.debug("mss capture failed: %s", e)
        errors.append(f"mss: {e}")

    # 2) try Qt capture (requires a running QGuiApplication)
    try:
        return _qt_capture(left, top, width, height)
    except Exception as e:
        logger.debug("qt capture failed: %s", e)
        errors.append(f"qt: {e}")

    # 3) platform CLI fallbacks
    if sys.platform == "darwin":
        try:
            return _macos_capture(left, top, width, height)
        except Exception as e:
            logger.debug("macos capture failed: %s", e)
            errors.append(f"macos: {e}")

    # 4) Wayland / grim
    try:
        return _grim_capture(left, top, width, height)
    except Exception as e:
        logger.debug("grim capture failed: %s", e)
        errors.append(f"grim: {e}")

    # 5) maim
    try:
        return _maim_capture(left, top, width, height)
    except Exception as e:
        logger.debug("maim capture failed: %s", e)
        errors.append(f"maim: {e}")

    # 6) ImageMagick import
    try:
        return _import_capture(left, top, width, height)
    except Exception as e:
        logger.debug("import capture failed: %s", e)
        errors.append(f"import: {e}")

    raise RuntimeError("no_suitable_screencapture_backend: " + ", ".join(errors))
