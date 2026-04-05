"""Page registry — auto-discovers page modules and returns unbound seeds."""

import importlib
from pathlib import Path

from engine.pageform import PageForm


def discover_pages() -> dict[str, PageForm]:
    """Import all page modules and return {key: unbound_definition}.

    Each .py file in this directory (except __init__.py) must export a
    `definition` — an unbound PageForm. The page key comes from the
    definition's key attribute, not the filename.

    The returned definitions are seeds — they hold no store binding and
    carry no runtime state.
    """
    pages = {}
    pages_dir = Path(__file__).parent
    for module_path in sorted(pages_dir.glob("*.py")):
        if module_path.name == "__init__.py":
            continue
        module = importlib.import_module(f"pages.{module_path.stem}")
        definition = module.definition
        pages[definition.key] = definition
    return pages


def bind_page(seed: PageForm, data_dir: Path, instance_id: str,
              label: str | None = None) -> PageForm:
    """Bind a seed to its store, producing a transient bound page."""
    bound = seed.bind(
        data_dir,
        scope=instance_id,
        url_prefix=f"/pages/{instance_id}",
    )
    if label is not None:
        bound.label = label
    return bound
