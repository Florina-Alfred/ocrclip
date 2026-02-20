AGENTS — Bot & Developer Guidelines
=================================

Purpose
-------
This file documents useful commands and a concise code-style guide for agentic
coding assistants (and humans) working in this repository. It is intentionally
practical: commands you can run, conventions used in `src/main.py`, and
recommendations for safe edits, testing, and packaging.

Repository layout (important files)
- `src/main.py` — main application code (GUI, screenshot, OCR glue)
- `requirements.txt` — runtime dependencies
- `.venv/` — local virtualenv (committed here; prefer ignoring in forks)
 - `.venv/` — local virtualenv (committed here; prefer ignoring in forks). Note: repo now includes a `.gitignore` recommendation to avoid committing `.venv`.

Quick start / build / run
-------------------------
Create a virtualenv and install deps (preferred: `uv`):

```bash
# recommended (uv manages venv creation & installs per pyproject.toml)
uv .venv --activate --install

# fallback (plain virtualenv + pip)
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip setuptools wheel
pip install -e .            # installs lite deps
```
```

- Run the app (developer mode):

```bash
python3 -m src.main
# or, explicitly using the venv python
.venv/bin/python3 -m src.main
```

- Build a single-file executable (example using PyInstaller):

```bash
# PyInstaller will require additional work for PySide6 plugins on some OSes.
pip install pyinstaller
pyinstaller --name ocrclip --onefile src/main.py
```

Linting / Formatting / Static checks
-----------------------------------
We don't enforce a heavy toolchain in-tree, but the recommended set is:

- ruff for linting/fast fixes
- black for formatting
- isort for import ordering
- mypy for optional static typing checks
 - uv (recommended) or a PEP-621-compatible `pyproject.toml` — this repo now includes a `pyproject.toml` and optional extras for `full` and `dev` installs

Install locally (use .venv/ created by `uv`):

```bash
.venv/bin/pip install ruff black isort mypy
```

Common commands:

```bash
# lint check
ruff check src

# auto-fix fixes where supported
ruff check --fix src

# format
black src
isort src

# static typing
mypy src
```

Testing
-------
There are no tests currently committed, but follow these conventions when you
add tests. Use `pytest` (widely used, simple fixtures, and good plugin support).

Install: `.venv/bin/pip install pytest pytest-qt` (use `pytest-qt` for GUI-related tests).

Run all tests:

```bash
pytest -q
```

Run a single test file:

```bash
pytest tests/test_example.py -q
```

Run a single test case (function or method):

```bash
# by node id (recommended)
pytest tests/test_example.py::test_some_behavior -q

# or by -k substring match
pytest -k "some_behavior" -q
```

Or with unittest style:

```bash
python -m unittest tests.test_example.TestClass.test_method
```

If tests touch Qt, run them with a display or use headless CI (Xvfb) or
`pytest-qt`'s helpers to create a QApp fixture. Use the venv-managed pytest
binary: `.venv/bin/pytest`.

Signals for agents: When testing code that uses `TrayApp` or `SnipOverlay`,
prefer to inject a fake `reader` into `TrayApp(app, reader, args)` so OCR is
deterministic and fast.

Environment variables
---------------------
- `OCRCLIP_LOG` — if set, overrides the log file path used by the app. Default
  is `/tmp/ocrclip.log` in the code. Use this in CI to capture logs.

Agent workflow note
-------------------
This repository standardizes on `uv` for environment management. Agents and
developers should use `uv` in scripts and CI to create and manage `.venv` and
to install dependencies from `pyproject.toml`. Do not use `pip` directly to
install project dependencies in the repo; use `.venv/bin/pip` only to install
or pin additional tools inside the created venv.

Code style guidelines (applies to new edits)
-------------------------------------------
Follow idiomatic modern Python + Qt best-practices. The rules below are
intended to keep changes safe and easy for automated agents.

Imports
- Standard library imports first, then third-party, then local imports.
- Separate groups with a single blank line.
- Keep imports grouped and sorted alphabetically within groups — use `isort`.
- Prefer explicit imports for Qt modules, e.g. `from PySide6 import QtCore, QtGui, QtWidgets`.

Formatting
- Use `black` formatting (default settings). Keep line length to `88` unless
  there's a good reason to increase it.
- Use f-strings for string interpolation.
- Use trailing commas for multi-line collections/literals to make diffs cleaner.

Types
- Add type hints for public functions, methods, and class attributes where it
  improves readability and testability. Aim for gradual typing — prefer
  specific types over `Any` when possible.
- Annotate Qt callbacks where useful (e.g. `event: QtGui.QMouseEvent`).
- For complex data structures use `typing` (e.g. `list[str]`, `Optional[Image.Image]`).

Naming
- Variables & functions: `snake_case`
- Classes: `PascalCase`
- Constants and environment variables: `UPPER_SNAKE_CASE`
- Signals: name them as verbs or verb phrases (e.g. `ocr_finished`) and keep
  them lowercase/snake_case to match code in `src/main.py`.

Error handling & logging
- Avoid bare `except:`. Always catch specific exceptions when practical.
- When you must catch a broad exception, use `except Exception as e:` and
  `logging.exception("context")` to preserve traceback.
- Prefer `logging` over `print()` for messages the app will rely on. `print()`
  is acceptable in quick dev/debug helpers but prefer replacement with logging
  before landing changes.
- Never swallow exceptions silently — either handle them or log them with
  context. If intentionally ignoring an exception, add a comment explaining why.

Concurrency & Qt thread-safety
- Never touch Qt widgets or application state from a non-GUI thread.
- Use Qt signals (or `QMetaObject.invokeMethod` / `QTimer.singleShot(0, ...)`)
  to marshal results back to the GUI thread. `TrayApp.ocr_finished` pattern is
  the correct approach used in `src/main.py`.
- Background threads should be `daemon=True` unless you explicitly need to
  join them during shutdown.

Design for testability
- Prefer dependency injection: pass an `easyocr` reader-like object to
  `TrayApp` (the code already supports this). In tests provide a fake object
  with a `readtext(img)` method.
- Decouple I/O and side-effects (clipboard, OS hotkeys) behind small wrappers
  or by mocking them in tests.

Small, focused changes
- Keep edits small and focused. Separate refactors from feature work.
- If you change behavior, update or add tests demonstrating the new behavior.

Qt / GUI specifics and gotchas
- The code uses `QtCore.Signal` declarations and emits strings/bytes across
  threads. Keep emitted payloads simple (primitive types, bytes, or small
  serializable objects) to avoid cross-thread ownership issues.
- When capturing screen regions, the code hides the overlay before grabbing to
  avoid self-capture. Preserve that behavior when refactoring.

Packaging & CI
- Building binaries with PyInstaller often needs extra plugin packaging for
  `PySide6` and shaders. Test on target OS and include runtime hooks as
  required by PyInstaller.

Cursor / Copilot rules
----------------------
No Cursor rules found in `.cursor/` or `.cursorrules` in this repository.
No Copilot rules found in `.github/copilot-instructions.md`.

If you add such files, document the location and any agent-facing instructions
here (the agent should re-read this file after those files change).

Safety / git hygiene for agents
------------------------------
- Do not modify files outside the targeted change unless explicitly asked.
- Do not commit secrets or large binary files. If a credentials file is added
  accidentally, alert a human.
- When making commits provide a short, clear commit message describing the
  why (not just the what). Example: `fix(ui): avoid self-capture when snipping`.

Where to look first in this repo
--------------------------------
- `src/main.py` — study it before changing UI/workflow: it contains the core
  application flow, background reader wrapper, and threading model.
- `requirements.txt` — runtime dependencies to install in CI or locally.

If you are blocked
------------------
- If a change is destructive (data/loss/permissions), ask a human.
- If a native dependency (e.g. PyTorch GPU setup) is required, prefer
  documenting reproducible steps in `README.md` rather than embedding them
  into automation without approval.

Common commands recap
---------------------
```bash
# setup
    ./scripts/dev-setup.sh

# run app
python3 -m src.main

# run single pytest test
pytest tests/test_module.py::test_name -q

# lint & format
ruff check --fix src && black src && isort src
```

— End of AGENTS guidelines —
