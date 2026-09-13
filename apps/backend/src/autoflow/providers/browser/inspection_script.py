"""Adapted from frozen WebRPA element_picker/script.py; no runtime reference dependency."""
PICKER_SCRIPT = r"""(() => {
  if (window.__autoflowPicker) return;
  const state = { active: false, selected: null, cancelled: false, layer: null, cleanup: null };
  window.__autoflowPicker = state;
  const layer = () => {
    if (state.layer?.isConnected) return state.layer;
    const el = document.createElement('div');
    el.setAttribute('data-autoflow-overlay', 'picker');
    el.style.cssText = 'position:fixed;inset:0;z-index:2147483647;pointer-events:none';
    const shadow = el.attachShadow({mode:'open'});
    shadow.innerHTML = '<div id="box" style="position:fixed;border:2px solid #b45309;background:#fbbf2422;pointer-events:none"></div><div style="position:fixed;top:8px;left:8px;background:#292524;color:white;padding:8px 12px;font:13px sans-serif;pointer-events:none">AutoFlow · 点击拾取元素 · Esc 取消</div>';
    document.documentElement.appendChild(el); state.layer = el; return el;
  };
  state.setActive = active => {
    state.active = active; state.selected = null; state.cancelled = false;
    if (!active) { state.layer?.remove(); state.layer = null; }
    else layer();
  };
  const target = ev => ev.composedPath().find(el => el instanceof Element);
  const suppress = ev => { ev.preventDefault(); ev.stopImmediatePropagation(); };
  window.addEventListener('pointermove', ev => {
    if (!state.active) return;
    const el = target(ev); if (!el) return;
    const box = layer().shadowRoot.getElementById('box'), r = el.getBoundingClientRect();
    Object.assign(box.style, {left:r.x+'px',top:r.y+'px',width:r.width+'px',height:r.height+'px'});
  }, true);
  for (const type of ['pointerdown','pointerup','mousedown','mouseup','click','dblclick','auxclick','contextmenu','submit','touchstart','touchend']) {
    window.addEventListener(type, ev => {
      if (!state.active) return;
      suppress(ev);
      if (type === 'click' && ev.button === 0 && !state.selected) {
        state.selected = target(ev);
        state.layer?.remove(); state.layer = null;
        // Remain intercepting through the complete click sequence; Python disables all frames.
      }
    }, {capture:true, passive:false});
  }
  window.addEventListener('keydown', ev => {
    if (!state.active) return;
    suppress(ev);
    if (ev.key === 'Escape') { state.cancelled = true; state.layer?.remove(); state.layer = null; }
  }, true);
})()"""

CANDIDATES_SCRIPT = r"""el => {
  const esc = CSS.escape;
  const quote = s => '"' + s.replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\n/g,'\\a ') + '"';
  const safe = s => s.length < 8000 && !/\$?\{[^{}]+\}/u.test(s);
  function local(e) {
    const result = [], tag = e.tagName.toLowerCase();
    if (e.id) result.push({selector:'#'+esc(e.id), positional:false});
    for (const attr of ['data-testid','data-test','data-qa','name','aria-label','placeholder','title','type']) {
      const value = e.getAttribute(attr);
      if (value) result.push({selector:tag+'['+attr+'='+quote(value)+']', positional:false});
    }
    const classes = [...e.classList].slice(0,4);
    for (const cls of classes) result.push({selector:tag+'.'+esc(cls), positional:false});
    if (classes.length > 1) result.push({selector:tag+classes.map(c=>'.'+esc(c)).join(''), positional:false});
    let path = '', cur = e;
    while (cur instanceof Element) {
      const t = cur.tagName.toLowerCase();
      const index = cur.parentNode?.children ? [...cur.parentNode.children].filter(c=>c.tagName===cur.tagName).indexOf(cur)+1 : 1;
      path = t+':nth-of-type('+index+')'+(path ? ' > '+path : '');
      if (cur !== e && cur.id) result.push({selector:'#'+esc(cur.id)+' > '+path.split(' > ').slice(1).join(' > '), positional:true});
      cur = cur.parentElement;
    }
    result.push({selector:path, positional:true});
    return result.filter(c=>safe(c.selector));
  }
  function candidates(e) {
    const root=e.getRootNode(), own=local(e);
    if (!(root instanceof ShadowRoot)) return own;
    const hosts=candidates(root.host);
    // Host paths constrain repeated identifiers in separate open shadow roots.
    return hosts.slice(0,8).flatMap(h=>own.map(c=>({selector:h.selector+' >> css='+c.selector,positional:h.positional||c.positional}))).slice(0,80);
  }
  return candidates(el);
}"""

HIGHLIGHT_SCRIPT = r"""elements => {
  document.querySelector('[data-autoflow-overlay="test"]')?.remove();
  const layer=document.createElement('div'); layer.setAttribute('data-autoflow-overlay','test');
  layer.style.cssText='position:fixed;inset:0;z-index:2147483647;pointer-events:none';
  const root=layer.attachShadow({mode:'open'});
  elements.forEach((el,i)=>{
    const r=el.getBoundingClientRect(), style=getComputedStyle(el);
    if (!r.width || !r.height || style.visibility==='hidden') return;
    const box=document.createElement('div');
    box.style.cssText='position:fixed;border:2px solid '+(i===0?'#b45309':'#2563eb')+';background:#fbbf241a;pointer-events:none';
    Object.assign(box.style,{left:r.x+'px',top:r.y+'px',width:r.width+'px',height:r.height+'px'});
    box.textContent=String(i+1); root.appendChild(box);
  });
  document.documentElement.appendChild(layer); setTimeout(()=>layer.remove(),3000);
}"""
