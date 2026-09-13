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
const workspace = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-m3-inspection-')))
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
let child, base, profile
const checks=[]
const executable = arg('--executable')
const mode = executable ? 'frozen' : 'source'
const qa=join(root,'docs/migration/automation-studio-m3-qa')
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

const inspectionPath='workflows/inspection-sessions'
const startInspection=()=>api(inspectionPath,{method:'POST',body:JSON.stringify({sessionId:randomUUID(),profileId:profile.id})})
async function ready(id){return until(async()=>{const s=await api(inspectionPath+'/'+id);if(s.state==='failed')throw new Error(JSON.stringify(s));return s.state==='ready'?s:null},'inspection ready',60000)}
const closeInspection=id=>api(inspectionPath+'/'+id+'/close',{method:'POST'})
function workerPid(){const rows=execFileSync('ps',['-ax','-o','pid=,ppid=,command='],{encoding:'utf8'}).split('\n');return rows.map(l=>l.trim().match(/^(\d+)\s+(\d+)\s+(.*)$/)).find(m=>m&&Number(m[2])===child.pid&&m[3].includes('--inspection-worker'))?.[1]}
try {
  await startBackend()
  profile=await api('profiles',{method:'POST',body:JSON.stringify({name:'M3 worker cleanup profile',browserVersion:kernel.version,headless:true,startUrl:url+'/unexpected-start',locale:'ja-JP',timezone:'Asia/Tokyo'})})
  let s=await startInspection();s=await ready(s.sessionId)
  assert.equal(s.pages[0].url,'about:blank');assert.equal(s.headless,false)
  assert.equal((await api(inspectionPath,{method:'POST',body:JSON.stringify({sessionId:s.sessionId,profileId:profile.id})})).sessionId,s.sessionId)
  assert.equal((await response(inspectionPath,{method:'POST',body:JSON.stringify({sessionId:randomUUID(),profileId:profile.id})})).status,409)
  assert.equal((await response('profiles/'+profile.id,{method:'DELETE'})).status,409)
  await api(inspectionPath+'/'+s.sessionId+'/page',{method:'POST',body:JSON.stringify({pageId:s.pages[0].pageId,url})})
  const tested=await api(inspectionPath+'/'+s.sessionId+'/test-selector',{method:'POST',body:JSON.stringify({pageId:s.pages[0].pageId,selector:'#entry'})})
  assert.equal(tested.count,1)
  await closeInspection(s.sessionId);await noOwnedBrowsers()
  passed('real worker launch, headless override, blank start, idempotency, exclusive resource locks, navigation/test, cleanup')
  for(let attempt=0;attempt<5;attempt++){s=await startInspection();const began=Date.now();await closeInspection(s.sessionId);assert.ok(Date.now()-began<10000,'startup close exceeded 10s');await noOwnedBrowsers()}
  passed('five consecutive closes during startup clean worker/browser and release sessions')
  s=await startInspection();s=await ready(s.sessionId)
  const pending=response(inspectionPath+'/'+s.sessionId+'/page',{method:'POST',body:JSON.stringify({pageId:s.pages[0].pageId,url:url+'/hang'})}).catch(()=>null)
  await until(()=>visits.includes('/hang'),'pending navigation')
  const started=Date.now();await closeInspection(s.sessionId);assert.ok(Date.now()-started<10000);await pending;await noOwnedBrowsers()
  passed('close interrupts pending navigation without waiting full node timeout')
  s=await startInspection();await ready(s.sessionId)
  let pid=await until(workerPid,'owned worker PID');process.kill(Number(pid),'SIGKILL')
  await until(async()=>['failed','closed'].includes((await api(inspectionPath+'/'+s.sessionId)).state),'worker terminal');await noOwnedBrowsers()
  passed('SIGKILL owned worker reaps its browser tree and releases resources')
  s=await startInspection();await ready(s.sessionId)
  pid=await until(workerPid,'owned worker PID');process.kill(child.pid,'SIGKILL');await noOwnedBrowsers()
  await until(()=>{try{process.kill(Number(pid),0);return false}catch{return true}},'orphan worker gone')
  await startBackend();assert.equal(await api(inspectionPath),null)
  s=await startInspection();await ready(s.sessionId);await closeInspection(s.sessionId);await noOwnedBrowsers()
  passed('sidecar crash cleans owned worker/browser; restart creates no session and permits a fresh one')
} finally {
  if(child?.exitCode===null){const s=await api(inspectionPath).catch(()=>null);if(s&&!['closed','failed'].includes(s.state))await closeInspection(s.sessionId).catch(()=>{})}
  await stop(child).catch(()=>{});server.closeAllConnections();await new Promise(r=>server.close(r));await noOwnedBrowsers().catch(()=>{})
  await writeFile(join(qa,`${mode}-worker.json`),JSON.stringify({platform:process.platform,arch:process.arch,mode,kernelVersion:kernel.version,checks,complete:checks.length===5},null,2))
  await rm(workspace,{recursive:true,force:true})
}
