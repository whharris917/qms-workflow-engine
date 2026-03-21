/* ======================================================================
   RENDERER: PORTAL — Agent Portal dashboard
   Projects the canonical {state, instructions, affordances} payload
   into the card-grid human view.  Every button corresponds to an
   affordance — no actions are invented by the renderer.
   ====================================================================== */
(function() {

function esc(s) { return s == null ? '' : String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function affTooltip(aff) {
    var lines = aff.method + ' ' + aff.url;
    if (aff.body !== undefined) {
        lines += ' ' + JSON.stringify(aff.body);
    }
    return lines;
}

function renderPortal(container, data) {
    var state = data.state || {};
    var instructions = data.instructions || '';
    var affordances = data.affordances || [];
    var workflows = state.workflows || [];
    var title = state.page_title || 'Agent Portal';
    // Index affordances by URL+method for lookup
    var affIndex = {};
    affordances.forEach(function(a) {
        affIndex[a.method + ' ' + a.url] = a;
    });

    var html = '<h1>' + esc(title) + '</h1>';
    html += '<p>' + esc(instructions) + '</p>';
    html += '<div class="portal-grid">';

    workflows.forEach(function(wf) {
        html += '<div class="portal-card">';
        html += '<h2>' + esc(wf.title) + '</h2>';
        html += '<p>' + esc(wf.description) + '</p>';

        html += '<table class="portal-inst-table">';
        if (wf.instances && wf.instances.length > 0) {
            html += '<thead><tr><th>Instance</th><th>Node</th><th></th></tr></thead><tbody>';
            wf.instances.forEach(function(inst) {
                html += '<tr>';
                html += '<td class="portal-inst-id">' + esc(inst.id) + '</td>';
                html += '<td class="portal-inst-node">' + esc(inst.node) + '</td>';
                html += '<td class="portal-inst-actions">';

                // Open — from GET affordance
                var openAff = affIndex['GET ' + inst.url];
                if (openAff) {
                    html += '<a class="portal-btn-observe" href="' + esc(openAff.url) + '" title="' + esc(affTooltip(openAff)) + '">Open</a>';
                }

                // Delete — from POST affordance
                var deleteAff = affIndex['POST ' + inst.url + '/delete'];
                if (deleteAff) {
                    html += '<button class="portal-btn-delete" data-url="' + esc(deleteAff.url) + '" data-id="' + esc(deleteAff.id) + '" title="' + esc(affTooltip(deleteAff)) + '">Delete</button>';
                }

                html += '</td>';
                html += '</tr>';
            });
            html += '</tbody>';
        }
        html += '</table>';

        // New instance — from POST affordance
        var newAff = affIndex['POST /agent/' + wf.id + '/new'];
        if (newAff) {
            html += '<div class="portal-new-wrap">';
            html += '<form action="' + esc(newAff.url) + '" method="POST" style="margin:0;">';
            html += '<button class="portal-btn-new" type="submit" title="' + esc(affTooltip(newAff)) + '">+ New Instance</button>';
            html += '</form>';
            html += '</div>';
        }

        html += '</div>';
    });

    html += '</div>';
    container.innerHTML = html;

    // Bind delete buttons — each reads its URL from the affordance
    container.querySelectorAll('.portal-btn-delete').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var url = btn.getAttribute('data-url');
            fetch(url, { method: 'POST' })
                .then(function(r) { return r.json(); })
                .then(function() { location.reload(); });
        });
    });
}

window._portalRenderer = { render: renderPortal };

})();
