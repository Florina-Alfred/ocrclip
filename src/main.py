import sys
import argparse
import threading
import logging
import faulthandler
import signal
import os
import tempfile
import atexit
import shutil
import subprocess
import time
import importlib

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except Exception as e:
    sys.stderr.write(
        "Missing dependency PySide6 (Qt).\n"
        "Please install runtime deps into the project venv and re-run.\n"
        "Recommended (uv-managed):\n  uv .venv --activate --install\n"
        "Then run: uv run -- python -m src.main\n"
    )
    raise

try:
    from PIL import Image
except Exception:
    sys.stderr.write(
        "Missing dependency Pillow. Install via uv-managed venv: uv .venv --activate --install\n"
    )
    raise

try:
    import numpy as np
except Exception:
    sys.stderr.write(
        "Missing dependency numpy. Install via uv-managed venv: uv .venv --activate --install\n"
    )
    raise

import io
from typing import Optional

# capture backend (tries multiple strategies)
try:
    # when run as a module (python -m src.main)
    from . import capture
except Exception:
    try:
        # fallback: import as package module
        import src.capture as capture  # type: ignore
    except Exception:
        capture = None


def _ensure_capture_module():
    """Attempt to (re)import the capture module if it's not present.

    This helps in situations where an early import failed (transient env or
    dependency issues) but the module becomes available later.
    """
    global capture
    if capture is not None:
        # Try to reload an existing module so that optional-backend flags
        # (like `_HAS_MSS`) are recomputed if dependencies were installed
        # after the initial import.
        try:
            importlib.reload(capture)  # type: ignore
        except Exception:
            logging.debug(
                "capture.reload failed; keeping existing module", exc_info=True
            )
        return capture
    try:
        from . import capture as _cap

        capture = _cap
        return capture
    except Exception:
        try:
            import src.capture as _cap

            capture = _cap
            return capture
        except Exception:
            capture = None
            return None


# Logging and crash handlers (robust across OSes)
LOG_PATH = os.environ.get(
    "OCRCLIP_LOG", os.path.join(tempfile.gettempdir(), "ocrclip.log")
)
_log_fh = None
try:
    _log_fh = open(LOG_PATH, "a")
except Exception:
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(levelname)s: %(message)s"
    )
    logging.warning("Could not open log file %s, falling back to stderr", LOG_PATH)
else:
    logging.basicConfig(
        stream=_log_fh,
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s: %(message)s",
    )
    try:
        faulthandler.enable(file=_log_fh)
    except Exception:
        logging.exception("faulthandler.enable failed")
    try:
        faulthandler.register(signal.SIGABRT, file=_log_fh, all_threads=True)
    except Exception:
        logging.exception("faulthandler.register failed")
    atexit.register(lambda: _log_fh.close())

logging.debug("Starting OCRClip")

try:
    import easyocr
except Exception:
    easyocr = None
logging.debug(f"easyocr available: {easyocr is not None}")


class SnipOverlay(QtWidgets.QWidget):
    # snipped emits PNG bytes (bytes) or None on error
    snipped = QtCore.Signal(object)

    def __init__(self):
        super().__init__(
            None,
            QtCore.Qt.Window
            | QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint,
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setWindowState(self.windowState() | QtCore.Qt.WindowFullScreen)
        # Use explicit None checks (QPoint(0,0) is falsy in some bindings)
        self.begin: Optional[QtCore.QPoint] = None
        self.end: Optional[QtCore.QPoint] = None
        self.rubberBand = QtWidgets.QRubberBand(QtWidgets.QRubberBand.Rectangle, self)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        # Use position() (QPointF) to avoid Qt6 deprecation of pos()
        try:
            self.begin = event.position().toPoint()
        except Exception:
            self.begin = event.pos()
        self.rubberBand.setGeometry(QtCore.QRect(self.begin, QtCore.QSize()))
        self.rubberBand.show()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if self.begin is None:
            return
        try:
            self.end = event.position().toPoint()
        except Exception:
            self.end = event.pos()
        rect = QtCore.QRect(self.begin, self.end).normalized()
        self.rubberBand.setGeometry(rect)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        # Explicit None checks to allow selections that include (0,0)
        if self.begin is None or self.end is None:
            self.close()
            return
        rect = QtCore.QRect(self.begin, self.end).normalized()
        self.rubberBand.hide()
        self.grab_region(rect)
        self.close()

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        # allow user to cancel with Escape
        if event.key() == QtCore.Qt.Key_Escape:
            self.rubberBand.hide()
            self.close()
        else:
            super().keyPressEvent(event)

    def grab_region(self, rect: QtCore.QRect):
        # Convert Qt rect to screen coordinates
        logging.debug(
            "grab_region: rect=%d,%d %dx%d",
            rect.left(),
            rect.top(),
            rect.width(),
            rect.height(),
        )
        geo = self.geometry()
        logging.debug(
            "overlay geometry=%d,%d %dx%d",
            geo.left(),
            geo.top(),
            geo.width(),
            geo.height(),
        )
        # Hide overlay before capturing so we don't capture our overlay.
        # Use a short delayed capture (singleShot) to allow the compositor
        # to update and avoid self-capture on flaky systems.
        try:
            self.hide()
        except Exception:
            pass

        left = geo.left() + rect.left()
        top = geo.top() + rect.top()
        width = rect.width()
        height = rect.height()

        # Attempt to account for HiDPI / devicePixelRatio differences.
        try:
            center_point = QtCore.QPoint(left + width // 2, top + height // 2)
            screen_obj = QtGui.QGuiApplication.screenAt(center_point)
            if screen_obj is None:
                screen_obj = QtGui.QGuiApplication.primaryScreen()
            try:
                pixel_ratio = float(screen_obj.devicePixelRatioF())
            except Exception:
                try:
                    pixel_ratio = float(screen_obj.devicePixelRatio())
                except Exception:
                    pixel_ratio = 1.0
            if pixel_ratio <= 0:
                pixel_ratio = 1.0
        except Exception:
            pixel_ratio = 1.0

        if pixel_ratio != 1.0:
            logging.debug("Applying devicePixelRatio scaling: %s", pixel_ratio)

        scaled_left = int(left * pixel_ratio)
        scaled_top = int(top * pixel_ratio)
        scaled_width = int(width * pixel_ratio)
        scaled_height = int(height * pixel_ratio)

        # Avoid zero-area captures which will often fail or return empty images
        if scaled_width <= 0 or scaled_height <= 0:
            logging.warning(
                "zero-area selection after DPI scaling; ignoring capture (%d x %d)",
                scaled_width,
                scaled_height,
            )
            try:
                self.snipped.emit(None)
            except Exception:
                pass
            return

        # Allow the event loop and compositor a moment to hide the overlay.
        try:
            QtWidgets.QApplication.processEvents()
        except Exception:
            pass

        def _perform_capture(
            s_left=scaled_left, s_top=scaled_top, s_w=scaled_width, s_h=scaled_height
        ):
            # Consolidated capture flow: try capture module, then Qt fallback.
            png = None
            # Ensure capture module is fresh and available
            _ensure_capture_module()
            if capture is not None:
                try:
                    png = capture.capture_region(s_left, s_top, s_w, s_h)
                except Exception:
                    logging.exception("capture.capture_region failed")
                    png = None
            else:
                logging.debug("capture module not available; Qt fallback only")

            # Qt fallback: use QScreen.grabWindow into a QBuffer
            if png is None:
                try:
                    screen = QtGui.QGuiApplication.primaryScreen()
                    if screen is None:
                        raise RuntimeError("no_qt_screen")
                    pix = screen.grabWindow(0, s_left, s_top, s_w, s_h)
                    buf = QtCore.QBuffer()
                    buf.open(QtCore.QBuffer.ReadWrite)
                    ok = pix.save(buf, "PNG")
                    if ok:
                        png = bytes(buf.data())
                    else:
                        logging.debug("QPixmap.save returned False in Qt fallback")
                except Exception:
                    logging.exception("Qt fallback capture failed")
                    png = None

            if png is None:
                logging.warning("Screen capture failed via all backends")
                try:
                    self.snipped.emit(None)
                except Exception:
                    pass
                return

            # Write a raw debug dump of the payload to help diagnose issues.
            try:
                ts = int(time.time() * 1000)
                raw_dbg = os.path.join(tempfile.gettempdir(), f"ocrclip-raw-{ts}.bin")
                try:
                    with open(raw_dbg, "wb") as fh:
                        if isinstance(png, (bytes, bytearray)):
                            fh.write(bytes(png))
                        else:
                            try:
                                fh.write(repr(png).encode("utf-8"))
                            except Exception:
                                fh.write(b"<unreprable-payload>")
                    logging.info("Wrote raw capture payload to %s", raw_dbg)
                except Exception:
                    logging.debug("Failed to write raw debug payload", exc_info=True)
            except Exception:
                pass

            # Coerce commonly-returned types into PNG bytes
            png_bytes = None
            if isinstance(png, (bytes, bytearray)):
                png_bytes = bytes(png)
            elif isinstance(png, memoryview):
                png_bytes = png.tobytes()
            else:
                try:
                    if isinstance(png, Image.Image):
                        buf = io.BytesIO()
                        png.save(buf, format="PNG")
                        png_bytes = buf.getvalue()
                except Exception:
                    png_bytes = None

            if png_bytes is None:
                try:
                    if hasattr(QtGui, "QImage") and isinstance(png, QtGui.QImage):
                        buf = QtCore.QBuffer()
                        buf.open(QtCore.QIODevice.WriteOnly)
                        ok = png.save(buf, "PNG")
                        if ok:
                            png_bytes = bytes(buf.data())
                    elif hasattr(QtGui, "QPixmap") and isinstance(png, QtGui.QPixmap):
                        buf = QtCore.QBuffer()
                        buf.open(QtCore.QIODevice.WriteOnly)
                        ok = png.save(buf, "PNG")
                        if ok:
                            png_bytes = bytes(buf.data())
                    else:
                        if hasattr(png, "data") and callable(getattr(png, "data")):
                            try:
                                maybe = png.data()
                                png_bytes = bytes(maybe)
                            except Exception:
                                png_bytes = None
                        elif hasattr(png, "tobytes"):
                            try:
                                png_bytes = png.tobytes()
                            except Exception:
                                png_bytes = None
                        else:
                            try:
                                png_bytes = bytes(png)
                            except Exception:
                                png_bytes = None
                except Exception:
                    png_bytes = None

            if not isinstance(png_bytes, (bytes, bytearray)):
                logging.exception(
                    "Could not coerce capture payload of type %s to bytes", type(png)
                )
                try:
                    ts = int(time.time() * 1000)
                    dbg_path = os.path.join(
                        tempfile.gettempdir(), f"ocrclip-capture-failed-{ts}.bin"
                    )
                    with open(dbg_path, "wb") as fh:
                        try:
                            fh.write(repr(png).encode("utf-8"))
                        except Exception:
                            fh.write(b"<unreprable payload>")
                    logging.error("Wrote debug payload to %s", dbg_path)
                except Exception:
                    pass
                try:
                    self.snipped.emit(None)
                except Exception:
                    pass
                return

            # Validate PNG bytes by attempting to open and load them now
            try:
                tmp_img = Image.open(io.BytesIO(png_bytes))
                tmp_img.load()
            except Exception:
                logging.exception("Captured bytes are not a valid image")
                try:
                    ts = int(time.time() * 1000)
                    dbg_path = os.path.join(
                        tempfile.gettempdir(), f"ocrclip-capture-invalid-{ts}.png"
                    )
                    with open(dbg_path, "wb") as fh:
                        fh.write(
                            png_bytes
                            if isinstance(png_bytes, (bytes, bytearray))
                            else b""
                        )
                    logging.error("Wrote invalid capture bytes to %s", dbg_path)
                except Exception:
                    pass
                try:
                    self.snipped.emit(None)
                except Exception:
                    pass
                return

            try:
                self.snipped.emit((bytes(png_bytes), s_w, s_h))
            except Exception:
                logging.exception("snipped.emit failed")

        # Use a small delay so the overlay has time to hide and compositor
        # to repaint; 80ms is a reasonable compromise across platforms.
        try:
            QtCore.QTimer.singleShot(80, _perform_capture)
        except Exception:
            # As a last resort, perform capture synchronously
            _perform_capture()


class TrayApp(QtWidgets.QSystemTrayIcon):
    # Signal emitted when OCR finishes (runs in GUI thread)
    ocr_finished = QtCore.Signal(str)

    def __init__(self, app, reader, args):
        # Try a themed icon first, fall back to a tiny generated icon so
        # the tray doesn't complain when a theme icon isn't available.
        icon = QtGui.QIcon.fromTheme("camera")
        if icon.isNull():
            pix = QtGui.QPixmap(16, 16)
            pix.fill(QtGui.QColor(0, 0, 0, 0))
            painter = QtGui.QPainter(pix)
            pen = QtGui.QPen(QtGui.QColor(60, 60, 60))
            painter.setPen(pen)
            painter.setBrush(QtGui.QBrush(QtGui.QColor(220, 220, 220)))
            painter.drawRect(2, 4, 12, 8)
            painter.drawEllipse(6, 6, 4, 4)
            painter.end()
            icon = QtGui.QIcon(pix)
        super().__init__(icon, app)
        self.app = app
        self.reader = reader
        self.args = args
        self.setToolTip("OCR Clip")
        menu = QtWidgets.QMenu()
        snip_action = menu.addAction("Snip (Capture Area)")
        snip_action.triggered.connect(self.start_snip)
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.app.quit)
        self.setContextMenu(menu)
        self.activated.connect(self.on_activated)
        # connect signal to slot that updates clipboard in GUI thread
        self.ocr_finished.connect(self._on_ocr_finished)
        self.show()

    def start_snip(self):
        # Ensure any previous overlay is closed
        try:
            if hasattr(self, "overlay") and self.overlay is not None:
                self.overlay.close()
        except Exception:
            pass
        self.overlay = SnipOverlay()
        self.overlay.snipped.connect(self.handle_snip)
        self.overlay.show()

    def handle_snip(self, pil_image: Image.Image):
        # Run OCR in a thread. The snipped payload may be PNG bytes or None.
        # On Windows, when the overlay capture fails (None) fall back to the
        # native snipping UI and poll the clipboard for the resulting image.
        if pil_image is None and sys.platform == "win32":
            try:
                # Launch the Windows snip UI. Prefer the ms-screenclip URI which
                # works on recent Windows 10/11 builds; fall back to SnippingTool.
                try:
                    subprocess.Popen(["explorer.exe", "ms-screenclip:"])
                except Exception:
                    sniptool = shutil.which("SnippingTool.exe") or shutil.which(
                        "snippingtool.exe"
                    )
                    if sniptool:
                        subprocess.Popen([sniptool])

                # Poll the Qt clipboard on a QTimer (runs in the GUI thread).
                clipboard = self.app.clipboard()
                timer = QtCore.QTimer(self)
                timer.setInterval(300)
                start = time.time()

                def _check_clipboard():
                    try:
                        # QMimeData.hasImage() is the safest cross-format check
                        if clipboard.mimeData().hasImage():
                            qimg = clipboard.image()
                            # Make sure the QImage is valid
                            try:
                                # Some bindings expose isNull(), others may not
                                if hasattr(qimg, "isNull") and qimg.isNull():
                                    return
                            except Exception:
                                pass
                            buf = QtCore.QBuffer()
                            buf.open(QtCore.QIODevice.WriteOnly)
                            try:
                                ok = qimg.save(buf, "PNG")
                                if not ok:
                                    return
                            except Exception:
                                # Some QImage/QPixmap implementations may raise; fallthrough
                                try:
                                    qimg.save(buf, "PNG")
                                except Exception:
                                    return
                            data = bytes(buf.data())
                            timer.stop()
                            # Process the image bytes in background thread
                            threading.Thread(
                                target=self._ocr_and_copy, args=(data,), daemon=True
                            ).start()
                            return
                        # timeout after a reasonable period
                        if time.time() - start > 15:
                            timer.stop()
                            threading.Thread(
                                target=self._ocr_and_copy, args=(None,), daemon=True
                            ).start()
                    except Exception:
                        logging.exception("clipboard polling failed")
                        timer.stop()

                timer.timeout.connect(_check_clipboard)
                timer.start()
                return
            except Exception:
                logging.exception("Windows clipboard fallback failed")

        threading.Thread(
            target=self._ocr_and_copy, args=(pil_image,), daemon=True
        ).start()

    def _ocr_and_copy(self, pil_image: Image.Image):
        # pil_image may be raw PNG bytes emitted by the overlay; handle both
        # bytes and PIL.Image inputs.
        try:
            if pil_image is None:
                raise ValueError("no image")

            pil_image_obj = None

            # The overlay emits a tuple (png_bytes, scaled_width, scaled_height)
            # to preserve DPI-aware sizes. Handle that first.
            if isinstance(pil_image, tuple) and len(pil_image) == 3:
                payload, scaled_w, scaled_h = pil_image
                if isinstance(payload, (bytes, bytearray, memoryview)):
                    b = bytes(payload)
                    logging.debug(
                        "_ocr_and_copy: received tuple bytes payload size=%d (scaled %dx%d)",
                        len(b),
                        scaled_w,
                        scaled_h,
                    )
                    # Try loading from memory first
                    try:
                        pil_image_obj = Image.open(io.BytesIO(b))
                        pil_image_obj.load()
                    except Exception:
                        logging.exception(
                            "PIL failed to open image from bytes in-memory; trying temp file"
                        )
                        tmp = None
                        try:
                            tmp = tempfile.NamedTemporaryFile(
                                suffix=".png", delete=False
                            )
                            tmp_name = tmp.name
                            tmp.write(b)
                            tmp.flush()
                            tmp.close()
                            pil_image_obj = Image.open(tmp_name)
                            pil_image_obj.load()
                        except Exception:
                            logging.exception("PIL failed to open image from temp file")
                            # Try to salvage by finding an embedded PNG signature
                            try:
                                idx = b.find(b"\x89PNG")
                                if idx > 0:
                                    logging.debug(
                                        "Found PNG signature at offset %d, retrying load",
                                        idx,
                                    )
                                    try:
                                        pil_image_obj = Image.open(io.BytesIO(b[idx:]))
                                        pil_image_obj.load()
                                    except Exception:
                                        logging.exception(
                                            "Retry after signature slicing failed"
                                        )
                            except Exception:
                                logging.exception("Signature-scan failed")
                            finally:
                                if tmp is not None:
                                    try:
                                        os.unlink(tmp_name)
                                    except Exception:
                                        pass

                        # If we still don't have an image, see if the payload is
                        # raw pixel data (RGB or RGBA) using the scaled dims.
                        if pil_image_obj is None:
                            try:
                                expected_rgb = scaled_w * scaled_h * 3
                                expected_rgba = scaled_w * scaled_h * 4
                                lb = len(b)
                                logging.debug(
                                    "Failed PIL open. payload len=%d expected_rgb=%d expected_rgba=%d",
                                    lb,
                                    expected_rgb,
                                    expected_rgba,
                                )
                                if lb == expected_rgb:
                                    logging.info(
                                        "Interpreting payload as raw RGB bytes"
                                    )
                                    try:
                                        pil_image_obj = Image.frombytes(
                                            "RGB", (scaled_w, scaled_h), b
                                        )
                                    except Exception:
                                        try:
                                            pil_image_obj = Image.frombuffer(
                                                "RGB",
                                                (scaled_w, scaled_h),
                                                b,
                                                "raw",
                                                "RGB",
                                                0,
                                                1,
                                            )
                                        except Exception:
                                            logging.exception(
                                                "Raw RGB reconstruction failed"
                                            )
                                elif lb == expected_rgba:
                                    logging.info(
                                        "Interpreting payload as raw RGBA bytes"
                                    )
                                    try:
                                        pil_image_obj = Image.frombytes(
                                            "RGBA", (scaled_w, scaled_h), b
                                        ).convert("RGB")
                                    except Exception:
                                        try:
                                            pil_image_obj = Image.frombuffer(
                                                "RGBA",
                                                (scaled_w, scaled_h),
                                                b,
                                                "raw",
                                                "RGBA",
                                                0,
                                                1,
                                            ).convert("RGB")
                                        except Exception:
                                            logging.exception(
                                                "Raw RGBA reconstruction failed"
                                            )
                            except Exception:
                                logging.exception("Raw-pixel salvage logic failed")

                        if pil_image_obj is None:
                            logging.error("Could not decode image from tuple payload")
                            try:
                                # Write debug dump for worker-side failures
                                ts = int(time.time() * 1000)
                                dbg_worker = os.path.join(
                                    tempfile.gettempdir(),
                                    f"ocrclip-worker-failed-{ts}.bin",
                                )
                                with open(dbg_worker, "wb") as fh:
                                    fh.write(b)
                                logging.error(
                                    "Wrote worker debug payload to %s", dbg_worker
                                )
                            except Exception:
                                logging.exception(
                                    "Failed to write worker debug payload"
                                )
                            try:
                                self.ocr_finished.emit("(snip conversion error)")
                            except Exception:
                                pass
                            return
                elif isinstance(payload, Image.Image):
                    pil_image_obj = payload
                else:
                    logging.error("Unsupported tuple payload type: %s", type(payload))
                    try:
                        self.ocr_finished.emit("(snip conversion error)")
                    except Exception:
                        pass
                    return

            elif isinstance(pil_image, (bytes, bytearray, memoryview)):
                b = bytes(pil_image)
                logging.debug("_ocr_and_copy: received bytes payload size=%d", len(b))
                try:
                    pil_image_obj = Image.open(io.BytesIO(b))
                    pil_image_obj.load()
                except Exception:
                    logging.exception(
                        "PIL failed to open image from bytes payload (direct)"
                    )
                    try:
                        self.ocr_finished.emit("(snip conversion error)")
                    except Exception:
                        pass
                    return
            elif isinstance(pil_image, Image.Image):
                pil_image_obj = pil_image
            else:
                logging.error("Unsupported snip type: %s", type(pil_image))
                try:
                    self.ocr_finished.emit("(snip conversion error)")
                except Exception:
                    pass
                return

            img_rgb = pil_image_obj.convert("RGB")
            img = np.asarray(img_rgb)
        except Exception:
            logging.exception("Failed to convert snip to array")
            try:
                self.ocr_finished.emit("(snip conversion error)")
            except Exception:
                pass
            return

        if self.reader is None:
            text = "(easyocr not installed)"
        else:
            try:
                results = self.reader.readtext(img)
                text = "\n".join([r[1] for r in results])
            except RuntimeError as e:
                # Reader not ready yet — notify user and copy nothing
                if str(e) == "ocr_not_ready":
                    text = "(ocr initializing - try again shortly)"
                else:
                    text = "(ocr failed to run)"
            except Exception:
                logging.exception("Unexpected OCR error")
                text = "(ocr error)"

        # Emit result to GUI thread; do not touch Qt objects here
        try:
            self.ocr_finished.emit(text)
        except Exception:
            logging.exception("Failed to emit OCR result signal")
            logging.debug("OCR text: %s", text)

    def on_activated(self, reason):
        # left click to start
        if reason == QtWidgets.QSystemTrayIcon.Trigger:
            self.start_snip()

    def _on_ocr_finished(self, text: str):
        # Runs in GUI thread — safe to access Qt objects
        try:
            cb = self.app.clipboard()
            cb.setText(text)
        except Exception:
            logging.exception("Failed to set clipboard")
        # Small notification
        try:
            self.showMessage(
                "OCR Clip",
                "Text copied to clipboard",
                QtWidgets.QSystemTrayIcon.Information,
                2000,
            )
        except Exception:
            pass


def build_reader(args):
    if easyocr is None:
        return None
    gpu = not args.no_gpu
    langs = [l.strip() for l in args.lang.split(",") if l.strip()]

    # Lazy background initialization wrapper so the UI doesn't block while
    # EasyOCR downloads models / initializes PyTorch. The wrapper exposes a
    # `readtext(img)` method and raises RuntimeError('ocr_not_ready') if the
    # model is still initializing.
    class ReaderWrapper:
        def __init__(self, langs, gpu):
            self._real = None
            self._failed = False
            self._event = threading.Event()
            self.langs = langs
            self.gpu = gpu
            threading.Thread(target=self._init, daemon=True).start()

        def _init(self):
            try:
                logging.info("Initializing EasyOCR reader in background...")
                self._real = easyocr.Reader(self.langs, gpu=self.gpu)
            except Exception:
                logging.exception("EasyOCR initialization failed")
                self._failed = True
            finally:
                self._event.set()

        def readtext(self, img):
            # If initialization hasn't finished yet, signal caller to retry
            if not self._event.is_set():
                raise RuntimeError("ocr_not_ready")
            if self._failed or self._real is None:
                raise RuntimeError("ocr_failed")
            return self._real.readtext(img)

        def ready(self):
            return self._event.is_set() and not self._failed

    try:
        return ReaderWrapper(langs, gpu)
    except Exception:
        logging.exception("Failed to start EasyOCR init")
        return None


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--no-gpu", action="store_true")
    p.add_argument("--lang", default="en")
    p.add_argument("--hotkey", default="ctrl+shift+s")
    p.add_argument(
        "--no-hotkey", action="store_true", help="Disable global hotkey (use tray icon)"
    )
    p.add_argument(
        "--hotkey-backend",
        choices=["pynput", "qt", "none"],
        default="pynput",
        help="Preferred hotkey backend (pynput may not work on Wayland)",
    )
    p.add_argument(
        "--wait-ocr",
        action="store_true",
        help="Block startup until OCR models are initialized (or timeout)",
    )
    p.add_argument(
        "--wait-seconds",
        type=int,
        default=30,
        help="Seconds to wait for OCR initialization when --wait-ocr is used",
    )
    return p.parse_args()


def main():
    args = parse_args()

    # Preflight checks and diagnostics
    def _preflight_checks(a):
        try:
            logging.info("Preflight: platform=%s", sys.platform)
            is_wayland = (
                os.environ.get("XDG_SESSION_TYPE") == "wayland"
                or "WAYLAND_DISPLAY" in os.environ
            )
            logging.info(
                "Display server: %s",
                "wayland"
                if is_wayland
                else os.environ.get("XDG_SESSION_TYPE", "unknown"),
            )
            # capture backends
            if capture is None:
                logging.warning(
                    "capture backend module not available; screen capture may fail"
                )
            else:
                try:
                    # check mss availability
                    has_mss = getattr(capture, "_HAS_MSS", False)
                    logging.info("mss available: %s", bool(has_mss))
                except Exception:
                    logging.debug("Could not determine mss availability")

            # CLI tools
            def _which(cmd):
                try:
                    return shutil.which(cmd) is not None
                except Exception:
                    return False

            logging.info("grim installed: %s", _which("grim"))
            logging.info("maim installed: %s", _which("maim"))
            logging.info("screencapture installed (macos): %s", _which("screencapture"))
            logging.info("imagemagick import installed: %s", _which("import"))
            # hotkey lib
            try:
                import pynput  # type: ignore

                logging.info("pynput available: True")
            except Exception:
                logging.info("pynput available: False")
            # easyocr
            logging.info("easyocr available: %s", easyocr is not None)
        except Exception:
            logging.exception("Preflight checks failed")

    _preflight_checks(args)
    app = QtWidgets.QApplication(sys.argv)
    reader = build_reader(args)
    tray = TrayApp(app, reader, args)

    # Optional: wait for OCR to finish initialization
    if args.wait_ocr and reader is not None:
        logging.info(
            "Waiting up to %d seconds for OCR initialization...", args.wait_seconds
        )
        start = time.time()
        while time.time() - start < args.wait_seconds:
            if reader.ready():
                logging.info("OCR initialized")
                break
            time.sleep(0.25)
        else:
            logging.warning("OCR did not initialize within timeout; continuing")

    # Global hotkey handling (pluggable backends)
    if not args.no_hotkey and args.hotkey_backend != "none":
        # Detect Wayland and warn: many global hotkey libraries don't work there
        is_wayland = (
            os.environ.get("XDG_SESSION_TYPE") == "wayland"
            or "WAYLAND_DISPLAY" in os.environ
        )
        if is_wayland and args.hotkey_backend == "pynput":
            logging.warning(
                "Wayland session detected: pynput may not be able to register global hotkeys. Use --no-hotkey or --hotkey-backend=qt if available."
            )

        if args.hotkey_backend == "pynput":
            try:
                from pynput import keyboard

                def on_activate():
                    tray.start_snip()

                # parse a simple ctrl/shift/alt combination + key
                parts = args.hotkey.lower().split("+")
                mods = set(parts[:-1])
                key = parts[-1]

                comb = set()
                if "ctrl" in mods:
                    comb.add(keyboard.Key.ctrl)
                if "shift" in mods:
                    comb.add(keyboard.Key.shift)
                if "alt" in mods:
                    comb.add(keyboard.Key.alt)

                current = set()

                def on_press(k):
                    if k in comb:
                        current.add(k)
                    else:
                        try:
                            if hasattr(k, "char") and k.char == key:
                                if comb.issubset(current):
                                    on_activate()
                        except Exception:
                            pass

                def on_release(k):
                    if k in current:
                        current.remove(k)

                listener = keyboard.Listener(on_press=on_press, on_release=on_release)
                listener.start()
                # Keep a reference on the tray so the listener isn't GC'd
                tray._pynput_listener = listener
            except Exception:
                logging.exception(
                    "pynput hotkey failed; falling back to tray activation"
                )
        elif args.hotkey_backend == "qt":
            logging.info("hotkey backend set to qt; note: platform support varies")
            # Try to use QHotkey (optional dependency) to register a global
            # hotkey via the Qt event loop. If it's not available we fall back
            # to using the tray icon activation.
            try:
                from qhotkey import QHotkey  # type: ignore

                hotkey_str = args.hotkey
                # Normalize common modifier names to capitalized form
                hotkey_str = (
                    hotkey_str.replace("ctrl", "Ctrl")
                    .replace("shift", "Shift")
                    .replace("alt", "Alt")
                )
                try:
                    hk = QHotkey(hotkey_str, parent=tray)
                except TypeError:
                    # Some QHotkey bindings accept (keyseq, registered, parent)
                    try:
                        hk = QHotkey(hotkey_str, False, tray)
                    except Exception:
                        hk = None

                if hk is not None:
                    try:
                        hk.activated.connect(tray.start_snip)
                    except Exception:
                        # Some versions expose a different signal name; ignore if connect fails
                        pass
                    try:
                        if hasattr(hk, "setRegistered"):
                            hk.setRegistered(True)
                        elif hasattr(hk, "registerHotkey"):
                            hk.registerHotkey()
                        elif hasattr(hk, "register"):
                            hk.register()
                    except Exception:
                        logging.exception("Failed to register Qt hotkey via QHotkey")
                    # Keep reference so the QHotkey object isn't GC'd
                    tray._qhotkey = hk
                else:
                    logging.info(
                        "QHotkey import succeeded but could not instantiate hotkey; falling back to tray icon"
                    )
            except Exception:
                logging.exception(
                    "qt hotkey backend unavailable (qhotkey not installed); falling back to tray icon"
                )
        else:
            logging.info("No hotkey backend requested; using tray icon activation")
    else:
        logging.info(
            "Global hotkey disabled via --no-hotkey or backend=none; use tray icon to snip"
        )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
