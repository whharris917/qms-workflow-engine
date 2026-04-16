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
        body = {};
        body[el.getAttribute('data-ef-key')] = el.checked;
    } else if (el.hasAttribute('data-ef-field')) {
        body = {};
        body[el.getAttribute('data-ef-field')] = el.value;
    } else if (el.hasAttribute('data-ef-template')) {
        body = JSON.parse(el.getAttribute('data-ef-template'));
        for (var k in body) {
            if (body[k] === '__VALUE') body[k] = el.value;
        }
    }
    if (body) _efPost(url, JSON.stringify(body));
});

/* ---------------------------------------------------------------
 * Builder: palette drag (add from type palette to canvas)
 * --------------------------------------------------------------- */

/* Drag context — stashed on dragstart, read during dragover
   (dataTransfer.getData() is blocked during dragover for security). */
var _efDragCtx = null;

document.addEventListener('dragstart', function(e) {
    var type = e.target.closest('[data-ef-palette-type]');
    if (!type) return;
    e.dataTransfer.setData('application/ef-type', type.dataset.efPaletteType);
    e.dataTransfer.setData('application/ef-url', type.dataset.efAdd);
    e.dataTransfer.effectAllowed = 'copy';
    type.classList.add('dragging');
    _efDragCtx = { palette: true, type: type.dataset.efPaletteType,
                   url: type.dataset.efAdd };
});

document.addEventListener('dragend', function(e) {
    var type = e.target.closest('[data-ef-palette-type]');
    if (type) type.classList.remove('dragging');
    _efDragCtx = null;
    _efHideDragTooltip();
});

/* ---------------------------------------------------------------
 * Schematic canvas: drag-and-drop reorder + multi-select + group
 *
 * Draggable elements:
 *   .blk--leaf  (entire block is draggable)
 *   .blk__head  (header bar of container blocks)
 * Drop zones:
 *   .sleek-struct__list  (top-level canvas body)
 *   .blk__children       (inside containers, has data-parent)
 * --------------------------------------------------------------- */

/* Helper: find the .blk ancestor that owns this drag handle */
function _blkFromDragHandle(el) {
    if (el.classList.contains('blk')) return el;
    return el.closest('.blk');
}

/* Drag-and-drop: start */
document.addEventListener('dragstart', function(e) {
    /* Palette drag handled above */
    if (e.target.closest('[data-ef-palette-type]')) return;

    /* Block drag: leaf (.blk--leaf) or container header (.blk__head) */
    var handle = e.target.closest('.blk--leaf, .blk__head');
    if (!handle) return;
    var blk = _blkFromDragHandle(handle);
    if (!blk) return;

    e.dataTransfer.setData('text/plain', blk.dataset.key);
    e.dataTransfer.effectAllowed = 'move';
    blk.classList.add('dragging');
    _efDragCtx = { palette: false, key: blk.dataset.key };
});

/* Drag-and-drop: end */
document.addEventListener('dragend', function(e) {
    if (e.target.closest('[data-ef-palette-type]')) return;
    var handle = e.target.closest('.blk--leaf, .blk__head');
    if (handle) {
        var blk = _blkFromDragHandle(handle);
        if (blk) blk.classList.remove('dragging');
    }
    _efClearDropFeedback();
    _efDragCtx = null;
    _efHideDragTooltip();
    document.querySelectorAll('.builder__canvas-body.drop-active').forEach(function(el) {
        el.classList.remove('drop-active');
    });
});

function _efClearDropFeedback() {
    document.querySelectorAll('.sleek-struct__drop-indicator').forEach(function(el) {
        el.remove();
    });
    document.querySelectorAll('.blk.drop-target').forEach(function(el) {
        el.classList.remove('drop-target');
    });
}

/* Drag tooltip — shows the POST body that would execute on release */
var _efDragTip = null;
function _efShowDragTooltip(x, y, url, body) {
    if (!_efDragTip) {
        _efDragTip = document.createElement('div');
        _efDragTip.className = 'ef-drag-tooltip';
        document.body.appendChild(_efDragTip);
    }
    _efDragTip.textContent = 'POST ' + url + ' ' + JSON.stringify(body);
    _efDragTip.style.left = (x + 16) + 'px';
    _efDragTip.style.top = (y + 16) + 'px';
    _efDragTip.style.display = 'block';
}
function _efHideDragTooltip() {
    if (_efDragTip) _efDragTip.style.display = 'none';
}

/*
 * _efFindDropZone: find the nearest drop container.
 *   .blk__children (nested zone inside a container, has data-parent)
 *   .sleek-struct__list (top-level canvas body)
 */
function _efFindDropZone(target) {
    var children = target.closest('.blk__children');
    if (children) return { container: children, parent: children.dataset.parent };
    var list = target.closest('.sleek-struct__list');
    if (list) return { container: list, parent: null };
    return null;
}

/* Drag-and-drop: over */
document.addEventListener('dragover', function(e) {
    var zone = _efFindDropZone(e.target);
    if (!zone) { _efHideDragTooltip(); return; }
    e.preventDefault();

    var isPalette = e.dataTransfer.types.indexOf('application/ef-type') !== -1;
    e.dataTransfer.dropEffect = isPalette ? 'copy' : 'move';

    _efClearDropFeedback();

    if (isPalette) {
        var canvasBody = e.target.closest('.builder__canvas-body');
        if (canvasBody) canvasBody.classList.add('drop-active');
    }

    var container = zone.container;
    var ctx = _efDragCtx;
    var tipUrl = ctx ? (ctx.url || (container.closest('.sleek-struct__list') || {}).dataset.efUrl || '') : '';

    /* Reparent: hovering over a container block's header (middle 60%) */
    if (!isPalette) {
        var hoverBlock = e.target.closest('.blk--container');
        if (hoverBlock && !hoverBlock.classList.contains('dragging')) {
            var headEl = hoverBlock.querySelector(':scope > .blk__head');
            if (headEl) {
                var rect = headEl.getBoundingClientRect();
                var zoneY = (e.clientY - rect.top) / rect.height;
                if (zoneY > 0.2 && zoneY < 0.8) {
                    hoverBlock.classList.add('drop-target');
                    if (ctx && !ctx.palette) {
                        _efShowDragTooltip(e.clientX, e.clientY, tipUrl,
                            {action: 'reparent_eigenform', key: ctx.key,
                             target: hoverBlock.dataset.key});
                    }
                    return;
                }
            }
        }
    }

    /* Insertion line between sibling blocks */
    var siblings = Array.from(container.querySelectorAll(
        ':scope > .blk:not(.dragging)'
    ));
    var indicator = document.createElement('div');
    indicator.className = 'sleek-struct__drop-indicator';
    var insertIdx = siblings.length;

    for (var i = 0; i < siblings.length; i++) {
        var rect = siblings[i].getBoundingClientRect();
        if (e.clientY < rect.top + rect.height / 2) {
            container.insertBefore(indicator, siblings[i]);
            insertIdx = i;
            break;
        }
    }
    if (insertIdx === siblings.length) {
        container.appendChild(indicator);
    }

    /* Show drag tooltip with the would-be POST body */
    if (ctx) {
        var body;
        if (ctx.palette) {
            body = {action: 'add_eigenform', type: ctx.type, position: insertIdx};
        } else if (zone.parent) {
            var isChild = container.querySelector(':scope > .blk[data-key="' + ctx.key + '"]');
            if (!isChild) {
                body = {action: 'reparent_eigenform', key: ctx.key, target: zone.parent};
            } else {
                body = {action: 'move_eigenform', key: ctx.key, position: insertIdx};
                body.parent = zone.parent;
            }
        } else {
            body = {action: 'move_eigenform', key: ctx.key, position: insertIdx};
        }
        _efShowDragTooltip(e.clientX, e.clientY, tipUrl, body);
    }
});

/* Drag-and-drop: drop */
document.addEventListener('drop', function(e) {
    _efDragCtx = null;
    _efHideDragTooltip();
    var zone = _efFindDropZone(e.target);
    if (!zone) return;
    e.preventDefault();

    document.querySelectorAll('.builder__canvas-body.drop-active').forEach(function(el) {
        el.classList.remove('drop-active');
    });

    /* Palette drop — add new eigenform at position */
    var efType = e.dataTransfer.getData('application/ef-type');
    if (efType) {
        var url = e.dataTransfer.getData('application/ef-url');
        var container = zone.container;
        var indicator = container.querySelector(':scope > .sleek-struct__drop-indicator');
        var siblings = Array.from(container.querySelectorAll(':scope > .blk'));
        var targetIndex = siblings.length;
        if (indicator) {
            var pos = 0;
            var node = container.firstElementChild;
            while (node && node !== indicator) {
                if (node.classList && node.classList.contains('blk')) pos++;
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

    /* Block reorder / reparent */
    var key = e.dataTransfer.getData('text/plain');
    var list = e.target.closest('.sleek-struct__list') ||
               (function() {
                   var c = e.target.closest('.blk__children');
                   return c ? c.closest('.sleek-struct__list') : null;
               })();
    if (!list) return;
    var url = list.dataset.efUrl;

    /* Reparent: drop on a container block's header highlight */
    var dropTarget = document.querySelector('.blk.drop-target');
    if (dropTarget) {
        var targetKey = dropTarget.dataset.key;
        _efClearDropFeedback();
        _efPost(url, JSON.stringify({
            action: 'reparent_eigenform', key: key, target: targetKey
        }));
        return;
    }

    /* Dropping into a container's child zone: check if the item is
       already a child of that container.  If not, reparent first. */
    if (zone.parent) {
        var isChild = zone.container.querySelector(':scope > .blk[data-key="' + key + '"]');
        if (!isChild) {
            _efClearDropFeedback();
            _efPost(url, JSON.stringify({
                action: 'reparent_eigenform', key: key, target: zone.parent
            }));
            return;
        }
    }

    /* Reorder via insertion line */
    var container = zone.container;
    var indicator = container.querySelector(':scope > .sleek-struct__drop-indicator');
    var siblings = Array.from(container.querySelectorAll(':scope > .blk'));
    var targetIndex = siblings.length;

    if (indicator) {
        var pos = 0;
        var node = container.firstElementChild;
        while (node && node !== indicator) {
            if (node.classList && node.classList.contains('blk')
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

/* Multi-select blocks (Ctrl+click) */
document.addEventListener('click', function(e) {
    /* Only on block drag handles */
    var handle = e.target.closest('.blk--leaf, .blk__head');
    if (!handle) return;
    if (e.target.closest('button') || e.target.closest('[data-ef-post]')) return;
    if (!e.ctrlKey && !e.metaKey) return;

    var blk = _blkFromDragHandle(handle);
    if (!blk) return;
    blk.classList.toggle('selected');

    var canvas = blk.closest('.builder__canvas');
    _efUpdateGroupBar(canvas);
});

function _efUpdateGroupBar(editor) {
    if (!editor) return;
    var selected = editor.querySelectorAll('.blk.selected');
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

    var canvas = btn.closest('.builder__canvas') || btn.closest('.sleek-struct');
    var url = btn.dataset.efUrl;
    var selected = canvas.querySelectorAll('.blk.selected');
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

/* Synthesize POST-body tooltips on every element whose POST body
   is deterministic at render time.  Covers two protocols:
     1. data-ef-post + data-ef-body  (static-body buttons)
     2. data-ef-add  + data-ef-palette-type  (palette one-click add)
   Input-dependent protocols (forms, change, group) are left alone
   since their bodies depend on user input at interaction time. */
function _efSyncTooltips() {
    document.querySelectorAll('[data-ef-post][data-ef-body]').forEach(function(el) {
        el.setAttribute('title',
            'POST ' + el.getAttribute('data-ef-post') +
            ' ' + el.getAttribute('data-ef-body'));
    });
    document.querySelectorAll('[data-ef-add][data-ef-palette-type]').forEach(function(el) {
        el.setAttribute('title',
            'POST ' + el.getAttribute('data-ef-add') +
            ' {"action":"add_eigenform","type":"' +
            el.getAttribute('data-ef-palette-type') + '"}');
    });
}
_efSyncTooltips();

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
        _efSyncTooltips();
    });
}
