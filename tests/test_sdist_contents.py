import subprocess
import sys
import tarfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_sdist_includes_docs_and_tutorials(tmp_path: Path):
    pytest.importorskip("build")
    dist_dir = tmp_path / "dist"
    result = subprocess.run(
        [sys.executable, "-m", "build", "--sdist", "--outdir", str(dist_dir)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    archives = list(dist_dir.glob("*.tar.gz"))
    assert len(archives) == 1
    root = archives[0].name.removesuffix(".tar.gz")
    with tarfile.open(archives[0]) as archive:
        names = set(archive.getnames())

    required = [
        "README.md",
        "mkdocs.yml",
        "docs/index.md",
        "docs/assets/aaax-logo-text-black.png",
        "docs/assets/aaax-logo-text-white.png",
        "docs/composition/index.md",
        "docs/concepts/strategies.md",
        "docs/javascripts/mermaid-init.20260629.js",
        "docs/javascripts/vendor/mermaid.min.js",
        "docs/javascripts/vendor/mermaid-LICENSE.txt",
        "docs/launch/index.md",
        "docs/overrides/partials/header.html",
        "docs/reference/cli.md",
        "docs/stylesheets/custom.20260629.css",
        "docs/tutorials/channel-events.md",
        "docs/tutorials/compose-packages.md",
        "docs/tutorials/serve-package.md",
        "docs/tutorials/tactic-endpoint.md",
    ]
    missing = [path for path in required if f"{root}/{path}" not in names]

    assert not missing
    assert not any(name.startswith(f"{root}/site/") for name in names)
