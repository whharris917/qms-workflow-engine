"""Page registry — auto-discovers page_*.py modules and binds their definitions."""

import importlib
from pathlib import Path


def build_pages(data_dir: Path) -> dict:
    """Import all page_*.py modules, bind their definitions, return {key: PageForm}."""
    pages = {}
    pages_dir = Path(__file__).parent
    for module_path in sorted(pages_dir.glob("page_*.py")):
        # page_1.py -> page-1
        page_key = module_path.stem.replace("_", "-")
        module = importlib.import_module(f"pages.{module_path.stem}")
        definition = module.definition
        pages[page_key] = definition.bind(
            data_dir=data_dir,
            scope=page_key,
            url_prefix=f"/pages/{page_key}",
        )
    return pages
