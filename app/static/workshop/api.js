// ═══════════════════════════════════════════════════════════════════
// API Design Workshop
// JSON ↔ HTML cross-highlighting experiment.
// 2x2 grid: Full (top) / Focused (bottom) × JSON (left) / Rendered (right)
// Isolated — no dependencies on engine code.
// ═══════════════════════════════════════════════════════════════════

(function () {
  "use strict";

  // ── Sample data ──────────────────────────────────────────────────

  const FULL_STATE = {
    title: "Equipment Calibration Review",
    status: "In Progress",
    priority: "High",
    fields: {
      equipment_id: "EQ-2041",
      location: "Building 7, Lab 3",
      calibration_due: "2026-04-15",
      assigned_to: "J. Martinez",
      last_calibrated: "2025-10-12",
      in_tolerance: true
    },
    actions: [
      { label: "Approve", method: "POST", href: "/approve" },
      { label: "Request Changes", method: "POST", href: "/request-changes" },
      { label: "Escalate", method: "POST", href: "/escalate" }
    ],
    notes: [
      "Instrument drift observed at +0.3% — within spec but trending.",
      "Recommend 6-month recalibration instead of annual."
    ]
  };

  const FOCUSED_STATE = {
    focus: "fields",
    title: "Equipment Calibration Review",
    status: "In Progress",
    fields: {
      equipment_id: {
        value: "EQ-2041",
        affordance: { label: "Set Equipment ID", method: "POST", href: "/fields/equipment_id", param: "value" }
      },
      location: {
        value: "Building 7, Lab 3",
        affordance: { label: "Set Location", method: "POST", href: "/fields/location", param: "value" }
      },
      calibration_due: {
        value: "2026-04-15",
        affordance: { label: "Set Calibration Due", method: "POST", href: "/fields/calibration_due", param: "value" }
      },
      assigned_to: {
        value: "J. Martinez",
        affordance: { label: "Set Assigned To", method: "POST", href: "/fields/assigned_to", param: "value" }
      },
      last_calibrated: {
        value: "2025-10-12",
        affordance: { label: "Set Last Calibrated", method: "POST", href: "/fields/last_calibrated", param: "value" }
      },
      in_tolerance: {
        value: true,
        affordance: { label: "Set In Tolerance", method: "POST", href: "/fields/in_tolerance", param: "value", options: [true, false] }
      }
    },
    actions: [
      { label: "Unfocus", method: "POST", href: "/unfocus" },
      { label: "Approve", method: "POST", href: "/approve" }
    ]
  };

  // ── Path utilities ───────────────────────────────────────────────

  function pathId(parts) { return parts.join("."); }

  // ── JSON → Syntax-highlighted HTML ───────────────────────────────

  function jsonToHtml(value, path, indent) {
    if (indent === undefined) indent = 0;
    if (!path) path = [];
    var pad = "  ".repeat(indent);
    var pad1 = "  ".repeat(indent + 1);

    if (value === null) return sp("j-null", "null");
    if (typeof value === "boolean") return sp("j-bool", String(value));
    if (typeof value === "number") return sp("j-num", String(value));
    if (typeof value === "string") return sp("j-str", '"' + escHtml(value) + '"');

    if (Array.isArray(value)) {
      if (value.length === 0) return sp("j-brace", "[]");
      var out = sp("j-brace", "[") + "\n";
      value.forEach(function (item, i) {
        var p = path.concat(String(i));
        var comma = i < value.length - 1 ? "," : "";
        out += entry(p, pad1 + jsonToHtml(item, p, indent + 1) + comma) + "\n";
      });
      out += pad + sp("j-brace", "]");
      return out;
    }

    var keys = Object.keys(value);
    if (keys.length === 0) return sp("j-brace", "{}");
    var out = sp("j-brace", "{") + "\n";
    keys.forEach(function (k, i) {
      var p = path.concat(k);
      var comma = i < keys.length - 1 ? "," : "";
      var keyHtml = sp("j-key", '"' + escHtml(k) + '"');
      out += entry(p, pad1 + keyHtml + ": " + jsonToHtml(value[k], p, indent + 1) + comma) + "\n";
    });
    out += pad + sp("j-brace", "}");
    return out;
  }

  function sp(cls, text) { return '<span class="' + cls + '">' + text + "</span>"; }

  function entry(path, inner) {
    return '<span class="j-entry" data-path="' + escAttr(pathId(path)) + '">' + inner + "</span>";
  }

  function escHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function escAttr(s) {
    return s.replace(/&/g, "&amp;").replace(/"/g, "&quot;");
  }

  // ── Render: Full state (read-only summary) ───────────────────────

  function renderFull(data) {
    var html = "";

    if (data.title) {
      html += rn("title", "<h2 style='margin:0 0 0.25rem;'>" + escHtml(data.title) + "</h2>");
    }

    if (data.status || data.priority) {
      var badges = "";
      if (data.status) {
        badges += rn("status", "<span style='display:inline-block;padding:0.2rem 0.6rem;border-radius:4px;background:#e3f2fd;color:#1565c0;font-size:0.8rem;font-weight:600;margin-right:0.5rem;'>"
          + escHtml(data.status) + "</span>");
      }
      if (data.priority) {
        var bg = data.priority === "High" ? "#fce4ec" : "#f5f5f5";
        var fg = data.priority === "High" ? "#c62828" : "#555";
        badges += rn("priority", "<span style='display:inline-block;padding:0.2rem 0.6rem;border-radius:4px;background:" + bg + ";color:" + fg + ";font-size:0.8rem;font-weight:600;'>"
          + escHtml(data.priority) + "</span>");
      }
      html += "<div style='margin-bottom:1rem;'>" + badges + "</div>";
    }

    if (data.fields) {
      html += rn("fields", renderFieldsReadOnly(data.fields));
    }

    if (data.actions && data.actions.length) {
      var btns = "";
      data.actions.forEach(function (a, i) {
        var primary = i === 0;
        var bg = primary ? "#1976d2" : "#f5f5f5";
        var fg = primary ? "#fff" : "#333";
        var border = primary ? "none" : "1px solid #ccc";
        btns += rn("actions." + i,
          "<button style='padding:0.4rem 1rem;border-radius:5px;border:" + border
          + ";background:" + bg + ";color:" + fg
          + ";font-size:0.85rem;cursor:pointer;margin-right:0.5rem;'>"
          + escHtml(a.label) + "</button>");
      });
      html += rn("actions", "<div style='margin-bottom:1.25rem;'>" + btns + "</div>");
    }

    if (data.notes && data.notes.length) {
      var items = "";
      data.notes.forEach(function (n, i) {
        items += rn("notes." + i,
          "<li style='margin-bottom:0.3rem;font-size:0.85rem;color:#555;'>"
          + escHtml(n) + "</li>");
      });
      html += rn("notes",
        "<div style='margin-top:0.5rem;'>"
        + "<h3 style='font-size:0.9rem;font-weight:600;margin:0 0 0.4rem;'>Notes</h3>"
        + "<ul style='margin:0;padding-left:1.25rem;'>" + items + "</ul></div>");
    }

    return html;
  }

  function renderFieldsReadOnly(fields) {
    var rows = "";
    Object.keys(fields).forEach(function (k) {
      var v = fields[k];
      var label = k.replace(/_/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); });
      var display;
      if (typeof v === "boolean") {
        display = v
          ? "<span style='color:#2e7d32;font-weight:600;'>Yes</span>"
          : "<span style='color:#c62828;font-weight:600;'>No</span>";
      } else {
        display = escHtml(String(v));
      }
      rows += rn("fields." + k,
        "<tr><td style='padding:0.3rem 0.75rem 0.3rem 0;font-size:0.8rem;color:#888;white-space:nowrap;vertical-align:top;'>"
        + escHtml(label)
        + "</td><td style='padding:0.3rem 0;font-size:0.85rem;'>"
        + display + "</td></tr>");
    });
    return "<table style='border-collapse:collapse;margin-bottom:1.25rem;width:100%;'>"
      + "<tbody>" + rows + "</tbody></table>";
  }

  // ── Render: Focused state (interactive affordances) ──────────────

  function renderFocused(data) {
    var html = "";

    // Header: title + focus breadcrumb
    if (data.title) {
      html += rn("title", "<h2 style='margin:0 0 0.1rem;font-size:1rem;color:#888;'>" + escHtml(data.title) + "</h2>");
    }
    if (data.focus) {
      html += rn("focus", "<div style='margin-bottom:1rem;font-size:0.85rem;font-weight:600;color:#d32f2f;'>Focus: "
        + escHtml(data.focus) + "</div>");
    }

    // Fields with inline affordances
    if (data.fields) {
      html += rn("fields", renderFieldsFocused(data.fields));
    }

    // Actions
    if (data.actions && data.actions.length) {
      var btns = "";
      data.actions.forEach(function (a, i) {
        var isUnfocus = a.label === "Unfocus";
        var bg, fg, border;
        if (isUnfocus) {
          bg = "#fff"; fg = "#d32f2f"; border = "1px solid #d32f2f";
        } else if (i === 0 || (i === 1 && data.actions[0].label === "Unfocus")) {
          bg = "#1976d2"; fg = "#fff"; border = "none";
        } else {
          bg = "#f5f5f5"; fg = "#333"; border = "1px solid #ccc";
        }
        btns += rn("actions." + i,
          "<button style='padding:0.4rem 1rem;border-radius:5px;border:" + border
          + ";background:" + bg + ";color:" + fg
          + ";font-size:0.85rem;cursor:pointer;margin-right:0.5rem;'>"
          + escHtml(a.label) + "</button>");
      });
      html += rn("actions", "<div style='margin-top:0.5rem;'>" + btns + "</div>");
    }

    return html;
  }

  function renderFieldsFocused(fields) {
    var rows = "";
    Object.keys(fields).forEach(function (k) {
      var field = fields[k];
      var label = k.replace(/_/g, " ").replace(/\b\w/g, function (c) { return c.toUpperCase(); });
      var val = field.value;
      var aff = field.affordance;

      // Current value display
      var valDisplay;
      if (typeof val === "boolean") {
        valDisplay = val
          ? "<span style='color:#2e7d32;font-weight:600;'>Yes</span>"
          : "<span style='color:#c62828;font-weight:600;'>No</span>";
      } else {
        valDisplay = escHtml(String(val));
      }

      // Affordance control
      var control = "";
      if (aff) {
        if (aff.options) {
          // Option buttons
          var optBtns = "";
          aff.options.forEach(function (opt) {
            var active = String(opt) === String(val);
            var obg = active ? "#e3f2fd" : "#f5f5f5";
            var ofg = active ? "#1565c0" : "#555";
            var oborder = active ? "1px solid #90caf9" : "1px solid #ddd";
            optBtns += "<button style='padding:0.15rem 0.5rem;border-radius:3px;border:" + oborder
              + ";background:" + obg + ";color:" + ofg
              + ";font-size:0.75rem;cursor:pointer;margin-left:0.25rem;'>"
              + escHtml(String(opt)) + "</button>";
          });
          control = optBtns;
        } else {
          // Text input + set button
          control = "<input type='text' placeholder='" + escAttr(String(val))
            + "' style='padding:0.15rem 0.4rem;border:1px solid #ddd;border-radius:3px;font-size:0.75rem;width:100px;margin-left:0.5rem;'>"
            + "<button style='padding:0.15rem 0.5rem;border-radius:3px;border:1px solid #ddd;background:#f5f5f5;color:#555;font-size:0.75rem;cursor:pointer;margin-left:0.25rem;'>Set</button>";
        }
      }

      rows += rn("fields." + k,
        "<tr>"
        + "<td style='padding:0.4rem 0.75rem 0.4rem 0;font-size:0.8rem;color:#888;white-space:nowrap;vertical-align:middle;'>"
        + escHtml(label) + "</td>"
        + "<td style='padding:0.4rem 0.5rem 0.4rem 0;font-size:0.85rem;vertical-align:middle;'>"
        + valDisplay + "</td>"
        + "<td style='padding:0.4rem 0;vertical-align:middle;white-space:nowrap;'>"
        + control + "</td>"
        + "</tr>");
    });
    return "<table style='border-collapse:collapse;margin-bottom:1rem;width:100%;'>"
      + "<tbody>" + rows + "</tbody></table>";
  }

  /** Wrap rendered HTML in a node that can be highlighted by path */
  function rn(path, inner) {
    return '<span class="r-node" data-path="' + escAttr(path) + '">' + inner + "</span>";
  }

  // ── Cross-highlighting ───────────────────────────────────────────

  function setupHighlighting(jsonEl, renderEl) {
    var activeEntries = [];
    var activeNodes = [];

    jsonEl.addEventListener("mouseover", function (e) {
      var ent = e.target.closest(".j-entry");
      if (!ent) return;
      var path = ent.getAttribute("data-path");
      if (!path) return;

      clearHighlights();

      ent.classList.add("j-hl");
      activeEntries.push(ent);

      renderEl.querySelectorAll('.r-node[data-path]').forEach(function (node) {
        var np = node.getAttribute("data-path");
        if (np === path || np.indexOf(path + ".") === 0 || path.indexOf(np + ".") === 0) {
          node.classList.add("r-hl");
          activeNodes.push(node);
        }
      });
    });

    jsonEl.addEventListener("mouseleave", function () {
      clearHighlights();
    });

    function clearHighlights() {
      activeEntries.forEach(function (el) { el.classList.remove("j-hl"); });
      activeNodes.forEach(function (el) { el.classList.remove("r-hl"); });
      activeEntries = [];
      activeNodes = [];
    }
  }

  // ── Init ─────────────────────────────────────────────────────────

  function init() {
    var jsonFull = document.getElementById("json-full");
    var renderFull_ = document.getElementById("render-full");
    var jsonFocused = document.getElementById("json-focused");
    var renderFocused_ = document.getElementById("render-focused");
    if (!jsonFull || !renderFull_ || !jsonFocused || !renderFocused_) return;

    // Top row: full state
    jsonFull.innerHTML = jsonToHtml(FULL_STATE, [], 0);
    renderFull_.innerHTML = renderFull(FULL_STATE);
    setupHighlighting(jsonFull, renderFull_);

    // Bottom row: focused state
    jsonFocused.innerHTML = jsonToHtml(FOCUSED_STATE, [], 0);
    renderFocused_.innerHTML = renderFocused(FOCUSED_STATE);
    setupHighlighting(jsonFocused, renderFocused_);
  }

  init();
})();
