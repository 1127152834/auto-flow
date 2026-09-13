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
const workspace = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-m2-runs-')))
const copied = join(workspace, 'data/kernels', basename(kernel.directory))
await cp(kernel.directory, copied, { recursive: true, verbatimSymlinks: true, mode: constants.COPYFILE_FICLONE })
const html = await readFile(join(root, 'apps/backend/tests/fixtures/workflow-page.html'))
const observations = [], actions = [], visits = []
const server = createServer(async (req,res) => {
  visits.push(req.url)
  if (req.method === 'POST') {
    let body='';for await (const chunk of req) body += chunk;
    if (req.url === '/observation') observations.push(JSON.parse(body));
    if (req.url === '/action') actions.push(body);
    res.end('ok');return;
  }
  if (req.url === '/hang') return;
  if (req.url === '/popup') { res.setHeader('Content-Type','text/html');res.end('<h1 id="popup-result">popup</h1>');return; }
  if (req.url === '/pixel.svg') { res.setHeader('Content-Type','image/svg+xml');res.end('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"><rect width="24" height="24" fill="red"/></svg>');return; }
  res.setHeader('Content-Type','text/html;charset=utf-8');res.end(html);
})
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
const url = `http://127.0.0.1:${server.address().port}`
const token = randomUUID(), hostToken = randomUUID()
let child, base, catalog, profile
const checks=[]
const executable = arg('--executable')
const mode = executable ? 'frozen' : 'source'
const qa=arg('--qa-directory') ? resolve(arg('--qa-directory')) : join(root,'docs/migration/automation-studio-m2-qa')
await mkdir(qa,{recursive:true})
const wait = ms => new Promise(resolve=>setTimeout(resolve,ms))
async function until(fn,label,ms=20000) { const end=Date.now()+ms;while(Date.now()<end){const v=await fn();if(v)return v;await wait(80)}throw new Error(`Timeout: ${label}`) }
async function startBackend() {
  const command=executable?[resolve(executable)]:['uv','run','--directory','apps/backend','python','-m','autoflow']
  child=spawn(command[0],[...command.slice(1),'--data-dir',workspace,'--instance-id',randomUUID(),'--port','0'],{cwd:root,env:{...process.env,AUTOFLOW_INSTANCE_TOKEN:token,AUTOFLOW_HOST_TOKEN:hostToken},stdio:['ignore','pipe','pipe']})
  let output='', errors='';child.stderr.on('data',b=>{errors+=b})
  child.stdout.on('data',b=>{output+=b})
  await until(()=>{if(child.exitCode!==null)throw new Error(`Backend ${child.exitCode}: ${errors}`);const match=output.match(/AUTOFLOW_READY (.+)/);if(match){base=`http://127.0.0.1:${JSON.parse(match[1]).port}`;return true}},'backend ready',30000)
}
async function response(path,options={}) { return fetch(base+'/api/v1/'+path,{...options,headers:{'x-autoflow-token':token,'content-type':'application/json',...options.headers},signal:AbortSignal.timeout(15000)}) }
async function api(path,options={}) {const r=await response(path,options);const text=await r.text();assert.ok(r.ok,`${path}: ${r.status} ${text}`);return text?JSON.parse(text):null}
function request(steps,variables=[]) {
  const nodes=steps.map(([type,config],i)=>({id:`n${i}`,type,label:`${i+1} ${type}`,config:{...catalog.find(x=>x.type===type).defaultConfig,...config}}))
  return {runId:randomUUID(),profileId:profile.id,document:{id:randomUUID(),name:'M2 controlled run',schemaVersion:1,nodes,edges:nodes.slice(1).map((n,i)=>({id:`e${i}`,source:nodes[i].id,target:n.id,sourceHandle:'out',targetHandle:'in'})),variables},layout:{nodes:Object.fromEntries(nodes.map((n,i)=>[n.id,{x:i*240,y:100}])),viewport:{x:0,y:0,zoom:1}}}
}
const open=['open_page',{url}]
async function launch(body) { return api('workflows/runs',{method:'POST',body:JSON.stringify(body)}) }
async function terminal(id,expected='succeeded') {const record=await until(async()=>{const r=await api(`workflows/runs/${id}`);return ['succeeded','failed','cancelled','interrupted'].includes(r.state)?r:null},`terminal ${id}`,30000);assert.equal(record.state,expected,JSON.stringify(record.error));return record}
async function run(steps,variables=[]) {const body=request(steps,variables);await launch(body);return terminal(body.runId)}
async function values(record) {return Promise.all(record.artifacts.filter(a=>a.kind==='json').map(async a=>{const r=await response(`workflows/runs/${record.runId}/artifacts/${a.id}`);assert.ok(r.ok);return r.json()}))}
function passed(label) {checks.push(label);console.log('PASS '+label)}
async function noOwnedBrowsers() {
  if(process.platform==='win32')return;
  await until(()=>!execFileSync('ps',['-ax','-o','command='],{encoding:'utf8'}).split('\n').some(l=>l.includes(copied)&&!l.includes('ps -ax')),'owned browser cleanup',10000)
}

try {
  await startBackend()
  catalog=(await api('workflows/node-catalog')).items
  profile=await api('profiles',{method:'POST',body:JSON.stringify({name:'M2 controlled profile',browserVersion:kernel.version,startUrl:url+'/unexpected-start',locale:'ja-JP',timezone:'Asia/Tokyo',headless:true,viewportJson:{width:1100,height:700},proxyMode:'none'})})
  const chain=[open,['input_text',{selector:'#entry',text:'${输入}'}],['click_element',{selector:'#submit'}],['wait_element',{selector:'#result'}],['get_element_info',{selector:'#result'}],['screenshot',{}]]
  const first=request(chain,[{name:'输入',type:'string',value:'AutoFlow真实运行'}])
  await launch(first)
  assert.equal((await launch(first)).runId,first.runId)
  let result=await terminal(first.runId)
  assert.deepEqual(await values(result),['AutoFlow真实运行'])
  assert.deepEqual((await api('workflows')).items,[])
  const png=result.artifacts.find(a=>a.kind==='image')
  const image=Buffer.from(await (await response(`workflows/runs/${result.runId}/artifacts/${png.id}`)).arrayBuffer())
  assert.equal(image.subarray(1,4).toString(),'PNG')
  await writeFile(join(qa,`${mode}-fullpage.png`),image)
  await noOwnedBrowsers()
  passed('six real nodes; unsaved snapshot; idempotent request; extraction and real PNG; cleanup')

  result=await run([open,['input_text',{selector:'#entry',text:'-append',clearBefore:false}],['get_element_info',{selector:'#entry',attribute:'value'}],['input_text',{selector:'#entry',text:''}],['get_element_info',{selector:'#entry',attribute:'value'}],['input_text',{selector:'#container',text:'container'}],['get_element_info',{selector:'#container input',attribute:'value'}],['input_text',{selector:'#editable',text:'-tail',clearBefore:false}],['get_element_info',{selector:'#editable'}],['input_text',{selector:'.many',text:'chosen'}],['get_element_info',{selector:'xpath=//input[@class="many"]',attribute:'value'}]])
  assert.deepEqual(await values(result),['seed-append','','container','seed-tail','chosen'])
  passed('replacement, append, empty input, container, contenteditable, CSS/XPath first match')

  result=await run([open,['get_element_info',{selector:'#info'}],['get_element_info',{selector:'#info',attribute:'innerHTML'}],['get_element_info',{selector:'#link',attribute:'href'}],['get_element_info',{selector:'#image',attribute:'src'}],['get_element_info',{selector:'#info',attribute:'href'}],['get_element_info',{selector:'#link',attribute:'attributes'}],['get_element_info',{selector:'#large'}],['click_element',{selector:'#timers'}],['wait_element',{selector:'#attached',waitCondition:'attached'}],['wait_element',{selector:'#attached',waitCondition:'hidden'}],['wait_element',{selector:'#remove',waitCondition:'detached'}],['wait_element',{selector:'#hidden',waitCondition:'visible'}]])
  const extracted=await values(result)
  assert.equal(extracted[0],'plainhidden text');assert.match(extracted[1],/<span/)
  assert.equal(extracted[2],'/relative');assert.equal(extracted[3],'/pixel.svg');assert.equal(extracted[4],null)
  assert.equal(extracted[5]['data-label'],'中文');assert.equal(extracted[6],'中文数据'.repeat(20000))
  passed('six extraction modes including raw attributes/null/large UTF-8 results; all wait states')

  result=await run([open,['click_element',{selector:'#popup',followNewTab:false}],['get_element_info',{selector:'#entry',attribute:'value'}],['click_element',{selector:'#popup',followNewTab:true}],['get_element_info',{selector:'#popup-result'}]])
  assert.deepEqual(await values(result),['seed','popup'])
  result=await run([open,['click_element',{selector:'#noop',followNewTab:true}],['click_element',{selector:'#double',clickType:'double'}],['get_element_info',{selector:'#result'}],['click_element',{selector:'#right',clickType:'right'}],['get_element_info',{selector:'#result'}]])
  assert.deepEqual(await values(result),['double','right'])
  passed('popup follow on/off and no-popup success; double/right clicks')

  const external=join(workspace,'external','explicit.PNG')
  result=await run([open,['screenshot',{screenshotType:'viewport',savePath:'nested'}],['screenshot',{screenshotType:'element',selector:'#entry',savePath:external}]])
  assert.equal(result.artifacts.length,2)
  assert.deepEqual(await readFile(external),Buffer.from(await (await response(`workflows/runs/${result.runId}/artifacts/${result.artifacts[1].id}`)).arrayBuffer()))
  for(const config of [{screenshotType:'viewport',savePath:external},{savePath:'../escape.png'}]) {
    const b=request([open,['screenshot',config]]);await launch(b);const failed=await terminal(b.runId,'failed');assert.equal(failed.error.nodeId,'n1')
  }
  passed('viewport/element screenshots, relative directory, explicit absolute PNG, retained copy, collision/traversal refusal')

  const invalid=request([['open_page',{url:''}]]);assert.equal((await response('workflows/runs',{method:'POST',body:JSON.stringify(invalid)})).status,422)
  const timeout=request([open,['wait_element',{selector:'#never',timeoutSeconds:0.25}],['click_element',{selector:'#submit'}]])
  const before=actions.length;await launch(timeout);result=await terminal(timeout.runId,'failed');assert.equal(result.error.nodeId,'n1');assert.equal(actions.length,before)
  const waiting=request([open,['wait_element',{selector:'#never'}],['click_element',{selector:'#submit'}]])
  await launch(waiting);await until(async()=>(await api(`workflows/runs/${waiting.runId}`)).currentNodeId==='n1','long wait started')
  assert.equal((await response('workflows/runs',{method:'POST',body:JSON.stringify(request([open]))})).status,409)
  assert.equal((await response(`profiles/${profile.id}`,{method:'DELETE'})).status,409)
  assert.equal((await response(`kernels/${kernel.version}?edition=public`,{method:'DELETE'})).status,409)
  const stopped=Date.now();await api(`workflows/runs/${waiting.runId}/stop`,{method:'POST'});await terminal(waiting.runId,'cancelled');assert.ok(Date.now()-stopped<10000)
  assert.equal(actions.length,before);await noOwnedBrowsers()
  passed('preflight, fractional timeout, fail-fast, single active run, resource deletion guard, stop interrupts wait')

  let events=[],seq=0
  while(true){const page=await api(`workflows/runs/${first.runId}/events?afterSeq=${seq}&limit=2`);events.push(...page.items);seq=page.nextSeq;if(!page.hasMore)break}
  assert.deepEqual(events.map(e=>e.seq),Array.from({length:events.length},(_,i)=>i+1))
  const stream=await response(`workflows/runs/${first.runId}/stream?afterSeq=${events[0].seq}`)
  const reader=stream.body.getReader();const chunk=new TextDecoder().decode((await reader.read()).value);assert.ok(chunk.includes('data:'));await reader.cancel()
  await stop(child);await startBackend();assert.equal((await api(`workflows/runs/${first.runId}`)).state,'succeeded')
  assert.equal((await api(`workflows/runs/${first.runId}/events?limit=1000`)).items.length,events.length)
  assert.deepEqual(await values(await api(`workflows/runs/${first.runId}`)),['AutoFlow真实运行'])
  passed('ordered event pagination, SSE cursor replay, restart restores run/log/results without replay')
  assert.ok(observations.length>=4)
  assert.ok(observations.every(o=>o.cookie===''&&o.storage===null&&o.locale==='ja-JP'&&o.timezone==='Asia/Tokyo'),JSON.stringify(observations.map(({cookie,storage,locale,timezone})=>({cookie,storage,locale,timezone}))))
  assert.ok(!visits.includes('/unexpected-start'))
  passed('temporary sessions isolated; actual locale/timezone; Profile start URL not visited')
} finally {
  await stop(child).catch(()=>{});server.closeAllConnections();await new Promise(resolve=>server.close(resolve));await noOwnedBrowsers().catch(()=>{});
  await writeFile(join(qa,`${mode}.json`),JSON.stringify({platform:process.platform,arch:process.arch,mode,kernelVersion:kernel.version,checks,observations,complete:checks.length===8},null,2))
  await rm(workspace,{recursive:true,force:true})
}
