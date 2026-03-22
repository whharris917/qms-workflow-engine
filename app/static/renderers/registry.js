/* ======================================================================
   RENDERER REGISTRY — two-mode rendering system
     'raw'   = Agent renderer (formatted JSON)
     'light' = Human renderer (interactive UI with flowchart)
   Each renderer is an object with:
     .id        — unique string key
     .label     — display name
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

var allowedRenderers = window._WFE_ALLOWED_RENDERERS || [];

function registerRenderer(r) {
    renderers[r.id] = r;
    var container = document.createElement('div');
    container.id = 'rc-' + r.id;
    container.className = 'renderer-container';
    document.getElementById('view-frame').appendChild(container);
    r._container = container;
    r.init(container);
}

function setMode(id) {
    /* Feedback forces Agent renderer */
    if (id !== 'raw' && viewMode === 'feedback') {
        viewMode = 'full';
        var bf = document.getElementById('btn-full');
        var bfb = document.getElementById('btn-feedback');
        if (bf) bf.classList.add('active');
        if (bfb) bfb.classList.remove('active');
    }
    if (activeRenderer === id) return;
    if (activeRenderer && renderers[activeRenderer]) {
        renderers[activeRenderer]._container.classList.remove('active');
        renderers[activeRenderer].deactivate();
    }
    activeRenderer = id;
    var r = renderers[id];
    r._container.classList.add('active');
    r.activate();
    _updateToggleHighlight();
    if (agentState) dispatchRender();
}

function _updateToggleHighlight() {
    var btn = document.getElementById('renderer-toggle');
    if (!btn) return;
    var isAgent = activeRenderer === 'raw';
    btn.textContent = isAgent ? 'Agent' : 'Human';
    btn.style.background = isAgent ? '#4a9eff' : '#1a1a2e';
    btn.style.color = isAgent ? '#fff' : '#ccc';
    btn.style.borderColor = isAgent ? '#4a9eff' : '#444';
}

function toggleRenderer() {
    if (activeRenderer === 'raw') {
        setMode('light');
    } else {
        setMode('raw');
    }
}

function setViewMode(mode) {
    viewMode = mode;
    var btn = document.getElementById('btn-view-mode');
    if (btn) {
        btn.textContent = mode === 'full' ? 'Full' : 'Feedback';
        btn.classList.toggle('active', mode === 'feedback');
    }
    if (mode === 'feedback' && activeRenderer !== 'raw') {
        setMode('raw');
        return;
    }
    if (activeRenderer && renderers[activeRenderer]) {
        dispatchRender();
    }
}

function toggleViewMode() {
    setViewMode(viewMode === 'full' ? 'feedback' : 'full');
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

function extractState(raw, feedback) {
    var obj;
    try { obj = typeof raw === 'string' ? JSON.parse(raw) : raw; } catch(e) { return; }
    if (!obj || !obj.state) return;
    lastRaw = typeof raw === 'string' ? raw : JSON.stringify(raw);
    broadcastState(obj, obj.message || '', feedback);
}
