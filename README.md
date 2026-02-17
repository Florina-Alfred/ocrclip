OCR Clip
========

Simple cross-platform screenshot->OCR->clipboard utility written in Python.

Features
- Global hotkey to start a snip overlay (default Ctrl+Shift+S)
- Select a rectangular region; the app runs OCR and places plain text into the clipboard
- Uses PySide6 for UI, mss for fast screenshots, and EasyOCR (PyTorch) for accurate OCR (GPU optional)

Quick start

1. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
```

If you have a CUDA-capable GPU and want GPU acceleration for EasyOCR, install torch with CUDA first following instructions at https://pytorch.org, then install EasyOCR.

2. Run the app:

```bash
python3 -m src.main
# or when using the virtualenv python directly:
.venv/bin/python3 -m src.main
```

Command line flags
- `--no-gpu` : disable GPU use in EasyOCR (default: use GPU if available)
- `--lang` : comma-separated languages for EasyOCR (default: `en`)
- `--hotkey` : hotkey string for activation (default: `ctrl+shift+s`)

Notes and limitations
- Wayland: global hotkeys and direct screenshots may be restricted on some Wayland compositors. See README for troubleshooting.
- Packaging: use PyInstaller to create standalone EXEs. Expect large binaries due to PyTorch/EasyOCR.

Files
- `src/main.py` : main application code

License: MIT
# ocrclip
