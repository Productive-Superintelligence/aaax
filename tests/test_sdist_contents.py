import subprocess
import sys
import tarfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_sdist_includes_docs_and_examples(tmp_path: Path):
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
        "CHANGELOG.md",
        "README.md",
        "assets/aaax-logo-text-black.png",
        "assets/aaax-logo-text-white.png",
        "mkdocs.yml",
        # setuptools ships tests/test*.py; they import tests/helpers.py, and
        # the deploy test reads the deploy script and the Firebase config.
        "tests/test_channels.py",
        "tests/helpers.py",
        "tests/test_deploy_firebase_hosting.py",
        ".firebaserc",
        "firebase.json",
        "scripts/deploy_firebase_hosting.py",
        "docs/index.md",
        "docs/assets/aaax-logo-text-black.png",
        "docs/assets/aaax-logo-text-white.png",
        "docs/strategies.md",
        "docs/packages.md",
        "docs/concepts.md",
        "docs/serving.md",
        "docs/javascripts/mermaid-init.20260629.js",
        "docs/javascripts/vendor/mermaid.min.js",
        "docs/javascripts/vendor/mermaid-LICENSE.txt",
        "docs/agents.md",
        "docs/channels.md",
        "docs/overrides/partials/header.html",
        "docs/api/index.md",
        "docs/api/cli.md",
        "docs/api/http-api.md",
        "docs/stylesheets/custom.20260702.css",
        "docs/examples/index.md",
        "docs/examples/support-desk.md",
        "scripts/docs_hooks.py",
    ]
    missing = [path for path in required if f"{root}/{path}" not in names]

    assert not missing
    assert not any(name.startswith(f"{root}/site/") for name in names)
