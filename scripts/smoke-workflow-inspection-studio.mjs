import assert from 'node:assert/strict'
import { constants } from 'node:fs'
import { cp, mkdir, mkdtemp, readFile, readdir, realpath, rm, writeFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import { homedir, tmpdir } from 'node:os'
import { basename, join, resolve } from 'node:path'
import { launchElectron, connectCdp, wait, waitFor } from './electron-cdp.mjs'
import { inspectPublicKernel } from './smoke-profile-test-browser.mjs'
import { stop } from './smoke-sidecar.mjs'

const root=resolve(import.meta.dirname,'..')
const installed=join(homedir(),'Library/Application Support/@autoflow/desktop/data/kernels')
const supplied=process.argv.indexOf('--kernel-directory')
const kernel=await inspectPublicKernel(supplied<0?join(installed,(await readdir(installed)).filter(n=>/^chromium-[\d.]+$/.test(n)).sort().at(-1)):process.argv[supplied+1])
const workspace=await realpath(await mkdtemp(join(tmpdir(),'autoflow-m3-studio-')))
const target=await realpath(await mkdtemp(join(tmpdir(),'autoflow-m3-target-')))
await cp(kernel.directory,join(workspace,'data/kernels',basename(kernel.directory)),{recursive:true,verbatimSymlinks:true,mode:constants.COPYFILE_FICLONE})
await writeFile(join(workspace,'.autoflow-workspace.json'),JSON.stringify({schemaVersion:1,kind:'autoflow-workspace'}))
await writeFile(join(workspace,'desktop-settings.json'),JSON.stringify({schemaVersion:1,currentPath:workspace,previousPath:target,preferences:{zoom:100,motion:'system'}}))
let pickTarget = false
const server=createServer(async(req,res)=>{
  if(req.url==='/pick-target'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify(pickTarget));return}
  res.setHeader('Content-Type','text/html;charset=utf-8')
  const html=req.url==='/frame'?`<meta charset=utf-8><title>M3 iframe</title><p id="result">M3 真实框架结果</p><script>setInterval(async()=>{if(window.__autoflowPicker?.active && await(await fetch('/pick-target')).json())document.querySelector('#result').click()},250)</script>`:`<meta charset=utf-8><title>M3 controlled page</title><h1>M3</h1><iframe id="outer" src="http://localhost:${server.address().port}/frame" style="width:600px;height:300px"></iframe>`
  res.end(html)
})
await new Promise(r=>server.listen(0,'127.0.0.1',r))
const url=`http://127.0.0.1:${server.address().port}`
const qa=join(root,'docs/migration/automation-studio-m3-qa');await mkdir(qa,{recursive:true})
const mode=process.argv.includes('--executable')?'packaged':process.argv.includes('--dev')?'dev':'built'
let desktop,studio,native,devServer,context
const checks=[]
const until = async (fn,label,ms=30000) => { const end=Date.now()+ms; while(Date.now()<end){const value=await fn();if(value)return value;await wait(100)}throw new Error('Timeout: '+label) }
async function targets(){return (await(await fetch(desktop.debugOrigin+'/json/list')).json()).filter(t=>t.type==='page')}
async function api(path,options={}){const r=await fetch(context.sidecar.baseUrl+'/api/v1/'+path,{...options,headers:{'x-autoflow-token':context.sidecar.token,'content-type':'application/json'},signal:AbortSignal.timeout(15000)});const text=await r.text();assert.ok(r.ok,`${path}: ${r.status} ${text}`);return text?JSON.parse(text):null}
async function click(cdp,selector,text){const p=await waitFor(cdp,`(()=>{const e=${selector?`document.querySelector(${JSON.stringify(selector)})`:`[...document.querySelectorAll('button')].find(e=>e.textContent.trim()===${JSON.stringify(text)})`};if(!e||e.disabled)return false;e.scrollIntoView({block:'nearest'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2,hit=document.elementFromPoint(x,y);return hit && e.contains(hit)?{x,y}:false})()`,text||selector);await cdp.command('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...p});await cdp.command('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...p});await wait(100)}
async function input(cdp,selector,value){await cdp.evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.focus();const proto=e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(proto,'value').set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));e.blur()})()`);await wait(75)}
async function labeled(label,value){const id=await studio.evaluate(`[...document.querySelectorAll('label')].find(e=>e.textContent.trim()===${JSON.stringify(label)}).htmlFor`);await input(studio,'#'+CSSescape(id),value)}
function CSSescape(id){return id.replace(/[^a-zA-Z0-9_-]/g,c=>'\\'+c)}
async function add(name) {
  const before = await studio.evaluate(`[...document.querySelectorAll('.react-flow__node')].map(n=>n.dataset.id)`)
  await click(studio, `[aria-label="添加${name}"]`)
  return await waitFor(studio, `[...document.querySelectorAll('.react-flow__node')].map(n=>n.dataset.id).find(id=>!${JSON.stringify(before)}.includes(id))`, 'added node')
}
async function connect(ids) {
  await click(studio, '.react-flow__controls-fitview')
  await wait(500)
  for (let i = 0; i < ids.length - 1; i++) {
    const pts = await studio.evaluate(`[${JSON.stringify(ids[i])},${JSON.stringify(ids[i+1])}].map((id,i)=>{const r=document.querySelector('.react-flow__node[data-id="'+id+'"] '+(i?'.target':'.source')).getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})`)
    await studio.command('Input.dispatchMouseEvent', {type:'mouseMoved', ...pts[0]})
    await studio.command('Input.dispatchMouseEvent', {type:'mousePressed', button:'left', buttons:1, clickCount:1, ...pts[0]})
    for (let n = 1; n <= 8; n++) await studio.command('Input.dispatchMouseEvent', {type:'mouseMoved', button:'left', buttons:1, x:pts[0].x+(pts[1].x-pts[0].x)*n/8, y:pts[0].y+(pts[1].y-pts[0].y)*n/8})
    await studio.command('Input.dispatchMouseEvent', {type:'mouseReleased', button:'left', clickCount:1, ...pts[1]})
    await waitFor(studio, `document.querySelectorAll('.react-flow__edge').length===${i+1}`, 'connected edge')
  }
}
async function capture(name){await writeFile(join(qa,`${mode}-${name}.png`),Buffer.from((await studio.command('Page.captureScreenshot',{format:'png'})).data,'base64'))}
function passed(label){checks.push(label);console.log('PASS '+label)}

try {
  if(process.argv.includes('--dev')){const {resolveConfig}=await import('electron-vite');const {createServer}=await import('vite');const {config}=await resolveConfig({root:join(root,'apps/desktop')},'serve','development');devServer=await createServer({...config.renderer,root:join(root,'apps/desktop/src/renderer'),server:{host:'127.0.0.1',port:0}});await devServer.listen();process.env.ELECTRON_RENDERER_URL=devServer.resolvedUrls.local[0]}
  desktop=await launchElectron(root,{launchArgs:[`--user-data-dir=${workspace}`,'--inspect=0']})
  native=await connectCdp(desktop.inspectorUrl)
  await native.evaluate("globalThis.smokeElectron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');true")
  await waitFor(desktop.cdp,`document.body?.innerText.includes('工作流工作台')`,'main ready',30000)
  context=await desktop.cdp.evaluate('window.autoflow.getRuntimeContext()')
  const profile=await api('profiles',{method:'POST',body:JSON.stringify({name:'M3 真实拾取配置',browserVersion:kernel.version,headless:true,viewportJson:{width:1100,height:700}})})
  await desktop.cdp.evaluate('window.autoflow.openAutomationStudio()')
  const t=await until(async()=>(await targets()).find(t=>t.url.includes('view=automation-studio')),'Studio')
  studio=await connectCdp(t.webSocketDebuggerUrl)
  await waitFor(studio,`Boolean(document.querySelector('#run-profile option[value]:not([value=""])'))`,'profiles')
  await click(studio,'[aria-label="拾取浏览器"] button')
  await studio.evaluate(`(()=>{for(const e of [document.querySelector('#run-profile'),document.querySelector('[aria-label="拾取浏览器配置"]')]){e.value=${JSON.stringify(profile.id)};e.dispatchEvent(new Event('change',{bubbles:true}))}})()`)
  await click(studio,'','打开拾取浏览器')
  let session=await until(async()=>{const s=await api('workflows/inspection-sessions');return s?.state==='ready'?s:null},'real inspection worker',60000)
  assert.equal(session.headless,false)
  assert.equal(session.pages[0].url,'about:blank')
  await waitFor(studio,`Boolean(document.querySelector('[aria-label="拾取目标标签页"]')?.value)`,'target page visible')
  await input(studio,'[aria-label="拾取网页地址"]',url)
  await click(studio,'','前往')
  await until(async()=>{session=await api('workflows/inspection-sessions');return session.pages[0]?.url===url+'/'},'navigation')
  passed('formal Studio starts dedicated visible browser from headless Profile and manually navigates')
  const ids=[await add('打开网页'),await add('提取数据')];await connect(ids)
  await click(studio,`.react-flow__node[data-id="${ids[0]}"]`);await labeled('网页地址',url)
  await click(studio,`.react-flow__node[data-id="${ids[1]}"]`)
  pickTarget=true
  await click(studio,'','拾取元素')
  await waitFor(studio,`document.body.innerText.includes('应用到节点')`,'actual iframe picker result',20000)
  pickTarget=false
  await capture('picker')
  await click(studio,'','应用到节点')
  await waitFor(studio,`document.querySelector('[aria-label="元素定位工具"] textarea').value==='#outer'`,'applied frame path')
  await click(studio,'','测试定位')
  await waitFor(studio,`document.body.innerText.includes('匹配 1 个元素')`,'real locator result')
  await capture('test')
  await click(studio,'','保存')
  await waitFor(studio,`document.body.innerText.includes('已保存')`,'saved')
  const saved=(await api('workflows')).items[0]
  const doc=await api('workflows/'+saved.id)
  assert.equal(doc.document.nodes[1].config.selector,'#result')
  assert.deepEqual(doc.document.nodes[1].config.framePath,['#outer'])
  await click(studio,'[aria-label="撤销"]');await waitFor(studio,`document.querySelector('[aria-label="元素定位工具"] textarea').value===''`,'undo picker application')
  await click(studio,'[aria-label="重做"]');await waitFor(studio,`document.querySelector('[aria-label="元素定位工具"] textarea').value==='#outer'`,'redo both target fields')
  passed('real iframe DOM picker result previews/applies/tests/saves; selector and frame path undo together')
  await click(studio,'','运行当前草稿')
  await waitFor(studio,`document.querySelector('[role=dialog]')?.innerText.includes('关闭拾取浏览器后运行')`,'run confirmation')
  await click(studio,'','取消')
  assert.equal((await api('workflows/inspection-sessions')).state,'ready')
  assert.equal((await api('workflows/runs')).items.length,0)
  await click(studio,'','运行当前草稿');await waitFor(studio,`Boolean(document.querySelector('[role=dialog]'))`,'confirm again')
  await click(studio,'','关闭并运行')
  const run=await until(async()=>{const list=await api('workflows/runs');if(!list.items.length)return null;const r=await api('workflows/runs/'+list.items[0].runId);if(r.state==='failed')throw new Error(JSON.stringify(r.error));return r.state==='succeeded'?r:null},'fresh run',60000)
  assert.equal((await api('workflows/inspection-sessions')).state,'closed')
  const artifact=run.artifacts.find(a=>a.kind==='json')
  assert.equal(await api(`workflows/runs/${run.runId}/artifacts/${artifact.id}`),'M3 真实框架结果')
  passed('cancel preserves inspection; confirm cleans inspection then independent worker executes saved iframe target')
  await click(studio,'','打开拾取浏览器')
  await until(async()=>(await api('workflows/inspection-sessions'))?.state==='ready','second session',60000)
  const studioWindow="smokeElectron.BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().includes('view=automation-studio'))"
  await native.evaluate(`${studioWindow}.close()`)
  await waitFor(studio,`document.querySelector('[role=dialog]')?.innerText.includes('关闭拾取浏览器')`,'native close protection')
  await click(studio,'','取消');assert.equal((await api('workflows/inspection-sessions')).state,'ready')
  await native.evaluate(`${studioWindow}.close()`)
  await waitFor(studio,`Boolean(document.querySelector('[role=dialog]'))`,'close again')
  await click(studio,'','关闭浏览器并继续')
  await until(async()=>(await api('workflows/inspection-sessions')).state==='closed','closed before window')
  passed('native Studio close is guarded; cancel keeps browser; confirmed close waits for cleanup')
} catch(error) {
  if(studio){await capture('failure').catch(()=>{});console.error(await studio.evaluate('document.body.innerText').catch(()=>''))}
  throw error
} finally {
  if(context){const s=await api('workflows/inspection-sessions').catch(()=>null);if(s&&!['closed','failed'].includes(s.state))await api('workflows/inspection-sessions/'+s.sessionId+'/close',{method:'POST'}).catch(()=>{})}
  studio?.close();native?.close();desktop?.cdp?.close();await stop(desktop?.child).catch(()=>{});await devServer?.close();server.closeAllConnections();await new Promise(r=>server.close(r))
  await writeFile(join(qa,`${mode}-studio.json`),JSON.stringify({platform:process.platform,arch:process.arch,mode,kernelVersion:kernel.version,checks,complete:checks.length===4,pickerInput:'Controlled page dispatches DOM click; trusted browser input and suppression independently tested by smoke-workflow-inspection.py'},null,2))
  await rm(workspace,{recursive:true,force:true});await rm(target,{recursive:true,force:true})
}
