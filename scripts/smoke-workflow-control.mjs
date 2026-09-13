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
const workspace = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-m4-control-')))
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
const qa=arg('--qa-directory') ? resolve(arg('--qa-directory')) : join(root,'docs/migration/automation-studio-m4-qa')
await mkdir(qa,{recursive:true})
const wait = ms => new Promise(resolve=>setTimeout(resolve,ms))
async function until(fn,label,ms=20000) { const end=Date.now()+ms;while(Date.now()<end){const v=await fn();if(v)return v;await wait(80)}throw new Error(`Timeout: ${label}`) }
async function startBackend() {
  const command=executable?[resolve(executable)]:[join(root,'apps/backend/.venv/bin/python'),'-m','autoflow']
  child=spawn(command[0],[...command.slice(1),'--data-dir',workspace,'--instance-id',randomUUID(),'--port','0'],{cwd:root,env:{...process.env,AUTOFLOW_INSTANCE_TOKEN:token,AUTOFLOW_HOST_TOKEN:hostToken,PYTHONPATH:join(root,'apps/backend/src')},stdio:['ignore','pipe','pipe']})
  let output='', errors='';child.stderr.on('data',b=>{errors+=b})
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
try {
 await startBackend();catalog=(await api('workflows/node-catalog')).items
 profile=await api('profiles',{method:'POST',body:JSON.stringify({name:'M4 real execution',browserVersion:kernel.version,headless:true,startUrl:url+'/must-not-visit'})})
 const frames=['#outer','#inner']
 const content=flow([
 node('open','open_page',{url}), node('ready','wait_element',{selector:'#entry',framePath:frames}),
 node('loop','loop',{mode:'foreach',source:literal([{enabled:true,text:'alpha'},{enabled:false,text:'ignored'},{enabled:true,text:'gamma'}]),endNodeId:'end'}),
 node('branch','condition',{endNodeId:'join',rules:[rule(variable('item','enabled'),'is_true',true),{kind:'page',operator:'visible',selector:'#entry',framePath:frames}]}),
 node('skip','continue_loop'),node('input','input_text',{selector:'#entry',framePath:frames,text:'{index}'}),node('click','click_element',{selector:'#apply',framePath:frames}),
 node('extract','get_element_info',{selector:'#result',framePath:frames,variableName:'value'}),node('append','set_variable',{variableName:'results',operation:'append',value:variable('value')}),
 node('image','screenshot',{screenshotType:'element',selector:'#result',framePath:frames}),node('join','condition_end',{ownerNodeId:'branch'}),node('end','loop_end',{ownerNodeId:'loop'}),
 node('output','input_text',{selector:'#entry',framePath:frames,text:'{results}'}),node('verify','get_element_info',{selector:'#entry',framePath:frames,attribute:'value',variableName:'final'})
 ],[['open','out','ready'],['ready','out','loop'],['loop','body','branch'],['branch','true','input'],['branch','false','skip'],['input','out','click'],['click','out','extract'],['extract','out','append'],['append','out','image'],['image','out','join'],['join','out','end'],['loop','done','output'],['output','out','verify']],[{name:'results',type:'array',value:[]}])
 const saved=await api('workflows',{method:'POST',body:JSON.stringify(content)})
 assert.equal(saved.issues.length,0)
 await stop(child);await startBackend()
 const reopened=await api('workflows/'+content.document.id);assert.deepEqual(reopened.document,content.document)
 let result=await execute({document:reopened.document,layout:reopened.layout});assert.equal(result.state,'succeeded',JSON.stringify(result.error))
 let items=await artifacts(result);assert.equal(items.length,5);assert.deepEqual(JSON.parse(await value(result,items.at(-1))),['1','3'])
 assert.deepEqual(items.filter(a=>a.nodeId==='extract').map(a=>a.loopPath[0].iteration),[1,3]);assert.equal(new Set(items.map(a=>a.executionId)).size,5)
 for(const a of items.filter(a=>a.kind==='image')){const bytes=Buffer.from(await (await response(`workflows/runs/${result.runId}/artifacts/${a.id}`)).arrayBuffer());assert.equal(bytes.subarray(1,4).toString(),'PNG')}
 passed('save/reopen across service restart: nested cross-origin iframe + typed branch + foreach/continue + real input/click/extract/PNG + cumulative [1,3]')
 const events=[];let seq=0;while(true){const page=await api(`workflows/runs/${result.runId}/events?afterSeq=${seq}&limit=7`);events.push(...page.items);seq=page.nextSeq;if(!page.hasMore)break}
 assert.deepEqual(events.map(e=>e.seq),Array.from({length:events.length},(_,i)=>i+1));assert.equal(events.filter(e=>e.type==='node_started').length,result.executionCount)
 assert.equal(events.filter(e=>e.type==='node_succeeded'&&e.nodeId==='verify').length,1)
 passed('execution IDs, loop iterations, branch selection, exact event continuation and dynamic execution count')
 const many=flow([node('open','open_page',{url:url+'/inner'}),node('loop','loop',{mode:'count',source:literal(55),endNodeId:'end'}),node('extract','get_element_info',{selector:'#inside',variableName:'v'}),node('end','loop_end',{ownerNodeId:'loop'})],[['open','out','loop'],['loop','body','extract'],['extract','out','end']])
 result=await execute(many);assert.equal(result.state,'succeeded',JSON.stringify(result.error));assert.equal(result.artifactCount,55);assert.equal(result.artifacts.length,50);assert.equal(result.nextArtifactCursor,50)
 items=await artifacts(result);assert.equal(items.length,55);assert.equal(new Set(items.map(a=>a.id)).size,55);assert.equal(await value(result,items[54]),'shadow')
 const filtered=await api(`workflows/runs/${result.runId}/artifacts?executionId=${items[54].executionId}`);assert.equal(filtered.items.length,1)
 await stop(child);await startBackend();assert.equal((await api('workflows/runs/'+result.runId)).artifactCount,55);assert.equal(await value(result,items[54]),'shadow')
 passed('55 repeated real Shadow DOM extractions remain unique, paginated, execution-filterable and readable after restart')
 const pure=flow([node('loop','loop',{source:literal(1000),endNodeId:'end'}),node('add','set_variable',{variableName:'count',operation:'add',value:literal(1)}),node('end','loop_end',{ownerNodeId:'loop'}),node('open','open_page',{url:url+'/inner'}),node('input','input_text',{selector:'#entry',text:'{count}'}),node('read','get_element_info',{selector:'#entry',attribute:'value'})],[['loop','body','add'],['add','out','end'],['loop','done','open'],['open','out','input'],['input','out','read']],[{name:'count',type:'number',value:0}])
 result=await execute(pure);assert.equal(result.state,'succeeded',JSON.stringify(result.error));assert.equal(await value(result,result.artifacts[0]),'1000');assert.equal(result.executionCount,3004)
 passed('1000 pure-variable iterations yield correctly and expose accumulated 1000 through a real browser value')
 pure.document.nodes[0].config={...pure.document.nodes[0].config,mode:'while',rules:[rule(literal(true),'is_true',true)],maxIterations:100000}
 const running=await api('workflows/runs',{method:'POST',body:JSON.stringify({runId:randomUUID(),profileId:profile.id,...pure})})
 await until(async()=> (await api('workflows/runs/'+running.runId)).executionCount>20,'pure loop starts')
 const began=Date.now();const stopped=await api('workflows/runs/'+running.runId+'/stop',{method:'POST'});assert.equal(stopped.state,'cancelled');assert.ok(Date.now()-began<10000);await noOwnedBrowsers()
 passed('stop interrupts a pure-variable while loop and confirms worker/browser cleanup before terminal response')
 const pageRule=(selector,operator='exists',framePath=[])=>({kind:'page',selector,operator,framePath})
 const decisions=[
 ['zero', 'all', [pageRule('#absent')], false],
 ['hidden','all',[pageRule('#hidden','visible')],false],
 ['hidden-negative','all',[pageRule('#hidden','not_visible')],true],
 ['zero-negative','all',[pageRule('#absent','not_exists')],true],
 ['shadow','all',[pageRule('#shadow #inside','visible')],true],
 ['xpath','all',[pageRule('xpath=//input[@id="entry"]')],true],
 ['short-all','all',[rule(literal(false),'is_true',true),pageRule('[')],false],
 ['short-any','any',[rule(literal(true),'is_true',true),pageRule('[')],true],
 ]
 for(const [name,match,rules,expected] of decisions){
  const b=flow([node('open','open_page',{url:url+'/inner'}),node('c','condition',{match,rules,endNodeId:'end'}),node('yes','set_variable',{variableName:'answer',value:literal(true)}),node('no','set_variable',{variableName:'answer',value:literal(false)}),node('end','condition_end',{ownerNodeId:'c'}),node('input','input_text',{selector:'#entry',text:'{answer}'}),node('read','get_element_info',{selector:'#entry',attribute:'value'})],[['open','out','c'],['c','true','yes'],['c','false','no'],['yes','out','end'],['no','out','end'],['end','out','input'],['input','out','read']])
  const r=await execute(b);assert.equal(r.state,'succeeded',name+JSON.stringify(r.error));assert.equal(await value(r,r.artifacts[0]),String(expected),name)
 }
 for(const [selector,frames,path] of [['[',[],['config','rules','0','selector']],['#entry',['#absent'],['config','rules','0','framePath','0']]]){
  const b=flow([node('open','open_page',{url:url+'/inner'}),node('c','condition',{rules:[pageRule(selector,'exists',frames)],endNodeId:'end'}),node('end','condition_end',{ownerNodeId:'c'})],[['open','out','c'],['c','true','end'],['c','false','end']])
  const r=await execute(b);assert.equal(r.state,'failed');assert.deepEqual(r.error.path,path);assert.equal(r.error.nodeId,'c')
 }
 passed('real page predicates: zero/hidden/negative/XPath/open Shadow, ordered all/any short circuit; invalid CSS and missing frame fail with exact rule path')
 const whileFlow=flow([node('loop','loop',{mode:'while',rules:[rule(variable('n'),'lt',2)],endNodeId:'end',maxIterations:2}),node('add','set_variable',{variableName:'n',operation:'add',value:literal(1)}),node('end','loop_end',{ownerNodeId:'loop'}),node('open','open_page',{url:url+'/inner'}),node('input','input_text',{selector:'#entry',text:'{n}'}),node('read','get_element_info',{selector:'#entry',attribute:'value'})],[['loop','body','add'],['add','out','end'],['loop','done','open'],['open','out','input'],['input','out','read']],[{name:'n',type:'number',value:0}])
 result=await execute(whileFlow);assert.equal(result.state,'succeeded');assert.equal(await value(result,result.artifacts[0]),'2')
 whileFlow.document.nodes[0].config.maxIterations=1;result=await execute(whileFlow);assert.equal(result.state,'failed');assert.equal(result.error.code,'LOOP_LIMIT_EXCEEDED');assert.equal(result.artifactCount,0)
 const nested=flow([node('outer','loop',{mode:'foreach',source:variable('items'),indexVariable:'outerIndex',itemVariable:'outerItem',endNodeId:'outerEnd'}),node('inner','loop',{source:literal(3),endNodeId:'innerEnd'}),node('break','break_loop'),node('innerEnd','loop_end',{ownerNodeId:'inner'}),node('append','set_variable',{variableName:'items',operation:'append',value:literal(9)}),node('outerEnd','loop_end',{ownerNodeId:'outer'}),node('open','open_page',{url:url+'/inner'}),node('input','input_text',{selector:'#entry',text:'{items}'}),node('read','get_element_info',{selector:'#entry',attribute:'value'})],[['outer','body','inner'],['inner','body','break'],['inner','done','append'],['append','out','outerEnd'],['outer','done','open'],['open','out','input'],['input','out','read']],[{name:'items',type:'array',value:[1,2]}])
 result=await execute(nested);assert.equal(result.state,'succeeded');assert.deepEqual(JSON.parse(await value(result,result.artifacts[0])),[1,2,9,9])
 passed('real worker while re-evaluation/limit failure and nested break only nearest loop; foreach snapshot ignores appended items')

} finally {
 await stop(child).catch(()=>{});server.closeAllConnections();await new Promise(r=>server.close(r));await noOwnedBrowsers().catch(()=>{})
 await writeFile(join(qa,`${mode}-control.json`),JSON.stringify({platform:process.platform,arch:process.arch,mode,kernelVersion:kernel.version,checks,complete:checks.length===7},null,2))
 await rm(workspace,{recursive:true,force:true})
}
