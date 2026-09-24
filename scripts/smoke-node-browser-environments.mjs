import assert from 'node:assert/strict'
import {execFileSync} from 'node:child_process'
import {randomUUID} from 'node:crypto'
import {mkdir,mkdtemp,writeFile} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {basename,join,resolve} from 'node:path'
import {connectCdp,launchElectron,wait,waitFor,clickElement} from './electron-cdp.mjs'
import {stop} from './smoke-sidecar.mjs'
const root=resolve(import.meta.dirname,'..')
const kernel=process.env.AUTOFLOW_B1_KERNEL_DIR
if(!kernel)throw new Error('Set AUTOFLOW_B1_KERNEL_DIR to an installed kernel directory')
const version=basename(kernel).replace(/^chromium-/,'')
const evidence=resolve(process.env.AUTOFLOW_QA_OUTPUT??'artifacts/node-browser-environments')
const workspace=await mkdtemp(join(tmpdir(),'autoflow-node-browser-'))
await mkdir(evidence,{recursive:true})
await mkdir(join(workspace,'data/kernels'),{recursive:true})
await writeFile(join(workspace,'.autoflow-workspace.json'),JSON.stringify({schemaVersion:1,kind:'autoflow-workspace'}))
// macOS clone copies keep the installed browser executable and isolate all writable data.
execFileSync('cp',['-cR',kernel,join(workspace,'data/kernels',basename(kernel))])
let desktop,main,studio,runtime
const checks=[]
async function api(path,body,method=body===undefined?'GET':'POST'){
 const response=await fetch(`${runtime.sidecar.baseUrl}/api${path}`,{method,headers:{'x-autoflow-token':runtime.sidecar.token,'content-type':'application/json','Idempotency-Key':randomUUID()},body:body===undefined?undefined:JSON.stringify(body)})
 if(!response.ok)throw new Error(`${method} ${path}: ${response.status} ${await response.text()}`)
 return response.status===204?null:response.json()
}
async function click(cdp,selector,text){await clickElement(cdp,text??'',selector);await wait(150)}
async function poll(read,name){const end=Date.now()+30000;while(Date.now()<end){const value=await read();if(value)return value;await wait(150)}throw new Error(`Timeout ${name}`)}
async function capture(cdp,name){const {data}=await cdp.command('Page.captureScreenshot',{format:'png'});await writeFile(join(evidence,name+'.png'),Buffer.from(data,'base64'))}
try{
 desktop=await launchElectron(root,{launchArgs:[`--user-data-dir=${workspace}`],cliArgs:[]});main=desktop.cdp
 await main.command('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false})
 await waitFor(main,"document.body?.innerText.includes('本地服务正常')",'sidecar ready',30000)
 runtime=await main.evaluate('window.autoflow.getRuntimeContext()')
 const profile=await api('/v1/profiles',{name:'节点验收模板',browserVersion:version,browserEdition:'public',headless:true,proxyMode:'none'})
 const project=await api('/v1/projects',{name:'节点环境隔离验收'})
 const document=await api('/workflows',{id:randomUUID(),clientRequestId:randomUUID(),name:'节点环境验收',schemaVersion:3,browserEnvironmentVersion:1,variables:[],nodes:[{id:'open',type:'open_page',position:{x:100,y:100},data:{moduleType:'open_page',label:'初始化实例',url:'about:blank',browserEnvironment:{source:'newFromProfile'}}}],edges:[]})
 await api(`/v1/projects/${project.projectId}/automations`,{name:'节点自动化',description:'',workflowId:document.id,inputPlan:{inputs:[]},parameterSchema:[],environmentPolicy:{source:'newFromProfile',profileId:profile.id,proxyOverride:{mode:'none'},modelProviderId:null},runPolicy:{maxTasks:1,concurrency:1,maxLiveInstances:1,continueAfterFailure:false,automaticExecutionTimeoutSeconds:120,manualDeadlineSeconds:300}})
 await main.evaluate(`location.hash=${JSON.stringify(`#/projects/${project.projectId}/environments`)}`)
 await waitFor(main,"document.body.innerText.includes('新建环境默认设置')",'environment defaults')
 await click(main,'button','新建环境默认设置')
 await waitFor(main,"Boolean(document.querySelector('[aria-label=\"默认浏览器模板\"]') || document.querySelector('form'))",'defaults controls')
 assert.equal(await main.evaluate("Boolean(document.querySelector('aside'))"),false)
 await click(main,'[aria-label="默认浏览器模板"]');await click(main,'[role=option]','节点验收模板')
 await click(main,'button','保存默认设置')
 await poll(async()=> (await api(`/v1/projects/${project.projectId}`)).defaultResources.profileId===profile.id,'saved project default')
 await capture(main,'project-environment-defaults');checks.push('Environment page has editable defaults and no sidebar cards')
 await main.evaluate(`window.autoflow.openAutomationStudio(${JSON.stringify({projectId:project.projectId,workflowId:document.id})})`)
 const target=await poll(async()=> (await (await fetch(desktop.debugOrigin+'/json/list')).json()).find(t=>t.type==='page'&&t.url.includes('view=automation-studio')),'Studio window')
 studio=await connectCdp(target.webSocketDebuggerUrl)
 await studio.command('Emulation.setDeviceMetricsOverride',{width:1600,height:1100,deviceScaleFactor:1,mobile:false})
 await waitFor(studio,"Boolean(document.querySelector('.react-flow__node[data-id=\"open\"]'))",'document load',30000)
 assert.equal(await studio.evaluate("Boolean(document.querySelector('[aria-label=\"运行浏览器配置\"]'))"),false)
 await click(studio,'.react-flow__node[data-id="open"]')
 await waitFor(studio,"Boolean(document.querySelector('#node-browser-template'))",'node configuration')
 await click(studio,'#node-browser-template');await click(studio,'[role=option]','节点验收模板')
 await click(studio,'#node-browser-proxy');await click(studio,'[role=option]','不使用代理')
 await click(studio,'#node-browser-kernel');await click(studio,'[role=option]',`公开版 ${version}`)
 await capture(studio,'open-page-environment-fields')
 await click(studio,'button','保存')
 const saved=await poll(async()=>{const d=await api('/workflows/'+document.id);return d.nodes[0].data.browserEnvironment.profileId===profile.id?d:null},'saved node configuration')
 assert.deepEqual(saved.nodes[0].data.browserEnvironment,{source:'newFromProfile',profileId:profile.id,proxy:{mode:'none'},kernel:{edition:'public',version}})
 assert.equal(saved.browserEnvironmentVersion,1)
 checks.push('Node template/proxy/kernel configured in actual Studio UI and persisted by production HTTP')
 await click(studio,'[aria-label="运行 (F5)"]');await click(studio,'[role=menuitem]','无头运行')
 const run=await poll(async()=>{const page=await api(`/workflow-runs?documentId=${document.id}&projectId=${project.projectId}`);const run=page.items[0];if(!run)return null;const detail=await api(`/workflow-runs/${run.runId}?projectId=${project.projectId}`);return ['completed','failed','stopped','interrupted'].includes(detail.status)?detail:null},'real worker terminal')
 assert.equal(run.status,'completed',JSON.stringify(run))
 const after=await api('/v1/profiles/'+profile.id)
 assert.equal(after.browserVersion,version);assert.equal(after.proxyMode,'none')
 checks.push('UI run completes through real sidecar and worker without global profile; template unchanged')
 await capture(studio,'node-browser-run-completed')
 await writeFile(join(evidence,'result.json'),JSON.stringify({status:'passed',date:new Date().toISOString(),checks,runId:run.runId,workspace,platform:process.platform,arch:process.arch,kernelVersion:version,limits:['source build; no signing/notarization or Windows/Intel physical-device proof']},null,2))
 console.log(JSON.stringify({status:'passed',checks,evidence}))
}catch(error){if(studio)await capture(studio,'failure-studio').catch(()=>{});if(main)await capture(main,'failure-main').catch(()=>{});throw error}
finally{studio?.close();main?.close();if(desktop)await stop(desktop.child)}
