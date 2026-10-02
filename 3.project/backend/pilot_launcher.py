"""Stable script entry point for C-Pilot.exe and scheduled tasks."""
from pathlib import Path
import sys

# Direct script execution adds backend/ to sys.path; package imports need its parent.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.launcher.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
