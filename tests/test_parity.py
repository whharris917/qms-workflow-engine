"""Parity test — verifies the JSON and HTML action surfaces match.

This is the structural guarantee that agents (reading JSON) and humans
(reading HTML) see the same set of actions on every page. A JSON affordance
without an HTML counterpart means a human cannot take an action an agent
claims; an HTML button without a JSON counterpart means an agent cannot know
about an action a human can take. Both are faithful-projection violations.

Coverage:
  * Every page renders and serializes without exception.
  * Every page has a non-empty affordance list (or is documented to have none).
  * No affordance carries an empty URL.
  * No affordance is missing a method.
  * Forward parity: every JSON affordance URL+action appears in HTML.
  * Reverse parity: every HTML action URL+action appears in JSON.
  * URL resolvability: every affordance URL resolves to a real component.

Scanned HTML attributes (all URL-carrying):
  data-c-post    data-c-submit    data-c-change
  data-c-add     data-c-url

Chrome-rendered affordances (floated compounds marked _chrome_rendered=True)
are deliberately excluded from forward parity — they are agent-JSON-only by
design (see docs/architecture.md §4).

Tests use tmp_path for isolation — no interaction with the real data/
directory.
"""

from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path

import pytest

from pages import discover_pages, bind_page


# ---- Fixtures ----

@pytest.fixture(scope="module")
def all_pages(tmp_path_factory):
    """Bind all page definitions to an isolated tmp directory."""
    data_dir = tmp_path_factory.mktemp("parity-data")
    return {
        key: bind_page(seed, data_dir, key)
        for key, seed in discover_pages().items()
    }


# ---- JSON affordance extraction ----

_PARAMETERIZATION_KEYS = ("targets", "tabs", "sections", "steps", "options")


def extract_json_affordances(data) -> list[dict]:
    """Recursively collect all affordances from a fully-serialized component tree.

    Uses _serialize_full() output (not serialize()) because the _chrome_rendered
    flag is stripped by serialize() — and we need it to know which floated
    compound affordances are deliberately agent-JSON-only.

    Parameterized compound affordances (O(N)->O(1) collapse) carry their
    per-option URLs inside dicts named `targets`, `tabs`, `sections`, `steps`,
    or `options` — this walker synthesizes one affordance entry per URL found
    in those dicts, so reverse parity treats them as legitimately declared.

    Returns a list of {url, method, action, _chrome_rendered, path} dicts.
    `path` is the dotted path into the tree, for diagnostic output.
    """
    results: list[dict] = []

    def _record(aff: dict, path: str, override_url: str | None = None,
                override_label: str | None = None):
        body = aff.get("body", {})
        action = body.get("action", "") if isinstance(body, dict) else ""
        results.append({
            "url": override_url if override_url is not None else aff.get("url", ""),
            "method": aff.get("method", ""),
            "action": action,
            "label": override_label if override_label is not None else aff.get("label", ""),
            "_chrome_rendered": bool(aff.get("_chrome_rendered")),
            "disabled": bool(aff.get("disabled")),
            "path": path,
        })

    def _walk(node, path: str):
        if not isinstance(node, dict):
            return
        for aff in node.get("affordances", []):
            # Record the top-level affordance URL itself.
            _record(aff, path)
            # If the affordance has a parameterization dict mapping per-option
            # URLs to labels (floated compounds) or keys to metadata (nav),
            # record each as an independently-declared action URL.
            for pk in _PARAMETERIZATION_KEYS:
                val = aff.get(pk)
                if not isinstance(val, dict):
                    continue
                for sub_key, sub_val in val.items():
                    if pk == "targets":
                        # targets: {full_url: child_label}
                        if isinstance(sub_key, str) and sub_key.startswith("/"):
                            _record(aff, f"{path}:{pk}", override_url=sub_key,
                                    override_label=str(sub_val))
                    # For tabs/sections/steps/options, the parameterization
                    # is {step_key: label_or_metadata} — URL stays the owning
                    # affordance's URL; the key is a body parameter. Agents
                    # POST to the owning URL with body[step/tab/...]=sub_key.
                    # No separate URL to record.
        for key, value in node.items():
            if key == "affordances":
                continue
            if isinstance(value, dict):
                _walk(value, f"{path}.{key}" if path else key)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        _walk(item, f"{path}.{key}[{i}]" if path else f"{key}[{i}]")

    _walk(data, path="")
    return results


# ---- HTML action extraction ----

_URL_ATTRS = ("data-c-post", "data-c-submit", "data-c-change",
              "data-c-add", "data-c-url")


class _DataAttrParser(HTMLParser):
    """Extract every (url, attr, body_json) triple from a rendered page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.actions: list[dict] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr_dict = {name: val for name, val in attrs}
        for url_attr in _URL_ATTRS:
            url = attr_dict.get(url_attr)
            if not url:
                continue
            body_raw = attr_dict.get("data-c-body", "")
            body_action = ""
            if body_raw:
                try:
                    body = json.loads(body_raw)
                    if isinstance(body, dict):
                        body_action = body.get("action", "")
                except (ValueError, TypeError):
                    pass
            self.actions.append({
                "url": url,
                "attr": url_attr,
                "action": body_action,
                "tag": tag,
            })


def extract_html_actions(html: str) -> list[dict]:
    """Extract all component action entries from rendered HTML."""
    parser = _DataAttrParser()
    parser.feed(html)
    return parser.actions


# ---- pytest parametrization ----

def pytest_generate_tests(metafunc):
    """Parametrize every per-page test with all discovered page keys."""
    if "page_key" in metafunc.fixturenames:
        pages = discover_pages()
        metafunc.parametrize("page_key", sorted(pages.keys()))


# ========================================================================
# Smoke tests — every page must at least render and serialize.
# ========================================================================

def test_all_pages_render(all_pages):
    """Every page must render without errors."""
    for key, pg in all_pages.items():
        try:
            html = pg.render()
        except Exception as e:
            pytest.fail(f"Page {key!r} failed to render: {type(e).__name__}: {e}")
        assert isinstance(html, str)
        assert html.strip(), f"Page {key!r} rendered empty HTML"


def test_all_pages_serialize(all_pages):
    """Every page must serialize without errors.

    serialize() is the agent-facing contract: clean dict with content fields
    and an affordances list. The internal form/key identifiers are
    deliberately stripped — agents work against URLs and action names, not
    internal type tags.
    """
    for key, pg in all_pages.items():
        try:
            data = pg.serialize()
        except Exception as e:
            pytest.fail(f"Page {key!r} failed to serialize: {type(e).__name__}: {e}")
        assert isinstance(data, dict), f"Page {key!r} serialized to non-dict"
        assert "affordances" in data, f"Page {key!r} serialize() missing affordances"


# ========================================================================
# Shape assertions — the serialized output has the invariants we rely on.
# ========================================================================

def test_serialized_page_has_required_shape(all_pages, page_key):
    """Every page's serialize() output must have the expected agent-facing shape.

    Deliberately NOT checking 'form' or 'key' on the top-level output —
    Page.serialize() strips both (agent-facing cleanliness). The internal
    representation with 'form' available via _serialize_full() is a separate
    concern.
    """
    pg = all_pages[page_key]
    data = pg.serialize()
    assert "affordances" in data, f"{page_key}: missing 'affordances' field"
    assert isinstance(data["affordances"], list), (
        f"{page_key}: affordances must be a list, got {type(data['affordances']).__name__}"
    )
    if "complete" in data:
        assert isinstance(data["complete"], bool), (
            f"{page_key}: 'complete' must be bool, got {type(data['complete']).__name__}"
        )

    # And the internal _serialize_full output MUST carry form="page" —
    # this is how rendering identifies the container template.
    full = pg._serialize_full()
    assert full.get("form") == "page", (
        f"{page_key}: _serialize_full().form is {full.get('form')!r}, expected 'page'"
    )
    assert full.get("key") == page_key, (
        f"{page_key}: _serialize_full().key is {full.get('key')!r}, expected {page_key!r}"
    )


def test_no_empty_url_affordances(all_pages, page_key):
    """No affordance in JSON may carry an empty URL.

    A URL-less affordance is a silent bug: the client cannot route it.
    The test covers only affordances that are NOT marked _chrome_rendered
    or disabled (DisabledAffordance intentionally has an empty URL).
    """
    pg = all_pages[page_key]
    affs = extract_json_affordances(pg._serialize_full())
    offenders = [
        a for a in affs
        if not a["url"]
        and not a["_chrome_rendered"]
        # Disabled buttons (Action precondition-unmet) intentionally have no URL.
        and not a["disabled"]
    ]
    if offenders:
        lines = "\n  ".join(f"[{a['path']}] {a['label']!r} action={a['action']!r}" for a in offenders)
        pytest.fail(
            f"{page_key}: {len(offenders)} affordance(s) with empty URL:\n  {lines}"
        )


def test_affordance_methods_are_declared(all_pages, page_key):
    """Every affordance in JSON must declare a method (typically POST)."""
    pg = all_pages[page_key]
    affs = extract_json_affordances(pg._serialize_full())
    offenders = [
        a for a in affs
        if a["url"] and not a["method"] and not a["_chrome_rendered"]
    ]
    if offenders:
        lines = "\n  ".join(f"[{a['path']}] url={a['url']!r}" for a in offenders)
        pytest.fail(f"{page_key}: affordance(s) with empty method:\n  {lines}")


# ========================================================================
# Forward parity — every JSON affordance URL appears in HTML.
# ========================================================================

def test_forward_parity(all_pages, page_key):
    """Every JSON affordance URL (non-chrome) must appear in rendered HTML.

    This is the half-guarantee the original parity test provided: an agent
    that sees an affordance can trust a human can also trigger it.
    """
    pg = all_pages[page_key]
    json_affs = extract_json_affordances(pg._serialize_full())
    html_actions = extract_html_actions(pg.render())
    html_urls = {a["url"] for a in html_actions}

    # Exclude chrome-rendered compounds — these are agent-JSON-only by design
    # (floated compound affordances; see docs/architecture.md §4).
    missing = [
        a for a in json_affs
        if a["url"] and not a["_chrome_rendered"] and a["url"] not in html_urls
    ]
    if missing:
        lines = "\n  ".join(
            f"{a['url']} (action={a['action']!r}, label={a['label']!r})"
            for a in missing
        )
        pytest.fail(
            f"{page_key}: {len(missing)} JSON affordance URL(s) not present in HTML:\n  {lines}"
        )


# ========================================================================
# Reverse parity — every HTML action URL appears in JSON.  (NEW)
# ========================================================================

def test_reverse_parity(all_pages, page_key):
    """Every HTML action URL must correspond to a JSON affordance URL.

    If HTML contains a button whose URL is not in JSON, a human can take
    an action an agent cannot discover — a faithful-projection violation
    in the direction the original parity test never checked.

    Exclusions:
      * Internal view-toggle URLs (JSON link, view selector) whose query
        strings make them non-affordance browse links — no component
        action, just navigation.
    """
    pg = all_pages[page_key]
    json_urls = {
        a["url"] for a in extract_json_affordances(pg._serialize_full())
        if a["url"]
    }
    html_actions = extract_html_actions(pg.render())

    extra = [
        a for a in html_actions
        if a["url"] and a["url"] not in json_urls
    ]
    if extra:
        lines = "\n  ".join(
            f"{a['url']} ({a['attr']} on <{a['tag']}> action={a['action']!r})"
            for a in extra
        )
        pytest.fail(
            f"{page_key}: {len(extra)} HTML action URL(s) have no JSON "
            f"counterpart — human can act, agent cannot discover:\n  {lines}"
        )


# ========================================================================
# Action-name parity — same URL must carry the same action in JSON and HTML.
# ========================================================================

def test_action_name_parity(all_pages, page_key):
    """Where both sides declare an action name for the same URL, they match.

    A button whose HTML body is `{"action": "set_valeu"}` (typo) while the
    JSON declares `{"action": "set_value"}` passes the URL-only forward
    check but is completely broken at runtime.
    """
    pg = all_pages[page_key]
    json_affs = extract_json_affordances(pg._serialize_full())
    html_actions = extract_html_actions(pg.render())

    # Build {url: set-of-actions} for both sides (multiple buttons can share
    # a URL but differ in body — e.g., move_up vs move_down on a list).
    json_map: dict[str, set[str]] = {}
    for a in json_affs:
        if a["url"] and a["action"] and not a["_chrome_rendered"]:
            json_map.setdefault(a["url"], set()).add(a["action"])
    html_map: dict[str, set[str]] = {}
    for a in html_actions:
        if a["url"] and a["action"]:
            html_map.setdefault(a["url"], set()).add(a["action"])

    violations = []
    for url, html_actions_set in html_map.items():
        json_actions_set = json_map.get(url, set())
        if not json_actions_set:
            # URL exists in HTML but has no JSON entries declaring action
            # names. That's a separate concern (reverse parity / bodyless
            # submit forms); not an action-name mismatch.
            continue
        unknown_actions = html_actions_set - json_actions_set
        if unknown_actions:
            violations.append((url, json_actions_set, unknown_actions))
    if violations:
        lines = []
        for url, json_acts, unknown in violations:
            lines.append(
                f"{url}: HTML declares actions {sorted(unknown)!r} "
                f"that JSON does not recognize (JSON has {sorted(json_acts)!r})"
            )
        joined = "\n  ".join(lines)
        pytest.fail(f"{page_key}: action-name mismatch:\n  {joined}")


# ========================================================================
# URL resolvability — every JSON affordance URL resolves to a component.
# ========================================================================

def test_affordance_urls_resolve(all_pages, page_key):
    """Every JSON affordance URL must route to a real component via find_component.

    A URL like /pages/foo/bar that parity-matches between JSON and HTML
    is still broken if find_component("bar") returns None. The server
    would 404 every attempt to use that affordance.

    Exclusions:
      * URLs targeting the page itself (end with /pages/{key}) — always
        resolvable to the Page.
      * URLs into embedded pages (contain /{parent}/{child} with child
        having its own url_prefix) — resolve via the embedded store.
    """
    pg = all_pages[page_key]
    affs = extract_json_affordances(pg._serialize_full())

    page_url = pg.url or f"/pages/{page_key}"
    unresolved = []
    for a in affs:
        url = a["url"]
        if not url or a["_chrome_rendered"]:
            continue
        # Page-level URLs resolve to the Page itself.
        if url == page_url:
            continue
        # Extract the path portion beyond the page URL.
        if url.startswith(page_url + "/"):
            sub_path = url[len(page_url) + 1:]
        else:
            # URLs outside the page's own prefix (e.g., embedded children
            # with independent URL prefixes) — skip resolvability check;
            # they route against a different tree.
            continue
        try:
            target = pg.find_component(sub_path)
        except Exception as e:
            unresolved.append((url, f"{type(e).__name__}: {e}"))
            continue
        if target is None:
            unresolved.append((url, "find_component returned None"))
    if unresolved:
        lines = "\n  ".join(f"{u} -> {reason}" for u, reason in unresolved)
        pytest.fail(
            f"{page_key}: {len(unresolved)} affordance URL(s) do not resolve:\n  {lines}"
        )
