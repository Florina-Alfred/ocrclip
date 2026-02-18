"""Make the top-level `src` directory importable for tests and module runs.

This project exposes modules as `src.*` (e.g. `src.main`) and some tests
and entrypoints rely on that import path. An empty package ensures
`import src` works during test collection and when running `python -m src.main`.
"""

__all__ = []
