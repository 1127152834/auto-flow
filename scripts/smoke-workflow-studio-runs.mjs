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
const workspace=await realpath(await mkdtemp(join(tmpdir(),'autoflow-m2-studio-')))
const target=await realpath(await mkdtemp(join(tmpdir(),'autoflow-m2-target-')))
await cp(kernel.directory,join(workspace,'data/kernels',basename(kernel.directory)),{recursive:true,verbatimSymlinks:true,mode:constants.COPYFILE_FICLONE})
await writeFile(join(workspace,'.autoflow-workspace.json'),JSON.stringify({schemaVersion:1,kind:'autoflow-workspace'}))
await writeFile(join(workspace,'desktop-settings.json'),JSON.stringify({schemaVersion:1,currentPath:workspace,previousPath:target,preferences:{zoom:100,motion:'system'}}))
const html=await readFile(join(root,'apps/backend/tests/fixtures/workflow-page.html'))
const server=createServer(async(req,res)=>{if(req.method==='POST'){for await(const _ of req){}res.end('ok')}else{res.setHeader('Content-Type','text/html;charset=utf-8');res.end(html)}})
await new Promise(r=>server.listen(0,'127.0.0.1',r))
const url=`http://127.0.0.1:${server.address().port}`
const qa=join(root,'docs/migration/automation-studio-m2-qa');await mkdir(qa,{recursive:true})
const mode=process.argv.includes('--executable')?'packaged':process.argv.includes('--dev')?'dev':'built'
let desktop,studio,native,devServer,context
const checks=[]
async function targets(){return (await(await fetch(desktop.debugOrigin+'/json/list')).json()).filter(t=>t.type==='page')}
async function api(path,options={}){const r=await fetch(context.sidecar.baseUrl+'/api/v1/'+path,{...options,headers:{'x-autoflow-token':context.sidecar.token,'content-type':'application/json'},signal:AbortSignal.timeout(15000)});const text=await r.text();assert.ok(r.ok,`${path}: ${r.status} ${text}`);return text?JSON.parse(text):null}
async function click(cdp,selector,text){const p=await cdp.evaluate(`(()=>{const e=${selector?`document.querySelector(${JSON.stringify(selector)})`:`[...document.querySelectorAll('button')].find(e=>e.textContent.trim()===${JSON.stringify(text)})`};if(!e||e.disabled)throw new Error('missing/disabled button');e.scrollIntoView({block:'nearest'});const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`);await cdp.command('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...p});await cdp.command('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...p});await wait(100)}
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

try{
  if(process.argv.includes('--dev')){const {resolveConfig}=await import('electron-vite');const {createServer}=await import('vite');const {config}=await resolveConfig({root:join(root,'apps/desktop')},'serve','development');devServer=await createServer({...config.renderer,root:join(root,'apps/desktop/src/renderer'),server:{host:'127.0.0.1',port:0}});await devServer.listen();process.env.ELECTRON_RENDERER_URL=devServer.resolvedUrls.local[0]}
  desktop=await launchElectron(root,{launchArgs:[`--user-data-dir=${workspace}`,'--inspect=0']})
  native=await connectCdp(desktop.inspectorUrl)
  await native.evaluate("globalThis.smokeElectron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');true")
  const main=desktop.cdp
  await waitFor(main,`document.body?.innerText.includes('工作流工作台')`,'main ready',30000)
  context=await main.evaluate('window.autoflow.getRuntimeContext()')
  await api('profiles',{method:'POST',body:JSON.stringify({name:'M2 Studio 浏览器',browserVersion:kernel.version,headless:true,locale:'ja-JP',timezone:'Asia/Tokyo',viewportJson:{width:1100,height:700}})})
  await main.evaluate('window.autoflow.openAutomationStudio()')
  let t;for(let i=0;i<100;i++){t=(await targets()).find(t=>t.url.includes('view=automation-studio'));if(t)break;await wait(100)}
  studio=await connectCdp(t.webSocketDebuggerUrl)
  await waitFor(studio,`Boolean(document.querySelector('#run-profile option[value]:not([value=""])'))`,'profile list')
  await studio.evaluate(`(()=>{const e=document.querySelector('#run-profile');e.value=[...e.options].find(o=>o.value).value;e.dispatchEvent(new Event('change',{bubbles:true}))})()`)
  const names=['打开网页','输入文本','点击元素','等待元素','提取数据','网页截图'],ids=[]
  for(const name of names)ids.push(await add(name))
  await connect(ids)
  const configure=async(i,fields)=>{await click(studio,`.react-flow__node[data-id="${ids[i]}"]`);for(const [label,value]of fields)await labeled(label,value)}
  await configure(0,[['网页地址',url]])
  await configure(1,[['元素选择器','#entry'],['输入文本','Studio真实草稿']])
  await configure(2,[['元素选择器','#submit']])
  await configure(3,[['元素选择器','#result']])
  await configure(4,[['元素选择器','#result']])
  await click(studio,`.react-flow__node[data-id="${ids[5]}"]`)
  const screenshotSelect=await studio.evaluate(`[...document.querySelectorAll('label')].find(e=>e.textContent.trim()==='截图范围').htmlFor`)
  await studio.evaluate(`(()=>{const e=document.getElementById(${JSON.stringify(screenshotSelect)});e.value='viewport';e.dispatchEvent(new Event('change',{bubbles:true}))})()`)
  await input(studio,'#workflow-name','M2 Studio 草稿快照')
  await click(studio,'','运行当前草稿')
  await input(studio,'#workflow-name','运行期间继续编辑')
  await waitFor(studio,`document.body.innerText.includes('运行完成')`,'real workflow success',30000)
  assert.deepEqual((await api('workflows')).items,[])
  const records=(await api('workflows/runs')).items
  const first=await api('workflows/runs/'+records[0].runId)
  assert.equal(first.state,'succeeded');assert.equal(first.name,'M2 Studio 草稿快照')
  assert.equal(await studio.evaluate(`document.querySelector('#workflow-name').value`),'运行期间继续编辑')
  assert.ok(await studio.evaluate(`document.body.innerText.includes('快照不同')`))
  await click(studio,'.react-flow__controls-fitview');await wait(300);await capture('logs')
  await click(studio,'[role="tab"][value="results"]',null).catch(async()=>{const id=await studio.evaluate(`[...document.querySelectorAll('[role=tab]')].find(e=>e.textContent.includes('只读结果')).id`);await click(studio,'#'+CSSescape(id))})
  await click(studio,'','查看完整结果');await click(studio,'','查看截图');await waitFor(studio,`Boolean(document.querySelector('[aria-label=运行记录] img')?.naturalWidth)`,'screenshot preview');await studio.evaluate(`document.querySelector('[aria-label=运行记录] img').scrollIntoView({block:'nearest'})`);await capture('results')
  passed('formal Studio draws/configures/connects six nodes and runs unsaved snapshot; concurrent edit preserved; real results')

  await click(studio,'','新建')
  await waitFor(studio,`Boolean(document.querySelector('[role=dialog]'))`,'discard old draft')
  await click(studio,'','放弃修改');await waitFor(studio,`!document.querySelector('[role=dialog]') && document.querySelectorAll('.react-flow__node').length===0`,'new empty draft');await wait(300)
  const waitIds=[await add('打开网页'),await add('等待元素')]
  await connect(waitIds)
  await click(studio,`.react-flow__node[data-id="${waitIds[0]}"]`);await labeled('网页地址',url)
  await click(studio,`.react-flow__node[data-id="${waitIds[1]}"]`);await labeled('元素选择器','#never')
  await click(studio,'','运行当前草稿')
  await waitFor(studio,`document.body.innerText.includes('运行中 · 1/2 步')`,'waiting run',30000)
  const active=(await api('workflows/runs')).activeRunId;assert.ok(active)
  const studioWindow="smokeElectron.BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().includes('view=automation-studio'))"
  await native.evaluate(`${studioWindow}.close()`)
  await waitFor(studio,`document.querySelector('[role=dialog]')?.innerText.includes('停止')`,'native run close guard')
  await capture('leave')
  await click(studio,'','取消');await waitFor(studio,`!document.querySelector('[role=dialog]')`,'dialog dismissed');await wait(250)
  assert.ok(['starting','running'].includes((await api('workflows/runs/'+active)).state))
  await native.evaluate('smokeElectron.app.quit()')
  await waitFor(studio,`Boolean(document.querySelector('[role=dialog]'))`,'quit guard');await click(studio,'','取消');await waitFor(studio,`!document.querySelector('[role=dialog]')`,'dialog dismissed');await wait(250)
  const choice=await main.evaluate("window.autoflow.chooseWorkspace('previous')");assert.equal(choice.ok,true)
  await main.evaluate(`window.switchResult=null;window.autoflow.confirmWorkspace(${JSON.stringify(choice.value.id)}).then(v=>window.switchResult=v);true`)
  await waitFor(studio,`Boolean(document.querySelector('[role=dialog]'))`,'workspace guard');await click(studio,'','取消');await waitFor(studio,`!document.querySelector('[role=dialog]')`,'dialog dismissed');await wait(250)
  assert.equal((await waitFor(main,'window.switchResult','switch cancelled')).ok,false)
  const restart=await main.evaluate(`window.autoflow.restartSidecar().then(()=>false,()=>true)`);assert.equal(restart,true)
  await waitFor(studio,`!document.body.innerText.includes('正在连接本地服务') && !document.body.innerText.includes('正在核实运行状态')`,'connection settled after rejected restart');await wait(250)
  passed('native close, quit and workspace switch cancellation preserve active run; explicit restart blocked')
  await native.evaluate(`${studioWindow}.close()`)
  await waitFor(studio,`Boolean(document.querySelector('[role=dialog]'))`,'native stop close')
  const discard=await studio.evaluate(`[...document.querySelectorAll('[role=dialog] button')].find(b=>b.textContent.includes('放弃')).textContent.trim()`)
  await click(studio,'',discard)
  for(let i=0;i<150;i++){if(!(await targets()).some(t=>t.url.includes('view=automation-studio')))break;await wait(100)}
  assert.equal((await api('workflows/runs/'+active)).state,'cancelled')
  assert.equal((await targets()).some(t=>t.url.includes('view=automation-studio')),false)
  await main.evaluate('window.autoflow.restartSidecar()');context=await main.evaluate('window.autoflow.getRuntimeContext()')
  assert.equal((await api('workflows/runs/'+first.runId)).state,'succeeded')
  passed('discard-and-stop cleans before native close; service restart retains completed record')
}catch(error){
  if(studio){await capture('failure').catch(()=>{});await writeFile(join(qa,`${mode}-failure.txt`),await studio.evaluate('document.body.innerText').catch(()=>String(error)))}
  throw error
}finally{
  studio?.close();native?.close();desktop?.cdp.close();await stop(desktop?.child,{graceMs:10000,killMs:2000}).catch(()=>{});await devServer?.close();server.closeAllConnections();await new Promise(r=>server.close(r))
  await writeFile(join(qa,`${mode}-studio.json`),JSON.stringify({mode,platform:process.platform,arch:process.arch,checks,complete:checks.length===3},null,2))
  await rm(workspace,{recursive:true,force:true});await rm(target,{recursive:true,force:true})
}
