from __future__ import annotations

import sys
from pathlib import Path


def pytest_configure(config) -> None:
    config.addinivalue_line("markers", "asyncio: mark test as async")


ROOT = Path(__file__).resolve().parents[2]
for framework_dir in (ROOT, ROOT / "sssn", ROOT / "lllm"):
    path = str(framework_dir)
    if path not in sys.path:
        sys.path.insert(0, path)
