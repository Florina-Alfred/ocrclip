#!/usr/bin/env bash
# scripts/dev-setup.sh
# Create a venv and install project dependencies. Prefer `uv` when available,
# fall back to a plain venv + pip installation. Designed to be safe when run
# non-interactively (it does not rely on sourcing the venv).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

usage() {
  cat <<'USAGE'
Usage: dev-setup.sh [--full] [--preinstall-torch]

Options:
  --full             Install full extras (easyocr, pyinstaller). Default installs minimal deps.
  --preinstall-torch Pre-install CPU torch wheel before installing rest (useful for reproducible builds).
  -h, --help         Show this help

This script creates .venv/ (if missing) and installs project dependencies there.
It prefers `uv` if available, otherwise falls back to `pip install -e .`.
To activate the venv in your current shell run: `source .venv/bin/activate`.
USAGE
}

PREINSTALL_TORCH=0
MODE=light

while [ ${#} -gt 0 ]; do
  case "$1" in
    --preinstall-torch|-t)
      PREINSTALL_TORCH=1
      shift
      ;;
    --full)
      MODE=full
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 2
      ;;
  esac
done

PY=python3

if [ ! -d .venv ]; then
  echo "[dev-setup] creating venv (.venv)"
  $PY -m venv .venv
fi

PIP=.venv/bin/pip
PYBIN=.venv/bin/python

echo "[dev-setup] upgrading pip / setuptools / wheel inside venv"
$PIP install -U pip setuptools wheel

if [ "$PREINSTALL_TORCH" -eq 1 ]; then
  echo "[dev-setup] preinstalling CPU torch into .venv (this may be large)"
  # best-effort; allow failure but continue
  "$PIP" install --index-url https://download.pytorch.org/whl/cpu torch || true
fi

# Prefer a system-wide uv (so users can manage envs globally), but also
# accept a uv installed into the venv (.venv/bin/uv) if present.
UV_CMD=""
if command -v uv >/dev/null 2>&1; then
  UV_CMD=uv
elif [ -x .venv/bin/uv ]; then
  UV_CMD=.venv/bin/uv
fi

if [ -n "$UV_CMD" ]; then
  echo "[dev-setup] using uv to install dependencies: $UV_CMD .venv --install"
  # Create/install into the venv using uv (uv will detect the venv path).
  # Run in non-interactive mode; uv will create the venv if needed and install.
  "$UV_CMD" .venv --install
  echo "[dev-setup] uv install complete"
else
  echo "[dev-setup] uv not found; falling back to pip editable install"
  if [ "$MODE" = "full" ]; then
    "$PIP" install -e '.[full]'
  else
    "$PIP" install -e .
  fi
fi

cat <<EOF
[dev-setup] complete.
To activate the environment in your shell run:
  source .venv/bin/activate

If you used uv and want the uv helper on PATH, consider installing it via pipx:
  python -m pip install --user pipx && python -m pipx ensurepath && pipx install uv
EOF
