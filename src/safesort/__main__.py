"""Allows running SafeSort as ``python -m safesort``."""

from __future__ import annotations

import sys

from safesort.cli import main

if __name__ == "__main__":
    sys.exit(main())
