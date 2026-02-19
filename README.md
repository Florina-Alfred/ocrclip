OCR Clip
========

Simple cross-platform screenshot->OCR->clipboard utility written in Python.

Features
- Global hotkey to start a snip overlay (default Ctrl+Shift+S)
- Select a rectangular region; the app runs OCR and places plain text into the clipboard
- Uses PySide6 for UI, mss for fast screenshots, and EasyOCR (PyTorch) for accurate OCR (GPU optional)

Quick start

1. Create a virtual environment and install dependencies.

With `uv` installed (recommended):

```bash
# create + install deps into a pyproject-managed venv
uv .venv --activate --install
```

Fallback — plain virtualenv + pip:

```bash
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -U pip setuptools wheel
pip install -e .            # installs "lite" dependencies by default
```

To install heavy dependencies (easyocr/torch) use the `full` extras:

```bash
# CPU-only full extras (may be large)
pip install --index-url https://download.pytorch.org/whl/cpu torch
pip install -e .[full]
```

Developer helper (recommended)

Run the included helper which prefers `uv` but falls back to pip:

```bash
./scripts/dev-setup.sh         # installs lite deps
# or
./scripts/dev-setup.sh --full  # installs full extras (torch+easyocr)
```

If you have a CUDA-capable GPU and want GPU acceleration for EasyOCR, install torch with CUDA first following instructions at https://pytorch.org, then install EasyOCR.

2. Run the app:

```bash
python3 -m src.main
# or when using the virtualenv python directly:
.venv/bin/python3 -m src.main
```

Platform notes
- macOS: grant Screen Recording and Accessibility permissions for the app (System Settings -> Privacy & Security). Without Screen Recording the app cannot capture the screen.
- Linux (Wayland): global hotkeys and direct screenshots may be restricted depending on the compositor. Install helpers like `grim`/`slurp` or `xdg-desktop-portal` and use the tray icon if hotkeys fail.
- Windows: running as a normal user is sufficient for screenshots, but PyInstaller builds should include the Visual C++ runtime.

Command line flags
- `--no-gpu` : disable GPU use in EasyOCR (default: use GPU if available)
- `--lang` : comma-separated languages for EasyOCR (default: `en`)
- `--hotkey` : hotkey string for activation (default: `ctrl+shift+s`)
 - `--no-hotkey` : disable global hotkey and use tray icon only
 - `--hotkey-backend` : preferred hotkey backend (`pynput`, `qt`, or `none`)
 - `--wait-ocr` : block startup until OCR models initialize (useful on first run)

Troubleshooting & packaging notes
- On macOS you must grant Screen Recording and Accessibility permissions; when running from a bundle (App) grant permissions to the packaged binary.
- On Wayland you may need `grim` + `slurp` or `xdg-desktop-portal` for screenshots and/or permissions. If global hotkeys do not work, use `--no-hotkey`.
- For packaging with PyInstaller include Qt plugins and test the single-file build on each target OS. Use `--collect-all PySide6` or PyInstaller hooks for PySide6.

Notes and limitations
- Wayland: global hotkeys and direct screenshots may be restricted on some Wayland compositors. See README for troubleshooting.
- Packaging: use PyInstaller to create standalone EXEs. Expect large binaries due to PyTorch/EasyOCR.

Files
- `src/main.py` : main application code

License: MIT
# ocrclip
