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

/* Synthesize POST-body tooltips.  Covers three protocols:
     1. data-c-post + data-c-body  (static-body buttons)
     2. data-c-add  + data-c-palette-type  (palette one-click add)
     3. form[data-c-submit]  (form submit — body built from fields) */
function _cFormBody(form) {
    var body = {};
    new FormData(form).forEach(function(v, k) { body[k] = v; });
    return 'POST ' + form.getAttribute('data-c-submit') + ' ' + JSON.stringify(body);
}
function _cSyncFormTooltip(form) {
    var tip = _cFormBody(form);
    var btn = form.querySelector('button[type="submit"]');
    if (btn) btn.setAttribute('title', tip);
    form.querySelectorAll('input[name], textarea[name], select[name]').forEach(function(el) {
        el.setAttribute('title', tip);
    });
}
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
    document.querySelectorAll('form[data-c-submit]').forEach(_cSyncFormTooltip);
}
_cSyncTooltips();
document.addEventListener('input', function(e) {
    var form = e.target.closest('form[data-c-submit]');
    if (form) _cSyncFormTooltip(form);
});

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
    } else {
        morphdom(root, '<div id="page-content">' + html + '</div>', {
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
    document.dispatchEvent(new CustomEvent('c-page-updated'));
}

/* ---------------------------------------------------------------
 * Right-click context menu — human-only chrome layer.
 *
 * Actions here are things agents don't need: inspecting JSON,
 * toggling debug views, etc. No affordances, no parity tests.
 * --------------------------------------------------------------- */

(function() {
    var ctxMenu = null;
    var inspectPanel = null;
    var inspectState = null; /* { view, componentUrl, key, form, pageUrl, storeUrl, activeView } */

    /* Inject styles once */
    var style = document.createElement('style');
    style.textContent =
        /* Context menu */
        '.c-ctx-menu{position:fixed;z-index:10000;background:#1e1e1e;border:1px solid #555;' +
        'border-radius:4px;padding:4px 0;min-width:160px;box-shadow:0 4px 12px rgba(0,0,0,.5);font-family:inherit;font-size:13px}' +
        '.c-ctx-menu__item{padding:6px 16px;color:#ccc;cursor:pointer;display:flex;align-items:center;gap:8px}' +
        '.c-ctx-menu__item:hover{background:#2a2d2e;color:#fff}' +
        '.c-ctx-menu__icon{opacity:.7;font-size:12px;width:16px;text-align:center}' +
        /* Inspect panel */
        '.c-inspect{position:fixed;top:0;right:0;bottom:0;width:min(480px,45vw);min-width:240px;' +
        'z-index:9999;background:#1e1e1e;border-left:none;display:flex;flex-direction:row;' +
        'box-shadow:-4px 0 16px rgba(0,0,0,.4)}' +
        '.c-inspect__resize{width:5px;cursor:col-resize;background:#555;flex-shrink:0;' +
        'transition:background .15s}' +
        '.c-inspect__resize:hover,.c-inspect__resize.active{background:#2563eb}' +
        '.c-inspect__main{flex:1;display:flex;flex-direction:column;overflow:hidden}' +
        '.c-inspect__header{display:flex;align-items:center;padding:8px 12px;background:#22272e;' +
        'border-bottom:1px solid #444;gap:8px;flex-shrink:0}' +
        '.c-inspect__title{color:#ccc;font-size:12px;font-family:monospace;overflow:hidden;' +
        'text-overflow:ellipsis;white-space:nowrap;flex:1}' +
        '.c-inspect__badge{background:#2563eb;color:#fff;font-size:10px;padding:1px 6px;' +
        'border-radius:3px;font-family:sans-serif;flex-shrink:0}' +
        '.c-inspect__close{background:none;border:none;color:#aaa;font-size:18px;cursor:pointer;' +
        'padding:0 4px;line-height:1;flex-shrink:0}' +
        '.c-inspect__close:hover{color:#fff}' +
        '.c-inspect__btn{background:none;border:1px solid #555;color:#aaa;font-size:11px;' +
        'cursor:pointer;padding:2px 8px;border-radius:3px;flex-shrink:0;font-family:sans-serif}' +
        '.c-inspect__btn:hover{color:#fff;border-color:#888}' +
        '.c-inspect__sep{width:1px;height:16px;background:#444;flex-shrink:0}' +
        '.c-inspect__body{flex:1;overflow:auto;padding:8px 12px;font-size:12px;line-height:1.6;' +
        'font-family:Consolas,Monaco,"Courier New",monospace}' +
        '.c-inspect__loading{color:#888;font-style:italic;font-family:sans-serif}' +
        /* JSON tree */
        '.c-jt-row{white-space:nowrap}' +
        '.c-jt-children{padding-left:16px}' +
        '.c-jt-toggle{cursor:pointer;user-select:none}' +
        '.c-jt-toggle:hover .c-jt-arrow{color:#fff}' +
        '.c-jt-arrow{display:inline-block;width:14px;font-size:10px;color:#888;text-align:center;' +
        'font-family:sans-serif;flex-shrink:0}' +
        '.c-jt-key{color:#9cdcfe}' +
        '.c-jt-idx{color:#b5cea8}' +
        '.c-jt-str{color:#ce9178}' +
        '.c-jt-num{color:#b5cea8}' +
        '.c-jt-bool{color:#569cd6}' +
        '.c-jt-null{color:#569cd6;font-style:italic}' +
        '.c-jt-bracket{color:#888}' +
        '.c-jt-preview{color:#666}' +
        '.c-jt-target{border-left:2px solid #2563eb;margin-left:-2px}';
    document.head.appendChild(style);

    function esc(s) {
        var d = document.createElement('span');
        d.textContent = s;
        return d.innerHTML;
    }

    function jsonPreview(data) {
        if (Array.isArray(data)) {
            var items = [];
            for (var i = 0; i < Math.min(data.length, 3); i++) {
                if (data[i] === null) items.push('null');
                else if (typeof data[i] === 'object') items.push(Array.isArray(data[i]) ? '[…]' : '{…}');
                else if (typeof data[i] === 'string') {
                    var s = data[i].length > 20 ? data[i].substring(0, 20) + '…' : data[i];
                    items.push('"' + s + '"');
                }
                else items.push(String(data[i]));
            }
            if (data.length > 3) items.push('…');
            return '(' + data.length + ')\u00a0[' + items.join(', ') + ']';
        }
        var keys = Object.keys(data);
        var parts = [];
        for (var i = 0; i < Math.min(keys.length, 3); i++) {
            var v = data[keys[i]];
            var vs;
            if (v === null) vs = 'null';
            else if (typeof v === 'object') vs = Array.isArray(v) ? '('+v.length+') […]' : '{…}';
            else if (typeof v === 'string') {
                vs = '"' + (v.length > 20 ? v.substring(0, 20) + '…' : v) + '"';
            }
            else vs = String(v);
            parts.push(keys[i] + ': ' + vs);
        }
        if (keys.length > 3) parts.push('…');
        return '{' + parts.join(', ') + '}';
    }

    function matchesTarget(data, targetUrl) {
        if (!targetUrl || typeof data !== 'object' || data === null || Array.isArray(data)) return false;
        var affs = data.affordances;
        if (!Array.isArray(affs)) return false;
        for (var i = 0; i < affs.length; i++) {
            if (affs[i] && affs[i].url === targetUrl) return true;
        }
        return false;
    }

    /* Build a collapsible JSON tree.
     * targetUrl: the component URL to highlight and auto-expand to.
     * Returns { el: DOMElement, found: boolean }. */
    function buildTree(data, key, depth, targetUrl) {
        var keyHtml = '';
        if (key !== null && key !== undefined) {
            if (typeof key === 'number') {
                keyHtml = '<span class="c-jt-idx">' + key + '</span>: ';
            } else {
                keyHtml = '<span class="c-jt-key">"' + esc(key) + '"</span>: ';
            }
        }

        /* Primitives */
        if (data === null || typeof data !== 'object') {
            var row = document.createElement('div');
            row.className = 'c-jt-row';
            var cls, val;
            if (data === null) { cls = 'c-jt-null'; val = 'null'; }
            else if (typeof data === 'boolean') { cls = 'c-jt-bool'; val = String(data); }
            else if (typeof data === 'number') { cls = 'c-jt-num'; val = String(data); }
            else { cls = 'c-jt-str'; val = '"' + esc(String(data)) + '"'; }
            row.innerHTML = '<span class="c-jt-arrow"></span>' + keyHtml +
                '<span class="' + cls + '">' + val + '</span>';
            return { el: row, found: false };
        }

        /* Object or Array */
        var isArr = Array.isArray(data);
        var entries = isArr ? data : Object.keys(data);
        var open = isArr ? '[' : '{';
        var close = isArr ? ']' : '}';
        var isTarget = matchesTarget(data, targetUrl);

        /* Build children first so we know if the target is a descendant */
        var childEls = [];
        var childFound = false;
        if (isArr) {
            for (var i = 0; i < data.length; i++) {
                var cr = buildTree(data[i], i, depth + 1, targetUrl);
                childEls.push(cr.el);
                if (cr.found) childFound = true;
            }
        } else {
            for (var i = 0; i < entries.length; i++) {
                var cr = buildTree(data[entries[i]], entries[i], depth + 1, targetUrl);
                childEls.push(cr.el);
                if (cr.found) childFound = true;
            }
        }

        var found = isTarget || childFound;
        var expanded = (depth === 0) || isTarget || childFound;

        var wrapper = document.createElement('div');
        if (isTarget) wrapper.className = 'c-jt-target';
        wrapper.setAttribute('data-jt-close', close);

        /* Header row: arrow + key + bracket/preview */
        var header = document.createElement('div');
        header.className = 'c-jt-row c-jt-toggle';

        var arrowSpan = document.createElement('span');
        arrowSpan.className = 'c-jt-arrow';
        arrowSpan.textContent = expanded ? '\u25BC' : '\u25B6';

        var labelSpan = document.createElement('span');
        labelSpan.innerHTML = keyHtml;

        var bracketOpen = document.createElement('span');
        bracketOpen.className = 'c-jt-bracket';
        bracketOpen.textContent = open;

        var preview = document.createElement('span');
        preview.className = 'c-jt-preview';
        preview.textContent = expanded ? '' : '\u00a0' + jsonPreview(data);
        preview.style.display = expanded ? 'none' : 'inline';

        var bracketClose = document.createElement('span');
        bracketClose.className = 'c-jt-bracket';
        bracketClose.textContent = expanded ? '' : close;

        header.appendChild(arrowSpan);
        header.appendChild(labelSpan);
        header.appendChild(bracketOpen);
        header.appendChild(preview);
        header.appendChild(bracketClose);

        /* Children */
        var children = document.createElement('div');
        children.className = 'c-jt-children';
        children.style.display = expanded ? 'block' : 'none';
        for (var i = 0; i < childEls.length; i++) {
            children.appendChild(childEls[i]);
        }

        /* Closing bracket on its own line (visible when expanded) */
        var closingRow = document.createElement('div');
        closingRow.className = 'c-jt-row';
        closingRow.innerHTML = '<span class="c-jt-arrow"></span>' +
            '<span class="c-jt-bracket">' + close + '</span>';
        closingRow.style.display = expanded ? 'block' : 'none';

        /* Toggle */
        header.addEventListener('click', function() {
            var isOpen = children.style.display !== 'none';
            children.style.display = isOpen ? 'none' : 'block';
            closingRow.style.display = isOpen ? 'none' : 'block';
            preview.style.display = isOpen ? 'inline' : 'none';
            bracketClose.textContent = isOpen ? close : '';
            arrowSpan.textContent = isOpen ? '\u25B6' : '\u25BC';
        });

        wrapper.appendChild(header);
        wrapper.appendChild(children);
        wrapper.appendChild(closingRow);
        return { el: wrapper, found: found };
    }

    function dismissCtx() {
        if (ctxMenu) { ctxMenu.remove(); ctxMenu = null; }
    }

    function dismissInspect() {
        if (inspectPanel) { inspectPanel.remove(); inspectPanel = null; }
        inspectState = null;
    }

    /* ---- Data extractors for filtered views ---- */

    function collectAffordances(data, path) {
        var result = [];
        if (typeof data !== 'object' || data === null) return result;
        if (Array.isArray(data)) {
            for (var i = 0; i < data.length; i++)
                result = result.concat(collectAffordances(data[i], path));
            return result;
        }
        if (data.affordances && data.label) {
            var affs = data.affordances.filter(function(a) {
                return a && !a._floatable;
            });
            if (affs.length > 0)
                result.push({ label: data.label, path: path, affordances: affs });
        }
        var containers = ['components', 'sections', 'tabs', 'steps', 'component'];
        for (var i = 0; i < containers.length; i++) {
            var k = containers[i];
            if (data[k]) result = result.concat(collectAffordances(data[k], path + '/' + k));
        }
        return result;
    }

    function collectLabels(data, depth) {
        var result = [];
        if (typeof data !== 'object' || data === null) return result;
        if (Array.isArray(data)) {
            for (var i = 0; i < data.length; i++)
                result = result.concat(collectLabels(data[i], depth));
            return result;
        }
        if (data.label !== undefined) {
            var entry = { label: data.label, depth: depth };
            if (data.complete !== undefined) entry.complete = data.complete;
            result.push(entry);
        }
        var containers = ['components', 'sections', 'tabs', 'steps', 'component'];
        for (var i = 0; i < containers.length; i++) {
            if (data[containers[i]])
                result = result.concat(collectLabels(data[containers[i]], depth + 1));
        }
        return result;
    }

    /* ---- Panel infrastructure ---- */

    function showCtxMenu(x, y, url, key, form) {
        dismissCtx();
        var menu = document.createElement('div');
        menu.className = 'c-ctx-menu';
        menu.innerHTML =
            '<div class="c-ctx-menu__item" data-ctx-action="inspect">' +
            '<span class="c-ctx-menu__icon">{}</span>Inspect</div>' +
            '<div class="c-ctx-menu__item" data-ctx-action="affordances">' +
            '<span class="c-ctx-menu__icon">\u25B7</span>Affordances</div>' +
            '<div class="c-ctx-menu__item" data-ctx-action="data">' +
            '<span class="c-ctx-menu__icon">\u2261</span>Data</div>';
        document.body.appendChild(menu);
        ctxMenu = menu;

        var r = menu.getBoundingClientRect();
        menu.style.left = (x + r.width > window.innerWidth ? x - r.width : x) + 'px';
        menu.style.top = (y + r.height > window.innerHeight ? y - r.height : y) + 'px';

        menu.addEventListener('click', function(e) {
            var item = e.target.closest('[data-ctx-action]');
            if (!item) return;
            var action = item.dataset.ctxAction;
            dismissCtx();
            if (action === 'inspect') openPanel(url, key, form, 'inspect');
            else if (action === 'affordances') openPanel(url, key, form, 'affordances');
            else if (action === 'data') openPanel(url, key, form, 'data');
        });
    }

    function openPanel(componentUrl, key, form, view) {
        dismissInspect();

        var parts = componentUrl.split('/');
        var pageUrl = '/' + parts[1] + '/' + parts[2];
        var storeUrl = pageUrl + '/_store';

        inspectState = {
            view: view, componentUrl: componentUrl,
            key: key, form: form,
            pageUrl: pageUrl, storeUrl: storeUrl,
            activeView: view
        };

        var panel = document.createElement('div');
        panel.className = 'c-inspect';
        panel.innerHTML =
            '<div class="c-inspect__resize"></div>' +
            '<div class="c-inspect__main">' +
            '<div class="c-inspect__header">' +
            '<span class="c-inspect__badge">' + esc(form) + '</span>' +
            '<span class="c-inspect__title">' + esc(key) + '</span>' +
            '<button class="c-inspect__btn" data-inspect-action="expand" title="Expand All">Expand</button>' +
            '<button class="c-inspect__btn" data-inspect-action="collapse" title="Collapse All">Collapse</button>' +
            '<span class="c-inspect__sep"></span>' +
            '<button class="c-inspect__btn" data-inspect-view="allAffordances" title="All page affordances">All Affs</button>' +
            '<button class="c-inspect__btn" data-inspect-view="labels" title="Component labels">Labels</button>' +
            '<button class="c-inspect__close" title="Close (Esc)">&times;</button>' +
            '</div>' +
            '<div class="c-inspect__body"><span class="c-inspect__loading">Loading\u2026</span></div>' +
            '</div>';
        document.body.appendChild(panel);
        inspectPanel = panel;

        var cachedPageData = null;
        var body = panel.querySelector('.c-inspect__body');

        panel.querySelector('.c-inspect__close').addEventListener('click', dismissInspect);

        /* Expand / Collapse All */
        panel.addEventListener('click', function(e) {
            var btn = e.target.closest('[data-inspect-action]');
            if (!btn) return;
            var expand = btn.dataset.inspectAction === 'expand';
            if (!body) return;
            body.querySelectorAll('[data-jt-close]').forEach(function(wrapper) {
                var cls = wrapper.getAttribute('data-jt-close');
                var toggle = wrapper.querySelector(':scope > .c-jt-toggle');
                var children = wrapper.querySelector(':scope > .c-jt-children');
                if (!toggle || !children) return;
                var closing = children.nextElementSibling;
                var arrow = toggle.querySelector('.c-jt-arrow');
                var preview = toggle.querySelector('.c-jt-preview');
                var bracketClose = toggle.lastElementChild;
                children.style.display = expand ? 'block' : 'none';
                if (closing) closing.style.display = expand ? 'block' : 'none';
                if (arrow) arrow.textContent = expand ? '\u25BC' : '\u25B6';
                if (preview) preview.style.display = expand ? 'none' : 'inline';
                if (bracketClose) bracketClose.textContent = expand ? '' : cls;
            });
        });

        /* View switcher buttons (All Affordances, Labels) */
        panel.addEventListener('click', function(e) {
            var btn = e.target.closest('[data-inspect-view]');
            if (!btn || !cachedPageData) return;
            var v = btn.dataset.inspectView;
            if (inspectState) inspectState.activeView = v;
            if (v === 'allAffordances') renderAllAffordances(cachedPageData);
            else if (v === 'labels') renderLabels(cachedPageData);
        });

        /* Resize handle drag */
        var handle = panel.querySelector('.c-inspect__resize');
        handle.addEventListener('mousedown', function(e) {
            e.preventDefault();
            handle.classList.add('active');
            var onMove = function(e) {
                var w = window.innerWidth - e.clientX;
                if (w >= 240) panel.style.width = w + 'px';
            };
            var onUp = function() {
                handle.classList.remove('active');
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
            };
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });

        function renderTree(data, target) {
            body.innerHTML = '';
            var tree = buildTree(data, null, 0, target);
            body.appendChild(tree.el);
            var tgt = body.querySelector('.c-jt-target');
            if (tgt) tgt.scrollIntoView({ block: 'center' });
        }

        function renderAllAffordances(pageData) {
            var groups = collectAffordances(pageData, '');
            if (groups.length === 0) {
                body.innerHTML = '<span class="c-inspect__loading">No affordances found</span>';
                return;
            }
            var obj = {};
            for (var i = 0; i < groups.length; i++) {
                obj[groups[i].label] = groups[i].affordances;
            }
            body.innerHTML = '';
            body.appendChild(buildTree(obj, null, 0, null).el);
        }

        function renderLabels(pageData) {
            var labels = collectLabels(pageData, 0);
            body.innerHTML = '';
            var frag = document.createDocumentFragment();
            for (var i = 0; i < labels.length; i++) {
                var row = document.createElement('div');
                row.className = 'c-jt-row';
                var indent = labels[i].depth * 16;
                var dot = labels[i].complete
                    ? '<span class="c-jt-bool" style="margin-right:6px">\u25CF</span>'
                    : '<span class="c-jt-null" style="margin-right:6px">\u25CB</span>';
                row.style.paddingLeft = indent + 'px';
                row.innerHTML = dot + '<span class="c-jt-key">' + esc(labels[i].label) + '</span>';
                frag.appendChild(row);
            }
            body.appendChild(frag);
        }

        /* Load initial view */
        if (view === 'inspect') {
            fetch(pageUrl, { headers: { 'Accept': 'application/json' } })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    cachedPageData = data;
                    renderTree(data, componentUrl);
                })
                .catch(function() { body.innerHTML = '<span class="c-inspect__loading">Failed to load</span>'; });
        } else if (view === 'affordances') {
            fetch(componentUrl, { headers: { 'Accept': 'application/json' } })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var affs = data.affordances || [];
                    body.innerHTML = '';
                    body.appendChild(buildTree(affs, null, 0, null).el);
                    /* Also fetch page data for toolbar buttons */
                    return fetch(pageUrl, { headers: { 'Accept': 'application/json' } });
                })
                .then(function(r) { return r.json(); })
                .then(function(data) { cachedPageData = data; })
                .catch(function() { body.innerHTML = '<span class="c-inspect__loading">Failed to load</span>'; });
        } else if (view === 'data') {
            fetch(storeUrl)
                .then(function(r) { return r.json(); })
                .then(function(storeData) {
                    var urlParts = componentUrl.split('/');
                    var scope = urlParts.length > 4 ? urlParts[urlParts.length - 2] : key;
                    body.innerHTML = '';
                    body.appendChild(buildTree(storeData[scope] || {}, null, 0, null).el);
                    /* Also fetch page data for toolbar buttons */
                    return fetch(pageUrl, { headers: { 'Accept': 'application/json' } });
                })
                .then(function(r) { return r.json(); })
                .then(function(data) { cachedPageData = data; })
                .catch(function() { body.innerHTML = '<span class="c-inspect__loading">Failed to load</span>'; });
        }
    }

    document.addEventListener('contextmenu', function(e) {
        var comp = e.target.closest('[data-url]');
        if (!comp) return;
        e.preventDefault();
        showCtxMenu(
            e.clientX, e.clientY,
            comp.getAttribute('data-url'),
            comp.getAttribute('data-key'),
            comp.getAttribute('data-form')
        );
    });

    document.addEventListener('mousedown', function(e) {
        if (ctxMenu && !ctxMenu.contains(e.target)) dismissCtx();
    });

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            if (inspectPanel) { dismissInspect(); return; }
            if (ctxMenu) { dismissCtx(); return; }
        }
    });

    /* Live refresh: re-render the inspect panel when the page updates */
    document.addEventListener('c-page-updated', function() {
        if (!inspectPanel || !inspectState) return;
        var s = inspectState;
        var body = inspectPanel.querySelector('.c-inspect__body');
        if (!body) return;
        var scrollTop = body.scrollTop;
        var v = s.activeView;

        if (v === 'inspect') {
            fetch(s.pageUrl, { headers: { 'Accept': 'application/json' } })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    body.innerHTML = '';
                    var tree = buildTree(data, null, 0, s.componentUrl);
                    body.appendChild(tree.el);
                    body.scrollTop = scrollTop;
                });
        } else if (v === 'affordances') {
            fetch(s.componentUrl, { headers: { 'Accept': 'application/json' } })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    body.innerHTML = '';
                    body.appendChild(buildTree(data.affordances || [], null, 0, null).el);
                    body.scrollTop = scrollTop;
                });
        } else if (v === 'data') {
            fetch(s.storeUrl)
                .then(function(r) { return r.json(); })
                .then(function(storeData) {
                    body.innerHTML = '';
                    var urlParts = s.componentUrl.split('/');
                    var scope = urlParts.length > 4 ? urlParts[urlParts.length - 2] : s.key;
                    body.appendChild(buildTree(storeData[scope] || {}, null, 0, null).el);
                    body.scrollTop = scrollTop;
                });
        } else if (v === 'allAffordances') {
            fetch(s.pageUrl, { headers: { 'Accept': 'application/json' } })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var groups = collectAffordances(data, '');
                    var obj = {};
                    for (var i = 0; i < groups.length; i++)
                        obj[groups[i].label] = groups[i].affordances;
                    body.innerHTML = '';
                    body.appendChild(buildTree(obj, null, 0, null).el);
                    body.scrollTop = scrollTop;
                });
        } else if (v === 'labels') {
            fetch(s.pageUrl, { headers: { 'Accept': 'application/json' } })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var labels = collectLabels(data, 0);
                    body.innerHTML = '';
                    var frag = document.createDocumentFragment();
                    for (var i = 0; i < labels.length; i++) {
                        var row = document.createElement('div');
                        row.className = 'c-jt-row';
                        row.style.paddingLeft = (labels[i].depth * 16) + 'px';
                        var dot = labels[i].complete
                            ? '<span class="c-jt-bool" style="margin-right:6px">\u25CF</span>'
                            : '<span class="c-jt-null" style="margin-right:6px">\u25CB</span>';
                        row.innerHTML = dot + '<span class="c-jt-key">' + esc(labels[i].label) + '</span>';
                        frag.appendChild(row);
                    }
                    body.appendChild(frag);
                    body.scrollTop = scrollTop;
                });
        }
    });
})();

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
