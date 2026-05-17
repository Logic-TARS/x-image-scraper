"""Backward-compatible root entry point for Playwright mode."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from xscrape.playwright_cli import main


if __name__ == "__main__":
    raise SystemExit(main())
