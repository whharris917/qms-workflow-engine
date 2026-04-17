"""Page registry — auto-discovers page modules and returns unbound seeds."""

import importlib
import sys
from pathlib import Path

from engine.pagecomponent import PageComponent


def discover_pages() -> dict[str, PageComponent]:
    """Import all page modules and return {key: unbound_definition}.

    Each .py file in this directory (except __init__.py) must export a
    `definition` — an unbound PageComponent. The page key comes from the
    definition's key attribute, not the filename.

    The returned definitions are seeds — they hold no store binding and
    carry no runtime state.

    Discovery is fresh on every call: modules are reloaded if already
    cached, and stale module cache entries (deleted files) are purged.
    """
    pages = {}
    pages_dir = Path(__file__).parent
    live_modules = set()
    for module_path in sorted(pages_dir.glob("*.py")):
        if module_path.name == "__init__.py":
            continue
        mod_name = f"pages.{module_path.stem}"
        live_modules.add(mod_name)
        if mod_name in sys.modules:
            module = importlib.reload(sys.modules[mod_name])
        else:
            module = importlib.import_module(mod_name)
        definition = module.definition
        pages[definition.key] = definition

    # Purge cached modules for deleted page files
    stale = [k for k in sys.modules if k.startswith("pages.") and k != "pages" and k not in live_modules]
    for k in stale:
        del sys.modules[k]

    return pages


def bind_page(seed: PageComponent, data_dir: Path, instance_id: str,
              label: str | None = None) -> PageComponent:
    """Bind a seed to its store, producing a transient bound page."""
    bound = seed.bind(
        data_dir,
        scope=instance_id,
        url_prefix=f"/pages/{instance_id}",
    )
    if label is not None:
        bound.label = label
    return bound
