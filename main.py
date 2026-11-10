"""Run Weather Stream backend + React using PyCharm's existing main configuration."""
from pathlib import Path
import runpy


if __name__ == "__main__":
    launcher = Path(__file__).resolve().parent / "source/scripts/run_dev.py"
    runpy.run_path(str(launcher), run_name="__main__")
