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
  cat <<USAGE
Usage: $0 <command> [options]

Commands:
  build                 Build AppImage artifacts via Docker (unchanged)
  pull [ARCH] [--install]
                        Download heavy binary wheels into ./binaries and
                        optionally install them into .venv. ARCH can be
                        'cpu' (default) or a CUDA tag like 'cu118'.

Examples:
  $0 build
  $0 pull            # download CPU torch + easyocr + lite deps into ./binaries
  $0 pull cu118 --install  # download CUDA 11.8 torch wheel and install into .venv
USAGE
  exit 1
}

if [ $# -lt 1 ]; then
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
    # Defaults
    ARCH=cpu
    INSTALL=0

    # Parse optional args after 'pull'
    if [ $# -ge 2 ]; then
      for arg in "${@:2}"; do
        case "$arg" in
          --install|-i)
            INSTALL=1
            ;;
          cpu)
            ARCH=cpu
            ;;
          cu*|cu-*)
            ARCH=${arg//-/}
            ;;
          *)
            echo "Unknown option: $arg" >&2
            usage
            ;;
        esac
      done
    fi

    DEST_DIR="$ROOT_DIR/binaries"
    mkdir -p "$DEST_DIR"

    # Use uv-managed venv's pip if uv is available; otherwise require uv installation
    if ! command -v uv >/dev/null 2>&1; then
      echo "uv is required to manage environments. Install uv (pipx recommended) and re-run."
      exit 1
    fi

    # Create a temporary uv-managed venv to download wheels into the destination
    TMP_VENV="$DEST_DIR/.tmp_venv"
    if [ ! -d "$TMP_VENV" ]; then
      uv "$TMP_VENV" --install
    fi
    PIP_CMD="$TMP_VENV/bin/pip"

    echo "Downloading lightweight dependencies (requirements-lite.txt) and their dependencies into: $DEST_DIR"
    "$PIP_CMD" download -d "$DEST_DIR" -r "$ROOT_DIR/requirements-lite.txt"

    echo "Downloading EasyOCR (no dependencies) into: $DEST_DIR"
    "$PIP_CMD" download --no-deps -d "$DEST_DIR" easyocr

    echo "Downloading torch (arch=$ARCH) into: $DEST_DIR"
    if [ "$ARCH" = "cpu" ]; then
      "$PIP_CMD" download --no-deps -d "$DEST_DIR" --index-url https://download.pytorch.org/whl/cpu torch
    else
      # For CUDA variants the PyTorch index uses a path like /whl/cu118
      "$PIP_CMD" download --no-deps -d "$DEST_DIR" --index-url "https://download.pytorch.org/whl/$ARCH" torch
    fi

    echo
    echo "Downloaded files (summary):"
    ls -lh "$DEST_DIR" || true

    if [ "$INSTALL" -eq 1 ]; then
      if [ -d "$ROOT_DIR/.venv" ]; then
        echo "Installing downloaded wheels into .venv (this uses pip inside .venv)"
        # Install all wheel files found in binaries/ into the venv (no index)
        .venv/bin/pip install --no-index --find-links="$DEST_DIR" "$DEST_DIR"/*.whl
        echo "Installed wheels into .venv"
      else
        echo ".venv not found. Run scripts/dev-setup.sh to create a virtualenv first, or run the following to install manually:"
        echo "  python3 -m pip install --no-index --find-links=\"$DEST_DIR\" $DEST_DIR/*.whl"
      fi
    else
      echo
      echo "To install the downloaded wheels into an existing venv run (example):"
      echo "  .venv/bin/pip install --no-index --find-links=\"$DEST_DIR\" $DEST_DIR/*.whl"
    fi

    ;;

  *)
    usage
    ;;
esac
