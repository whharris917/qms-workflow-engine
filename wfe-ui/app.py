"""WFE Web UI — minimal Flask application."""

import json
import time as _time
from pathlib import Path
from queue import Queue, Empty

import yaml
import markdown
from flask import Flask, render_template, abort, request, redirect, url_for, jsonify, Response

app = Flask(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Register the execution API blueprint
from api import api as api_blueprint  # noqa: E402
app.register_blueprint(api_blueprint)

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


def _list_crs():
    """List all CR data files, sorted by ID."""
    crs = []
    for p in sorted(DATA_DIR.glob("CR-*.json")):
        crs.append(json.loads(p.read_text(encoding="utf-8")))
    return crs


@app.route("/qms")
def qms():
    return render_template("qms.html", active_page="qms", crs=_list_crs())


@app.route("/workspace")
def workspace():
    return render_template("workspace.html", active_page="workspace", crs=_list_crs())


@app.route("/inbox")
def inbox():
    return render_template("inbox.html", active_page="inbox")


WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / "workflows"


def _list_workflows():
    """List all workflow YAML files with name and state."""
    workflows = []
    if WORKFLOWS_DIR.exists():
        import yaml
        for p in sorted(WORKFLOWS_DIR.glob("*.yaml")):
            try:
                data = yaml.safe_load(p.read_text(encoding="utf-8"))
                workflows.append({
                    "name": data.get("name", p.stem),
                    "state": data.get("state", "unknown"),
                })
            except Exception:
                workflows.append({"name": p.stem, "state": "error"})
    return workflows


@app.route("/initiate")
def initiate():
    return render_template("initiate.html", active_page="home", workflows=_list_workflows())


# --- Template Editor ---

DOCTYPES_DIR = Path(__file__).resolve().parent / "templates" / "doctypes"
DOCTYPES_DIR.mkdir(exist_ok=True)


def _list_templates():
    """List all template YAML files."""
    templates = []
    for p in sorted(DOCTYPES_DIR.glob("*.template.yaml")):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            templates.append({
                "slug": p.name.replace(".template.yaml", ""),
                "name": data.get("name", p.stem),
                "abbreviation": data.get("abbreviation", ""),
                "field_count": len(data.get("fields", [])),
            })
        except Exception:
            templates.append({"slug": p.stem, "name": p.stem, "abbreviation": "?", "field_count": 0})
    return templates


@app.route("/templates")
def template_list():
    return render_template("template_list.html", active_page="templates", templates=_list_templates())


@app.route("/template/<slug>")
def template_editor(slug):
    tpl_path = DOCTYPES_DIR / f"{slug}.template.yaml"
    if not tpl_path.exists():
        abort(404)
    tpl_data = yaml.safe_load(tpl_path.read_text(encoding="utf-8"))
    wf_path = DOCTYPES_DIR / f"{slug}.workflow.yaml"
    wf_data = yaml.safe_load(wf_path.read_text(encoding="utf-8")) if wf_path.exists() else None
    return render_template("template_editor.html", active_page="templates", slug=slug,
                           template_data=tpl_data, workflow_data=wf_data)


@app.route("/template/<slug>/save", methods=["POST"])
def template_save(slug):
    payload = request.get_json()
    if not payload:
        return {"ok": False, "error": "No data"}, 400
    tpl_data = payload.get("template")
    wf_data = payload.get("workflow")
    if tpl_data:
        path = DOCTYPES_DIR / f"{slug}.template.yaml"
        path.write_text(yaml.dump(tpl_data, default_flow_style=False, sort_keys=False, allow_unicode=True), encoding="utf-8")
    if wf_data:
        path = DOCTYPES_DIR / f"{slug}.workflow.yaml"
        path.write_text(yaml.dump(wf_data, default_flow_style=False, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return {"ok": True}


@app.route("/template/create", methods=["POST"])
def template_create():
    payload = request.get_json()
    name = payload.get("name", "").strip()
    abbreviation = payload.get("abbreviation", "").strip().upper()
    if not abbreviation:
        return {"ok": False, "error": "Abbreviation is required"}, 400
    slug = abbreviation
    path = DOCTYPES_DIR / f"{slug}.template.yaml"
    if path.exists():
        return {"ok": False, "error": f"Template {slug} already exists"}, 409
    data = {
        "name": name or f"{abbreviation} Document",
        "abbreviation": abbreviation,
        "id_format": f"{abbreviation}-{{number:03d}}",
        "fields": [],
    }
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return {"ok": True, "slug": slug}


def _next_cr_number():
    """Determine the next CR number by scanning existing data files."""
    existing = sorted(DATA_DIR.glob("CR-*.json"))
    if not existing:
        return 1
    # Extract the highest number from filenames like CR-001.json
    highest = max(int(p.stem.split("-")[1]) for p in existing)
    return highest + 1


def _load_cr(cr_id):
    """Load a CR's data from disk. Returns None if not found."""
    path = DATA_DIR / f"{cr_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save_cr(cr_id, data):
    """Save a CR's data to disk."""
    path = DATA_DIR / f"{cr_id}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


@app.route("/create/cr")
def create_cr():
    """Initiation stage — no CR ID yet."""
    return render_template("create_cr.html", active_page="home", stage="initiation", cr=None)


@app.route("/create/cr", methods=["POST"])
def initiate_cr():
    """Handle the Initiation form: assign a CR ID and persist initial data."""
    num = _next_cr_number()
    cr_id = f"CR-{num:03d}"
    data = {
        "id": cr_id,
        "stage": "definition",
        "title": request.form.get("title", "").strip(),
        "affects_code": request.form.get("affects_code") == "on",
        "affects_submodule": request.form.get("affects_submodule") == "on",
        "submodule": request.form.get("submodule", ""),
        "purpose": request.form.get("purpose", "").strip(),
        # Remaining fields empty until Change Definition stage
        "scope_context": "",
        "scope_changes": "",
        "scope_files": "",
        "current_state": "",
        "proposed_state": "",
        "change_description": "",
        "justification": "",
        "impact_files": "",
        "impact_documents": "",
        "impact_other": "",
        "testing_summary": "",
        "implementation_plan": "",
        "eis": [],
        "plan_columns": [],
        "plan_rows": [],
        "table_properties": {},
    }
    _save_cr(cr_id, data)
    return redirect(url_for("edit_cr", cr_id=cr_id))


@app.route("/cr/<cr_id>")
def edit_cr(cr_id):
    """Change Definition stage — full form, all fields editable."""
    data = _load_cr(cr_id)
    if data is None:
        abort(404)
    return render_template("create_cr.html", active_page="home", stage="definition", cr=data)


@app.route("/cr/<cr_id>/save", methods=["POST"])
def save_cr(cr_id):
    """Save all fields for an existing CR."""
    data = _load_cr(cr_id)
    if data is None:
        abort(404)
    # Update all fields from form
    for field in [
        "title", "purpose", "scope_context", "scope_changes", "scope_files",
        "current_state", "proposed_state", "change_description", "justification",
        "impact_files", "impact_documents", "impact_other",
        "testing_summary", "implementation_plan",
    ]:
        data[field] = request.form.get(field, "").strip()
    data["affects_code"] = request.form.get("affects_code") == "on"
    data["affects_submodule"] = request.form.get("affects_submodule") == "on"
    data["submodule"] = request.form.get("submodule", "")
    _save_cr(cr_id, data)
    return redirect(url_for("edit_cr", cr_id=cr_id))


@app.route("/cr/<cr_id>/plan")
def edit_plan(cr_id):
    """Implementation Plan editor — dedicated page."""
    data = _load_cr(cr_id)
    if data is None:
        abort(404)
    # Ensure plan fields exist (for CRs created before this feature)
    data.setdefault("plan_columns", [])
    data.setdefault("plan_rows", [])
    data.setdefault("table_properties", {})
    return render_template("edit_plan.html", active_page="home", cr=data)


@app.route("/cr/<cr_id>/plan/save", methods=["POST"])
def save_plan(cr_id):
    """Save the implementation plan table data."""
    data = _load_cr(cr_id)
    if data is None:
        abort(404)
    payload = request.get_json()
    data["plan_columns"] = payload.get("columns", [])
    data["plan_rows"] = payload.get("rows", [])
    data["table_properties"] = payload.get("tableProperties", {})
    data["eis"] = data["plan_rows"]  # keep eis in sync for the CR summary
    _save_cr(cr_id, data)
    return {"ok": True}


@app.route("/sandbox")
def sandbox():
    templates = _list_templates()
    return render_template("sandbox.html", active_page="sandbox", templates=templates)


# ── Agent Portal ──

# -- Workflow registry: per-workflow state, observers, history --

_WORKFLOW_STATE_DIR = DATA_DIR / "workflows"
_WORKFLOW_STATE_DIR.mkdir(exist_ok=True)

# In-memory state per workflow: observers and event history (not persisted)
_workflow_observers: dict[str, list[Queue]] = {}
_workflow_history: dict[str, list[dict]] = {}
_workflow_current_path: dict[str, str | None] = {}


def _wf_state_path(workflow_id: str) -> Path:
    """Return the on-disk JSON state file for a workflow."""
    return _WORKFLOW_STATE_DIR / f"{workflow_id}.state.json"


def _wf_load_state(workflow_id: str) -> dict:
    """Load workflow state from disk, or return empty dict if none."""
    p = _wf_state_path(workflow_id)
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {}


def _wf_save_state(workflow_id: str, data: dict):
    """Persist workflow state to disk."""
    p = _wf_state_path(workflow_id)
    with open(p, "w") as f:
        json.dump(data, f, indent=2)


def _wf_notify(workflow_id: str, event: dict):
    """Append event to history and push to all SSE observers for a workflow."""
    event.setdefault("timestamp", _time.time())
    hist = _workflow_history.setdefault(workflow_id, [])
    hist.append(event)
    if len(hist) > 500:
        _workflow_history[workflow_id] = hist[-500:]
    dead = []
    for q in _workflow_observers.get(workflow_id, []):
        try:
            q.put_nowait(event)
        except Exception:
            dead.append(q)
    for q in dead:
        _workflow_observers[workflow_id].remove(q)


def _compute_focus(before: dict, after: dict) -> dict:
    """Compute the Focus — the subset of the FoV that changed between two renders.

    Returns a dict with:
      message   — the action confirmation message (from the after FoV)
      changed   — fields whose value changed (same shape as state.fields)
      unlocked  — affordance labels that are new (not present in before)
      affordances — the full affordance objects for newly unlocked affordances
    """
    before_fields = (before.get("state") or {}).get("fields", {})
    after_fields = (after.get("state") or {}).get("fields", {})

    changed = {}
    for label, field in after_fields.items():
        old = before_fields.get(label)
        if old is None or old.get("value") != field.get("value"):
            changed[label] = field

    before_ids = {a["id"] for a in before.get("affordances", [])}
    before_labels = {a["label"] for a in before.get("affordances", [])}
    unlocked = []
    unlocked_affordances = []
    for a in after.get("affordances", []):
        if a["id"] not in before_ids and a["label"] not in before_labels:
            unlocked.append(a["label"])
            unlocked_affordances.append(a)

    return {
        "message": after.get("message"),
        "changed": changed,
        "unlocked": unlocked,
        "affordances": unlocked_affordances,
    }


# ---------------------------------------------------------------------------
# Dungeon Puzzle — rooms, items, hazards, combat, locked doors
# ---------------------------------------------------------------------------

_MAZE = {
    "entrance": {
        "title": "Entrance Hall",
        "description": "You stand in a cold stone entrance hall. Dim torchlight flickers across rough-hewn walls. A heavy wooden door is set into the east wall. To the south, a narrow staircase descends into darkness. A rusty iron torch sits in a bracket on the wall.",
        "exits": {"east": "corridor", "south": "cellar"},
        "items": ["torch"],
    },
    "corridor": {
        "title": "Stone Corridor",
        "description": "A long corridor stretches before you. Faded tapestries line the walls. You hear dripping water somewhere below. To the north, an archway opens into a larger space. East, a reinforced door stands ajar. A locked iron gate blocks the passage south — it has a large keyhole.",
        "exits": {"west": "entrance", "north": "gallery", "east": "armory"},
        "locked_exits": {"south": {"dest": "crypt", "key": "rusty_key", "desc": "Go south through the iron gate"}},
    },
    "gallery": {
        "title": "Portrait Gallery",
        "description": "Oil paintings line the walls; the portraits seem to watch you. Dust motes drift in shafts of light from high windows. A door to the east is marked 'LIBRARY'. A small glass bottle filled with red liquid sits on a shelf.",
        "exits": {"south": "corridor", "east": "library"},
        "items": ["potion"],
    },
    "library": {
        "title": "The Library",
        "description": "Floor-to-ceiling bookshelves crammed with moldering volumes. A reading desk holds an open journal. The last entry reads: 'The treasure lies beyond water and stone. Descend from the entrance, not from the armory — that way lies only the pit. The crypt key is hidden in the armory.'",
        "exits": {"west": "gallery", "south": "armory"},
    },
    "armory": {
        "title": "The Armory",
        "description": "Racks of rusted weapons line the walls. A few shields bear faded crests. The air smells of old iron. A heavy gate to the south has a warning scratched into the frame: 'BEWARE'. A sturdy sword leans against the far wall, and a battered shield hangs from a peg. Under a loose stone you spot a rusty key.",
        "exits": {"west": "corridor", "north": "library", "south": "guardroom"},
        "items": ["sword", "shield", "rusty_key"],
    },
    "guardroom": {
        "title": "The Guardroom",
        "description": "An abandoned guardpost. A table holds dice and empty tankards. The east passage slopes steeply downward — you feel a draft of warm, stale air. A dusty first-aid pouch sits on a chair.",
        "exits": {"north": "armory", "east": "pit"},
        "items": ["bandage"],
    },
    "pit": {
        "title": "The Pit",
        "description": "The floor gives way! You slide down a smooth stone chute, tumbling in darkness, and land hard on a pile of rubble.",
        "auto_move": "entrance",
        "damage": 3,
        "damage_msg": "The fall bruises you badly.",
    },
    "cellar": {
        "title": "The Cellar",
        "description": "A damp cellar. Broken barrels line the walls and the floor is slick with moisture. Water trickles east through a low archway. It is pitch dark here — you can barely see your own hands.",
        "exits": {"north": "entrance", "east": "cistern"},
        "dark": True,
        "dark_description": "It is too dark to see. You can feel a passage north (back up) and hear water to the east. There might be something on the ground, but you can't make it out.",
        "items": ["amulet"],
    },
    "cistern": {
        "title": "The Cistern",
        "description": "A circular chamber half-filled with dark, still water. The water channel feeds in from the west. Condensation covers the stone walls. A tunnel entrance sits just above the waterline to the south. The water looks clean enough to drink.",
        "exits": {"west": "cellar", "south": "tunnel"},
        "drink": True,
    },
    "tunnel": {
        "title": "The Tunnel",
        "description": "A narrow tunnel through bedrock. Loose rocks line the ceiling — this passage looks unstable. A faint breeze from the east carries a metallic scent.",
        "exits": {"north": "cistern", "east": "vault"},
        "hazard": "rocks",
        "hazard_damage": 2,
        "hazard_shield": True,
        "hazard_msg": "Rocks fall from the ceiling, striking you!",
        "hazard_shield_msg": "Rocks fall, but your shield deflects them.",
    },
    "crypt": {
        "title": "The Crypt",
        "description": "A cold, vaulted crypt. Stone sarcophagi line the walls. At the far end, a skeletal warrior stands motionless, gripping a notched blade. Its eye sockets glow faintly. It blocks the passage east.",
        "exits": {"north": "corridor"},
        "enemy": "skeleton",
        "enemy_hp": 2,
        "enemy_damage": 3,
        "enemy_desc_alive": "The skeleton warrior blocks the eastern passage, its empty eyes fixed on you.",
        "enemy_desc_dead": "The skeleton lies in a heap of bones. The eastern passage is clear.",
        "enemy_exit": {"east": "shrine"},
    },
    "shrine": {
        "title": "The Shrine",
        "description": "A small, peaceful chamber. A stone altar holds a glowing crystal that pulses with warm light. You feel your wounds beginning to close. A passage leads south to the vault.",
        "exits": {"west": "crypt", "south": "vault"},
        "heal": 5,
        "heal_msg": "The crystal's light washes over you, restoring your vitality.",
        "heal_once": True,
    },
    "vault": {
        "title": "The Treasure Vault",
        "description": "A vaulted chamber. Light pours from a crack in the ceiling, illuminating a stone pedestal. On it rests a single gold coin, glinting in the light. This is it — the treasure vault.",
        "exits": {"west": "tunnel", "north": "shrine"},
    },
}

_ITEMS = {
    "torch": {"name": "Torch", "desc": "A rusty iron torch. It burns with a steady flame."},
    "sword": {"name": "Sword", "desc": "A sturdy steel sword. Good for fighting."},
    "shield": {"name": "Shield", "desc": "A battered wooden shield. Blocks falling debris."},
    "rusty_key": {"name": "Rusty Key", "desc": "An old iron key. Fits a large lock."},
    "potion": {"name": "Healing Potion", "desc": "A glass bottle of red liquid. Restores 4 HP.", "consumable": True, "heal": 4},
    "bandage": {"name": "Bandage", "desc": "A dusty first-aid pouch. Restores 2 HP.", "consumable": True, "heal": 2},
    "amulet": {"name": "Amulet of Warding", "desc": "A silver amulet. Reduces all damage by 1."},
    "treasure": {"name": "Gold Coin", "desc": "A heavy gold coin. The objective of your quest."},
}

_MAX_HP = 10
_START_HP = 7


def _maze_default_data():
    """Return a fresh agent data dict for the maze."""
    return {
        "position": "entrance",
        "hp": _START_HP,
        "max_hp": _MAX_HP,
        "inventory": [],
        "picked_up": [],       # items permanently removed from rooms
        "flags": {},           # skeleton_defeated, cistern_drunk, shrine_healed, etc.
    }


def _maze_data(workflow_id: str) -> dict:
    """Return the current maze data for a workflow, initializing if needed."""
    d = _wf_load_state(workflow_id)
    if "hp" not in d:
        d = _maze_default_data()
        _wf_save_state(workflow_id, d)
    return d


def _maze_items_here(room_id, data):
    """Return list of item IDs present in a room (not yet picked up)."""
    room = _MAZE.get(room_id, {})
    return [i for i in room.get("items", []) if i not in data["picked_up"]]


def _render_maze_room(room_id, workflow_id: str):
    """Render the agent's current maze room as a JSON-serializable dict."""
    room = _MAZE.get(room_id)
    if room is None:
        return None

    data = _maze_data(workflow_id)
    api_url = f"/agent/{workflow_id}"

    # Handle pit auto-move + damage
    if "auto_move" in room:
        dmg = room.get("damage", 0)
        if dmg and "amulet" in data["inventory"]:
            dmg = max(0, dmg - 1)
        data["hp"] = max(0, data["hp"] - dmg)
        dest = room["auto_move"]
        data["position"] = dest
        _wf_save_state(workflow_id, data)
        msg = room.get("damage_msg", "")
        if data["hp"] <= 0:
            return _render_death(workflow_id, msg)
        _wf_notify(workflow_id, {"type": "navigate", "path": dest, "content": f"(auto-moved to {dest})"})
        page = _render_maze_room(dest, workflow_id)
        if msg:
            page["message"] = msg + f" (-{room.get('damage', 0)} HP)"
        return page

    # Handle tunnel hazard (on entry)
    if "hazard" in room and not data["flags"].get(f"hazard_{room_id}"):
        data["flags"][f"hazard_{room_id}"] = True
        has_shield = "shield" in data["inventory"]
        if room.get("hazard_shield") and has_shield:
            msg = room.get("hazard_shield_msg", "")
        else:
            dmg = room.get("hazard_damage", 0)
            if "amulet" in data["inventory"]:
                dmg = max(0, dmg - 1)
            data["hp"] = max(0, data["hp"] - dmg)
            msg = room.get("hazard_msg", "") + f" (-{dmg} HP)"
            if data["hp"] <= 0:
                return _render_death(workflow_id, msg)

    # Handle shrine heal
    if room.get("heal") and not data["flags"].get(f"healed_{room_id}"):
        if room.get("heal_once"):
            data["flags"][f"healed_{room_id}"] = True
        heal = room["heal"]
        old_hp = data["hp"]
        data["hp"] = min(data["max_hp"], data["hp"] + heal)
        actual = data["hp"] - old_hp
        if actual > 0:
            msg = room.get("heal_msg", f"You recover {actual} HP.")

    # Persist any mutations from hazard/heal processing
    _wf_save_state(workflow_id, data)

    # Determine description
    is_dark = room.get("dark") and "torch" not in data["inventory"]
    desc = room.get("dark_description", room["description"]) if is_dark else room["description"]

    # Enemy overlay
    enemy = room.get("enemy")
    if enemy and not data["flags"].get(f"{enemy}_defeated"):
        desc += " " + room.get("enemy_desc_alive", "")
    elif enemy and data["flags"].get(f"{enemy}_defeated"):
        desc += " " + room.get("enemy_desc_dead", "")

    # Build affordances
    affordances = []
    n = 1

    # Movement
    for direction, dest in room.get("exits", {}).items():
        affordances.append({
            "id": n, "label": f"Move {direction}",
            "method": "POST", "url": api_url,
            "body": {"action": "move", "direction": direction},
        })
        n += 1

    # Locked exits
    for direction, lock in room.get("locked_exits", {}).items():
        if data["flags"].get(f"unlocked_{room_id}_{direction}"):
            affordances.append({
                "id": n, "label": f"Move {direction} (unlocked)",
                "method": "POST", "url": api_url,
                "body": {"action": "move", "direction": direction},
            })
            n += 1
        elif lock["key"] in data["inventory"]:
            affordances.append({
                "id": n, "label": f"Unlock {direction} gate with {_ITEMS[lock['key']]['name']}",
                "method": "POST", "url": api_url,
                "body": {"action": "unlock", "direction": direction},
            })
            n += 1
        else:
            affordances.append({
                "id": n, "label": f"[Locked] {lock['desc']} (need a key)",
                "method": "POST", "url": api_url,
                "body": {"action": "move", "direction": direction},
            })
            n += 1

    # Enemy exit (only available after defeating enemy)
    if enemy and data["flags"].get(f"{enemy}_defeated"):
        for direction, dest in room.get("enemy_exit", {}).items():
            affordances.append({
                "id": n, "label": f"Move {direction}",
                "method": "POST", "url": api_url,
                "body": {"action": "move", "direction": direction},
            })
            n += 1

    # Pick up items
    items_here = _maze_items_here(room_id, data) if not is_dark else []
    for item_id in items_here:
        item = _ITEMS[item_id]
        affordances.append({
            "id": n, "label": f"Pick up {item['name']}",
            "method": "POST", "url": api_url,
            "body": {"action": "pick_up", "item": item_id},
        })
        n += 1

    # Dark room — hint about light
    if is_dark:
        items_here = []  # can't see items

    # Use consumables
    for item_id in data["inventory"]:
        item = _ITEMS.get(item_id, {})
        if item.get("consumable"):
            affordances.append({
                "id": n, "label": f"Use {item['name']}",
                "method": "POST", "url": api_url,
                "body": {"action": "use", "item": item_id},
            })
            n += 1

    # Drink from cistern
    if room.get("drink") and not data["flags"].get(f"drunk_{room_id}"):
        affordances.append({
            "id": n, "label": "Drink from the cistern",
            "method": "POST", "url": api_url,
            "body": {"action": "drink"},
        })
        n += 1

    # Attack enemy
    if enemy and not data["flags"].get(f"{enemy}_defeated"):
        if "sword" in data["inventory"]:
            affordances.append({
                "id": n, "label": f"Attack the {enemy} with your sword",
                "method": "POST", "url": api_url,
                "body": {"action": "attack"},
            })
            n += 1
        else:
            affordances.append({
                "id": n, "label": f"Attack the {enemy} (bare-handed — risky!)",
                "method": "POST", "url": api_url,
                "body": {"action": "attack"},
            })
            n += 1

    # Take treasure
    if room_id == "vault" and "treasure" not in data["picked_up"]:
        affordances.append({
            "id": n, "label": "Take the gold coin",
            "method": "POST", "url": api_url,
            "body": {"action": "take_treasure"},
        })
        n += 1

    # Items visible on ground
    visible_items = [_ITEMS[i]["name"] for i in items_here]
    if room_id == "vault" and "treasure" not in data["picked_up"]:
        visible_items.append("Gold Coin (on pedestal)")

    result = {
        "state": {
            "position": room_id,
            "room": room["title"],
            "hp": f"{data['hp']}/{data['max_hp']}",
            "inventory": [_ITEMS[i]["name"] for i in data["inventory"]],
            "items_here": visible_items,
        },
        "instructions": desc,
        "affordances": affordances,
    }

    if not data["flags"].get("won"):
        result["objective"] = "Find the treasure vault and take the gold coin. Explore carefully — there are hazards, locked doors, enemies, and useful items."

    return result


def _render_death(workflow_id: str, reason=""):
    """Render the death screen."""
    data = _maze_data(workflow_id)
    api_url = f"/agent/{workflow_id}"
    msg = "You have perished."
    if reason:
        msg = reason + " " + msg
    return {
        "state": {
            "position": data["position"],
            "room": "DEATH",
            "hp": "0/" + str(data["max_hp"]),
            "inventory": [_ITEMS[i]["name"] for i in data["inventory"]],
            "items_here": [],
        },
        "instructions": msg,
        "affordances": [{
            "id": 1, "label": "Restart from entrance",
            "method": "POST", "url": api_url,
            "body": {"action": "restart"},
        }],
    }


# ---------------------------------------------------------------------------
# Create Change Record Workflow
# ---------------------------------------------------------------------------

# -- Load CR workflow definition from YAML --
_CR_YAML_PATH = Path(__file__).parent / "data" / "agent_create_cr.yaml"
with open(_CR_YAML_PATH) as _f:
    _CR_DEF = yaml.safe_load(_f)

_CR_SUBMODULES = _CR_DEF["submodules"]
_CR_SDLC_GOVERNED = set(_CR_DEF["sdlc_governed"])
_CR_STAGES = list(_CR_DEF["stages"].keys())
_CR_LIFECYCLE = _CR_DEF["lifecycle_banner"]
_CR_OBJECTIVE = _CR_DEF["objective"]
_CR_FIELDS = _CR_DEF["fields"]

# Derived from the stages dict
_CR_STAGE_INFO = {
    sid: {"title": s["title"], "instruction": s["instruction"]}
    for sid, s in _CR_DEF["stages"].items()
}
_CR_STAGE_TO_LIFECYCLE = {
    sid: s["lifecycle_label"]
    for sid, s in _CR_DEF["stages"].items()
}

# -- Workflow registry --
# Each entry maps a workflow_id to its type and display metadata.
# The type determines which render/process functions handle it.
_WORKFLOWS = {
    "maze": {
        "type": "maze",
        "title": "Dungeon Maze",
        "description": "Navigate a 13-room dungeon. Find the treasure, avoid the traps.",
        "renderers": ["raw", "map", "terminal"],
    },
    "create-cr": {
        "type": "create-cr",
        "title": "Create Change Record",
        "description": "Author a Change Record through the full pre-approval lifecycle.",
        "renderers": ["raw", "workflow"],
    },
}


def _cr_default_data():
    """Return a fresh agent data dict for the CR workflow, derived from YAML."""
    d = {"stage": _CR_STAGES[0], "completed_stages": [], "message": None}
    for fdef in _CR_FIELDS.values():
        if fdef.get("type") != "computed":
            d[fdef["key"]] = fdef.get("default")
    return d


def _cr_data(workflow_id: str) -> dict:
    """Return the current CR workflow data, initializing if needed."""
    d = _wf_load_state(workflow_id)
    if "stage" not in d or "title" not in d:
        d = _cr_default_data()
        _wf_save_state(workflow_id, d)
    return d


def _trunc(val, length=80):
    """Truncate a string for display, adding ellipsis if needed."""
    if not val:
        return None
    return val[:length] + ("..." if len(val) > length else "")


def _field(value, instruction=None):
    """Build a field object with value and optional instruction."""
    f = {"value": value}
    if instruction:
        f["instruction"] = instruction
    return f


def _cr_field_visible(fdef, data):
    """Evaluate whether a field's visible_when conditions are satisfied."""
    conds = fdef.get("visible_when")
    if not conds:
        return True
    for key, expected in conds.items():
        val = data.get(key)
        if expected == "not_null":
            if val is None:
                return False
        elif val != expected:
            return False
    return True


def _cr_field_summary(data, stage):
    """Return a dict of all fields relevant to the current stage, including nulls.

    Driven entirely by the YAML workflow definition — no hardcoded field logic.
    """
    fields = {}
    for fdef in _CR_FIELDS.values():
        # Stage gate
        if stage not in fdef.get("stages", []):
            continue
        # Conditional visibility
        if not _cr_field_visible(fdef, data):
            continue

        ftype = fdef.get("type", "text")
        key = fdef["key"]
        label = fdef["label"]

        if ftype == "boolean":
            value = "Yes" if data.get(key) else "No"
            instruction = fdef.get("instruction")
        elif ftype == "computed" and fdef.get("computed") == "sdlc_check":
            value = "Yes" if data.get(key) in _CR_SDLC_GOVERNED else "No"
            if data.get(key) in _CR_SDLC_GOVERNED:
                instruction = fdef.get("instruction_when_true")
            else:
                instruction = fdef.get("instruction_when_false")
        else:
            value = _trunc(data.get(key))
            instruction = fdef.get("instruction")

        fields[label] = _field(value, instruction)
    return fields


def _cr_build_affordances(data, stage, workflow_id: str):
    """Generate affordances from YAML field definitions and stage config.

    Affordance rules by field type:
      text     → "Set {label}" with placeholder as value template
      boolean  → toggle showing current state, offering the opposite
      select   → one affordance per option, marking current selection
      computed → no affordance (read-only)

    Stage-level affordances (from stages.{stage} in YAML):
      navigation → always emitted
      proceed    → gated on all required fields being non-null
      actions    → unconditional
    """
    affordances = []
    n = 1
    api_url = f"/agent/{workflow_id}"
    stage_def = _CR_DEF["stages"][stage]

    # -- Field affordances --
    for fdef in _CR_FIELDS.values():
        if stage not in fdef.get("stages", []):
            continue
        if not _cr_field_visible(fdef, data):
            continue

        ftype = fdef.get("type", "text")
        key = fdef["key"]
        label = fdef["label"]

        if ftype == "text":
            current = data.get(key)
            suffix = ""
            if current:
                suffix = f" (current: \"{_trunc(current, 50)}\")"
            placeholder = fdef.get("placeholder", f"<{label.lower()}>")
            a = {"id": n, "label": f"Set {label}{suffix}",
                 "method": "POST", "url": api_url,
                 "body": {"action": "set_field", "field": key, "value": placeholder}}
            affordances.append(a)
            n += 1

        elif ftype == "boolean":
            current = data.get(key, False)
            tag = "Yes" if current else "No"
            opposite = not current
            opp_tag = "Yes" if opposite else "No"
            a = {"id": n,
                 "label": f"[{tag}] {label} — click to set {opp_tag}",
                 "method": "POST", "url": api_url,
                 "body": {"action": "set_field", "field": key, "value": opposite}}
            affordances.append(a)
            n += 1

        elif ftype == "select":
            options_ref = fdef.get("options_ref")
            options = _CR_DEF.get(options_ref, []) if options_ref else []
            annotate_set = set(_CR_DEF.get(fdef.get("annotate_from", ""), []))
            annotation = fdef.get("annotation", "")
            current = data.get(key)
            for opt in options:
                selected = current == opt
                tag = f" {annotation}" if opt in annotate_set else ""
                prefix = "[Selected] " if selected else ""
                a = {"id": n,
                     "label": f"{prefix}Set {label.lower()}: {opt}{tag}",
                     "method": "POST", "url": api_url,
                     "body": {"action": "set_field", "field": key, "value": opt}}
                affordances.append(a)
                n += 1

        # computed → no affordance

    # -- Navigation affordances --
    for nav in stage_def.get("navigation", []):
        body = {"action": nav["action"]}
        if "stage" in nav:
            body["stage"] = nav["stage"]
        a = {"id": n, "label": nav["label"],
             "method": "POST", "url": api_url, "body": body}
        affordances.append(a)
        n += 1

    # -- Proceed gate --
    proceed = stage_def.get("proceed")
    if proceed:
        required = proceed.get("requires", [])
        if all(data.get(f) for f in required):
            a = {"id": n, "label": proceed["label"],
                 "method": "POST", "url": api_url,
                 "body": {"action": "proceed"}}
            affordances.append(a)
            n += 1

    # -- Stage actions --
    for act in stage_def.get("actions", []):
        a = {"id": n, "label": act["label"],
             "method": "POST", "url": api_url,
             "body": {"action": act["action"]}}
        affordances.append(a)
        n += 1

    return affordances


def _render_cr_stage(workflow_id: str, stage=None):
    """Render the current CR workflow stage as a JSON-serializable dict."""
    data = _cr_data(workflow_id)
    if stage is None:
        stage = data["stage"]

    info = _CR_STAGE_INFO[stage]
    stage_idx = _CR_STAGES.index(stage)
    affordances = _cr_build_affordances(data, stage, workflow_id)

    # Build fields display
    fields_display = _cr_field_summary(data, stage)

    # Build lifecycle banner data
    lifecycle_current = _CR_STAGE_TO_LIFECYCLE.get(stage, "Initiation")
    lifecycle_completed = []
    for cs in data["completed_stages"]:
        lbl = _CR_STAGE_TO_LIFECYCLE.get(cs)
        if lbl and lbl not in lifecycle_completed:
            lifecycle_completed.append(lbl)

    result = {
        "message": data.get("message"),
        "state": {
            "workflow": "Create Change Record",
            "stage": stage,
            "stage_title": info["title"],
            "progress": f"{stage_idx + 1}/{len(_CR_STAGES)}",
            "lifecycle": _CR_LIFECYCLE,
            "lifecycle_current": lifecycle_current,
            "lifecycle_completed": lifecycle_completed,
            "completed_stages": data["completed_stages"],
            "fields": fields_display,
        },
        "instructions": info["instruction"],
        "affordances": affordances,
    }

    if stage == "preflight":
        result["review"] = {
            "title": data["title"],
            "affects_code": data["affects_code"],
            "submodule": data["submodule"],
            "purpose": data["purpose"],
            "scope_context": data["scope_context"],
            "scope_changes": data["scope_changes"],
            "scope_files": data["scope_files"],
            "current_state": data["current_state"],
            "proposed_state": data["proposed_state"],
            "change_description": data["change_description"],
            "justification": data["justification"],
            "impact_files": data["impact_files"],
            "impact_documents": data["impact_documents"],
            "impact_other": data["impact_other"],
            "testing_summary": data["testing_summary"],
        }

    if stage != "submitted":
        result["objective"] = "Complete all required fields and submit this Change Record for review."

    return result


def _process_cr_action(workflow_id: str, body):
    """Process a POST action for the Create CR workflow."""
    data = _cr_data(workflow_id)
    action = body.get("action")

    if action == "restart":
        data = _cr_default_data()
        _wf_save_state(workflow_id, data)
        return _render_cr_stage(workflow_id)

    stage = data["stage"]

    if action == "set_field":
        field = body.get("field", "")
        value = body.get("value", "")
        valid_text = [
            "title", "purpose", "scope_context", "scope_changes", "scope_files",
            "current_state", "proposed_state", "change_description", "justification",
            "impact_files", "impact_documents", "impact_other", "testing_summary",
        ]
        valid_bool = ["affects_code", "affects_submodule"]
        valid_enum = ["submodule"]

        if field in valid_text:
            data[field] = value
        elif field in valid_bool:
            data[field] = bool(value)
            # Clear downstream fields when toggling off
            if field == "affects_code" and not value:
                data["affects_submodule"] = False
                data["submodule"] = None
            if field == "affects_submodule" and not value:
                data["submodule"] = None
        elif field == "submodule":
            if value not in _CR_SUBMODULES:
                return {"error": f"Invalid submodule. Choose: {', '.join(_CR_SUBMODULES)}"}
            data[field] = value
        else:
            return {"error": f"Unknown field: {field}"}

        display_val = str(value)
        data["message"] = f"Set {field} = \"{_trunc(display_val, 60)}\""
        _wf_save_state(workflow_id, data)
        return _render_cr_stage(workflow_id)

    if action == "proceed":
        idx = _CR_STAGES.index(stage)
        if idx >= len(_CR_STAGES) - 1:
            return {"error": "Already at the final stage."}
        if stage not in data["completed_stages"]:
            data["completed_stages"].append(stage)
        data["stage"] = _CR_STAGES[idx + 1]
        data["message"] = f"Advanced to: {_CR_STAGE_INFO[data['stage']]['title']}"
        _wf_save_state(workflow_id, data)
        page = _render_cr_stage(workflow_id)
        _wf_notify(workflow_id, {"type": "navigate", "path": data["stage"], "content": json.dumps(page)})
        return page

    if action == "go_back":
        idx = _CR_STAGES.index(stage)
        if idx <= 0:
            return {"error": "Already at the first stage."}
        data["stage"] = _CR_STAGES[idx - 1]
        data["message"] = f"Returned to: {_CR_STAGE_INFO[data['stage']]['title']}"
        _wf_save_state(workflow_id, data)
        page = _render_cr_stage(workflow_id)
        _wf_notify(workflow_id, {"type": "navigate", "path": data["stage"], "content": json.dumps(page)})
        return page

    if action == "go_to":
        target = body.get("stage", "")
        if target not in _CR_STAGES:
            return {"error": f"Unknown stage: {target}"}
        data["stage"] = target
        data["message"] = f"Jumped to: {_CR_STAGE_INFO[target]['title']}"
        _wf_save_state(workflow_id, data)
        page = _render_cr_stage(workflow_id)
        _wf_notify(workflow_id, {"type": "navigate", "path": target, "content": json.dumps(page)})
        return page

    if action == "submit":
        if stage != "preflight":
            return {"error": "You can only submit from the Pre-Submission Review stage."}
        data["stage"] = "submitted"
        if "preflight" not in data["completed_stages"]:
            data["completed_stages"].append("preflight")
        data["message"] = "Change Record submitted for review. Well done."
        _wf_save_state(workflow_id, data)
        page = _render_cr_stage(workflow_id)
        _wf_notify(workflow_id, {"type": "navigate", "path": "submitted", "content": json.dumps(page)})
        return page

    return {"error": f"Unknown action: {action}"}


def _render_agent_node(workflow_id: str):
    """Render the current state of a workflow as a JSON-serializable dict."""
    wf_type = _WORKFLOWS.get(workflow_id, {}).get("type")
    if wf_type == "maze":
        data = _maze_data(workflow_id)
        if data["hp"] <= 0:
            return _render_death(workflow_id)
        return _render_maze_room(data["position"], workflow_id)

    if wf_type == "create-cr":
        return _render_cr_stage(workflow_id)

    return {"error": f"Unknown workflow: {workflow_id}"}


_last_action_times: dict[str, float] = {}
_ACTION_COOLDOWN: float = 1.0  # seconds between actions


def _process_agent_action(workflow_id: str, body):
    """Process a POST action for a workflow."""
    # Rate limit per workflow
    now = _time.time()
    elapsed = now - _last_action_times.get(workflow_id, 0.0)
    if elapsed < _ACTION_COOLDOWN:
        return {
            "error": f"Too fast. Wait {_ACTION_COOLDOWN - elapsed:.1f}s before your next action.",
            "retry_after": round(_ACTION_COOLDOWN - elapsed, 1),
        }
    _last_action_times[workflow_id] = now

    wf_type = _WORKFLOWS.get(workflow_id, {}).get("type")

    if wf_type == "create-cr":
        return _process_cr_action(workflow_id, body)

    if wf_type != "maze":
        return {"error": f"Unknown workflow: {workflow_id}"}

    data = _maze_data(workflow_id)
    pos = data["position"]
    room = _MAZE.get(pos)
    if room is None:
        return {"error": "Invalid position"}

    action = body.get("action")

    # --- restart ---
    if action == "restart":
        data = _maze_default_data()
        _wf_save_state(workflow_id, data)
        page = _render_maze_room("entrance", workflow_id)
        page["message"] = "You awaken at the entrance, memories of your demise fading like a dream."
        _wf_notify(workflow_id, {"type": "navigate", "path": "entrance", "content": json.dumps(page)})
        return page

    # --- dead check ---
    if data["hp"] <= 0:
        return _render_death(workflow_id)

    # --- move ---
    if action == "move":
        direction = body.get("direction", "").lower()

        # Check locked exits
        locked = room.get("locked_exits", {}).get(direction)
        if locked:
            if data["flags"].get(f"unlocked_{pos}_{direction}"):
                dest = locked["dest"]
            else:
                return {"error": f"The {direction} gate is locked. You need a key."}
        # Check enemy-gated exits
        elif direction in (room.get("enemy_exit") or {}):
            enemy = room.get("enemy")
            if enemy and not data["flags"].get(f"{enemy}_defeated"):
                return {"error": f"The {enemy} blocks your path. You must defeat it first."}
            dest = room["enemy_exit"][direction]
        # Normal exits
        elif direction in room.get("exits", {}):
            dest = room["exits"][direction]
        else:
            valid = list(room.get("exits", {}).keys())
            valid += [d for d in room.get("locked_exits", {}).keys()
                      if data["flags"].get(f"unlocked_{pos}_{d}")]
            if room.get("enemy") and data["flags"].get(f"{room['enemy']}_defeated"):
                valid += list((room.get("enemy_exit") or {}).keys())
            return {"error": f"Cannot go {direction}. Valid exits: {', '.join(valid) or 'none'}"}

        data["position"] = dest
        data["flags"].pop(f"hazard_{dest}", None)
        _wf_save_state(workflow_id, data)
        page = _render_maze_room(data["position"], workflow_id)
        _wf_notify(workflow_id, {"type": "navigate", "path": data["position"], "content": json.dumps(page)})
        return page

    # --- unlock ---
    if action == "unlock":
        direction = body.get("direction", "").lower()
        locked = room.get("locked_exits", {}).get(direction)
        if not locked:
            return {"error": f"Nothing to unlock in direction: {direction}"}
        if locked["key"] not in data["inventory"]:
            return {"error": f"You don't have the required key."}
        data["flags"][f"unlocked_{pos}_{direction}"] = True
        _wf_save_state(workflow_id, data)
        page = _render_maze_room(pos, workflow_id)
        page["message"] = f"You unlock the {direction} gate with the {_ITEMS[locked['key']]['name']}. The way is open."
        return page

    # --- pick_up ---
    if action == "pick_up":
        item_id = body.get("item", "")
        is_dark = room.get("dark") and "torch" not in data["inventory"]
        items_here = _maze_items_here(pos, data)
        if is_dark:
            return {"error": "It's too dark to see what's here. You need a light source."}
        if item_id not in items_here:
            return {"error": f"No '{item_id}' here to pick up."}
        data["inventory"].append(item_id)
        data["picked_up"].append(item_id)
        _wf_save_state(workflow_id, data)
        page = _render_maze_room(pos, workflow_id)
        page["message"] = f"You pick up the {_ITEMS[item_id]['name']}. {_ITEMS[item_id]['desc']}"
        return page

    # --- use (consumables) ---
    if action == "use":
        item_id = body.get("item", "")
        if item_id not in data["inventory"]:
            return {"error": f"You don't have '{item_id}' in your inventory."}
        item = _ITEMS.get(item_id, {})
        if not item.get("consumable"):
            return {"error": f"You can't use {item.get('name', item_id)} that way."}
        heal = item.get("heal", 0)
        old_hp = data["hp"]
        data["hp"] = min(data["max_hp"], data["hp"] + heal)
        actual = data["hp"] - old_hp
        data["inventory"].remove(item_id)
        _wf_save_state(workflow_id, data)
        page = _render_maze_room(pos, workflow_id)
        page["message"] = f"You use the {item['name']}. Restored {actual} HP."
        return page

    # --- drink (cistern) ---
    if action == "drink":
        if not room.get("drink"):
            return {"error": "There's nothing to drink here."}
        if data["flags"].get(f"drunk_{pos}"):
            return {"error": "You've already drunk from this water source."}
        data["flags"][f"drunk_{pos}"] = True
        old_hp = data["hp"]
        data["hp"] = min(data["max_hp"], data["hp"] + 2)
        actual = data["hp"] - old_hp
        _wf_save_state(workflow_id, data)
        page = _render_maze_room(pos, workflow_id)
        page["message"] = f"You drink the cool water. Restored {actual} HP."
        return page

    # --- attack ---
    if action == "attack":
        enemy = room.get("enemy")
        if not enemy:
            return {"error": "Nothing to attack here."}
        if data["flags"].get(f"{enemy}_defeated"):
            return {"error": f"The {enemy} is already defeated."}
        has_sword = "sword" in data["inventory"]
        enemy_dmg = room.get("enemy_damage", 2)
        if "amulet" in data["inventory"]:
            enemy_dmg = max(0, enemy_dmg - 1)
        if has_sword:
            dmg_taken = max(0, enemy_dmg - 2)
            data["hp"] = max(0, data["hp"] - dmg_taken)
            data["flags"][f"{enemy}_defeated"] = True
            _wf_save_state(workflow_id, data)
            if data["hp"] <= 0:
                return _render_death(workflow_id, f"You slay the {enemy}, but its dying blow fells you.")
            page = _render_maze_room(pos, workflow_id)
            msg = f"You strike the {enemy} with your sword and it crumbles to dust!"
            if dmg_taken > 0:
                msg += f" It managed to wound you in the fight. (-{dmg_taken} HP)"
            page["message"] = msg
            return page
        else:
            data["hp"] = max(0, data["hp"] - enemy_dmg)
            data["flags"][f"{enemy}_defeated"] = True
            _wf_save_state(workflow_id, data)
            if data["hp"] <= 0:
                return _render_death(workflow_id, f"You wrestle the {enemy} to pieces, but its claws tear you apart.")
            page = _render_maze_room(pos, workflow_id)
            page["message"] = f"You wrestle the {enemy} apart with your bare hands! But it wounds you grievously. (-{enemy_dmg} HP)"
            return page

    # --- take_treasure ---
    if action == "take_treasure":
        if pos != "vault":
            return {"error": "There's no treasure here."}
        if "treasure" in data["picked_up"]:
            return {"error": "You already have the treasure."}
        data["inventory"].append("treasure")
        data["picked_up"].append("treasure")
        data["flags"]["won"] = True
        _wf_save_state(workflow_id, data)
        page = _render_maze_room(pos, workflow_id)
        page["message"] = "You take the gold coin from the pedestal. It is heavy and warm in your hand. Congratulations — you have completed the dungeon!"
        page["completed"] = True
        return page

    return {"error": f"Unknown action: {action}"}


@app.route("/agent")
def agent_portal():
    # Build workflow list with state summaries
    workflows = []
    for wf_id, wf_info in _WORKFLOWS.items():
        state = _wf_load_state(wf_id)
        has_state = bool(state)
        workflows.append({
            "id": wf_id,
            "title": wf_info["title"],
            "description": wf_info["description"],
            "has_state": has_state,
        })
    return render_template("agent.html", active_page="agent", workflows=workflows)


@app.route("/agent/<workflow_id>/observe")
def agent_observe(workflow_id):
    if workflow_id not in _WORKFLOWS:
        abort(404)
    wf_info = _WORKFLOWS[workflow_id]
    return render_template(
        "agent_observer.html",
        workflow_id=workflow_id,
        workflow_title=wf_info["title"],
        stream_url=f"/agent/{workflow_id}/stream",
        renderers=json.dumps(wf_info["renderers"]),
    )


@app.route("/agent/<workflow_id>/stream")
def agent_stream(workflow_id):
    if workflow_id not in _WORKFLOWS:
        return jsonify({"error": "Unknown workflow"}), 404

    def generate():
        q = Queue()
        observers = _workflow_observers.setdefault(workflow_id, [])
        observers.append(q)
        try:
            page = _render_agent_node(workflow_id)
            init = {
                "type": "init",
                "current_path": _workflow_current_path.get(workflow_id),
                "page": page,
                "history": _workflow_history.get(workflow_id, [])[-100:],
            }
            yield f"data: {json.dumps(init)}\n\n"
            while True:
                try:
                    event = q.get(timeout=15)
                    yield f"data: {json.dumps(event)}\n\n"
                except Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            if q in _workflow_observers.get(workflow_id, []):
                _workflow_observers[workflow_id].remove(q)
    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/agent/<workflow_id>/reset", methods=["POST"])
def agent_reset(workflow_id):
    if workflow_id not in _WORKFLOWS:
        return jsonify({"error": "Unknown workflow"}), 404
    p = _wf_state_path(workflow_id)
    if p.exists():
        p.unlink()
    _workflow_history.pop(workflow_id, None)
    _workflow_current_path.pop(workflow_id, None)
    return jsonify({"message": f"Workflow '{workflow_id}' reset."})


@app.route("/agent/<workflow_id>", methods=["GET"])
def agent_workflow_get(workflow_id):
    if workflow_id not in _WORKFLOWS:
        return jsonify({"error": f"Unknown workflow: {workflow_id}"}), 404
    page = _render_agent_node(workflow_id)
    _workflow_current_path[workflow_id] = workflow_id
    _wf_notify(workflow_id, {"type": "navigate", "path": workflow_id, "content": json.dumps(page)})
    if page is None:
        return jsonify({"error": f"Unknown workflow: {workflow_id}"}), 404
    return jsonify(page)


@app.route("/agent/<workflow_id>", methods=["POST"])
def agent_workflow_post(workflow_id):
    if workflow_id not in _WORKFLOWS:
        return jsonify({"error": f"Unknown workflow: {workflow_id}"}), 404
    body = request.get_json(silent=True) or {}

    # Capture before-FoV
    before_fov = _render_agent_node(workflow_id)

    _wf_notify(workflow_id, {"type": "action", "path": workflow_id, "body": body})
    result = _process_agent_action(workflow_id, body)

    if "error" in result:
        _wf_notify(workflow_id, {"type": "result", "path": workflow_id, "result": result})
        return jsonify(result), 422

    # result is the after-FoV (returned by the action processor)
    after_fov = result
    focus = _compute_focus(before_fov, after_fov)

    # Push full FoV + Focus to Observer via SSE
    _wf_notify(workflow_id, {"type": "result", "path": workflow_id, "result": after_fov, "focus": focus})

    # Return Focus to agent
    return jsonify(focus)


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
    app.run(debug=True, port=5000, threaded=True)
