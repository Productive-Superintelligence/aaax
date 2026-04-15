from __future__ import annotations

import sys
from pathlib import Path


def ensure_vendor_paths() -> None:
    """Prefer vendored local framework repos when they exist in the workspace."""
    root = Path(__file__).resolve().parents[1]
    for name in ("sssn", "lllm"):
        candidate = root / name
        if not candidate.is_dir():
            continue
        path = str(candidate)
        if path not in sys.path:
            sys.path.insert(0, path)
