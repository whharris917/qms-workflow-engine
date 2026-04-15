/**
 * Eigenform event delegation.
 *
 * Eigenforms control their own interaction by emitting data attributes.
 * This script is a thin mechanism that reads those attributes and
 * executes the fetch+swap cycle. It does not contain any eigenform
 * logic — the eigenform dictates the URL, body, and input strategy.
 *
 * Protocols:
 *   data-ef-post  + data-ef-body      — static-body click (buttons)
 *   data-ef-submit (on <form>)        — form submission, body from fields
 *   data-ef-change + data-ef-key      — checkbox: {key: checked}
 *   data-ef-change + data-ef-field    — radio/input: {field: value}
 *   data-ef-change + data-ef-template — complex: JSON with __VALUE replaced
 */

/* Static-body clicks */
document.addEventListener('click', function(e) {
    var el = e.target.closest('[data-ef-post]');
    if (!el) return;
    e.preventDefault();
    _efPost(el.getAttribute('data-ef-post'), el.getAttribute('data-ef-body'));
});

/* One-click add eigenform (sleek theme + builder palette) */
document.addEventListener('click', function(e) {
    var el = e.target.closest('[data-ef-add]');
    if (!el) return;
    e.preventDefault();
    var type = el.getAttribute('data-type') || el.getAttribute('data-ef-palette-type');
    if (!type) return;
    _efPost(el.getAttribute('data-ef-add'), JSON.stringify({
        action: 'add_eigenform',
        type: type
    }));
});

/* Form submissions — body built from named form fields */
document.addEventListener('submit', function(e) {
    var form = e.target.closest('form[data-ef-submit]');
    if (!form) return;
    e.preventDefault();
    var body = {};
    new FormData(form).forEach(function(v, k) { body[k] = v; });
    _efPost(form.getAttribute('data-ef-submit'), JSON.stringify(body));
});

/* Immediate-change elements (checkbox, radio, select) */
document.addEventListener('change', function(e) {
    var el = e.target.closest('[data-ef-change]');
    if (!el) return;
    var url = el.getAttribute('data-ef-change');
    var body;
    if (el.hasAttribute('data-ef-key')) {
        /* Checkbox: body = {key: checked} */
        body = {};
        body[el.getAttribute('data-ef-key')] = el.checked;
    } else if (el.hasAttribute('data-ef-field')) {
        /* Radio/input: body = {field: value} */
        body = {};
        body[el.getAttribute('data-ef-field')] = el.value;
    } else if (el.hasAttribute('data-ef-template')) {
        /* Template: replace __VALUE sentinel */
        body = JSON.parse(el.getAttribute('data-ef-template'));
        for (var k in body) {
            if (body[k] === '__VALUE') body[k] = el.value;
        }
    }
    if (body) _efPost(url, JSON.stringify(body));
});

/* ---------------------------------------------------------------
 * Structural editor: drag-and-drop reorder + multi-select + group
 * --------------------------------------------------------------- */

/* ---------------------------------------------------------------
 * Builder: palette drag (add from type palette to canvas)
 * --------------------------------------------------------------- */

document.addEventListener('dragstart', function(e) {
    var type = e.target.closest('[data-ef-palette-type]');
    if (!type) return;
    e.dataTransfer.setData('application/ef-type', type.dataset.efPaletteType);
    e.dataTransfer.setData('application/ef-url', type.dataset.efAdd);
    e.dataTransfer.effectAllowed = 'copy';
    type.classList.add('dragging');
});

document.addEventListener('dragend', function(e) {
    var type = e.target.closest('[data-ef-palette-type]');
    if (type) type.classList.remove('dragging');
});

/* Builder: collapse/expand canvas items */
document.addEventListener('click', function(e) {
    var tile = e.target.closest('.builder__item > .sleek-struct__tile');
    if (!tile) return;
    /* Don't toggle when clicking buttons */
    if (e.target.closest('button') || e.target.closest('[data-ef-post]')) return;
    var item = tile.closest('.builder__item');
    var body = item.querySelector('.builder__item-body');
    if (!body) return;
    var collapsed = body.getAttribute('data-collapsed') === 'true';
    body.setAttribute('data-collapsed', collapsed ? 'false' : 'true');
});

/* Drag-and-drop reorder */
document.addEventListener('dragstart', function(e) {
    var tile = e.target.closest('.sleek-struct__tile');
    if (!tile) return;
    /* Don't conflict with palette drag */
    if (e.target.closest('[data-ef-palette-type]')) return;
    e.dataTransfer.setData('text/plain', tile.dataset.key);
    e.dataTransfer.effectAllowed = 'move';
    tile.classList.add('dragging');
    /* In builder mode, also mark the parent item as dragging */
    var item = tile.closest('.builder__item');
    if (item) item.classList.add('dragging');
});

document.addEventListener('dragend', function(e) {
    var tile = e.target.closest('.sleek-struct__tile');
    if (tile) {
        tile.classList.remove('dragging');
        var item = tile.closest('.builder__item');
        if (item) item.classList.remove('dragging');
    }
    _efClearDropFeedback();
    /* Clear canvas drop-active outline */
    document.querySelectorAll('.builder__canvas-body.drop-active').forEach(function(el) {
        el.classList.remove('drop-active');
    });
});

function _efClearDropFeedback() {
    document.querySelectorAll('.sleek-struct__drop-indicator').forEach(function(el) {
        el.remove();
    });
    document.querySelectorAll('.sleek-struct__tile.drop-target').forEach(function(el) {
        el.classList.remove('drop-target');
    });
}

/*
 * _efFindDropZone: find the nearest drop container (nest or top-level list)
 * and determine whether we're hovering over a container tile.
 */
function _efFindDropZone(target) {
    /* Prefer the innermost nest (for reorder within a group) */
    var nest = target.closest('.sleek-struct__nest');
    if (nest) return { container: nest, parent: nest.dataset.parent };
    var list = target.closest('.sleek-struct__list');
    if (list) return { container: list, parent: null };
    return null;
}

document.addEventListener('dragover', function(e) {
    var zone = _efFindDropZone(e.target);
    if (!zone) return;
    e.preventDefault();

    /* Detect whether this is a palette drag (copy) or tile drag (move) */
    var isPalette = e.dataTransfer.types.indexOf('application/ef-type') !== -1;
    e.dataTransfer.dropEffect = isPalette ? 'copy' : 'move';

    _efClearDropFeedback();

    var container = zone.container;

    /* Activate canvas drop zone outline for palette drags */
    if (isPalette) {
        var canvasBody = e.target.closest('.builder__canvas-body');
        if (canvasBody) canvasBody.classList.add('drop-active');
    }

    /* Check if hovering over a container tile (for reparent) — tiles only */
    if (!isPalette) {
        var hoverTile = e.target.closest('.sleek-struct__tile--container');
        if (hoverTile && !hoverTile.classList.contains('dragging')) {
            var rect = hoverTile.getBoundingClientRect();
            var zoneY = (e.clientY - rect.top) / rect.height;
            if (zoneY > 0.2 && zoneY < 0.8) {
                hoverTile.classList.add('drop-target');
                return;
            }
        }
    }

    /* Insertion-line: works for both palette drops and tile reorder.
       In builder mode, children are .builder__item; in legacy mode, .sleek-struct__tile */
    var children = Array.from(container.querySelectorAll(
        ':scope > .builder__item:not(.dragging), :scope > .sleek-struct__tile:not(.dragging)'
    ));
    var indicator = document.createElement('div');
    indicator.className = 'sleek-struct__drop-indicator';
    var inserted = false;

    for (var i = 0; i < children.length; i++) {
        var rect = children[i].getBoundingClientRect();
        if (e.clientY < rect.top + rect.height / 2) {
            container.insertBefore(indicator, children[i]);
            inserted = true;
            break;
        }
    }
    if (!inserted) {
        container.appendChild(indicator);
    }
});

document.addEventListener('drop', function(e) {
    var zone = _efFindDropZone(e.target);
    if (!zone) return;
    e.preventDefault();

    /* Clear canvas drop-active outline */
    document.querySelectorAll('.builder__canvas-body.drop-active').forEach(function(el) {
        el.classList.remove('drop-active');
    });

    /* Palette drop — add new eigenform at position */
    var efType = e.dataTransfer.getData('application/ef-type');
    if (efType) {
        var url = e.dataTransfer.getData('application/ef-url');
        var container = zone.container;
        var indicator = container.querySelector(':scope > .sleek-struct__drop-indicator');

        /* Calculate insertion position from builder items or tiles */
        var children = Array.from(container.querySelectorAll(
            ':scope > .builder__item, :scope > .sleek-struct__tile'
        ));
        var targetIndex = children.length;
        if (indicator) {
            var pos = 0;
            var node = container.firstElementChild;
            while (node && node !== indicator) {
                if (node.classList && (node.classList.contains('builder__item') ||
                    node.classList.contains('sleek-struct__tile'))) {
                    pos++;
                }
                node = node.nextElementSibling;
            }
            targetIndex = pos;
            indicator.remove();
        }

        _efClearDropFeedback();
        _efPost(url, JSON.stringify({
            action: 'add_eigenform', type: efType, position: targetIndex
        }));
        return;
    }

    /* Tile reorder drop */
    var key = e.dataTransfer.getData('text/plain');
    var list = e.target.closest('.sleek-struct__list') ||
               e.target.closest('.sleek-struct__nest').closest('.sleek-struct__list');
    var url = list.dataset.efUrl;

    /* Check if dropping on a container tile (reparent) */
    var dropTarget = document.querySelector('.sleek-struct__tile.drop-target');
    if (dropTarget) {
        var targetKey = dropTarget.dataset.key;
        _efClearDropFeedback();
        _efPost(url, JSON.stringify({
            action: 'reparent_eigenform', key: key, target: targetKey
        }));
        return;
    }

    /* Reorder via insertion line */
    var container = zone.container;
    var indicator = container.querySelector(':scope > .sleek-struct__drop-indicator');
    /* Count builder items or tiles for position */
    var siblings = Array.from(container.querySelectorAll(
        ':scope > .builder__item, :scope > .sleek-struct__tile'
    ));
    var targetIndex = siblings.length;

    if (indicator) {
        var pos = 0;
        var node = container.firstElementChild;
        while (node && node !== indicator) {
            if (node.classList && (node.classList.contains('builder__item') ||
                node.classList.contains('sleek-struct__tile'))
                && !node.classList.contains('dragging')) {
                pos++;
            }
            node = node.nextElementSibling;
        }
        targetIndex = pos;
        indicator.remove();
    }

    var body = { action: 'move_eigenform', key: key, position: targetIndex };
    if (zone.parent) body.parent = zone.parent;

    _efClearDropFeedback();
    _efPost(url, JSON.stringify(body));
});

/* Multi-select tiles (Ctrl+click in builder, plain click in legacy) */
document.addEventListener('click', function(e) {
    var tile = e.target.closest('.sleek-struct__tile');
    if (!tile) return;
    /* Don't interfere with buttons inside the tile */
    if (e.target.closest('button') || e.target.closest('[data-ef-post]')) return;

    /* In builder layout, Ctrl+click to multi-select (plain click = collapse/expand) */
    var item = tile.closest('.builder__item');
    if (item) {
        if (!e.ctrlKey && !e.metaKey) return;  /* Let collapse handler take plain clicks */
        item.classList.toggle('selected');
        var editor = tile.closest('.builder__canvas');
        _efUpdateGroupBar(editor);
        return;
    }

    /* Legacy structural editor — plain click to select */
    tile.classList.toggle('selected');
    _efUpdateGroupBar(tile.closest('.sleek-struct'));
});

function _efUpdateGroupBar(editor) {
    if (!editor) return;
    /* In builder layout, selected class is on .builder__item; in legacy, on .sleek-struct__tile */
    var selected = editor.querySelectorAll('.builder__item.selected, .sleek-struct__tile.selected');
    var bar = editor.querySelector('.sleek-struct__group-bar') ||
              document.querySelector('.builder__canvas-footer .sleek-struct__group-bar');
    if (bar) {
        bar.style.display = selected.length >= 2 ? 'flex' : 'none';
    }
}

/* Group button */
document.addEventListener('click', function(e) {
    var btn = e.target.closest('.sleek-struct__group-btn');
    if (!btn) return;

    var editor = btn.closest('.sleek-struct') || btn.closest('.builder__canvas-footer');
    var canvas = btn.closest('.builder__canvas') || btn.closest('.sleek-struct');
    var url = btn.dataset.efUrl;
    var selected = canvas.querySelectorAll('.builder__item.selected, .sleek-struct__tile.selected');
    if (selected.length < 2) return;

    var keys = Array.from(selected).map(function(t) {
        return t.dataset.key || t.querySelector('[data-key]').dataset.key;
    });
    var bar = btn.closest('.sleek-struct__group-bar');
    var groupKey = bar.querySelector('[data-field="group_key"]').value.trim();
    var groupLabel = bar.querySelector('[data-field="group_label"]').value.trim();

    if (!groupKey) {
        bar.querySelector('[data-field="group_key"]').focus();
        return;
    }

    _efPost(url, JSON.stringify({
        action: 'group_eigenforms',
        keys: keys,
        group_key: groupKey,
        group_label: groupLabel || groupKey
    }));
});

function _efPost(url, body) {
    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'text/html'
        },
        body: body
    }).then(function(resp) {
        return resp.text();
    }).then(function(html) {
        var scrollY = window.scrollY;
        document.getElementById('page-content').innerHTML = html;
        window.scrollTo(0, scrollY);
    });
}
