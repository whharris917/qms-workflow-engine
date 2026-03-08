"""WFE Web UI — minimal Flask application."""

from pathlib import Path

import markdown
from flask import Flask, render_template, abort

app = Flask(__name__)

QUALITY_MANUAL_DIR = Path(__file__).resolve().parent.parent.parent / "Quality-Manual"


def _build_manual_toc():
    """Build a structured table of contents from the Quality Manual directory."""
    sections = []

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


import re


def _rewrite_md_links(html, current_slug):
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
            # Go up one level from current dir
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


def _render_md(file_path, current_slug=""):
    """Read a markdown file and return HTML with rewritten links."""
    if not file_path.exists():
        return None
    text = file_path.read_text(encoding="utf-8")
    html = markdown.markdown(text, extensions=["tables", "fenced_code", "toc"])
    return _rewrite_md_links(html, current_slug)


@app.route("/")
def index():
    return render_template("index.html", active_page="home")


@app.route("/qms")
def qms():
    return render_template("qms.html", active_page="qms")


@app.route("/workspace")
def workspace():
    return render_template("workspace.html", active_page="workspace")


@app.route("/inbox")
def inbox():
    return render_template("inbox.html", active_page="inbox")


@app.route("/initiate")
def initiate():
    return render_template("initiate.html", active_page="home")


@app.route("/create/cr")
def create_cr():
    return render_template("create_cr.html", active_page="home")


@app.route("/manual")
def manual_index():
    toc = _build_manual_toc()
    return render_template("manual_index.html", active_page="manual", toc=toc)


@app.route("/manual/<path:slug>")
def manual_page(slug):
    file_path = QUALITY_MANUAL_DIR / f"{slug}.md"
    html_content = _render_md(file_path, current_slug=slug)
    if html_content is None:
        abort(404)
    toc = _build_manual_toc()
    title = file_path.stem.replace("-", " ").replace("_", " ")
    return render_template(
        "manual_page.html",
        active_page="manual",
        toc=toc,
        content=html_content,
        page_title=title,
        current_slug=slug,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
