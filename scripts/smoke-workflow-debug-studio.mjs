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
const workspace=await realpath(await mkdtemp(join(tmpdir(),'autoflow-m5-studio-')))
const target=await realpath(await mkdtemp(join(tmpdir(),'autoflow-m5-target-')))
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
const qa=join(root,'docs/migration/automation-studio-m5-qa');await mkdir(qa,{recursive:true})
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
async function edge(source,handle,target) {
 await click(studio,'.react-flow__controls-fitview');await wait(350)
 const before=await studio.evaluate(`document.querySelectorAll('.react-flow__edge').length`)
 const pts=await studio.evaluate(`[${JSON.stringify(source)},${JSON.stringify(target)}].map((id,i)=>{const r=document.querySelector('.react-flow__node[data-id="'+id+'"] '+(i?'.target':'.source[data-handleid="${handle}"]')).getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})`)
 await studio.command('Input.dispatchMouseEvent',{type:'mouseMoved',...pts[0]});await studio.command('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',buttons:1,clickCount:1,...pts[0]})
 for(let i=1;i<=10;i++)await studio.command('Input.dispatchMouseEvent',{type:'mouseMoved',buttons:1,button:'left',x:pts[0].x+(pts[1].x-pts[0].x)*i/10,y:pts[0].y+(pts[1].y-pts[0].y)*i/10})
 await studio.command('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...pts[1]})
 await waitFor(studio,`document.querySelectorAll('.react-flow__edge').length===${before+1}`,'control edge')
}
async function removeEdge(id) {
 await waitFor(studio,`Boolean(document.querySelector('.react-flow__edge[data-id="${id}"]'))`,'paired edge rendered')
 await studio.evaluate(`document.querySelector('.react-flow__edge[data-id="${id}"]').dispatchEvent(new MouseEvent('click',{bubbles:true}))`)
 await click(studio,'[aria-label="删除选中项"]')
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
 const profile=await api('profiles',{method:'POST',body:JSON.stringify({name:'M5 调试浏览器',browserVersion:kernel.version,headless:true})})
 await desktop.cdp.evaluate('window.autoflow.openAutomationStudio()')
 let t=await until(async()=>(await targets()).find(t=>t.url.includes('view=automation-studio')),'Studio');studio=await connectCdp(t.webSocketDebuggerUrl)
 await waitFor(studio,`Boolean(document.querySelector('#run-profile option[value]:not([value=""])'))`,'profiles')
 const open=await add('打开网页');await labeled('网页地址',url)
 const loop=await add('重复指定次数');await input(studio,'[aria-label="循环次数值"]','2')
 const branch=await add('条件判断')
 const extract=await add('提取数据');await labeled('元素选择器','#result')
 await input(studio,'#workflow-name','M5 正式调试控制流')
 await click(studio,'','保存')
 const summary=(await api('workflows')).items[0];let stored=await api('workflows/'+summary.id)
 const loopEnd=stored.document.nodes.find(n=>n.id===loop).config.endNodeId,joinNode=stored.document.nodes.find(n=>n.id===branch).config.endNodeId
 // Configure the iframe path through the existing M3 property field UI.
 await input(studio,'textarea[id^="frames-"]','#outer')
 await removeEdge(stored.document.edges.find(e=>e.source===loop).id)
 await removeEdge(stored.document.edges.find(e=>e.source===branch&&e.sourceHandle==='true').id)
 await edge(open,'out',loop);await edge(loop,'body',branch);await edge(branch,'true',extract);await edge(extract,'out',joinNode);await edge(joinNode,'out',loopEnd)
 await click(studio,'','保存');await until(async()=>{stored=await api('workflows/'+summary.id);return stored.document.edges.length===6},'saved complete control')
 assert.equal(stored.document.schemaVersion,2);assert.deepEqual(stored.issues,[])
 await capture('editor');passed('formal canvas creates paired loop/condition, configures typed count and iframe extraction, connects distinct handles and saves v2')
 await click(studio,'','新建');await click(studio,'','打开');await waitFor(studio,`(()=>{const e=[...document.querySelectorAll('[role=dialog] button')].find(e=>e.textContent.includes('M5 正式调试控制流'));if(e)e.id='m4-open-flow';return Boolean(e)})()`,'flow list');await click(studio,'#m4-open-flow')
 await waitFor(studio,`document.querySelectorAll('.react-flow__node').length===6`,'reopened control nodes')
 await studio.evaluate(`(()=>{const e=document.querySelector('#run-profile');e.value=${JSON.stringify(profile.id)};e.dispatchEvent(new Event('change',{bubbles:true}))})()`)

 await click(studio,'[aria-label="启动调试"] summary');await click(studio,'','开始调试')
 let run=await until(async()=>{const list=await api('workflows/runs');if(!list.items.length)return;const r=await api('workflows/runs/'+list.items[0].runId);return r.state==='paused'?r:null},'entry pause')
 assert.equal(run.executionCount,0)
 await waitFor(studio,`Boolean(document.querySelector('[aria-label="修改运行变量"]'))`,'variable editor')
 await input(studio,'[aria-label="修改运行变量"]',JSON.stringify({note:'native editor value'}));await click(studio,'','应用变量修改')
 await waitFor(studio,`document.querySelector('[aria-label="修改运行变量"]').value==='{}'`,'applied modification')
 await capture('paused');await click(studio,'','单步')
 await until(async()=>{const r=await api('workflows/runs/'+run.runId);return r.state==='paused'&&r.executionCount===1&&r.debug.pendingNodeId===loop},'single open action')
 await waitFor(studio,`document.body.innerText.includes('待执行：${loop}')`,'updated pause')
 await click(studio,'','刷新标签页');await waitFor(studio,`document.querySelector('[aria-label="调试目标页"]').options.length>1`,'browser page list')
 await click(studio,'','继续')
 run=await until(async()=>{const r=await api('workflows/runs/'+run.runId);return ['succeeded','failed'].includes(r.state)?r:null},'debug completion',60000)
 assert.equal(run.state,'succeeded',JSON.stringify(run.error));assert.equal(run.mode,'debug');assert.equal(run.artifactCount,2)
 assert.deepEqual(run.artifacts.map(a=>a.loopPath[0].iteration),[1,2]);for(const a of run.artifacts)assert.equal(await api(`workflows/runs/${run.runId}/artifacts/${a.id}`),'M3 真实框架结果')
 const checkpoint=await api(`workflows/runs/${run.runId}/debug/variables`);const full=await api(`workflows/runs/${run.runId}/artifacts/${checkpoint.checkpointId}`);assert.equal(full.variables.find(v=>v.name==='note').value,'native editor value')
 await capture('executed');passed('native Studio debug entry pause, manual variable commit, one real open action, page list, resume and loop/condition/iframe completion')
 await click(studio,'','搜索／导出');await input(studio,'[aria-label="日志关键词"]','调试')
 await waitFor(studio,`document.querySelector('[aria-label="运行日志筛选与导出"] ol')?.innerText.includes('调试')`,'persisted log search')
 await capture('diagnostics');
 const exportedPath=join(workspace,'native-export.jsonl');await native.evaluate(`globalThis.smokeElectron.dialog.showSaveDialog=async()=>({canceled:false,filePath:${JSON.stringify(exportedPath)}})`);await click(studio,'','导出筛选日志');await until(async()=>{try{return (await readFile(exportedPath,'utf8')).includes('调试')}catch{return false}},'native streamed export');
 passed('formal variable checkpoint survives completion and full-history log search uses real persisted debug events')

 await click(studio,'[aria-label="启动调试"] summary');await click(studio,'','开始调试')
 const leavingRun=await until(async()=>{const r=(await api('workflows/runs')).items.find(r=>r.state==='paused');return r},'leave protection pause')
 await input(studio,'#workflow-name','M5 暂停中的未保存修改');await click(studio,'','新建');await click(studio,'','取消');assert.equal((await api('workflows/runs/'+leavingRun.runId)).state,'paused')
 // Real competing revision causes save failure before the browser may be stopped.
 const latest=await api('workflows/'+summary.id);await api('workflows/'+summary.id,{method:'PUT',body:JSON.stringify({document:latest.document,layout:latest.layout,expectedRevision:latest.revision})})
 await click(studio,'','新建');await click(studio,'','保存并停止');await waitFor(studio,`document.querySelector('[role=dialog] [role=alert]')?.textContent.length>0`,'save conflict protects pause');assert.equal((await api('workflows/runs/'+leavingRun.runId)).state,'paused')
 await click(studio,'','取消');await click(studio,'','新建');await click(studio,'','放弃并停止');await waitFor(studio,`document.querySelectorAll('.react-flow__node').length===0`,'cleanup before new document');assert.equal((await api('workflows/runs/'+leavingRun.runId)).state,'cancelled')
 passed('paused debug leave protection: cancel and real save conflict retain browser; discard waits for cleanup before creating next document')
} catch(error) {if(studio){await capture('failure').catch(()=>{});console.error(await studio.evaluate('document.body.innerText').catch(()=>''));console.error(JSON.stringify(await studio.evaluate(`({nodes:[...document.querySelectorAll('.react-flow__node')].map(e=>({id:e.dataset.id,style:e.getAttribute('style'),html:e.innerHTML.slice(0,400)})),viewport:document.querySelector('.react-flow__viewport')?.getAttribute('style')})`).catch(()=>null)))}throw error}
finally {
 studio?.close();native?.close();desktop?.cdp?.close();await stop(desktop?.child).catch(()=>{});await devServer?.close();server.closeAllConnections();await new Promise(r=>server.close(r))
 await writeFile(join(qa,`${mode}-studio.json`),JSON.stringify({platform:process.platform,arch:process.arch,mode,kernelVersion:kernel.version,checks,complete:checks.length===4},null,2))
 await rm(workspace,{recursive:true,force:true});await rm(target,{recursive:true,force:true})
}
