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

# Require `uv` for environment management — we no longer support a pip
# fallback. Install uv via pipx (recommended) or pip: `python3 -m pipx install uv`
UV_CMD=""
if command -v uv >/dev/null 2>&1; then
  UV_CMD=uv
fi

if [ -z "$UV_CMD" ]; then
  cat <<'ERR'
[dev-setup] uv is required but not found on PATH.
Install uv (recommended via pipx):

  python3 -m pip install --user pipx && python3 -m pipx ensurepath
  python3 -m pipx install uv

Or, as an alternative (not recommended):
  python3 -m pip install --user uv

After installing uv, re-run this script.
ERR
  exit 1
fi

echo "[dev-setup] using uv to create/install into .venv: $UV_CMD .venv --install"

# If preinstall-torch is requested we will create the venv first and then
# preinstall the torch wheel into the venv before installing the rest.
if [ ! -d .venv ]; then
  # Create the venv using uv (this will also install project deps)
  "$UV_CMD" .venv --install
fi

PIP=.venv/bin/pip
PYBIN=.venv/bin/python

echo "[dev-setup] upgrading pip / setuptools / wheel inside venv"
"$PIP" install -U pip setuptools wheel

if [ "$PREINSTALL_TORCH" -eq 1 ]; then
  echo "[dev-setup] preinstalling CPU torch into .venv (this may be large)"
  # best-effort; allow failure but continue
  "$PIP" install --index-url https://download.pytorch.org/whl/cpu torch || true
fi

if [ "$MODE" = "full" ]; then
  echo "[dev-setup] installing full extras into .venv"
  "$PIP" install -e '.[full]'
else
  echo "[dev-setup] installing project into .venv"
  "$PIP" install -e .
fi

cat <<EOF
[dev-setup] complete.
To activate the environment in your shell run:
  source .venv/bin/activate

If you used uv and want the uv helper on PATH, consider installing it via pipx:
  python -m pip install --user pipx && python -m pipx ensurepath && pipx install uv
EOF
