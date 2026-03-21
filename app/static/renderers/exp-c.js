/* ======================================================================
   RENDERER: EXPERIMENTAL C — tree outline
   ====================================================================== */
(function() {
    var container;

    function treeVal(v, indent) {
        var pfx = indent;
        if (v == null) return pfx + '(null)\n';
        if (typeof v === 'boolean' || typeof v === 'number') return pfx + String(v) + '\n';
        if (typeof v === 'string') return pfx + '"' + v.replace(/"/g, '\\"') + '"\n';
        if (Array.isArray(v)) {
            if (!v.length) return pfx + '(empty list)\n';
            var out = '';
            for (var i = 0; i < v.length; i++) {
                var isLast = i === v.length - 1;
                var branch = isLast ? '\u2514\u2500 ' : '\u251c\u2500 ';
                var childPfx = indent + (isLast ? '   ' : '\u2502  ');
                if (typeof v[i] === 'object' && v[i] !== null) {
                    out += indent + branch + '[' + i + ']\n';
                    out += treeObj(v[i], childPfx);
                } else {
                    out += indent + branch + treeVal(v[i], '').trim() + '\n';
                }
            }
            return out;
        }
        if (typeof v === 'object') return '\n' + treeObj(v, indent);
        return pfx + String(v) + '\n';
    }

    function treeObj(obj, indent) {
        var keys = Object.keys(obj);
        if (!keys.length) return indent + '(empty)\n';
        var out = '';
        for (var i = 0; i < keys.length; i++) {
            var k = keys[i];
            var isLast = i === keys.length - 1;
            var branch = isLast ? '\u2514\u2500 ' : '\u251c\u2500 ';
            var childPfx = indent + (isLast ? '   ' : '\u2502  ');
            var val = obj[k];
            if (val && typeof val === 'object' && !Array.isArray(val)) {
                out += indent + branch + k + '\n';
                out += treeObj(val, childPfx);
            } else if (Array.isArray(val)) {
                out += indent + branch + k + '\n';
                out += treeVal(val, childPfx);
            } else {
                out += indent + branch + k + ': ' + treeVal(val, '').trim() + '\n';
            }
        }
        return out;
    }

    function expCRenderPage(c, state, msg, feedback) {
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
        var lines = [];

        /* Root */
        lines.push('<span class="tc-root">' + wfEsc(s.workflow || 'Workflow') + '</span>');

        /* Lifecycle */
        var lifecycle = s.lifecycle || [];
        var current = s.lifecycle_current || '';
        var completed = s.lifecycle_completed || [];
        if (lifecycle.length) {
            lines.push('\u251c\u2500 <span class="tc-key">lifecycle</span>');
            for (var i = 0; i < lifecycle.length; i++) {
                var item = lifecycle[i];
                var label = (typeof item === 'string') ? item : (item.title || '');
                var itemId = (typeof item === 'string') ? item : (item.id || '');
                var isLast = i === lifecycle.length - 1;
                var branch = isLast ? '   \u2514\u2500 ' : '   \u251c\u2500 ';
                var cls = 'tc-phase';
                if (itemId === current || label === current) cls = 'tc-phase-cur';
                else if (completed.indexOf(itemId) !== -1 || completed.indexOf(label) !== -1) cls = 'tc-phase-done';
                lines.push(branch + '<span class="' + cls + '">' + wfEsc(label) + '</span>');
            }
        }

        /* Node (node_title rendered here; node raw ID and completed_nodes rendered by lifecycle above) */
        lines.push('\u251c\u2500 <span class="tc-key">node</span>: <span class="tc-node">' + wfEsc(s.node_title || s.node) + '</span>');

        /* Instructions */
        if (state.instructions) {
            lines.push('\u251c\u2500 <span class="tc-key">instructions</span>: <span class="tc-str">' + wfEsc(state.instructions) + '</span>');
        }

        /* Fields */
        if (s.fields) {
            var fkeys = Object.keys(s.fields);
            var hasMore = s.table || (state.affordances && state.affordances.length);
            var fieldBranch = hasMore ? '\u251c\u2500 ' : '\u2514\u2500 ';
            var fieldCont = hasMore ? '\u2502  ' : '   ';
            lines.push(fieldBranch + '<span class="tc-key">state.fields</span>');
            if (fkeys.length) {
                for (var i = 0; i < fkeys.length; i++) {
                    var k = fkeys[i];
                    var f = s.fields[k];
                    var isLast = i === fkeys.length - 1;
                    var fb = isLast ? '\u2514\u2500 ' : '\u251c\u2500 ';
                    var fc = isLast ? '   ' : '\u2502  ';
                    var cat = fieldCategory[k] || null;
                    var tagStr = '';
                    var tagMap = {outcome:'SET', 'new':'NEW', modified:'CHG'};
                    if (cat) tagStr = ' <span class="tc-tag tc-tag-' + cat + '">[' + tagMap[cat] + ']</span>';
                    lines.push(fieldCont + fb + '<span class="tc-fname' + (cat ? ' tc-f-' + cat : '') + '">' + wfEsc(k) + '</span>' + tagStr);
                    if (f && typeof f === 'object' && 'value' in f) {
                        var subPfx = fieldCont + fc;
                        var subParts = [];
                        if (f.value == null) subParts.push('value: <span class="tc-null">(not set)</span>');
                        else subParts.push('value: <span class="tc-str">' + wfEsc(f.value) + '</span>');
                        if (f.instruction) subParts.push('instruction: <span class="tc-instr">' + wfEsc(f.instruction) + '</span>');
                        if (f.options) subParts.push('options: <span class="tc-opts">' + wfEsc(f.options.join(', ')) + '</span>');
                        for (var j = 0; j < subParts.length; j++) {
                            var sIsLast = j === subParts.length - 1;
                            lines.push(subPfx + (sIsLast ? '\u2514\u2500 ' : '\u251c\u2500 ') + subParts[j]);
                        }
                    } else {
                        lines.push(fieldCont + fc + '\u2514\u2500 ' + treeVal(f, '').trim());
                    }
                }
            } else {
                lines.push(fieldCont + '\u2514\u2500 <span class="tc-null">(empty)</span>');
            }
        }

        /* Table — prefer execution_table during execution, fall back to construction table */
        var showExec = !!s.execution_table;
        var tblData = showExec ? s.execution_table : s.table;
        if (tblData) {
            var hasAffs = state.affordances && state.affordances.length;
            var tblBranch = hasAffs ? '\u251c\u2500 ' : '\u2514\u2500 ';
            var tblCont = hasAffs ? '\u2502  ' : '   ';
            var tblKey = showExec ? 'state.execution_table' : 'state.table';
            lines.push(tblBranch + '<span class="tc-key">' + tblKey + '</span>');

            if (showExec) {
                /* Execution table: rows are objects with cells, acceptance, gating */
                var etCols = tblData.columns || [];
                var etRows = tblData.rows || [];
                lines.push(tblCont + '\u251c\u2500 <span class="tc-key">columns</span>');
                for (var ci = 0; ci < etCols.length; ci++) {
                    var cLast = ci === etCols.length - 1;
                    var colExtra = '';
                    if (etCols[ci].choices) colExtra += ' choices=' + JSON.stringify(etCols[ci].choices);
                    if (etCols[ci].rule) colExtra += ' rule=' + wfRuleToExpr(etCols[ci].rule, etCols);
                    lines.push(tblCont + '\u2502  ' + (cLast ? '\u2514\u2500 ' : '\u251c\u2500 ') + '<span class="tc-fname">' + wfEsc(etCols[ci].name) + '</span> <span class="tc-opts">(' + wfEsc(etCols[ci].type) + ')</span>' + (colExtra ? ' <span class="tc-opts">' + wfEsc(colExtra) + '</span>' : ''));
                }
                if (!etCols.length) lines.push(tblCont + '\u2502  \u2514\u2500 <span class="tc-null">(none)</span>');
                lines.push(tblCont + '\u2514\u2500 <span class="tc-key">rows</span> (' + etRows.length + ')');
                for (var ri = 0; ri < etRows.length; ri++) {
                    var rLast = ri === etRows.length - 1;
                    var rb = rLast ? '\u2514\u2500 ' : '\u251c\u2500 ';
                    var rc = rLast ? '   ' : '\u2502  ';
                    var r = etRows[ri];
                    var acc = r.acceptance || {};
                    var gTag = r.gated ? ' <span class="tc-null">[gated:true]</span>' : '';
                    var aTag = acc.passed ? ' <span class="tc-f-new">[acceptance.passed:true]</span>' : ' <span class="tc-null">[acceptance.passed:false]</span>';
                    lines.push(tblCont + '   ' + rb + '<span class="tc-fname">' + wfEsc(r.row_id || 'row ' + r.row) + '</span>' + gTag + aTag);
                    if (r.gated_by && r.gated_by.length) {
                        lines.push(tblCont + '   ' + rc + '\u251c\u2500 <span class="tc-key">gated_by</span>: <span class="tc-str">' + wfEsc(JSON.stringify(r.gated_by)) + '</span>');
                    }
                    if (acc.reason) {
                        lines.push(tblCont + '   ' + rc + '\u251c\u2500 <span class="tc-key">acceptance.reason</span>: <span class="tc-str">' + wfEsc(acc.reason) + '</span>');
                    }
                    var cells = r.cells || [];
                    for (var ci2 = 0; ci2 < cells.length; ci2++) {
                        var cLast2 = ci2 === cells.length - 1;
                        var cell = cells[ci2];
                        var dv = cell.display_value || '';
                        var statusTag = '<span class="tc-opts">[' + (cell.status || '?') + ']</span>';
                        var cellLine = wfEsc(cell.column_name) + ' <span class="tc-opts">(' + wfEsc(cell.column_type) + ')</span> ' + statusTag + ': ' + (dv ? '<span class="tc-str">' + wfEsc(dv) + '</span>' : '<span class="tc-null">\u2014</span>');
                        if (cell.value && cell.value !== cell.display_value) cellLine += ' <span class="tc-opts">value=' + wfEsc(cell.value) + '</span>';
                        if (cell.available_actions && cell.available_actions.length) cellLine += ' <span class="tc-opts">actions=' + wfEsc(JSON.stringify(cell.available_actions)) + '</span>';
                        if (cell.locked_reason) cellLine += ' <span class="tc-opts">locked_reason=' + wfEsc(cell.locked_reason) + '</span>';
                        lines.push(tblCont + '   ' + rc + (cLast2 ? '\u2514\u2500 ' : '\u251c\u2500 ') + cellLine);
                    }
                }
                if (!etRows.length) lines.push(tblCont + '   \u2514\u2500 <span class="tc-null">(none)</span>');
            } else {
                /* Construction table: rows are flat arrays */
                var tbl = tblData;
                var cols = tbl.columns || [];
                var rows = tbl.rows || [];
                if (tbl.summary) {
                    lines.push(tblCont + '\u251c\u2500 summary: <span class="tc-str">' + wfEsc(tbl.summary) + '</span>');
                }
                lines.push(tblCont + '\u251c\u2500 <span class="tc-key">columns</span>');
                for (var ci = 0; ci < cols.length; ci++) {
                    var cLast = ci === cols.length - 1;
                    var cb = cLast ? '\u2514\u2500 ' : '\u251c\u2500 ';
                    var cExtra = '';
                    if (cols[ci].choices) cExtra += ' choices=' + JSON.stringify(cols[ci].choices);
                    if (cols[ci].rule) cExtra += ' rule=' + wfRuleToExpr(cols[ci].rule, cols);
                    lines.push(tblCont + '\u2502  ' + cb + '<span class="tc-fname">' + wfEsc(cols[ci].name) + '</span> <span class="tc-opts">(' + wfEsc(cols[ci].type) + ')</span>' + (cExtra ? ' <span class="tc-opts">' + wfEsc(cExtra) + '</span>' : ''));
                }
                if (!cols.length) lines.push(tblCont + '\u2502  \u2514\u2500 <span class="tc-null">(none)</span>');
                var hasProps = tbl.properties && Object.keys(tbl.properties).length;
                var rowBranch = hasProps ? '\u251c\u2500 ' : '\u2514\u2500 ';
                lines.push(tblCont + rowBranch + '<span class="tc-key">rows</span> (' + rows.length + ')');
                for (var ri = 0; ri < rows.length; ri++) {
                    var rLast = ri === rows.length - 1;
                    var rb = rLast ? '\u2514\u2500 ' : '\u251c\u2500 ';
                    var rc = rLast ? '   ' : '\u2502  ';
                    var rowPfx = tblCont + (hasProps ? '\u2502  ' : '   ');
                    lines.push(rowPfx + rb + '<span class="tc-fname">row ' + ri + '</span>');
                    for (var ci2 = 0; ci2 < rows[ri].length; ci2++) {
                        var cLast2 = ci2 === rows[ri].length - 1;
                        var cn = cols[ci2] ? cols[ci2].name : 'col-' + ci2;
                        var cv = rows[ri][ci2];
                        lines.push(rowPfx + rc + (cLast2 ? '\u2514\u2500 ' : '\u251c\u2500 ') + wfEsc(cn) + ': ' + (cv ? '<span class="tc-str">' + wfEsc(cv) + '</span>' : '<span class="tc-null">\u2014</span>'));
                    }
                }
                if (!rows.length) lines.push(tblCont + (hasProps ? '\u2502  ' : '   ') + '\u2514\u2500 <span class="tc-null">(none)</span>');
                if (hasProps) {
                    lines.push(tblCont + '\u2514\u2500 <span class="tc-key">properties</span>');
                    var pk = Object.keys(tbl.properties);
                    for (var pi = 0; pi < pk.length; pi++) {
                        var pLast = pi === pk.length - 1;
                        lines.push(tblCont + '   ' + (pLast ? '\u2514\u2500 ' : '\u251c\u2500 ') + wfEsc(pk[pi]) + ': <span class="tc-str">' + wfEsc(String(tbl.properties[pk[pi]])) + '</span>');
                    }
                }
            }
        }

        /* Extra state keys (generic rendering for unknown keys) */
        var extraProps = wfRenderStateProps(state);
        if (extraProps) {
            lines.push('\u251c\u2500 <span class="tc-key">(extra state)</span>');
            lines.push('   ' + extraProps.replace(/<[^>]+>/g, '').substring(0, 200));
        }

        /* Affordances */
        if (state.affordances && state.affordances.length) {
            lines.push('\u2514\u2500 <span class="tc-key">affordances</span>');
            for (var i = 0; i < state.affordances.length; i++) {
                var a = state.affordances[i];
                var isLast = i === state.affordances.length - 1;
                var ab = isLast ? '   \u2514\u2500 ' : '   \u251c\u2500 ';
                var ac2 = isLast ? '      ' : '   \u2502  ';
                var acCat = affCategory[a.label] || null;
                var acTag = '';
                if (acCat === 'new') acTag = ' <span class="tc-tag tc-tag-new">[NEW]</span>';
                else if (acCat === 'modified') acTag = ' <span class="tc-tag tc-tag-modified">[CHG]</span>';
                var affCls = 'tc-aff';
                if (/Proceed|Submit/.test(a.label)) affCls += ' tc-aff-primary';
                else if (/Go back/.test(a.label)) affCls += ' tc-aff-nav';
                else if (/\[Selected\]/.test(a.label)) affCls += ' tc-aff-selected';
                lines.push(ab + '<span class="tc-aff-id">[' + a.id + ']</span> <span class="' + affCls + '">' + wfEsc(a.label) + '</span>' + acTag);
                lines.push(ac2 + '\u251c\u2500 <span class="tc-aff-m">' + wfEsc(a.method) + '</span> <span class="tc-aff-url">' + wfEsc(a.url) + '</span>');
                var pStr = wfRenderParams(a);
                var bodyLine = ac2 + (pStr ? '\u251c\u2500 ' : '\u2514\u2500 ') + 'body: <span class="tc-aff-body">' + wfEsc(JSON.stringify(a.body)) + '</span>';
                lines.push(bodyLine);
                if (pStr) {
                    lines.push(ac2 + '\u2514\u2500 <span class="tc-opts">' + wfEsc(pStr) + '</span>');
                }
            }
        }

        c.querySelector('.tc-content').innerHTML = lines.join('\n');
    }

    var EXP_C_CSS = ''
        + '#rc-exp-c { background:#0a100a; color:#88b888; font-family:Consolas,"Courier New",monospace; overflow-y:auto; padding:0.8rem 1rem; }'
        + '#rc-exp-c .tc-content { white-space:pre; line-height:1.6; font-size:0.82rem; }'
        + '#rc-exp-c .tc-root { font-size:1rem; font-weight:700; color:#50fa7b; }'
        + '#rc-exp-c .tc-key { color:#6abf6a; font-weight:600; }'
        + '#rc-exp-c .tc-node { color:#f1fa8c; font-weight:600; }'
        + '#rc-exp-c .tc-phase { color:#4a6a4a; }'
        + '#rc-exp-c .tc-phase-cur { color:#50fa7b; font-weight:700; text-decoration:underline; }'
        + '#rc-exp-c .tc-phase-done { color:#6abf6a; }'
        + '#rc-exp-c .tc-str { color:#c8e8c8; }'
        + '#rc-exp-c .tc-null { color:#4a6a4a; font-style:italic; }'
        + '#rc-exp-c .tc-instr { color:#6a8a6a; font-style:italic; }'
        + '#rc-exp-c .tc-opts { color:#6a8a6a; }'
        + '#rc-exp-c .tc-fname { color:#8be88b; font-weight:600; }'
        + '#rc-exp-c .tc-f-outcome { color:#6abf6a; }'
        + '#rc-exp-c .tc-f-new { color:#50fa7b; }'
        + '#rc-exp-c .tc-f-modified { color:#f1fa8c; }'
        + '#rc-exp-c .tc-tag { font-size:0.7em; font-weight:700; }'
        + '#rc-exp-c .tc-tag-outcome { color:#6abf6a; }'
        + '#rc-exp-c .tc-tag-new { color:#50fa7b; }'
        + '#rc-exp-c .tc-tag-modified { color:#f1fa8c; }'
        + '#rc-exp-c .tc-aff-id { color:#50fa7b; font-weight:700; }'
        + '#rc-exp-c .tc-aff { color:#88b888; }'
        + '#rc-exp-c .tc-aff-primary { color:#50fa7b; font-weight:700; }'
        + '#rc-exp-c .tc-aff-nav { color:#4a6a4a; }'
        + '#rc-exp-c .tc-aff-selected { color:#8be88b; text-decoration:underline; }'
        + '#rc-exp-c .tc-aff-m { color:#6abf6a; font-weight:600; }'
        + '#rc-exp-c .tc-aff-url { color:#88b888; }'
        + '#rc-exp-c .tc-aff-body { color:#6a8a6a; }'
        ;

    registerRenderer({
        id: 'exp-c',
        label: 'Experimental - C',
        format: 'exp-c',
        init: function(c) {
            c.style.cssText = 'overflow-y:auto;padding:0;';
            var style = document.createElement('style');
            style.textContent = EXP_C_CSS;
            document.head.appendChild(style);
            var pre = document.createElement('pre');
            pre.className = 'tc-content';
            c.appendChild(pre);
            container = c;
        },
        update: function(state, msg, feedback) { expCRenderPage(container, state, msg, feedback); },
        activate: function() {},
        deactivate: function() {}
    });
})();
