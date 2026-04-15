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

/* One-click add eigenform (sleek theme) */
document.addEventListener('click', function(e) {
    var el = e.target.closest('[data-ef-add]');
    if (!el) return;
    e.preventDefault();
    _efPost(el.getAttribute('data-ef-add'), JSON.stringify({
        action: 'add_eigenform',
        type: el.getAttribute('data-type')
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

/* Drag-and-drop reorder */
document.addEventListener('dragstart', function(e) {
    var tile = e.target.closest('.sleek-struct__tile');
    if (!tile) return;
    e.dataTransfer.setData('text/plain', tile.dataset.key);
    e.dataTransfer.effectAllowed = 'move';
    tile.classList.add('dragging');
});

document.addEventListener('dragend', function(e) {
    var tile = e.target.closest('.sleek-struct__tile');
    if (tile) tile.classList.remove('dragging');
    _efClearDropFeedback();
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
    e.dataTransfer.dropEffect = 'move';
    _efClearDropFeedback();

    var container = zone.container;

    /* Check if hovering over a container tile (for reparent) */
    var hoverTile = e.target.closest('.sleek-struct__tile--container');
    if (hoverTile && !hoverTile.classList.contains('dragging')) {
        var rect = hoverTile.getBoundingClientRect();
        var zoneY = (e.clientY - rect.top) / rect.height;
        /* Middle 60% of the tile = drop-into-container zone */
        if (zoneY > 0.2 && zoneY < 0.8) {
            hoverTile.classList.add('drop-target');
            return;
        }
    }

    /* Insertion-line reorder among sibling tiles in this container */
    var tiles = Array.from(container.querySelectorAll(':scope > .sleek-struct__tile:not(.dragging)'));
    var indicator = document.createElement('div');
    indicator.className = 'sleek-struct__drop-indicator';
    var inserted = false;

    for (var i = 0; i < tiles.length; i++) {
        var rect = tiles[i].getBoundingClientRect();
        if (e.clientY < rect.top + rect.height / 2) {
            container.insertBefore(indicator, tiles[i]);
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

    var key = e.dataTransfer.getData('text/plain');
    /* Find the page URL from the top-level list */
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
    var siblings = Array.from(container.querySelectorAll(':scope > .sleek-struct__tile'));
    var targetIndex = siblings.length;

    if (indicator) {
        var pos = 0;
        var node = container.firstElementChild;
        while (node && node !== indicator) {
            if (node.classList && node.classList.contains('sleek-struct__tile')
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

/* Multi-select tiles */
document.addEventListener('click', function(e) {
    var tile = e.target.closest('.sleek-struct__tile');
    if (!tile) return;
    /* Don't interfere with buttons inside the tile */
    if (e.target.closest('button') || e.target.closest('[data-ef-post]')) return;

    tile.classList.toggle('selected');
    _efUpdateGroupBar(tile.closest('.sleek-struct'));
});

function _efUpdateGroupBar(editor) {
    if (!editor) return;
    var selected = editor.querySelectorAll('.sleek-struct__tile.selected');
    var bar = editor.querySelector('.sleek-struct__group-bar');
    if (bar) {
        bar.style.display = selected.length >= 2 ? 'flex' : 'none';
    }
}

/* Group button */
document.addEventListener('click', function(e) {
    var btn = e.target.closest('.sleek-struct__group-btn');
    if (!btn) return;

    var editor = btn.closest('.sleek-struct');
    var url = btn.dataset.efUrl;
    var selected = editor.querySelectorAll('.sleek-struct__tile.selected');
    if (selected.length < 2) return;

    var keys = Array.from(selected).map(function(t) { return t.dataset.key; });
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
