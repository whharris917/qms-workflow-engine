// ═══════════════════════════════════════════════════════════════════
// Element Library Workshop
// Canonical representations and renderings of UI elements.
// Isolated — no dependencies on engine code.
//
// Architecture:
//   Every element sits inside a CONTAINER — a generic wrapper that
//   provides focus/addressing/dimming. The element renders itself
//   and its own affordances. The container provides structural
//   focus controls (Focus / Focus All / Unfocus).
//
//   The container does not know what's inside it.
//   The element does not know about focus.
//
//   Focus state is a sparse map: { path → mode }. Modes:
//     collapsed  — summary (one-line)
//     focused    — full element, children collapsed
//     focused_all — full element, children recursively expanded
// ═══════════════════════════════════════════════════════════════════

(function () {
  "use strict";

  // ═══════════════════════════════════════════════════════════════
  // RENDERER REGISTRY
  // ═══════════════════════════════════════════════════════════════

  var RENDERERS = {};

  function renderElement(data, path) {
    if (!path) path = [];
    var type = data && data.element;
    var fn = type && RENDERERS[type];
    if (fn) return fn(data, path);
    var t = type ? esc(type) : "(missing)";
    return '<div class="el-error">'
      + '<div class="el-error-type">Unrenderable: element=' + t + '</div>'
      + '<div class="el-error-msg">No renderer for <strong>' + t + '</strong>.</div></div>';
  }

  // ═══════════════════════════════════════════════════════════════
  // CONTAINER
  // The generic wrapper that provides focus functionality.
  // Every element in the tree is rendered through this.
  // ═══════════════════════════════════════════════════════════════

  function renderContainer(node, path, focusMap) {
    var cp = path.join(".");
    var mode = resolveFocusMode(cp, focusMap);
    var isGroup = node && node.element === "group" && node.children && node.children.length;
    var isInline = isGroup && node.inline;

    // Inline groups skip the container machinery — always fully expanded
    if (isInline) {
      return renderGroupInner(node, path, focusMap, true);
    }

    if (mode === "collapsed") {
      var summary = makeSummary(node);
      var btns = focusBtn(cp, "focused", "Focus");
      if (isGroup) btns += focusBtn(cp, "focused_all", "Focus All");
      return '<div class="el-container el-container-collapsed">'
        + '<div class="el-container-summary">' + summary + '</div>'
        + '<div class="el-container-bar">' + btns + '</div></div>';
    }

    // Focused or focused_all — render the element in full
    var inner;

    if (isGroup) {
      inner = renderGroupInner(node, path, focusMap, mode === "focused_all");
    } else {
      inner = renderElement(node, path);
    }

    var unfocus = unfocusBtn(cp);
    var extraBtn = (mode === "focused" && isGroup) ? focusBtn(cp, "focused_all", "Focus All") : "";

    return '<div class="el-container el-container-' + mode + '">'
      + '<div class="el-container-bar">' + unfocus + extraBtn + '</div>'
      + inner + '</div>';
  }

  /** Render a group's interior: label + children.
   *  If allExpanded, children render via renderElement (no containers).
   *  Otherwise, children render via renderContainer (each gets focus controls). */
  function renderGroupInner(node, path, focusMap, allExpanded) {
    var h = '<div class="el-group">';
    if (node.label) h += rn(path, "label", '<div class="el-group-label">' + esc(node.label) + '</div>');
    h += '<div class="el-group-children">';
    node.children.forEach(function (child, i) {
      var childPath = path.concat("children", String(i));
      if (allExpanded) {
        // Inline/Focus All: render element directly, but recurse for nested groups
        if (child.element === "group" && child.children) {
          h += renderGroupInner(child, childPath, focusMap, true);
        } else {
          h += renderElement(child, childPath);
        }
      } else {
        h += renderContainer(child, childPath, focusMap);
      }
    });
    return h + '</div></div>';
  }

  // ── Focus map resolution ──────────────────────────────────────

  function resolveFocusMode(cp, focusMap) {
    // Explicit entry
    if (focusMap.hasOwnProperty(cp)) return focusMap[cp];
    // Root default
    if (cp === "") return "focused";
    // Walk up to find nearest ancestor
    var parts = cp.split(".");
    for (var i = parts.length - 1; i >= 0; i--) {
      var ancestor = parts.slice(0, i).join(".");
      if (focusMap.hasOwnProperty(ancestor)) {
        var parentMode = focusMap[ancestor];
        if (parentMode === "focused_all") return "focused_all";
        if (parentMode === "focused") return "collapsed";
        return "collapsed";
      }
    }
    return "collapsed";
  }

  // ── Container affordance buttons ──────────────────────────────

  function focusBtn(cp, mode, label) {
    var body = JSON.stringify({ path: cp, mode: mode });
    return '<button class="el-ctn-btn el-ctn-focus"'
      + ' data-aff-method="POST" data-aff-url="/focus"'
      + ' data-aff-body="' + escA(body) + '"'
      + ' data-aff-key="__focus__"'
      + ' data-aff-value="' + escA(body) + '">'
      + esc(label) + '</button>';
  }

  function unfocusBtn(cp) {
    var body = JSON.stringify({ path: cp, mode: "collapsed" });
    return '<button class="el-ctn-btn el-ctn-unfocus"'
      + ' data-aff-method="POST" data-aff-url="/focus"'
      + ' data-aff-body="' + escA(body) + '"'
      + ' data-aff-key="__focus__"'
      + ' data-aff-value="' + escA(body) + '">'
      + 'Unfocus</button>';
  }

  // ── Summary (collapsed representation) ────────────────────────

  function makeSummary(node) {
    var label = node.label || node.key || (node.element || "?");
    var type = node.element || "?";
    var preview = "";
    if (node.element === "field" && node.value != null) {
      preview = typeof node.value === "boolean" ? (node.value ? "True" : "False") : String(node.value);
    } else if (node.element === "group" && node.children) {
      preview = node.children.length + " items";
    } else if (node.element === "note" && node.text) {
      preview = node.text.length > 50 ? node.text.substring(0, 50) + "\u2026" : node.text;
    } else if (node.element === "badge") {
      preview = String(node.value);
    } else if (node.element === "action") {
      preview = node.label;
    }
    return '<span class="el-summary-type">' + esc(type) + '</span>'
      + '<span class="el-summary-label">' + esc(label) + '</span>'
      + (preview ? '<span class="el-summary-preview">' + esc(preview) + '</span>' : '');
  }

  // ═══════════════════════════════════════════════════════════════
  // RENDERERS (elements — no focus knowledge)
  // ═══════════════════════════════════════════════════════════════

  RENDERERS["field"] = function (f, path) {
    var h = '<div class="el-field">';
    h += rn(path, "label", '<div class="el-field-label">' + esc(f.label) + '</div>');
    if (f.instruction) h += rn(path, "instruction", '<div class="el-field-instruction">' + esc(f.instruction) + '</div>');
    var vc = "el-field-value" + (f.value === null ? " empty" : "");
    h += rn(path, "value", '<div class="' + vc + '">' + fmtVal(f.type, f.value) + '</div>');
    if (f.affordance) h += rn(path, "affordance", '<div class="el-aff">' + fieldAff(f, path) + '</div>');
    return h + '</div>';
  };

  function fmtVal(t, v) {
    if (v === null) return "Not set";
    if (t === "boolean") return v ? '<span style="color:#2e7d32;font-weight:600">True</span>' : '<span style="color:#c62828;font-weight:600">False</span>';
    if (t === "computed") return '<span style="color:#555;font-style:italic">' + esc(v) + '</span>';
    return esc(String(v));
  }

  function fieldAff(f, path) {
    var a = f.affordance, pr = a.parameters;
    var at = ' data-aff-method="' + escA(a.method) + '" data-aff-url="' + escA(a.url) + '"'
      + ' data-aff-body="' + escA(JSON.stringify(a.body)) + '" data-aff-key="' + escA(f.key) + '"';
    if (pr && pr.value && pr.value.options) {
      var btns = "";
      pr.value.options.forEach(function (o) {
        var act = String(o) === String(f.value), cls = "el-aff-opt" + (act ? " active" : "");
        var lab = typeof o === "boolean" ? (o ? "True" : "False") : esc(String(o));
        btns += '<button class="' + cls + '"' + at + ' data-aff-value="' + escA(JSON.stringify(o)) + '">' + lab + '</button>';
      });
      return '<div class="el-aff-row">' + btns + '</div>';
    }
    var ph = f.value !== null ? String(f.value) : f.label;
    return '<div class="el-aff-row"><input class="el-aff-input" type="text" placeholder="' + escA(ph) + '">'
      + '<button class="el-aff-btn"' + at + '>Set</button></div>';
  }

  RENDERERS["group"] = function (g, path) {
    // When rendered directly (Focus All mode, no container intervention),
    // render label + children via renderElement (not container).
    var h = '<div class="el-group">';
    if (g.label) h += rn(path, "label", '<div class="el-group-label">' + esc(g.label) + '</div>');
    h += '<div class="el-group-children">';
    if (g.children) g.children.forEach(function (c, i) {
      h += rn(path, "children." + i, renderElement(c, path.concat("children", "" + i)));
    });
    return h + '</div></div>';
  };

  RENDERERS["action"] = function (a, path) {
    var v = a.variant || "secondary";
    var at = ' data-aff-method="' + escA(a.method) + '" data-aff-url="' + escA(a.url) + '"'
      + ' data-aff-body="' + escA(JSON.stringify(a.body || {})) + '"'
      + ' data-aff-key="__action__" data-aff-value="' + escA(JSON.stringify(a.label)) + '"';
    return '<div class="el-action">' + rn(path, "label",
      '<button class="el-action-btn ' + v + '"' + at + '>' + esc(a.label) + '</button>') + '</div>';
  };

  RENDERERS["badge"] = function (b, path) {
    var v = b.variant || "info";
    return '<div class="el-badge ' + v + '">'
      + (b.label ? rn(path, "label", '<span class="el-badge-label">' + esc(b.label) + ':</span>') : '')
      + rn(path, "value", '<span>' + esc(String(b.value)) + '</span>') + '</div>';
  };

  RENDERERS["note"] = function (n, path) {
    return rn(path, "text", '<div class="el-note">' + esc(n.text) + '</div>');
  };

  // ═══════════════════════════════════════════════════════════════
  // HUMAN OBSERVER
  // Full rendering of everything, dimming based on focus map.
  // ═══════════════════════════════════════════════════════════════

  function renderHumanObserver(state) {
    return renderHumanNode(deepCopy(state.data), [], state.focus, "");
  }

  function renderHumanNode(node, path, focusMap, cp) {
    if (!node || typeof node !== "object") return "";
    var type = node.element, fn = type && RENDERERS[type], html;

    if (type === "group" && node.children) {
      html = '<div class="el-group">';
      if (node.label) html += '<div class="el-group-label">' + esc(node.label) + '</div>';
      html += '<div class="el-group-children">';
      node.children.forEach(function (c, i) {
        var childCp = cp ? cp + ".children." + i : "children." + i;
        html += renderHumanNode(c, path.concat("children", "" + i), focusMap, childCp);
      });
      html += '</div></div>';
    } else if (fn) {
      html = fn(node, path);
    } else {
      html = renderElement(node, path);
    }

    var mode = resolveFocusMode(cp, focusMap);
    var dim = (mode === "collapsed") ? "ho-dimmed" : "ho-focused";
    return '<div class="' + dim + '">' + html + '</div>';
  }

  // ═══════════════════════════════════════════════════════════════
  // UTILITIES
  // ═══════════════════════════════════════════════════════════════

  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  function escA(s) { return String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;"); }
  function rn(bp, sf, inner) { return '<span class="r-node" data-path="' + escA(bp.concat(sf.split(".")).join(".")) + '">' + inner + '</span>'; }
  function deepCopy(o) { return JSON.parse(JSON.stringify(o)); }

  // ═══════════════════════════════════════════════════════════════
  // AGENT DATA PROJECTION
  // Produces a reduced JSON matching the current focus level.
  // Collapsed → one-line summary. Focused → full detail.
  // Focused All → full detail recursively.
  // ═══════════════════════════════════════════════════════════════

  function projectAgentData(node, path, focusMap) {
    var cp = path.join(".");
    var isGroup = node.element === "group" && node.children;
    var isInline = isGroup && node.inline;
    var mode = isInline ? "focused_all" : resolveFocusMode(cp, focusMap);

    if (mode === "collapsed") {
      // Minimal summary — just enough to identify and navigate
      var s = { _collapsed: true, element: node.element };
      if (node.label) s.label = node.label;
      else if (node.key) s.label = node.key;
      if (node.element === "field" && node.value != null) s.value = node.value;
      if (isGroup) s.children_count = node.children.length;
      if (node.element === "badge") s.value = node.value;
      s.focus = { method: "POST", url: "/focus", body: { path: cp, mode: "focused" } };
      if (isGroup) {
        s.focus_all = { method: "POST", url: "/focus", body: { path: cp, mode: "focused_all" } };
      }
      return s;
    }

    // Focused or focused_all — show full element data
    if (isGroup) {
      var g = { element: "group" };
      if (node.label) g.label = node.label;
      if (!isInline) {
        g.unfocus = { method: "POST", url: "/focus", body: { path: cp, mode: "collapsed" } };
        if (mode === "focused") {
          g.focus_all = { method: "POST", url: "/focus", body: { path: cp, mode: "focused_all" } };
        }
      }
      g.children = node.children.map(function (child, i) {
        return projectAgentData(child, path.concat("children", "" + i), focusMap);
      });
      return g;
    }

    // Leaf element — copy relevant data, strip internal fields
    var copy = {};
    Object.keys(node).forEach(function (k) {
      if (k[0] !== "_") copy[k] = node[k];
    });
    if (cp !== "") {
      copy.unfocus = { method: "POST", url: "/focus", body: { path: cp, mode: "collapsed" } };
    }
    return copy;
  }

  // ═══════════════════════════════════════════════════════════════
  // JSON SYNTAX HIGHLIGHTING
  // ═══════════════════════════════════════════════════════════════

  function jsonToHtml(v, p, ind) {
    if (ind === undefined) ind = 0; if (!p) p = [];
    var pad = "  ".repeat(ind), pad1 = "  ".repeat(ind + 1);
    if (v === null) return sp("j-null", "null");
    if (typeof v === "boolean") return sp("j-bool", String(v));
    if (typeof v === "number") return sp("j-num", String(v));
    if (typeof v === "string") return sp("j-str", '"' + esc(v) + '"');
    if (Array.isArray(v)) {
      if (!v.length) return sp("j-brace", "[]");
      var o = sp("j-brace", "[") + "\n";
      v.forEach(function (it, i) { var q = p.concat("" + i); o += je(q, pad1 + jsonToHtml(it, q, ind + 1) + (i < v.length - 1 ? "," : "")) + "\n"; });
      return o + pad + sp("j-brace", "]");
    }
    var ks = Object.keys(v);
    if (!ks.length) return sp("j-brace", "{}");
    var o = sp("j-brace", "{") + "\n";
    ks.forEach(function (k, i) { var q = p.concat(k); o += je(q, pad1 + sp("j-key", '"' + esc(k) + '"') + ": " + jsonToHtml(v[k], q, ind + 1) + (i < ks.length - 1 ? "," : "")) + "\n"; });
    return o + pad + sp("j-brace", "}");
  }
  function sp(c, t) { return '<span class="' + c + '">' + t + '</span>'; }
  function je(p, inner) { return '<span class="j-entry" data-path="' + escA(p.join(".")) + '">' + inner + '</span>'; }

  // ═══════════════════════════════════════════════════════════════
  // AFFORDANCE HANDLER + TOOLTIP
  // ═══════════════════════════════════════════════════════════════

  function resolveAff(btn) {
    var method = btn.getAttribute("data-aff-method"), url = btn.getAttribute("data-aff-url"),
      bt = JSON.parse(btn.getAttribute("data-aff-body")), val;
    if (btn.hasAttribute("data-aff-value")) val = JSON.parse(btn.getAttribute("data-aff-value"));
    else { var inp = btn.closest(".el-aff-row"); inp = inp && inp.querySelector(".el-aff-input"); val = inp ? inp.value : null; }
    var body = {};
    Object.keys(bt).forEach(function (k) { body[k] = bt[k] === "{input}" ? val : bt[k]; });
    return { method: method, url: url, body: body };
  }

  function applyMutation(state, key, body) {
    if (key === "__focus__") {
      // Container focus mutation: { path, mode }
      var p = body.path !== undefined ? body.path : "";
      var m = body.mode || "collapsed";
      if (m === "collapsed") {
        // Remove all descendant entries first (they collapse with us)
        Object.keys(state.focus).forEach(function (k) {
          if (k.indexOf(p + ".") === 0) delete state.focus[k];
        });
        // Delete our own entry, then check what we'd inherit.
        // If inheritance would give us something other than collapsed,
        // we must store an explicit "collapsed" to override.
        delete state.focus[p];
        var inherited = resolveFocusMode(p, state.focus);
        if (inherited !== "collapsed") {
          state.focus[p] = "collapsed";
        }
      } else {
        state.focus[p] = m;
        // If focusing_all, remove explicit descendant entries (they inherit)
        if (m === "focused_all") {
          Object.keys(state.focus).forEach(function (k) {
            if (k !== p && k.indexOf(p + ".") === 0) delete state.focus[k];
          });
        }
      }
      // Ensure root stays focused
      if (!state.focus.hasOwnProperty("")) state.focus[""] = "focused";
      return;
    }
    if (body.value !== undefined) {
      applyFieldMut(state.data, key, body.value);
    }
  }

  function applyFieldMut(node, key, val) {
    if (node.element === "field" && node.key === key) { node.value = val; return true; }
    if (node.children) { for (var i = 0; i < node.children.length; i++) { if (applyFieldMut(node.children[i], key, val)) return true; } }
    return false;
  }

  function setupHandler(renderEl, getState, rerender) {
    renderEl.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-aff-url]"); if (!btn) return;
      var r = resolveAff(btn);
      fetch(r.url, { method: r.method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(r.body) });
      var key = btn.getAttribute("data-aff-key"), state = getState();
      applyMutation(state, key, r.body);
      rerender();
    });

    var tip = document.createElement("div"); tip.className = "el-aff-tooltip"; tip.style.display = "none";
    document.body.appendChild(tip);
    renderEl.addEventListener("mouseover", function (e) {
      var btn = e.target.closest("[data-aff-url]");
      if (!btn) { tip.style.display = "none"; return; }
      tip.innerHTML = fmtTip(resolveAff(btn)); tip.style.display = "block"; posTip(tip, e);
    });
    renderEl.addEventListener("mousemove", function (e) { if (tip.style.display === "block") posTip(tip, e); });
    renderEl.addEventListener("mouseleave", function () { tip.style.display = "none"; });
  }

  function posTip(tip, e) {
    var x = e.clientX + 12, y = e.clientY + 12, r = tip.getBoundingClientRect();
    if (x + r.width > window.innerWidth - 8) x = e.clientX - r.width - 8;
    if (y + r.height > window.innerHeight - 8) y = e.clientY - r.height - 8;
    tip.style.left = x + "px"; tip.style.top = y + "px";
  }

  function fmtTip(r) {
    var s = '<span class="tt-method">' + esc(r.method) + '</span> <span class="tt-url">' + esc(r.url) + '</span>\n';
    var ks = Object.keys(r.body);
    s += sp("tt-brace", "{") + "\n";
    ks.forEach(function (k, i) {
      var v = r.body[k], vh;
      if (typeof v === "string") vh = '<span class="tt-str">"' + esc(v) + '"</span>';
      else if (typeof v === "boolean") vh = '<span class="tt-val">' + v + '</span>';
      else if (v === null) vh = '<span class="tt-val">null</span>';
      else vh = '<span class="tt-val">' + esc(JSON.stringify(v)) + '</span>';
      s += '  <span class="tt-key">"' + esc(k) + '"</span>: ' + vh + (i < ks.length - 1 ? "," : "") + "\n";
    });
    return s + sp("tt-brace", "}");
  }

  // ═══════════════════════════════════════════════════════════════
  // CROSS-HIGHLIGHTING
  // ═══════════════════════════════════════════════════════════════

  function setupHL(jsonEl, renderEl) {
    var ae = [], an = [];
    jsonEl.addEventListener("mouseover", function (e) {
      var ent = e.target.closest(".j-entry"); if (!ent) return;
      var path = ent.getAttribute("data-path"); if (!path) return;
      clearHL(); ent.classList.add("j-hl"); ae.push(ent);
      renderEl.querySelectorAll(".r-node[data-path]").forEach(function (n) {
        var np = n.getAttribute("data-path");
        if (np === path || np.indexOf(path + ".") === 0 || path.indexOf(np + ".") === 0) { n.classList.add("r-hl"); an.push(n); }
      });
    });
    jsonEl.addEventListener("mouseleave", clearHL);
    function clearHL() { ae.forEach(function (e) { e.classList.remove("j-hl"); }); an.forEach(function (e) { e.classList.remove("r-hl"); }); ae = []; an = []; }
  }

  // ═══════════════════════════════════════════════════════════════
  // SPECIMENS
  // focus is now a sparse map: { path → mode }
  // ═══════════════════════════════════════════════════════════════

  var SPECIMENS = {

    "Field: Text": {
      focus: { "": "focused" },
      data: {
        element: "field", key: "equipment_id", type: "text",
        label: "Equipment ID", instruction: "Enter the unique identifier from the asset registry.",
        value: "EQ-2041",
        affordance: { method: "POST", url: "/fields/equipment_id", body: { value: "{input}" } }
      }
    },

    "Field: Boolean": {
      focus: { "": "focused" },
      data: {
        element: "field", key: "in_tolerance", type: "boolean",
        label: "In Tolerance", instruction: "Was the measurement within acceptable tolerance?",
        value: true,
        affordance: { method: "POST", url: "/fields/in_tolerance", body: { value: "{input}" },
          parameters: { value: { options: [true, false] } } }
      }
    },

    "Field: Select": {
      focus: { "": "focused" },
      data: {
        element: "field", key: "priority", type: "select",
        label: "Priority", instruction: "Set the review priority level.", value: "High",
        affordance: { method: "POST", url: "/fields/priority", body: { value: "{input}" },
          parameters: { value: { options: ["Critical", "High", "Medium", "Low"] } } }
      }
    },

    "Field: Computed": {
      focus: { "": "focused" },
      data: {
        element: "field", key: "days_overdue", type: "computed",
        label: "Days Overdue", instruction: "Calculated from calibration due date.", value: 12, affordance: null
      }
    },

    "Group: Calibration": {
      focus: { "": "focused" },
      data: {
        element: "group", label: "Calibration Details",
        children: [
          { element: "field", key: "equipment_id", type: "text", label: "Equipment ID", instruction: null, value: "EQ-2041",
            affordance: { method: "POST", url: "/fields/equipment_id", body: { value: "{input}" } } },
          { element: "field", key: "location", type: "text", label: "Location", instruction: null, value: "Building 7, Lab 3",
            affordance: { method: "POST", url: "/fields/location", body: { value: "{input}" } } },
          { element: "field", key: "in_tolerance", type: "boolean", label: "In Tolerance", instruction: null, value: true,
            affordance: { method: "POST", url: "/fields/in_tolerance", body: { value: "{input}" },
              parameters: { value: { options: [true, false] } } } },
          { element: "field", key: "days_overdue", type: "computed", label: "Days Overdue", instruction: null, value: 12, affordance: null }
        ]
      }
    },

    "Group: With Unknown": {
      focus: { "": "focused" },
      data: {
        element: "group", label: "Mixed Elements",
        children: [
          { element: "field", key: "status", type: "select", label: "Status", instruction: null, value: "In Progress",
            affordance: { method: "POST", url: "/fields/status", body: { value: "{input}" },
              parameters: { value: { options: ["Draft", "In Progress", "Complete"] } } } },
          { element: "chart", chart_type: "bar", data: [10, 25, 15, 30], labels: ["Q1", "Q2", "Q3", "Q4"] },
          { element: "field", key: "notes", type: "text", label: "Notes", instruction: null, value: null,
            affordance: { method: "POST", url: "/fields/notes", body: { value: "{input}" } } },
          { element: "timeline", events: [{ date: "2026-01-15", label: "Created" }, { date: "2026-03-01", label: "Reviewed" }] }
        ]
      }
    },

    "Unknown Element": {
      focus: { "": "focused" },
      data: { element: "sparkline", data: [3, 7, 2, 9, 4], color: "#1976d2" }
    },

    "Demo: Calibration Review": {
      focus: { "": "focused" },
      data: {
        element: "group", label: "Equipment Calibration Review",
        children: [
          { element: "group", label: "Header", inline: true, children: [
            { element: "field", key: "title", type: "text", label: "Title", instruction: null,
              value: "Annual Calibration \u2014 Pressure Transducer PT-207", affordance: null },
            { element: "badge", label: "Status", value: "In Review", variant: "info" },
            { element: "field", key: "priority", type: "select", label: "Priority", instruction: "Review priority level.", value: "High",
              affordance: { method: "POST", url: "/fields/priority", body: { value: "{input}" },
                parameters: { value: { options: ["Critical", "High", "Medium", "Low"] } } } },
            { element: "field", key: "assigned_to", type: "text", label: "Assigned To", instruction: null, value: "J. Martinez",
              affordance: { method: "POST", url: "/fields/assigned_to", body: { value: "{input}" } } }
          ]},
          { element: "group", label: "Equipment Details", children: [
            { element: "field", key: "equipment_id", type: "text", label: "Equipment ID",
              instruction: "Unique identifier from the asset registry.", value: "EQ-2041",
              affordance: { method: "POST", url: "/fields/equipment_id", body: { value: "{input}" } } },
            { element: "field", key: "serial_number", type: "text", label: "Serial Number",
              instruction: "Factory serial. Not editable.", value: "SN-80412-X", affordance: null },
            { element: "field", key: "location", type: "text", label: "Location", instruction: null, value: "Building 7, Lab 3",
              affordance: { method: "POST", url: "/fields/location", body: { value: "{input}" } } },
            { element: "field", key: "last_calibrated", type: "text", label: "Last Calibrated", instruction: null,
              value: "2025-10-12", affordance: null }
          ]},
          { element: "group", label: "Measurements", children: [
            { element: "field", key: "in_tolerance", type: "boolean", label: "In Tolerance",
              instruction: "Was the measurement within acceptable tolerance?", value: true,
              affordance: { method: "POST", url: "/fields/in_tolerance", body: { value: "{input}" },
                parameters: { value: { options: [true, false] } } } },
            { element: "field", key: "drift_pct", type: "computed", label: "Drift",
              instruction: "Calculated from reference standard.", value: "+0.3%", affordance: null },
            { element: "chart", chart_type: "line", title: "Drift Over Time",
              data: [0.1, 0.15, 0.2, 0.25, 0.3], labels: ["2024-Q1", "2024-Q3", "2025-Q1", "2025-Q3", "2026-Q1"] },
            { element: "field", key: "interval", type: "select", label: "Recommended Interval",
              instruction: "Recalibration interval based on drift trend.", value: "6 months",
              affordance: { method: "POST", url: "/fields/interval", body: { value: "{input}" },
                parameters: { value: { options: ["3 months", "6 months", "Annual", "Biennial"] } } } }
          ]},
          { element: "group", label: "Review", children: [
            { element: "note", text: "Instrument drift observed at +0.3% \u2014 within spec but trending upward. Recommend shortened recalibration interval. Verify against reference standard PT-REF-003 before next cycle." },
            { element: "field", key: "requires_followup", type: "boolean", label: "Requires Follow-up", instruction: null, value: null,
              affordance: { method: "POST", url: "/fields/requires_followup", body: { value: "{input}" },
                parameters: { value: { options: [true, false] } } } },
            { element: "field", key: "disposition", type: "select", label: "Disposition",
              instruction: "Final disposition after review.", value: null,
              affordance: { method: "POST", url: "/fields/disposition", body: { value: "{input}" },
                parameters: { value: { options: ["Approve", "Reject", "Defer", "Escalate"] } } } }
          ]},
          { element: "group", label: "Audit Trail", children: [
            { element: "field", key: "created", type: "text", label: "Created", instruction: null,
              value: "2026-03-18 by System", affordance: null },
            { element: "timeline", title: "History",
              events: [{ date: "2026-03-18", actor: "System", action: "Created" },
                { date: "2026-03-19", actor: "J. Martinez", action: "Assigned" },
                { date: "2026-03-20", actor: "J. Martinez", action: "Measurements recorded" },
                { date: "2026-03-22", actor: "R. Chen", action: "Review started" }] },
            { element: "field", key: "approval_status", type: "computed", label: "Approval Status",
              instruction: "Derived from disposition and follow-up fields.", value: "Pending", affordance: null }
          ]},
          { element: "group", label: "Actions", inline: true, children: [
            { element: "action", label: "Approve", method: "POST", url: "/review/approve", body: {}, variant: "primary" },
            { element: "action", label: "Request Changes", method: "POST", url: "/review/request-changes",
              body: { comment: "{input}" }, variant: "secondary" },
            { element: "action", label: "Escalate", method: "POST", url: "/review/escalate",
              body: { reason: "{input}" }, variant: "danger" }
          ]}
        ]
      }
    }
  };

  // ═══════════════════════════════════════════════════════════════
  // INIT
  // ═══════════════════════════════════════════════════════════════

  function init() {
    var nav = document.getElementById("el-nav");
    var jsonEl = document.getElementById("el-json");
    var renderEl = document.getElementById("el-render");
    var humanEl = document.getElementById("el-human");
    if (!nav || !jsonEl || !renderEl || !humanEl) return;

    var currentState = null;
    var names = Object.keys(SPECIMENS);
    var currentBtn = null;

    function rerender() {
      if (!currentState) return;
      // Agent view: container-based rendering with focus
      renderEl.innerHTML = renderContainer(currentState.data, [], currentState.focus);
      // Agent JSON: projected data matching current focus level
      var agentJson = projectAgentData(currentState.data, [], currentState.focus);
      jsonEl.innerHTML = jsonToHtml(agentJson, [], 0);
      // Human observer: full rendering with dimming
      humanEl.innerHTML = renderHumanObserver(currentState);
      setupHL(jsonEl, renderEl);
    }

    setupHandler(renderEl, function () { return currentState; }, rerender);

    function show(name) {
      currentState = deepCopy(SPECIMENS[name]);
      rerender();
      if (currentBtn) currentBtn.classList.remove("active");
      nav.querySelectorAll("button").forEach(function (b) {
        if (b.textContent === name) { b.classList.add("active"); currentBtn = b; }
      });
    }

    names.forEach(function (name) {
      var btn = document.createElement("button");
      btn.textContent = name;
      btn.addEventListener("click", function () { show(name); });
      nav.appendChild(btn);
    });

    show(names[0]);
  }

  init();
})();
