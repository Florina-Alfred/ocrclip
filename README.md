OCR Clip
========

Simple cross-platform screenshot->OCR->clipboard utility written in Python.

Features
- Global hotkey to start a snip overlay (default Ctrl+Shift+S)
- Select a rectangular region; the app runs OCR and places plain text into the clipboard
- Uses PySide6 for UI, mss for fast screenshots, and EasyOCR (PyTorch) for accurate OCR (GPU optional)

Quick start

1. Create a virtual environment and install dependencies.

Required: `uv` manages the venv and installs dependencies from `pyproject.toml`.

```bash
# create + install deps into a pyproject-managed venv
uv .venv --activate --install
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

Packaging artifacts removed from main
-----------------------------------
This repository used to contain committed build artifacts (AppDir, dist, and a local `.venv`) which made the main branch very large. Those binaries have been removed from `main` to keep the repository lean.

If you need the previous build outputs for debugging they are preserved as a GitHub release asset named "Build artifacts - preserve". We intentionally do not commit these binaries in the repository. Instead, build them locally or in Docker using `Dockerfile.build.full` and the scripts under `scripts/build/linux/`.

Quick instructions to rebuild the full AppImage (recommended: use Docker)

1) Build the reproducible builder image (Ubuntu 22.04):

```bash
docker build -f Dockerfile.build.full -t ocrclip-builder .
```

2) Run the builder which will run the AppImage build script and place artifacts under `dist/` on the host (mounted):

```bash
docker run --rm -v "$(pwd)/dist:/workspace/dist" ocrclip-builder \
  /bin/bash -lc "./scripts/build/linux/build_appimage_full.sh"
```

3) Inspect `dist/` for the produced AppImage and run it on a clean VM to verify missing system libs. See `scripts/pyi_post_build_linux_fix_rpath.py` for rpath fixups.

Manage binaries helper
----------------------
We include a small helper script `scripts/manage_binaries.sh` to simplify working with heavy binary artifacts.

- Build the full AppImage via Docker (recommended):

```bash
./scripts/manage_binaries.sh build
```

- Get recommended commands to install official prebuilt wheels (PyTorch CPU wheel first, then EasyOCR):

```bash
./scripts/manage_binaries.sh pull
```

The `pull` mode prints the canonical commands we recommend (for example:
`pip install --index-url https://download.pytorch.org/whl/cpu torch` then
`pip install easyocr`). We intentionally avoid committing prebuilt binaries to
the repository — use the Docker builder or the `manage_binaries.sh` helper to
produce or fetch them on-demand.

`pull` usage (automated download)
--------------------------------
The `pull` subcommand now automates downloading wheel files (and light deps)
into a local `./binaries/` directory (this directory is ignored by git).

Usage examples:

  - Download CPU wheels and required lite deps into `./binaries`:

      ./scripts/manage_binaries.sh pull

  - Download a CUDA build (example for CUDA 11.8) and install into `.venv`:

      ./scripts/manage_binaries.sh pull cu118 --install

Notes:
- Downloaded wheels are saved to `./binaries/` (see `.gitignore`) so they are
  never committed to the repository.
- Use `--install` to install the downloaded wheels into an existing `.venv`.
- The script downloads `requirements-lite.txt` packages, `easyocr` (no-deps),
  and a `torch` wheel for the requested architecture.


Why we removed binaries
- Prebuilt artifacts (torch, opencv, Qt libs) are large, frequently platform-specific, and cause repository bloat.
- Reproducible builds are safer and easier to maintain when done in a controlled environment (Docker builder). This README documents how to reproduce the artifacts.

If you'd like, I can now remove the tracked AppDir files from the index and commit the cleanup so main no longer contains any of the binary files — confirm and I'll proceed.

Notes and limitations
- Wayland: global hotkeys and direct screenshots may be restricted on some Wayland compositors. See README for troubleshooting.
- Packaging: use PyInstaller to create standalone EXEs. Expect large binaries due to PyTorch/EasyOCR.

Files
- `src/main.py` : main application code

License: MIT
# ocrclip
