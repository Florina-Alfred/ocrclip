import sys
import os
from PySide6 import QtWidgets

# Ensure repository root is on sys.path so tests can import the `src` package
# when pytest changes the current working directory during collection.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.main import TrayApp


def test_on_ocr_finished_sets_clipboard(qtbot):
    # Ensure a QApplication exists (pytest-qt provides fixtures to manage this)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

    class DummyTray:
        def __init__(self, app):
            self.app = app

        def showMessage(self, *args, **kwargs):
            # emulate QSystemTrayIcon.showMessage (no-op for test)
            self._shown = True

    tray = DummyTray(app)

    # Call the unbound method with our dummy instance — this avoids having
    # to create a real QSystemTrayIcon which may interact with the OS.
    TrayApp._on_ocr_finished(tray, "hello world")

    assert app.clipboard().text() == "hello world"
