"""Passive capture; no page storage, injected credentials, or event interception."""
RECORDING_SCRIPT = r"""(() => {
 if(window.__autoflowRecording) return;
 const state={active:false, segment:0, epoch:crypto.randomUUID(), seq:0, elements:new Map(), pending:Promise.resolve(), value:null, click:null, timer:null, composing:false};
 window.__autoflowRecording=state;
 const element=e=>e.composedPath().find(n=>n instanceof Element);
 const own=e=>e?.closest?.('[data-autoflow-overlay]');
 const send=(action,el,config={})=>{
   const targetId=crypto.randomUUID();state.elements.set(targetId,el);
   const data={action,config,targetId,epoch:state.epoch,sourceSeq:++state.seq,segment:state.segment};
   const request=window.__autoflowRecord(data).then(result=>{if(!result.received)state.failed=true;}).catch(()=>{state.failed=true;}).finally(()=>state.elements.delete(targetId));
   state.pending=Promise.all([state.pending,request]);
 };
 const flushValue=()=>{if(state.value){const p=state.value;state.value=null;send(p.action,p.el,p.config);}};
 const flushClick=()=>{clearTimeout(state.timer);if(state.click){const p=state.click;state.click=null;send('click',p.el,{});}};
 state.flush=async()=>{flushValue();flushClick();await state.pending;return {epoch:state.epoch,sourceSeq:state.seq,failed:!!state.failed};};
 state.set=async(active,segment)=>{if(!active){state.active=false;await state.flush();}else {state.active=true;state.segment=segment;}return {epoch:state.epoch,sourceSeq:state.seq};};
 const input=(el)=>{
   if(!el)return;
   const tag=el.tagName,t=(el.type||'').toLowerCase();
   if(tag==='INPUT'&&['checkbox','radio','file','hidden'].includes(t))return;
   if(!['INPUT','TEXTAREA'].includes(tag)&&!el.isContentEditable)return;
   flushClick();
   if(state.value&&state.value.el!==el)flushValue();
   state.value={action:'input',el,config:{text:t==='password'?'':('value'in el?el.value:el.textContent||''),requiresValue:t==='password'}};
 };
 for(const type of ['input','change','blur','compositionstart','compositionend'])window.addEventListener(type,e=>{
   if(!state.active)return; const el=element(e);if(!el||own(el))return;
   if(type==='compositionstart'){state.composing=true;return;}
   if(type==='compositionend'){state.composing=false;input(el);return;}
   if(type==='change'&&el.tagName==='SELECT'){flushValue();flushClick();send('select',el,{values:[...el.selectedOptions].map(o=>o.value)});return;}
   if(type==='change'&&['checkbox','radio'].includes(el.type)){flushValue();flushClick();if(el.type!=='radio'||el.checked)send('check',el,{checked:el.checked});return;}
   if(type==='change'&&el.type==='file'){flushValue();send('unsupported',el,{reason:'文件上传尚未支持，请补充步骤'});return;}
   if(!state.composing)input(el);
   if(type==='blur'||type==='change')flushValue();
 },true);
 for(const type of ['click','dblclick','contextmenu'])window.addEventListener(type,e=>{
   if(!state.active||!e.isTrusted)return;const el=element(e);if(!el||own(el))return;
   if(el.tagName==='SELECT'||['checkbox','radio','file'].includes(el.type)||el.closest('label')?.control)return;
   flushValue();
   if(type==='dblclick'){clearTimeout(state.timer);state.click=null;send('dblclick',el,{});return;}
   if(type==='contextmenu'){flushClick();send(type,el,{});return;}
   if(state.click?.el!==el)flushClick();
   state.click={el};clearTimeout(state.timer);state.timer=setTimeout(flushClick,450);
 },true);
 window.addEventListener('keydown',e=>{
   if(!state.active||!e.isTrusted||e.isComposing)return;
   if(!['Enter','Tab','Escape','ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.key))return;
   flushValue();flushClick();
   const el=element(e);if(!el||own(el))return;
   send(e.ctrlKey||e.metaKey||e.altKey?'unsupported':'keypress',el,{key:e.key});
 },true);
 let scrollTimer,scrollValue;
 const flushScroll=()=>{clearTimeout(scrollTimer);if(scrollValue){const v=scrollValue;scrollValue=null;send('scroll',v.el,v.config);}};
 window.addEventListener('scroll',e=>{
   if(!state.active)return;
   const raw=element(e),el=raw||document.documentElement;if(own(el))return;
   const page=e.target===document||el===document.documentElement||el===document.body;
   const target=page?document.scrollingElement:el;
   if(scrollValue?.el!==el)flushScroll();
   scrollValue={el,config:{target:page?'page':'element',x:Math.max(0,target.scrollLeft),y:Math.max(0,target.scrollTop)}};
   clearTimeout(scrollTimer);scrollTimer=setTimeout(flushScroll,200);
 },true);
 const baseFlush=state.flush;state.flush=async()=>{flushScroll();return await baseFlush();};
 window.addEventListener('pointerdown',()=>{if(state.active){flushScroll();flushValue();}},true);
 window.addEventListener('dragstart',e=>{if(state.active){flushValue();flushClick();send('unsupported',element(e),{reason:'拖拽尚未支持，请补充步骤'});}},true);
 window.addEventListener('pagehide',()=>{if(state.active){flushScroll();flushValue();}},true);
})()"""
