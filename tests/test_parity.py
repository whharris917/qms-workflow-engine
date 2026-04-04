"""Parity test — verifies that every affordance URL in the JSON API
appears as an interactive element in the rendered HTML.

This is the structural guarantee that agents and humans see the same
action surface. It replaces the runtime mark_rendered() accounting
with a CI-time check that catches parity violations before merge.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

import pytest

from pages import discover_pages, bind_page


# ---- Fixtures ----

@pytest.fixture(scope="module")
def all_pages():
    """Bind all page definitions once per test module."""
    data_dir = Path("data")
    return {key: bind_page(seed, data_dir, key) for key, seed in discover_pages().items()}


# ---- Helpers ----

def extract_affordance_urls(data: dict) -> set[str]:
    """Recursively extract all affordance URLs from a serialized eigenform tree."""
    urls: set[str] = set()
    if not isinstance(data, dict):
        return urls
    for aff in data.get("affordances", []):
        url = aff.get("url", "")
        if url:  # skip disabled/empty-URL affordances
            urls.add(url)
    # Recurse into all nested structures
    for key, value in data.items():
        if key == "affordances":
            continue
        if isinstance(value, dict):
            urls |= extract_affordance_urls(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    urls |= extract_affordance_urls(item)
    return urls


class _DataAttrParser(HTMLParser):
    """Extract all data-ef-post/submit/change URLs from rendered HTML."""

    def __init__(self):
        super().__init__()
        self.urls: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        for name, val in attrs:
            if name in ("data-ef-post", "data-ef-submit", "data-ef-change"):
                if val:
                    self.urls.add(val)


def extract_html_action_urls(html: str) -> set[str]:
    """Extract all eigenform action URLs from rendered HTML."""
    parser = _DataAttrParser()
    parser.feed(html)
    return parser.urls


# ---- Tests ----

def test_all_pages_render(all_pages):
    """Every page must render without errors."""
    for key, pg in all_pages.items():
        try:
            pg.render()
        except Exception as e:
            pytest.fail(f"Page {key!r} failed to render: {e}")


def test_all_pages_serialize(all_pages):
    """Every page must serialize without errors."""
    for key, pg in all_pages.items():
        try:
            pg.serialize()
        except Exception as e:
            pytest.fail(f"Page {key!r} failed to serialize: {e}")


def test_affordance_parity(all_pages, page_key):
    """Every affordance URL in the JSON output must appear in the HTML output.

    This is the core parity guarantee: the agent's action surface and
    the human's action surface must match.
    """
    pg = all_pages[page_key]
    json_urls = extract_affordance_urls(pg.serialize())
    html_urls = extract_html_action_urls(pg.render())

    missing = json_urls - html_urls
    if missing:
        formatted = "\n  ".join(sorted(missing))
        pytest.fail(
            f"Page {page_key!r}: {len(missing)} affordance URL(s) in JSON "
            f"but not in HTML:\n  {formatted}"
        )


def pytest_generate_tests(metafunc):
    """Dynamically parametrize test_affordance_parity with all page keys."""
    if "page_key" in metafunc.fixturenames:
        pages = discover_pages()
        metafunc.parametrize("page_key", sorted(pages.keys()))
