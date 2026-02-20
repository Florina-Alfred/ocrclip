#!/usr/bin/env bash
# scripts/build/linux/build_appimage_full.sh
# Build a full CPU-only AppImage including EasyOCR + Torch using PyInstaller
# Run inside a clean Ubuntu-based Docker container for reproducibility.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"

# prefer uv for virtualenv management
PYTHON=${PYTHON:-python3}

echo "[build] repo root: $REPO_ROOT"
echo "[build] using python: $($PYTHON --version)"

# 1) create virtualenv using uv (required)
if ! command -v uv >/dev/null 2>&1; then
  echo "[build] uv is required in the build image PATH. Install uv before running this script."
  exit 1
fi

if [ -d ".venv" ]; then
  echo "[build] reusing existing .venv"
else
  echo "[build] creating .venv via uv"
  uv .venv --install
fi

source .venv/bin/activate
PIP=.venv/bin/pip
"$PIP" install -U pip setuptools wheel

# 2) Install CPU PyTorch wheel - prefer explicit CPU index for reproducible CPU-only builds
echo "[build] Installing CPU torch wheel (this may take a while)..."
pip install --index-url https://download.pytorch.org/whl/cpu torch || true

# 3) Install project with full extras (easyocr, pyinstaller)
echo "[build] Installing project (.[full])"
pip install -e '.[full]'

# Ensure pyinstaller is available
pip install pyinstaller

# 4) Clean prior builds
rm -rf build dist AppDir *.AppImage

# 5) Prepare pyinstaller hooks dir
HOOKS_DIR="$REPO_ROOT/pyinstaller-hooks"
mkdir -p "$HOOKS_DIR"

echo "[build] Running PyInstaller (one-dir)"
pyinstaller --noconfirm --clean --log-level=DEBUG --onedir \
  --additional-hooks-dir "$HOOKS_DIR" \
  --runtime-hook "scripts/pyi_rth_ldpath.py" \
  --runtime-hook "scripts/pyi_rth_qt.py" \
  --name ocrclip src/main.py

# 6) Post-build: fix RPATHs for bundled .so files (requires patchelf available in image)
echo "[build] Running rpath fixups"
python3 scripts/pyi_post_build_linux_fix_rpath.py dist/ocrclip || true

# 7) Create AppDir layout
APPDIR=AppDir
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -r dist/ocrclip/* "$APPDIR/usr/bin/"

# rename executable to allow wrapper named 'ocrclip'
if [ -f "$APPDIR/usr/bin/ocrclip" ]; then
  mv "$APPDIR/usr/bin/ocrclip" "$APPDIR/usr/bin/ocrclip-bin" || true
fi

# 8) Wrapper
cat > "$APPDIR/usr/bin/ocrclip" <<'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.."
export LD_LIBRARY_PATH="$HERE/lib:${LD_LIBRARY_PATH:-}"
export QT_PLUGIN_PATH="$HERE/plugins:${QT_PLUGIN_PATH:-}"
exec "$HERE/bin/ocrclip-bin" "$@"
EOF
chmod +x "$APPDIR/usr/bin/ocrclip"

# 9) Desktop file
cat > "$APPDIR/usr/share/applications/ocrclip.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=OCR Clip
Exec=ocrclip %u
Icon=ocrclip
Categories=Utility;Text;
EOF

# 10) Icon (optional)
if [ -f resources/icon.png ]; then
  cp resources/icon.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/ocrclip.png"
fi

echo "[build] Creating AppImage (linuxdeployqt or appimagetool required)"

# Prefer linuxdeployqt if available; otherwise look for AppImage helpers in repo
if command -v linuxdeployqt >/dev/null 2>&1; then
  linuxdeployqt "$APPDIR/usr/share/applications/ocrclip.desktop" -appimage || true
elif [ -x ./linuxdeployqt-x86_64.AppImage ]; then
  chmod +x ./linuxdeployqt-x86_64.AppImage
  ./linuxdeployqt-x86_64.AppImage "$APPDIR/usr/share/applications/ocrclip.desktop" -appimage || true
elif [ -x ./appimagetool.AppImage ]; then
  chmod +x ./appimagetool.AppImage
  ./appimagetool.AppImage "$APPDIR" || true
else
  echo "linuxdeployqt or appimagetool not found in PATH or repo root. Skipping AppImage creation. You can run linuxdeployqt or appimagetool manually on $APPDIR."
fi

mkdir -p dist
mv *.AppImage dist/ 2>/dev/null || true
echo "[build] Done. Artifacts (if created) are in dist/." 
