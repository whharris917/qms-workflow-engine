/* ======================================================================
   RENDERER: EXPERIMENTAL A — two-column blueprint layout
   ====================================================================== */
(function() {
    var container;

    function expARenderPage(c, state, msg, feedback) {
        if (!c || !state) return;

        var fieldCategory = {};
        var affCategory = {};
        if (feedback) {
            var out = feedback.outcome || {};
            var eff = feedback.effects || {};
            for (var k in out) fieldCategory[k] = 'outcome';
            for (var k in (eff.new_fields || {})) fieldCategory[k] = 'new';
            for (var k in (eff.modified_fields || {})) fieldCategory[k] = 'modified';
            (eff.new_affordances || []).forEach(function(a){ affCategory[a.label] = 'new'; });
            (eff.modified_affordances || []).forEach(function(a){ affCategory[a.label] = 'modified'; });
        }

        var s = state.state || {};
        var html = '';

        /* ── Top bar: workflow title + node as breadcrumb ── */
        html += '<div class="ex-topbar">';
        html += '<span class="ex-crumb">' + wfEsc(s.workflow || 'Workflow') + '</span>';
        html += '<span class="ex-sep">&rsaquo;</span>';
        html += '<span class="ex-crumb ex-crumb-active">' + wfEsc(s.node_title || s.node) + '</span>';
        html += '</div>';

        /* ── Progress breadcrumb ── */
        var defnNodes = (s.definition || s.banner_definition || {}).nodes || [];
        var current = s.node || '';
        var completed = s.completed_nodes || [];
        if (defnNodes.length) {
            html += '<div class="ex-progress">';
            for (var i = 0; i < defnNodes.length; i++) {
                var item = defnNodes[i];
                var isCurrent = item.id === current;
                var isDone = completed.indexOf(item.id) !== -1;
                if (i > 0) html += '<span class="ex-arrow">&rarr;</span>';
                var cls = 'ex-phase';
                if (isCurrent) cls += ' ex-phase-current';
                else if (isDone) cls += ' ex-phase-done';
                html += '<span class="' + cls + '">' + wfEsc(item.title) + '</span>';
            }
            html += '</div>';
        }

        /* ── Instructions ── */
        if (state.instructions) {
            html += '<div class="ex-instructions">' + wfEsc(state.instructions) + '</div>';
        }

        html += wfRenderStateProps(state);

        /* ── Table (if present) ── */
        if (s.execution_table) {
            html += wfRenderExecTable(s.execution_table);
        } else if (s.table) {
            html += wfRenderTable(s.table);
        }

        /* ── Two-column body ── */
        html += '<div class="ex-columns">';

        /* Left column: fields */
        html += '<div class="ex-col ex-col-fields">';
        html += '<div class="ex-col-head">state.fields</div>';
        if (s.fields) {
            var fkeys = Object.keys(s.fields);
            if (fkeys.length) {
                html += '<table class="ex-ftable"><thead><tr>';
                html += '<th>Field</th><th>Value</th><th>Options</th><th>Status</th>';
                html += '</tr></thead><tbody>';
                for (var i = 0; i < fkeys.length; i++) {
                    var k = fkeys[i];
                    var f = s.fields[k];
                    var cat = fieldCategory[k] || null;
                    var rowCls = cat ? ' ex-row-' + cat : '';
                    html += '<tr class="' + rowCls + '">';
                    html += '<td class="ex-fname">' + wfEsc(k) + '</td>';
                    if (f && typeof f === 'object' && 'value' in f) {
                        html += '<td class="ex-fval">';
                        if (f.value == null) html += '<span class="ex-unset">—</span>';
                        else html += wfEsc(f.value);
                        if (f.instruction) html += '<div class="ex-finstr">' + wfEsc(f.instruction) + '</div>';
                        html += '</td>';
                        html += '<td class="ex-fopts">';
                        if (f.options) html += wfEsc(f.options.join(', '));
                        html += '</td>';
                    } else {
                        html += '<td class="ex-fval">' + wfRenderValue(f) + '</td>';
                        html += '<td class="ex-fopts"></td>';
                    }
                    var tagMap = {outcome:'SET', 'new':'NEW', modified:'CHG'};
                    html += '<td class="ex-fstatus">';
                    if (cat) html += '<span class="ex-tag ex-tag-' + cat + '">' + tagMap[cat] + '</span>';
                    html += '</td>';
                    html += '</tr>';
                }
                html += '</tbody></table>';
            } else {
                html += '<span class="ex-empty">(empty)</span>';
            }
        } else {
            html += '<span class="ex-empty">(no fields)</span>';
        }
        html += '</div>';

        /* Right column: affordances */
        html += '<div class="ex-col ex-col-affs">';
        html += '<div class="ex-col-head">affordances</div>';
        if (state.affordances && state.affordances.length) {
            html += '<div class="ex-aff-grid">';
            for (var i = 0; i < state.affordances.length; i++) {
                var a = state.affordances[i];
                var cls = 'ex-aff';
                if (/Proceed|Submit/.test(a.label)) cls += ' ex-aff-primary';
                else if (/Go back/.test(a.label)) cls += ' ex-aff-nav';
                else if (/\[Selected\]/.test(a.label)) cls += ' ex-aff-selected';
                if (affCategory[a.label]) cls += ' ex-aff-fb-' + affCategory[a.label];
                html += '<div class="' + cls + '">';
                html += '<div class="ex-aff-head">';
                html += '<span class="ex-aff-idx">' + a.id + '</span>';
                html += '<span class="ex-aff-lbl">' + wfEsc(a.label);
                var ac = affCategory[a.label];
                if (ac === 'new') html += ' <span class="ex-tag ex-tag-new">NEW</span>';
                else if (ac === 'modified') html += ' <span class="ex-tag ex-tag-modified">CHG</span>';
                html += '</span>';
                html += '</div>';
                html += '<div class="ex-aff-meta">';
                html += '<span class="ex-aff-verb">' + wfEsc(a.method) + '</span> ';
                html += '<span class="ex-aff-url">' + wfEsc(a.url) + '</span>';
                html += '</div>';
                html += '<div class="ex-aff-body">' + wfEsc(JSON.stringify(a.body)) + '</div>';
                var pStr = wfRenderParams(a);
                if (pStr) {
                    html += '<div class="ex-aff-opts">' + wfEsc(pStr) + '</div>';
                }
                html += '</div>';
            }
            html += '</div>';
        } else {
            html += '<span class="ex-empty">(none)</span>';
        }
        html += '</div>';

        html += '</div>'; /* close ex-columns */

        c.innerHTML = html;
    }

    var EXP_CSS = ''
        /* Container */
        + '#rc-exp-a { background:#0b1622; color:#b0c4d8; font-family:Consolas,Monaco,"Courier New",monospace; overflow-y:auto; padding:0; }'

        /* Top bar */
        + '#rc-exp-a .ex-topbar { display:flex; align-items:center; gap:0.4rem; padding:0.8rem 1.2rem 0.3rem; border-bottom:1px dashed #1e3a5f; }'
        + '#rc-exp-a .ex-crumb { font-size:0.9rem; color:#4a7a9b; }'
        + '#rc-exp-a .ex-crumb-active { color:#7fdbff; font-weight:700; }'
        + '#rc-exp-a .ex-sep { color:#2a4a6b; font-size:1rem; }'

        /* Progress breadcrumb */
        + '#rc-exp-a .ex-progress { display:flex; align-items:center; gap:0.3rem; padding:0.5rem 1.2rem; flex-wrap:wrap; }'
        + '#rc-exp-a .ex-phase { font-size:0.72rem; padding:0.2rem 0.5rem; border:1px solid #1e3a5f; border-radius:2px; color:#4a7a9b; background:#0d1e30; }'
        + '#rc-exp-a .ex-phase-current { border-color:#7fdbff; color:#7fdbff; background:#0d2a40; box-shadow:0 0 6px rgba(127,219,255,0.15); }'
        + '#rc-exp-a .ex-phase-done { border-color:#2ecc71; color:#2ecc71; background:#0d2a1a; }'
        + '#rc-exp-a .ex-arrow { color:#1e3a5f; font-size:0.8rem; }'

        /* Instructions */
        + '#rc-exp-a .ex-instructions { padding:0.4rem 1.2rem 0.6rem; font-size:0.82rem; color:#6a8fa8; line-height:1.5; border-bottom:1px dashed #1e3a5f; font-style:italic; white-space:pre-line; }'

        /* Two-column layout */
        + '#rc-exp-a .ex-columns { display:flex; gap:0; min-height:0; }'
        + '#rc-exp-a .ex-col { flex:1; padding:0.6rem 0.8rem; }'
        + '#rc-exp-a .ex-col-fields { border-right:1px dashed #1e3a5f; }'
        + '#rc-exp-a .ex-col-head { font-size:0.68rem; text-transform:uppercase; letter-spacing:0.1em; color:#3a6a8f; margin-bottom:0.5rem; padding-bottom:0.25rem; border-bottom:1px solid #1e3a5f; }'

        /* Fields table */
        + '#rc-exp-a .ex-ftable { width:100%; border-collapse:collapse; font-size:0.78rem; }'
        + '#rc-exp-a .ex-ftable th { text-align:left; font-size:0.65rem; text-transform:uppercase; letter-spacing:0.08em; color:#3a6a8f; padding:0.3rem 0.4rem; border-bottom:1px solid #1e3a5f; font-weight:500; }'
        + '#rc-exp-a .ex-ftable td { padding:0.35rem 0.4rem; border-bottom:1px solid #0f2236; vertical-align:top; }'
        + '#rc-exp-a .ex-fname { color:#7fdbff; white-space:nowrap; font-weight:600; width:120px; }'
        + '#rc-exp-a .ex-fval { color:#b0c4d8; word-break:break-word; }'
        + '#rc-exp-a .ex-unset { color:#2a4a6b; }'
        + '#rc-exp-a .ex-finstr { font-size:0.7rem; color:#4a6a80; font-style:italic; margin-top:0.15rem; }'
        + '#rc-exp-a .ex-fopts { color:#4a6a80; font-size:0.72rem; }'
        + '#rc-exp-a .ex-fstatus { width:40px; text-align:center; }'
        + '#rc-exp-a .ex-empty { color:#2a4a6b; font-style:italic; font-size:0.8rem; }'

        /* Feedback row highlights */
        + '#rc-exp-a .ex-row-outcome { background:rgba(127,219,255,0.06); }'
        + '#rc-exp-a .ex-row-new { background:rgba(46,204,113,0.06); }'
        + '#rc-exp-a .ex-row-modified { background:rgba(230,168,23,0.06); }'

        /* Tags */
        + '#rc-exp-a .ex-tag { font-size:0.6rem; font-weight:700; letter-spacing:0.06em; padding:0.1rem 0.3rem; border-radius:2px; }'
        + '#rc-exp-a .ex-tag-outcome { color:#7fdbff; background:rgba(127,219,255,0.12); }'
        + '#rc-exp-a .ex-tag-new { color:#2ecc71; background:rgba(46,204,113,0.12); }'
        + '#rc-exp-a .ex-tag-modified { color:#e6a817; background:rgba(230,168,23,0.12); }'

        /* Affordance grid */
        + '#rc-exp-a .ex-aff-grid { display:grid; grid-template-columns:1fr; gap:0.4rem; }'
        + '#rc-exp-a .ex-aff { border:1px solid #1e3a5f; border-radius:3px; padding:0.4rem 0.5rem; background:#0d1e30; }'
        + '#rc-exp-a .ex-aff-head { display:flex; align-items:center; gap:0.4rem; }'
        + '#rc-exp-a .ex-aff-idx { display:inline-flex; align-items:center; justify-content:center; width:18px; height:18px; border-radius:2px; font-size:0.65rem; font-weight:700; background:#1e3a5f; color:#7fdbff; flex-shrink:0; }'
        + '#rc-exp-a .ex-aff-lbl { font-size:0.8rem; color:#b0c4d8; }'
        + '#rc-exp-a .ex-aff-meta { font-size:0.68rem; margin-top:0.2rem; }'
        + '#rc-exp-a .ex-aff-verb { color:#3a6a8f; font-weight:600; }'
        + '#rc-exp-a .ex-aff-url { color:#4a7a9b; }'
        + '#rc-exp-a .ex-aff-body { font-size:0.68rem; color:#3a5a70; margin-top:0.1rem; word-break:break-all; }'
        + '#rc-exp-a .ex-aff-opts { font-size:0.68rem; color:#3a5a70; margin-top:0.1rem; }'

        /* Affordance variants */
        + '#rc-exp-a .ex-aff-primary { border-color:#7fdbff; background:#0d2a40; box-shadow:0 0 8px rgba(127,219,255,0.08); }'
        + '#rc-exp-a .ex-aff-primary .ex-aff-lbl { color:#7fdbff; font-weight:700; }'
        + '#rc-exp-a .ex-aff-primary .ex-aff-idx { background:#7fdbff; color:#0b1622; }'
        + '#rc-exp-a .ex-aff-nav { border-color:#1e3a5f; background:#0b1622; border-style:dashed; }'
        + '#rc-exp-a .ex-aff-nav .ex-aff-lbl { color:#4a6a80; }'
        + '#rc-exp-a .ex-aff-selected { border-color:#2ecc71; background:#0d2a1a; }'
        + '#rc-exp-a .ex-aff-selected .ex-aff-lbl { color:#2ecc71; }'
        + '#rc-exp-a .ex-aff-selected .ex-aff-idx { background:#2ecc71; color:#0b1622; }'
        + '#rc-exp-a .ex-aff-fb-new { border-left:3px solid #2ecc71; }'
        + '#rc-exp-a .ex-aff-fb-modified { border-left:3px solid #e6a817; }'

        /* Value types (reused from shared wfRenderValue) */
        + '#rc-exp-a .wf-null, #rc-exp-a .wf-empty-arr, #rc-exp-a .wf-empty-obj { color:#2a4a6b; font-style:italic; font-size:0.75rem; }'
        + '#rc-exp-a .wf-bool, #rc-exp-a .wf-num { color:#7fdbff; }'
        + '#rc-exp-a .wf-str { color:#b0c4d8; }'
        + '#rc-exp-a .wf-tbl { width:100%; border-collapse:collapse; }'
        + '#rc-exp-a .wf-tbl td { padding:0.2rem 0.3rem; font-size:0.75rem; border-bottom:1px solid #0f2236; }'
        + '#rc-exp-a .wf-key { color:#4a7a9b; font-weight:500; width:100px; }'
        + '#rc-exp-a .wf-val { color:#b0c4d8; }'
        + '#rc-exp-a .wf-arr { display:flex; flex-direction:column; gap:0.1rem; }'
        + '#rc-exp-a .wf-arr-item { padding-left:0.4rem; border-left:2px solid #1e3a5f; }'
        + '#rc-exp-a .wf-table th { background:#0d1e30; border-color:#1e3a5f; color:#7fdbff; }'
        + '#rc-exp-a .wf-table td { border-color:#1e3a5f; }'
        + '#rc-exp-a .wf-table-rownum { color:#3a6a8f; background:#0b1622; }'
        + '#rc-exp-a .wf-table-coltype { color:#3a6a8f; }'
        + '#rc-exp-a .wf-table-empty { color:#2a4a6b; }'
        + '#rc-exp-a .wf-table-summary { color:#3a6a8f; }'
        + '#rc-exp-a .wf-table-prop { color:#3a6a8f; }'
        ;

    registerRenderer({
        id: 'exp-a',
        label: 'Experimental - A',
        format: 'exp-a',
        init: function(c) {
            c.style.cssText = 'overflow-y:auto;padding:0;';
            var style = document.createElement('style');
            style.textContent = EXP_CSS;
            document.head.appendChild(style);
            container = c;
        },
        update: function(state, msg, feedback) { expARenderPage(container, state, msg, feedback); },
        activate: function() {},
        deactivate: function() {}
    });
})();
