#!/usr/bin/env bash
set -euo pipefail

# Manage heavy binary artifacts (Qt libs, torch wheels, AppDir contents).
#
# This script provides two functions:
# - build: run the existing Docker builder to produce AppImage artifacts
# - pull: download official prebuilt wheels or redistributable bundles when
#         available (e.g. official PyTorch wheels from the PyTorch index)
#
# Usage:
#   ./scripts/manage_binaries.sh build   # produce artifacts in ./dist via Docker
#   ./scripts/manage_binaries.sh pull    # instructive helper to download wheels

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)

function usage() {
  echo "Usage: $0 <build|pull>"
  exit 1
}

if [ $# -ne 1 ]; then
  usage
fi

case "$1" in
  build)
    echo "Building artifacts via Docker builder..."
    docker build -f Dockerfile.build.full -t ocrclip-builder "$ROOT_DIR"
    mkdir -p "$ROOT_DIR/dist"
    docker run --rm -v "$ROOT_DIR/dist:/workspace/dist" ocrclip-builder /bin/bash -lc "./scripts/build/linux/build_appimage_full.sh"
    echo "Artifacts placed under ./dist"
    ;;
  pull)
    cat <<'EOF'
This helper prints recommended commands to download heavy binary deps.

PyTorch (CPU wheel) - install into virtualenv before installing project:

  pip install --index-url https://download.pytorch.org/whl/cpu torch

EasyOCR - regular pip install after torch:

  pip install easyocr

If you need a prebuilt AppImage from this repository, we do not commit
AppImage binaries to the repo. Instead, run `./scripts/manage_binaries.sh build`
to produce them inside Docker, or download a release asset if one exists.

EOF
    ;;
  *)
    usage
    ;;
esac
