import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

import pytest


ROOT = Path(__file__).resolve().parents[1]
NAV_SECTIONS = ["Tutorials", "Strategy", "Shell", "Use with LLLM", "Reference"]
DOCS_SWITCH = [
    ("https://lllm.one/", "LLLM"),
    ("https://sssn.one/", "SSSN"),
    ("https://aaax.one/", "AAAX"),
]


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


def test_docs_use_strategy_shell_framing():
    sources = {
        "README": ROOT / "README.md",
        "home": ROOT / "docs" / "index.md",
        "strategies": ROOT / "docs" / "concepts" / "strategies.md",
        "launch": ROOT / "docs" / "concepts" / "launch-boundary.md",
        "package docstring": ROOT / "aaax" / "__init__.py",
        "package metadata": ROOT / "pyproject.toml",
        "metadata": ROOT / "mkdocs.yml",
    }
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in sources.values()
    )

    assert "strategy shell" in combined
    assert "built on LLLM" in combined
    assert "LLLM package" in combined
    assert "FastAPI" in combined
    assert "Advanced Autonomous Agentic ICS" not in combined
    assert "LibOS" not in combined
    assert "kernel" not in combined.lower()


def test_docs_build_with_shared_visual_contract(tmp_path: Path):
    site_dir = build_docs(tmp_path)
    index = (site_dir / "index.html").read_text(encoding="utf-8")
    css = (
        site_dir / "stylesheets" / "custom.20260702.css"
    ).read_text(encoding="utf-8")

    assert "AAAX" in index
    assert "psi-header-nav" in index
    for section in NAV_SECTIONS:
        assert section in index
    assert "Overview" not in index
    assert "aaax-shell" in index
    assert "aaax-logo-text-black.png" in index
    assert "aaax-logo-text-white.png" in index
    assert "aaax-logo-text-black.png" in css
    assert "aaax-logo-text-white.png" in css
    assert "background-color: #ffffff" in css
    assert "Space Mono" in css
    assert (site_dir / "CNAME").read_text(encoding="utf-8").strip() == "aaax.one"


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


def nav_pages(config: str) -> list[str]:
    return re.findall(r"^\s*-\s+(?:[^:\n]+:\s+)?([\w./-]+\.md)\s*$", config, re.M)


def test_docs_nav_sections_and_no_orphan_pages():
    config = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    nav = config.split("\nnav:\n", 1)[1].split("\n\n", 1)[0]

    # The header renders the top-level sections as tabs; the logo is the way
    # home, so there is no Home section and index.md stays out of the nav.
    assert re.findall(r"^  - ([^:\n]+):", nav, re.M) == NAV_SECTIONS
    assert "homepage: https://aaax.one/" in config
    pages = nav_pages(config)
    docs = ROOT / "docs"
    assert [page for page in pages if not (docs / page).is_file()] == []
    assert "index.md" not in pages
    assert pages[0] == "getting-started.md"
    all_pages = {
        path.relative_to(docs).as_posix()
        for path in docs.rglob("*.md")
        if "overrides" not in path.parts
    }
    assert sorted(all_pages - set(pages)) == ["index.md"]


def test_docs_header_has_section_tabs_and_switches_between_the_three_sites(tmp_path):
    site_dir = build_docs(tmp_path)
    config = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    switch = config.split("  docs_switch:\n", 1)[1].split("\n  social:", 1)[0]

    assert re.findall(r"title: (\w+)\n\s+url: (\S+)", switch) == [
        (title, url) for url, title in DOCS_SWITCH
    ]
    for page in (
        "index.html",
        "getting-started/index.html",
        "guides/lllm/index.html",
        "reference/cli/index.html",
    ):
        html = (site_dir / page).read_text(encoding="utf-8")
        header = html.split('class="psi-header-nav"', 1)[1].split("</div>", 1)[0]
        tabs = re.findall(r'class="psi-header-nav__link[^"]*">\s*(.*?)\s*</a>', header, re.S)
        menu = html.split('class="psi-doc-switch__menu"', 1)[1].split("</div>", 1)[0]
        docs = re.findall(r'<a href="([^"]+)" class="psi-doc-switch__link[^"]*">\s*(\w+)', menu)
        drawer = html.split('class="psi-drawer-sections"', 1)[1].split("</div>", 1)[0]
        drawer_links = re.findall(
            r'class="psi-drawer-sections__link[^"]*">\s*(.*?)\s*</a>', drawer, re.S
        )

        assert tabs == NAV_SECTIONS, page
        assert docs == DOCS_SWITCH, page
        assert drawer_links == NAV_SECTIONS + [title for _url, title in DOCS_SWITCH], page
        assert 'href="https://aaax.one/" title="AAAX" class="md-header__button md-logo"' in html
        assert re.search(r'psi-doc-switch__link--active">\s*AAAX', html), page


def test_public_text_uses_lllm_names():
    text_paths = [ROOT / "README.md"]
    text_paths.extend((ROOT / "docs").rglob("*.md"))
    text_paths.extend((ROOT / "docs" / "overrides").rglob("*.html"))
    text_paths.extend((ROOT / "aaax").rglob("*.py"))
    text_paths.extend([ROOT / "mkdocs.yml", ROOT / "pyproject.toml"])
    # PsiHub, psi.toml, psi:// refs, PsiCLI, and the PSI shell are gone:
    # packages are LLLM packages (lllm.toml, lllm:// refs), the CLI family is
    # lllm, and channel stores live in .lllm/network.
    gone = re.compile(
        r"psihub|psi\.toml|psi://|\.psi/|psicli|psisdk|prosi\.io/docs|psi_version"
        r"|PSI shell|aaax\[(?:integrations|packages|tactics)\]|\.sssn\b",
        re.IGNORECASE,
    )
    # The deprecated lllm.shell path is named only where the docs explain it.
    old_module = re.compile(r"(?<![\w./])lllm\.shell\b")

    for path in text_paths:
        text = path.read_text(encoding="utf-8")
        match = gone.search(text)
        assert match is None, f"{path.relative_to(ROOT)} mentions {match.group(0)}"
        if path != ROOT / "docs" / "guides" / "lllm.md":
            match = old_module.search(text)
            assert match is None, f"{path.relative_to(ROOT)} mentions {match.group(0)}"


def test_lllm_guide_covers_every_integration_point():
    guide = (ROOT / "docs" / "guides" / "lllm.md").read_text(encoding="utf-8")

    for text in (
        "add_tactic",
        "create_tactic_app",
        "CallContext",
        "coerce_tactic",
        "strategy_from_package",
        "lllm hub get demo/support-desk --dest vendor",
        '[project.entry-points."lllm.commands"]',
        'shell = "aaax.cli"',
        "lllm shell needs the aaax package: pip install aaax",
        "Channel stores need the sssn package: pip install sssn",
        "TacticProcessor",
        "/network/",
        "Resolver.from_config",
        "https://sssn.one/",
        "from aaax import ...",
    ):
        assert text in guide, text


def test_readme_and_docs_local_links_resolve():
    pattern = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
    text_paths = [ROOT / "README.md"]
    text_paths.extend((ROOT / "docs").rglob("*.md"))
    skip_prefixes = ("http://", "https://", "mailto:", "#")

    missing = []
    for path in sorted(text_paths):
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            target = match.group(1).strip()
            if not target or target.startswith(skip_prefixes) or "://" in target:
                continue
            target = target.split("#", 1)[0].split("?", 1)[0]
            if not target:
                continue
            if not (path.parent / unquote(target)).resolve().exists():
                missing.append(f"{path.relative_to(ROOT)} -> {match.group(1)}")

    assert missing == []


def test_docs_local_asset_references_resolve():
    patterns = [
        re.compile(r'\bsrc="([^"]+)"'),
        re.compile(r"url\([\"']?([^\"')]+)[\"']?\)"),
        re.compile(r"!\[[^\]]*\]\(([^)]+)\)"),
    ]
    text_paths = [ROOT / "README.md"]
    text_paths.extend((ROOT / "docs").rglob("*.md"))
    text_paths.extend((ROOT / "docs" / "stylesheets").glob("*.css"))
    skip_prefixes = ("http://", "https://", "mailto:", "data:", "#")

    missing = []
    for path in sorted(text_paths):
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            for match in pattern.finditer(text):
                target = match.group(1).strip()
                if (
                    not target
                    or target.startswith(skip_prefixes)
                    or "://" in target
                ):
                    continue
                target = target.split("#", 1)[0].split("?", 1)[0]
                if not target:
                    continue
                if not (path.parent / unquote(target)).resolve().exists():
                    missing.append(
                        f"{path.relative_to(ROOT)} -> {match.group(1)}"
                    )

    assert missing == []
