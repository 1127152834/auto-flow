import assert from 'node:assert/strict'
import { spawn, execFileSync } from 'node:child_process'
import { constants } from 'node:fs'
import { cp, mkdir, mkdtemp, readFile, readdir, realpath, rm, writeFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import { homedir, tmpdir } from 'node:os'
import { basename, join, resolve } from 'node:path'
import { randomUUID } from 'node:crypto'
import { inspectPublicKernel } from './smoke-profile-test-browser.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const arg = name => { const i = process.argv.indexOf(name); return i < 0 ? undefined : process.argv[i + 1] }
const supplied = arg('--kernel-directory')
const installed = join(homedir(), 'Library/Application Support/@autoflow/desktop/data/kernels')
const candidates = supplied ? [supplied] : (await readdir(installed)).filter(n => /^chromium-[\d.]+$/.test(n)).sort().reverse().map(n => join(installed,n))
const kernel = await inspectPublicKernel(candidates[0])
const workspace = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-m5-debug-')))
const copied = join(workspace, 'data/kernels', basename(kernel.directory))
await cp(kernel.directory, copied, { recursive: true, verbatimSymlinks: true, mode: constants.COPYFILE_FICLONE })
const observations = []
const server = createServer(async (req,res) => {
  res.setHeader('Content-Type','text/html;charset=utf-8')
  const port = server.address().port
  if (req.url === '/') { res.end(`<iframe id="outer" src="http://localhost:${port}/outer"></iframe>`); return }
  if (req.url === '/outer') { res.end(`<iframe id="inner" src="http://127.0.0.1:${port}/inner"></iframe>`); return }
  res.end(`<input id="entry"><button id="apply" onclick="document.querySelector('#result').textContent=document.querySelector('#entry').value;document.querySelector('#count').textContent=++window.count">apply</button><p id="result"></p><p id="count">0</p><p id="hidden" hidden>hidden</p><div id="shadow"></div><script>window.count=0;document.querySelector('#shadow').attachShadow({mode:'open'}).innerHTML='<span id="inside">shadow</span>'</script>`)
})
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
const url = `http://127.0.0.1:${server.address().port}`
const token = randomUUID(), hostToken = randomUUID()
let child, base, profile
const checks=[]
const executable = arg('--executable')
const mode = executable ? 'frozen' : 'source'
const qa=join(root,'docs/migration/automation-studio-m5-qa')
await mkdir(qa,{recursive:true})
const wait = ms => new Promise(resolve=>setTimeout(resolve,ms))
async function until(fn,label,ms=20000) { const end=Date.now()+ms;while(Date.now()<end){const v=await fn();if(v)return v;await wait(80)}throw new Error(`Timeout: ${label}`) }
async function startBackend() {
  const command=executable?[resolve(executable)]:[join(root,'apps/backend/.venv/bin/python'),'-m','autoflow']
  child=spawn(command[0],[...command.slice(1),'--data-dir',workspace,'--instance-id',randomUUID(),'--port','0'],{cwd:root,env:{...process.env,AUTOFLOW_INSTANCE_TOKEN:token,AUTOFLOW_HOST_TOKEN:hostToken,PYTHONPATH:join(root,'apps/backend/src')},stdio:['ignore','pipe','pipe']})
  let output='', errors='';child.stderr.on('data',b=>{errors+=b;process.stderr.write(b)})
  child.stdout.on('data',b=>{output+=b})
  await until(()=>{if(child.exitCode!==null)throw new Error(`Backend ${child.exitCode}: ${errors}`);const match=output.match(/AUTOFLOW_READY (.+)/);if(match){base=`http://127.0.0.1:${JSON.parse(match[1]).port}`;return true}},'backend ready',30000)
}
async function response(path,options={}) { return fetch(base+'/api/v1/'+path,{...options,headers:{'x-autoflow-token':token,'content-type':'application/json',...options.headers},signal:AbortSignal.timeout(15000)}) }
async function api(path,options={}) {let r;try{r=await response(path,options)}catch(error){throw new Error(`API ${options.method||'GET'} ${path}: ${error}`,{cause:error})};const text=await r.text();assert.ok(r.ok,`${path}: ${r.status} ${text}`);return text?JSON.parse(text):null}
function passed(label) {checks.push(label);console.log('PASS '+label)}
async function noOwnedBrowsers() {
  if(process.platform==='win32')return;
  await until(()=>!execFileSync('ps',['-ax','-o','command='],{encoding:'utf8'}).split('\n').some(l=>l.includes(copied)&&!l.includes('ps -ax')),'owned browser cleanup',10000)
}

let catalog
const literal=value=>({kind:'literal',value})
const variable=(name,...path)=>({kind:'variable',name,path})
const rule=(left,operator,right)=>({kind:'value',left,operator,right:literal(right)})
const node=(id,type,config={})=>({id,type,label:id,config:{...structuredClone(catalog.find(n=>n.type===type).defaultConfig),...config}})
function flow(nodes,edges,variables=[]) {return {document:{id:randomUUID(),name:'M4 real control',schemaVersion:2,nodes,edges:edges.map(([source,sourceHandle,target],i)=>({id:'e'+i,source,sourceHandle,target,targetHandle:'in'})),variables},layout:{nodes:Object.fromEntries(nodes.map((n,i)=>[n.id,{x:(i%5)*280,y:Math.floor(i/5)*160}])),viewport:{x:0,y:0,zoom:0.6}}}}
async function execute(content) {
 const runId=randomUUID();const request={runId,profileId:profile.id,...content}
 await api('workflows/runs',{method:'POST',body:JSON.stringify(request)})
 assert.equal((await api('workflows/runs',{method:'POST',body:JSON.stringify(request)})).runId,runId)
 const result=await until(async()=>{const r=await api('workflows/runs/'+runId);return ['succeeded','failed','cancelled'].includes(r.state)?r:null},'run completes',120000)
 await noOwnedBrowsers()
 return result
}
async function artifacts(run) {
 let after=0,items=[]
 do {const page=await api(`workflows/runs/${run.runId}/artifacts?after=${after}&limit=17`);items.push(...page.items);after=page.nextCursor}while(after!==null)
 return items
}
async function value(run,a){const r=await response(`workflows/runs/${run.runId}/artifacts/${a.id}`);assert.ok(r.ok);return r.json()}
async function get(run) {return api('workflows/runs/'+run.runId)}
async function paused(run,nodeId) {return until(async()=>{const r=await get(run);if(['failed','cancelled','interrupted'].includes(r.state))throw new Error(JSON.stringify(r));return r.state==='paused'&&(!nodeId||r.debug.pendingNodeId===nodeId)?r:null},'pause '+nodeId,30000)}
async function control(run,action,extra={}) {
 const current=await get(run),command={commandId:randomUUID(),expectedRevision:current.debug.controlRevision,pauseId:current.debug.pauseId,action,...extra}
 const first=await api(`workflows/runs/${run.runId}/debug/commands`,{method:'POST',body:JSON.stringify(command)})
 const result=first.state==='accepted'?await until(async()=>{const r=await api(`workflows/runs/${run.runId}/debug/commands/${command.commandId}`);return r.state!=='accepted'?r:null},'command '+action,20000):first
 assert.equal(result.state,'applied',JSON.stringify(result));return {command,result}
}
async function startDebug(body,debug={start:'entry'}) {return api('workflows/runs',{method:'POST',body:JSON.stringify({runId:randomUUID(),...body,profileId:profile.id,mode:'debug',debug})})}
async function finish(run,state='succeeded') {const r=await until(async()=>{const r=await get(run);return ['succeeded','failed','cancelled'].includes(r.state)?r:null},'terminal',120000);assert.equal(r.state,state,JSON.stringify(r.error));await noOwnedBrowsers(); if (r.mode === 'debug' && ['failed','cancelled'].includes(r.state)) { const ds=await api(`workflows/runs/${r.runId}/debug/variables`); const cp=await value(r,{id:ds.checkpointId}); assert.equal(cp.reason,'ended') } return r}
try {
 await startBackend();catalog=(await api('workflows/node-catalog')).items
 profile=await api('profiles',{method:'POST',body:JSON.stringify({name:'M5 real debug',browserVersion:kernel.version,headless:true,startUrl:url+'/must-not-visit'})})
 const frames=['#outer','#inner']
 const body=flow([node('open','open_page',{url}),node('loop','loop',{source:literal(2),endNodeId:'end'}),node('input','input_text',{selector:'#entry',framePath:frames,text:'{text}'}),node('click','click_element',{selector:'#apply',framePath:frames}),node('read','get_element_info',{selector:'#result',framePath:frames,variableName:'result'}),node('end','loop_end',{ownerNodeId:'loop'})],[['open','out','loop'],['loop','body','input'],['input','out','click'],['click','out','read'],['read','out','end']],[{name:'text',type:'string',value:'initial'}])
 let run=await startDebug(body,{start:'entry',breakpoints:['input']});run=await paused(run,'open');assert.equal(run.executionCount,0)
 await wait(12000);assert.equal((await get(run)).state,'paused')
 const step=await control(run,'step');await paused(run,'loop');const duplicate=await api(`workflows/runs/${run.runId}/debug/commands`,{method:'POST',body:JSON.stringify(step.command)});assert.equal(duplicate.state,'applied');await wait(100);assert.equal((await get(run)).executionCount,1)
 const conflict=await response(`workflows/runs/${run.runId}/debug/commands`,{method:'POST',body:JSON.stringify({...step.command,action:'resume'})});assert.equal(conflict.status,409)
 const stale=await api(`workflows/runs/${run.runId}/debug/commands`,{method:'POST',body:JSON.stringify({...step.command,commandId:randomUUID()})});const denied=await until(async()=>{const r=await api(`workflows/runs/${run.runId}/debug/commands/${stale.commandId}`);return r.state!=='accepted'?r:null},'stale pause rejection');assert.equal(denied.state,'rejected')
 await control(run,'resume');run=await paused(run,'input');assert.equal(run.debug.loopPath[0].iteration,1)
 await control(run,'variables',{values:{text:'modified'}});await control(run,'step');run=await paused(run,'click');assert.equal(run.executionCount,3)
 await control(run,'resume');await until(async()=>{const r=await get(run);return r.state==='paused'&&r.debug.pendingNodeId==='input'&&r.debug.loopPath[0].iteration===2},'second breakpoint')
 await control(run,'variables',{values:{text:'second'}});await control(run,'resume');run=await finish(run)
 const results=await artifacts(run);assert.equal(results.length,2);assert.equal(await value(run,results[0]),'modified');assert.equal(await value(run,results[1]),'second')
 const vars=await api(`workflows/runs/${run.runId}/debug/variables`);assert.ok(vars.checkpointId);assert.ok(vars.diagnosticArtifacts.length>0);assert.equal(run.artifactCount,2)
 passed('real cross-origin iframe loop: entry pause, 12s heartbeat, duplicate single-step once, per-iteration breakpoint and manual variable edits produce modified/second')
 const bad=flow([node('open','open_page',{url:url+'/inner'}),node('bad','click_element',{selector:'#absent',timeoutSeconds:.1}),node('never','input_text',{selector:'#entry',text:'must-not-run'})],[['open','out','bad'],['bad','out','never']])
 let fail=await startDebug(bad,{start:'until',targetNodeId:'bad'});await paused(fail,'bad');await control(fail,'resume');await until(async()=>{const r=await get(fail);return r.state==='failed_paused'},'failure retained');const pages=await control(fail,'pages');assert.ok(pages.result.data.pages.length)
 const before=await get(fail);const rejected=await api(`workflows/runs/${fail.runId}/debug/commands`,{method:'POST',body:JSON.stringify({commandId:randomUUID(),expectedRevision:before.debug.controlRevision,pauseId:before.debug.pauseId,action:'resume'})});const rejectedResult=await until(async()=>{const r=await api(`workflows/runs/${fail.runId}/debug/commands/${rejected.commandId}`);return r.state!=='accepted'?r:null},'reject failure resume');assert.equal(rejectedResult.state,'rejected')
 await api(`workflows/runs/${fail.runId}/stop`,{method:'POST'});fail=await finish(fail,'failed');assert.equal(fail.error.nodeId,'bad');assert.equal(fail.executionCount,2)
 passed('failed action retains real browser, forbids resume, never schedules successor, ending debug preserves failed outcome and closes processes')
 const direct=flow([node('skip','open_page',{url:''}),node('input','input_text',{selector:'#entry',text:'{provided}'}),node('read','get_element_info',{selector:'#entry',attribute:'value'})],[['skip','out','input'],['input','out','read']])
 let local=await startDebug(direct,{start:'node',targetNodeId:'input',values:{provided:'manual-page'}});await paused(local,'input');const pageList=await control(local,'pages');await control(local,'page',{pageId:pageList.result.data.pages[0].pageId,url:url+'/inner',focus:true});await control(local,'resume');local=await finish(local);assert.equal(await value(local,local.artifacts[0]),'manual-page');assert.equal(local.executionCount,2)
 passed('top-level direct entry skips invalid upstream configuration; explicit initial variable and manual navigation support independent real execution')
 const huge='x'.repeat(70000);let large=await startDebug(flow([node('set','set_variable',{variableName:'data',value:literal(huge)})],[]));await paused(large,'set');await control(large,'resume');large=await finish(large);const largeVars=await api(`workflows/runs/${large.runId}/debug/variables`);const checkpoint=await value(large,{id:largeVars.checkpointId});assert.equal(checkpoint.variables.find(v=>v.name==='data').value.length,70000)
 const exported=await response(`workflows/runs/${run.runId}/export?kind=results`);assert.ok(exported.ok);assert.equal(Buffer.from(await exported.arrayBuffer()).readUInt32LE(),0x04034b50)
 const logs=await api(`workflows/runs/${run.runId}/logs?nodeId=input&limit=2`);assert.equal(logs.items.length,2);assert.ok(logs.items.every(e=>e.nodeId==='input'))
 const diagnosticExport=await response(`workflows/runs/${large.runId}/export?kind=diagnostics`);assert.ok((await diagnosticExport.json()).some(x=>x.diagnostic.kind==='checkpoint'))
 await stop(child);await startBackend();assert.equal((await api(`workflows/runs/${run.runId}/debug/variables`)).checkpointId,vars.checkpointId)
 passed('70KiB variable stored outside protocol; result ZIP/diagnostic JSON, server-side filtered log pagination and restart persistence')

 const many=flow([node('loop','loop',{source:literal(1000),endNodeId:'end'}),node('append','set_variable',{variableName:'items',operation:'append',value:variable('index')}),node('end','loop_end',{ownerNodeId:'loop'}),node('open','open_page',{url:url+'/inner'}),node('input','input_text',{selector:'#entry',text:'{items}'}),node('read','get_element_info',{selector:'#entry',attribute:'value'})],[['loop','body','append'],['append','out','end'],['loop','done','open'],['open','out','input'],['input','out','read']],[{name:'items',type:'array',value:[]}])
 let long=await startDebug(many);await paused(long,'loop');await control(long,'resume');long=await finish(long);const actual=JSON.parse(await value(long,long.artifacts[0]));assert.equal(actual.length,1000);assert.equal(actual[999],1000);assert.equal(long.artifactCount,1);assert.equal(long.nodeExecutionCounts.append,1000)
 const deltaPage=await api(`workflows/runs/${long.runId}/debug/variables?after=50&limit=50`);assert.equal(deltaPage.diagnosticArtifacts.length,50);assert.ok(deltaPage.nextCursor>50)
 passed('1000 real debug loop iterations use incremental append diagnostics, preserve browser result, count 1000 executions and paginate diagnostics')
 let nested=await startDebug(body,{start:'until',targetNodeId:'input'});nested=await paused(nested,'input');assert.equal(nested.debug.loopPath[0].iteration,1);assert.equal(nested.executionCount,2);await api(`workflows/runs/${nested.runId}/stop`,{method:'POST'});await finish(nested,'cancelled')
 const spinning=flow([node('loop','loop',{mode:'while',rules:[rule(literal(true),'is_true',true)],endNodeId:'end',maxIterations:100000}),node('add','set_variable',{variableName:'n',operation:'add',value:literal(1)}),node('end','loop_end',{ownerNodeId:'loop'})],[['loop','body','add'],['add','out','end']],[{name:'n',type:'number',value:0}])
 let running=await startDebug(spinning);await paused(running,'loop');await control(running,'resume');await until(async()=> (await get(running)).executionCount>20,'pure loop running');await control(running,'pause');await paused(running);await api(`workflows/runs/${running.runId}/stop`,{method:'POST'});await finish(running,'cancelled')
 passed('run-until nested node keeps real first-iteration context; pure-variable debug loop accepts pause and stop with resource cleanup')

 const deep=flow([node('open','open_page',{url:url+'/inner'}),node('outer','loop',{source:literal(2),indexVariable:'outerIndex',endNodeId:'outerEnd'}),node('inner','loop',{source:literal(2),indexVariable:'innerIndex',endNodeId:'innerEnd'}),node('condition','condition',{endNodeId:'join',rules:[rule(variable('innerIndex'),'eq',1)]}),node('click','click_element',{selector:'#apply'}),node('join','condition_end',{ownerNodeId:'condition'}),node('innerEnd','loop_end',{ownerNodeId:'inner'}),node('outerEnd','loop_end',{ownerNodeId:'outer'}),node('count','get_element_info',{selector:'#count'})],[['open','out','outer'],['outer','body','inner'],['inner','body','condition'],['condition','true','click'],['condition','false','join'],['click','out','join'],['join','out','innerEnd'],['inner','done','outerEnd'],['outer','done','count']])
 let stepping=await startDebug(deep);stepping=await paused(stepping,'open');let stepCount=0,seenNested=false
 while(stepping.state==='paused') {
   const priorPause=stepping.debug.pauseId
   if(stepping.debug.pendingNodeId==='condition') {assert.equal(stepping.debug.loopPath.length,2);seenNested=true}
   await control(stepping,'step');stepCount++
   stepping=await until(async()=>{const r=await get(stepping);return r.state==='paused'&&r.debug.pauseId!==priorPause||['succeeded','failed','cancelled'].includes(r.state)?r:null},'one nested dispatch')
   assert.equal(stepping.executionCount,stepCount)
 }
 stepping=await finish(stepping);assert.ok(seenNested);assert.equal(stepping.nodeExecutionCounts.condition,4);assert.equal(stepping.nodeExecutionCounts.inner,6);assert.equal(stepping.nodeExecutionCounts.click,2);assert.equal(stepping.nodeExecutionCounts.join,4);assert.equal(await value(stepping,stepping.artifacts[0]),'2')
 passed('every dispatch single-stepped through two nested loops and both conditional paths; actual browser click count is two, paired ends and loop heads each count independently')

 let interrupted=await startDebug(body);await paused(interrupted,'open');child.kill('SIGKILL');await until(()=>child.exitCode!==null||child.signalCode!==null,'sidecar killed');await noOwnedBrowsers();await startBackend();interrupted=await get(interrupted);assert.equal(interrupted.state,'interrupted');assert.equal(interrupted.executionCount,0);assert.ok((await api(`workflows/runs/${interrupted.runId}/debug/variables`)).checkpointId)
 const recovery=await startDebug(body);await paused(recovery,'open');await api(`workflows/runs/${recovery.runId}/stop`,{method:'POST'});await finish(recovery,'cancelled')
 passed('real sidecar SIGKILL during pause cleans owned browsers, recovers interrupted history without replay and releases resources for a fresh debug session')
} finally {
 await stop(child).catch(()=>{});server.closeAllConnections();await new Promise(r=>server.close(r));await noOwnedBrowsers().catch(()=>{})
 await writeFile(join(qa,`${mode}-debug.json`),JSON.stringify({platform:process.platform,arch:process.arch,mode,kernelVersion:kernel.version,checks,complete:checks.length===8},null,2))
 await rm(workspace,{recursive:true,force:true})
}
