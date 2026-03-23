// ═══════════════════════════════════════════════════════════════════
// Workflow Console — Full-stack element architecture demo.
// One JSON document. Every screen is a focus depth. Every click is a POST.
// Self-contained — no dependencies on engine code.
// ═══════════════════════════════════════════════════════════════════

(function () {
  "use strict";

  // ═══════════════════════════════════════════════════════════════
  // RENDERER REGISTRY
  // ═══════════════════════════════════════════════════════════════
  var R = {};

  function renderElement(data, path) {
    if (!path) path = [];
    var type = data && data.element;
    var fn = type && R[type];
    var html = fn ? fn(data, path)
      : '<div class="el-error">'
        + rn(path,"element",'<div class="el-error-type">Unknown: '+esc(type||"(none)")+'</div>')
        + '</div>';
    if (data && data._focus_aff) {
      html = '<div class="el-focusable">' + html + focusBtn(data._focus_aff) + '</div>';
    }
    return html;
  }

  // ── Helpers ────────────────────────────────────────────────────
  function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}
  function escA(s){return String(s).replace(/&/g,"&amp;").replace(/"/g,"&quot;")}
  function rn(bp,sf,inner){return '<span class="r-node" data-path="'+escA(bp.concat(sf.split(".")).join("."))+'">'+inner+'</span>'}
  function affAttrs(a,key){
    return ' data-aff-method="'+escA(a.method)+'" data-aff-url="'+escA(a.url)+'"'
      +' data-aff-body="'+escA(JSON.stringify(a.body||{}))+'" data-aff-key="'+escA(key||"")+'"';
  }
  function focusBtn(a){
    return '<button class="el-focus-btn"'+affAttrs(a,"__focus__")
      +' data-aff-value="'+escA(JSON.stringify(a.body.focus))+'">'+esc(a.label)+'</button>';
  }

  // ═══════════════════════════════════════════════════════════════
  // RENDERERS
  // ═══════════════════════════════════════════════════════════════

  // ── group ──
  R["group"] = function(g,p){
    var h = '<div class="el-group">';
    if(g.label) h += rn(p,"label",'<div class="el-group-label">'+esc(g.label)+'</div>');
    h += '<div class="el-group-children">';
    if(g.children) g.children.forEach(function(c,i){
      h += rn(p,"children."+i, renderElement(c, p.concat("children",""+i)));
    });
    return h + '</div></div>';
  };

  // ── field ──
  R["field"] = function(f,p){
    var h = '<div class="el-field">';
    h += rn(p,"label",'<div class="el-field-label">'+esc(f.label)+'</div>');
    if(f.instruction) h += rn(p,"instruction",'<div class="el-field-instruction">'+esc(f.instruction)+'</div>');
    var vClass = "el-field-value"+(f.value===null?" empty":"");
    h += rn(p,"value",'<div class="'+vClass+'">'+fmtVal(f.type,f.value)+'</div>');
    if(f.affordance) h += rn(p,"affordance",'<div class="el-aff">'+fieldAff(f,p)+'</div>');
    return h + '</div>';
  };
  function fmtVal(t,v){
    if(v===null) return "Not set";
    if(t==="boolean") return v?'<span style="color:#2e7d32;font-weight:600">True</span>':'<span style="color:#c62828;font-weight:600">False</span>';
    if(t==="computed") return '<span style="color:#555;font-style:italic">'+esc(v)+'</span>';
    return esc(v);
  }
  function fieldAff(f,p){
    var a=f.affordance, pr=a.parameters, at=affAttrs(a,f.key);
    if(pr&&pr.value&&pr.value.options){
      var b="";
      pr.value.options.forEach(function(o){
        var act=String(o)===String(f.value), cls="el-aff-opt"+(act?" active":"");
        var lab=typeof o==="boolean"?(o?"True":"False"):esc(o);
        b+='<button class="'+cls+'"'+at+' data-aff-value="'+escA(JSON.stringify(o))+'">'+lab+'</button>';
      });
      return '<div class="el-aff-row">'+b+'</div>';
    }
    var ph=f.value!==null?String(f.value):f.label;
    return '<div class="el-aff-row"><input class="el-aff-input" type="text" placeholder="'+escA(ph)+'">'
      +'<button class="el-aff-btn"'+at+'>Set</button></div>';
  }

  // ── badge ──
  R["badge"] = function(b,p){
    var v=b.variant||"info";
    return '<div class="el-badge '+v+'">'
      +(b.label?rn(p,"label",'<span class="el-badge-label">'+esc(b.label)+'</span>'):'')
      +rn(p,"value",'<span>'+esc(b.value)+'</span>')+'</div>';
  };

  // ── note ──
  R["note"] = function(n,p){ return rn(p,"text",'<div class="el-note">'+esc(n.text)+'</div>'); };

  // ── action ──
  R["action"] = function(a,p){
    var v=a.variant||"secondary";
    return '<div class="el-action">'+rn(p,"label",
      '<button class="el-action-btn '+v+'"'+affAttrs(a,"__action__")
      +' data-aff-value="'+escA(JSON.stringify(a.label))+'">'+esc(a.label)+'</button>')+'</div>';
  };

  // ── stat ──
  R["stat"] = function(s,p){
    var vc=s.variant?" "+s.variant:"";
    return '<div class="el-stat">'
      +rn(p,"value",'<div class="el-stat-value'+vc+'">'+esc(s.value)
        +(s.suffix?'<span class="el-stat-suffix"> '+esc(s.suffix)+'</span>':'')+'</div>')
      +rn(p,"label",'<div class="el-stat-label">'+esc(s.label)+'</div>')+'</div>';
  };

  // ── progress ──
  R["progress"] = function(pr,p){
    var pct=pr.max>0?Math.round(pr.value/pr.max*100):0;
    var v=pr.variant||(pct>=100?"success":"info");
    return '<div class="el-progress">'
      +'<div class="el-progress-label"><span>'+esc(pr.label)+'</span><span>'+pr.value+' / '+pr.max+'</span></div>'
      +'<div class="el-progress-bar"><div class="el-progress-fill '+v+'" style="width:'+pct+'%"></div></div></div>';
  };

  // ── step ──
  R["step"] = function(s,p){
    var st=s.status||"locked";
    var icons={complete:"\u2713",active:"\u25B6",locked:"\u2022",failed:"\u2717"};
    var h='<div class="el-step '+st+'">'
      +'<div class="el-step-icon '+st+'">'+icons[st]+'</div>'
      +'<div class="el-step-body">'
      +rn(p,"label",'<div class="el-step-label '+st+'">'+esc(s.label)+'</div>');
    if(st==="active"&&s.children&&s.children.length){
      h+='<div class="el-step-children">';
      s.children.forEach(function(c,i){
        h+=rn(p,"children."+i,renderElement(c,p.concat("children",""+i)));
      });
      h+='</div>';
    }
    return h+'</div></div>';
  };

  // ── alert ──
  R["alert"] = function(a,p){
    var icons={info:"\u2139",warning:"\u26A0",error:"\u2716"};
    var v=a.variant||"info";
    return '<div class="el-alert '+v+'">'
      +'<span class="el-alert-icon">'+(icons[v]||"")+'</span>'
      +rn(p,"text",'<span>'+esc(a.text)+'</span>')+'</div>';
  };

  // ── toggle ──
  R["toggle"] = function(t,p){
    var on=!!t.value, cls=on?"on":"off";
    var a=t.affordance;
    return '<div class="el-toggle">'
      +rn(p,"label",'<span>'+esc(t.label)+'</span>')
      +'<button class="el-toggle-track '+cls+'"'+affAttrs(a,t.key)
      +' data-aff-value="'+escA(JSON.stringify(!on))+'">'
      +'<div class="el-toggle-thumb"></div></button></div>';
  };

  // ── divider ──
  R["divider"] = function(d,p){
    return '<div class="el-divider"><div class="el-divider-line"></div>'
      +(d.label?'<div class="el-divider-label">'+esc(d.label)+'</div><div class="el-divider-line"></div>':'')
      +'</div>';
  };

  // ── status_bar ──
  R["status_bar"] = function(sb,p){
    var h='<div class="el-status-bar">';
    sb.items.forEach(function(it,i){
      h+=rn(p,"items."+i,'<div class="el-status-bar-item">'
        +'<div class="el-status-bar-label">'+esc(it.label)+'</div>'
        +'<div class="el-status-bar-value">'+esc(it.value)+'</div></div>');
    });
    return h+'</div>';
  };

  // ── gated_action ──
  R["gated_action"] = function(ga,p){
    var open=ga.gate_open;
    if(open){
      return '<div class="el-gated"><button class="el-gated-btn unlocked"'
        +affAttrs(ga,"__action__")+' data-aff-value="'+escA(JSON.stringify(ga.label))+'">'
        +esc(ga.label)+'</button></div>';
    }
    return '<div class="el-gated"><button class="el-gated-btn locked" disabled>'
      +esc(ga.label)+'</button>'
      +'<span class="el-gated-msg">'+esc(ga.gate_message||"Locked")+'</span></div>';
  };

  // ── summary ──
  R["summary"] = function(s,p){
    var h='<div class="el-summary">';
    h+=rn(p,"type",'<span class="el-summary-type">'+esc(s.type)+'</span>');
    h+=rn(p,"label",'<span class="el-summary-label">'+esc(s.label)+'</span>');
    if(s.child_count!=null) h+=rn(p,"child_count",'<span class="el-summary-meta">'+s.child_count+' items</span>');
    else if(s.preview) h+=rn(p,"preview",'<span class="el-summary-preview">'+esc(s.preview)+'</span>');
    if(s.status_icon) h+='<span class="el-step-icon '+s.status_icon+'" style="width:14px;height:14px;font-size:0.5rem;margin-left:auto">'
      +({complete:"\u2713",active:"\u25B6",locked:"\u2022",failed:"\u2717"}[s.status_icon]||"")+'</span>';
    return h+'</div>';
  };

  // ── view ──
  R["view"] = function(v,p){
    var h='<div class="el-view">';
    // Breadcrumb
    if(v.breadcrumb&&v.breadcrumb.length){
      h+='<div class="el-breadcrumb">';
      v.breadcrumb.forEach(function(seg,i){
        if(i>0) h+='<span class="el-breadcrumb-sep">\u203A</span>';
        if(seg.focus_path!==undefined){
          h+='<button class="el-breadcrumb-seg"'+affAttrs({method:"POST",url:"/focus",body:{focus:seg.focus_path}},"__focus__")
            +' data-aff-value="'+escA(JSON.stringify(seg.focus_path))+'">'+esc(seg.label)+'</button>';
        } else {
          h+='<span class="el-breadcrumb-current">'+esc(seg.label)+'</span>';
        }
      });
      if(v.auto_focus) h+=' <span class="el-auto-badge">AUTO</span>';
      h+='</div>';
    }
    // Scope bar
    if(v.scope_affordances&&v.scope_affordances.length){
      h+='<div class="el-scope-bar">';
      v.scope_affordances.forEach(function(a){
        var cls="el-scope-btn"+(a.label==="Unfocus"?" el-scope-unfocus":"");
        h+='<button class="'+cls+'"'+affAttrs(a,"__focus__")
          +(a.body.focus!==undefined?' data-aff-value="'+escA(JSON.stringify(a.body.focus))+'"':'')
          +'>'+esc(a.label)+'</button>';
      });
      h+='</div>';
    }
    if(v.content) h+=rn(p,"content",renderElement(v.content,p.concat("content")));
    return h+'</div>';
  };

  // ═══════════════════════════════════════════════════════════════
  // COMPUTED VALUES
  // Walk the state tree and compute derived values before projection.
  // ═══════════════════════════════════════════════════════════════

  function computeState(state){
    var root=state.data;
    if(root.element!=="group"||!root.children) return;
    // Walk work items (skip header/alert)
    root.children.forEach(function(child){
      if(child.element==="group"&&child._type==="work_item"){
        computeWorkItem(child);
      }
    });
  }

  function computeWorkItem(item){
    var steps=[], total=0, done=0, failed=0;
    walkSteps(item, steps);
    steps.forEach(function(s){
      total++;
      if(s.status==="complete") done++;
      if(s.status==="failed") failed++;
    });
    // Update progress children
    walkAll(item, function(node){
      if(node.element==="progress"&&node._computed){
        node.value=done; node.max=total;
        node.variant=failed>0?"error":(done===total?"success":"info");
      }
      if(node.element==="gated_action"){
        node.gate_open=(done===total&&total>0&&failed===0);
        node.gate_message=done<total?"Complete all "+total+" steps first ("+done+"/"+total+" done)"
          :failed>0?failed+" step(s) failed — resolve before approval":"";
      }
    });
  }

  function walkSteps(node, out){
    if(node.element==="step") out.push(node);
    if(node.children) node.children.forEach(function(c){ walkSteps(c,out); });
  }

  function walkAll(node, fn){
    fn(node);
    if(node.children) node.children.forEach(function(c){ walkAll(c,fn); });
    if(node.items) node.items.forEach(function(c){ walkAll(c,fn); });
  }

  // ═══════════════════════════════════════════════════════════════
  // PROJECTION
  // ═══════════════════════════════════════════════════════════════

  function project(state){
    computeState(state);
    var focus=state.focus, root=state.data;
    var bc=buildBreadcrumb(root, focus, state.auto_focus);

    if(!focus){
      return { element:"view", breadcrumb:bc, scope_affordances:[], auto_focus:state.auto_focus,
        content: summarize(root,"") };
    }

    var target=resolvePath(root,focus);
    if(!target) return { element:"view", breadcrumb:bc,
      scope_affordances:[unfocusAff()], content:summarize(root,"") };

    var scopeAffs=[unfocusAff()];
    var sib=getSiblings(root,focus);
    if(sib.prev) scopeAffs.push({label:"\u2190 "+sibLabel(root,sib.prev),method:"POST",url:"/focus",body:{focus:sib.prev}});
    if(sib.next) scopeAffs.push({label:sibLabel(root,sib.next)+" \u2192",method:"POST",url:"/focus",body:{focus:sib.next}});

    var content;
    if(target.element==="group"||target.element==="step"){
      content=summarize(target,focus);
    } else {
      content=deepCopy(target);
    }

    return { element:"view", breadcrumb:bc, scope_affordances:scopeAffs,
      auto_focus:state.auto_focus, content:content };
  }

  function summarize(node,prefix){
    if(!node) return node;
    var hasKids = (node.element==="group"||node.element==="step") && node.children && node.children.length;
    if(!hasKids) return deepCopy(node);

    var copy={element:node.element, label:node.label, children:[]};
    if(node._type) copy._type=node._type;
    if(node.status) copy.status=node.status;
    node.children.forEach(function(child,i){
      var fp=prefix?prefix+".children."+i:"children."+i;
      copy.children.push(makeSummary(child,fp));
    });
    return copy;
  }

  function makeSummary(node,fp){
    var label=node.label||node.key||node.element;
    var preview=null, childCount=null, statusIcon=null;
    if(node.element==="field"){
      if(node.value!=null) preview=typeof node.value==="boolean"?(node.value?"True":"False"):String(node.value);
    } else if((node.element==="group"||node.element==="step")&&node.children){
      childCount=node.children.length;
    }
    if(node.element==="step") statusIcon=node.status||"locked";
    if(node.element==="badge") preview=String(node.value);
    if(node.element==="note") preview=node.text&&node.text.length>50?node.text.substring(0,50)+"\u2026":node.text;
    if(node.element==="action") preview=node.method+" "+node.url;
    if(node.element==="progress") preview=node.value+"/"+node.max;
    if(node.element==="gated_action") preview=node.gate_open?"Ready":"Locked";
    if(node.element==="toggle") preview=node.value?"On":"Off";
    if(node.element==="alert") preview=node.text&&node.text.length>40?node.text.substring(0,40)+"\u2026":node.text;

    return { element:"summary", type:node.element, label:label, preview:preview,
      child_count:childCount, status_icon:statusIcon,
      _focus_aff:{label:"Focus",method:"POST",url:"/focus",body:{focus:fp}} };
  }

  function buildBreadcrumb(root,focus,autoFocus){
    var crumbs=[{label:root.label||"Console",focus_path:focus?null:undefined}];
    if(!focus){
      crumbs[0]={label:root.label||"Console"};
      return crumbs;
    }
    crumbs[0].focus_path=null; // clickable → unfocus
    var parts=focus.split("."), built="";
    for(var i=0;i<parts.length;i++){
      built+=(i>0?".":"")+parts[i];
      var node=resolvePath(root,built);
      if(node&&(node.label||node.key)){
        if(i<parts.length-1){
          crumbs.push({label:node.label||node.key, focus_path:built});
        } else {
          crumbs.push({label:node.label||node.key});
        }
      }
    }
    return crumbs;
  }

  function unfocusAff(){return{label:"Unfocus",method:"POST",url:"/focus",body:{focus:null}}}

  // ═══════════════════════════════════════════════════════════════
  // AGENT JSON PROJECTION
  // Produces what an agent actually sees: state (data visible at
  // this focus level), affordances (what the agent can do), and
  // navigation (how to move focus). Clean, flat, action-oriented.
  // No rendering metadata, no element types, no internal fields.
  // ═══════════════════════════════════════════════════════════════

  function projectAgent(state){
    computeState(state);
    var focus=state.focus, root=state.data;
    var result = { focus: focus, auto_focus: state.auto_focus, state: {}, affordances: [], navigation: [] };

    // Navigation: breadcrumb ancestors + unfocus + siblings
    if(focus){
      result.navigation.push({rel:"unfocus",label:"Unfocus",method:"POST",url:"/focus",body:{focus:null}});
      // Ancestor breadcrumb links (intermediate focus levels)
      var parts=focus.split("."), built="";
      for(var i=0;i<parts.length-1;i++){
        built+=(i>0?".":"")+parts[i];
        var ancestor=resolvePath(root,built);
        if(ancestor&&(ancestor.label||ancestor.key)){
          result.navigation.push({rel:"ancestor",label:ancestor.label||ancestor.key,
            method:"POST",url:"/focus",body:{focus:built}});
        }
      }
      // Sibling navigation
      var sib=getSiblings(root,focus);
      if(sib.prev) result.navigation.push({rel:"prev",label:sibLabel(root,sib.prev),method:"POST",url:"/focus",body:{focus:sib.prev}});
      if(sib.next) result.navigation.push({rel:"next",label:sibLabel(root,sib.next),method:"POST",url:"/focus",body:{focus:sib.next}});
    }

    // Toggle auto-focus is always available
    result.affordances.push({rel:"setting",label:(state.auto_focus?"Disable":"Enable")+" Auto-focus",
      method:"POST",url:"/toggle/auto_focus",body:{value:!state.auto_focus}});

    if(!focus){
      agentRootView(root, result);
    } else {
      var target=resolvePath(root,focus);
      if(!target) return result;
      agentNodeView(target, focus, root, result);
    }
    return result;
  }

  function agentRootView(root, result){
    var items=[];
    root.children.forEach(function(child,i){
      if(child._type==="work_item"){
        var steps=[],done=0;
        walkSteps(child,steps);
        steps.forEach(function(s){if(s.status==="complete")done++});
        items.push({
          label:child.label,
          status:findBadgeWithVariant(child,"Status"),
          priority:findBadgeWithVariant(child,"Priority"),
          assigned:findStatusBarItem(child,"Assigned"),
          due:findStatusBarItem(child,"Due"),
          progress:done+"/"+steps.length,
          focus:{method:"POST",url:"/focus",body:{focus:"children."+i}}
        });
      }
    });
    result.state.work_items=items;
    // Alerts with severity
    var alerts=[];
    walkAll(root,function(n){if(n.element==="alert")alerts.push({text:n.text,severity:n.variant||"info"})});
    if(alerts.length) result.state.alerts=alerts;
  }

  function agentNodeView(target, focus, root, result){
    if(target.element==="step"){
      // Step detail: show fields, notes, instructions, and step actions from state
      result.state.step=target.label;
      result.state.status=target.status;
      if(target.children){
        var fields={}, notes=[];
        target.children.forEach(function(child){
          if(child.element==="field"){
            var f={label:child.label, value:child.value, type:child.type};
            if(child.instruction) f.instruction=child.instruction;
            fields[child.key]=f;
            if(child.affordance) result.affordances.push(agentFieldAff(child));
          } else if(child.element==="note"){
            notes.push(child.text);
          } else if(child.element==="action"){
            // Read affordances from the state tree, not hardcoded
            result.affordances.push({rel:"action",label:child.label,method:child.method,url:child.url,body:child.body||{}});
          }
        });
        result.state.fields=fields;
        if(notes.length) result.state.notes=notes;
      }
      return;
    }

    if(target._type==="work_item"){
      result.state.title=target.label;
      result.state.status=findBadgeWithVariant(target,"Status");
      result.state.priority=findBadgeWithVariant(target,"Priority");
      result.state.assigned=findStatusBarItem(target,"Assigned");
      result.state.due=findStatusBarItem(target,"Due");
      var steps=[];
      walkSteps(target,steps);
      var done=0;steps.forEach(function(s){if(s.status==="complete")done++});
      result.state.progress=done+"/"+steps.length;
      result.state.steps=[];
      target.children.forEach(function(topChild,ti){
        if(topChild.element==="group"&&topChild.label==="Steps"&&topChild.children){
          topChild.children.forEach(function(step,si){
            var sp=focus+".children."+ti+".children."+si;
            result.state.steps.push({label:step.label,status:step.status,
              focus:{method:"POST",url:"/focus",body:{focus:sp}}});
          });
        }
      });
      // Gated action
      walkAll(target,function(n){
        if(n.element==="gated_action"){
          if(n.gate_open) result.affordances.push({rel:"action",label:n.label,method:n.method,url:n.url,body:n.body});
          else result.state.gate={label:n.label,locked:true,reason:n.gate_message};
        }
      });
      return;
    }

    // Generic group: list children as focusable items
    if(target.element==="group"&&target.children){
      result.state.label=target.label;
      result.state.items=[];
      target.children.forEach(function(child,i){
        var fp=focus+".children."+i;
        var item={label:child.label||child.key||child.element, type:child.element};
        if(child.element==="field") item.value=child.value;
        if(child.element==="step") item.status=child.status;
        item.focus={method:"POST",url:"/focus",body:{focus:fp}};
        result.state.items.push(item);
      });
    }
  }

  function agentFieldAff(field){
    var a={rel:"field",label:"Set "+field.label,method:field.affordance.method,url:field.affordance.url};
    // Use concrete body with parameters instead of "{input}" placeholder
    a.body={value:null};
    if(field.affordance.parameters) a.parameters=field.affordance.parameters;
    else a.parameters={value:{type:field.type==="boolean"?"boolean":"string"}};
    return a;
  }

  function findBadgeWithVariant(node,label){
    var val=null;
    walkAll(node,function(n){if(n.element==="badge"&&n.label===label)val={value:n.value,variant:n.variant||"info"}});
    return val;
  }

  function findStatusBarItem(node,label){
    var val=null;
    walkAll(node,function(n){
      if(n.element==="status_bar"&&n.items){
        n.items.forEach(function(it){if(it.label===label)val=it.value});
      }
    });
    return val;
  }

  function resolvePath(root,path){
    var parts=path.split("."),node=root;
    for(var i=0;i<parts.length;i++){
      if(!node) return null;
      node=Array.isArray(node)?node[parseInt(parts[i],10)]:node[parts[i]];
    }
    return node||null;
  }

  function getSiblings(root,fp){
    var parts=fp.split("."),idx=parseInt(parts[parts.length-1],10);
    if(isNaN(idx)) return{prev:null,next:null};
    var pp=parts.slice(0,-1).join("."),parent=pp?resolvePath(root,pp):root;
    if(!Array.isArray(parent)) return{prev:null,next:null};
    var pre=pp?pp+".":"";
    return{prev:idx>0?pre+(idx-1):null, next:idx<parent.length-1?pre+(idx+1):null};
  }

  function sibLabel(root,path){
    var t=resolvePath(root,path);
    return t?(t.label||t.key||path):path;
  }

  function deepCopy(o){return JSON.parse(JSON.stringify(o))}

  // ═══════════════════════════════════════════════════════════════
  // HUMAN OBSERVER (full render with dimming)
  // ═══════════════════════════════════════════════════════════════

  function renderHuman(state){
    computeState(state);
    return renderHumanNode(deepCopy(state.data),[],state.focus,"");
  }

  function renderHumanNode(node,path,focus,cp){
    if(!node||typeof node!=="object") return "";
    var type=node.element, fn=type&&R[type], html;

    if((type==="group"||type==="step")&&node.children){
      var tag=type==="step"?"el-step "+((node.status)||"locked"):"el-group";
      html='<div class="'+tag+'">';
      if(type==="step"){
        var icons={complete:"\u2713",active:"\u25B6",locked:"\u2022",failed:"\u2717"};
        html+='<div class="el-step-icon '+(node.status||"locked")+'">'+(icons[node.status||"locked"])+'</div><div class="el-step-body">';
        html+='<div class="el-step-label '+(node.status||"")+'">' +esc(node.label)+'</div>';
        if(node.status==="active"){
          html+='<div class="el-step-children">';
          node.children.forEach(function(c,i){
            var childCp=cp?cp+".children."+i:"children."+i;
            html+=renderHumanNode(c,path.concat("children",""+i),focus,childCp);
          });
          html+='</div>';
        }
        html+='</div></div>';
      } else {
        if(node.label) html+='<div class="el-group-label">'+esc(node.label)+'</div>';
        html+='<div class="el-group-children">';
        node.children.forEach(function(c,i){
          var childCp=cp?cp+".children."+i:"children."+i;
          html+=renderHumanNode(c,path.concat("children",""+i),focus,childCp);
        });
        html+='</div></div>';
      }
    } else if(fn){
      html=fn(node,path);
    } else {
      html=renderElement(node,path);
    }

    var dim=getDim(cp,focus);
    return '<div class="'+dim+'">'+html+'</div>';
  }

  function getDim(cp,focus){
    if(!focus) return "ho-focused";
    if(!cp) return "ho-focused";
    if(cp===focus) return "ho-focused";
    if(focus.indexOf(cp+".")===0) return "ho-focused";
    if(cp.indexOf(focus+".")===0) return "ho-focused";
    return "ho-dimmed";
  }

  // ═══════════════════════════════════════════════════════════════
  // MUTATION
  // ═══════════════════════════════════════════════════════════════

  function applyMutation(state,key,body,url){
    // Focus
    if(key==="__focus__"){
      state.focus=body.focus!=null?body.focus:null;
      return;
    }
    // Step complete/fail
    if(url&&url.match(/^\/step\/(.+)\/(complete|fail)$/)){
      var m=url.match(/^\/step\/(.+)\/(complete|fail)$/);
      var stepKey=m[1], action=m[2];
      var step=findNode(state.data,function(n){return n.element==="step"&&n.key===stepKey});
      if(step){
        step.status=action==="complete"?"complete":"failed";
        activateNextStep(state.data);
        if(state.auto_focus) autoAdvanceFocus(state);
      }
      return;
    }
    // Toggle
    if(key==="auto_focus"){
      state.auto_focus=!state.auto_focus;
      return;
    }
    // Gated action
    if(url&&url.match(/^\/item\/(.+)\/approve$/)){
      var itemKey=url.match(/^\/item\/(.+)\/approve$/)[1];
      var item=findNode(state.data,function(n){return n._type==="work_item"&&n._key===itemKey});
      if(item){
        // Set status badge to Approved
        walkAll(item,function(n){
          if(n.element==="badge"&&n.label==="Status"){n.value="Approved";n.variant="success";}
        });
      }
      return;
    }
    // Field value
    if(body.value!==undefined){
      applyFieldMut(state.data,key,body.value);
    }
  }

  function applyFieldMut(node,key,val){
    if(node.element==="field"&&node.key===key){node.value=val;return true}
    if(node.element==="toggle"&&node.key===key){node.value=val;return true}
    if(node.children){for(var i=0;i<node.children.length;i++){if(applyFieldMut(node.children[i],key,val))return true}}
    return false;
  }

  function findNode(node,pred){
    if(pred(node)) return node;
    if(node.children){for(var i=0;i<node.children.length;i++){var r=findNode(node.children[i],pred);if(r)return r}}
    return null;
  }

  /** After a step completes, activate the next locked step. */
  function activateNextStep(root){
    var steps=[];
    walkSteps(root,steps);
    var foundComplete=false, activated=false;
    steps.forEach(function(s){
      if(s.status==="complete"){foundComplete=true;return}
      if(!activated&&s.status==="locked"){s.status="active";activated=true}
    });
  }

  /** Auto-focus: find the next active step and focus on it. */
  function autoAdvanceFocus(state){
    var path=findPathOf(state.data,function(n){return n.element==="step"&&n.status==="active"},"");
    if(path) state.focus=path;
  }

  function findPathOf(node,pred,cp){
    if(pred(node)) return cp;
    if(node.children){
      for(var i=0;i<node.children.length;i++){
        var childCp=cp?(cp+".children."+i):"children."+i;
        var r=findPathOf(node.children[i],pred,childCp);
        if(r) return r;
      }
    }
    return null;
  }

  // ═══════════════════════════════════════════════════════════════
  // JSON SYNTAX HIGHLIGHTING
  // ═══════════════════════════════════════════════════════════════

  function jsonToHtml(v,p,ind){
    if(ind===undefined)ind=0;if(!p)p=[];
    var pad="  ".repeat(ind),pad1="  ".repeat(ind+1);
    if(v===null)return sp("j-null","null");
    if(typeof v==="boolean")return sp("j-bool",String(v));
    if(typeof v==="number")return sp("j-num",String(v));
    if(typeof v==="string")return sp("j-str",'"'+esc(v)+'"');
    if(Array.isArray(v)){
      if(!v.length)return sp("j-brace","[]");
      var o=sp("j-brace","[")+"\n";
      v.forEach(function(it,i){var q=p.concat(""+i),cm=i<v.length-1?",":"";
        o+=je(q,pad1+jsonToHtml(it,q,ind+1)+cm)+"\n"});
      return o+pad+sp("j-brace","]");
    }
    var ks=Object.keys(v).filter(function(k){return k[0]!=="_"});
    if(!ks.length)return sp("j-brace","{}");
    var o=sp("j-brace","{")+"\n";
    ks.forEach(function(k,i){var q=p.concat(k),cm=i<ks.length-1?",":"";
      o+=je(q,pad1+sp("j-key",'"'+esc(k)+'"')+": "+jsonToHtml(v[k],q,ind+1)+cm)+"\n"});
    return o+pad+sp("j-brace","}");
  }
  function sp(c,t){return'<span class="'+c+'">'+t+'</span>'}
  function je(p,inner){return'<span class="j-entry" data-path="'+escA(p.join("."))+'">'+inner+'</span>'}

  // ═══════════════════════════════════════════════════════════════
  // AFFORDANCE HANDLER + TOOLTIP
  // ═══════════════════════════════════════════════════════════════

  function resolveAff(btn){
    var method=btn.getAttribute("data-aff-method"),url=btn.getAttribute("data-aff-url"),
      bt=JSON.parse(btn.getAttribute("data-aff-body")),val;
    if(btn.hasAttribute("data-aff-value")) val=JSON.parse(btn.getAttribute("data-aff-value"));
    else{var inp=btn.closest(".el-aff-row");inp=inp&&inp.querySelector(".el-aff-input");val=inp?inp.value:null}
    var body={};Object.keys(bt).forEach(function(k){body[k]=bt[k]==="{input}"?val:bt[k]});
    return{method:method,url:url,body:body};
  }

  function setupHandler(appEl,getState,rerender){
    appEl.addEventListener("click",function(e){
      var btn=e.target.closest("[data-aff-url]");if(!btn)return;
      var r=resolveAff(btn);
      fetch(r.url,{method:r.method,headers:{"Content-Type":"application/json"},body:JSON.stringify(r.body)});
      var key=btn.getAttribute("data-aff-key"),state=getState();
      applyMutation(state,key,r.body,r.url);
      rerender();
    });

    var tip=document.createElement("div");tip.className="wc-tooltip";tip.style.display="none";
    document.body.appendChild(tip);

    appEl.addEventListener("mouseover",function(e){
      var btn=e.target.closest("[data-aff-url]");
      if(!btn){tip.style.display="none";return}
      var r=resolveAff(btn);tip.innerHTML=fmtTip(r);tip.style.display="block";posTip(tip,e);
    });
    appEl.addEventListener("mousemove",function(e){if(tip.style.display==="block")posTip(tip,e)});
    appEl.addEventListener("mouseleave",function(){tip.style.display="none"});
  }

  function posTip(tip,e){
    var x=e.clientX+12,y=e.clientY+12,r=tip.getBoundingClientRect();
    if(x+r.width>window.innerWidth-8)x=e.clientX-r.width-8;
    if(y+r.height>window.innerHeight-8)y=e.clientY-r.height-8;
    tip.style.left=x+"px";tip.style.top=y+"px";
  }

  function fmtTip(r){
    var s='<span class="tt-method">'+esc(r.method)+'</span> <span class="tt-url">'+esc(r.url)+'</span>\n';
    var ks=Object.keys(r.body);
    if(ks.length){
      s+=sp("tt-brace","{")+"\n";
      ks.forEach(function(k,i){
        var v=r.body[k],vh;
        if(typeof v==="string")vh='<span class="tt-str">"'+esc(v)+'"</span>';
        else if(typeof v==="boolean")vh='<span class="tt-val">'+v+'</span>';
        else if(v===null)vh='<span class="tt-val">null</span>';
        else vh='<span class="tt-val">'+esc(JSON.stringify(v))+'</span>';
        s+='  <span class="tt-key">"'+esc(k)+'"</span>: '+vh+(i<ks.length-1?",":"")+"\n";
      });
      s+=sp("tt-brace","}");
    } else { s+=sp("tt-brace","{}"); }
    return s;
  }

  // ═══════════════════════════════════════════════════════════════
  // CROSS-HIGHLIGHTING
  // ═══════════════════════════════════════════════════════════════

  function setupHL(jsonEl,appEl){
    var ae=[],an=[];
    jsonEl.addEventListener("mouseover",function(e){
      var ent=e.target.closest(".j-entry");if(!ent)return;
      var path=ent.getAttribute("data-path");if(!path)return;
      clearHL();ent.classList.add("j-hl");ae.push(ent);
      appEl.querySelectorAll(".r-node[data-path]").forEach(function(n){
        var np=n.getAttribute("data-path");
        if(np===path||np.indexOf(path+".")===0||path.indexOf(np+".")===0){n.classList.add("r-hl");an.push(n)}
      });
    });
    jsonEl.addEventListener("mouseleave",clearHL);
    function clearHL(){ae.forEach(function(e){e.classList.remove("j-hl")});an.forEach(function(e){e.classList.remove("r-hl")});ae=[];an=[]}
  }

  // ═══════════════════════════════════════════════════════════════
  // STATE — THE ENTIRE APPLICATION
  // ═══════════════════════════════════════════════════════════════

  function mkField(key,label,type,value,instruction,editable){
    var f={element:"field",key:key,type:type||"text",label:label,instruction:instruction||null,value:value,affordance:null};
    if(editable!==false&&type!=="computed") f.affordance={method:"POST",url:"/fields/"+key,body:{value:"{input}"}};
    if(type==="boolean"&&f.affordance) f.affordance.parameters={value:{options:[true,false]}};
    if(type==="select"&&f.affordance) f.affordance.parameters={value:{options:editable}};
    return f;
  }

  function mkStep(key,label,status,children){
    var s={element:"step",key:key,label:label,status:status,children:children||[]};
    if(status==="active"&&children){
      s.children.push({element:"action",label:"Complete Step",method:"POST",url:"/step/"+key+"/complete",body:{},variant:"primary"});
      s.children.push({element:"action",label:"Flag Issue",method:"POST",url:"/step/"+key+"/fail",body:{},variant:"danger"});
    }
    return s;
  }

  function mkWorkItem(key,label,status,priority,assigned,due,steps){
    return {
      element:"group", label:label, _type:"work_item", _key:key,
      children:[
        {element:"group",label:null,children:[
          {element:"badge",label:"Status",value:status,variant:status==="Overdue"?"error":status==="In Progress"?"info":"success"},
          {element:"badge",label:"Priority",value:priority,variant:priority==="High"?"warning":"info"},
          {element:"status_bar",items:[
            {label:"Assigned",value:assigned},
            {label:"Due",value:due}
          ]},
          {element:"progress",label:"Progress",value:0,max:0,_computed:true}
        ]},
        {element:"divider",label:"Checklist"},
        {element:"group",label:"Steps",children:steps},
        {element:"gated_action",label:"Approve & Close",method:"POST",url:"/item/"+key+"/approve",body:{},
          gate_open:false,gate_message:""}
      ]
    };
  }

  var STATE = {
    focus: null,
    auto_focus: true,
    data: {
      element: "group",
      label: "Calibration Review Console",
      children: [
        // ── Dashboard header ──
        { element:"group", label:null, children:[
          {element:"toggle",key:"auto_focus",label:"Auto-focus",value:true,
            affordance:{method:"POST",url:"/toggle/auto_focus",body:{value:"{input}"}}},
          {element:"alert",text:"1 work item is overdue. FG-089 Flow Gauge was due 2026-03-18.",variant:"warning"}
        ]},
        // ── Work Items ──
        mkWorkItem("pt207","PT-207 Pressure Transducer","In Progress","High","J. Martinez","2026-04-15",[
          mkStep("pt207_s1","Record Equipment Info","complete",[
            mkField("pt207_equip","Equipment ID","text","PT-207",null,false),
            mkField("pt207_serial","Serial Number","text","SN-80412-X",null,false),
            mkField("pt207_loc","Location","text","Building 7, Lab 3")
          ]),
          mkStep("pt207_s2","Perform Measurements","active",[
            mkField("pt207_r1","Reading 1","text",null,"Record primary measurement"),
            mkField("pt207_r2","Reading 2","text",null,"Record confirmatory measurement"),
            mkField("pt207_tol","In Tolerance","boolean",null,"Are readings within spec?")
          ]),
          mkStep("pt207_s3","Review Results","locked",[
            mkField("pt207_drift","Drift","computed",null),
            mkField("pt207_interval","Recommended Interval","select",null,null,["3 months","6 months","Annual","Biennial"]),
            {element:"note",text:"Compare readings against reference standard PT-REF-003. Document any anomalies."}
          ]),
          mkStep("pt207_s4","Final Disposition","locked",[
            mkField("pt207_disp","Disposition","select",null,null,["Approve","Reject","Defer","Escalate"]),
            mkField("pt207_notes","Reviewer Notes","text",null,"Additional observations")
          ])
        ]),
        mkWorkItem("tc112","TC-112 Thermocouple","In Progress","Medium","R. Chen","2026-04-22",[
          mkStep("tc112_s1","Record Equipment Info","complete",[
            mkField("tc112_equip","Equipment ID","text","TC-112",null,false),
            mkField("tc112_serial","Serial Number","text","SN-91203-T",null,false),
            mkField("tc112_loc","Location","text","Building 3, Clean Room 2")
          ]),
          mkStep("tc112_s2","Perform Measurements","complete",[
            mkField("tc112_r1","Reading 1","text","22.4°C"),
            mkField("tc112_r2","Reading 2","text","22.3°C"),
            mkField("tc112_tol","In Tolerance","boolean",true)
          ]),
          mkStep("tc112_s3","Review Results","active",[
            mkField("tc112_drift","Drift","computed","+0.1°C"),
            mkField("tc112_interval","Recommended Interval","select",null,null,["3 months","6 months","Annual","Biennial"]),
            {element:"note",text:"Thermocouple readings are excellent. Minimal drift."}
          ]),
          mkStep("tc112_s4","Final Disposition","locked",[
            mkField("tc112_disp","Disposition","select",null,null,["Approve","Reject","Defer","Escalate"]),
            mkField("tc112_notes","Reviewer Notes","text",null)
          ])
        ]),
        mkWorkItem("fg089","FG-089 Flow Gauge","Overdue","High","Unassigned","2026-03-18",[
          mkStep("fg089_s1","Record Equipment Info","active",[
            mkField("fg089_equip","Equipment ID","text","FG-089",null,false),
            mkField("fg089_serial","Serial Number","text","SN-44017-F",null,false),
            mkField("fg089_loc","Location","text",null,"Enter installation location")
          ]),
          mkStep("fg089_s2","Perform Measurements","locked",[
            mkField("fg089_r1","Reading 1","text",null),
            mkField("fg089_r2","Reading 2","text",null),
            mkField("fg089_tol","In Tolerance","boolean",null)
          ]),
          mkStep("fg089_s3","Review Results","locked",[
            mkField("fg089_drift","Drift","computed",null),
            mkField("fg089_interval","Recommended Interval","select",null,null,["3 months","6 months","Annual","Biennial"])
          ]),
          mkStep("fg089_s4","Final Disposition","locked",[
            mkField("fg089_disp","Disposition","select",null,null,["Approve","Reject","Defer","Escalate"])
          ])
        ])
      ]
    }
  };

  // ═══════════════════════════════════════════════════════════════
  // INIT
  // ═══════════════════════════════════════════════════════════════

  function init(){
    var jsonEl=document.getElementById("wc-json");
    var appEl=document.getElementById("wc-app");
    var autoInd=document.getElementById("wc-auto-indicator");
    if(!jsonEl||!appEl) return;

    var state=deepCopy(STATE);

    function rerender(){
      var agentView=projectAgent(state);
      jsonEl.innerHTML=jsonToHtml(agentView,[],0);
      appEl.innerHTML=renderHuman(state);
      setupHL(jsonEl,appEl);
      if(autoInd) autoInd.innerHTML=state.auto_focus?'<span class="el-auto-badge">AUTO-FOCUS ON</span>':'';
    }

    setupHandler(appEl,function(){return state},rerender);
    rerender();
  }

  init();
})();
