/* ======================================================================
   RENDERER: AGENT — formatted JSON
   ====================================================================== */
registerRenderer({
    id: 'raw',
    label: 'Agent',
    format: 'raw',
    _pre: null,
    init: function(c) {
        c.style.overflowY = 'auto';
        c.style.padding = '0.75rem';
        this._pre = document.createElement('pre');
        this._pre.style.cssText = 'margin:0;white-space:pre-wrap;word-break:break-word;color:#ccc;';
        c.appendChild(this._pre);
    },
    update: function(state) {
        this._pre.textContent = JSON.stringify(state, null, 2);
    },
    activate: function() {},
    deactivate: function() {}
});
