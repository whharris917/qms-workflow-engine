"""Page registry — auto-discovers page modules and binds their definitions."""

import importlib
from pathlib import Path


def build_pages(data_dir: Path) -> dict:
    """Import all page modules, bind their definitions, return {key: PageForm}.

    Each .py file in this directory (except __init__.py) must export a
    `definition` — an unbound PageForm. The page key comes from the
    definition's key attribute, not the filename.
    """
    pages = {}
    pages_dir = Path(__file__).parent
    for module_path in sorted(pages_dir.glob("*.py")):
        if module_path.name == "__init__.py":
            continue
        module = importlib.import_module(f"pages.{module_path.stem}")
        definition = module.definition
        page_key = definition.key
        pages[page_key] = definition.bind(
            data_dir=data_dir,
            scope=page_key,
            url_prefix=f"/pages/{page_key}",
        )
    return pages
