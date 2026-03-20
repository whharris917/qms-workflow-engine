/* ======================================================================
   RENDERER REGISTRY — pluggable rendering system
   Each renderer is an object with:
     .id        — unique string key
     .label     — button text
     .init(container)       — build DOM inside container, called once
     .update(state, msg)    — redraw with new agent state + last message
     .activate()            — called when switching TO this renderer
     .deactivate()          — called when switching AWAY
   ====================================================================== */

var renderers = {};        // id -> renderer object
var activeRenderer = null; // currently active renderer id
var agentState = null;     // latest parsed page JSON
var lastRaw = null;        // latest raw content string
var lastMessage = '';
var currentFeedback = null;  // latest Feedback from POST result
var viewMode = 'full';        // 'full' or 'feedback'

/* Renderer availability is declared by the workflow, not guessed from data shape. */
var allowedRenderers = window._WFE_ALLOWED_RENDERERS || [];

/* Hierarchical renderer metadata:
   Each renderer can declare: format, verbosity, style.
   The top-level format defines what dimensions it exposes.
   Selector UI auto-adapts: only shows sub-selectors if the format has multiple options. */
var formatIndex = {};  // format -> [{id, verbosity, style, verbosity_label, style_label}]
var activeFormat = null;
var activeVerbosity = null;
var activeStyle = null;

function registerRenderer(r) {
    renderers[r.id] = r;
    /* Create container div */
    var container = document.createElement('div');
    container.id = 'rc-' + r.id;
    container.className = 'renderer-container';
    document.getElementById('view-frame').appendChild(container);
    r._container = container;
    r.init(container);

    /* Index by format for hierarchical selection */
    var fmt = r.format || r.id;
    if (!formatIndex[fmt]) formatIndex[fmt] = [];
    formatIndex[fmt].push({
        id: r.id,
        verbosity: r.verbosity || 'default',
        style: r.style || 'default',
        verbosity_label: r.verbosity_label || r.verbosity || 'Default',
        style_label: r.style_label || r.style || 'Default',
    });
}

function buildModeToggle() {
    /* Build the hierarchical selector UI after all renderers are registered. */
    var toggle = document.getElementById('mode-toggle');
    toggle.innerHTML = '';

    /* Format buttons — one per format that has at least one allowed renderer */
    var formats = Object.keys(formatIndex);
    for (var i = 0; i < formats.length; i++) {
        var fmt = formats[i];
        var entries = formatIndex[fmt];
        var hasAllowed = entries.some(function(e) { return allowedRenderers.indexOf(e.id) >= 0; });
        if (!hasAllowed) continue;
        var btn = document.createElement('button');
        btn.className = 'mode-btn';
        btn.id = 'btn-fmt-' + fmt;
        btn.textContent = entries[0].id === fmt ? (renderers[fmt] || {}).label || fmt : fmt;
        /* Use the format label from the first renderer's label if format === id (single-option) */
        if (entries.length === 1 && renderers[entries[0].id]) {
            btn.textContent = renderers[entries[0].id].label || fmt;
        } else {
            /* Multi-option format: use format name capitalized */
            btn.textContent = fmt.charAt(0).toUpperCase() + fmt.slice(1);
        }
        btn.setAttribute('data-format', fmt);
        btn.onclick = (function(f) { return function() { selectFormat(f); }; })(fmt);
        toggle.appendChild(btn);
    }

    /* Sub-selector containers */
    var subBar = document.getElementById('sub-toggle');
    if (!subBar) {
        subBar = document.createElement('div');
        subBar.id = 'sub-toggle';
        subBar.className = 'mode-toggle';
        subBar.style.marginLeft = '0';
        toggle.parentNode.insertBefore(subBar, toggle.nextSibling);
    }
}

function selectFormat(fmt) {
    activeFormat = fmt;
    var entries = formatIndex[fmt] || [];

    /* Determine available verbosities and styles */
    var verbosities = [], styles = [];
    var vSet = {}, sSet = {};
    for (var i = 0; i < entries.length; i++) {
        if (!vSet[entries[i].verbosity]) { verbosities.push(entries[i]); vSet[entries[i].verbosity] = true; }
        if (!sSet[entries[i].style]) { styles.push(entries[i]); sSet[entries[i].style] = true; }
    }

    /* Build sub-selectors if format has multiple options */
    var subBar = document.getElementById('sub-toggle');
    subBar.innerHTML = '';

    var hasMultipleVerbosities = Object.keys(vSet).length > 1;
    var hasMultipleStyles = Object.keys(sSet).length > 1;

    if (hasMultipleVerbosities) {
        var sep = document.createElement('span');
        sep.style.cssText = 'color:#333;margin:0 0.3rem;';
        sep.textContent = '|';
        subBar.appendChild(sep);
        for (var vi = 0; vi < verbosities.length; vi++) {
            var vb = document.createElement('button');
            vb.className = 'mode-btn';
            vb.id = 'btn-verb-' + verbosities[vi].verbosity;
            vb.textContent = verbosities[vi].verbosity_label;
            vb.setAttribute('data-verbosity', verbosities[vi].verbosity);
            vb.onclick = (function(v) { return function() { selectVerbosity(v); }; })(verbosities[vi].verbosity);
            subBar.appendChild(vb);
        }
    }

    if (hasMultipleStyles) {
        var sep2 = document.createElement('span');
        sep2.style.cssText = 'color:#333;margin:0 0.3rem;';
        sep2.textContent = '|';
        subBar.appendChild(sep2);
        for (var si = 0; si < styles.length; si++) {
            var sb = document.createElement('button');
            sb.className = 'mode-btn';
            sb.id = 'btn-style-' + styles[si].style;
            sb.textContent = styles[si].style_label;
            sb.setAttribute('data-style', styles[si].style);
            sb.onclick = (function(s) { return function() { selectStyle(s); }; })(styles[si].style);
            subBar.appendChild(sb);
        }
    }

    /* Pick defaults */
    activeVerbosity = hasMultipleVerbosities ? (activeVerbosity && vSet[activeVerbosity] ? activeVerbosity : verbosities[0].verbosity) : entries[0].verbosity;
    activeStyle = hasMultipleStyles ? (activeStyle && sSet[activeStyle] ? activeStyle : styles[0].style) : entries[0].style;

    _activateRendererFromSelection();
}

function selectVerbosity(v) {
    activeVerbosity = v;
    _activateRendererFromSelection();
}

function selectStyle(s) {
    activeStyle = s;
    _activateRendererFromSelection();
}

function _activateRendererFromSelection() {
    /* Find the renderer matching current format + verbosity + style */
    var entries = formatIndex[activeFormat] || [];
    var match = null;
    for (var i = 0; i < entries.length; i++) {
        if (entries[i].verbosity === activeVerbosity && entries[i].style === activeStyle) {
            match = entries[i].id;
            break;
        }
    }
    /* Fallback: match format + verbosity, or just format */
    if (!match) {
        for (var i = 0; i < entries.length; i++) {
            if (entries[i].verbosity === activeVerbosity) { match = entries[i].id; break; }
        }
    }
    if (!match && entries.length) match = entries[0].id;
    if (match) setMode(match);
}

function setMode(id) {
    /* Non-raw renderers force Full mode */
    if (id !== 'raw' && viewMode === 'feedback') {
        viewMode = 'full';
        document.getElementById('btn-full').classList.add('active');
        document.getElementById('btn-feedback').classList.remove('active');
    }
    if (activeRenderer === id) return;
    /* Deactivate previous */
    if (activeRenderer && renderers[activeRenderer]) {
        renderers[activeRenderer]._container.classList.remove('active');
        renderers[activeRenderer].deactivate();
    }
    /* Activate new */
    activeRenderer = id;
    var r = renderers[id];
    r._container.classList.add('active');
    r.activate();
    /* Update button highlights */
    _updateToggleHighlights();
    if (agentState) dispatchRender();
}

function _updateToggleHighlights() {
    /* Highlight active format button */
    var fmtBtns = document.querySelectorAll('#mode-toggle .mode-btn');
    for (var i = 0; i < fmtBtns.length; i++) {
        fmtBtns[i].classList.toggle('active', fmtBtns[i].getAttribute('data-format') === activeFormat);
    }
    /* Highlight active verbosity/style buttons */
    var subBtns = document.querySelectorAll('#sub-toggle .mode-btn');
    for (var i = 0; i < subBtns.length; i++) {
        var isVerb = subBtns[i].getAttribute('data-verbosity');
        var isStyle = subBtns[i].getAttribute('data-style');
        if (isVerb) subBtns[i].classList.toggle('active', isVerb === activeVerbosity);
        if (isStyle) subBtns[i].classList.toggle('active', isStyle === activeStyle);
    }
}

function setViewMode(mode) {
    viewMode = mode;
    document.getElementById('btn-full').classList.toggle('active', mode === 'full');
    document.getElementById('btn-feedback').classList.toggle('active', mode === 'feedback');
    /* Feedback forces Raw renderer */
    if (mode === 'feedback' && activeRenderer !== 'raw') {
        setMode('raw');
        return; /* setMode already calls dispatchRender */
    }
    /* Re-render with current data */
    if (activeRenderer && renderers[activeRenderer]) {
        dispatchRender();
    }
}

function dispatchRender() {
    var r = renderers[activeRenderer];
    if (!r) return;
    if (viewMode === 'feedback' && activeRenderer === 'raw') {
        if (currentFeedback) {
            r.update(currentFeedback, currentFeedback.attempted_action || '', null);
        } else {
            r.update({}, '(no feedback yet — perform an action to see feedback)', null);
        }
    } else {
        r.update(agentState, lastMessage, currentFeedback);
    }
}

function broadcastState(state, msg, feedback) {
    agentState = state;
    lastMessage = msg;
    currentFeedback = feedback || null;
    if (activeRenderer && renderers[activeRenderer]) {
        dispatchRender();
    }
}

/* ── State extraction from SSE payloads ── */
function extractState(raw, feedback) {
    var obj;
    try { obj = typeof raw === 'string' ? JSON.parse(raw) : raw; } catch(e) { return; }
    if (!obj || !obj.state) return;
    lastRaw = typeof raw === 'string' ? raw : JSON.stringify(raw);
    broadcastState(obj, obj.message || '', feedback);
}
