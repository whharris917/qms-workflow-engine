"""Quality Manual rendering helpers.

Pure functions for building the TOC, rendering markdown, and rewriting
internal .md links to /manual/ routes.
"""

import re
from pathlib import Path

import markdown

QUALITY_MANUAL_DIR = Path(__file__).resolve().parent.parent.parent / "Quality-Manual"


def build_manual_toc() -> list[dict]:
    """Build a structured table of contents from the Quality Manual directory."""
    sections: list[dict] = []

    # Main numbered documents (sorted by filename)
    numbered = sorted(QUALITY_MANUAL_DIR.glob("[0-9]*.md"))
    for p in numbered:
        num, *rest = p.stem.split("-", 1)
        title = rest[0].replace("-", " ") if rest else p.stem
        sections.append({"slug": p.stem, "title": f"{num}. {title}", "category": "main"})

    # Key documents
    for name, title in [
        ("START_HERE", "Start Here"),
        ("QMS-Policy", "QMS Policy"),
        ("QMS-Glossary", "QMS Glossary"),
        ("FAQ", "FAQ"),
    ]:
        if (QUALITY_MANUAL_DIR / f"{name}.md").exists():
            sections.append({"slug": name, "title": title, "category": "key"})

    # Guides
    guides_dir = QUALITY_MANUAL_DIR / "guides"
    if guides_dir.exists():
        for p in sorted(guides_dir.glob("*.md")):
            title = p.stem.replace("-", " ").title()
            sections.append({"slug": f"guides/{p.stem}", "title": title, "category": "guides"})

    # Type references
    types_dir = QUALITY_MANUAL_DIR / "types"
    if types_dir.exists():
        for p in sorted(types_dir.glob("*.md")):
            sections.append({"slug": f"types/{p.stem}", "title": p.stem, "category": "types"})

    return sections


def _rewrite_md_links(html: str, current_slug: str) -> str:
    """Rewrite .md links to /manual/ routes.

    Handles patterns like:
      href="03-Workflows.md"           -> /manual/03-Workflows
      href="03-Workflows.md#section"   -> /manual/03-Workflows#section
      href="../07-Child-Documents.md"  -> /manual/07-Child-Documents
      href="CR.md"                     -> /manual/types/CR  (when inside types/)
      href="../QMS-Glossary.md"        -> /manual/QMS-Glossary
    """
    current_dir = str(Path(current_slug).parent) if "/" in current_slug else ""

    def _replace(match):
        raw_path = match.group(1)
        fragment = match.group(2) or ""

        # Resolve relative path against current document's directory
        if raw_path.startswith("../"):
            rel = raw_path[3:]  # strip ../
        elif current_dir:
            rel = f"{current_dir}/{raw_path}"
        else:
            rel = raw_path

        # Strip .md extension
        slug = rel.removesuffix(".md")

        # Normalize: remove any remaining ../
        parts = []
        for part in slug.split("/"):
            if part == "..":
                if parts:
                    parts.pop()
            elif part and part != ".":
                parts.append(part)
        slug = "/".join(parts)

        return f'href="/manual/{slug}{fragment}"'

    return re.sub(r'href="([^"]*?\.md)(#[^"]*)?(?:")', _replace, html)


def render_md(file_path: Path, current_slug: str = "") -> str | None:
    """Read a markdown file and return HTML with rewritten links."""
    if not file_path.exists():
        return None
    text = file_path.read_text(encoding="utf-8")
    html = markdown.markdown(text, extensions=["tables", "fenced_code", "toc"])
    return _rewrite_md_links(html, current_slug)


def render_md_file(file_path: Path) -> str | None:
    """Render a standalone markdown file to HTML (no link rewriting)."""
    if not file_path.exists():
        return None
    text = file_path.read_text(encoding="utf-8")
    return markdown.markdown(text, extensions=["tables", "fenced_code", "toc"])
