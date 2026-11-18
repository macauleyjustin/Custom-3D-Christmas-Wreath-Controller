"""Backward-compatible master effects CLI delegating to the unified ``controllights`` CLI."""

from controllights import main, resolve_controller, run_interactive_cli

__all__ = ["main", "resolve_controller", "run_interactive_cli"]

if __name__ == "__main__":
    raise SystemExit(main())
