/**
 * Component event delegation.
 *
 * Components control their own interaction by emitting data attributes.
 * This script is a thin mechanism that reads those attributes and
 * executes the fetch+swap cycle. It does not contain any component
 * logic — the component dictates the URL, body, and input strategy.
 *
 * Protocols:
 *   data-c-post  + data-c-body      — static-body click (buttons)
 *   data-c-submit (on <form>)        — form submission, body from fields
 *   data-c-change + data-c-key      — checkbox: {key: checked}
 *   data-c-change + data-c-field    — radio/input: {field: value}
 *   data-c-change + data-c-template — complex: JSON with __VALUE replaced
 */

/* Static-body clicks */
document.addEventListener('click', function(e) {
    var el = e.target.closest('[data-c-post]');
    if (!el) return;
    e.preventDefault();
    _cPost(el.getAttribute('data-c-post'), el.getAttribute('data-c-body'));
});

/* One-click add component (sleek theme + builder palette) */
document.addEventListener('click', function(e) {
    var el = e.target.closest('[data-c-add]');
    if (!el) return;
    e.preventDefault();
    var type = el.getAttribute('data-type') || el.getAttribute('data-c-palette-type');
    if (!type) return;
    _cPost(el.getAttribute('data-c-add'), JSON.stringify({
        action: 'add_component',
        type: type
    }));
});

/* Form submissions — body built from named form fields */
document.addEventListener('submit', function(e) {
    var form = e.target.closest('form[data-c-submit]');
    if (!form) return;
    e.preventDefault();
    var body = {};
    new FormData(form).forEach(function(v, k) { body[k] = v; });
    _cPost(form.getAttribute('data-c-submit'), JSON.stringify(body));
});

/* Immediate-change elements (checkbox, radio, select) */
document.addEventListener('change', function(e) {
    var el = e.target.closest('[data-c-change]');
    if (!el) return;
    var url = el.getAttribute('data-c-change');
    var body;
    if (el.hasAttribute('data-c-key')) {
        body = {};
        body[el.getAttribute('data-c-key')] = el.checked;
    } else if (el.hasAttribute('data-c-field')) {
        body = {};
        body[el.getAttribute('data-c-field')] = el.value;
    } else if (el.hasAttribute('data-c-template')) {
        body = JSON.parse(el.getAttribute('data-c-template'));
        for (var k in body) {
            if (body[k] === '__VALUE') body[k] = el.value;
        }
    }
    if (body) _cPost(url, JSON.stringify(body));
});

/* ---------------------------------------------------------------
 * Builder: palette drag (add from type palette to canvas)
 * --------------------------------------------------------------- */

/* Drag context — stashed on dragstart, read during dragover
   (dataTransfer.getData() is blocked during dragover for security). */
var _cDragCtx = null;

document.addEventListener('dragstart', function(e) {
    var type = e.target.closest('[data-c-palette-type]');
    if (!type) return;
    e.dataTransfer.setData('application/c-type', type.dataset.cPaletteType);
    e.dataTransfer.setData('application/c-url', type.dataset.cAdd);
    e.dataTransfer.effectAllowed = 'copy';
    type.classList.add('dragging');
    _cDragCtx = { palette: true, type: type.dataset.cPaletteType,
                   url: type.dataset.cAdd };
});

document.addEventListener('dragend', function(e) {
    var type = e.target.closest('[data-c-palette-type]');
    if (type) type.classList.remove('dragging');
    _cDragCtx = null;
    _cHideDragTooltip();
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
    if (e.target.closest('[data-c-palette-type]')) return;

    /* Block drag: leaf (.blk--leaf) or container header (.blk__head) */
    var handle = e.target.closest('.blk--leaf, .blk__head');
    if (!handle) return;
    var blk = _blkFromDragHandle(handle);
    if (!blk) return;

    e.dataTransfer.setData('text/plain', blk.dataset.key);
    e.dataTransfer.effectAllowed = 'move';
    blk.classList.add('dragging');
    _cDragCtx = { palette: false, key: blk.dataset.key };
});

/* Drag-and-drop: end */
document.addEventListener('dragend', function(e) {
    if (e.target.closest('[data-c-palette-type]')) return;
    var handle = e.target.closest('.blk--leaf, .blk__head');
    if (handle) {
        var blk = _blkFromDragHandle(handle);
        if (blk) blk.classList.remove('dragging');
    }
    _cClearDropFeedback();
    _cDragCtx = null;
    _cHideDragTooltip();
    document.querySelectorAll('.builder__canvas-body.drop-active').forEach(function(el) {
        el.classList.remove('drop-active');
    });
});

function _cClearDropFeedback() {
    document.querySelectorAll('.sleek-struct__drop-indicator').forEach(function(el) {
        el.remove();
    });
    document.querySelectorAll('.blk.drop-target').forEach(function(el) {
        el.classList.remove('drop-target');
    });
}

/* Drag tooltip — shows the POST body that would execute on release */
var _cDragTip = null;
function _cShowDragTooltip(x, y, url, body) {
    if (!_cDragTip) {
        _cDragTip = document.createElement('div');
        _cDragTip.className = 'c-drag-tooltip';
        document.body.appendChild(_cDragTip);
    }
    _cDragTip.textContent = 'POST ' + url + ' ' + JSON.stringify(body);
    _cDragTip.style.left = (x + 16) + 'px';
    _cDragTip.style.top = (y + 16) + 'px';
    _cDragTip.style.display = 'block';
}
function _cHideDragTooltip() {
    if (_cDragTip) _cDragTip.style.display = 'none';
}

/*
 * _cFindDropZone: find the nearest drop container.
 *   .blk__children (nested zone inside a container, has data-parent)
 *   .sleek-struct__list (top-level canvas body)
 */
function _cFindDropZone(target) {
    var children = target.closest('.blk__children');
    if (children) return { container: children, parent: children.dataset.parent };
    var list = target.closest('.sleek-struct__list');
    if (list) return { container: list, parent: null };
    return null;
}

/* Drag-and-drop: over */
document.addEventListener('dragover', function(e) {
    var zone = _cFindDropZone(e.target);
    if (!zone) { _cHideDragTooltip(); return; }
    e.preventDefault();

    var isPalette = e.dataTransfer.types.indexOf('application/c-type') !== -1;
    e.dataTransfer.dropEffect = isPalette ? 'copy' : 'move';

    _cClearDropFeedback();

    if (isPalette) {
        var canvasBody = e.target.closest('.builder__canvas-body');
        if (canvasBody) canvasBody.classList.add('drop-active');
    }

    var container = zone.container;
    var ctx = _cDragCtx;
    var tipUrl = ctx ? (ctx.url || (container.closest('.sleek-struct__list') || {}).dataset.cUrl || '') : '';

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
                        _cShowDragTooltip(e.clientX, e.clientY, tipUrl,
                            {action: 'reparent_component', key: ctx.key,
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
            body = {action: 'add_component', type: ctx.type, position: insertIdx};
        } else if (zone.parent) {
            var isChild = container.querySelector(':scope > .blk[data-key="' + ctx.key + '"]');
            if (!isChild) {
                body = {action: 'reparent_component', key: ctx.key, target: zone.parent};
            } else {
                body = {action: 'move_component', key: ctx.key, position: insertIdx};
                body.parent = zone.parent;
            }
        } else {
            body = {action: 'move_component', key: ctx.key, position: insertIdx};
        }
        _cShowDragTooltip(e.clientX, e.clientY, tipUrl, body);
    }
});

/* Drag-and-drop: drop */
document.addEventListener('drop', function(e) {
    _cDragCtx = null;
    _cHideDragTooltip();
    var zone = _cFindDropZone(e.target);
    if (!zone) return;
    e.preventDefault();

    document.querySelectorAll('.builder__canvas-body.drop-active').forEach(function(el) {
        el.classList.remove('drop-active');
    });

    /* Palette drop — add new component at position */
    var efType = e.dataTransfer.getData('application/c-type');
    if (efType) {
        var url = e.dataTransfer.getData('application/c-url');
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
        _cClearDropFeedback();
        _cPost(url, JSON.stringify({
            action: 'add_component', type: efType, position: targetIndex
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
    var url = list.dataset.cUrl;

    /* Reparent: drop on a container block's header highlight */
    var dropTarget = document.querySelector('.blk.drop-target');
    if (dropTarget) {
        var targetKey = dropTarget.dataset.key;
        _cClearDropFeedback();
        _cPost(url, JSON.stringify({
            action: 'reparent_component', key: key, target: targetKey
        }));
        return;
    }

    /* Dropping into a container's child zone: check if the item is
       already a child of that container.  If not, reparent first. */
    if (zone.parent) {
        var isChild = zone.container.querySelector(':scope > .blk[data-key="' + key + '"]');
        if (!isChild) {
            _cClearDropFeedback();
            _cPost(url, JSON.stringify({
                action: 'reparent_component', key: key, target: zone.parent
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

    var body = { action: 'move_component', key: key, position: targetIndex };
    if (zone.parent) body.parent = zone.parent;

    _cClearDropFeedback();
    _cPost(url, JSON.stringify(body));
});

/* Multi-select blocks (Ctrl+click) */
document.addEventListener('click', function(e) {
    /* Only on block drag handles */
    var handle = e.target.closest('.blk--leaf, .blk__head');
    if (!handle) return;
    if (e.target.closest('button') || e.target.closest('[data-c-post]')) return;
    if (!e.ctrlKey && !e.metaKey) return;

    var blk = _blkFromDragHandle(handle);
    if (!blk) return;
    blk.classList.toggle('selected');

    var canvas = blk.closest('.builder__canvas');
    _cUpdateGroupBar(canvas);
});

function _cUpdateGroupBar(editor) {
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
    var url = btn.dataset.cUrl;
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

    _cPost(url, JSON.stringify({
        action: 'group_components',
        keys: keys,
        group_key: groupKey,
        group_label: groupLabel || groupKey
    }));
});

/* Synthesize POST-body tooltips on every element whose POST body
   is deterministic at render time.  Covers two protocols:
     1. data-c-post + data-c-body  (static-body buttons)
     2. data-c-add  + data-c-palette-type  (palette one-click add)
   Input-dependent protocols (forms, change, group) are left alone
   since their bodies depend on user input at interaction time. */
function _cSyncTooltips() {
    document.querySelectorAll('[data-c-post][data-c-body]').forEach(function(el) {
        el.setAttribute('title',
            'POST ' + el.getAttribute('data-c-post') +
            ' ' + el.getAttribute('data-c-body'));
    });
    document.querySelectorAll('[data-c-add][data-c-palette-type]').forEach(function(el) {
        el.setAttribute('title',
            'POST ' + el.getAttribute('data-c-add') +
            ' {"action":"add_component","type":"' +
            el.getAttribute('data-c-palette-type') + '"}');
    });
}
_cSyncTooltips();

/* Morphdom integration: in-place DOM diff instead of innerHTML swap.
 * Preserves focus, scroll (window + nested), caret position, in-progress
 * input values, <details> open/closed, and CSS transitions in flight.
 * Falls back to innerHTML swap if morphdom isn't loaded. */
function _cSwap(html) {
    var root = document.getElementById('page-content');
    if (typeof morphdom === 'undefined') {
        var scrollY = window.scrollY;
        root.innerHTML = html;
        window.scrollTo(0, scrollY);
        return;
    }
    morphdom(root, '<div id="page-content">' + html + '</div>', {
        /* If a focused input would be morphed, leave it alone so the user
         * doesn't lose what they're typing. The structural diff still
         * happens around it. */
        onBeforeElUpdated: function(fromEl, toEl) {
            if (fromEl === document.activeElement &&
                (fromEl.tagName === 'INPUT' || fromEl.tagName === 'TEXTAREA' ||
                 fromEl.tagName === 'SELECT')) {
                return false;
            }
            return true;
        }
    });
}

function _cPost(url, body) {
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
        _cSwap(html);
        _cSyncTooltips();
    });
}
