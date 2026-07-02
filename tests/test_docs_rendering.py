import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def build_docs(tmp_path: Path) -> Path:
    pytest.importorskip("mkdocs")
    site_dir = tmp_path / "site"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mkdocs",
            "build",
            "--strict",
            "--site-dir",
            str(site_dir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    return site_dir


def test_docs_use_strategy_launch_framing():
    sources = {
        "README": ROOT / "README.md",
        "home": ROOT / "docs" / "index.md",
        "strategies": ROOT / "docs" / "concepts" / "strategies.md",
        "launch": ROOT / "docs" / "concepts" / "launch-boundary.md",
        "metadata": ROOT / "mkdocs.yml",
    }
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in sources.values()
    )

    assert "PSI shell" in combined
    assert "PsiHub package" in combined
    assert "FastAPI" in combined
    assert "Advanced Autonomous Agentic ICS" not in combined
    assert "LibOS" not in combined
    assert "kernel" not in combined.lower()


def test_docs_build_with_shared_visual_contract(tmp_path: Path):
    site_dir = build_docs(tmp_path)
    index = (site_dir / "index.html").read_text(encoding="utf-8")
    css = (
        site_dir / "stylesheets" / "custom.20260629.css"
    ).read_text(encoding="utf-8")

    assert "AAAX" in index
    assert "psi-header-nav" in index
    assert "Overview" in index
    assert "Composition" in index
    assert "Shell" in index
    assert "aaax-shell" in index
    assert "Tutorials" in index
    assert "Reference" in index
    assert "aaax-logo-text-black.png" in index
    assert "aaax-logo-text-white.png" in index
    assert "aaax-logo-text-black.png" in css
    assert "aaax-logo-text-white.png" in css
    assert "background-color: #ffffff" in css
    assert "Roboto Mono" in css


def test_docs_render_mermaid_as_local_diagram_containers(tmp_path: Path):
    site_dir = build_docs(tmp_path)
    html_pages = [
        (path, path.read_text(encoding="utf-8"))
        for path in sorted(site_dir.rglob("*.html"))
    ]
    diagram_pages = [
        path for path, html in html_pages if 'class="mermaid"' in html
    ]
    highlighted_pages = [
        path
        for path, html in html_pages
        if "language-mermaid" in html or "highlight-mermaid" in html
    ]

    assert diagram_pages
    assert not highlighted_pages

    for path in diagram_pages:
        html = path.read_text(encoding="utf-8")
        assert "javascripts/vendor/mermaid.min.js" in html
        assert "javascripts/mermaid-init.20260629.js" in html
        assert "cdn.jsdelivr" not in html
        assert "unpkg" not in html

    assert (site_dir / "javascripts" / "vendor" / "mermaid.min.js").exists()
    assert (
        site_dir / "javascripts" / "vendor" / "mermaid-LICENSE.txt"
    ).exists()
