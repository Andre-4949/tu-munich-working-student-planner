"""Entry point: python -I scripts/plan.py <export.csv> [options]. See planner/cli.py for the options."""

import sys
from pathlib import Path

# Isolated mode (-I) keeps the script folder off sys.path, so add the project root explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from planner.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
