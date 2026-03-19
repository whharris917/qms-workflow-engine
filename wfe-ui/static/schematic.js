// ═══════════════════════════════════════════════════════════════════
// Schematic Renderer — shared module
//
// Workflow topology visualization pipeline:
//   definitionToSpine → flattenSpine → treeOrderLines → layout → renderHybrid
//
// renderHybrid: unified HTML-over-canvas renderer. Callers provide a
// nodeRenderer(item, status) callback returning HTML for each node.
// The canvas draws only topology (wires + bars); nodes are real DOM elements.
//
// Consumed by agent_observer.html (banner, flowchart, standalone) and
// workshop.html (test harness).
// ═══════════════════════════════════════════════════════════════════

var Schematic = (function() {
'use strict';

// ── Configuration ──────────────────────────────────────────────────

var C = {
  font: '13px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  fontBold: '600 13px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  fontSmall: '500 11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  fontSmallBold: '600 11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  fontRef: 'bold 9px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  lineH: 36,
  lineGap: 4,
  padX: 20,
  padY: 16,
  depthIndent: 28,
  wireW: 20,
  refR: 12,
  stepPadX: 13,
  stepH: 30,
  stepR: 15,
  condPadX: 8,
  condH: 20,
  arrowW: 12,
  dotR: 3.5,

  // Colors (monochrome — structure communicates semantics)
  white: '#fff',
  bg: '#fafbfc',
  grayBorder: '#e5e7eb',
  grayText: '#374151',
  grayDot: '#6b7280',
  grayWire: '#d1d5db',
  grayLight: '#9ca3af',
  grayRefBg: '#f9fafb',
  grayRefBorder: '#9ca3af',
  grayRefText: '#6b7280',
  bpBg: '#f3f4f6',
  bpBorder: '#9ca3af',
  bpText: '#374151',
  barColor: '#9ca3af',
  condBg: '#f3f4f6',
  condText: '#374151',

  // Execution state colors
  currentFill: '#e3f2fd',
  currentBorder: '#2a6bcf',
  currentDot: '#2a6bcf',
  currentText: '#1a1a2e',
  completedFill: '#e8f5e9',
  completedBorder: '#4caf50',
  completedDot: '#4caf50',
  completedText: '#2e7d32',
};

// ── Ref counter ────────────────────────────────────────────────────

var _refCounter = 0;
function resetRefs() { _refCounter = 0; }
function nextRef() {
  var n = _refCounter++;
  return String.fromCharCode(65 + (n % 26)) + (n >= 26 ? Math.floor(n / 26) : '');
}

// ── Text measurement ───────────────────────────────────────────────

var _mc = document.createElement('canvas').getContext('2d');
function tw(text, font) { _mc.font = font || C.font; return _mc.measureText(text).width; }

// ═══════════════════════════════════════════════════════════════════
// DEFINITION → SPINE CONVERTER
// ═══════════════════════════════════════════════════════════════════

function definitionToSpine(definition) {
  var nodes = definition.nodes;
  if (!nodes || !nodes.length) return [];

  // Index by id
  var byId = {};
  for (var i = 0; i < nodes.length; i++) byId[nodes[i].id] = nodes[i];

  // Collect all node IDs claimed by fork branches + merge targets
  var claimed = {};  // node_id → true
  var mergeNodes = {}; // merge_node_id → fork_node_id
  for (var i = 0; i < nodes.length; i++) {
    var nd = nodes[i];
    if (nd.fork) {
      mergeNodes[nd.fork.merge] = nd.id;
      var branches = nd.fork.branches;
      for (var bid in branches) {
        var bnodes = branches[bid].nodes;
        for (var j = 0; j < bnodes.length; j++) claimed[bnodes[j]] = true;
      }
    }
  }

  // Build human-readable condition label from a `when` expression
  function condLabel(when) {
    if (!when) return '';
    if (when.type === 'field_equals') return when.key + ' = ' + when.value;
    if (when.type === 'field_in') return when.key + ' in [' + (when.values || []).join(', ') + ']';
    if (when.type === 'field_truthy') return when.key;
    if (when.op === 'AND' || when.op === 'OR') {
      var parts = (when.conditions || []).map(condLabel);
      return parts.join(' ' + when.op + ' ');
    }
    // Fallback: try to produce something readable
    if (when.key && when.value) return when.key + ' = ' + when.value;
    return JSON.stringify(when);
  }

  // Find where router routes converge by walking forward from each target
  function findConvergence(routerNode, stopSet) {
    var routes = routerNode.router;
    if (!routes || routes.length < 2) {
      return routes && routes.length === 1 && routes[0].target ? routes[0].target : null;
    }

    // For each route, collect the chain of reachable node IDs
    var paths = [];
    for (var ri = 0; ri < routes.length; ri++) {
      var chain = [];
      var cur = routes[ri].target;
      while (cur && !stopSet[cur] && !claimed[cur] && !mergeNodes[cur]) {
        chain.push(cur);
        var n = byId[cur];
        if (!n) break;
        if (n.router) {
          // Skip past nested router — find its convergence and continue from there
          var innerConv = findConvergence(n, stopSet);
          if (innerConv) { chain.push(innerConv); cur = byId[innerConv] && byId[innerConv].proceed ? byId[innerConv].proceed.target : null; }
          else break;
        } else if (n.fork) {
          // Skip past nested fork — continue from merge node's proceed target
          var mn = byId[n.fork.merge];
          if (mn) { chain.push(n.fork.merge); cur = mn.proceed ? mn.proceed.target : null; }
          else break;
        } else {
          cur = n.proceed ? n.proceed.target : null;
        }
      }
      // Also add the stop node if we reached it
      if (cur && (stopSet[cur] || claimed[cur] || mergeNodes[cur])) chain.push(cur);
      paths.push(chain);
    }

    // Find first node in paths[0] that appears in ALL other paths
    if (paths.length === 0) return null;
    for (var ci = 0; ci < paths[0].length; ci++) {
      var candidate = paths[0][ci];
      var inAll = true;
      for (var pi = 1; pi < paths.length; pi++) {
        if (paths[pi].indexOf(candidate) === -1) { inAll = false; break; }
      }
      if (inAll) return candidate;
    }
    return null;
  }

  // Walk a chain of nodes, building spine elements. Stops at IDs in stopSet.
  function walkChain(startId, stopSet) {
    var spine = [];
    var currentId = startId;
    var safety = 200;

    while (currentId && !stopSet[currentId] && --safety > 0) {
      var nd = byId[currentId];
      if (!nd) break;

      if (nd.router) {
        // Gate (conditional router)
        var conv = findConvergence(nd, stopSet);
        var innerStop = {};
        for (var k in stopSet) innerStop[k] = true;
        if (conv) innerStop[conv] = true;

        var routes = [];
        for (var ri = 0; ri < nd.router.length; ri++) {
          var r = nd.router[ri];
          var routePath = r.target ? walkChain(r.target, innerStop) : [];
          var cond = condLabel(r.when);
          var label = cond || 'Default';
          routes.push({ label: label, condition: label, path: routePath });
        }
        spine.push({ type: 'gate', id: nd.id, title: nd.title, routes: routes });
        currentId = conv;

      } else if (nd.fork) {
        // Split (parallel fork)
        var branches = [];
        var branchMap = nd.fork.branches;
        for (var bid in branchMap) {
          var bdef = branchMap[bid];
          var branchPath = walkBranch(bdef.nodes, stopSet);
          branches.push({ label: bdef.label || bid, path: branchPath });
        }
        var mergeNd = byId[nd.fork.merge];
        spine.push({
          type: 'split', id: nd.id, title: nd.title,
          branches: branches,
          merge: mergeNd ? { id: mergeNd.id, title: mergeNd.title } : { id: nd.fork.merge, title: nd.fork.merge }
        });
        // Continue from merge node's proceed target
        currentId = mergeNd && mergeNd.proceed ? mergeNd.proceed.target : null;

      } else {
        // Simple step
        spine.push({ type: 'step', id: nd.id, title: nd.title });
        currentId = nd.proceed ? nd.proceed.target : null;
      }
    }
    return spine;
  }

  // Walk an explicit list of branch node IDs as a mini-spine
  function walkBranch(nodeIds, outerStop) {
    if (!nodeIds || !nodeIds.length) return [];
    var subSpine = [];
    var i = 0;
    var safety = 200;

    while (i < nodeIds.length && --safety > 0) {
      var nid = nodeIds[i];
      var nd = byId[nid];
      if (!nd) { i++; continue; }

      if (nd.router) {
        // Find convergence within remaining branch nodes
        var remaining = {};
        for (var ri = i + 1; ri < nodeIds.length; ri++) remaining[nodeIds[ri]] = true;
        for (var k in outerStop) remaining[k] = true;
        var conv = findConvergence(nd, remaining);

        var innerStop = {};
        for (var k2 in remaining) innerStop[k2] = true;
        if (conv) innerStop[conv] = true;

        var routes = [];
        for (var rri = 0; rri < nd.router.length; rri++) {
          var r = nd.router[rri];
          var routePath = r.target ? walkChain(r.target, innerStop) : [];
          var label = condLabel(r.when) || ('Route ' + (rri + 1));
          routes.push({ label: label, condition: condLabel(r.when), path: routePath });
        }
        subSpine.push({ type: 'gate', id: nd.id, title: nd.title, routes: routes });

        // Skip ahead to convergence node in the branch list
        if (conv) {
          var convIdx = nodeIds.indexOf(conv);
          i = convIdx >= 0 ? convIdx : i + 1;
        } else {
          i++;
        }

      } else if (nd.fork) {
        var branches = [];
        var branchMap = nd.fork.branches;
        for (var bid in branchMap) {
          var bdef = branchMap[bid];
          var branchPath = walkBranch(bdef.nodes, outerStop);
          branches.push({ label: bdef.label || bid, path: branchPath });
        }
        var mergeNd = byId[nd.fork.merge];
        subSpine.push({
          type: 'split', id: nd.id, title: nd.title,
          branches: branches,
          merge: mergeNd ? { id: mergeNd.id, title: mergeNd.title } : { id: nd.fork.merge, title: nd.fork.merge }
        });
        // Skip past merge node in branch list
        var mergeIdx = nodeIds.indexOf(nd.fork.merge);
        i = mergeIdx >= 0 ? mergeIdx + 1 : i + 1;

      } else {
        subSpine.push({ type: 'step', id: nid, title: nd.title });
        i++;
      }
    }
    return subSpine;
  }

  return walkChain(nodes[0].id, {});
}

// ═══════════════════════════════════════════════════════════════════
// FLATTEN SPINE → LINES
// ═══════════════════════════════════════════════════════════════════

function flattenSpine(spine, depth, rejoinRef) {
  var lines = [];
  var cur = { depth: depth, elements: [] };

  function wire() { if (cur.elements.length > 0) cur.elements.push({ kind: 'wire' }); }

  function emitSimplePath(pathSegs, startElements, d, endRef) {
    var line = { depth: d, elements: startElements.slice(), rejoinLabel: endRef };
    var sr = startElements.find(function(e) { return e.kind === 'ref'; });
    if (sr) { line.branchLabel = sr.label; line.branchType = sr.type; if (sr.type === 'rejoin') line.isContinuation = true; }
    for (var si = 0; si < pathSegs.length; si++) {
      line.elements.push({ kind: 'wire' });
      line.elements.push({ kind: 'step', title: pathSegs[si].title, id: pathSegs[si].id, height: pathSegs[si].height });
    }
    line.elements.push({ kind: 'rejoin-arrow' });
    line.elements.push({ kind: 'ref', label: endRef, type: 'rejoin' });
    lines.push(line);
  }

  function emitPath(pathSegs, startElements, d, endRef) {
    if (pathSegs.length === 0) {
      var line = { depth: d, elements: startElements.slice(), rejoinLabel: endRef };
      var sr = startElements.find(function(e) { return e.kind === 'ref'; });
      if (sr) { line.branchLabel = sr.label; line.branchType = sr.type; if (sr.type === 'rejoin') line.isContinuation = true; }
      line.elements.push({ kind: 'rejoin-arrow' });
      line.elements.push({ kind: 'ref', label: endRef, type: 'rejoin' });
      lines.push(line);
      return [];
    }
    var hasBranch = pathSegs.some(function(s) { return s.type === 'gate' || s.type === 'split'; });
    if (!hasBranch) { emitSimplePath(pathSegs, startElements, d, endRef); return []; }
    var subLines = flattenSpine(pathSegs, d, endRef);
    if (subLines.length === 0) return [];

    var branchLines = [];
    var contLines = [];
    var seenBranchPoint = false;
    var lastRejoinStart = -1;

    for (var si = 0; si < subLines.length; si++) {
      if (subLines[si].elements.find(function(e) { return e.kind === 'branch-point'; })) seenBranchPoint = true;
      if (seenBranchPoint && subLines[si].isContinuation) lastRejoinStart = si;
    }

    if (lastRejoinStart > 0) {
      for (var si2 = 0; si2 < lastRejoinStart; si2++) branchLines.push(subLines[si2]);
      for (var si3 = lastRejoinStart; si3 < subLines.length; si3++) {
        subLines[si3].depth = Math.max(0, d - 1);
        contLines.push(subLines[si3]);
      }
    } else {
      branchLines = subLines.slice();
    }

    if (branchLines.length > 0) {
      branchLines[0].elements = startElements.concat([{ kind: 'wire' }]).concat(branchLines[0].elements);
      var sr2 = startElements.find(function(e) { return e.kind === 'ref'; });
      if (sr2) {
        branchLines[0].branchLabel = sr2.label;
        branchLines[0].branchType = sr2.type;
        if (sr2.type === 'rejoin') branchLines[0].isContinuation = true;
      }
    }

    lines.push.apply(lines, branchLines);
    return contLines;
  }

  function tagGroupByRefs(arr, startIdx, refLabels, type, gid, rejoinLabel) {
    for (var gi = startIdx; gi < arr.length; gi++) {
      if (arr[gi].branchLabel && refLabels.indexOf(arr[gi].branchLabel) >= 0) {
        if (!arr[gi].groups) arr[gi].groups = [];
        arr[gi].groups.push({ type: type, gid: gid, rejoinLabel: rejoinLabel });
      }
    }
  }

  for (var i = 0; i < spine.length; i++) {
    var seg = spine[i];
    if (seg.type === 'step') {
      wire();
      cur.elements.push({ kind: 'step', title: seg.title, id: seg.id, height: seg.height });
    }
    else if (seg.type === 'gate') {
      wire();
      var gid = 'g' + _refCounter;
      cur.elements.push({ kind: 'branch-point', title: seg.title, type: 'gate', groupId: gid, id: seg.id, height: seg.height });
      var rejoinLabel = nextRef();
      var routeRefs = seg.routes.map(function() { return nextRef(); });
      lines.push(cur);
      var gs = lines.length;
      for (var ri = 0; ri < seg.routes.length; ri++) {
        var route = seg.routes[ri];
        var start = [{ kind: 'ref', label: routeRefs[ri], type: 'gate' }];
        if (route.condition) start.push({ kind: 'cond', text: route.condition, type: 'gate' });
        var cont = emitPath(route.path, start, depth + 1, rejoinLabel);
        lines.push.apply(lines, cont);
      }
      tagGroupByRefs(lines, gs, routeRefs, 'gate', gid, rejoinLabel);
      cur = { depth: depth, elements: [{ kind: 'ref', label: rejoinLabel, type: 'rejoin' }],
              branchLabel: rejoinLabel, branchType: 'rejoin', isContinuation: true };
    }
    else if (seg.type === 'split') {
      wire();
      var gid2 = 'g' + _refCounter;
      cur.elements.push({ kind: 'branch-point', title: seg.title, type: 'split', groupId: gid2, id: seg.id, height: seg.height });
      var mergeLabel = nextRef();
      var branchRefs = seg.branches.map(function() { return nextRef(); });
      lines.push(cur);
      var gs2 = lines.length;
      for (var bi = 0; bi < seg.branches.length; bi++) {
        var branch = seg.branches[bi];
        var start2 = [
          { kind: 'ref', label: branchRefs[bi], type: 'split' },
          { kind: 'cond', text: branch.label, type: 'split' },
        ];
        var cont2 = emitPath(branch.path, start2, depth + 1, mergeLabel);
        lines.push.apply(lines, cont2);
      }
      tagGroupByRefs(lines, gs2, branchRefs, 'split', gid2, mergeLabel);
      cur = { depth: depth, elements: [{ kind: 'ref', label: mergeLabel, type: 'rejoin' }],
              branchLabel: mergeLabel, branchType: 'rejoin', isContinuation: true };
      if (seg.merge) { cur.elements.push({ kind: 'step', title: seg.merge.title, id: seg.merge.id, height: seg.merge.height }); }
    }
  }

  if (rejoinRef && cur.elements.length > 0) {
    cur.rejoinLabel = rejoinRef;
    if (!cur.branchLabel) { cur.branchLabel = rejoinRef; cur.branchType = 'rejoin'; cur.isContinuation = true; }
    cur.elements.push({ kind: 'rejoin-arrow' });
    cur.elements.push({ kind: 'ref', label: rejoinRef, type: 'rejoin' });
  }
  if (cur.elements.length > 0) lines.push(cur);

  return lines;
}

// ═══════════════════════════════════════════════════════════════════
// TREE-BASED ORDERING AND Y-ASSIGNMENT
// ═══════════════════════════════════════════════════════════════════

// Pre-compute element heights so treeOrderLines has accurate per-row sizing.
function _precomputeHeights(lines, opts) {
  var explicitH = opts && opts.nodeH;  // only override when explicitly provided
  for (var li = 0; li < lines.length; li++) {
    for (var ei = 0; ei < lines[li].elements.length; ei++) {
      var elem = lines[li].elements[ei];
      if (elem.kind === 'step' && !elem.height) {
        if (explicitH) {
          elem.height = explicitH;
        } else {
          // Auto-compute from multi-line title
          var titleLines = elem.title.split('\n');
          if (titleLines.length > 1) {
            elem.height = Math.max(C.stepH, titleLines.length * 15 + 10);
          }
        }
      }
    }
  }
}

function treeOrderLines(lines, opts) {
  var defaultH = (opts && opts.nodeH) || C.lineH;
  var gap = (opts && opts.lineGap !== undefined) ? opts.lineGap : C.lineGap;

  var groupMembers = {};
  var groupRejoinLabel = {};
  var continuationFor = {};

  for (var i = 0; i < lines.length; i++) {
    if (lines[i].groups) {
      for (var gi = 0; gi < lines[i].groups.length; gi++) {
        var g = lines[i].groups[gi];
        if (!groupMembers[g.gid]) groupMembers[g.gid] = [];
        groupMembers[g.gid].push(i);
        if (g.rejoinLabel) groupRejoinLabel[g.gid] = g.rejoinLabel;
      }
    }
    if (lines[i].isContinuation && lines[i].branchLabel) {
      continuationFor[lines[i].branchLabel] = i;
    }
  }

  // Compute per-line row height from the tallest element on each line.
  // Elements can declare height via seg.height in the spine data; otherwise
  // use defaultH. For lines with multiple elements, take the max.
  for (var li = 0; li < lines.length; li++) {
    var maxH = defaultH;
    for (var ei = 0; ei < lines[li].elements.length; ei++) {
      var elem = lines[li].elements[ei];
      if (elem.kind === 'step' || elem.kind === 'branch-point') {
        var eh = elem.height || defaultH;
        if (eh > maxH) maxH = eh;
      }
    }
    lines[li]._rowH = maxH;
  }

  var visited = {};
  var result = [];

  function assignY(idx, startY) {
    if (visited[idx]) return startY;
    visited[idx] = true;
    var line = lines[idx];
    line._assignedY = startY;
    result.push(line);

    var bp = line.elements.find(function(e) { return e.kind === 'branch-point'; });
    if (!bp) return startY + line._rowH + gap;

    var gid = bp.groupId;
    var members = groupMembers[gid] || [];

    var rejoinLabel = groupRejoinLabel[gid];
    var contSubtreeBottom = startY + line._rowH + gap;

    if (rejoinLabel && continuationFor[rejoinLabel] !== undefined) {
      var contIdx = continuationFor[rejoinLabel];
      var contLine = lines[contIdx];
      var hasBP = contLine.elements.find(function(e) { return e.kind === 'branch-point'; });

      while (contLine.elements.length > 0 &&
             (contLine.elements[0].kind === 'ref' || contLine.elements[0].kind === 'wire')) {
        contLine.elements.shift();
      }

      if (!hasBP) {
        contLine._assignedY = startY;
        // Shared row: both lines must use the same rowH (the max)
        var sharedLeafH = Math.max(line._rowH, contLine._rowH);
        line._rowH = sharedLeafH;
        contLine._rowH = sharedLeafH;
        visited[contIdx] = true;
        result.push(contLine);
      } else {
        contSubtreeBottom = assignY(contIdx, startY);
        // Shared row: take max of both lines' rowH
        var sharedH = Math.max(line._rowH, lines[contIdx]._rowH);
        line._rowH = sharedH;
        lines[contIdx]._rowH = sharedH;
      }
    }

    // Branches start after the row height of the parent line
    var branchY = startY + line._rowH + gap;
    for (var mi = 0; mi < members.length; mi++) {
      branchY = assignY(members[mi], branchY);
    }

    // Update contSubtreeBottom if it was based on old rowH
    if (contSubtreeBottom === startY + defaultH + gap) {
      contSubtreeBottom = startY + line._rowH + gap;
    }

    return Math.max(branchY, contSubtreeBottom);
  }

  var y = C.padY;
  for (var i2 = 0; i2 < lines.length; i2++) {
    if (!visited[i2]) {
      y = assignY(i2, y);
    }
  }

  return result;
}

// ═══════════════════════════════════════════════════════════════════
// CANVAS LAYOUT ENGINE
// ═══════════════════════════════════════════════════════════════════

function layout(lines, opts) {
  var nodeW = (opts && opts.nodeW) || 0;   // 0 = text-measured (default)
  var nodeH = (opts && opts.nodeH) || C.stepH;

  var positioned = [];
  var totalW = 0;

  for (var li = 0; li < lines.length; li++) {
    var line = lines[li];
    var y = line._assignedY;
    var indent = C.padX + line.depth * C.depthIndent;
    var x = indent;
    var items = [];
    var contentEndX = 0;
    var rejoinStartIdx = -1;

    for (var ei = 0; ei < line.elements.length; ei++) {
      var elem = line.elements[ei];
      var item = null;

      switch (elem.kind) {
        case 'step': {
          var titleLines = elem.title.split('\n');
          var textW = 0;
          for (var tli = 0; tli < titleLines.length; tli++) {
            var lw = tw(titleLines[tli], C.font);
            if (lw > textW) textW = lw;
          }
          var dotSpace = C.dotR * 2 + 5;
          var w = nodeW || (C.stepPadX + dotSpace + textW + C.stepPadX);
          var naturalH = titleLines.length > 1 ? Math.max(C.stepH, titleLines.length * 15 + 10) : C.stepH;
          var h = elem.height || (nodeW ? nodeH : naturalH);
          item = { kind: 'step', x: x, y: y, w: w, h: h, title: elem.title, id: elem.id, textW: textW, dotSpace: dotSpace };
          x += w;
          break;
        }
        case 'wire': {
          item = { kind: 'wire', x: x, y: y, w: C.wireW };
          x += C.wireW;
          break;
        }
        case 'ref': {
          item = { kind: 'ref', x: x, y: y, w: 0, h: 0, label: elem.label, type: elem.type };
          break;
        }
        case 'branch-point': {
          var textW2 = tw(elem.title, C.fontBold);
          var bpH = nodeW ? nodeH : C.stepH;
          var w2;
          if (nodeW) {
            w2 = nodeW;
          } else if (elem.type === 'gate') {
            w2 = textW2 + C.stepPadX * 2 + bpH * 0.5;
          } else {
            w2 = textW2 + C.stepPadX * 2 + 16;
          }
          item = { kind: 'branch-point', x: x, y: y, w: w2, h: bpH, title: elem.title,
                   type: elem.type, groupId: elem.groupId, id: elem.id, textW: textW2 };
          x += w2;
          break;
        }
        case 'cond': {
          var textW3 = tw(elem.text, C.fontSmall);
          var w3 = textW3 + C.condPadX * 2;
          item = { kind: 'cond', x: x + 4, y: y, w: w3, h: C.condH, text: elem.text, type: elem.type };
          x += w3 + 4;
          break;
        }
        case 'rejoin-arrow': {
          rejoinStartIdx = items.length;
          item = { kind: 'rejoin-arrow', x: x, y: y, w: C.arrowW };
          x += C.arrowW;
          break;
        }
      }

      if (item) {
        if (rejoinStartIdx === -1) contentEndX = x;
        items.push(item);
      }
    }

    positioned.push({ y: y, items: items, contentEndX: contentEndX, rejoinStartIdx: rejoinStartIdx, depth: line.depth,
                       rejoinLabel: line.rejoinLabel, groups: line.groups,
                       isContinuation: line.isContinuation, branchLabel: line.branchLabel,
                       _assignedY: line._assignedY, _rowH: line._rowH || C.lineH,
                       totalContentW: x });
    totalW = Math.max(totalW, x + C.padX);
  }

  // Identify continuation lines whose first visible item is a branch-point
  var contWithBP = [];
  for (var ci = 0; ci < positioned.length; ci++) {
    if (positioned[ci].isContinuation) {
      var first = positioned[ci].items.find(function(it) { return it.kind === 'step' || it.kind === 'branch-point'; });
      if (first && first.kind === 'branch-point') contWithBP.push(positioned[ci]);
    }
  }
  function isContWithBP(pl) { return contWithBP.indexOf(pl) >= 0; }

  var groupDisplace = {};

  var groupOrder = [];
  for (var pi = 0; pi < positioned.length; pi++) {
    for (var ii = 0; ii < positioned[pi].items.length; ii++) {
      var itm = positioned[pi].items[ii];
      if (itm.kind === 'branch-point' && itm.groupId) {
        groupOrder.push({ gid: itm.groupId, depth: positioned[pi].depth });
        if (isContWithBP(positioned[pi])) {
          var maxCondW = 0;
          for (var pi2 = 0; pi2 < positioned.length; pi2++) {
            if (!positioned[pi2].groups) continue;
            for (var gi2 = 0; gi2 < positioned[pi2].groups.length; gi2++) {
              if (positioned[pi2].groups[gi2].gid === itm.groupId) {
                var ci2 = positioned[pi2].items.find(function(it2) { return it2.kind === 'cond'; });
                if (ci2) maxCondW = Math.max(maxCondW, ci2.w);
                break;
              }
            }
          }
          groupDisplace[itm.groupId] = maxCondW / 2 + 8;
        }
      }
    }
  }
  groupOrder.sort(function(a, b) { return a.depth - b.depth; });

  function alignGroups() {
    for (var gi3 = 0; gi3 < groupOrder.length; gi3++) {
      var gid = groupOrder[gi3].gid;
      var targetX;
      for (var pi3 = 0; pi3 < positioned.length; pi3++) {
        for (var ii3 = 0; ii3 < positioned[pi3].items.length; ii3++) {
          var it3 = positioned[pi3].items[ii3];
          if (it3.kind === 'branch-point' && it3.groupId === gid) {
            targetX = it3.x + it3.w / 2;
          }
        }
      }
      if (targetX === undefined) continue;

      targetX += groupDisplace[gid] || 0;

      for (var pi4 = 0; pi4 < positioned.length; pi4++) {
        var pl = positioned[pi4];
        if (!pl.groups) continue;
        var deepestGid = null;
        var deepestDepth = -1;
        for (var gi4 = 0; gi4 < pl.groups.length; gi4++) {
          var gentry = pl.groups[gi4];
          var goEntry = groupOrder.find(function(go) { return go.gid === gentry.gid; });
          var d = goEntry ? goEntry.depth : -1;
          if (d > deepestDepth) { deepestDepth = d; deepestGid = gentry.gid; }
        }
        if (deepestGid !== gid) continue;
        var condItem = pl.items.find(function(it4) { return it4.kind === 'cond'; });
        var anchor = condItem || pl.items.find(function(it5) { return it5.kind === 'step' || it5.kind === 'wire'; });
        if (!anchor) continue;
        var anchorCx = anchor.x + anchor.w / 2;
        var shift = targetX - anchorCx;
        if (Math.abs(shift) > 0.5) {
          for (var ii4 = 0; ii4 < pl.items.length; ii4++) {
            pl.items[ii4].x += shift;
          }
          pl.totalContentW += shift;
          pl.contentEndX += shift;
        }
      }
    }
  }

  alignGroups();

  // Convergence alignment
  var rejoinGroups = {};
  for (var pi5 = 0; pi5 < positioned.length; pi5++) {
    if (positioned[pi5].rejoinLabel) {
      if (!rejoinGroups[positioned[pi5].rejoinLabel]) rejoinGroups[positioned[pi5].rejoinLabel] = [];
      rejoinGroups[positioned[pi5].rejoinLabel].push(positioned[pi5]);
    }
  }

  var contLinesByLabel = {};
  for (var pi6 = 0; pi6 < positioned.length; pi6++) {
    if (positioned[pi6].isContinuation && positioned[pi6].branchLabel) {
      if (!contLinesByLabel[positioned[pi6].branchLabel]) contLinesByLabel[positioned[pi6].branchLabel] = [];
      contLinesByLabel[positioned[pi6].branchLabel].push(positioned[pi6]);
    }
  }

  var rejoinLabelOrder = [];
  for (var rlabel in rejoinGroups) rejoinLabelOrder.push([rlabel, rejoinGroups[rlabel]]);
  rejoinLabelOrder.sort(function(a, b) {
    var depthA = Math.max.apply(null, a[1].map(function(pl2) { return pl2.depth; }));
    var depthB = Math.max.apply(null, b[1].map(function(pl3) { return pl3.depth; }));
    return depthB - depthA;
  });

  for (var iter = 0; iter < 10; iter++) {
    var changed = false;

    for (var rli = 0; rli < rejoinLabelOrder.length; rli++) {
      var label = rejoinLabelOrder[rli][0];
      var plines = rejoinLabelOrder[rli][1];
      var clLines = contLinesByLabel[label] || [];

      var convergenceX = 0;

      for (var pli = 0; pli < plines.length; pli++) {
        var pl2 = plines[pli];
        if (pl2.rejoinStartIdx >= 0) {
          if (pl2.isContinuation) {
            convergenceX = Math.max(convergenceX, pl2.contentEndX + C.arrowW);
          } else {
            var arrow = pl2.items[pl2.rejoinStartIdx];
            convergenceX = Math.max(convergenceX, arrow.x + arrow.w);
          }
        }
        if (pl2._convergenceXByLabel) {
          for (var ck in pl2._convergenceXByLabel) {
            convergenceX = Math.max(convergenceX, pl2._convergenceXByLabel[ck]);
          }
        }
      }

      for (var cli = 0; cli < clLines.length; cli++) {
        var cl = clLines[cli];
        if (plines.indexOf(cl) >= 0) continue;
        var anch = cl.items.find(function(it6) { return it6.kind === 'step' || it6.kind === 'branch-point'; });
        if (anch) convergenceX = Math.max(convergenceX, anch.x + anch.w / 2);
      }

      if (convergenceX === 0) continue;

      for (var pli2 = 0; pli2 < plines.length; pli2++) {
        var pl3 = plines[pli2];
        if (pl3.rejoinStartIdx >= 0) {
          var arrow2 = pl3.items[pl3.rejoinStartIdx];
          var currentTip = arrow2.x + arrow2.w;
          var shift2 = convergenceX - currentTip;
          if (Math.abs(shift2) > 0.5) {
            for (var si = pl3.rejoinStartIdx; si < pl3.items.length; si++) {
              pl3.items[si].x += shift2;
            }
            changed = true;
          }
        }
        if (!pl3._convergenceXByLabel) pl3._convergenceXByLabel = {};
        pl3._convergenceXByLabel[label] = convergenceX;
      }

      for (var cli2 = 0; cli2 < clLines.length; cli2++) {
        var cl2 = clLines[cli2];
        if (plines.indexOf(cl2) >= 0) continue;
        var anch2 = cl2.items.find(function(it7) { return it7.kind === 'step' || it7.kind === 'branch-point'; });
        if (!anch2) continue;
        var currentCx = anch2.x + anch2.w / 2;
        var shift3 = convergenceX - currentCx;
        if (Math.abs(shift3) > 0.5) {
          for (var ii5 = 0; ii5 < cl2.items.length; ii5++) {
            cl2.items[ii5].x += shift3;
          }
          cl2.totalContentW += shift3;
          cl2.contentEndX += shift3;
          changed = true;
        }
        if (!cl2._convergenceXByLabel) cl2._convergenceXByLabel = {};
        cl2._convergenceXByLabel[label] = convergenceX;
      }
    }

    alignGroups();
    if (!changed) break;
  }

  // Widen and shift BPs on continuation lines
  for (var pi7 = 0; pi7 < positioned.length; pi7++) {
    for (var ii6 = 0; ii6 < positioned[pi7].items.length; ii6++) {
      var itm2 = positioned[pi7].items[ii6];
      if (itm2.kind === 'branch-point' && itm2.groupId && groupDisplace[itm2.groupId]) {
        var displace = groupDisplace[itm2.groupId];
        itm2.x += displace / 2;
        if (itm2.w < displace) {
          var extra = displace - itm2.w;
          itm2.x -= extra / 2;
          itm2.w = displace;
        }
      }
    }
  }

  // Even-spacing pass
  for (var pi8 = 0; pi8 < positioned.length; pi8++) {
    var pl4 = positioned[pi8];
    if (pl4.rejoinStartIdx < 0) continue;

    var solidItems = [];
    var wireItems = [];
    for (var ii7 = 0; ii7 < pl4.rejoinStartIdx; ii7++) {
      var it8 = pl4.items[ii7];
      if (it8.kind === 'wire') wireItems.push(ii7);
      else if (it8.w > 0) solidItems.push(ii7);
    }

    if (solidItems.length < 2) continue;

    var firstSolid = pl4.items[solidItems[0]];
    var arrow3 = pl4.items[pl4.rejoinStartIdx];
    var spanStart = firstSolid.x;
    var spanEnd = arrow3.x;

    var totalSolidW = 0;
    for (var si2 = 0; si2 < solidItems.length; si2++) totalSolidW += pl4.items[solidItems[si2]].w;

    var totalGap = spanEnd - spanStart - totalSolidW;
    if (totalGap <= 0) continue;

    var gapCount = solidItems.length;
    var gap = totalGap / gapCount;

    var ex = spanStart;
    for (var si3 = 0; si3 < solidItems.length; si3++) {
      var item2 = pl4.items[solidItems[si3]];
      item2.x = ex;
      ex += item2.w + gap;
    }

    for (var wi = 0; wi < wireItems.length; wi++) {
      var wire2 = pl4.items[wireItems[wi]];
      var prevSolidEnd = spanStart;
      var nextSolidStart = spanEnd;
      for (var si4 = 0; si4 < solidItems.length; si4++) {
        var it9 = pl4.items[solidItems[si4]];
        if (solidItems[si4] < wireItems[wi] && it9.x + it9.w > prevSolidEnd) prevSolidEnd = it9.x + it9.w;
        if (solidItems[si4] > wireItems[wi] && it9.x < nextSolidStart) nextSolidStart = it9.x;
      }
      wire2.x = prevSolidEnd;
      wire2.w = nextSolidStart - prevSolidEnd;
    }
  }

  // Update totalW
  for (var pi9 = 0; pi9 < positioned.length; pi9++) {
    var lastItem = positioned[pi9].items[positioned[pi9].items.length - 1];
    if (lastItem) totalW = Math.max(totalW, lastItem.x + (lastItem.w || 0) + C.padX);
  }

  // Compute vertical bars
  var vbars = [];

  // Divergence bars
  for (var pi10 = 0; pi10 < positioned.length; pi10++) {
    for (var ii8 = 0; ii8 < positioned[pi10].items.length; ii8++) {
      var itm3 = positioned[pi10].items[ii8];
      if (itm3.kind === 'branch-point' && itm3.groupId) {
        var gid2 = itm3.groupId;
        var bpCx = itm3.x + itm3.w / 2;
        var bpCy = positioned[pi10].y + positioned[pi10]._rowH / 2;
        var barX = bpCx + (groupDisplace[gid2] ? groupDisplace[gid2] / 2 : 0);
        var lastCy = bpCy;
        for (var pi11 = 0; pi11 < positioned.length; pi11++) {
          if (positioned[pi11].groups) {
            for (var gi5 = 0; gi5 < positioned[pi11].groups.length; gi5++) {
              if (positioned[pi11].groups[gi5].gid === gid2) {
                lastCy = positioned[pi11].y + positioned[pi11]._rowH / 2;
                break;
              }
            }
          }
        }
        if (lastCy > bpCy) {
          vbars.push({ x: barX, y1: bpCy, y2: lastCy, type: itm3.type });
        }
      }
    }
  }

  // Convergence bars
  for (var rlabel2 in rejoinGroups) {
    var plines2 = rejoinGroups[rlabel2];
    var points = [];
    var type = 'gate';

    for (var pli3 = 0; pli3 < plines2.length; pli3++) {
      var pl5 = plines2[pli3];
      var cx = pl5._convergenceXByLabel && pl5._convergenceXByLabel[rlabel2];
      if (cx !== undefined) points.push({ cx: cx, cy: pl5.y + pl5._rowH / 2 });
      if (pl5.groups && pl5.groups.length > 0 && type === 'gate') type = pl5.groups[0].type;
    }

    var clLines2 = contLinesByLabel[rlabel2] || [];
    for (var cli3 = 0; cli3 < clLines2.length; cli3++) {
      var cl3 = clLines2[cli3];
      if (plines2.indexOf(cl3) >= 0) continue;
      var cx2 = cl3._convergenceXByLabel && cl3._convergenceXByLabel[rlabel2];
      if (cx2 !== undefined) points.push({ cx: cx2, cy: cl3.y + cl3._rowH / 2 });
    }

    if (points.length < 2) continue;

    var byX = {};
    for (var pti = 0; pti < points.length; pti++) {
      var key = Math.round(points[pti].cx);
      if (!byX[key]) byX[key] = [];
      byX[key].push(points[pti]);
    }

    for (var xKey in byX) {
      var xPoints = byX[xKey];
      if (xPoints.length < 2) continue;
      xPoints.sort(function(a, b) { return a.cy - b.cy; });
      vbars.push({
        x: xPoints[0].cx,
        y1: xPoints[0].cy,
        y2: xPoints[xPoints.length - 1].cy,
        type: type,
      });
    }
  }

  var maxY = 0;
  for (var pi12 = 0; pi12 < positioned.length; pi12++) { if (positioned[pi12].y > maxY) maxY = positioned[pi12].y; }
  var maxRowH = C.lineH;
  for (var pi13 = 0; pi13 < positioned.length; pi13++) {
    if (positioned[pi13].y === maxY && positioned[pi13]._rowH > maxRowH) maxRowH = positioned[pi13]._rowH;
  }
  var totalH = positioned.length > 0 ? maxY + maxRowH + C.padY : C.padY * 2;
  return { width: totalW, height: totalH, lines: positioned, vbars: vbars };
}

// ═══════════════════════════════════════════════════════════════════
// CANVAS DRAW ENGINE
// ═══════════════════════════════════════════════════════════════════

function drawPill(ctx, x, y, w, h, r, fill, stroke, lineWidth) {
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
  ctx.fillStyle = fill;
  ctx.fill();
  if (stroke !== 'transparent' && lineWidth > 0) {
    ctx.strokeStyle = stroke;
    ctx.lineWidth = lineWidth;
    ctx.stroke();
  }
}

function _nodeStatus(item, execState) {
  if (!execState || !item.id) return 'pending';
  if (item.id === execState.current) return 'current';
  if (execState.completed && execState.completed.indexOf(item.id) >= 0) return 'completed';
  return 'pending';
}

function drawSchematic(canvas, layoutData, execState, opts) {
  var wiresOnly = opts && opts.wiresOnly;  // skip node shapes, draw only topology
  var dpr = window.devicePixelRatio || 1;
  canvas.width = layoutData.width * dpr;
  canvas.height = layoutData.height * dpr;
  canvas.style.width = layoutData.width + 'px';
  canvas.style.height = layoutData.height + 'px';

  var ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  // Topology lines (drawn first, behind nodes)

  // Horizontal wires: one continuous line per layout row
  for (var li3 = 0; li3 < layoutData.lines.length; li3++) {
    var line3 = layoutData.lines[li3];
    var cy3 = line3.y + (line3._rowH || C.lineH) / 2;
    var spanLeft = Infinity, spanRight = -Infinity;
    for (var si = 0; si < line3.items.length; si++) {
      var sit = line3.items[si];
      if (sit.kind === 'step' || sit.kind === 'branch-point') {
        spanLeft = Math.min(spanLeft, sit.x + sit.w / 2);
        spanRight = Math.max(spanRight, sit.x + sit.w / 2);
      } else if (sit.kind === 'rejoin-arrow') {
        spanRight = Math.max(spanRight, sit.x + sit.w);
      } else if (sit.kind === 'cond') {
        spanLeft = Math.min(spanLeft, sit.x + sit.w / 2);
        spanRight = Math.max(spanRight, sit.x + sit.w / 2);
      }
    }
    if (spanLeft < spanRight) {
      ctx.beginPath();
      ctx.moveTo(spanLeft, cy3);
      ctx.lineTo(spanRight, cy3);
      ctx.strokeStyle = C.grayWire;
      ctx.lineWidth = 2;
      ctx.setLineDash([]);
      ctx.stroke();
    }
  }

  // Vertical bars
  for (var vi = 0; vi < layoutData.vbars.length; vi++) {
    var vb = layoutData.vbars[vi];
    ctx.beginPath();
    ctx.moveTo(vb.x, vb.y1);
    ctx.lineTo(vb.x, vb.y2);
    ctx.strokeStyle = C.barColor;
    ctx.lineWidth = 2;
    if (vb.type === 'gate') ctx.setLineDash([4, 3]);
    else ctx.setLineDash([]);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // Elements (drawn on top of topology lines)
  if (!wiresOnly) {
  for (var li2 = 0; li2 < layoutData.lines.length; li2++) {
    var line2 = layoutData.lines[li2];
    var cy = line2.y + (line2._rowH || C.lineH) / 2;
    var lastItemRight = null;

    for (var ii9 = 0; ii9 < line2.items.length; ii9++) {
      var item3 = line2.items[ii9];
      switch (item3.kind) {
        case 'step': {
          var status = _nodeStatus(item3, execState);
          var fillColor = status === 'current' ? C.currentFill : status === 'completed' ? C.completedFill : C.white;
          var borderColor = status === 'current' ? C.currentBorder : status === 'completed' ? C.completedBorder : C.grayBorder;
          var dotColor = status === 'current' ? C.currentDot : status === 'completed' ? C.completedDot : C.grayDot;
          var textColor = status === 'current' ? C.currentText : status === 'completed' ? C.completedText : C.grayText;

          drawPill(ctx, item3.x, cy - item3.h / 2, item3.w, item3.h, C.stepR, fillColor, borderColor, 1.5);
          ctx.beginPath();
          ctx.arc(item3.x + C.stepPadX + C.dotR, cy, C.dotR, 0, Math.PI * 2);
          ctx.fillStyle = dotColor;
          ctx.fill();
          ctx.font = C.font;
          ctx.fillStyle = textColor;
          ctx.textBaseline = 'middle';
          // Multi-line text support
          var titleLines = item3.title.split('\n');
          if (titleLines.length === 1) {
            ctx.fillText(item3.title, item3.x + C.stepPadX + C.dotR * 2 + 5, cy);
          } else {
            var textLH = 15;
            var textStartY = cy - (titleLines.length - 1) * textLH / 2;
            for (var tli = 0; tli < titleLines.length; tli++) {
              ctx.fillText(titleLines[tli], item3.x + C.stepPadX + C.dotR * 2 + 5, textStartY + tli * textLH);
            }
          }
          break;
        }

        case 'wire':
          // Covered by the continuous horizontal line drawn above
          break;

        case 'ref':
          break;

        case 'branch-point': {
          var bpStatus = _nodeStatus(item3, execState);
          var bpFill = bpStatus === 'current' ? C.currentFill : bpStatus === 'completed' ? C.completedFill : C.bpBg;
          var bpBorder = bpStatus === 'current' ? C.currentBorder : bpStatus === 'completed' ? C.completedBorder : C.bpBorder;
          var bpTextC = bpStatus === 'current' ? C.currentText : bpStatus === 'completed' ? C.completedText : C.bpText;

          if (item3.type === 'gate') {
            var hh = item3.h / 2;
            var pointW = hh * 0.5;
            ctx.beginPath();
            ctx.moveTo(item3.x + pointW, cy - hh);
            ctx.lineTo(item3.x + item3.w - pointW, cy - hh);
            ctx.lineTo(item3.x + item3.w, cy);
            ctx.lineTo(item3.x + item3.w - pointW, cy + hh);
            ctx.lineTo(item3.x + pointW, cy + hh);
            ctx.lineTo(item3.x, cy);
            ctx.closePath();
            ctx.fillStyle = bpFill;
            ctx.fill();
            ctx.strokeStyle = bpBorder;
            ctx.lineWidth = 1.5;
            ctx.stroke();
          } else {
            drawPill(ctx, item3.x, cy - item3.h / 2, item3.w, item3.h, 4, bpFill, bpBorder, 1.5);
            ctx.strokeStyle = bpBorder;
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.moveTo(item3.x + 6, cy - item3.h / 2 + 5);
            ctx.lineTo(item3.x + 6, cy + item3.h / 2 - 5);
            ctx.moveTo(item3.x + 10, cy - item3.h / 2 + 5);
            ctx.lineTo(item3.x + 10, cy + item3.h / 2 - 5);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(item3.x + item3.w - 6, cy - item3.h / 2 + 5);
            ctx.lineTo(item3.x + item3.w - 6, cy + item3.h / 2 - 5);
            ctx.moveTo(item3.x + item3.w - 10, cy - item3.h / 2 + 5);
            ctx.lineTo(item3.x + item3.w - 10, cy + item3.h / 2 - 5);
            ctx.stroke();
          }
          ctx.font = C.fontBold;
          ctx.fillStyle = bpTextC;
          ctx.textBaseline = 'middle';
          ctx.textAlign = 'center';
          ctx.fillText(item3.title, item3.x + item3.w / 2, cy);
          ctx.textAlign = 'start';
          break;
        }

        case 'cond': {
          drawPill(ctx, item3.x, cy - item3.h / 2, item3.w, item3.h, item3.h / 2, C.condBg, C.grayBorder, 1.5);
          ctx.font = C.fontSmall;
          ctx.fillStyle = C.condText;
          ctx.textBaseline = 'middle';
          ctx.fillText(item3.text, item3.x + C.condPadX, cy);
          break;
        }

        case 'rejoin-arrow': {
          // Wire covered by continuous horizontal line; just draw arrowhead
          var ax = item3.x + item3.w;
          ctx.beginPath();
          ctx.moveTo(ax - 6, cy - 4);
          ctx.lineTo(ax, cy);
          ctx.lineTo(ax - 6, cy + 4);
          ctx.closePath();
          ctx.fillStyle = C.grayLight;
          ctx.fill();
          break;
        }
      }
      if (item3.kind !== 'ref') {
        lastItemRight = item3.x + (item3.w || 0);
      }
    }
  }
  } // end if (!wiresOnly)

}

// ── Convenience entry point ────────────────────────────────────────

function renderWorkflow(spine, canvas, execState, layoutOpts) {
  resetRefs();
  var rawLines = flattenSpine(spine, 0, null);
  _precomputeHeights(rawLines, layoutOpts);
  var lines = treeOrderLines(rawLines, layoutOpts);
  var layoutData = layout(lines, layoutOpts);
  if (canvas) drawSchematic(canvas, layoutData, execState || null);
  return layoutData;
}

// ═══════════════════════════════════════════════════════════════════
// SET SPINE HEIGHTS — inject measured heights into spine tree
// ═══════════════════════════════════════════════════════════════════

function setSpineHeights(spineArr, heightMap) {
  for (var si = 0; si < spineArr.length; si++) {
    var seg = spineArr[si];
    if (seg.id && heightMap[seg.id]) {
      seg.height = heightMap[seg.id];
    }
    if (seg.type === 'gate' && seg.routes) {
      for (var ri = 0; ri < seg.routes.length; ri++) {
        setSpineHeights(seg.routes[ri].path, heightMap);
      }
    }
    if (seg.type === 'split' && seg.branches) {
      for (var bi = 0; bi < seg.branches.length; bi++) {
        setSpineHeights(seg.branches[bi].path, heightMap);
      }
      if (seg.merge && seg.merge.id && heightMap[seg.merge.id]) {
        seg.merge.height = heightMap[seg.merge.id];
      }
    }
  }
}

// ═══════════════════════════════════════════════════════════════════
// HYBRID RENDERER — HTML nodes over canvas topology
// ═══════════════════════════════════════════════════════════════════
//
// Unified rendering pipeline:
//   1. Caller provides nodeRenderer(item, status) → HTML string
//   2. Measure node HTML in hidden container → height map
//   3. Inject heights into spine → run layout
//   4. Draw wires/bars on canvas (z:0)
//   5. Position HTML nodes absolutely (z:1)
//
// opts:
//   nodeRenderer(item, status)  — required, returns HTML string
//   condRenderer(item, status)  — optional, returns HTML for condition labels
//   nodeW        — fixed node width (0 = text-measured)
//   lineGap      — vertical gap between rows
//   onLayout(layoutData)  — optional callback after layout, before DOM population

var _cssInjected = false;
var _CSS = ''
  + '.sch-node-wrap { z-index:2; position:relative; display:flex; }'
  + '.sch-node-wrap::after { content:""; position:absolute; top:0; left:0; right:0; bottom:0; background:rgba(128,0,255,0.25); z-index:999; pointer-events:none; }'
  + '.sch-cond-wrap { z-index:2; position:relative; }'
  + '.sch-cond-wrap::after { content:""; position:absolute; top:0; left:0; right:0; bottom:0; background:rgba(128,0,255,0.25); z-index:999; pointer-events:none; }'
  + '.sch-cond { display:inline-flex; align-items:center; justify-content:center; padding:0 8px; border-radius:10px; height:20px; border:1.5px solid #e5e7eb; background:#f3f4f6; font:500 11px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; color:#374151; white-space:nowrap; }'
  + '.sch-pill { display:inline-flex; align-items:center; gap:5px; padding:4px 13px; border-radius:15px; min-height:30px; background:#fff; border:1.5px solid #e5e7eb; font:13px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; color:#374151; box-sizing:border-box; }'
  + '.sch-pill-dot { width:7px; height:7px; border-radius:50%; background:#6b7280; flex-shrink:0; }'
  + '.sch-pill-title { white-space:pre-line; line-height:1.3; }'
  + '.sch-bp { display:inline-flex; align-items:center; justify-content:center; padding:4px 13px; min-height:30px; background:#f3f4f6; border:1.5px solid #9ca3af; font:600 13px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; color:#374151; box-sizing:border-box; white-space:pre-line; text-align:center; line-height:1.3; }'
  + '.sch-bp-gate { clip-path:polygon(8% 0%,92% 0%,100% 50%,92% 100%,8% 100%,0% 50%); padding:4px 20px; }'
  + '.sch-bp-split { border-radius:4px; }'
  + '.sch-bp-split-bars { position:absolute; top:5px; bottom:5px; width:4px; }'
  + '.sch-bp-split-bars-l { left:4px; border-left:1.5px solid #9ca3af; border-right:1.5px solid #9ca3af; }'
  + '.sch-bp-split-bars-r { right:4px; border-left:1.5px solid #9ca3af; border-right:1.5px solid #9ca3af; }'
  + '.sch-node-current .sch-pill { background:#e3f2fd; border-color:#2a6bcf; color:#1a1a2e; }'
  + '.sch-node-current .sch-pill-dot { background:#2a6bcf; }'
  + '.sch-node-current .sch-bp { background:#e3f2fd; border-color:#2a6bcf; color:#1a1a2e; }'
  + '.sch-node-completed .sch-pill { background:#e8f5e9; border-color:#4caf50; color:#2e7d32; }'
  + '.sch-node-completed .sch-pill-dot { background:#4caf50; }'
  + '.sch-node-completed .sch-bp { background:#e8f5e9; border-color:#4caf50; color:#2e7d32; }'
  ;

function _injectCSS() {
  if (_cssInjected) return;
  var style = document.createElement('style');
  style.textContent = _CSS;
  document.head.appendChild(style);
  _cssInjected = true;
}

function renderHybrid(spine, container, execState, opts) {
  _injectCSS();
  if (!container || !spine || !spine.length) return null;
  opts = opts || {};

  var nodeRenderer = opts.nodeRenderer;
  if (!nodeRenderer) return null;

  var nodeW = opts.nodeW || 0;
  var lineGap = opts.lineGap !== undefined ? opts.lineGap : C.lineGap;

  // Collect all node IDs from the spine for measurement
  var nodeIds = [];
  (function collectIds(arr) {
    for (var i = 0; i < arr.length; i++) {
      var seg = arr[i];
      if (seg.id) nodeIds.push(seg.id);
      if (seg.type === 'gate' && seg.routes) {
        for (var ri = 0; ri < seg.routes.length; ri++) collectIds(seg.routes[ri].path);
      }
      if (seg.type === 'split' && seg.branches) {
        for (var bi = 0; bi < seg.branches.length; bi++) collectIds(seg.branches[bi].path);
        if (seg.merge && seg.merge.id) nodeIds.push(seg.merge.id);
      }
    }
  })(spine);

  // Build a title/kind map from spine for nodeRenderer calls during measurement
  var spineInfo = {};
  (function mapInfo(arr) {
    for (var i = 0; i < arr.length; i++) {
      var seg = arr[i];
      if (seg.id) spineInfo[seg.id] = { title: seg.title, kind: seg.type === 'gate' || seg.type === 'split' ? 'branch-point' : 'step', type: seg.type };
      if (seg.type === 'gate' && seg.routes) {
        for (var ri = 0; ri < seg.routes.length; ri++) mapInfo(seg.routes[ri].path);
      }
      if (seg.type === 'split' && seg.branches) {
        for (var bi = 0; bi < seg.branches.length; bi++) mapInfo(seg.branches[bi].path);
        if (seg.merge) spineInfo[seg.merge.id] = { title: seg.merge.title, kind: 'step', type: 'merge' };
      }
    }
  })(spine);

  // Phase 1: Measure — render each node into a hidden container.
  // Use display:flex on the wrapper to match the render context and
  // eliminate inline formatting artifacts (strut, baseline gaps).
  var measurer = document.createElement('div');
  measurer.style.cssText = 'position:absolute;left:-9999px;top:-9999px;visibility:hidden;'
    + (nodeW ? 'width:' + nodeW + 'px;' : '');
  document.body.appendChild(measurer);

  var heightMap = {};
  var widthMap = {};
  for (var ni = 0; ni < nodeIds.length; ni++) {
    var nid = nodeIds[ni];
    var info = spineInfo[nid] || { title: nid, kind: 'step', type: 'step' };
    var status = _nodeStatus({ id: nid }, execState);
    var html = nodeRenderer({ id: nid, kind: info.kind, type: info.type, title: info.title }, status);
    var mDiv = document.createElement('div');
    // display:inline-flex shrink-wraps both dimensions and eliminates
    // the inline strut that causes height discrepancies vs positioned divs
    mDiv.style.display = 'inline-flex';
    mDiv.innerHTML = html;
    measurer.appendChild(mDiv);
    heightMap[nid] = mDiv.offsetHeight;
    if (!nodeW) widthMap[nid] = mDiv.offsetWidth;
    measurer.removeChild(mDiv);
  }
  document.body.removeChild(measurer);

  // Phase 2: Inject heights + run layout
  setSpineHeights(spine, heightMap);
  var layoutOpts = { lineGap: lineGap };
  if (nodeW) layoutOpts.nodeW = nodeW;
  var layoutData = renderWorkflow(spine, null, execState, layoutOpts);

  // Phase 2b: When not using fixed nodeW, adjust item widths to match
  // measured DOM widths while preserving center positions for wire alignment.
  if (!nodeW) {
    for (var ali = 0; ali < layoutData.lines.length; ali++) {
      var aln = layoutData.lines[ali];
      for (var aii = 0; aii < aln.items.length; aii++) {
        var aitm = aln.items[aii];
        if ((aitm.kind === 'step' || aitm.kind === 'branch-point') && aitm.id && widthMap[aitm.id]) {
          var measuredW = widthMap[aitm.id];
          var cx = aitm.x + aitm.w / 2;  // preserve center
          aitm.x = cx - measuredW / 2;
          aitm.w = measuredW;
        }
      }
    }
  }

  if (opts.onLayout) opts.onLayout(layoutData);

  // Phase 3: Draw topology canvas
  var topoCanvas = document.createElement('canvas');
  topoCanvas.style.cssText = 'position:absolute;left:0;top:0;z-index:0;pointer-events:none;';
  drawSchematic(topoCanvas, layoutData, execState || null, { wiresOnly: true });

  // Phase 4: Build positioned HTML nodes
  var nodesHtml = '';
  var condRenderer = opts.condRenderer || null;

  for (var li = 0; li < layoutData.lines.length; li++) {
    var ln = layoutData.lines[li];
    var rowH = ln._rowH || C.lineH;
    for (var ii = 0; ii < ln.items.length; ii++) {
      var itm = ln.items[ii];

      if ((itm.kind === 'step' || itm.kind === 'branch-point') && itm.id) {
        var itemInfo = spineInfo[itm.id] || { title: itm.title, kind: itm.kind, type: itm.kind };
        var itemStatus = _nodeStatus(itm, execState);
        var nodeHtml = nodeRenderer(
          { id: itm.id, kind: itm.kind, type: itemInfo.type, title: itm.title, w: itm.w, h: itm.h },
          itemStatus
        );
        var ch = heightMap[itm.id] || rowH;
        var nodeTop = ln.y + (rowH - ch) / 2;
        nodesHtml += '<div class="sch-node-wrap sch-node-' + itemStatus
            + '" style="position:absolute;left:' + itm.x + 'px;top:' + nodeTop + 'px;width:' + itm.w + 'px;z-index:1;">'
            + nodeHtml + '</div>';
      }

      if (itm.kind === 'cond') {
        var condCy = ln.y + rowH / 2;
        if (condRenderer) {
          var condStatus = 'pending';
          nodesHtml += '<div class="sch-cond-wrap" style="position:absolute;left:' + itm.x + 'px;top:' + (condCy - itm.h / 2)
              + 'px;width:' + itm.w + 'px;height:' + itm.h + 'px;z-index:1;">'
              + condRenderer({ text: itm.text, type: itm.type, w: itm.w, h: itm.h }, condStatus)
              + '</div>';
        } else {
          // Default condition label
          nodesHtml += '<div class="sch-cond-wrap" style="position:absolute;left:' + itm.x + 'px;top:' + (condCy - itm.h / 2)
              + 'px;z-index:1;"><div class="sch-cond">' + _escHtml(itm.text) + '</div></div>';
        }
      }
    }
  }

  // Phase 5: Populate container
  container.style.position = 'relative';
  container.style.width = layoutData.width + 'px';
  container.style.minHeight = layoutData.height + 'px';
  container.innerHTML = nodesHtml;
  container.insertBefore(topoCanvas, container.firstChild);

  return layoutData;
}

// Minimal HTML escaping for default renderers
function _escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Public API ─────────────────────────────────────────────────────

return {
  C: C,
  resetRefs: resetRefs,
  flattenSpine: flattenSpine,
  treeOrderLines: treeOrderLines,
  layout: layout,
  drawSchematic: drawSchematic,
  drawPill: drawPill,
  definitionToSpine: definitionToSpine,
  renderWorkflow: renderWorkflow,
  renderHybrid: renderHybrid,
  setSpineHeights: setSpineHeights,
  _nodeStatus: _nodeStatus,
  tw: tw,
};

})();
