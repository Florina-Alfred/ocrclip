#!/usr/bin/env bash
set -euo pipefail

# scripts/cleanup_artifacts.sh
# Safely remove or move large build artifacts from the repository working tree.
# This script moves artifacts to a timestamped directory under $HOME by default
# and falls back to deleting them. It will NOT remove files that are tracked by
# git. Use --yes to run non-interactively.

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

BACKUP_BASE=${1:-}
FORCE=0
if [ "${BACKUP_BASE}" = "--yes" ]; then
  FORCE=1
  BACKUP_BASE=""
fi

while [ $# -gt 0 ]; do
  case "$1" in
    --yes|-y)
      FORCE=1
      shift
      ;;
    --move-to)
      shift
      BACKUP_BASE="$1"
      shift
      ;;
    *)
      shift
      ;;
  esac
done

TIMESTAMP=$(date +%Y%m%d%H%M%S)
BACKUP_DIR=${BACKUP_BASE:-"$HOME/ocrclip_artifacts_backup_$TIMESTAMP"}

TARGETS=(AppDir dist .venv artifacts)

echo "Repository root: $REPO_ROOT"
echo "Backup directory: $BACKUP_DIR"
echo

to_remove=()

for t in "${TARGETS[@]}"; do
  if [ -e "$t" ]; then
    # If git is tracking any files under this path, skip it to avoid removing
    # tracked content accidentally.
    tracked_count=$(git ls-files -- "$t" | wc -l | tr -d ' ')
    if [ "$tracked_count" -gt 0 ]; then
      echo "Skipping $t — contains $tracked_count tracked file(s) in git."
      continue
    fi

    size=$(du -sh "$t" 2>/dev/null | cut -f1 || echo "?")
    echo "Will remove (untracked) $t — size: $size"
    to_remove+=("$t")
  fi
done

if [ ${#to_remove[@]} -eq 0 ]; then
  echo "Nothing to remove. Working tree is clean of the usual large artifacts."
  exit 0
fi

if [ "$FORCE" -ne 1 ]; then
  echo
  echo "Run this script with --yes to proceed and move the above paths to: $BACKUP_DIR"
  echo "Or rerun with: $0 --yes --move-to /path/to/backup"
  exit 0
fi

mkdir -p "$BACKUP_DIR"

for p in "${to_remove[@]}"; do
  echo "Processing $p -> $BACKUP_DIR"
  # Prefer move to backup (preserve), fallback to sudo move or sudo delete.
  if mv "$p" "$BACKUP_DIR/" 2>/dev/null; then
    echo "Moved $p -> $BACKUP_DIR/"
    continue
  fi

  echo "Move failed (permission?), attempting sudo move..."
  if sudo mv "$p" "$BACKUP_DIR/" 2>/dev/null; then
    echo "Moved (sudo) $p -> $BACKUP_DIR/"
    continue
  fi

  echo "sudo move failed. Attempting sudo rm -rf (destructive)..."
  sudo rm -rf "$p"
  echo "Removed $p"
done

echo
echo "Cleanup complete. Backups (if any) are under: $BACKUP_DIR"
echo "Double-check that no large files remain with: du -sh * | sort -h"
