/* ======================================================================
   SHARED SIMPLE RENDERER — rendering logic used by Light and Dark modes
   ====================================================================== */

function wfEsc(s) {
    var d = document.createElement('div');
    d.textContent = String(s == null ? '' : s);
    return d.innerHTML.replace(/"/g, '&quot;');
}

function wfRenderParams(a) {
    /* Render affordance parameters (or legacy options) as a compact string. */
    if (a.parameters) {
        var parts = [];
        var keys = Object.keys(a.parameters);
        for (var ki = 0; ki < keys.length; ki++) {
            var k = keys[ki];
            var p = a.parameters[k];
            var s = k;
            if (p.options) s += '=' + JSON.stringify(p.options);
            if (p.labels) s += ' (' + p.labels.join(', ') + ')';
            parts.push(s);
        }
        return parts.join(' | ');
    }
    if (a.options) return JSON.stringify(a.options);
    return '';
}

function wfRenderValue(v) {
    if (v == null) return '<span class="wf-null">(null)</span>';
    if (typeof v === 'boolean') return '<span class="wf-bool">' + v + '</span>';
    if (typeof v === 'number') return '<span class="wf-num">' + v + '</span>';
    if (Array.isArray(v)) {
        if (v.length === 0) return '<span class="wf-empty-arr">(empty)</span>';
        var html = '<div class="wf-arr">';
        for (var i = 0; i < v.length; i++) {
            html += '<div class="wf-arr-item">' + wfRenderValue(v[i]) + '</div>';
        }
        return html + '</div>';
    }
    if (typeof v === 'object') return wfRenderObject(v);
    return '<span class="wf-str">' + wfEsc(v) + '</span>';
}

function wfRenderObject(obj) {
    var keys = Object.keys(obj);
    if (!keys.length) return '<span class="wf-empty-obj">(empty)</span>';
    var html = '<table class="wf-tbl">';
    for (var i = 0; i < keys.length; i++) {
        html += '<tr><td class="wf-key">' + wfEsc(keys[i]) + '</td><td class="wf-val">' + wfRenderValue(obj[keys[i]]) + '</td></tr>';
    }
    return html + '</table>';
}

function wfRuleToExpr(rule, columns) {
    /* Translate a rule JSON tree into a human-readable boolean expression.
       columns is the columns array (for resolving column index to name). */
    if (!rule || !rule.conditions) return JSON.stringify(rule);
    var parts = [];
    for (var i = 0; i < rule.conditions.length; i++) {
        var c = rule.conditions[i];
        if (c.op) {
            /* Nested group */
            parts.push('(' + wfRuleToExpr(c, columns) + ')');
        } else if (c.type === 'all-executed') {
            parts.push('all-executed');
        } else if (c.type === 'column' && c.column !== undefined) {
            var colName = (columns && columns[c.column]) ? columns[c.column].name : 'col ' + c.column;
            var op = c.operator || '?';
            if (op === 'is-filled' || op === 'is-signed') {
                parts.push(colName + ' ' + op);
            } else if (op === 'equals' || op === 'ref-status') {
                parts.push(colName + ' ' + op + ' "' + (c.value || '') + '"');
            } else {
                parts.push(colName + ' ' + op);
            }
        } else {
            parts.push(JSON.stringify(c));
        }
    }
    if (parts.length === 0) return '(empty)';
    if (parts.length === 1) return parts[0];
    return parts.join(' ' + (rule.op || 'AND') + ' ');
}

function wfRenderFields(fields, fieldCategory, fieldAffordances) {
    var keys = Object.keys(fields);
    if (!keys.length) return '<span class="wf-empty-obj">(empty)</span>';
    /* Legacy fallback: if affordances are passed separately, build lookup.
       New format: each field has f.affordance inline. */
    var affByLabel = {};
    if (fieldAffordances) {
        for (var ai = 0; ai < fieldAffordances.length; ai++) {
            var aff = fieldAffordances[ai];
            var m = aff.label.match(/^Set (.+?)( \(current:|$)/);
            if (m) affByLabel[m[1]] = aff;
        }
    }
    var html = '<div class="wf-fields">';
    for (var i = 0; i < keys.length; i++) {
        var k = keys[i];
        var f = fields[k];
        var cat = fieldCategory[k] || null;
        var catCls = cat ? ' wf-fb-' + cat : '';
        /* Prefer inline affordance; fall back to legacy regex match */
        var aff = (f && f.affordance) || affByLabel[k] || null;
        var tooltip = aff ? aff.method + ' ' + aff.url + (aff.body !== undefined ? ' ' + JSON.stringify(aff.body) : '') : '';
        html += '<div class="wf-field' + catCls + '">';
        var tagMap = {outcome:'SET', 'new':'NEW', modified:'CHANGED'};
        var tagCls = {outcome:'wf-tag-outcome', 'new':'wf-tag-new', modified:'wf-tag-modified'};
        var tag = cat ? '<span class="' + tagCls[cat] + '">' + tagMap[cat] + '</span>' : '';
        html += '<div class="wf-field-label">' + wfEsc(k) + tag + '</div>';
        if (f && typeof f === 'object' && 'value' in f) {
            if (f.instruction) {
                html += '<div class="wf-field-instruction">' + wfEsc(f.instruction) + '</div>';
            }
            if (aff) {
                /* Editable field — inline affordance control */
                var options = (aff.parameters && aff.parameters.value && aff.parameters.value.options) || null;
                if (options) {
                    /* Decide: buttons for short/few options, dropdown for long/many */
                    var useDropdown = options.length > 3;
                    if (!useDropdown) {
                        for (var oi = 0; oi < options.length; oi++) {
                            var ol = options[oi] === true ? 'Yes' : options[oi] === false ? 'No' : String(options[oi]);
                            if (ol.length > 20) { useDropdown = true; break; }
                        }
                    }
                    if (useDropdown) {
                        /* Dropdown: current value + select + Set on one line */
                        var curDisplay = f.value === true ? 'Yes' : f.value === false ? 'No' : f.value != null ? String(f.value) : '';
                        html += '<div class="wf-field-row">';
                        if (curDisplay) {
                            html += '<span class="wf-field-current">' + wfEsc(curDisplay) + '</span>';
                        } else {
                            html += '<span class="wf-field-current wf-field-empty">(not set)</span>';
                        }
                        html += '<select class="wf-aff-select" data-aff-url="' + wfEsc(aff.url) + '">';
                        html += '<option value="">— Select —</option>';
                        for (var oi = 0; oi < options.length; oi++) {
                            var oval = options[oi];
                            var olabel = oval === true ? 'Yes' : oval === false ? 'No' : String(oval);
                            html += '<option value="' + wfEsc(JSON.stringify(oval)) + '">' + wfEsc(olabel) + '</option>';
                        }
                        html += '</select>';
                        html += '<button class="wf-aff-submit" data-aff-url="' + wfEsc(aff.url) + '">Set</button>';
                        html += '</div>';
                    } else {
                        /* Short options: current value + buttons on one line */
                        var curDisplay = f.value === true ? 'Yes' : f.value === false ? 'No' : f.value != null ? String(f.value) : '';
                        html += '<div class="wf-field-row">';
                        if (curDisplay) {
                            html += '<span class="wf-field-current">' + wfEsc(curDisplay) + '</span>';
                        } else {
                            html += '<span class="wf-field-current wf-field-empty">(not set)</span>';
                        }
                        for (var oi = 0; oi < options.length; oi++) {
                            var oval = options[oi];
                            var olabel = oval === true ? 'Yes' : oval === false ? 'No' : String(oval);
                            var isActive = JSON.stringify(oval) === JSON.stringify(f.value);
                            var btnTooltip = aff.method + ' ' + aff.url + ' ' + JSON.stringify({value: oval});
                            html += '<button class="wf-aff-opt-btn' + (isActive ? ' wf-aff-opt-active' : '') + '" data-aff-url="' + wfEsc(aff.url) + '" data-aff-value="' + wfEsc(JSON.stringify(oval)) + '" title="' + wfEsc(btnTooltip) + '">' + wfEsc(olabel) + '</button>';
                        }
                        html += '</div>';
                    }
                } else {
                    /* Text field: current value + input + Set on one line */
                    var curVal = f.value == null ? '' : String(f.value);
                    html += '<div class="wf-field-row">';
                    if (curVal) {
                        html += '<span class="wf-field-current">' + wfEsc(curVal) + '</span>';
                    } else {
                        html += '<span class="wf-field-current wf-field-empty">(not set)</span>';
                    }
                    html += '<input class="wf-aff-input" type="text" data-aff-url="' + wfEsc(aff.url) + '" placeholder="New value\u2026">';
                    html += '<button class="wf-aff-submit" data-aff-url="' + wfEsc(aff.url) + '">Set</button>';
                    html += '</div>';
                }
            } else {
                /* Read-only field */
                if (f.value == null) {
                    html += '<div class="wf-field-value wf-field-empty">(not set)</div>';
                } else {
                    var displayVal = f.value;
                    if (displayVal === true) displayVal = 'Yes';
                    else if (displayVal === false) displayVal = 'No';
                    html += '<div class="wf-field-value">' + wfEsc(displayVal) + '</div>';
                }
            }
            if (!aff && f.options) {
                html += '<div class="wf-field-options">' + wfEsc(f.options.join(', ')) + '</div>';
            }
        } else {
            html += '<div class="wf-field-value">' + wfRenderValue(f) + '</div>';
        }
        html += '</div>';
    }
    return html + '</div>';
}

/* ── Workflow Definition Blueprint Renderer ── */
function wfRenderDefinition(defn) {
    if (!defn) return '';
    var html = '';

    /* Header: title, ID, description */
    html += '<div class="bp-header">';
    html += '<div class="bp-title">' + wfEsc(defn.workflow_title || '(untitled)') + '</div>';
    if (defn.workflow_id) {
        html += '<span class="bp-id">' + wfEsc(defn.workflow_id) + '</span>';
    }
    if (defn.workflow_description) {
        html += '<div class="bp-desc">' + wfEsc(defn.workflow_description) + '</div>';
    }
    html += '</div>';

    /* Node flow banner — derived from node titles */
    var nodes = defn.nodes || [];
    if (nodes.length) {
        html += '<div class="bp-lifecycle">';
        for (var i = 0; i < nodes.length; i++) {
            if (i > 0) html += '<div class="bp-lc-conn"></div>';
            html += '<div class="bp-lc-step">';
            html += '<span class="bp-lc-dot">' + (i + 1) + '</span>';
            html += '<span class="bp-lc-label">' + wfEsc(nodes[i].title || nodes[i].id) + '</span>';
            html += '</div>';
        }
        html += '</div>';
    }

    /* Node cards */
    if (!nodes.length) {
        html += '<div class="bp-empty">No nodes defined</div>';
        return '<div class="bp-wrap">' + html + '</div>';
    }

    html += '<div class="bp-nodes">';
    for (var ni = 0; ni < nodes.length; ni++) {
        var nd = nodes[ni];
        if (ni > 0) html += '<div class="bp-node-conn"><div class="bp-arrow">&#9660;</div></div>';

        html += '<div class="bp-node">';
        /* Node header: title + id only */
        html += '<div class="bp-node-head">';
        html += '<span class="bp-node-title">' + wfEsc(nd.title || nd.id) + '</span>';
        html += '<span class="bp-node-id">' + wfEsc(nd.id) + '</span>';
        if (nd.show_all_fields) {
            html += '<span class="bp-node-flag">show_all_fields</span>';
        }
        html += '</div>';

        /* Instruction */
        html += '<div class="bp-node-section">';
        html += '<div class="bp-node-section-label">Instruction</div>';
        if (nd.instruction) {
            html += '<div class="bp-node-instr">' + wfEsc(nd.instruction) + '</div>';
        } else {
            html += '<div class="bp-node-none">(none)</div>';
        }
        html += '</div>';

        /* Fields */
        var fields = nd.fields || [];
        html += '<div class="bp-node-section">';
        html += '<div class="bp-node-section-label">Fields</div>';
        if (fields.length) {
            html += '<table class="bp-fields-table"><thead><tr><th>Key</th><th>Label</th><th>Type</th><th>Details</th></tr></thead><tbody>';
            for (var fi = 0; fi < fields.length; fi++) {
                var fld = fields[fi];
                var typeCls = 'bp-type bp-type-' + (fld.type || 'text');
                html += '<tr>';
                html += '<td class="bp-field-key">' + wfEsc(fld.key || '') + '</td>';
                html += '<td>' + wfEsc(fld.label || '') + '</td>';
                html += '<td><span class="' + typeCls + '">' + wfEsc(fld.type || 'text') + '</span></td>';
                var details = [];
                if (fld.options && fld.options.length) details.push(fld.options.join(' | '));
                if (fld.instruction) details.push(fld.instruction);
                html += '<td class="bp-field-detail">' + (details.length ? wfEsc(details.join(' — ')) : '') + '</td>';
                html += '</tr>';
            }
            html += '</tbody></table>';
        } else {
            html += '<div class="bp-node-none">(no fields)</div>';
        }
        html += '</div>';

        /* Proceed gate */
        html += '<div class="bp-node-section">';
        html += '<div class="bp-node-section-label">Proceed Gate</div>';
        if (nd.proceed) {
            html += '<div class="bp-gate">';
            html += '<span class="bp-gate-icon">&#9654;</span>';
            html += '<span class="bp-gate-label">' + wfEsc(nd.proceed.label || 'Proceed') + '</span>';
            var reqs = nd.proceed.requires || [];
            if (reqs.length) {
                html += '<span class="bp-gate-reqs">requires: ' + reqs.map(function(r) { return '<span class="bp-gate-key">' + wfEsc(r) + '</span>'; }).join(', ') + '</span>';
            }
            html += '</div>';
        } else {
            html += '<div class="bp-node-none">(no proceed gate)</div>';
        }
        html += '</div>';

        /* Navigation */
        var navs = nd.navigation || [];
        html += '<div class="bp-node-section">';
        html += '<div class="bp-node-section-label">Navigation</div>';
        if (navs.length) {
            for (var nvi = 0; nvi < navs.length; nvi++) {
                var nav = navs[nvi];
                html += '<div class="bp-nav-item">';
                html += '<span class="bp-nav-action">' + wfEsc(nav.action) + '</span>';
                html += '<span class="bp-nav-label">' + wfEsc(nav.label) + '</span>';
                if (nav.node) html += '<span class="bp-nav-target">&rarr; ' + wfEsc(nav.node) + '</span>';
                html += '</div>';
            }
        } else {
            html += '<div class="bp-node-none">(no navigation)</div>';
        }
        html += '</div>';

        /* Actions */
        var acts = nd.actions || [];
        html += '<div class="bp-node-section">';
        html += '<div class="bp-node-section-label">Actions</div>';
        if (acts.length) {
            for (var ai = 0; ai < acts.length; ai++) {
                var act = acts[ai];
                html += '<div class="bp-action-item">';
                html += '<span class="bp-action-type">' + wfEsc(act.action) + '</span>';
                html += '<span class="bp-action-label">' + wfEsc(act.label) + '</span>';
                html += '</div>';
            }
        } else {
            html += '<div class="bp-node-none">(no actions)</div>';
        }
        html += '</div>';

        html += '</div>'; /* bp-node */
    }
    html += '</div>'; /* bp-nodes */

    return '<div class="bp-wrap">' + html + '</div>';
}

function _isDefinition(v) {
    /* Match only detailed definitions (with fields/instructions on nodes),
       not topology-only definitions used for the schematic banner. */
    if (!v || typeof v !== 'object' || Array.isArray(v)) return false;
    if (!v.nodes || !v.nodes.length) return false;
    // Check if any node has detail beyond id/title/proceed/router/fork
    for (var i = 0; i < v.nodes.length; i++) {
        var n = v.nodes[i];
        if (n.fields || n.instruction || n.actions || n.navigation) return true;
    }
    return false;
}

function wfRenderStateProps(state) {
    /* Render any state keys not handled by dedicated building blocks.
       Known keys (rendered elsewhere): workflow, node, node_title, completed_nodes,
       definition, fields, table, execution_table. */
    var s = state.state || {};
    var known = ['workflow','node','node_title','completed_nodes','definition','fields','table','execution_table','fork_state','banner_definition'];
    var extra = Object.keys(s).filter(function(k) { return known.indexOf(k) === -1; });
    if (!extra.length) return '';
    var html = '';
    for (var i = 0; i < extra.length; i++) {
        var k = extra[i];
        var v = s[k];
        /* Workflow definition gets the blueprint renderer */
        if (k === 'definition' && _isDefinition(v)) {
            html += wfRenderDefinition(v);
            continue;
        }
        html += '<div class="wf-card">';
        html += '<div class="wf-card-head">state.' + wfEsc(k) + '</div>';
        if (Array.isArray(v) && v.length && typeof v[0] === 'string') {
            /* Array of strings — render as list */
            html += '<ul class="wf-extra-list">';
            for (var j = 0; j < v.length; j++) {
                html += '<li>' + wfEsc(v[j]) + '</li>';
            }
            html += '</ul>';
        } else if (v && typeof v === 'object') {
            html += wfRenderValue(v);
        } else {
            html += '<div class="wf-field-value">' + wfRenderValue(v) + '</div>';
        }
        html += '</div>';
    }
    return html;
}

function wfRenderBanner(state) {
    var s = state.state || {};
    var defn = s.banner_definition || s.definition;
    var current = s.node || '';
    var completed = s.completed_nodes || [];

    if (defn && defn.nodes && defn.nodes.length) {
        return _wfSchematicBanner(defn, current, completed);
    }

    return '';
}

/* ── Pill node renderer — compact banner-style nodes ── */
function _pillNodeRenderer(item, status) {
    if (item.kind === 'branch-point') {
        if (item.type === 'gate') {
            return '<div class="sch-bp sch-bp-gate">'
                + Schematic.GATE_SVG
                + '<span style="position:relative">' + wfEsc(item.title) + '</span></div>';
        }
        // split (fork)
        return '<div class="sch-bp sch-bp-split" style="position:relative;">'
            + '<div class="sch-bp-split-bars sch-bp-split-bars-l"></div>'
            + wfEsc(item.title)
            + '<div class="sch-bp-split-bars sch-bp-split-bars-r"></div>'
            + '</div>';
    }
    return '<div class="sch-pill">'
        + '<span class="sch-pill-dot"></span>'
        + '<span class="sch-pill-title">' + wfEsc(item.title) + '</span>'
        + '</div>';
}

/* ── Schematic banner — HTML nodes over canvas topology ── */
function _wfSchematicBanner(defn, current, completed) {
    var containerId = 'sch-banner-' + Math.random().toString(36).substr(2, 6);

    setTimeout(function() {
        var el = document.getElementById(containerId);
        if (!el) return;
        try {
            var spine = Schematic.definitionToSpine(defn);
            var execState = { current: current, completed: completed };
            var layoutData = Schematic.renderHybrid(spine, el, execState, {
                nodeRenderer: _pillNodeRenderer,
                focusNode: current
            });
            if (layoutData) el.style.height = layoutData.height + 'px';
        } catch (e) {
            el.innerHTML = '<span style="color:#999;font-size:0.8rem;">Banner error: ' + e.message + '</span>';
        }
    }, 0);

    return '<div class="wf-banner wf-banner-flow" id="' + containerId + '" style="min-height:52px;"></div>';
}

/* ── Generic affordance renderer ──
   Renders an array of affordances as interactive controls.
   Works with or without labels — derives action name from URL if no label. */
function wfRenderAffordances(affs) {
    if (!affs || !affs.length) return '';
    var html = '<div class="wf-affs">';
    for (var i = 0; i < affs.length; i++) {
        var a = affs[i];
        var action = a.label || (a.body && a.body.key ? a.body.key.replace(/_/g, ' ') : a.url.split('/').pop().replace(/_/g, ' '));
        var params = a.parameters || {};
        var paramKeys = Object.keys(params);
        var tooltip = a.method + ' ' + a.url + ' ' + JSON.stringify(a.body);

        if (paramKeys.length) {
            /* Parametric: render as inline form */
            html += '<div class="wf-aff-inline" data-aff-url="' + wfEsc(a.url) + '" data-aff-body="' + wfEsc(JSON.stringify(a.body)) + '">';
            html += '<span class="wf-aff-action">' + wfEsc(action) + '</span>';
            for (var pi = 0; pi < paramKeys.length; pi++) {
                var pk = paramKeys[pi];
                var p = params[pk];
                /* Skip params that are pre-filled in the body (e.g., col) */
                if (a.body[pk] !== undefined && a.body[pk] !== '<' + pk + '>') continue;
                if (p.options) {
                    html += ' <select class="wf-param-input wf-aff-compact" data-param="' + wfEsc(pk) + '">';
                    for (var oi = 0; oi < p.options.length; oi++) {
                        var optVal = p.options[oi];
                        var optLabel = p.labels ? p.labels[oi] : (optVal === true ? 'Yes' : optVal === false ? 'No' : String(optVal));
                        html += '<option value="' + wfEsc(JSON.stringify(optVal)) + '">' + wfEsc(optLabel) + '</option>';
                    }
                    html += '</select>';
                } else {
                    html += ' <input class="wf-param-input wf-aff-compact" type="text" data-param="' + wfEsc(pk) + '"'
                        + ' placeholder="' + wfEsc(p.description || pk) + '">';
                }
            }
            html += ' <button class="wf-aff-go" data-aff-url="' + wfEsc(a.url) + '" title="' + wfEsc(tooltip) + '">' + wfEsc(action) + '</button>';
            html += '</div>';
        } else {
            /* Simple: render as button */
            html += '<button class="wf-aff-btn" data-aff-url="' + wfEsc(a.url) + '" data-aff-body="' + wfEsc(JSON.stringify(a.body)) + '" title="' + wfEsc(tooltip) + '">' + wfEsc(action) + '</button>';
        }
    }
    html += '</div>';
    return html;
}

function wfRenderTable(table) {
    if (!table) return '';
    var cols = table.columns || [];
    var rows = table.rows || [];
    var props = table.properties || {};
    var tableAffs = table.affordances || [];

    var html = '<div class="wf-card">';
    html += '<div class="wf-card-head">Table</div>';

    if (table.summary) {
        html += '<div class="wf-table-summary">' + wfEsc(table.summary) + '</div>';
    }

    /* Table-level affordances */
    html += wfRenderAffordances(tableAffs);

    if (cols.length) {
        html += '<div class="wf-table-wrap"><table class="wf-table"><thead><tr>';
        html += '<th class="wf-table-rownum">#</th>';
        for (var ci = 0; ci < cols.length; ci++) {
            var c = cols[ci];
            var colAffs = c.affordances || [];
            html += '<th>';
            html += _wfRenderColAffordances(c, colAffs, cols);
            html += '</th>';
        }
        html += '</tr></thead><tbody>';
        if (rows.length) {
            for (var ri = 0; ri < rows.length; ri++) {
                html += '<tr><td class="wf-table-rownum">' + ri + '</td>';
                for (var ci = 0; ci < cols.length; ci++) {
                    var val = (ri < rows.length && ci < rows[ri].length) ? rows[ri][ci] : '';
                    html += '<td>' + (val ? wfEsc(val) : '<span class="wf-table-empty">&mdash;</span>') + '</td>';
                }
                html += '</tr>';
            }
        } else {
            html += '<tr><td colspan="' + (cols.length + 1) + '" class="wf-table-empty">(no rows)</td></tr>';
        }
        html += '</tbody></table></div>';
    } else {
        html += '<div class="wf-table-empty">(no columns defined)</div>';
    }

    /* Properties: current value + affordance on one line */
    var propAffs = props.affordances || [];
    var propKeys = Object.keys(props).filter(function(k) { return k !== 'affordances'; });
    if (propKeys.length || propAffs.length) {
        html += '<div class="wf-table-props">';
        for (var i = 0; i < propKeys.length; i++) {
            var pk = propKeys[i];
            var pv = props[pk];
            /* Find matching affordance by body.key */
            var pAff = null;
            for (var ai = 0; ai < propAffs.length; ai++) {
                if (propAffs[ai].body && propAffs[ai].body.key === pk) { pAff = propAffs[ai]; break; }
            }
            var propLabel = pk.replace(/_/g, ' ');
            html += '<div class="wf-table-prop-row">';
            html += '<span class="wf-table-prop-label">' + wfEsc(propLabel) + '</span>';
            if (pAff) {
                var pOpts = pAff.parameters && pAff.parameters.value && pAff.parameters.value.options;
                var pvDisplay = pv === true ? 'Yes' : pv === false ? 'No' : pv != null ? String(pv) : '';
                var tooltip = pAff.method + ' ' + pAff.url + ' ' + JSON.stringify(pAff.body);
                html += '<span class="wf-field-current">' + (pvDisplay ? wfEsc(pvDisplay) : '<span class="wf-field-empty">(not set)</span>') + '</span>';
                if (pOpts) {
                    for (var oi = 0; oi < pOpts.length; oi++) {
                        var oval = pOpts[oi];
                        var olabel = oval === true ? 'Yes' : oval === false ? 'No' : String(oval);
                        var isActive = JSON.stringify(oval) === JSON.stringify(pv);
                        var fullBody = {key: pk, value: oval};
                        var btnTooltip = pAff.method + ' ' + pAff.url + ' ' + JSON.stringify(fullBody);
                        html += '<button class="wf-aff-btn' + (isActive ? ' wf-aff-opt-active' : '') + '" data-aff-url="' + wfEsc(pAff.url) + '" data-aff-body="' + wfEsc(JSON.stringify(fullBody)) + '" title="' + wfEsc(btnTooltip) + '">' + wfEsc(olabel) + '</button>';
                    }
                }
            } else {
                var pvDisplay = pv === true ? 'Yes' : pv === false ? 'No' : pv != null ? String(pv) : '(not set)';
                html += '<span class="wf-field-current">' + wfEsc(pvDisplay) + '</span>';
            }
            html += '</div>';
        }
        /* Render any property affordances not matched to a key */
        var unmatchedPropAffs = propAffs.filter(function(a) {
            return !a.body || !a.body.key || propKeys.indexOf(a.body.key) === -1;
        });
        if (unmatchedPropAffs.length) html += wfRenderAffordances(unmatchedPropAffs);
        html += '</div>';
    }

    html += '</div>';
    return html;
}

/* Render column affordances with current value + control layout */
function _wfRenderColAffordances(col, affs, cols) {
    var html = '';
    var rename = null, setType = null, remove = null, others = [];
    for (var i = 0; i < affs.length; i++) {
        var a = affs[i];
        var b = a.body || {};
        if (b.name !== undefined && a.parameters && a.parameters.name) rename = a;
        else if (b.type !== undefined && a.parameters && a.parameters.type) setType = a;
        else if (Object.keys(a.parameters || {}).length === 0 && Object.keys(b).length <= 1 && b.col !== undefined) remove = a;
        else others.push(a);
    }

    /* Name: current value + rename input (uses wf-aff-inline for body-template-aware binding) */
    if (rename) {
        var tooltip = rename.method + ' ' + rename.url + ' ' + JSON.stringify(rename.body);
        html += '<div class="wf-field-row wf-aff-inline" data-aff-url="' + wfEsc(rename.url) + '" data-aff-body="' + wfEsc(JSON.stringify(rename.body)) + '">';
        html += '<span class="wf-field-current wf-table-colname">' + wfEsc(col.name) + '</span>';
        html += '<input class="wf-param-input" type="text" data-param="name" placeholder="Rename\u2026">';
        html += '<button class="wf-aff-go" data-aff-url="' + wfEsc(rename.url) + '" title="' + wfEsc(tooltip) + '">Rename</button>';
        html += '</div>';
    } else {
        html += '<div class="wf-table-colname">' + wfEsc(col.name) + '</div>';
    }

    /* Type: current value + type dropdown (uses wf-aff-inline for body-template-aware binding) */
    if (setType) {
        var typeOpts = setType.parameters.type.options || [];
        var tooltip = setType.method + ' ' + setType.url + ' ' + JSON.stringify(setType.body);
        html += '<div class="wf-field-row wf-aff-inline" data-aff-url="' + wfEsc(setType.url) + '" data-aff-body="' + wfEsc(JSON.stringify(setType.body)) + '">';
        html += '<span class="wf-field-current wf-table-coltype">' + wfEsc(col.type) + '</span>';
        html += '<select class="wf-param-input" data-param="type">';
        html += '<option value="">\u2014 Change \u2014</option>';
        for (var oi = 0; oi < typeOpts.length; oi++) {
            html += '<option value="' + wfEsc(JSON.stringify(typeOpts[oi])) + '">' + wfEsc(String(typeOpts[oi])) + '</option>';
        }
        html += '</select>';
        html += '<button class="wf-aff-go" data-aff-url="' + wfEsc(setType.url) + '" title="' + wfEsc(tooltip) + '">Set</button>';
        html += '</div>';
    } else {
        html += '<div class="wf-table-coltype">' + wfEsc(col.type) + '</div>';
    }

    if (col.choices) html += '<div class="wf-table-colmeta">choices: ' + wfEsc(JSON.stringify(col.choices)) + '</div>';
    if (col.rule) html += '<div class="wf-table-colmeta">rule: ' + wfEsc(wfRuleToExpr(col.rule, cols)) + '</div>';

    /* Remove button */
    if (remove) {
        var tooltip = remove.method + ' ' + remove.url + ' ' + JSON.stringify(remove.body);
        html += '<button class="wf-aff-btn" data-aff-url="' + wfEsc(remove.url) + '" data-aff-body="' + wfEsc(JSON.stringify(remove.body)) + '" title="' + wfEsc(tooltip) + '">Remove</button>';
    }

    /* Remaining affordances (e.g. set_cell) — generic rendering */
    if (others.length) html += wfRenderAffordances(others);

    return html;
}

function wfRenderExecTable(et) {
    if (!et) return '';
    var cols = et.columns || [];
    var rows = et.rows || [];

    var html = '<div class="wf-card">';
    html += '<div class="wf-card-head">state.execution_table</div>';

    if (!cols.length) {
        html += '<div class="wf-table-empty">(no columns)</div></div>';
        return html;
    }

    /* Column definitions */
    html += '<div class="wf-table-wrap"><table class="wf-table"><thead><tr>';
    html += '<th class="wf-table-rownum">row_id</th>';
    for (var ci = 0; ci < cols.length; ci++) {
        var c = cols[ci];
        html += '<th><div class="wf-table-colname">' + wfEsc(c.name) + '</div>';
        html += '<div class="wf-table-coltype">' + wfEsc(c.type) + '</div>';
        if (c.choices) html += '<div class="wf-table-colmeta">choices: ' + wfEsc(JSON.stringify(c.choices)) + '</div>';
        if (c.rule) html += '<div class="wf-table-colmeta">rule: ' + wfEsc(wfRuleToExpr(c.rule, cols)) + '</div>';
        html += '</th>';
    }
    html += '</tr></thead><tbody>';

    /* Rows */
    for (var ri = 0; ri < rows.length; ri++) {
        var r = rows[ri];
        var rowCls = r.gated ? ' class="wf-row-gated"' : '';
        html += '<tr' + rowCls + '>';
        /* row_id + row-level properties */
        html += '<td class="wf-table-rownum">';
        html += wfEsc(r.row_id || String(r.row));
        html += '<div class="wf-exec-reason">gated: ' + r.gated + '</div>';
        if (r.gated_by && r.gated_by.length) {
            html += '<div class="wf-exec-reason">gated_by: ' + wfEsc(JSON.stringify(r.gated_by)) + '</div>';
        }
        var acc = r.acceptance || {};
        html += '<div class="wf-exec-reason ' + (acc.passed ? 'wf-exec-pass' : 'wf-exec-pending') + '">acceptance.passed: ' + acc.passed + '</div>';
        if (acc.reason) {
            html += '<div class="wf-exec-reason">acceptance.reason: ' + wfEsc(acc.reason) + '</div>';
        }
        html += '</td>';

        /* Cells */
        var cells = r.cells || [];
        for (var ci = 0; ci < cells.length; ci++) {
            var cell = cells[ci];
            var cellStatus = cell.status || 'empty';
            var isCompleted = (cell.display_value && cell.available_actions.indexOf('fill') === -1
                && cell.available_actions.indexOf('sign') === -1
                && cell.available_actions.indexOf('mark_na') === -1
                && cell.available_actions.indexOf('initiate_issue') === -1
                && cellStatus !== 'empty' && cellStatus !== 'locked' && cellStatus !== 'gated' && cellStatus !== 'pending');
            var cls = 'wf-exec-cell wf-exec-' + cellStatus;
            html += '<td class="' + cls + '"' + (isCompleted ? ' data-completed="true"' : '') + '>';
            /* display_value */
            html += '<div>' + (cell.display_value ? wfEsc(cell.display_value) : '<span class="wf-table-empty">&mdash;</span>') + '</div>';
            /* status */
            html += '<div class="wf-exec-reason">status: ' + wfEsc(cell.status || '') + '</div>';
            /* value (when different from display_value or non-empty) */
            if (cell.value && cell.value !== cell.display_value) {
                html += '<div class="wf-exec-reason">value: ' + wfEsc(cell.value) + '</div>';
            }
            /* available_actions */
            if (cell.available_actions && cell.available_actions.length) {
                html += '<div class="wf-exec-reason">actions: ' + wfEsc(JSON.stringify(cell.available_actions)) + '</div>';
            }
            /* locked_reason */
            if (cell.locked_reason) {
                html += '<div class="wf-exec-reason">locked_reason: ' + wfEsc(cell.locked_reason) + '</div>';
            }
            html += '</td>';
        }
        html += '</tr>';
    }

    html += '</tbody></table></div></div>';
    return html;
}

/* ── Parametric affordance form ── */
function wfRenderParamAff(aff) {
    var params = aff.parameters || {};
    var paramKeys = Object.keys(params);
    if (!paramKeys.length) return '';
    var tooltip = aff.method + ' ' + aff.url + ' ' + JSON.stringify(aff.body);
    var html = '<div class="wf-param-form" data-aff-url="' + wfEsc(aff.url) + '" data-aff-body="' + wfEsc(JSON.stringify(aff.body)) + '">';
    var action = aff.label || aff.url.split('/').pop().replace(/_/g, ' ');
    html += '<div class="wf-param-head">' + wfEsc(action) + '</div>';
    for (var pi = 0; pi < paramKeys.length; pi++) {
        var pk = paramKeys[pi];
        var p = params[pk];
        html += '<div class="wf-param-row">';
        html += '<label class="wf-param-label">' + wfEsc(pk) + '</label>';
        if (p.options) {
            html += '<select class="wf-param-input" data-param="' + wfEsc(pk) + '">';
            for (var oi = 0; oi < p.options.length; oi++) {
                var optVal = p.options[oi];
                var optLabel = p.labels ? p.labels[oi] : (optVal === true ? 'Yes' : optVal === false ? 'No' : String(optVal));
                html += '<option value="' + wfEsc(JSON.stringify(optVal)) + '">' + wfEsc(optLabel) + '</option>';
            }
            html += '</select>';
        } else {
            html += '<input class="wf-param-input" type="text" data-param="' + wfEsc(pk) + '"'
                + (p.description ? ' placeholder="' + wfEsc(p.description) + '"' : '') + '>';
        }
        html += '</div>';
    }
    html += '<button class="wf-param-submit" title="' + wfEsc(tooltip) + '">Submit</button>';
    html += '</div>';
    return html;
}

/* ── Faithful execution table — inline cell affordance controls ── */
function wfRenderExecTableFaithful(et, affordances) {
    if (!et) return '';
    var cols = et.columns || [];
    var rows = et.rows || [];

    /* Index cell affordances by "row,col" */
    var cellAffs = {};
    for (var i = 0; i < affordances.length; i++) {
        var a = affordances[i];
        if (a.body && a.body.cell_action !== undefined && a.body.row !== undefined && a.body.col !== undefined) {
            var key = a.body.row + ',' + a.body.col;
            if (!cellAffs[key]) cellAffs[key] = [];
            cellAffs[key].push(a);
        }
    }

    var html = '<div class="wf-card">';
    html += '<div class="wf-card-head">Execution Table</div>';

    if (!cols.length) {
        html += '<div class="wf-table-empty">(no columns)</div></div>';
        return html;
    }

    html += '<div class="wf-table-wrap"><table class="wf-table"><thead><tr>';
    html += '<th class="wf-table-rownum">Row</th>';
    for (var ci = 0; ci < cols.length; ci++) {
        var c = cols[ci];
        html += '<th><div class="wf-table-colname">' + wfEsc(c.name) + '</div>';
        html += '<div class="wf-table-coltype">' + wfEsc(c.type) + '</div>';
        if (c.rule) html += '<div class="wf-table-colmeta">rule: ' + wfEsc(wfRuleToExpr(c.rule, cols)) + '</div>';
        html += '</th>';
    }
    html += '</tr></thead><tbody>';

    for (var ri = 0; ri < rows.length; ri++) {
        var r = rows[ri];
        var rowCls = r.gated ? ' class="wf-row-gated"' : '';
        html += '<tr' + rowCls + '>';

        /* Row header with acceptance status */
        html += '<td class="wf-table-rownum">';
        html += wfEsc(r.row_id || String(r.row));
        var acc = r.acceptance || {};
        if (acc.passed) {
            html += '<div class="wf-exec-reason wf-exec-pass">&#10003; pass</div>';
        } else if (acc.reason) {
            html += '<div class="wf-exec-reason wf-exec-pending">' + wfEsc(acc.reason) + '</div>';
        }
        html += '</td>';

        /* Cells */
        var cells = r.cells || [];
        for (var ci = 0; ci < cells.length; ci++) {
            var cell = cells[ci];
            var cellStatus = cell.status || 'empty';
            var affsForCell = cellAffs[ri + ',' + ci] || [];
            var hasActions = affsForCell.length > 0;
            var isComplete = cell.display_value && !hasActions && cellStatus !== 'empty' && cellStatus !== 'gated' && cellStatus !== 'locked';
            var cls = 'wf-exec-cell wf-exec-' + cellStatus;
            html += '<td class="' + cls + '"' + (isComplete ? ' data-completed="true"' : '') + '>';

            /* Display value */
            if (cellStatus === 'gated') {
                html += '<span class="wf-table-empty">[GATED]</span>';
            } else if (cellStatus === 'locked') {
                html += '<span class="wf-table-empty">[LOCKED]</span>';
            } else if (cell.display_value) {
                html += '<div class="wf-exec-display">' + wfEsc(cell.display_value) + '</div>';
            }

            /* Inline affordance controls */
            for (var ai = 0; ai < affsForCell.length; ai++) {
                var a = affsForCell[ai];
                var action = a.body.cell_action;
                var tooltip = a.method + ' ' + a.url + ' ' + JSON.stringify(a.body);

                if (action === 'fill' || action === 'amend') {
                    var vp = a.parameters && a.parameters.value;
                    html += '<div class="wf-exec-control">';
                    if (vp && vp.options) {
                        html += '<select class="wf-exec-select" data-aff-url="' + wfEsc(a.url) + '" data-aff-body="' + wfEsc(JSON.stringify(a.body)) + '">';
                        for (var oi = 0; oi < vp.options.length; oi++) {
                            html += '<option value="' + wfEsc(JSON.stringify(vp.options[oi])) + '">' + wfEsc(String(vp.options[oi])) + '</option>';
                        }
                        html += '</select>';
                    } else {
                        html += '<input class="wf-exec-input" type="text" data-aff-url="' + wfEsc(a.url) + '" data-aff-body="' + wfEsc(JSON.stringify(a.body)) + '"'
                            + (action === 'amend' && cell.display_value ? ' value="' + wfEsc(cell.display_value) + '"' : '') + '>';
                    }
                    html += '<button class="wf-exec-submit" data-aff-url="' + wfEsc(a.url) + '" data-aff-body="' + wfEsc(JSON.stringify(a.body)) + '" title="' + wfEsc(tooltip) + '">' + wfEsc(action === 'fill' ? 'Fill' : 'Amend') + '</button>';
                    html += '</div>';
                } else if (action === 'sign' || action === 're-sign') {
                    html += '<button class="wf-exec-btn" data-aff-url="' + wfEsc(a.url) + '" data-aff-body="' + wfEsc(JSON.stringify(a.body)) + '" title="' + wfEsc(tooltip) + '">' + wfEsc(action === 'sign' ? 'Sign' : 'Re-sign') + '</button>';
                } else if (action === 'mark_na') {
                    html += '<button class="wf-exec-btn wf-exec-btn-sec" data-aff-url="' + wfEsc(a.url) + '" data-aff-body="' + wfEsc(JSON.stringify(a.body)) + '" title="' + wfEsc(tooltip) + '">N/A</button>';
                } else if (action === 'initiate_issue') {
                    var ip = a.parameters && a.parameters.issue_type;
                    html += '<div class="wf-exec-control">';
                    if (ip && ip.options) {
                        html += '<select class="wf-exec-select" data-aff-url="' + wfEsc(a.url) + '" data-aff-body="' + wfEsc(JSON.stringify(a.body)) + '" data-param="issue_type">';
                        for (var oi = 0; oi < ip.options.length; oi++) {
                            html += '<option value="' + wfEsc(JSON.stringify(ip.options[oi])) + '">' + wfEsc(String(ip.options[oi])) + '</option>';
                        }
                        html += '</select>';
                    }
                    html += '<button class="wf-exec-submit" data-aff-url="' + wfEsc(a.url) + '" data-aff-body="' + wfEsc(JSON.stringify(a.body)) + '" title="' + wfEsc(tooltip) + '">Issue</button>';
                    html += '</div>';
                } else {
                    html += '<button class="wf-exec-btn" data-aff-url="' + wfEsc(a.url) + '" data-aff-body="' + wfEsc(JSON.stringify(a.body)) + '" title="' + wfEsc(tooltip) + '">' + wfEsc(a.label) + '</button>';
                }
            }

            html += '</td>';
        }
        html += '</tr>';
    }

    html += '</tbody></table></div></div>';
    return html;
}

/* ======================================================================
   RENDERER: HUMAN — Flowchart + interactive affordances
   ====================================================================== */

/* ── Flowchart renderer ──
   HTML cards with absolute positioning + SVG edge layer behind.
   Layout computed from data -> positions assigned, not measured.
*/

/* ── Layout config ── */
var _FC = {
    nodeW: 378,        /* card width */
    rowGap: 70,        /* vertical gap between cards */
    marginTop: 40,     /* top padding in graph */
    marginBot: 40,
    marginLeft: 140,   /* space for back-edge arcs + labels on the left */
    marginRight: 140,
    branchGap: 30      /* horizontal gap between parallel branch columns */
};

/* ── Build a condition label for router edges ── */
function _fcCondLabel(when) {
    if (!when) return 'default';
    if (when.type === 'field_equals') return when.key + ' = ' + when.value;
    if (when.type === 'field_truthy') return when.key;
    if (when.op === 'NOT') return 'NOT(...)';
    if (when.op) return when.op + '(...)';
    return '?';
}

/* ── Build layout plan from flat node array ── */
function _fcBuildLayout(nodes) {
    var nodeIdMap = {};
    for (var i = 0; i < nodes.length; i++) nodeIdMap[nodes[i].id] = i;

    /* Identify nodes claimed by forks (branch nodes + merge targets) */
    var claimed = {};  /* node_id -> true */
    var mergeOf = {};  /* node_id -> fork_node_id */
    for (var i = 0; i < nodes.length; i++) {
        var nd = nodes[i];
        if (nd.fork) {
            var branches = nd.fork.branches || {};
            for (var bid in branches) {
                var bnodes = branches[bid].nodes || [];
                for (var j = 0; j < bnodes.length; j++) claimed[bnodes[j]] = true;
            }
            if (nd.fork.merge) mergeOf[nd.fork.merge] = nd.id;
        }
    }

    /* Build ordered layout items */
    var items = [];
    for (var i = 0; i < nodes.length; i++) {
        var nd = nodes[i];
        if (claimed[nd.id]) continue;
        if (mergeOf[nd.id] !== undefined) continue;

        if (nd.fork) {
            var fg = {
                type: 'fork_group', fork_idx: i,
                branches: [], merge_idx: nodeIdMap[nd.fork.merge]
            };
            var forkBranches = nd.fork.branches || {};
            for (var bid in forkBranches) {
                var bnodeIds = forkBranches[bid].nodes || [];
                fg.branches.push({
                    id: bid,
                    label: forkBranches[bid].label || bid,
                    node_indices: bnodeIds.map(function(nid) { return nodeIdMap[nid]; })
                });
            }
            items.push(fg);
        } else if (nd.router) {
            items.push({type: 'router', idx: i});
        } else {
            items.push({type: 'node', idx: i});
        }
    }
    return items;
}

/* ── Collect edges from layout plan ── */
function _fcEdges(nodes, items) {
    var nodeIdMap = {};
    for (var i = 0; i < nodes.length; i++) nodeIdMap[nodes[i].id] = i;
    var edges = [];

    for (var ii = 0; ii < items.length; ii++) {
        var item = items[ii];
        var nextItem = items[ii + 1];

        /* Helper: index of next item's first node */
        var nextIdx = nextItem
            ? (nextItem.type === 'fork_group' ? nextItem.fork_idx : nextItem.idx)
            : null;

        if (item.type === 'node') {
            var nd = nodes[item.idx];
            /* Forward to next layout item (unless proceed has explicit target) */
            if (nd.proceed && nd.proceed.target && nodeIdMap[nd.proceed.target] !== undefined) {
                edges.push({from: item.idx, to: nodeIdMap[nd.proceed.target],
                    label: nd.proceed.label || '', type: 'goto'});
            } else if (nextIdx !== null) {
                edges.push({from: item.idx, to: nextIdx, label: '', type: 'forward'});
            }
            /* Navigation edges */
            var navs = nd.navigation || [];
            for (var ni = 0; ni < navs.length; ni++) {
                var nav = navs[ni];
                if (nav.action === 'go_back') {
                    var t = nav.node ? nodeIdMap[nav.node] : (item.idx > 0 ? item.idx - 1 : 0);
                    if (t !== undefined) edges.push({from: item.idx, to: t, label: nav.label, type: 'back'});
                } else if (nav.action === 'go_to' && nav.node && nodeIdMap[nav.node] !== undefined) {
                    edges.push({from: item.idx, to: nodeIdMap[nav.node], label: nav.label, type: 'goto'});
                }
            }
        }
        else if (item.type === 'router') {
            var routes = nodes[item.idx].router || [];
            for (var ri = 0; ri < routes.length; ri++) {
                var route = routes[ri];
                var targetIdx = nodeIdMap[route.target];
                if (targetIdx !== undefined) {
                    edges.push({from: item.idx, to: targetIdx,
                        label: _fcCondLabel(route.when), type: 'router'});
                }
            }
        }
        else if (item.type === 'fork_group') {
            /* Fork -> branch first nodes */
            for (var bi = 0; bi < item.branches.length; bi++) {
                var branch = item.branches[bi];
                if (branch.node_indices.length > 0) {
                    edges.push({from: item.fork_idx, to: branch.node_indices[0],
                        label: branch.label, type: 'fork'});
                }
            }
            /* Branch internal forward edges + navigation edges */
            for (var bi = 0; bi < item.branches.length; bi++) {
                var branch = item.branches[bi];
                for (var ni = 0; ni < branch.node_indices.length - 1; ni++) {
                    edges.push({from: branch.node_indices[ni],
                        to: branch.node_indices[ni + 1], label: '', type: 'forward'});
                }
                /* Navigation edges within branch nodes */
                for (var ni = 0; ni < branch.node_indices.length; ni++) {
                    var bnd = nodes[branch.node_indices[ni]];
                    var bnavs = bnd.navigation || [];
                    for (var nvi = 0; nvi < bnavs.length; nvi++) {
                        var nav = bnavs[nvi];
                        if (nav.action === 'go_back') {
                            var t = nav.node ? nodeIdMap[nav.node] : (ni > 0 ? branch.node_indices[ni - 1] : item.fork_idx);
                            if (t !== undefined) edges.push({from: branch.node_indices[ni], to: t, label: nav.label, type: 'back'});
                        } else if (nav.action === 'go_to' && nav.node && nodeIdMap[nav.node] !== undefined) {
                            edges.push({from: branch.node_indices[ni], to: nodeIdMap[nav.node], label: nav.label, type: 'goto'});
                        }
                    }
                }
                /* Last branch node -> merge */
                if (branch.node_indices.length > 0) {
                    edges.push({from: branch.node_indices[branch.node_indices.length - 1],
                        to: item.merge_idx, label: '', type: 'merge'});
                }
            }
            /* Merge -> next layout item (or merge proceed.target) */
            var mergeNd = nodes[item.merge_idx];
            if (mergeNd && mergeNd.proceed && mergeNd.proceed.target && nodeIdMap[mergeNd.proceed.target] !== undefined) {
                edges.push({from: item.merge_idx, to: nodeIdMap[mergeNd.proceed.target],
                    label: mergeNd.proceed.label || '', type: 'goto'});
            } else if (nextIdx !== null) {
                edges.push({from: item.merge_idx, to: nextIdx, label: '', type: 'forward'});
            }
        }
    }
    return edges;
}

/* ── Estimate card height for initial layout ── */
function _fcEstimateHeight(nd) {
    var eh = 36 + 16; /* header + padding */
    if (nd.instruction) eh += Math.min(80, 20 + nd.instruction.length * 0.3);
    var fields = nd.fields || [];
    if (fields.length) eh += fields.length * 26 + 8;
    if (nd.proceed) eh += 28;
    if (nd.fork) eh += 38;
    if (nd.router) eh += nd.router.length * 22 + 12;
    if (nd.actions && nd.actions.length) eh += 28;
    return Math.max(60, eh);
}

/* ── Render a single node card as an HTML string ── */
function _fcNodeCard(nd, idx) {
    var isRouter = nd.router && nd.router.length > 0;
    var isFork = nd.fork && nd.fork.branches;
    var cardCls = 'fc-card' + (isRouter ? ' fc-card-router' : '') + (isFork ? ' fc-card-fork' : '');
    var h = '<div class="' + cardCls + '">';

    /* Header */
    h += '<div class="fc-card-head">';
    h += '<span class="fc-num">' + (idx + 1) + '</span>';
    if (isRouter) h += '<span class="fc-badge fc-badge-router">\u25C7 Router</span>';
    else if (isFork) h += '<span class="fc-badge fc-badge-fork">\u2442 Fork</span>';
    h += '<span class="fc-card-title">' + wfEsc(nd.title || nd.id) + '</span>';
    h += '<code class="fc-card-id">' + wfEsc(nd.id) + '</code>';
    if (nd.show_all_fields) {
        h += '<span class="fc-eye" title="show_all_fields">&#128065;</span>';
    }
    h += '</div>';

    /* Instruction */
    if (nd.instruction) {
        h += '<div class="fc-instr">' + wfEsc(nd.instruction) + '</div>';
    }

    /* Fields */
    var fields = nd.fields || [];
    if (fields.length) {
        h += '<div class="fc-fields">';
        for (var fi = 0; fi < fields.length; fi++) {
            var fld = fields[fi];
            var typeCls = 'fc-ft-text';
            var typeLabel = 'T';
            if (fld.type === 'boolean') { typeCls = 'fc-ft-bool'; typeLabel = '?'; }
            else if (fld.type === 'select') { typeCls = 'fc-ft-sel'; typeLabel = '\u25BE'; }
            h += '<div class="fc-field">';
            h += '<span class="fc-field-dot ' + typeCls + '">' + typeLabel + '</span>';
            h += '<span class="fc-field-name">' + wfEsc(fld.label || fld.key) + '</span>';
            h += '<code class="fc-field-key">' + wfEsc(fld.key) + '</code>';
            if (fld.type === 'select' && fld.options && fld.options.length) {
                h += '<div class="fc-field-opts">';
                for (var oi = 0; oi < fld.options.length; oi++) {
                    h += '<div class="fc-field-opt">' + wfEsc(fld.options[oi]) + '</div>';
                }
                h += '</div>';
            }
            h += '</div>';
        }
        h += '</div>';
    }

    /* Router routes */
    if (isRouter) {
        h += '<div class="fc-routes">';
        for (var ri = 0; ri < nd.router.length; ri++) {
            var route = nd.router[ri];
            var condLabel = route.when ? _fcCondLabel(route.when) : 'default';
            h += '<div class="fc-route">';
            h += '<span class="fc-route-arrow">\u2192</span>';
            h += '<span class="fc-route-cond">' + wfEsc(condLabel) + '</span>';
            h += '<code class="fc-route-target">' + wfEsc(route.target) + '</code>';
            h += '</div>';
        }
        h += '</div>';
    }

    /* Fork definition */
    if (isFork) {
        h += '<div class="fc-fork-info">';
        h += '<span class="fc-fork-label">\u2442 ' + wfEsc(nd.fork.label || 'Fork') + '</span>';
        h += '<span class="fc-fork-merge">\u2192 merge: <code>' + wfEsc(nd.fork.merge || '?') + '</code></span>';
        var bkeys = Object.keys(nd.fork.branches);
        h += '<div class="fc-fork-branches">';
        for (var bi = 0; bi < bkeys.length; bi++) {
            var br = nd.fork.branches[bkeys[bi]];
            h += '<span class="fc-fork-branch">' + wfEsc(br.label || bkeys[bi]) + '</span>';
        }
        h += '</div></div>';
    }

    /* Proceed gate */
    if (nd.proceed) {
        var reqs = nd.proceed.requires || [];
        h += '<div class="fc-gate">';
        h += '<span class="fc-gate-lock">&#128274;</span>';
        h += '<span class="fc-gate-lbl">' + wfEsc(nd.proceed.label || 'Proceed') + '</span>';
        if (reqs.length) {
            var sep = (nd.proceed.gate_op === 'OR') ? ' or ' : ', ';
            h += '<span class="fc-gate-reqs">&#128273; ' + wfEsc(reqs.join(sep)) + '</span>';
        }
        h += '</div>';
    }

    /* Actions */
    var acts = nd.actions || [];
    if (acts.length) {
        h += '<div class="fc-acts">';
        for (var ai = 0; ai < acts.length; ai++) {
            var act = acts[ai];
            var cls = act.action === 'submit' ? 'fc-act-submit' : 'fc-act-restart';
            var icon = act.action === 'submit' ? '\u2714 ' : '\u21BB ';
            h += '<span class="fc-act ' + cls + '">' + icon + wfEsc(act.label) + '</span>';
        }
        h += '</div>';
    }

    h += '</div>';
    return h;
}

/* ── Build SVG edges (orthogonal only) ── */
function _fcBuildEdgeSvg(slots, edges, totalW, totalH) {
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" class="fc-edge-svg" width="' + totalW + '" height="' + totalH + '" viewBox="0 0 ' + totalW + ' ' + totalH + '">';
    svg += '<defs>';
    svg += '<marker id="fc-af" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" class="fc-mf"/></marker>';
    svg += '<marker id="fc-ab" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" class="fc-mb"/></marker>';
    svg += '<marker id="fc-ag" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" class="fc-mg"/></marker>';
    svg += '<marker id="fc-ak" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" class="fc-mk"/></marker>';
    svg += '<marker id="fc-ar" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" class="fc-mr"/></marker>';
    svg += '</defs>';
    var forkGroups = {}, mergeGroups = {}, otherEdges = [];
    for (var i = 0; i < edges.length; i++) {
        var e = edges[i];
        if (e.type === 'fork') { (forkGroups[e.from] = forkGroups[e.from] || []).push(e); }
        else if (e.type === 'merge') { (mergeGroups[e.to] = mergeGroups[e.to] || []).push(e); }
        else { otherEdges.push(e); }
    }
    for (var forkIdx in forkGroups) {
        var group = forkGroups[forkIdx]; var fs = slots[forkIdx]; if (!fs) continue;
        var trunkX = fs.cx, trunkY1 = fs.y + fs.h; var busY = trunkY1 + _FC.rowGap * 0.35;
        var branchXs = [];
        for (var gi = 0; gi < group.length; gi++) { var ts = slots[group[gi].to]; if (ts) branchXs.push(ts.cx); }
        if (!branchXs.length) continue;
        var minX = Math.min.apply(null, branchXs); var maxX = Math.max.apply(null, branchXs);
        svg += '<path d="M' + trunkX + ' ' + trunkY1 + ' V' + busY + '" class="fc-efk"/>';
        svg += '<path d="M' + minX + ' ' + busY + ' H' + maxX + '" class="fc-efk"/>';
        for (var gi = 0; gi < group.length; gi++) {
            var e = group[gi], ts = slots[e.to]; if (!ts) continue;
            svg += '<path d="M' + ts.cx + ' ' + busY + ' V' + ts.y + '" class="fc-efk" marker-end="url(#fc-ak)"/>';
            if (e.label) { svg += '<text x="' + (ts.cx + 6) + '" y="' + (ts.y - 14) + '" class="fc-el fc-el-fk" text-anchor="start" dominant-baseline="auto">' + wfEsc(e.label) + '</text>'; }
        }
    }
    for (var mergeIdx in mergeGroups) {
        var group = mergeGroups[mergeIdx]; var ts = slots[mergeIdx]; if (!ts) continue;
        var trunkX = ts.cx, trunkY2 = ts.y; var busY = trunkY2 - _FC.rowGap * 0.35;
        var branchXs = [];
        for (var gi = 0; gi < group.length; gi++) { var fs = slots[group[gi].from]; if (fs) branchXs.push(fs.cx); }
        if (!branchXs.length) continue;
        var minX = Math.min.apply(null, branchXs); var maxX = Math.max.apply(null, branchXs);
        for (var gi = 0; gi < group.length; gi++) { var fs = slots[group[gi].from]; if (!fs) continue; svg += '<path d="M' + fs.cx + ' ' + (fs.y + fs.h) + ' V' + busY + '" class="fc-emg"/>'; }
        svg += '<path d="M' + minX + ' ' + busY + ' H' + maxX + '" class="fc-emg"/>';
        svg += '<path d="M' + trunkX + ' ' + busY + ' V' + trunkY2 + '" class="fc-emg" marker-end="url(#fc-ak)"/>';
    }
    var rightEdgesBySource = {}, rightEdgesByTarget = {}, rightEdges = [], plainEdges = [];
    for (var i = 0; i < otherEdges.length; i++) {
        var e = otherEdges[i];
        if (e.type === 'router' || e.type === 'goto') {
            if (!rightEdgesBySource[e.from]) rightEdgesBySource[e.from] = [];
            if (!rightEdgesByTarget[e.to]) rightEdgesByTarget[e.to] = [];
            var srcIdx = rightEdgesBySource[e.from].length; var tgtIdx = rightEdgesByTarget[e.to].length;
            rightEdgesBySource[e.from].push(e); rightEdgesByTarget[e.to].push(e);
            rightEdges.push({edge: e, srcIdx: srcIdx, tgtIdx: tgtIdx, channel: rightEdges.length});
        } else { plainEdges.push(e); }
    }
    var backChannel = 0, nodeLeftCount = {};
    for (var i = 0; i < plainEdges.length; i++) {
        if (plainEdges[i].type === 'back') {
            nodeLeftCount[plainEdges[i].from] = (nodeLeftCount[plainEdges[i].from] || 0) + 1;
            nodeLeftCount[plainEdges[i].to] = (nodeLeftCount[plainEdges[i].to] || 0) + 1;
        }
    }
    for (var i = 0; i < plainEdges.length; i++) {
        var e = plainEdges[i], fs = slots[e.from], ts = slots[e.to]; if (!fs || !ts) continue;
        if (e.type === 'forward') {
            var x1 = fs.cx, y1 = fs.y + fs.h, x2 = ts.cx, y2 = ts.y;
            if (Math.abs(x1 - x2) < 2) { svg += '<path d="M' + x1 + ' ' + y1 + ' V' + y2 + '" class="fc-ef" marker-end="url(#fc-af)"/>'; }
            else { var midY = y1 + (y2 - y1) * 0.5; svg += '<path d="M' + x1 + ' ' + y1 + ' V' + midY + ' H' + x2 + ' V' + y2 + '" class="fc-ef" marker-end="url(#fc-af)"/>'; }
        } else if (e.type === 'back') {
            var channelX = 20 + backChannel * 16; var yOffset = backChannel * 30; backChannel++;
            var x1 = fs.x, y1 = fs.y + fs.h * 0.5 + yOffset, x2 = ts.x, y2 = ts.y + ts.h * 0.5 + yOffset;
            svg += '<path d="M' + x1 + ' ' + y1 + ' H' + channelX + ' V' + y2 + ' H' + x2 + '" class="fc-eb" marker-end="url(#fc-ab)"/>';
            if (e.label) { svg += '<text x="' + (x2 + 6) + '" y="' + (y2 - 14) + '" class="fc-el fc-el-b" text-anchor="start" dominant-baseline="auto">' + wfEsc(e.label) + '</text>'; }
        }
    }
    var nodeRightCount = {};
    for (var i = 0; i < rightEdges.length; i++) { var e = rightEdges[i].edge; nodeRightCount[e.from] = (nodeRightCount[e.from] || 0) + 1; nodeRightCount[e.to] = (nodeRightCount[e.to] || 0) + 1; }
    var nodeRightNext = {};
    for (var i = 0; i < rightEdges.length; i++) {
        var re = rightEdges[i], e = re.edge, fs = slots[e.from], ts = slots[e.to]; if (!fs || !ts) continue;
        var channelX = totalW - 30 - re.channel * 16;
        if (nodeRightNext[e.from] === undefined) nodeRightNext[e.from] = 0;
        if (nodeRightNext[e.to] === undefined) nodeRightNext[e.to] = 0;
        var srcSlot = nodeRightNext[e.from]++; var tgtSlot = nodeRightNext[e.to]++;
        var srcTotal = nodeRightCount[e.from]; var tgtTotal = nodeRightCount[e.to];
        var srcFrac = srcTotal > 1 ? 0.2 + 0.6 * srcSlot / (srcTotal - 1) : 0.4;
        var tgtFrac = tgtTotal > 1 ? 0.2 + 0.6 * tgtSlot / (tgtTotal - 1) : 0.4;
        var x1 = fs.x + fs.w, y1 = fs.y + fs.h * srcFrac, x2 = ts.x + ts.w, y2 = ts.y + ts.h * tgtFrac;
        var cls = e.type === 'router' ? 'fc-ert' : 'fc-eg'; var marker = e.type === 'router' ? 'url(#fc-ar)' : 'url(#fc-ag)';
        svg += '<path d="M' + x1 + ' ' + y1 + ' H' + channelX + ' V' + y2 + ' H' + x2 + '" class="' + cls + '" marker-end="' + marker + '"/>';
        if (e.label) { var labelCls = e.type === 'router' ? 'fc-el-rt' : 'fc-el-g'; svg += '<text x="' + (x2 + 6) + '" y="' + (y2 - 14) + '" class="fc-el ' + labelCls + '" text-anchor="start" dominant-baseline="auto">' + wfEsc(e.label) + '</text>'; }
    }
    svg += '</svg>';
    return svg;
}

/* ── Compute slot positions from layout plan ── */
function _fcComputeSlots(nodes, items) {
    var slots = new Array(nodes.length); var cy = _FC.marginTop;
    var maxCols = 1;
    for (var ii = 0; ii < items.length; ii++) { if (items[ii].type === 'fork_group' && items[ii].branches.length > maxCols) maxCols = items[ii].branches.length; }
    var colStep = _FC.nodeW + _FC.branchGap;
    var totalW = _FC.marginLeft + maxCols * _FC.nodeW + (maxCols - 1) * _FC.branchGap + _FC.marginRight;
    var singleX = _FC.marginLeft + ((maxCols * _FC.nodeW + (maxCols - 1) * _FC.branchGap) - _FC.nodeW) / 2;
    for (var ii = 0; ii < items.length; ii++) {
        var item = items[ii];
        if (item.type === 'node' || item.type === 'router') {
            var eh = _fcEstimateHeight(nodes[item.idx]);
            slots[item.idx] = {x: singleX, y: cy, w: _FC.nodeW, h: eh, cx: singleX + _FC.nodeW / 2}; cy += eh + _FC.rowGap;
        } else if (item.type === 'fork_group') {
            var forkH = _fcEstimateHeight(nodes[item.fork_idx]);
            slots[item.fork_idx] = {x: singleX, y: cy, w: _FC.nodeW, h: forkH, cx: singleX + _FC.nodeW / 2}; cy += forkH + _FC.rowGap;
            var nBranches = item.branches.length;
            var branchGroupW = nBranches * _FC.nodeW + (nBranches - 1) * _FC.branchGap;
            var branchGroupX = _FC.marginLeft + ((maxCols * _FC.nodeW + (maxCols - 1) * _FC.branchGap) - branchGroupW) / 2;
            var maxRows = 0;
            for (var bi = 0; bi < nBranches; bi++) { if (item.branches[bi].node_indices.length > maxRows) maxRows = item.branches[bi].node_indices.length; }
            for (var ri = 0; ri < maxRows; ri++) {
                var rowH = 0;
                for (var bi = 0; bi < nBranches; bi++) { var branch = item.branches[bi]; if (ri < branch.node_indices.length) { var h = _fcEstimateHeight(nodes[branch.node_indices[ri]]); if (h > rowH) rowH = h; } }
                for (var bi = 0; bi < nBranches; bi++) { var branch = item.branches[bi]; if (ri < branch.node_indices.length) { var bIdx = branch.node_indices[ri]; var bx = branchGroupX + bi * colStep; slots[bIdx] = {x: bx, y: cy, w: _FC.nodeW, h: _fcEstimateHeight(nodes[bIdx]), cx: bx + _FC.nodeW / 2}; } }
                cy += rowH + _FC.rowGap;
            }
            var mergeH = _fcEstimateHeight(nodes[item.merge_idx]);
            slots[item.merge_idx] = {x: singleX, y: cy, w: _FC.nodeW, h: mergeH, cx: singleX + _FC.nodeW / 2}; cy += mergeH + _FC.rowGap;
        }
    }
    var totalH = cy - _FC.rowGap + _FC.marginBot;
    return {slots: slots, totalW: totalW, totalH: totalH};
}

/* ── Detailed card node renderer ── */
function _cardNodeRenderer(item, status) {
    var nd = _fcDefnNodes && _fcDefnNodes[item.id];
    if (!nd) return _pillNodeRenderer(item, status);
    var idx = _fcDefnIdx && _fcDefnIdx[item.id];
    return _fcNodeCard(nd, idx != null ? idx : 0);
}
var _fcDefnNodes = null;
var _fcDefnIdx = null;

/* ── Schematic-positioned detailed flowchart ── */
function _schematicFlowchart(defn, stateObj) {
    if (!defn || !defn.nodes || !defn.nodes.length) return '';
    var nodes = defn.nodes;
    var current = stateObj.node || '';
    var completed = stateObj.completed_nodes || [];
    _fcDefnNodes = {}; _fcDefnIdx = {};
    for (var i = 0; i < nodes.length; i++) { _fcDefnNodes[nodes[i].id] = nodes[i]; _fcDefnIdx[nodes[i].id] = i; }
    var spine;
    try { spine = Schematic.definitionToSpine(defn); } catch (e) {
        return '<div class="fc-wrap"><pre style="color:red;padding:1rem;">Schematic error: ' + e.message + '</pre></div>';
    }
    var graphId = 'sch-fc-' + Math.random().toString(36).substr(2, 6);
    var execState = { current: current, completed: completed };
    setTimeout(function() {
        var el = document.getElementById(graphId); if (!el) return;
        try {
            var sampleDiv = document.createElement('div');
            sampleDiv.style.cssText = 'position:absolute;left:-9999px;visibility:hidden;width:' + _FC.nodeW + 'px;';
            sampleDiv.innerHTML = _fcNodeCard(nodes[0], 0);
            document.body.appendChild(sampleDiv);
            var headEl = sampleDiv.querySelector('.fc-card-head');
            var handlePx = headEl ? headEl.getBoundingClientRect().height / 2 : 18;
            document.body.removeChild(sampleDiv);
            Schematic.renderHybrid(spine, el, execState, { nodeW: _FC.nodeW, lineGap: 16, handlePx: handlePx, nodeRenderer: _cardNodeRenderer });
        } catch (e) { el.innerHTML = '<pre style="color:red;padding:1rem;">Flowchart error: ' + e.message + '</pre>'; }
    }, 0);
    var hdr = '<div class="fc-hdr">';
    hdr += '<div class="fc-hdr-title">' + wfEsc(defn.workflow_title || '') + '</div>';
    if (defn.workflow_id) hdr += '<code class="fc-hdr-id">' + wfEsc(defn.workflow_id) + '</code>';
    if (defn.workflow_description) hdr += '<div class="fc-hdr-desc">' + wfEsc(defn.workflow_description) + '</div>';
    hdr += '</div>';
    return '<div class="fc-wrap">' + hdr + '<div class="fc-graph" id="' + graphId + '" style="min-height:200px;"></div></div>';
}

/* ── Main definition renderer (schematic card flowchart) ── */
function humanRenderDefinition(defn) {
    if (!defn) return '';
    var nodes = defn.nodes || [];
    var h = '<div class="fc-hdr">';
    h += '<span class="fc-hdr-title">' + wfEsc(defn.workflow_title || '(untitled)') + '</span>';
    if (defn.workflow_id) h += ' <code class="fc-hdr-id">' + wfEsc(defn.workflow_id) + '</code>';
    if (defn.workflow_description) h += '<div class="fc-hdr-desc">' + wfEsc(defn.workflow_description) + '</div>';
    h += '</div>';
    if (!nodes.length) return '<div class="fc-wrap">' + h + '<div class="fc-empty">No nodes defined</div></div>';
    var items = _fcBuildLayout(nodes); var edges = _fcEdges(nodes, items);
    var layout = _fcComputeSlots(nodes, items); var slots = layout.slots, totalW = layout.totalW, totalH = layout.totalH;
    var edgeSvg = _fcBuildEdgeSvg(slots, edges, totalW, totalH);
    var layoutData = {items: items, edges: edges, nodeCount: nodes.length};
    var layoutB64 = btoa(JSON.stringify(layoutData));
    h += '<div class="fc-graph" data-layout="' + layoutB64 + '" style="position:relative;width:' + totalW + 'px;min-height:' + totalH + 'px;">';
    h += '<div class="fc-edge-layer">' + edgeSvg + '</div>';
    for (var i = 0; i < nodes.length; i++) { var s = slots[i]; if (!s) continue; h += '<div class="fc-card-wrap" data-idx="' + i + '" style="position:absolute;left:' + s.x + 'px;top:' + s.y + 'px;width:' + s.w + 'px;">'; h += _fcNodeCard(nodes[i], i); h += '</div>'; }
    h += '</div>';
    return '<div class="fc-wrap">' + h + '</div>';
}

/* ── State props (definition-aware) ── */
function humanRenderStateProps(state) {
    var s = state.state || {};
    var known = ['workflow','node','node_title','completed_nodes','definition','fields','table','execution_table','fork_state','banner_definition'];
    var extra = Object.keys(s).filter(function(k) { return known.indexOf(k) === -1; });
    if (!extra.length) return '';
    var html = '';
    for (var i = 0; i < extra.length; i++) {
        var k = extra[i], v = s[k];
        if (k === 'definition' && _isDefinition(v)) { html += _schematicFlowchart(v, s); continue; }
        html += '<div class="wf-card"><div class="wf-card-head">state.' + wfEsc(k) + '</div>';
        if (Array.isArray(v) && v.length && typeof v[0] === 'string') { html += '<ul class="wf-extra-list">'; for (var j = 0; j < v.length; j++) html += '<li>' + wfEsc(v[j]) + '</li>'; html += '</ul>'; }
        else if (v && typeof v === 'object') { html += wfRenderValue(v); }
        else { html += '<div class="wf-field-value">' + wfRenderValue(v) + '</div>'; }
        html += '</div>';
    }
    return html;
}

/* ── Affordance execution ── */
function _wfExecAffordance(url, body) {
    fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(body),
    });
    /* SSE will push the updated state — no need to handle the response */
}

function _wfBindAffordances(container) {
    /* Option buttons (select affordances) */
    container.querySelectorAll('.wf-aff-opt-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var url = btn.getAttribute('data-aff-url');
            var val = JSON.parse(btn.getAttribute('data-aff-value'));
            _wfExecAffordance(url, { value: val });
        });
    });
    /* Text input — dynamic tooltips + submit */
    container.querySelectorAll('.wf-aff-input').forEach(function(input) {
        var url = input.getAttribute('data-aff-url');
        var btn = container.querySelector('.wf-aff-submit[data-aff-url="' + url + '"]');
        function updateTooltip() {
            var tip = 'POST ' + url + ' ' + JSON.stringify({value: input.value || ''});
            if (btn) btn.title = tip;
        }
        updateTooltip();
        input.addEventListener('input', updateTooltip);
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && input.value) _wfExecAffordance(url, { value: input.value });
        });
        if (btn) {
            btn.addEventListener('click', function() {
                if (input.value) _wfExecAffordance(url, { value: input.value });
            });
        }
    });
    /* Dropdown selects + Set button */
    container.querySelectorAll('.wf-aff-select').forEach(function(select) {
        var url = select.getAttribute('data-aff-url');
        var row = select.closest('.wf-field-row') || select.closest('.wf-aff-controls');
        var btn = row ? row.querySelector('.wf-aff-submit') : container.querySelector('.wf-aff-submit[data-aff-url="' + url + '"]');
        function updateTooltip() {
            if (!select.value) { if (btn) btn.title = ''; return; }
            var val = JSON.parse(select.value);
            var tip = 'POST ' + url + ' ' + JSON.stringify({value: val});
            if (btn) btn.title = tip;
        }
        updateTooltip();
        select.addEventListener('change', updateTooltip);
        if (btn) {
            btn.addEventListener('click', function() {
                if (!select.value) return;
                var val = JSON.parse(select.value);
                _wfExecAffordance(url, { value: val });
            });
        }
    });
    /* No-value action buttons */
    container.querySelectorAll('.wf-aff-action-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var url = btn.getAttribute('data-aff-url');
            var body = JSON.parse(btn.getAttribute('data-aff-body'));
            _wfExecAffordance(url, body);
        });
    });
    /* Parametric form submissions */
    container.querySelectorAll('.wf-param-submit').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var form = btn.closest('.wf-param-form');
            var url = form.getAttribute('data-aff-url');
            var body = JSON.parse(JSON.stringify(JSON.parse(form.getAttribute('data-aff-body'))));
            form.querySelectorAll('.wf-param-input').forEach(function(input) {
                var param = input.getAttribute('data-param');
                if (input.tagName === 'SELECT') {
                    body[param] = JSON.parse(input.value);
                } else {
                    body[param] = input.value;
                }
            });
            _wfExecAffordance(url, body);
        });
    });
    /* Generic inline affordance forms (wfRenderAffordances) */
    container.querySelectorAll('.wf-aff-go').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var inline = btn.closest('.wf-aff-inline');
            var url = btn.getAttribute('data-aff-url');
            var body = JSON.parse(JSON.stringify(JSON.parse(inline.getAttribute('data-aff-body'))));
            inline.querySelectorAll('.wf-param-input').forEach(function(input) {
                var param = input.getAttribute('data-param');
                if (input.tagName === 'SELECT') {
                    body[param] = JSON.parse(input.value);
                } else {
                    body[param] = input.value;
                }
            });
            _wfExecAffordance(url, body);
        });
    });
    /* Generic simple affordance buttons (wfRenderAffordances) */
    container.querySelectorAll('.wf-aff-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var url = btn.getAttribute('data-aff-url');
            var body = JSON.parse(btn.getAttribute('data-aff-body'));
            _wfExecAffordance(url, body);
        });
    });
    /* Execution cell submit buttons (fill/amend with value input) */
    container.querySelectorAll('.wf-exec-submit').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var url = btn.getAttribute('data-aff-url');
            var body = JSON.parse(JSON.stringify(JSON.parse(btn.getAttribute('data-aff-body'))));
            var control = btn.closest('.wf-exec-control');
            if (control) {
                var input = control.querySelector('.wf-exec-input, .wf-exec-select');
                if (input) {
                    var param = input.getAttribute('data-param') || 'value';
                    body[param] = input.tagName === 'SELECT' ? JSON.parse(input.value) : input.value;
                }
            }
            _wfExecAffordance(url, body);
        });
    });
    /* Execution cell action buttons (sign, mark_na, etc.) */
    container.querySelectorAll('.wf-exec-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var url = btn.getAttribute('data-aff-url');
            var body = JSON.parse(btn.getAttribute('data-aff-body'));
            _wfExecAffordance(url, body);
        });
    });
}

/* ── Focus target label derivation (renderer's responsibility) ── */
function _wfFocusLabel(target, s) {
    if (target === 'fields') return 'Fields';
    if (target === 'table') return 'Table';
    if (target === 'exec') return 'Execution Table';
    if (target && target.indexOf('table.col.') === 0) {
        var ci = parseInt(target.split('.')[2], 10);
        var cols = (s.table && s.table.columns) || [];
        var colName = (cols[ci] && cols[ci].name) || ('Column ' + ci);
        return 'Column ' + ci + ': ' + colName;
    }
    return target || '';
}

function _wfFocusBreadcrumb(target, s) {
    var label = _wfFocusLabel(target, s);
    if (target && target.indexOf('table.col.') === 0) {
        return 'Table > ' + label;
    }
    return label;
}

/* ── Classify affordances by role ── */
function _wfClassifyAffordances(affordances) {
    var focus = [], unfocus = null, objectAffs = [], actionBar = [];
    for (var i = 0; i < affordances.length; i++) {
        var a = affordances[i];
        var url = a.url || '';
        if (url.match(/\/focus$/) && a.body && a.body.target) {
            focus.push(a);
        } else if (url.match(/\/unfocus$/)) {
            unfocus = a;
        } else if (url.match(/\/(proceed|go_back|submit|restart|complete|switch_branch|go_to)$/) ||
                   (a.label && /Proceed|Go back|Submit|Complete|Restart/i.test(a.label))) {
            actionBar.push(a);
        } else {
            objectAffs.push(a);
        }
    }
    return { focus: focus, unfocus: unfocus, objectAffs: objectAffs, actionBar: actionBar };
}

/* ── Read-only fields (state zone) ── */
function _wfRenderFieldsReadOnly(fields, fieldCategory) {
    var keys = Object.keys(fields);
    if (!keys.length) return '';
    var html = '<div class="wf-fields">';
    for (var i = 0; i < keys.length; i++) {
        var k = keys[i];
        var f = fields[k];
        var cat = fieldCategory[k] || null;
        var catCls = cat ? ' wf-fb-' + cat : '';
        var tagMap = {outcome:'SET', 'new':'NEW', modified:'CHANGED'};
        var tagCls = {outcome:'wf-tag-outcome', 'new':'wf-tag-new', modified:'wf-tag-modified'};
        var tag = cat ? '<span class="' + tagCls[cat] + '">' + tagMap[cat] + '</span>' : '';
        html += '<div class="wf-field' + catCls + '">';
        html += '<div class="wf-field-label">' + wfEsc(k) + tag + '</div>';
        if (f && typeof f === 'object' && 'value' in f) {
            if (f.value == null) {
                html += '<div class="wf-field-value wf-field-empty">(not set)</div>';
            } else {
                var dv = f.value;
                if (dv === true) dv = 'Yes';
                else if (dv === false) dv = 'No';
                html += '<div class="wf-field-value">' + wfEsc(dv) + '</div>';
            }
        } else {
            html += '<div class="wf-field-value">' + wfRenderValue(f) + '</div>';
        }
        html += '</div>';
    }
    return html + '</div>';
}

/* ── Read-only table (state zone) ── */
function _wfRenderTableReadOnly(table) {
    if (!table) return '';
    var cols = table.columns || [];
    var rows = table.rows || [];
    var props = table.properties || {};
    var html = '';

    if (table.summary) {
        html += '<div class="wf-table-summary">' + wfEsc(table.summary) + '</div>';
    }

    if (cols.length) {
        html += '<div class="wf-table-wrap"><table class="wf-table"><thead><tr>';
        html += '<th class="wf-table-rownum">#</th>';
        for (var ci = 0; ci < cols.length; ci++) {
            var c = cols[ci];
            html += '<th><div class="wf-table-colname">' + wfEsc(c.name) + '</div>';
            html += '<div class="wf-table-coltype">' + wfEsc(c.type) + '</div>';
            if (c.choices) html += '<div class="wf-table-colmeta">choices: ' + wfEsc(JSON.stringify(c.choices)) + '</div>';
            if (c.rule) html += '<div class="wf-table-colmeta">rule: ' + wfEsc(wfRuleToExpr(c.rule, cols)) + '</div>';
            html += '</th>';
        }
        html += '</tr></thead><tbody>';
        if (rows.length) {
            for (var ri = 0; ri < rows.length; ri++) {
                html += '<tr><td class="wf-table-rownum">' + ri + '</td>';
                for (var ci = 0; ci < cols.length; ci++) {
                    var val = (ri < rows.length && ci < rows[ri].length) ? rows[ri][ci] : '';
                    html += '<td>' + (val ? wfEsc(val) : '<span class="wf-table-empty">&mdash;</span>') + '</td>';
                }
                html += '</tr>';
            }
        } else {
            html += '<tr><td colspan="' + (cols.length + 1) + '" class="wf-table-empty">(no rows)</td></tr>';
        }
        html += '</tbody></table></div>';
    } else {
        html += '<div class="wf-table-empty">(no columns defined)</div>';
    }

    /* Properties — read-only */
    var propKeys = Object.keys(props).filter(function(k) { return k !== 'affordances'; });
    if (propKeys.length) {
        html += '<div class="wf-table-props">';
        for (var i = 0; i < propKeys.length; i++) {
            var pk = propKeys[i];
            var pv = props[pk];
            var pvDisplay = pv === true ? 'Yes' : pv === false ? 'No' : pv != null ? String(pv) : '(not set)';
            html += '<div class="wf-table-prop-row">';
            html += '<span class="wf-table-prop-label">' + wfEsc(pk.replace(/_/g, ' ')) + '</span>';
            html += '<span class="wf-field-current">' + wfEsc(pvDisplay) + '</span>';
            html += '</div>';
        }
        html += '</div>';
    }

    return html;
}

/* ── Read-only execution table (state zone) ── */
function _wfRenderExecTableReadOnly(et) {
    if (!et) return '';
    var cols = et.columns || [];
    var rows = et.rows || [];
    if (!cols.length) return '<div class="wf-table-empty">(no columns)</div>';

    var html = '<div class="wf-table-wrap"><table class="wf-table"><thead><tr>';
    html += '<th class="wf-table-rownum">Row</th>';
    for (var ci = 0; ci < cols.length; ci++) {
        var c = cols[ci];
        html += '<th><div class="wf-table-colname">' + wfEsc(c.name) + '</div>';
        html += '<div class="wf-table-coltype">' + wfEsc(c.type) + '</div>';
        html += '</th>';
    }
    html += '</tr></thead><tbody>';
    for (var ri = 0; ri < rows.length; ri++) {
        var r = rows[ri];
        var rowCls = r.gated ? ' class="wf-row-gated"' : '';
        html += '<tr' + rowCls + '>';
        html += '<td class="wf-table-rownum">';
        html += wfEsc(r.row_id || String(r.row));
        var acc = r.acceptance || {};
        if (acc.passed) {
            html += '<div class="wf-exec-reason wf-exec-pass">&#10003; pass</div>';
        } else if (acc.reason) {
            html += '<div class="wf-exec-reason wf-exec-pending">' + wfEsc(acc.reason) + '</div>';
        }
        html += '</td>';
        var cells = r.cells || [];
        for (var ci = 0; ci < cells.length; ci++) {
            var cell = cells[ci];
            var cellStatus = cell.status || 'empty';
            var isComplete = cell.display_value && cellStatus !== 'empty' && cellStatus !== 'gated' && cellStatus !== 'locked';
            var cls = 'wf-exec-cell wf-exec-' + cellStatus;
            html += '<td class="' + cls + '"' + (isComplete ? ' data-completed="true"' : '') + '>';
            if (cellStatus === 'gated') {
                html += '<span class="wf-table-empty">[GATED]</span>';
            } else if (cellStatus === 'locked') {
                html += '<span class="wf-table-empty">[LOCKED]</span>';
            } else if (cell.display_value) {
                html += '<div class="wf-exec-display">' + wfEsc(cell.display_value) + '</div>';
            }
            html += '</td>';
        }
        html += '</tr>';
    }
    html += '</tbody></table></div>';
    return html;
}

/* ── Focus zone ── */
function _wfRenderFocusZone(s, state, classified, fieldCategory) {
    var focus = s.focus;
    if (!focus) {
        if (classified.focus.length) {
            return '<div class="wf-focus-hint">Focus on an element to reveal its affordances.</div>';
        }
        return '';
    }

    var html = '<div class="wf-focus-zone">';

    /* Header: breadcrumb + navigation + close */
    html += '<div class="wf-focus-header">';
    html += '<span class="wf-focus-breadcrumb">' + wfEsc(_wfFocusBreadcrumb(focus, s)) + '</span>';
    /* Sibling/parent focus navigation */
    var navAffs = classified.focus.filter(function(a) { return a.body.target !== focus; });
    if (navAffs.length) {
        html += '<span class="wf-focus-nav">';
        for (var i = 0; i < navAffs.length; i++) {
            var na = navAffs[i];
            var tooltip = na.method + ' ' + na.url + ' ' + JSON.stringify(na.body);
            html += '<button class="wf-focus-nav-btn wf-aff-btn" data-aff-url="' + wfEsc(na.url) + '" data-aff-body="' + wfEsc(JSON.stringify(na.body)) + '" title="' + wfEsc(tooltip) + '">' + wfEsc(_wfFocusLabel(na.body.target, s)) + '</button>';
        }
        html += '</span>';
    }
    if (classified.unfocus) {
        var ua = classified.unfocus;
        var tooltip = ua.method + ' ' + ua.url + ' ' + JSON.stringify(ua.body);
        html += '<button class="wf-focus-close wf-aff-btn" data-aff-url="' + wfEsc(ua.url) + '" data-aff-body="' + wfEsc(JSON.stringify(ua.body)) + '" title="' + wfEsc(tooltip) + '">Close</button>';
    }
    html += '</div>';

    /* Focused object's affordances */
    var affs = classified.objectAffs;
    if (focus === 'fields') {
        /* Render field affordances using the inline field patterns */
        html += _wfRenderFieldAffordances(s.fields, fieldCategory);
    } else if (affs.length) {
        /* Generic: parametric + simple */
        var paramAffs = [], simpleAffs = [];
        for (var i = 0; i < affs.length; i++) {
            var a = affs[i];
            if (a.parameters && Object.keys(a.parameters).length) {
                paramAffs.push(a);
            } else {
                simpleAffs.push(a);
            }
        }
        if (paramAffs.length) {
            for (var i = 0; i < paramAffs.length; i++) {
                html += wfRenderParamAff(paramAffs[i]);
            }
        }
        if (simpleAffs.length) {
            html += '<div class="wf-action-bar">';
            for (var i = 0; i < simpleAffs.length; i++) {
                var a = simpleAffs[i];
                var aLabel = a.label || (a.body && a.body.key ? a.body.key.replace(/_/g, ' ') : a.url.split('/').pop().replace(/_/g, ' '));
                var tooltip = a.method + ' ' + a.url + ' ' + JSON.stringify(a.body);
                html += '<button class="wf-aff-btn" data-aff-url="' + wfEsc(a.url) + '" data-aff-body="' + wfEsc(JSON.stringify(a.body)) + '" title="' + wfEsc(tooltip) + '">' + wfEsc(aLabel) + '</button>';
            }
            html += '</div>';
        }
    }

    /* Nested focusable objects (e.g., columns when focused on table) */
    var nestedFocus = classified.focus.filter(function(a) {
        return a.body.target && a.body.target.indexOf(focus + '.') === 0;
    });
    if (nestedFocus.length) {
        html += '<div class="wf-focus-nested-list">';
        for (var i = 0; i < nestedFocus.length; i++) {
            var nf = nestedFocus[i];
            var tooltip = nf.method + ' ' + nf.url + ' ' + JSON.stringify(nf.body);
            html += '<button class="wf-focus-nested-btn wf-aff-btn" data-aff-url="' + wfEsc(nf.url) + '" data-aff-body="' + wfEsc(JSON.stringify(nf.body)) + '" title="' + wfEsc(tooltip) + '">' + wfEsc(_wfFocusLabel(nf.body.target, s)) + '</button>';
        }
        html += '</div>';
    }

    html += '</div>';
    return html;
}

/* ── Field affordances in focus zone (reuses field patterns) ── */
function _wfRenderFieldAffordances(fields, fieldCategory) {
    if (!fields) return '';
    var keys = Object.keys(fields);
    var html = '<div class="wf-fields">';
    for (var i = 0; i < keys.length; i++) {
        var k = keys[i];
        var f = fields[k];
        if (!f || typeof f !== 'object' || !('value' in f)) continue;
        var aff = f.affordance;
        if (!aff) continue;
        var cat = fieldCategory[k] || null;
        var catCls = cat ? ' wf-fb-' + cat : '';
        html += '<div class="wf-field' + catCls + '">';
        html += '<div class="wf-field-label">' + wfEsc(k) + '</div>';
        if (f.instruction) {
            html += '<div class="wf-field-instruction">' + wfEsc(f.instruction) + '</div>';
        }
        var options = (aff.parameters && aff.parameters.value && aff.parameters.value.options) || null;
        if (options) {
            var useDropdown = options.length > 3;
            if (!useDropdown) {
                for (var oi = 0; oi < options.length; oi++) {
                    var ol = options[oi] === true ? 'Yes' : options[oi] === false ? 'No' : String(options[oi]);
                    if (ol.length > 20) { useDropdown = true; break; }
                }
            }
            var curDisplay = f.value === true ? 'Yes' : f.value === false ? 'No' : f.value != null ? String(f.value) : '';
            html += '<div class="wf-field-row">';
            html += curDisplay ? '<span class="wf-field-current">' + wfEsc(curDisplay) + '</span>' : '<span class="wf-field-current wf-field-empty">(not set)</span>';
            if (useDropdown) {
                html += '<select class="wf-aff-select" data-aff-url="' + wfEsc(aff.url) + '">';
                html += '<option value="">&mdash; Select &mdash;</option>';
                for (var oi = 0; oi < options.length; oi++) {
                    var oval = options[oi];
                    var olabel = oval === true ? 'Yes' : oval === false ? 'No' : String(oval);
                    html += '<option value="' + wfEsc(JSON.stringify(oval)) + '">' + wfEsc(olabel) + '</option>';
                }
                html += '</select>';
                html += '<button class="wf-aff-submit" data-aff-url="' + wfEsc(aff.url) + '">Set</button>';
            } else {
                for (var oi = 0; oi < options.length; oi++) {
                    var oval = options[oi];
                    var olabel = oval === true ? 'Yes' : oval === false ? 'No' : String(oval);
                    var isActive = JSON.stringify(oval) === JSON.stringify(f.value);
                    var btnTooltip = aff.method + ' ' + aff.url + ' ' + JSON.stringify({value: oval});
                    html += '<button class="wf-aff-opt-btn' + (isActive ? ' wf-aff-opt-active' : '') + '" data-aff-url="' + wfEsc(aff.url) + '" data-aff-value="' + wfEsc(JSON.stringify(oval)) + '" title="' + wfEsc(btnTooltip) + '">' + wfEsc(olabel) + '</button>';
                }
            }
            html += '</div>';
        } else {
            var curVal = f.value == null ? '' : String(f.value);
            html += '<div class="wf-field-row">';
            html += curVal ? '<span class="wf-field-current">' + wfEsc(curVal) + '</span>' : '<span class="wf-field-current wf-field-empty">(not set)</span>';
            html += '<input class="wf-aff-input" type="text" data-aff-url="' + wfEsc(aff.url) + '" placeholder="New value\u2026">';
            html += '<button class="wf-aff-submit" data-aff-url="' + wfEsc(aff.url) + '">Set</button>';
            html += '</div>';
        }
        html += '</div>';
    }
    return html + '</div>';
}

/* ── Page renderer (shared default + verbose) ── */
function _humanPage(container, state, msg, feedback, verbose) {
    if (!container || !state) return;
    var fieldCategory = {}, affCategory = {};
    if (feedback) {
        var out = feedback.outcome || {}, eff = feedback.effects || {};
        for (var k in out) fieldCategory[k] = 'outcome';
        for (var k in (eff.new_fields || {})) fieldCategory[k] = 'new';
        for (var k in (eff.modified_fields || {})) fieldCategory[k] = 'modified';
        (eff.new_affordances || []).forEach(function(a){ affCategory[a.label] = 'new'; });
        (eff.modified_affordances || []).forEach(function(a){ affCategory[a.label] = 'modified'; });
    }
    var html = '', s = state.state || {};

    /* ── Header ── */
    html += '<div class="wf-header"><h1 class="wf-title">' + wfEsc(s.workflow || 'Workflow') + '</h1></div>';
    html += wfRenderBanner(state);
    html += '<div class="wf-section"><div class="wf-section-head">' + wfEsc(s.node_title || s.node) + '</div></div>';
    if (feedback && feedback.outcome && feedback.outcome.error) {
        html += '<div class="wf-error">' + wfEsc(feedback.outcome.error) + '</div>';
    }
    if (state.instructions) html += '<div class="wf-desc">' + wfEsc(state.instructions) + '</div>';
    html += humanRenderStateProps(state);
    if (s.definition && _isDefinition(s.definition)) { html += _schematicFlowchart(s.definition, s); }

    /* ── Classify affordances ── */
    var classified = _wfClassifyAffordances(state.affordances || []);

    /* ── State zone (read-only) ── */
    if (s.fields) {
        var fieldFocusBtn = '';
        for (var fi = 0; fi < classified.focus.length; fi++) {
            if (classified.focus[fi].body.target === 'fields') {
                var fa = classified.focus[fi];
                fieldFocusBtn = '<button class="wf-focus-btn wf-aff-btn" data-aff-url="' + wfEsc(fa.url) + '" data-aff-body="' + wfEsc(JSON.stringify(fa.body)) + '" title="' + wfEsc(fa.method + ' ' + fa.url + ' ' + JSON.stringify(fa.body)) + '">Focus</button>';
                break;
            }
        }
        var fieldsFocused = s.focus === 'fields' ? ' wf-card-focused' : '';
        html += '<div class="wf-card' + fieldsFocused + '"><div class="wf-card-head">Fields' + fieldFocusBtn + '</div>';
        html += _wfRenderFieldsReadOnly(s.fields, fieldCategory);
        html += '</div>';
    }

    if (s.execution_table) {
        var execFocusBtn = '';
        for (var fi = 0; fi < classified.focus.length; fi++) {
            if (classified.focus[fi].body.target === 'exec') {
                var fa = classified.focus[fi];
                execFocusBtn = '<button class="wf-focus-btn wf-aff-btn" data-aff-url="' + wfEsc(fa.url) + '" data-aff-body="' + wfEsc(JSON.stringify(fa.body)) + '" title="' + wfEsc(fa.method + ' ' + fa.url + ' ' + JSON.stringify(fa.body)) + '">Focus</button>';
                break;
            }
        }
        var execFocused = s.focus === 'exec' ? ' wf-card-focused' : '';
        html += '<div class="wf-card' + execFocused + '"><div class="wf-card-head">Execution Table' + execFocusBtn + '</div>';
        html += _wfRenderExecTableReadOnly(s.execution_table);
        html += '</div>';
    } else if (s.table) {
        var tableFocusBtn = '';
        for (var fi = 0; fi < classified.focus.length; fi++) {
            if (classified.focus[fi].body.target === 'table') {
                var fa = classified.focus[fi];
                tableFocusBtn = '<button class="wf-focus-btn wf-aff-btn" data-aff-url="' + wfEsc(fa.url) + '" data-aff-body="' + wfEsc(JSON.stringify(fa.body)) + '" title="' + wfEsc(fa.method + ' ' + fa.url + ' ' + JSON.stringify(fa.body)) + '">Focus</button>';
                break;
            }
        }
        var tableFocused = (s.focus && (s.focus === 'table' || s.focus.indexOf('table.col.') === 0)) ? ' wf-card-focused' : '';
        html += '<div class="wf-card' + tableFocused + '"><div class="wf-card-head">Table' + tableFocusBtn + '</div>';
        html += _wfRenderTableReadOnly(s.table);
        html += '</div>';
    }

    /* ── Focus zone ── */
    html += _wfRenderFocusZone(s, state, classified, fieldCategory);

    /* ── Action bar (always visible) ── */
    if (classified.actionBar.length) {
        html += '<div class="wf-card"><div class="wf-card-head">Actions</div>';
        html += '<div class="wf-action-bar">';
        for (var i = 0; i < classified.actionBar.length; i++) {
            var a = classified.actionBar[i], cls = 'wf-aff-action-btn';
            var aLabel = a.label || a.url.split('/').pop().replace(/_/g, ' ');
            if (/Proceed|Submit|Complete/i.test(aLabel)) cls += ' wf-aff-action-primary';
            else if (/go.back/i.test(aLabel)) cls += ' wf-aff-action-nav';
            var tooltip = a.method + ' ' + a.url + (a.body !== undefined ? ' ' + JSON.stringify(a.body) : '');
            html += '<button class="' + cls + '" data-aff-url="' + wfEsc(a.url) + '" data-aff-body="' + wfEsc(JSON.stringify(a.body || {})) + '" title="' + wfEsc(tooltip) + '">' + wfEsc(aLabel) + '</button>';
        }
        html += '</div></div>';
    }

    container.innerHTML = html;
    _wfBindAffordances(container);
    requestAnimationFrame(function() { _fcFixLayout(container); });
}

/* ── Post-render layout correction ── */
function _fcFixLayout(container) {
    var graph = container.querySelector('.fc-graph'); if (!graph) return;
    var layoutB64 = graph.getAttribute('data-layout'); if (!layoutB64) return;
    var layoutData; try { layoutData = JSON.parse(atob(layoutB64)); } catch(e) { return; }
    var items = layoutData.items, edges = layoutData.edges, nodeCount = layoutData.nodeCount;
    var wrapsByIdx = {}; var allWraps = graph.querySelectorAll('.fc-card-wrap');
    for (var w = 0; w < allWraps.length; w++) { var idx = parseInt(allWraps[w].getAttribute('data-idx'), 10); if (!isNaN(idx)) wrapsByIdx[idx] = allWraps[w]; }
    function measureHeight(idx) { var wrap = wrapsByIdx[idx]; if (!wrap) return 60; var card = wrap.querySelector('.fc-card'); return card ? card.offsetHeight : 60; }
    var maxCols = 1;
    for (var ii = 0; ii < items.length; ii++) { if (items[ii].type === 'fork_group' && items[ii].branches.length > maxCols) maxCols = items[ii].branches.length; }
    var colStep = _FC.nodeW + _FC.branchGap;
    var totalW = _FC.marginLeft + maxCols * _FC.nodeW + (maxCols - 1) * _FC.branchGap + _FC.marginRight;
    var singleX = _FC.marginLeft + ((maxCols * _FC.nodeW + (maxCols - 1) * _FC.branchGap) - _FC.nodeW) / 2;
    var slots = new Array(nodeCount); var cy = _FC.marginTop;
    for (var ii = 0; ii < items.length; ii++) {
        var item = items[ii];
        if (item.type === 'node' || item.type === 'router') {
            var ah = measureHeight(item.idx); var wrap = wrapsByIdx[item.idx];
            slots[item.idx] = {x: singleX, y: cy, w: _FC.nodeW, h: ah, cx: singleX + _FC.nodeW / 2};
            if (wrap) { wrap.style.top = cy + 'px'; wrap.style.left = singleX + 'px'; wrap.style.width = _FC.nodeW + 'px'; }
            cy += ah + _FC.rowGap;
        } else if (item.type === 'fork_group') {
            var forkH = measureHeight(item.fork_idx); var forkWrap = wrapsByIdx[item.fork_idx];
            slots[item.fork_idx] = {x: singleX, y: cy, w: _FC.nodeW, h: forkH, cx: singleX + _FC.nodeW / 2};
            if (forkWrap) { forkWrap.style.top = cy + 'px'; forkWrap.style.left = singleX + 'px'; forkWrap.style.width = _FC.nodeW + 'px'; }
            cy += forkH + _FC.rowGap;
            var nBranches = item.branches.length;
            var branchGroupW = nBranches * _FC.nodeW + (nBranches - 1) * _FC.branchGap;
            var branchGroupX = _FC.marginLeft + ((maxCols * _FC.nodeW + (maxCols - 1) * _FC.branchGap) - branchGroupW) / 2;
            var maxRows = 0;
            for (var bi = 0; bi < nBranches; bi++) { if (item.branches[bi].node_indices.length > maxRows) maxRows = item.branches[bi].node_indices.length; }
            for (var ri = 0; ri < maxRows; ri++) {
                var rowH = 0;
                for (var bi = 0; bi < nBranches; bi++) { var branch = item.branches[bi]; if (ri < branch.node_indices.length) { var h = measureHeight(branch.node_indices[ri]); if (h > rowH) rowH = h; } }
                for (var bi = 0; bi < nBranches; bi++) { var branch = item.branches[bi]; if (ri < branch.node_indices.length) { var bIdx = branch.node_indices[ri]; var bx = branchGroupX + bi * colStep; var bh = measureHeight(bIdx); var bWrap = wrapsByIdx[bIdx]; slots[bIdx] = {x: bx, y: cy, w: _FC.nodeW, h: bh, cx: bx + _FC.nodeW / 2}; if (bWrap) { bWrap.style.top = cy + 'px'; bWrap.style.left = bx + 'px'; bWrap.style.width = _FC.nodeW + 'px'; } } }
                cy += rowH + _FC.rowGap;
            }
            var mergeH = measureHeight(item.merge_idx); var mergeWrap = wrapsByIdx[item.merge_idx];
            slots[item.merge_idx] = {x: singleX, y: cy, w: _FC.nodeW, h: mergeH, cx: singleX + _FC.nodeW / 2};
            if (mergeWrap) { mergeWrap.style.top = cy + 'px'; mergeWrap.style.left = singleX + 'px'; mergeWrap.style.width = _FC.nodeW + 'px'; }
            cy += mergeH + _FC.rowGap;
        }
    }
    var totalH = cy - _FC.rowGap + _FC.marginBot;
    graph.style.minHeight = totalH + 'px'; graph.style.width = totalW + 'px';
    var edgeLayer = graph.querySelector('.fc-edge-layer');
    if (edgeLayer) edgeLayer.innerHTML = _fcBuildEdgeSvg(slots, edges, totalW, totalH);
}
/* ======================================================================
   RENDERER: SIMPLE — CSS constants and variant registrations
   ====================================================================== */

/* Shared structural CSS (layout, sizing, typography — no colors) */
var WF_STRUCTURAL_CSS = ''
    + '.wf-header { display:flex; align-items:baseline; justify-content:space-between; padding:1.25rem 1.5rem 0.25rem; }'
    + '.wf-title { font-size:1.4rem; font-weight:600; margin:0; }'
    + '.wf-banner { display:flex; align-items:center; margin:0.75rem 1.5rem; padding:0.75rem 1rem; border-radius:8px; border:1px solid; overflow-x:auto; }'
    + '.wf-step { display:flex; flex-direction:column; align-items:center; gap:0.2rem; flex-shrink:0; }'
    + '.wf-dot { display:inline-flex; align-items:center; justify-content:center; width:22px; height:22px; border-radius:50%; font-size:0.7rem; font-weight:600; }'
    + '.wf-step-label { font-size:0.68rem; font-weight:500; text-align:center; white-space:nowrap; }'
    + '.wf-conn { flex:1; height:2px; margin:0 0.25rem; min-width:12px; align-self:center; margin-bottom:1rem; }'
    + '.wf-parallel { display:flex; flex-direction:column; gap:0.2rem; align-self:center; padding:0.3rem 0.5rem; border:1px dashed; border-radius:6px; }'
    + '.wf-branch { display:flex; align-items:center; gap:0.25rem; font-size:0.6rem; }'
    + '.wf-branch-label { font-weight:700; font-size:0.58rem; min-width:4em; }'
    + '.wf-branch-node { font-size:0.58rem; padding:0.1rem 0.3rem; border-radius:3px; border:1px solid; white-space:nowrap; }'
    + '.wf-branch-sep { font-size:0.5rem; opacity:0.5; }'
    + '.wf-step-targets { display:flex; flex-direction:column; gap:0.1rem; margin-top:0.15rem; }'
    + '.wf-target { font-size:0.55rem; padding:0.05rem 0.25rem; border-radius:2px; border:1px dashed; text-align:center; }'
    + '.wf-banner-flow { overflow:hidden !important; padding:0.25rem !important; display:block !important; }'
    + '.mb-svg { display:block; }'
    + '.wf-section { padding:0.5rem 1.5rem 0; }'
    + '.wf-section-head { font-size:1.1rem; font-weight:600; }'
    + '.wf-desc { padding:0.25rem 1.5rem 0.75rem; font-size:0.9rem; line-height:1.5; white-space:pre-line; }'
    + '.wf-error { margin:0.5rem 1.5rem; padding:0.6rem 0.8rem; background:#fef2f2; border:1px solid #fca5a5; border-radius:6px; color:#991b1b; font-size:0.85rem; font-weight:500; }'
    + '.wf-card { margin:0.5rem 1.5rem; padding:0.75rem; border:1px solid; border-radius:8px; }'
    + '.wf-card-head { font-size:0.75rem; font-weight:600; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:0.5rem; display:flex; align-items:center; }'
    + '.wf-tbl { width:100%; border-collapse:collapse; }'
    + '.wf-tbl td { padding:0.35rem 0.5rem; font-size:0.85rem; vertical-align:top; }'
    + '.wf-key { width:160px; white-space:nowrap; font-weight:500; font-size:0.8rem; }'
    + '.wf-val { word-break:break-word; }'
    + '.wf-null, .wf-empty-arr, .wf-empty-obj { font-style:italic; font-size:0.8rem; }'
    + '.wf-extra-list { margin:0.3rem 0; padding-left:1.2rem; list-style:disc; }'
    + '.wf-extra-list li { margin:0.15rem 0; font-size:0.85rem; }'
    + '.wf-arr { display:flex; flex-direction:column; gap:0.15rem; }'
    + '.wf-arr-item { padding-left:0.5rem; border-left:2px solid; }'
    + '.wf-fields { display:flex; flex-direction:column; gap:0.15rem; }'
    + '.wf-field { padding:0.5rem 0.6rem; }'
    + '.wf-field:last-child { border-bottom:none; }'
    + '.wf-field-label { font-size:0.8rem; font-weight:600; margin-bottom:0.15rem; }'
    + '.wf-field-instruction { font-size:0.75rem; font-style:italic; margin-bottom:0.2rem; line-height:1.3; }'
    + '.wf-field-value { font-size:0.85rem; }'
    + '.wf-field-empty { font-style:italic; font-size:0.8rem; }'
    + '.wf-field-row { display:flex; align-items:center; gap:0.4rem; }'
    + '.wf-field-current { font-size:0.85rem; flex-shrink:0; max-width:50%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }'
    + '.wf-field-options { font-size:0.72rem; font-family:Consolas,Monaco,monospace; margin-top:0.15rem; }'
    /* Focus zone */
    + '.wf-focus-hint { padding:0.5rem 1.5rem; font-size:0.82rem; font-style:italic; }'
    + '.wf-focus-zone { margin:0.5rem 1.5rem; padding:0.75rem; border-radius:8px; border-left:3px solid; }'
    + '.wf-focus-header { display:flex; align-items:center; gap:0.5rem; margin-bottom:0.5rem; flex-wrap:wrap; }'
    + '.wf-focus-breadcrumb { font-size:0.85rem; font-weight:600; flex:1; }'
    + '.wf-focus-nav { display:flex; gap:0.25rem; }'
    + '.wf-focus-nav-btn { font-size:0.72rem; padding:0.2rem 0.5rem; border-radius:3px; border:1px solid; cursor:pointer; background:transparent; font-family:inherit; }'
    + '.wf-focus-close { font-size:0.72rem; padding:0.2rem 0.5rem; border-radius:3px; border:1px solid; cursor:pointer; background:transparent; font-family:inherit; }'
    + '.wf-focus-nested-list { display:flex; gap:0.35rem; flex-wrap:wrap; margin-top:0.5rem; padding-top:0.5rem; border-top:1px solid; }'
    + '.wf-focus-nested-btn { font-size:0.78rem; padding:0.3rem 0.6rem; border-radius:4px; border:1px solid; cursor:pointer; background:transparent; font-family:inherit; }'
    + '.wf-card-focused { border-left:3px solid; }'
    + '.wf-focus-btn { font-size:0.72rem; padding:0.15rem 0.5rem; border-radius:3px; border:1px solid; cursor:pointer; background:transparent; font-family:inherit; margin-left:auto; }'
    + '.wf-aff { margin-bottom:0.4rem; padding:0.5rem 0.6rem; border:1px solid; border-radius:6px; }'
    + '.wf-aff-top { display:flex; align-items:center; gap:0.5rem; }'
    + '.wf-aff-id { display:inline-flex; align-items:center; justify-content:center; width:20px; height:20px; border-radius:50%; font-size:0.7rem; font-weight:600; flex-shrink:0; }'
    + '.wf-aff-label { flex:1; font-size:0.85rem; }'
    + '.wf-aff-method { font-size:0.65rem; font-weight:600; padding:0.15rem 0.4rem; border-radius:3px; }'
    + '.wf-aff-controls { display:flex; gap:0.35rem; margin-top:0.35rem; flex-wrap:wrap; align-items:center; }'
    + '.wf-aff-opt-btn { font-size:0.78rem; padding:0.3rem 0.7rem; border-radius:4px; border:1px solid #ccc; background:#f8f9fb; color:#333; cursor:pointer; transition:background 0.15s; }'
    + '.wf-aff-opt-btn:hover { background:#e8ecf1; }'
    + '.wf-aff-opt-active { background:#2a6bcf !important; color:#fff !important; border-color:#2a6bcf !important; }'
    + '.wf-aff-input { flex:1; font-size:0.82rem; padding:0.3rem 0.5rem; border:1px solid #ccc; border-radius:4px; min-width:120px; font-family:inherit; }'
    + '.wf-aff-input:focus { outline:none; border-color:#2a6bcf; }'
    + '.wf-aff-select { flex:1; font-size:0.82rem; padding:0.3rem 0.5rem; border:1px solid #ccc; border-radius:4px; min-width:120px; font-family:inherit; background:#fff; }'
    + '.wf-aff-select:focus { outline:none; border-color:#2a6bcf; }'
    + '.wf-aff-submit { font-size:0.78rem; padding:0.3rem 0.7rem; border-radius:4px; border:1px solid #2a6bcf; background:#2a6bcf; color:#fff; cursor:pointer; transition:background 0.15s; }'
    + '.wf-aff-submit:hover { background:#1a5bbf; }'
    + '.wf-aff-action-btn { font-size:0.82rem; padding:0.35rem 0.9rem; border-radius:4px; border:1px solid #218838; background:#218838; color:#fff; cursor:pointer; transition:background 0.15s; font-weight:500; }'
    + '.wf-aff-action-btn:hover { background:#196c2e; }'
    + '.wf-aff-primary .wf-aff-action-btn { background:#2a6bcf; border-color:#2a6bcf; }'
    + '.wf-aff-primary .wf-aff-action-btn:hover { background:#1a5bbf; }'
    + '.wf-action-bar { display:flex; gap:0.5rem; flex-wrap:wrap; padding:0.25rem 0; }'
    + '.wf-aff-action-primary { background:#2a6bcf !important; border-color:#2a6bcf !important; }'
    + '.wf-aff-action-primary:hover { background:#1a5bbf !important; }'
    + '.wf-aff-action-nav { background:#6c757d !important; border-color:#6c757d !important; }'
    + '.wf-aff-action-nav:hover { background:#5a6268 !important; }'
    + '.wf-tag-outcome { font-size:0.6em; font-weight:700; vertical-align:super; margin-left:0.5em; letter-spacing:0.05em; }'
    + '.wf-tag-new { font-size:0.6em; font-weight:700; vertical-align:super; margin-left:0.5em; letter-spacing:0.05em; }'
    + '.wf-tag-modified { font-size:0.6em; font-weight:700; vertical-align:super; margin-left:0.5em; letter-spacing:0.05em; }'
    + '.wf-table-summary { font-size:0.78rem; margin-bottom:0.5rem; font-style:italic; }'
    + '.wf-table-wrap { overflow-x:auto; }'
    + '.wf-table { width:100%; border-collapse:collapse; font-size:0.82rem; }'
    + '.wf-table th, .wf-table td { padding:0.4rem 0.6rem; border:1px solid; text-align:left; vertical-align:top; }'
    + '.wf-table-rownum { width:40px; text-align:center; font-size:0.75rem; font-weight:600; }'
    + '.wf-table-colname { font-weight:600; font-size:0.82rem; }'
    + '.wf-table-coltype { font-size:0.68rem; font-weight:400; }'
    + '.wf-table-empty { font-style:italic; font-size:0.8rem; text-align:center; padding:0.75rem; }'
    + '.wf-table-props { display:flex; gap:1rem; margin-top:0.5rem; font-size:0.72rem; }'
    + '.wf-table-prop { font-family:Consolas,Monaco,monospace; }'
    + '.wf-table-prop-row { display:flex; align-items:center; gap:0.4rem; padding:0.15rem 0; }'
    + '.wf-table-prop-label { font-size:0.78rem; font-weight:500; }'
    + '.wf-table-colmeta { font-size:0.68rem; word-break:break-all; max-width:200px; overflow:hidden; }'
    /* Blueprint renderer — workflow definition visualization */
    + '.bp-wrap { margin:0.5rem 1.5rem; }'
    + '.bp-header { padding:0.75rem 0; border-bottom:2px solid; margin-bottom:0.75rem; }'
    + '.bp-title { font-size:1.15rem; font-weight:700; }'
    + '.bp-id { display:inline-block; font-size:0.7rem; font-family:Consolas,Monaco,monospace; padding:0.15rem 0.5rem; border:1px solid; border-radius:3px; margin-top:0.25rem; }'
    + '.bp-desc { font-size:0.82rem; margin-top:0.3rem; line-height:1.4; }'
    + '.bp-lifecycle { display:flex; align-items:center; margin:0.75rem 0; padding:0.6rem 0.75rem; border-radius:8px; border:1px solid; overflow-x:auto; }'
    + '.bp-lc-step { display:flex; flex-direction:column; align-items:center; gap:0.15rem; flex-shrink:0; }'
    + '.bp-lc-dot { display:inline-flex; align-items:center; justify-content:center; width:20px; height:20px; border-radius:50%; font-size:0.65rem; font-weight:600; }'
    + '.bp-lc-label { font-size:0.65rem; font-weight:500; white-space:nowrap; }'
    + '.bp-lc-conn { flex:1; height:2px; margin:0 0.2rem; min-width:10px; align-self:center; margin-bottom:0.9rem; }'
    + '.bp-empty { font-size:0.82rem; font-style:italic; padding:0.5rem 0; }'
    + '.bp-nodes { display:flex; flex-direction:column; margin-top:0.5rem; }'
    + '.bp-node-conn { display:flex; justify-content:center; padding:0.1rem 0; }'
    + '.bp-arrow { font-size:0.7rem; line-height:1; }'
    + '.bp-node { border:1px solid; border-radius:8px; overflow:hidden; }'
    + '.bp-node-head { display:flex; align-items:center; gap:0.5rem; padding:0.5rem 0.75rem; flex-wrap:wrap; }'
    + '.bp-node-title { font-size:0.95rem; font-weight:700; }'
    + '.bp-node-id { font-size:0.65rem; font-family:Consolas,Monaco,monospace; padding:0.1rem 0.4rem; border:1px solid; border-radius:3px; }'

    + '.bp-node-flag { font-size:0.6rem; padding:0.1rem 0.4rem; border:1px dashed; border-radius:3px; font-family:Consolas,Monaco,monospace; }'
    + '.bp-node-section { padding:0.4rem 0.75rem; border-top:1px solid; }'
    + '.bp-node-section-label { font-size:0.62rem; font-weight:600; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:0.25rem; }'
    + '.bp-node-instr { font-size:0.78rem; line-height:1.4; white-space:pre-line; }'
    + '.bp-node-none { font-size:0.75rem; font-style:italic; }'
    + '.bp-fields-table { width:100%; border-collapse:collapse; font-size:0.78rem; }'
    + '.bp-fields-table th { text-align:left; font-size:0.62rem; text-transform:uppercase; letter-spacing:0.06em; padding:0.2rem 0.4rem; font-weight:500; }'
    + '.bp-fields-table td { padding:0.25rem 0.4rem; vertical-align:top; }'
    + '.bp-field-key { font-family:Consolas,Monaco,monospace; font-weight:600; font-size:0.75rem; }'
    + '.bp-field-detail { font-size:0.72rem; max-width:250px; overflow:hidden; text-overflow:ellipsis; }'
    + '.bp-type { display:inline-block; font-size:0.62rem; font-weight:600; padding:0.1rem 0.4rem; border-radius:10px; text-transform:uppercase; letter-spacing:0.03em; }'
    + '.bp-gate { display:flex; align-items:center; gap:0.4rem; padding:0.3rem 0; flex-wrap:wrap; }'
    + '.bp-gate-icon { font-size:0.7rem; }'
    + '.bp-gate-label { font-size:0.82rem; font-weight:600; }'
    + '.bp-gate-reqs { font-size:0.72rem; }'
    + '.bp-gate-key { font-family:Consolas,Monaco,monospace; font-weight:600; padding:0.05rem 0.3rem; border:1px solid; border-radius:3px; font-size:0.7rem; }'
    + '.bp-nav-item { display:flex; align-items:center; gap:0.4rem; padding:0.15rem 0; font-size:0.78rem; }'
    + '.bp-nav-action { font-size:0.62rem; font-weight:600; padding:0.1rem 0.35rem; border:1px solid; border-radius:3px; font-family:Consolas,Monaco,monospace; }'
    + '.bp-nav-label { }'
    + '.bp-nav-target { font-family:Consolas,Monaco,monospace; font-size:0.72rem; }'
    + '.bp-action-item { display:flex; align-items:center; gap:0.4rem; padding:0.15rem 0; font-size:0.78rem; }'
    + '.bp-action-type { font-size:0.62rem; font-weight:600; padding:0.1rem 0.35rem; border-radius:3px; text-transform:uppercase; }'

    + '.wf-exec-cell { font-size:0.8rem; }'
    + '.wf-exec-pass { font-weight:600; }'
    + '.wf-exec-pending { font-style:italic; }'
    + '.wf-exec-gated { opacity:0.5; }'
    + '.wf-exec-locked { opacity:0.5; }'
    + '.wf-exec-reason { font-size:0.7rem; font-style:italic; margin-top:0.15rem; }'
    + '.wf-row-gated { opacity:0.6; }'
    /* Parametric affordance forms */
    + '.wf-param-form { padding:0.5rem 0.6rem; border-bottom:1px solid #f0f0f0; }'
    + '.wf-param-form:last-child { border-bottom:none; }'
    + '.wf-param-head { font-size:0.82rem; font-weight:600; margin-bottom:0.35rem; }'
    + '.wf-param-row { display:flex; align-items:center; gap:0.4rem; margin-bottom:0.25rem; }'
    + '.wf-param-label { font-size:0.75rem; font-weight:500; min-width:60px; flex-shrink:0; }'
    + '.wf-param-input { flex:1; font-size:0.8rem; padding:0.25rem 0.4rem; border:1px solid #ccc; border-radius:4px; font-family:inherit; min-width:0; }'
    + 'select.wf-param-input { background:#fff; }'
    + '.wf-param-submit { font-size:0.78rem; padding:0.3rem 0.7rem; border-radius:4px; border:1px solid #2a6bcf; background:#2a6bcf; color:#fff; cursor:pointer; margin-top:0.25rem; }'
    + '.wf-param-submit:hover { background:#1a5bbf; }'
    /* Inline execution cell controls */
    + '.wf-exec-control { display:flex; gap:0.25rem; margin-top:0.25rem; align-items:center; }'
    + '.wf-exec-input { width:100%; font-size:0.78rem; padding:0.2rem 0.35rem; border:1px solid #ccc; border-radius:3px; font-family:inherit; box-sizing:border-box; }'
    + '.wf-exec-select { font-size:0.78rem; padding:0.2rem 0.35rem; border:1px solid #ccc; border-radius:3px; font-family:inherit; background:#fff; flex:1; min-width:0; }'
    + '.wf-exec-submit { font-size:0.72rem; padding:0.2rem 0.5rem; border-radius:3px; border:1px solid #2a6bcf; background:#2a6bcf; color:#fff; cursor:pointer; white-space:nowrap; flex-shrink:0; }'
    + '.wf-exec-submit:hover { background:#1a5bbf; }'
    + '.wf-exec-btn { font-size:0.72rem; padding:0.2rem 0.5rem; border-radius:3px; border:1px solid #218838; background:#218838; color:#fff; cursor:pointer; white-space:nowrap; margin-top:0.2rem; }'
    + '.wf-exec-btn:hover { background:#196c2e; }'
    + '.wf-exec-btn-sec { background:#6c757d; border-color:#6c757d; }'
    + '.wf-exec-btn-sec:hover { background:#5a6268; }'
    + '.wf-exec-display { margin-bottom:0.15rem; }'
    /* Schematic hybrid renderer — CSS injected by schematic.js on first use */
    ;

/* ── CSS ── */
var FC_CSS = ''
    /* Wrapper */
    + '.fc-wrap { margin:0.5rem 1rem; }'
    + '.fc-hdr { padding:0.4rem 0; border-bottom:2px solid; margin-bottom:0.5rem; }'
    + '.fc-hdr-title { font-size:1.05rem; font-weight:700; }'
    + '.fc-hdr-id { font-size:0.7rem; opacity:0.6; vertical-align:middle; }'
    + '.fc-hdr-desc { font-size:0.78rem; margin-top:0.15rem; opacity:0.6; }'
    + '.fc-empty { text-align:center; padding:2rem; opacity:0.6; font-style:italic; }'
    /* Graph container */
    + '.fc-graph { overflow:visible; }'
    + '.fc-edge-layer { position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:none; z-index:0; }'
    + '.fc-edge-svg { display:block; }'
    + '.fc-card-wrap { z-index:1; }'
    + '.fc-card-current .fc-card { border-color:#2a6bcf !important; box-shadow:0 0 0 2px rgba(42,107,207,0.2); }'
    + '.fc-card-done .fc-card { border-color:#4caf50 !important; background:#f6faf6; }'
    + '.sch-node-current .fc-card { border-color:#2a6bcf !important; box-shadow:0 0 0 2px rgba(42,107,207,0.2); }'
    + '.sch-node-completed .fc-card { border-color:#4caf50 !important; background:#f6faf6; }'
    /* Card */
    + '.fc-card { border:1px solid; border-radius:8px; overflow:hidden; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:#fff; }'
    + '.fc-card-head { display:flex; align-items:center; gap:0.4rem; padding:0.45rem 0.65rem; flex-wrap:wrap; }'
    + '.fc-num { display:inline-flex; align-items:center; justify-content:center; width:22px; height:22px; border-radius:50%; font-size:0.7rem; font-weight:700; flex-shrink:0; }'
    + '.fc-card-title { font-size:0.88rem; font-weight:700; }'
    + '.fc-card-id { font-size:0.62rem; opacity:0.6; font-family:Consolas,Monaco,monospace; }'
    + '.fc-eye { font-size:0.75rem; opacity:0.6; }'
    /* Instruction */
    + '.fc-instr { padding:0.2rem 0.65rem 0.35rem; font-size:0.72rem; line-height:1.35; opacity:0.6; white-space:pre-line; }'
    /* Fields */
    + '.fc-fields { padding:0.25rem 0.65rem; }'
    + '.fc-field { display:flex; align-items:center; gap:0.35rem; padding:0.2rem 0; font-size:0.78rem; }'
    + '.fc-field-dot { display:inline-flex; align-items:center; justify-content:center; width:18px; height:18px; border-radius:50%; font-size:0.6rem; font-weight:700; flex-shrink:0; border:1.5px solid; }'
    + '.fc-field-name { font-weight:600; }'
    + '.fc-field-key { font-size:0.62rem; margin-left:auto; }'
    + '.fc-field-opts { margin-left:2.2rem; padding:0.1rem 0; }'
    + '.fc-field-opt { font-size:0.62rem; font-family:Consolas,Monaco,monospace; padding:0.05rem 0; }'
    /* Gate */
    + '.fc-gate { display:flex; align-items:center; gap:0.3rem; padding:0.3rem 0.65rem; border-top:1px dashed; flex-wrap:wrap; font-size:0.78rem; }'
    + '.fc-gate-lock { font-size:0.8rem; }'
    + '.fc-gate-lbl { font-weight:600; }'
    + '.fc-gate-reqs { font-size:0.68rem; font-family:Consolas,monospace; margin-left:auto; }'
    /* Actions */
    + '.fc-acts { display:flex; gap:0.3rem; padding:0.3rem 0.65rem; border-top:1px solid; flex-wrap:wrap; }'
    + '.fc-act { font-size:0.72rem; font-weight:600; padding:0.15rem 0.5rem; border-radius:4px; }'
    /* Badge (router/fork) */
    + '.fc-badge { font-size:0.58rem; font-weight:700; padding:0.1rem 0.35rem; border-radius:3px; text-transform:uppercase; letter-spacing:0.04em; }'
    /* Router routes */
    + '.fc-routes { padding:0.25rem 0.65rem; }'
    + '.fc-route { display:flex; align-items:center; gap:0.3rem; padding:0.12rem 0; font-size:0.72rem; }'
    + '.fc-route-arrow { font-weight:700; }'
    + '.fc-route-cond { font-style:italic; }'
    + '.fc-route-target { font-size:0.62rem; margin-left:auto; }'
    /* Fork info */
    + '.fc-fork-info { padding:0.3rem 0.65rem; border-top:1px dashed; }'
    + '.fc-fork-label { font-size:0.78rem; font-weight:600; }'
    + '.fc-fork-merge { font-size:0.68rem; margin-left:0.8rem; }'
    + '.fc-fork-branches { display:flex; gap:0.4rem; margin-top:0.2rem; flex-wrap:wrap; }'
    + '.fc-fork-branch { font-size:0.65rem; padding:0.1rem 0.4rem; border-radius:3px; border:1px solid; }'
    /* Edge SVG */
    + '.fc-ef { fill:none; stroke-width:2; }'                             /* forward: solid */
    + '.fc-eb { fill:none; stroke-width:1.5; stroke-dasharray:3 3; }'   /* back: dotted */
    + '.fc-eg { fill:none; stroke-width:1.5; stroke-dasharray:3 3; }'   /* goto: dotted */
    + '.fc-efk { fill:none; stroke-width:2; }'                           /* fork: solid */
    + '.fc-emg { fill:none; stroke-width:2; }'                           /* merge: solid */
    + '.fc-ert { fill:none; stroke-width:1.5; stroke-dasharray:6 4; }'  /* router: dashed */
    + '.fc-el { font-size:11px; font-family:-apple-system,sans-serif; }'
    ;

/* ── Light tokens ── */
var FC_LIGHT = ''
    + '.fc-hdr { border-bottom-color:#2a6bcf; } .fc-hdr-title { color:#1a1a2e; }'
    + '.fc-card { background:#fff; border-color:#dde1e6; box-shadow:0 1px 4px rgba(0,0,0,0.06); }'
    + '.fc-card-head { background:linear-gradient(135deg,#e8ecf1,#dde2e8); }'
    + '.fc-num { background:#2a6bcf; color:#fff; }'
    + '.fc-card-title { color:#1a1a2e; }'
    + '.fc-ft-text { background:#e3f2fd; border-color:#1565c0; color:#1565c0; }'
    + '.fc-ft-bool { background:#fff3e0; border-color:#e65100; color:#e65100; }'
    + '.fc-ft-sel { background:#f3e5f5; border-color:#7b1fa2; color:#7b1fa2; }'
    + '.fc-gate { border-top-color:#c8e6c9; }'
    + '.fc-gate-lbl { color:#2e7d32; }'
    + '.fc-gate-reqs { color:#1565c0; }'
    + '.fc-acts { border-top-color:#f0f0f0; }'
    + '.fc-act-submit { background:#e8f5e9; color:#2e7d32; }'
    + '.fc-act-restart { background:#fff3e0; color:#e65100; }'
    + '.fc-badge-router { background:#fff3e0; color:#e65100; }'
    + '.fc-badge-fork { background:#e8f5e9; color:#2e7d32; }'
    + '.fc-card-router .fc-card-head { background:linear-gradient(135deg,#fff3e0,#ffe0b2); }'
    + '.fc-card-fork .fc-card-head { background:linear-gradient(135deg,#e8f5e9,#c8e6c9); }'
    + '.fc-route-arrow { color:#e65100; }'
    + '.fc-route-cond { color:#795548; }'
    + '.fc-route-target { color:#1565c0; }'
    + '.fc-fork-info { border-top-color:#c8e6c9; }'
    + '.fc-fork-label { color:#2e7d32; }'
    + '.fc-fork-merge { color:#666; }'
    + '.fc-fork-branch { background:#e8f5e9; border-color:#a5d6a7; color:#2e7d32; }'
    + '.fc-ef { stroke:#4caf50; } .fc-mf { fill:#4caf50; }'
    + '.fc-eb { stroke:#2a6bcf; } .fc-mb { fill:#2a6bcf; }'
    + '.fc-eg { stroke:#7b1fa2; } .fc-mg { fill:#7b1fa2; }'
    + '.fc-efk { stroke:#4caf50; } .fc-mk { fill:#4caf50; }'
    + '.fc-emg { stroke:#4caf50; }'
    + '.fc-ert { stroke:#e65100; } .fc-mr { fill:#e65100; }'
    + '.fc-el-b { fill:#2a6bcf; } .fc-el-g { fill:#7b1fa2; }'
    + '.fc-el-fk { fill:#4caf50; } .fc-el-rt { fill:#e65100; }'
    ;

function _scopeFC(sel, css) { return css.replace(/\.fc-/g, sel + ' .fc-'); }

(function() {
    var container;
    registerRenderer({
        id: 'light', label: 'Human',
        init: function(c) {
            c.style.cssText = 'overflow-y:auto;padding:0;';
            var style = document.createElement('style');
            style.textContent = WF_STRUCTURAL_CSS + FC_CSS
                + _scopeFC('#rc-light', FC_LIGHT)
                + '#rc-light { background:#f5f5f5; color:#333; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }'
                + '#rc-light .wf-title { color:#1a1a2e; } #rc-light .wf-banner { background:#f8f9fb; border-color:#e8e8e8; } #rc-light .wf-dot { background:#dde1e6; color:#888; } #rc-light .wf-step-label { color:#888; } #rc-light .wf-step-active .wf-dot { background:#2a6bcf; color:#fff; } #rc-light .wf-step-active .wf-step-label { color:#1a1a2e; font-weight:600; } #rc-light .wf-step-done .wf-dot { background:#4caf50; color:#fff; } #rc-light .wf-step-done .wf-step-label { color:#555; } #rc-light .wf-conn { background:#dde1e6; } #rc-light .wf-conn-active { background:#4caf50; } #rc-light .wf-section-head { color:#1a1a2e; } #rc-light .wf-desc { color:#666; } #rc-light .wf-card { background:#fff; border-color:#e8e8e8; } #rc-light .wf-card-head { color:#7f8fa6; } #rc-light .wf-tbl td { border-bottom:1px solid #f0f0f0; } #rc-light .wf-key { color:#7f8fa6; } #rc-light .wf-val { color:#333; } #rc-light .wf-null, #rc-light .wf-empty-arr, #rc-light .wf-empty-obj { color:#bbb; } #rc-light .wf-bool, #rc-light .wf-num { color:#2a6bcf; } #rc-light .wf-str { color:#333; } #rc-light .wf-arr-item { border-left-color:#e8e8e8; } #rc-light .wf-field { border-bottom:1px solid #f0f0f0; } #rc-light .wf-field-label { color:#555; } #rc-light .wf-field-instruction { color:#999; } #rc-light .wf-field-value { color:#333; } #rc-light .wf-field-empty { color:#bbb; } #rc-light .wf-field-current { color:#333; } #rc-light .wf-field-options { color:#7f8fa6; } #rc-light .wf-aff { background:#f8f9fb; border-color:#e8e8e8; } #rc-light .wf-aff-id { background:#dde1e6; color:#555; } #rc-light .wf-aff-label { color:#333; } #rc-light .wf-aff-method { color:#7f8fa6; background:#eef1f5; } #rc-light .wf-aff-detail { color:#999; } #rc-light .wf-aff-options { color:#7f8fa6; } #rc-light .wf-aff-primary { border-color:#2a6bcf; background:#f0f5ff; } #rc-light .wf-aff-primary .wf-aff-label { color:#2a6bcf; font-weight:600; } #rc-light .wf-aff-primary .wf-aff-id { background:#2a6bcf; color:#fff; } #rc-light .wf-aff-nav { border-color:#dde1e6; background:#fafafa; } #rc-light .wf-aff-nav .wf-aff-label { color:#888; } #rc-light .wf-aff-selected { border-color:#4caf50; background:#f0fff0; } #rc-light .wf-aff-selected .wf-aff-label { color:#2e7d32; } #rc-light .wf-aff-selected .wf-aff-id { background:#4caf50; color:#fff; } #rc-light .wf-fb-outcome { border-left:3px solid #2a6bcf; background:#f0f5ff; } #rc-light .wf-fb-new { border-left:3px solid #4caf50; background:#f0faf0; } #rc-light .wf-fb-modified { border-left:3px solid #e6a817; background:#fdf8ed; } #rc-light .wf-aff-new { border-left:3px solid #4caf50; background:#f0faf0; } #rc-light .wf-aff-modified { border-left:3px solid #e6a817; background:#fdf8ed; } #rc-light .wf-tag-outcome { color:#2a6bcf; } #rc-light .wf-tag-new { color:#4caf50; } #rc-light .wf-tag-modified { color:#e6a817; } #rc-light .wf-table th { background:#f4f6f9; border-color:#e8e8e8; } #rc-light .wf-table td { border-color:#e8e8e8; } #rc-light .wf-table-rownum { color:#aaa; background:#fafbfc; } #rc-light .wf-table-coltype { color:#7f8fa6; } #rc-light .wf-table-empty { color:#bbb; } #rc-light .wf-table-summary { color:#7f8fa6; } #rc-light .wf-table-prop { color:#7f8fa6; } #rc-light .wf-table-prop-label { color:#555; } #rc-light .wf-exec-pass { color:#2e7d32; } #rc-light .wf-exec-pending { color:#b0b0b0; } #rc-light [data-completed="true"] { background:#e8f5e9; } #rc-light .wf-exec-reason { color:#999; } #rc-light .wf-parallel { border-color:#c8e6c9; background:#f8fdf8; } #rc-light .wf-branch-label { color:#2e7d32; } #rc-light .wf-branch-node { background:#fff; border-color:#dde1e6; color:#555; } #rc-light .wf-branch-done { background:#e8f5e9; border-color:#4caf50; color:#2e7d32; } #rc-light .wf-branch-active { background:#e3f2fd; border-color:#2a6bcf; color:#1a1a2e; font-weight:600; } #rc-light .wf-dot-router { background:#e65100; } #rc-light .wf-dot-fork { background:#2e7d32; } #rc-light .wf-target { border-color:#e65100; color:#795548; } #rc-light .wf-target-done { background:#fff3e0; color:#e65100; } #rc-light .wf-target-active { background:#fff3e0; border-color:#e65100; color:#e65100; font-weight:600; } #rc-light .mb-node { background:#fff; border-color:#dde1e6; color:#555; } #rc-light .mb-current { background:#e3f2fd; border-color:#2a6bcf; color:#1a1a2e; font-weight:700; } #rc-light .mb-done { background:#e8f5e9; border-color:#4caf50; color:#2e7d32; } #rc-light .mb-router { border-color:#e65100; } #rc-light .mb-router.mb-done { border-color:#4caf50; } #rc-light .mb-fork { border-color:#2e7d32; } #rc-light .mb-fork.mb-done { border-color:#4caf50; } #rc-light .wf-param-form { border-bottom-color:#f0f0f0; } #rc-light .wf-param-head { color:#333; } #rc-light .wf-param-label { color:#555; } #rc-light .wf-param-input { border-color:#ccc; color:#333; } #rc-light .wf-param-input:focus { outline:none; border-color:#2a6bcf; } #rc-light .wf-exec-input { border-color:#ccc; color:#333; } #rc-light .wf-exec-input:focus { outline:none; border-color:#2a6bcf; } #rc-light .wf-exec-select { border-color:#ccc; color:#333; } #rc-light .wf-exec-select:focus { outline:none; border-color:#2a6bcf; } #rc-light .wf-exec-display { color:#333; } #rc-light .wf-focus-hint { color:#999; } #rc-light .wf-focus-zone { background:#fef5f5; border-left-color:#e53935; } #rc-light .wf-focus-breadcrumb { color:#1a1a2e; } #rc-light .wf-focus-nav-btn { color:#2a6bcf; border-color:#ccd5e0; } #rc-light .wf-focus-nav-btn:hover { background:#e8ecf1; } #rc-light .wf-focus-close { color:#999; border-color:#ccd5e0; } #rc-light .wf-focus-close:hover { color:#333; background:#e8ecf1; } #rc-light .wf-focus-nested-list { border-top-color:#ccd5e0; } #rc-light .wf-focus-nested-btn { color:#2a6bcf; border-color:#ccd5e0; } #rc-light .wf-focus-nested-btn:hover { background:#e8ecf1; } #rc-light .wf-card-focused { border-left-color:#e53935; } #rc-light .wf-focus-btn { color:#2a6bcf; border-color:#ccd5e0; } #rc-light .wf-focus-btn:hover { background:#e8ecf1; }'
                ; document.head.appendChild(style); container = c;
        },
        update: function(state, msg, feedback) { _humanPage(container, state, msg, feedback, false); },
        activate: function() {}, deactivate: function() {}
    });
})();
