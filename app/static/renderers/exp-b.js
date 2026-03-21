/* ======================================================================
   RENDERER: EXPERIMENTAL B — card grid layout
   ====================================================================== */
(function() {
    var container;

    function expBRenderPage(c, state, msg, feedback) {
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

        /* ── Header with filled progress bar ── */
        var defnNodes = (s.definition || s.banner_definition || {}).nodes || [];
        var current = s.node || '';
        var completed = s.completed_nodes || [];
        var progressCount = completed.length + (current && completed.indexOf(current) === -1 ? 1 : 0);
        var pct = defnNodes.length ? Math.round((progressCount / defnNodes.length) * 100) : 0;

        html += '<div class="gb-header">';
        html += '<div class="gb-title">' + wfEsc(s.workflow || 'Workflow') + '</div>';
        html += '<div class="gb-node">' + wfEsc(s.node_title || s.node) + '</div>';
        html += '</div>';

        if (defnNodes.length) {
            html += '<div class="gb-bar-wrap">';
            html += '<div class="gb-bar-track">';
            html += '<div class="gb-bar-fill" style="width:' + Math.max(pct, 4) + '%"></div>';
            html += '</div>';
            html += '<div class="gb-bar-labels">';
            for (var i = 0; i < defnNodes.length; i++) {
                var item = defnNodes[i];
                var isCurrent = item.id === current;
                var isDone = completed.indexOf(item.id) !== -1;
                html += '<span class="gb-bar-lbl' + (isCurrent ? ' gb-bar-lbl-cur' : '') + (isDone ? ' gb-bar-lbl-done' : '') + '">' + wfEsc(item.title) + '</span>';
            }
            html += '</div>';
            html += '</div>';
        }

        if (state.instructions) {
            html += '<div class="gb-instr">' + wfEsc(state.instructions) + '</div>';
        }

        /* ── Table (if present) ── */
        if (s.execution_table) {
            html += wfRenderExecTable(s.execution_table);
        } else if (s.table) {
            html += wfRenderTable(s.table);
        }

        /* ── Field cards in a grid ── */
        if (s.fields) {
            html += '<div class="gb-section-label">state.fields</div>';
            var fkeys = Object.keys(s.fields);
            if (fkeys.length) {
                html += '<div class="gb-grid">';
                for (var i = 0; i < fkeys.length; i++) {
                    var k = fkeys[i];
                    var f = s.fields[k];
                    var cat = fieldCategory[k] || null;
                    var cls = 'gb-fcard' + (cat ? ' gb-fc-' + cat : '');
                    html += '<div class="' + cls + '">';
                    var tagMap = {outcome:'SET', 'new':'NEW', modified:'CHG'};
                    html += '<div class="gb-fc-head">';
                    html += '<span class="gb-fc-name">' + wfEsc(k) + '</span>';
                    if (cat) html += '<span class="gb-tag gb-tag-' + cat + '">' + tagMap[cat] + '</span>';
                    html += '</div>';
                    if (f && typeof f === 'object' && 'value' in f) {
                        if (f.instruction) html += '<div class="gb-fc-instr">' + wfEsc(f.instruction) + '</div>';
                        if (f.value == null) html += '<div class="gb-fc-val gb-fc-empty">not set</div>';
                        else html += '<div class="gb-fc-val">' + wfEsc(f.value) + '</div>';
                        if (f.options) html += '<div class="gb-fc-opts">' + wfEsc(f.options.join(' | ')) + '</div>';
                    } else {
                        html += '<div class="gb-fc-val">' + wfRenderValue(f) + '</div>';
                    }
                    html += '</div>';
                }
                html += '</div>';
            } else {
                html += '<div class="gb-empty">(empty)</div>';
            }
        }

        /* ── Extra state (generic) ── */
        html += wfRenderStateProps(state);

        /* ── Affordances as pill toolbar ── */
        if (state.affordances && state.affordances.length) {
            html += '<div class="gb-section-label">affordances</div>';
            html += '<div class="gb-toolbar">';
            for (var i = 0; i < state.affordances.length; i++) {
                var a = state.affordances[i];
                var cls = 'gb-pill';
                if (/Proceed|Submit/.test(a.label)) cls += ' gb-pill-primary';
                else if (/Go back/.test(a.label)) cls += ' gb-pill-nav';
                else if (/\[Selected\]/.test(a.label)) cls += ' gb-pill-selected';
                var ac = affCategory[a.label];
                if (ac) cls += ' gb-pill-fb-' + ac;
                html += '<div class="' + cls + '">';
                html += '<span class="gb-pill-id">' + a.id + '</span>';
                html += '<span class="gb-pill-label">' + wfEsc(a.label);
                if (ac === 'new') html += ' <span class="gb-tag gb-tag-new">NEW</span>';
                else if (ac === 'modified') html += ' <span class="gb-tag gb-tag-modified">CHG</span>';
                html += '</span>';
                html += '<div class="gb-pill-detail">';
                html += '<span class="gb-pill-method">' + wfEsc(a.method) + '</span> ';
                html += wfEsc(a.url) + ' ' + wfEsc(JSON.stringify(a.body));
                html += '</div>';
                var pStr = wfRenderParams(a);
                if (pStr) html += '<div class="gb-pill-opts">' + wfEsc(pStr) + '</div>';
                html += '</div>';
            }
            html += '</div>';
        }

        c.innerHTML = html;
    }

    var EXP_B_CSS = ''
        + '#rc-exp-b { background:#1a1226; color:#d4c8e8; font-family:"Segoe UI",Roboto,sans-serif; overflow-y:auto; padding:0; }'
        + '#rc-exp-b .gb-header { padding:1rem 1.2rem 0.3rem; }'
        + '#rc-exp-b .gb-title { font-size:0.78rem; text-transform:uppercase; letter-spacing:0.12em; color:#8b6cc1; }'
        + '#rc-exp-b .gb-node { font-size:1.3rem; font-weight:700; color:#e8ddf5; margin-top:0.15rem; }'

        + '#rc-exp-b .gb-bar-wrap { padding:0.5rem 1.2rem; }'
        + '#rc-exp-b .gb-bar-track { height:6px; background:#2a1e3e; border-radius:3px; overflow:hidden; }'
        + '#rc-exp-b .gb-bar-fill { height:100%; background:linear-gradient(90deg,#8b6cc1,#c084fc); border-radius:3px; transition:width 0.3s; }'
        + '#rc-exp-b .gb-bar-labels { display:flex; justify-content:space-between; margin-top:0.3rem; }'
        + '#rc-exp-b .gb-bar-lbl { font-size:0.62rem; color:#5a4a70; }'
        + '#rc-exp-b .gb-bar-lbl-cur { color:#c084fc; font-weight:700; }'
        + '#rc-exp-b .gb-bar-lbl-done { color:#8b6cc1; }'

        + '#rc-exp-b .gb-instr { padding:0.3rem 1.2rem 0.6rem; font-size:0.82rem; color:#9a8ab0; line-height:1.5; white-space:pre-line; }'

        + '#rc-exp-b .gb-section-label { padding:0.3rem 1.2rem; font-size:0.65rem; text-transform:uppercase; letter-spacing:0.1em; color:#5a4a70; }'

        + '#rc-exp-b .gb-grid { display:grid; grid-template-columns:1fr 1fr; gap:0.5rem; padding:0.3rem 1.2rem 0.8rem; }'
        + '#rc-exp-b .gb-fcard { background:#221a33; border:1px solid #2e2444; border-radius:8px; padding:0.6rem 0.7rem; display:flex; flex-direction:column; gap:0.2rem; }'
        + '#rc-exp-b .gb-fc-head { display:flex; align-items:center; justify-content:space-between; }'
        + '#rc-exp-b .gb-fc-name { font-size:0.78rem; font-weight:600; color:#c084fc; }'
        + '#rc-exp-b .gb-fc-instr { font-size:0.7rem; color:#6a5a80; font-style:italic; }'
        + '#rc-exp-b .gb-fc-val { font-size:0.85rem; color:#d4c8e8; }'
        + '#rc-exp-b .gb-fc-empty { color:#4a3a60; font-style:italic; }'
        + '#rc-exp-b .gb-fc-opts { font-size:0.68rem; color:#6a5a80; font-family:Consolas,monospace; }'

        + '#rc-exp-b .gb-fc-outcome { border-left:3px solid #8b6cc1; background:#251d38; }'
        + '#rc-exp-b .gb-fc-new { border-left:3px solid #4caf50; background:#1a2a1a; }'
        + '#rc-exp-b .gb-fc-modified { border-left:3px solid #e6a817; background:#2a2210; }'

        + '#rc-exp-b .gb-tag { font-size:0.55rem; font-weight:700; letter-spacing:0.06em; padding:0.1rem 0.3rem; border-radius:3px; }'
        + '#rc-exp-b .gb-tag-outcome { color:#c084fc; background:rgba(192,132,252,0.15); }'
        + '#rc-exp-b .gb-tag-new { color:#4caf50; background:rgba(76,175,80,0.15); }'
        + '#rc-exp-b .gb-tag-modified { color:#e6a817; background:rgba(230,168,23,0.15); }'

        + '#rc-exp-b .gb-toolbar { display:flex; flex-direction:column; gap:0.35rem; padding:0.3rem 1.2rem 1rem; }'
        + '#rc-exp-b .gb-pill { display:flex; flex-wrap:wrap; align-items:center; gap:0.4rem; padding:0.5rem 0.7rem; background:#221a33; border:1px solid #2e2444; border-radius:20px; }'
        + '#rc-exp-b .gb-pill-id { display:inline-flex; align-items:center; justify-content:center; width:20px; height:20px; border-radius:50%; font-size:0.65rem; font-weight:700; background:#2e2444; color:#8b6cc1; flex-shrink:0; }'
        + '#rc-exp-b .gb-pill-label { font-size:0.82rem; color:#d4c8e8; flex:1; }'
        + '#rc-exp-b .gb-pill-detail { width:100%; font-size:0.65rem; color:#5a4a70; font-family:Consolas,monospace; padding-left:1.8rem; word-break:break-all; }'
        + '#rc-exp-b .gb-pill-method { font-weight:600; color:#6a5a80; }'
        + '#rc-exp-b .gb-pill-opts { width:100%; font-size:0.65rem; color:#5a4a70; font-family:Consolas,monospace; padding-left:1.8rem; }'

        + '#rc-exp-b .gb-pill-primary { border-color:#8b6cc1; background:#251d38; }'
        + '#rc-exp-b .gb-pill-primary .gb-pill-label { color:#c084fc; font-weight:700; }'
        + '#rc-exp-b .gb-pill-primary .gb-pill-id { background:#8b6cc1; color:#fff; }'
        + '#rc-exp-b .gb-pill-nav { border-style:dashed; border-color:#2e2444; }'
        + '#rc-exp-b .gb-pill-nav .gb-pill-label { color:#6a5a80; }'
        + '#rc-exp-b .gb-pill-selected { border-color:#4caf50; background:#1a2a1a; }'
        + '#rc-exp-b .gb-pill-selected .gb-pill-label { color:#4caf50; }'
        + '#rc-exp-b .gb-pill-selected .gb-pill-id { background:#4caf50; color:#fff; }'
        + '#rc-exp-b .gb-pill-fb-new { border-left:3px solid #4caf50; }'
        + '#rc-exp-b .gb-pill-fb-modified { border-left:3px solid #e6a817; }'

        + '#rc-exp-b .gb-empty { padding:0.5rem 1.2rem; color:#4a3a60; font-style:italic; font-size:0.8rem; }'

        + '#rc-exp-b .wf-null, #rc-exp-b .wf-empty-arr, #rc-exp-b .wf-empty-obj { color:#4a3a60; font-style:italic; font-size:0.8rem; }'
        + '#rc-exp-b .wf-bool, #rc-exp-b .wf-num { color:#c084fc; }'
        + '#rc-exp-b .wf-str { color:#d4c8e8; }'
        + '#rc-exp-b .wf-tbl { width:100%; border-collapse:collapse; }'
        + '#rc-exp-b .wf-tbl td { padding:0.2rem 0.3rem; font-size:0.78rem; border-bottom:1px solid #2e2444; }'
        + '#rc-exp-b .wf-key { color:#8b6cc1; font-weight:500; }'
        + '#rc-exp-b .wf-val { color:#d4c8e8; }'
        + '#rc-exp-b .wf-arr { display:flex; flex-direction:column; gap:0.1rem; }'
        + '#rc-exp-b .wf-arr-item { padding-left:0.4rem; border-left:2px solid #2e2444; }'
        + '#rc-exp-b .wf-table th { background:#221a33; border-color:#2e2444; color:#c084fc; }'
        + '#rc-exp-b .wf-table td { border-color:#2e2444; }'
        + '#rc-exp-b .wf-table-rownum { color:#5a4a70; background:#1a1226; }'
        + '#rc-exp-b .wf-table-coltype { color:#6a5a80; }'
        + '#rc-exp-b .wf-table-empty { color:#4a3a60; }'
        + '#rc-exp-b .wf-table-summary { color:#6a5a80; }'
        + '#rc-exp-b .wf-table-prop { color:#6a5a80; }'
        ;

    registerRenderer({
        id: 'exp-b',
        label: 'Experimental - B',
        format: 'exp-b',
        init: function(c) {
            c.style.cssText = 'overflow-y:auto;padding:0;';
            var style = document.createElement('style');
            style.textContent = EXP_B_CSS;
            document.head.appendChild(style);
            container = c;
        },
        update: function(state, msg, feedback) { expBRenderPage(container, state, msg, feedback); },
        activate: function() {},
        deactivate: function() {}
    });
})();

