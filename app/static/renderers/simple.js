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
    + '.wf-card { margin:0.5rem 1.5rem; padding:0.75rem; border:1px solid; border-radius:8px; }'
    + '.wf-card-head { font-size:0.75rem; font-weight:600; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:0.5rem; }'
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
    + '.wf-field-options { font-size:0.72rem; font-family:Consolas,Monaco,monospace; margin-top:0.15rem; }'
    + '.wf-aff { margin-bottom:0.4rem; padding:0.5rem 0.6rem; border:1px solid; border-radius:6px; }'
    + '.wf-aff-top { display:flex; align-items:center; gap:0.5rem; }'
    + '.wf-aff-id { display:inline-flex; align-items:center; justify-content:center; width:20px; height:20px; border-radius:50%; font-size:0.7rem; font-weight:600; flex-shrink:0; }'
    + '.wf-aff-label { flex:1; font-size:0.85rem; }'
    + '.wf-aff-method { font-size:0.65rem; font-weight:600; padding:0.15rem 0.4rem; border-radius:3px; }'
    + '.wf-aff-detail { font-size:0.72rem; margin-top:0.2rem; padding-left:2rem; font-family:Consolas,Monaco,monospace; word-break:break-all; }'
    + '.wf-aff-options { font-size:0.72rem; margin-top:0.15rem; padding-left:2rem; font-family:Consolas,Monaco,monospace; }'
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
    /* Schematic hybrid renderer — CSS injected by schematic.js on first use */
    ;

/* ── CSS ── */
var EXP_D_FC_CSS = ''
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
var EXP_D_FC_LIGHT = ''
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

/* ── Dark tokens ── */
var EXP_D_FC_DARK = ''
    + '.fc-hdr { border-bottom-color:#4a9eff; } .fc-hdr-title { color:#e0e0e0; }'
    + '.fc-card { background:#141414; border-color:#2a2a2a; box-shadow:0 1px 4px rgba(0,0,0,0.3); }'
    + '.fc-card-head { background:linear-gradient(135deg,#252525,#2a2a2a); }'
    + '.fc-num { background:#4a9eff; color:#fff; }'
    + '.fc-card-title { color:#e0e0e0; }'
    + '.fc-ft-text { background:#0d2a40; border-color:#64b5f6; color:#64b5f6; }'
    + '.fc-ft-bool { background:#2a1a00; border-color:#ffb74d; color:#ffb74d; }'
    + '.fc-ft-sel { background:#2a1a30; border-color:#ce93d8; color:#ce93d8; }'
    + '.fc-gate { border-top-color:#1b3a1b; }'
    + '.fc-gate-lbl { color:#66bb6a; }'
    + '.fc-gate-reqs { color:#64b5f6; }'
    + '.fc-acts { border-top-color:#1e1e1e; }'
    + '.fc-act-submit { background:#1b3a1b; color:#66bb6a; }'
    + '.fc-act-restart { background:#2a1a00; color:#ffb74d; }'
    + '.fc-badge-router { background:#2a1a00; color:#ffb74d; }'
    + '.fc-badge-fork { background:#1b3a1b; color:#66bb6a; }'
    + '.fc-card-router .fc-card-head { background:linear-gradient(135deg,#2a1a00,#332200); }'
    + '.fc-card-fork .fc-card-head { background:linear-gradient(135deg,#1b3a1b,#1f421f); }'
    + '.fc-route-arrow { color:#ffb74d; }'
    + '.fc-route-cond { color:#bcaaa4; }'
    + '.fc-route-target { color:#64b5f6; }'
    + '.fc-fork-info { border-top-color:#1b3a1b; }'
    + '.fc-fork-label { color:#66bb6a; }'
    + '.fc-fork-merge { color:#aaa; }'
    + '.fc-fork-branch { background:#1b3a1b; border-color:#2e7d32; color:#66bb6a; }'
    + '.fc-ef { stroke:#4caf50; } .fc-mf { fill:#4caf50; }'
    + '.fc-eb { stroke:#4a9eff; } .fc-mb { fill:#4a9eff; }'
    + '.fc-eg { stroke:#ce93d8; } .fc-mg { fill:#ce93d8; }'
    + '.fc-efk { stroke:#4caf50; } .fc-mk { fill:#4caf50; }'
    + '.fc-emg { stroke:#4caf50; }'
    + '.fc-ert { stroke:#ffb74d; } .fc-mr { fill:#ffb74d; }'
    + '.fc-el-b { fill:#4a9eff; } .fc-el-g { fill:#ce93d8; }'
    + '.fc-el-fk { fill:#4caf50; } .fc-el-rt { fill:#ffb74d; }'
    ;

function _scopeFC(sel, css) { return css.replace(/\.fc-/g, sel + ' .fc-'); }

/* ── Register 4 variants ── */
(function() {
    var container;
    registerRenderer({
        id: 'light', label: 'Simple', format: 'simple',
        verbosity: 'default', verbosity_label: 'Default', style: 'light', style_label: 'Light',
        init: function(c) {
            c.style.cssText = 'overflow-y:auto;padding:0;';
            var style = document.createElement('style');
            style.textContent = WF_STRUCTURAL_CSS + EXP_D_FC_CSS
                + _scopeFC('#rc-light', EXP_D_FC_LIGHT)
                + '#rc-light { background:#f5f5f5; color:#333; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }'
                + '#rc-light .wf-title { color:#1a1a2e; } #rc-light .wf-banner { background:#f8f9fb; border-color:#e8e8e8; } #rc-light .wf-dot { background:#dde1e6; color:#888; } #rc-light .wf-step-label { color:#888; } #rc-light .wf-step-active .wf-dot { background:#2a6bcf; color:#fff; } #rc-light .wf-step-active .wf-step-label { color:#1a1a2e; font-weight:600; } #rc-light .wf-step-done .wf-dot { background:#4caf50; color:#fff; } #rc-light .wf-step-done .wf-step-label { color:#555; } #rc-light .wf-conn { background:#dde1e6; } #rc-light .wf-conn-active { background:#4caf50; } #rc-light .wf-section-head { color:#1a1a2e; } #rc-light .wf-desc { color:#666; } #rc-light .wf-card { background:#fff; border-color:#e8e8e8; } #rc-light .wf-card-head { color:#7f8fa6; } #rc-light .wf-tbl td { border-bottom:1px solid #f0f0f0; } #rc-light .wf-key { color:#7f8fa6; } #rc-light .wf-val { color:#333; } #rc-light .wf-null, #rc-light .wf-empty-arr, #rc-light .wf-empty-obj { color:#bbb; } #rc-light .wf-bool, #rc-light .wf-num { color:#2a6bcf; } #rc-light .wf-str { color:#333; } #rc-light .wf-arr-item { border-left-color:#e8e8e8; } #rc-light .wf-field { border-bottom:1px solid #f0f0f0; } #rc-light .wf-field-label { color:#555; } #rc-light .wf-field-instruction { color:#999; } #rc-light .wf-field-value { color:#333; } #rc-light .wf-field-empty { color:#bbb; } #rc-light .wf-field-options { color:#7f8fa6; } #rc-light .wf-aff { background:#f8f9fb; border-color:#e8e8e8; } #rc-light .wf-aff-id { background:#dde1e6; color:#555; } #rc-light .wf-aff-label { color:#333; } #rc-light .wf-aff-method { color:#7f8fa6; background:#eef1f5; } #rc-light .wf-aff-detail { color:#999; } #rc-light .wf-aff-options { color:#7f8fa6; } #rc-light .wf-aff-primary { border-color:#2a6bcf; background:#f0f5ff; } #rc-light .wf-aff-primary .wf-aff-label { color:#2a6bcf; font-weight:600; } #rc-light .wf-aff-primary .wf-aff-id { background:#2a6bcf; color:#fff; } #rc-light .wf-aff-nav { border-color:#dde1e6; background:#fafafa; } #rc-light .wf-aff-nav .wf-aff-label { color:#888; } #rc-light .wf-aff-selected { border-color:#4caf50; background:#f0fff0; } #rc-light .wf-aff-selected .wf-aff-label { color:#2e7d32; } #rc-light .wf-aff-selected .wf-aff-id { background:#4caf50; color:#fff; } #rc-light .wf-fb-outcome { border-left:3px solid #2a6bcf; background:#f0f5ff; } #rc-light .wf-fb-new { border-left:3px solid #4caf50; background:#f0faf0; } #rc-light .wf-fb-modified { border-left:3px solid #e6a817; background:#fdf8ed; } #rc-light .wf-aff-new { border-left:3px solid #4caf50; background:#f0faf0; } #rc-light .wf-aff-modified { border-left:3px solid #e6a817; background:#fdf8ed; } #rc-light .wf-tag-outcome { color:#2a6bcf; } #rc-light .wf-tag-new { color:#4caf50; } #rc-light .wf-tag-modified { color:#e6a817; } #rc-light .wf-table th { background:#f4f6f9; border-color:#e8e8e8; } #rc-light .wf-table td { border-color:#e8e8e8; } #rc-light .wf-table-rownum { color:#aaa; background:#fafbfc; } #rc-light .wf-table-coltype { color:#7f8fa6; } #rc-light .wf-table-empty { color:#bbb; } #rc-light .wf-table-summary { color:#7f8fa6; } #rc-light .wf-table-prop { color:#7f8fa6; } #rc-light .wf-exec-pass { color:#2e7d32; } #rc-light .wf-exec-pending { color:#b0b0b0; } #rc-light [data-completed="true"] { background:#e8f5e9; } #rc-light .wf-exec-reason { color:#999; } #rc-light .wf-parallel { border-color:#c8e6c9; background:#f8fdf8; } #rc-light .wf-branch-label { color:#2e7d32; } #rc-light .wf-branch-node { background:#fff; border-color:#dde1e6; color:#555; } #rc-light .wf-branch-done { background:#e8f5e9; border-color:#4caf50; color:#2e7d32; } #rc-light .wf-branch-active { background:#e3f2fd; border-color:#2a6bcf; color:#1a1a2e; font-weight:600; } #rc-light .wf-dot-router { background:#e65100; } #rc-light .wf-dot-fork { background:#2e7d32; } #rc-light .wf-target { border-color:#e65100; color:#795548; } #rc-light .wf-target-done { background:#fff3e0; color:#e65100; } #rc-light .wf-target-active { background:#fff3e0; border-color:#e65100; color:#e65100; font-weight:600; } #rc-light .mb-node { background:#fff; border-color:#dde1e6; color:#555; } #rc-light .mb-current { background:#e3f2fd; border-color:#2a6bcf; color:#1a1a2e; font-weight:700; } #rc-light .mb-done { background:#e8f5e9; border-color:#4caf50; color:#2e7d32; } #rc-light .mb-router { border-color:#e65100; } #rc-light .mb-router.mb-done { border-color:#4caf50; } #rc-light .mb-fork { border-color:#2e7d32; } #rc-light .mb-fork.mb-done { border-color:#4caf50; }'
                ; document.head.appendChild(style); container = c;
        },
        update: function(state, msg, feedback) { _expDPage(container, state, msg, feedback, false); },
        activate: function() {}, deactivate: function() {}
    });
})();
(function() {
    var container;
    registerRenderer({
        id: 'light-verbose', label: 'Simple', format: 'simple',
        verbosity: 'verbose', verbosity_label: 'Verbose', style: 'light', style_label: 'Light',
        init: function(c) {
            c.style.cssText = 'overflow-y:auto;padding:0;';
            var style = document.createElement('style');
            style.textContent = WF_STRUCTURAL_CSS + EXP_D_FC_CSS
                + _scopeFC('#rc-light-verbose', EXP_D_FC_LIGHT)
                + '#rc-light-verbose { background:#f5f5f5; color:#333; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }'
                + '#rc-light-verbose .wf-title { color:#1a1a2e; } #rc-light-verbose .wf-banner { background:#f8f9fb; border-color:#e8e8e8; } #rc-light-verbose .wf-dot { background:#dde1e6; color:#888; } #rc-light-verbose .wf-step-label { color:#888; } #rc-light-verbose .wf-step-active .wf-dot { background:#2a6bcf; color:#fff; } #rc-light-verbose .wf-step-active .wf-step-label { color:#1a1a2e; font-weight:600; } #rc-light-verbose .wf-step-done .wf-dot { background:#4caf50; color:#fff; } #rc-light-verbose .wf-step-done .wf-step-label { color:#555; } #rc-light-verbose .wf-conn { background:#dde1e6; } #rc-light-verbose .wf-conn-active { background:#4caf50; } #rc-light-verbose .wf-section-head { color:#1a1a2e; } #rc-light-verbose .wf-desc { color:#666; } #rc-light-verbose .wf-card { background:#fff; border-color:#e8e8e8; } #rc-light-verbose .wf-card-head { color:#7f8fa6; } #rc-light-verbose .wf-tbl td { border-bottom:1px solid #f0f0f0; } #rc-light-verbose .wf-key { color:#7f8fa6; } #rc-light-verbose .wf-val { color:#333; } #rc-light-verbose .wf-null, #rc-light-verbose .wf-empty-arr, #rc-light-verbose .wf-empty-obj { color:#bbb; } #rc-light-verbose .wf-bool, #rc-light-verbose .wf-num { color:#2a6bcf; } #rc-light-verbose .wf-str { color:#333; } #rc-light-verbose .wf-arr-item { border-left-color:#e8e8e8; } #rc-light-verbose .wf-field { border-bottom:1px solid #f0f0f0; } #rc-light-verbose .wf-field-label { color:#555; } #rc-light-verbose .wf-field-instruction { color:#999; } #rc-light-verbose .wf-field-value { color:#333; } #rc-light-verbose .wf-field-empty { color:#bbb; } #rc-light-verbose .wf-field-options { color:#7f8fa6; } #rc-light-verbose .wf-aff { background:#f8f9fb; border-color:#e8e8e8; } #rc-light-verbose .wf-aff-id { background:#dde1e6; color:#555; } #rc-light-verbose .wf-aff-label { color:#333; } #rc-light-verbose .wf-aff-method { color:#7f8fa6; background:#eef1f5; } #rc-light-verbose .wf-aff-detail { color:#999; } #rc-light-verbose .wf-aff-options { color:#7f8fa6; } #rc-light-verbose .wf-aff-primary { border-color:#2a6bcf; background:#f0f5ff; } #rc-light-verbose .wf-aff-primary .wf-aff-label { color:#2a6bcf; font-weight:600; } #rc-light-verbose .wf-aff-primary .wf-aff-id { background:#2a6bcf; color:#fff; } #rc-light-verbose .wf-aff-nav { border-color:#dde1e6; background:#fafafa; } #rc-light-verbose .wf-aff-nav .wf-aff-label { color:#888; } #rc-light-verbose .wf-aff-selected { border-color:#4caf50; background:#f0fff0; } #rc-light-verbose .wf-aff-selected .wf-aff-label { color:#2e7d32; } #rc-light-verbose .wf-aff-selected .wf-aff-id { background:#4caf50; color:#fff; } #rc-light-verbose .wf-fb-outcome { border-left:3px solid #2a6bcf; background:#f0f5ff; } #rc-light-verbose .wf-fb-new { border-left:3px solid #4caf50; background:#f0faf0; } #rc-light-verbose .wf-fb-modified { border-left:3px solid #e6a817; background:#fdf8ed; } #rc-light-verbose .wf-aff-new { border-left:3px solid #4caf50; background:#f0faf0; } #rc-light-verbose .wf-aff-modified { border-left:3px solid #e6a817; background:#fdf8ed; } #rc-light-verbose .wf-tag-outcome { color:#2a6bcf; } #rc-light-verbose .wf-tag-new { color:#4caf50; } #rc-light-verbose .wf-tag-modified { color:#e6a817; } #rc-light-verbose .wf-table th { background:#f4f6f9; border-color:#e8e8e8; } #rc-light-verbose .wf-table td { border-color:#e8e8e8; } #rc-light-verbose .wf-table-rownum { color:#aaa; background:#fafbfc; } #rc-light-verbose .wf-table-coltype { color:#7f8fa6; } #rc-light-verbose .wf-table-empty { color:#bbb; } #rc-light-verbose .wf-table-summary { color:#7f8fa6; } #rc-light-verbose .wf-table-prop { color:#7f8fa6; } #rc-light-verbose .wf-exec-pass { color:#2e7d32; } #rc-light-verbose .wf-exec-pending { color:#b0b0b0; } #rc-light-verbose [data-completed="true"] { background:#e8f5e9; } #rc-light-verbose .wf-exec-reason { color:#999; }'
                ; document.head.appendChild(style); container = c;
        },
        update: function(state, msg, feedback) { _expDPage(container, state, msg, feedback, true); },
        activate: function() {}, deactivate: function() {}
    });
})();
(function() {
    var container;
    registerRenderer({
        id: 'dark', label: 'Simple', format: 'simple',
        verbosity: 'default', verbosity_label: 'Default', style: 'dark', style_label: 'Dark',
        init: function(c) {
            c.style.cssText = 'overflow-y:auto;padding:0;';
            var style = document.createElement('style');
            style.textContent = WF_STRUCTURAL_CSS + EXP_D_FC_CSS
                + _scopeFC('#rc-dark', EXP_D_FC_DARK)
                + '#rc-dark { background:#0e0e0e; color:#c8c8c8; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }'
                + '#rc-dark .wf-title { color:#e0e0e0; } #rc-dark .wf-banner { background:#1a1a1a; border-color:#2a2a2a; } #rc-dark .wf-dot { background:#333; color:#888; } #rc-dark .wf-step-label { color:#777; } #rc-dark .wf-step-active .wf-dot { background:#4a9eff; color:#fff; } #rc-dark .wf-step-active .wf-step-label { color:#e0e0e0; font-weight:600; } #rc-dark .wf-step-done .wf-dot { background:#4caf50; color:#fff; } #rc-dark .wf-step-done .wf-step-label { color:#888; } #rc-dark .wf-conn { background:#333; } #rc-dark .wf-conn-active { background:#4caf50; } #rc-dark .wf-section-head { color:#e0e0e0; } #rc-dark .wf-desc { color:#999; } #rc-dark .wf-card { background:#141414; border-color:#2a2a2a; } #rc-dark .wf-card-head { color:#666; } #rc-dark .wf-tbl td { border-bottom:1px solid #1e1e1e; } #rc-dark .wf-key { color:#666; } #rc-dark .wf-val { color:#c8c8c8; } #rc-dark .wf-null, #rc-dark .wf-empty-arr, #rc-dark .wf-empty-obj { color:#555; } #rc-dark .wf-bool, #rc-dark .wf-num { color:#4a9eff; } #rc-dark .wf-str { color:#c8c8c8; } #rc-dark .wf-arr-item { border-left-color:#2a2a2a; } #rc-dark .wf-field { border-bottom:1px solid #1e1e1e; } #rc-dark .wf-field-label { color:#999; } #rc-dark .wf-field-instruction { color:#666; } #rc-dark .wf-field-value { color:#c8c8c8; } #rc-dark .wf-field-empty { color:#555; } #rc-dark .wf-field-options { color:#666; } #rc-dark .wf-aff { background:#1a1a1a; border-color:#2a2a2a; } #rc-dark .wf-aff-id { background:#333; color:#aaa; } #rc-dark .wf-aff-label { color:#c8c8c8; } #rc-dark .wf-aff-method { color:#666; background:#1e1e1e; } #rc-dark .wf-aff-detail { color:#555; } #rc-dark .wf-aff-options { color:#666; } #rc-dark .wf-aff-primary { border-color:#4a9eff; background:#0d1a2e; } #rc-dark .wf-aff-primary .wf-aff-label { color:#4a9eff; font-weight:600; } #rc-dark .wf-aff-primary .wf-aff-id { background:#4a9eff; color:#fff; } #rc-dark .wf-aff-nav { border-color:#2a2a2a; background:#111; } #rc-dark .wf-aff-nav .wf-aff-label { color:#666; } #rc-dark .wf-aff-selected { border-color:#4caf50; background:#0d1a0d; } #rc-dark .wf-aff-selected .wf-aff-label { color:#4caf50; } #rc-dark .wf-aff-selected .wf-aff-id { background:#4caf50; color:#fff; } #rc-dark .wf-fb-outcome { border-left:3px solid #4a9eff; background:#0d1a2e; } #rc-dark .wf-fb-new { border-left:3px solid #4caf50; background:#0d1a0d; } #rc-dark .wf-fb-modified { border-left:3px solid #e6a817; background:#1a1500; } #rc-dark .wf-aff-new { border-left:3px solid #4caf50; background:#0d1a0d; } #rc-dark .wf-aff-modified { border-left:3px solid #e6a817; background:#1a1500; } #rc-dark .wf-tag-outcome { color:#4a9eff; } #rc-dark .wf-tag-new { color:#4caf50; } #rc-dark .wf-tag-modified { color:#e6a817; } #rc-dark .wf-table th { background:#1a1a1a; border-color:#2a2a2a; } #rc-dark .wf-table td { border-color:#2a2a2a; } #rc-dark .wf-table-rownum { color:#555; background:#141414; } #rc-dark .wf-table-coltype { color:#666; } #rc-dark .wf-table-empty { color:#555; } #rc-dark .wf-table-summary { color:#666; } #rc-dark .wf-table-prop { color:#666; } #rc-dark .wf-exec-pass { color:#66bb6a; } #rc-dark .wf-exec-pending { color:#666; } #rc-dark [data-completed="true"] { background:#1b3a1b; } #rc-dark .wf-exec-reason { color:#666; }'
                ; document.head.appendChild(style); container = c;
        },
        update: function(state, msg, feedback) { _expDPage(container, state, msg, feedback, false); },
        activate: function() {}, deactivate: function() {}
    });
})();
(function() {
    var container;
    registerRenderer({
        id: 'dark-verbose', label: 'Simple', format: 'simple',
        verbosity: 'verbose', verbosity_label: 'Verbose', style: 'dark', style_label: 'Dark',
        init: function(c) {
            c.style.cssText = 'overflow-y:auto;padding:0;';
            var style = document.createElement('style');
            style.textContent = WF_STRUCTURAL_CSS + EXP_D_FC_CSS
                + _scopeFC('#rc-dark-verbose', EXP_D_FC_DARK)
                + '#rc-dark-verbose { background:#0e0e0e; color:#c8c8c8; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }'
                + '#rc-dark-verbose .wf-title { color:#e0e0e0; } #rc-dark-verbose .wf-banner { background:#1a1a1a; border-color:#2a2a2a; } #rc-dark-verbose .wf-dot { background:#333; color:#888; } #rc-dark-verbose .wf-step-label { color:#777; } #rc-dark-verbose .wf-step-active .wf-dot { background:#4a9eff; color:#fff; } #rc-dark-verbose .wf-step-active .wf-step-label { color:#e0e0e0; font-weight:600; } #rc-dark-verbose .wf-step-done .wf-dot { background:#4caf50; color:#fff; } #rc-dark-verbose .wf-step-done .wf-step-label { color:#888; } #rc-dark-verbose .wf-conn { background:#333; } #rc-dark-verbose .wf-conn-active { background:#4caf50; } #rc-dark-verbose .wf-section-head { color:#e0e0e0; } #rc-dark-verbose .wf-desc { color:#999; } #rc-dark-verbose .wf-card { background:#141414; border-color:#2a2a2a; } #rc-dark-verbose .wf-card-head { color:#666; } #rc-dark-verbose .wf-tbl td { border-bottom:1px solid #1e1e1e; } #rc-dark-verbose .wf-key { color:#666; } #rc-dark-verbose .wf-val { color:#c8c8c8; } #rc-dark-verbose .wf-null, #rc-dark-verbose .wf-empty-arr, #rc-dark-verbose .wf-empty-obj { color:#555; } #rc-dark-verbose .wf-bool, #rc-dark-verbose .wf-num { color:#4a9eff; } #rc-dark-verbose .wf-str { color:#c8c8c8; } #rc-dark-verbose .wf-arr-item { border-left-color:#2a2a2a; } #rc-dark-verbose .wf-field { border-bottom:1px solid #1e1e1e; } #rc-dark-verbose .wf-field-label { color:#999; } #rc-dark-verbose .wf-field-instruction { color:#666; } #rc-dark-verbose .wf-field-value { color:#c8c8c8; } #rc-dark-verbose .wf-field-empty { color:#555; } #rc-dark-verbose .wf-field-options { color:#666; } #rc-dark-verbose .wf-aff { background:#1a1a1a; border-color:#2a2a2a; } #rc-dark-verbose .wf-aff-id { background:#333; color:#aaa; } #rc-dark-verbose .wf-aff-label { color:#c8c8c8; } #rc-dark-verbose .wf-aff-method { color:#666; background:#1e1e1e; } #rc-dark-verbose .wf-aff-detail { color:#555; } #rc-dark-verbose .wf-aff-options { color:#666; } #rc-dark-verbose .wf-aff-primary { border-color:#4a9eff; background:#0d1a2e; } #rc-dark-verbose .wf-aff-primary .wf-aff-label { color:#4a9eff; font-weight:600; } #rc-dark-verbose .wf-aff-primary .wf-aff-id { background:#4a9eff; color:#fff; } #rc-dark-verbose .wf-aff-nav { border-color:#2a2a2a; background:#111; } #rc-dark-verbose .wf-aff-nav .wf-aff-label { color:#666; } #rc-dark-verbose .wf-aff-selected { border-color:#4caf50; background:#0d1a0d; } #rc-dark-verbose .wf-aff-selected .wf-aff-label { color:#4caf50; } #rc-dark-verbose .wf-aff-selected .wf-aff-id { background:#4caf50; color:#fff; } #rc-dark-verbose .wf-fb-outcome { border-left:3px solid #4a9eff; background:#0d1a2e; } #rc-dark-verbose .wf-fb-new { border-left:3px solid #4caf50; background:#0d1a0d; } #rc-dark-verbose .wf-fb-modified { border-left:3px solid #e6a817; background:#1a1500; } #rc-dark-verbose .wf-aff-new { border-left:3px solid #4caf50; background:#0d1a0d; } #rc-dark-verbose .wf-aff-modified { border-left:3px solid #e6a817; background:#1a1500; } #rc-dark-verbose .wf-tag-outcome { color:#4a9eff; } #rc-dark-verbose .wf-tag-new { color:#4caf50; } #rc-dark-verbose .wf-tag-modified { color:#e6a817; } #rc-dark-verbose .wf-table th { background:#1a1a1a; border-color:#2a2a2a; } #rc-dark-verbose .wf-table td { border-color:#2a2a2a; } #rc-dark-verbose .wf-table-rownum { color:#555; background:#141414; } #rc-dark-verbose .wf-table-coltype { color:#666; } #rc-dark-verbose .wf-table-empty { color:#555; } #rc-dark-verbose .wf-table-summary { color:#666; } #rc-dark-verbose .wf-table-prop { color:#666; } #rc-dark-verbose .wf-exec-pass { color:#66bb6a; } #rc-dark-verbose .wf-exec-pending { color:#666; } #rc-dark-verbose [data-completed="true"] { background:#1b3a1b; } #rc-dark-verbose .wf-exec-reason { color:#666; }'
                ; document.head.appendChild(style); container = c;
        },
        update: function(state, msg, feedback) { _expDPage(container, state, msg, feedback, true); },
        activate: function() {}, deactivate: function() {}
    });
})();
