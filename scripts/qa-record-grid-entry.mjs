import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { mkdtemp, mkdir, writeFile, readFile, realpath, readdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { execFileSync } from 'node:child_process'
import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'
import { cleanupGridWorkspace } from './qa-record-grid-files.mjs'
if (process.argv.includes('--cleanup')) {
 const target=process.argv[process.argv.indexOf('--cleanup')+1]
 if(!target) throw new Error('请提供本工具创建的测试工作区路径')
 console.log('已清理测试工作区；证据保留于',await cleanupGridWorkspace(target));process.exit(0)
}
const root=resolve(import.meta.dirname,'..'), manual=process.argv.includes('--manual')
const output=join(root,'docs/project-management/design-alignment/acceptance/record-grid-entry/runs')
await mkdir(output,{recursive:true})
const evidence=await mkdtemp(join(output,'run-')), workspace=await realpath(await mkdtemp(join(tmpdir(),'autoflow-grid-qa-')))
await writeFile(join(workspace,'.autoflow-workspace.json'),JSON.stringify({schemaVersion:1,kind:'autoflow-workspace'}))
await writeFile(join(workspace,'.grid-qa.json'),JSON.stringify({kind:'autoflow-grid-qa',version:1,evidence}))
const report={started:new Date().toISOString(),workspace,evidence,source:execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim(),patchSha256:createHash('sha256').update(execFileSync('git',['diff'],{cwd:root})).digest('hex'),platform:process.platform,arch:process.arch,cases:[],windows:'notRun',packaging:'notRun'}
const tracked=execFileSync('git',['ls-files','-z','--cached','--others','--exclude-standard','--','apps/backend/src','apps/desktop/src','scripts'],{cwd:root,encoding:'utf8'}).split('\0').filter(Boolean).sort()
report.sourceContentSha256=createHash('sha256').update(JSON.stringify(await Promise.all(tracked.map(async path=>[path,createHash('sha256').update(await readFile(join(root,path))).digest('hex')])))).digest('hex')
async function builtFiles(path){const result=[];for(const entry of await readdir(path,{withFileTypes:true})){const next=join(path,entry.name);if(entry.isDirectory())result.push(...await builtFiles(next));else result.push([next.replace(root,''),createHash('sha256').update(await readFile(next)).digest('hex')])}return result.sort((a,b)=>a[0].localeCompare(b[0]))}
report.buildContentSha256=createHash('sha256').update(JSON.stringify(await builtFiles(join(root,'apps/desktop/out')))).digest('hex')
let desktop,renderer,native
const visible=(text)=>waitFor(renderer,`document.body?.innerText.includes(${JSON.stringify(text)})`,text)
async function target(selector, text){return waitFor(renderer,`(()=>{const list=[...document.querySelectorAll(${JSON.stringify(selector)})];const e=list.find(e=>e.getClientRects().length&&!e.disabled&&(${text===undefined?'true':`e.textContent.trim()===${JSON.stringify(text)}||e.getAttribute('aria-label')===${JSON.stringify(text)}`}));if(!e)return null;e.scrollIntoView({block:'center',inline:'center',behavior:'instant'});const r=e.getBoundingClientRect();const x=r.x+r.width/2,y=r.y+r.height/2;if(!e.contains(document.elementFromPoint(x,y)))return null;return{x,y}})()`,text??selector)}
async function click(text,selector='button',twice=false){const point=await target(selector,text);for(let i=1;i<=(twice?2:1);i++){await renderer.command('Input.dispatchMouseEvent',{type:'mousePressed',...point,button:'left',clickCount:i});await renderer.command('Input.dispatchMouseEvent',{type:'mouseReleased',...point,button:'left',clickCount:i})}await wait(80)}
async function input(selector,text){const p=await target(selector);await renderer.command('Input.dispatchMouseEvent',{type:'mousePressed',...p,button:'left',clickCount:1});await renderer.command('Input.dispatchMouseEvent',{type:'mouseReleased',...p,button:'left',clickCount:1});await key('a',process.platform==='darwin'?4:2);await renderer.command('Input.insertText',{text})}
async function key(key,modifiers=0){const code=key.length===1?`Key${key.toUpperCase()}`:key;const vk=key.length===1?key.toUpperCase().charCodeAt(0):({Enter:13,Tab:9,Escape:27}[key]);await renderer.command('Input.dispatchKeyEvent',{type:'keyDown',key,code,windowsVirtualKeyCode:vk,modifiers,...(key==='v'&&modifiers?{commands:['paste']}: key==='a'&&modifiers?{commands:['selectAll']}: {})});await renderer.command('Input.dispatchKeyEvent',{type:'keyUp',key,code,windowsVirtualKeyCode:vk,modifiers});await wait(80)}
async function capture(name){report.screenshots??=[];report.screenshots.push({name,viewport:await renderer.evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio,scrollY,font:getComputedStyle(document.body).fontFamily})'),source:name==='V01-two-drafts'?'CDP 1487x1058 baseline':'native Electron viewport',zoom:await native.evaluate('gridElectron.BrowserWindow.getAllWindows()[0].webContents.getZoomFactor()')});const {data}=await renderer.command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(join(evidence,`${name}.png`),data,'base64')}
async function select(label,option){await click(undefined,`[role=combobox][aria-label="${label}"]`);const text=await waitFor(renderer,`[...document.querySelectorAll('[role=option]')].find(e=>e.getClientRects().length&&e.textContent.trim().startsWith(${JSON.stringify(option)}))?.textContent.trim()`,'option '+option);await click(text,'[role=option]')}
function passed(id,details){report.cases.push({id,status:'passed',details,evidenceType:'Electron UI + real FastAPI + isolated SQLite'});console.log(`${id}: ${details}`)}
async function facts(path){const {sidecar}=await renderer.evaluate('window.autoflow.getRuntimeContext()');const r=await fetch(`${sidecar.baseUrl}/api/v1${path}`,{headers:{'x-autoflow-token':sidecar.token}});assert.equal(r.status,200);return r.json()}
async function launch(){desktop=await launchElectron(root,{launchArgs:[`--user-data-dir=${workspace}`,'--inspect=0'],cliArgs:[]});renderer=desktop.cdp;native=await connectCdp(desktop.inspectorUrl);await native.evaluate("globalThis.gridElectron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');gridElectron.BrowserWindow.getAllWindows()[0].setContentSize(1487,1058);true");await visible('本地服务正常')}
try{
 await launch();await click('项目');await click('新建项目');await input('#project-name','行内录入验收');await click('创建项目');await waitFor(renderer,"location.hash.includes('/overview')",'project overview');await wait(350);await click('数据');await wait(350);await click('新建数据表');await input('#data-table-name','资料库');await click('创建数据表');await visible('资料库')
 const project=(await facts('/projects')).items.find(p=>p.name==='行内录入验收');assert.ok(project)
 const table=(await facts(`/projects/${project.projectId}/tables`)).items.find(t=>t.name==='资料库');assert.ok(table)
 if(!await renderer.evaluate("Boolean(document.querySelector('[role=tab]'))")) await click('打开数据表：资料库','button');await wait(250);await click('字段与校验','[role=tab]')
 for(const [name,keyName] of [['标题','title'],['文章链接','url'],['摘要','summary']]){
  await click('新增字段');await input('#field-name',name);await input('#field-key',keyName)
  if(name==='标题')await click('必填','[role=switch]')
  await click('应用到草稿');await waitFor(renderer,"!document.querySelector('#schema-field-drawer-form')",'field draft applied')
 }
 await click('保存字段');await visible('保存字段前核对影响');await click('确认保存字段');await waitFor(renderer,"!document.querySelector('[role=dialog]')",'schema saved');
 await click('数据记录','[role=tab]');await click('新增行');assert.equal(await renderer.evaluate("Boolean(document.querySelector('[role=dialog]'))"),false)
 await click('第 1 行 · 标题','[role=gridcell]',true);await renderer.command('Input.insertText',{text:'温室光照管理笔记'});await key('Tab');await click('第 1 行 · 文章链接','[role=gridcell]',true);await renderer.command('Input.insertText',{text:'https://example.com/notes/001'});await key('Tab');await key('Enter')
 await click('第 2 行 · 标题','[role=gridcell]',true);await renderer.command('Input.insertText',{text:'阳台种植观察'});await key('Escape')
 // Escape retracts only the active edit, then re-enter the intended value.
 await click('第 2 行 · 标题','[role=gridcell]',true);await renderer.command('Input.insertText',{text:'阳台种植观察'});await key('Tab');await wait(2800);await renderer.command('Emulation.setDeviceMetricsOverride',{width:1487,height:1058,deviceScaleFactor:1,mobile:false});await renderer.evaluate("window.scrollTo({top:0,behavior:'instant'})");await capture('V01-two-drafts');await renderer.command('Emulation.clearDeviceMetricsOverride')
 assert.equal(await renderer.evaluate("document.querySelector('[data-record-action=create]').textContent.includes('新增行')"),true)
 const before=await facts(`/projects/${project.projectId}/tables/${table.tableId}/records?datasetGeneration=${table.datasetGeneration}`);assert.equal(before.total,0)
 await click('保存 2 行');await waitFor(renderer,"!document.querySelector('[data-record-draft]')",'batch saved')
 const records=await facts(`/projects/${project.projectId}/tables/${table.tableId}/records?datasetGeneration=${table.datasetGeneration}`);assert.equal(records.total,2);assert.ok(records.items.every(r=>r.statusId===null));await capture('V03-saved');passed('E01-E03','UI created project/table/fields and two inline rows; one visible batch save produced exactly two records')
 await click('新增行');await click('第 1 行 · 标题','[role=gridcell]')
 await native.evaluate("gridElectron.clipboard.writeText('001\\thttps://example.com/a\\t温室\\n002\\thttps://example.com/b\\t阳台');true")
 await key('v',process.platform==='darwin'?4:2);await visible('保存 2 行');await capture('V04-paste');await click('保存 2 行');await waitFor(renderer,"!document.querySelector('[data-record-draft]')",'pasted records saved')
 const after=await facts(`/projects/${project.projectId}/tables/${table.tableId}/records?datasetGeneration=${table.datasetGeneration}`);assert.equal(after.total,4);assert.ok(after.items.some(r=>r.values.some(v=>v.value==='001')));passed('E04','Real clipboard paste preserves leading-zero text and adds exactly two rows')
 await click('新增行');await click('第 1 行 · 摘要','[role=gridcell]',true);await renderer.command('Input.insertText',{text:'必填尚未填写'});await click('保存 1 行');await visible('请填写必填字段');await capture('V06-cell-error');assert.equal((await facts(`/projects/${project.projectId}/tables/${table.tableId}/records?datasetGeneration=${table.datasetGeneration}`)).total,4);passed('E06','Invalid required cell is focused and no records are written')
 await click('字段与校验','[role=tab]');await click('继续录入');assert.equal(await renderer.evaluate("Boolean(document.querySelector('[data-record-draft]'))"),true);passed('E11','Cancelled tab leave preserves grid draft')
 await capture('V09-retained-draft')

 // Invalid rectangular paste is rejected as a whole, including the original draft.
 await click('第 1 行 · 标题','[role=gridcell]');
 await native.evaluate("gridElectron.clipboard.writeText('a\\tb\\tc\\td');true");await key('v',process.platform==='darwin'?4:2)
 assert.equal(await renderer.evaluate("document.querySelectorAll('[data-record-draft]').length"),1)
 assert.equal(await renderer.evaluate("document.body.innerText.includes('必填尚未填写')"),true)
 for(const value of [Array.from({length:101},()=> '越限').join('\n'),'界'.repeat(350000)]) {
  await native.evaluate(`gridElectron.clipboard.writeText(${JSON.stringify(value)});true`);await key('v',process.platform==='darwin'?4:2)
  assert.equal(await renderer.evaluate("document.querySelectorAll('[data-record-draft]').length"),1)
 }
 await capture('V05-paste-rejected');passed('E05','Over-wide, over-100-row and over-1-MiB clipboard pastes leave original draft unchanged')
 await click('第 1 行 · 标题','[role=gridcell]',true);await renderer.command('Input.insertText',{text:'响应丢失验收'});await key('Tab')
 const recordRoute=await renderer.evaluate('location.hash')
 let lostResponses=0
 const intercept=event=>{const data=JSON.parse(event.data);if(data.method==='Fetch.requestPaused'){lostResponses++;void renderer.command('Fetch.failRequest',{requestId:data.params.requestId,errorReason:'Failed'})}}
 renderer.socket.addEventListener('message',intercept)
 await renderer.command('Fetch.enable',{patterns:[{urlPattern:'*/records/batch',requestStage:'Response'},{urlPattern:'*/operations/by-idempotency-key/*',requestStage:'Response'}]})
 await click('保存 1 行');await visible('查询保存结果');await capture('V08-uncertain')
 assert.equal((await facts(`/projects/${project.projectId}/tables/${table.tableId}/records?datasetGeneration=${table.datasetGeneration}`)).total,5)
 assert.ok(lostResponses>0)
 await renderer.command('Fetch.disable');renderer.socket.removeEventListener('message',intercept)
 renderer.close();native.close();await stop(desktop.child);await launch()
 // Direct route is explicitly recorded; this restart step tests persistence, not navigation.
 await renderer.evaluate(`location.hash=${JSON.stringify(recordRoute)}`);await visible('查询保存结果')
 await click('查询保存结果');await waitFor(renderer,"!document.querySelector('[data-record-draft]')",'recovered committed batch')
 assert.equal((await facts(`/projects/${project.projectId}/tables/${table.tableId}/records?datasetGeneration=${table.datasetGeneration}`)).total,5)
 passed('E09','Injected response loss after database commit; full Electron restart and original-key query recovered exactly one addition; restart route restored directly')
 await capture('V10-recovered')
 await click('新增行');await click('第 1 行 · 标题','[role=gridcell]',true);await renderer.command('Input.insertText',{text:'服务重连草稿'});await key('Tab')
 await renderer.evaluate('window.autoflow.restartSidecar()');await visible('本地服务正常');await wait(700)
 assert.equal(await renderer.evaluate("document.body.innerText.includes('服务重连草稿')"),true)
 passed('E12-service-reconnect','Existing controlled restartSidecar IPC restarts test service; same-workspace grid draft survives')
 await native.evaluate('gridElectron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(2);true');await wait(200)
 await renderer.evaluate("document.querySelector('[data-record-draft]').scrollIntoView({block:'center',behavior:'instant'})");await capture('V11-zoom-200')
 assert.ok(await renderer.evaluate("(()=>{const r=document.querySelector('footer[aria-label=\"新增记录保存\"]').getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight+1})()"))
 assert.ok(await renderer.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
 await key('Tab');await key('Escape');
 await native.evaluate('gridElectron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(1);true');await wait(200)
 await capture('V12-normal');passed('E15','Actual Electron 200% zoom preserves window width and draft; screenshot captured')
 await click('放弃新增');await click('放弃新增','[role=alertdialog] button');await waitFor(renderer,"!document.querySelector('[data-record-draft]')",'discarded draft')
 await renderer.evaluate(`(()=>{const original=window.fetch.bind(window);window.__gridEditRequests=[];window.fetch=async(...args)=>{const response=await original(...args);if(String(args[0]).includes('/records/'))window.__gridEditRequests.push({url:String(args[0]),method:args[1]?.method,result:await response.clone().json()});return response};return true})()`);
 await click('编辑');await visible('保存修改');await input('[aria-label="标题"]','已有记录仍可编辑');await click('保存修改');await visible('业务字段');await wait(1500);await writeFile(join(evidence,'edit-responses.json'),JSON.stringify(await renderer.evaluate('window.__gridEditRequests'),null,2));await visible('已有记录仍可编辑');await click('返回记录列表');await waitFor(renderer,"Boolean(document.querySelector('[data-record-action=create]'))",'returned record table');await visible('已有记录仍可编辑');passed('E16-edit','Saved record edit still uses existing detail/edit flow and persists through UI')
 await capture('V13-existing-edit')

 // A request blocked before reaching HTTP remains uncertain until a trusted not-found query.
 await click('新增行');await click('第 1 行 · 标题','[role=gridcell]',true);await renderer.command('Input.insertText',{text:'尚未接受原请求'});await key('Tab')
 const blockRequest=event=>{const data=JSON.parse(event.data);if(data.method==='Fetch.requestPaused')void renderer.command('Fetch.failRequest',{requestId:data.params.requestId,errorReason:'Failed'})}
 renderer.socket.addEventListener('message',blockRequest)
 await renderer.command('Fetch.enable',{patterns:[{urlPattern:'*/records/batch',requestStage:'Request'},{urlPattern:'*/operations/by-idempotency-key/*',requestStage:'Response'}]})
 await click('保存 1 行');await visible('查询保存结果')
 assert.equal((await facts(`/projects/${project.projectId}/tables/${table.tableId}/records?datasetGeneration=${table.datasetGeneration}`)).total,5)
 await renderer.command('Fetch.disable');renderer.socket.removeEventListener('message',blockRequest)
 await click('查询保存结果');await visible('重发原请求');await capture('V08-not-accepted');await click('重发原请求');await waitFor(renderer,"!document.querySelector('[data-record-draft]')",'original request resubmitted')
 assert.equal((await facts(`/projects/${project.projectId}/tables/${table.tableId}/records?datasetGeneration=${table.datasetGeneration}`)).total,6)
 passed('E10','Request-stage fault injection writes nothing; explicit original-key lookup and resend create one record')
 // A real competing schema write, never direct database mutation.
 await click('新增行');await click('第 1 行 · 标题','[role=gridcell]',true);await renderer.command('Input.insertText',{text:'结构冲突草稿'});await key('Tab')
 const currentTable=await facts(`/projects/${project.projectId}/tables/${table.tableId}`)
 const {sidecar}=await renderer.evaluate('window.autoflow.getRuntimeContext()')
 const mutation=await fetch(`${sidecar.baseUrl}/api/v1/projects/${project.projectId}/tables/${table.tableId}/fields`,{method:'POST',headers:{'content-type':'application/json','x-autoflow-token':sidecar.token,'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({expectedTableRevision:currentTable.tableRevision,definition:{key:'competition',name:'竞争新增字段',type:'string',required:false,validation:{}},sourceColumnPolicy:'localOnly'})})
 assert.equal(mutation.status,200)
 await click('保存 1 行');await visible('确认最新字段并继续');await capture('V07-schema-conflict')
 assert.equal((await facts(`/projects/${project.projectId}/tables/${table.tableId}/records?datasetGeneration=${table.datasetGeneration}`)).total,6)
 await click('确认最新字段并继续');await click('保存 1 行');await waitFor(renderer,"!document.querySelector('[data-record-draft]')",'confirmed current schema saved')
 assert.equal((await facts(`/projects/${project.projectId}/tables/${table.tableId}/records?datasetGeneration=${table.datasetGeneration}`)).total,7)
 passed('E08','Real competing HTTP field creation rejects stale structure, preserves cells, then explicit confirmation permits one save')

 await input('[aria-label="文本搜索"]','温室');await click('搜索记录');await wait(400)
 const filteredBefore=await renderer.evaluate("document.querySelector('[role=group][aria-label=记录工具]').innerText")
 await click('新增行');await click('第 1 行 · 标题','[role=gridcell]',true);await renderer.command('Input.insertText',{text:'不匹配搜索的记录'});await key('Tab');await click('保存 1 行');await waitFor(renderer,"!document.querySelector('[data-record-draft]')",'save under active filter');await wait(400)
 assert.equal(await renderer.evaluate("document.querySelector('[aria-label=文本搜索]').value"),'温室')
 assert.equal(await renderer.evaluate("document.querySelector('[role=group][aria-label=记录工具]').innerText"),filteredBefore)
 assert.equal((await facts(`/projects/${project.projectId}/tables/${table.tableId}/records?datasetGeneration=${table.datasetGeneration}`)).total,8)
 await capture('V14-filter-retained');passed('E14-list','Nonmatching row is saved, applied search and visible count stay unchanged')
 await click('清除文本搜索')

 // Business identity setup travels through the real Excel wizard, with only the native picker result injected.
 const identityFile=join(workspace,'identity.xlsx')
 execFileSync('uv',['run','--directory',join(root,'apps/backend'),'python','-c',`from openpyxl import Workbook; b=Workbook(); s=b.active; s.title='客户'; s.append(['编号','备注']); s.append(['001','已有记录']); b.save(${JSON.stringify(identityFile)})`],{cwd:root})
 const sourceHash=createHash('sha256').update(await readFile(identityFile)).digest('hex')
 await native.evaluate(`gridElectron.dialog.showOpenDialog=async()=>({canceled:false,filePaths:[${JSON.stringify(identityFile)}]});true`)
 await click('数据');await click('从 Excel 导入');await click('选择 Excel 文件');await click('检查文件');await select('工作表','客户');await click('继续字段映射');await select('记录身份','编号（候选）');await click('继续导入');await input('[aria-label="数据表名称"]','文本身份验收');await click('确认并开始导入');await waitFor(renderer,"!document.querySelector('[role=dialog]')",'identity import complete',30000)
 const identityTable=(await facts(`/projects/${project.projectId}/tables`)).items.find(t=>t.name==='文本身份验收');assert.ok(identityTable)
 await click('打开数据表：文本身份验收');await click('新增行');await click('第 1 行 · 编号','[role=gridcell]');await native.evaluate("gridElectron.clipboard.writeText('002\\t新记录一\\n002\\t新记录二');true");await key('v',process.platform==='darwin'?4:2);await click('保存 2 行');await visible('记录身份已存在');await capture('V06-duplicate-identity')
 assert.equal((await facts(`/projects/${project.projectId}/tables/${identityTable.tableId}/records?datasetGeneration=${identityTable.datasetGeneration}`)).total,1)
 await click('第 2 行 · 编号','[role=gridcell]',true);await input('textarea[aria-label="第 2 行 · 编号"]','003');await key('Tab');await click('保存 2 行');await waitFor(renderer,"!document.querySelector('[data-record-draft]')",'unique identity batch saved')
 assert.equal((await facts(`/projects/${project.projectId}/tables/${identityTable.tableId}/records?datasetGeneration=${identityTable.datasetGeneration}`)).total,3)
 await click('新增行');await click('第 1 行 · 编号','[role=gridcell]');await native.evaluate("gridElectron.clipboard.writeText('001\\t与已有身份冲突\\n004\\t不可部分写入');true");await key('v',process.platform==='darwin'?4:2);await click('保存 2 行');await visible('记录身份已存在')
 assert.equal((await facts(`/projects/${project.projectId}/tables/${identityTable.tableId}/records?datasetGeneration=${identityTable.datasetGeneration}`)).total,3)
 assert.equal(createHash('sha256').update(await readFile(identityFile)).digest('hex'),sourceHash)
 passed('E07','Real Excel identity table via wizard; duplicate batch and existing identity each reject every draft, unique batch succeeds, source bytes unchanged')
 await click('放弃新增');await click('放弃新增','[role=alertdialog] button')

 const extra=[]
 for(const [keyName,name,type] of [['date','日期','date'],['number','数量','number'],['boolean','启用','boolean']]) {
  const tableView=await facts(`/projects/${project.projectId}/tables/${identityTable.tableId}`), runtime=await renderer.evaluate('window.autoflow.getRuntimeContext()')
  const response=await fetch(`${runtime.sidecar.baseUrl}/api/v1/projects/${project.projectId}/tables/${identityTable.tableId}/fields`,{method:'POST',headers:{'content-type':'application/json','x-autoflow-token':runtime.sidecar.token,'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({expectedTableRevision:tableView.tableRevision,definition:{key:keyName,name,type,required:false,validation:{}},sourceColumnPolicy:'localOnly'})})
  assert.equal(response.status,200);extra.push((await response.json()).field)
 }
 await renderer.command('Page.reload');await visible('文本身份验收');await visible('启用');await click('新增行');await click('第 1 行 · 编号','[role=gridcell]')
 const rich='007\t"温室\n换行"\t2026-09-14\t0\tfalse\n008\t=1+1\t2026-09-14\t0\tfalse'
 await native.evaluate(`gridElectron.clipboard.writeText(${JSON.stringify(rich)});true`);await key('v',process.platform==='darwin'?4:2);await visible('保存 2 行');await key('z',process.platform==='darwin'?4:2)
 assert.equal(await renderer.evaluate("document.querySelectorAll('[data-record-draft]').length"),1)
 await key('v',process.platform==='darwin'?4:2);await visible('保存 2 行');await capture('V04-rich-paste');await click('保存 2 行');await waitFor(renderer,"!document.querySelector('[data-record-draft]')",'rich typed rows saved')
 const typed=(await facts(`/projects/${project.projectId}/tables/${identityTable.tableId}/records?datasetGeneration=${identityTable.datasetGeneration}`)).items.filter(r=>['007','008'].includes(r.ref.recordKey.value))
 assert.equal(typed.length,2)
 for(const record of typed){const values=new Map(record.values.map(v=>[v.fieldId,v.value]));assert.equal(values.get(extra[1].ref.fieldId),0);assert.equal(values.get(extra[2].ref.fieldId),false);assert.equal(values.get(extra[0].ref.fieldId).value,'2026-09-14')}
 assert.ok(typed.some(r=>r.values.some(v=>v.value==='温室\n换行')));assert.ok(typed.some(r=>r.values.some(v=>v.value==='=1+1')))
 passed('E04-rich-types','HTTP fixture fields plus real clipboard paste/undo/save preserve date, zero, false, quoted newline and formula-looking text')

 // Two real workspace folders. Selection/confirmation uses the existing controlled IPC, explicitly not UI clicks.
 const secondaryWorkspace=await realpath(await mkdtemp(join(tmpdir(),'autoflow-grid-qa-')))
 report.secondaryWorkspace=secondaryWorkspace
 await writeFile(join(secondaryWorkspace,'.autoflow-workspace.json'),JSON.stringify({schemaVersion:1,kind:'autoflow-workspace'}));await writeFile(join(secondaryWorkspace,'.grid-qa.json'),JSON.stringify({kind:'autoflow-grid-qa',version:1,evidence}))
 await click('新增行');await click('第 1 行 · 编号','[role=gridcell]',true);await renderer.command('Input.insertText',{text:'A未保存'});await key('Tab');const aRoute=await renderer.evaluate('location.hash')
 await native.evaluate(`gridElectron.dialog.showOpenDialog=async()=>({canceled:false,filePaths:[${JSON.stringify(secondaryWorkspace)}]});true`)
 async function switchFolder(source,expected){await renderer.evaluate(`(async()=>{const c=await window.autoflow.chooseWorkspace(${JSON.stringify(source)});if(!c.ok||!c.value)throw Error('没有选择');const r=await window.autoflow.confirmWorkspace(c.value.id);if(!r.ok)throw Error(r.error.message);return true})()`);await waitFor(renderer,`(async()=>{const r=await window.autoflow.getRuntimeContext();return r.workspaceKey===${JSON.stringify(expected)}&&r.sidecar.state==='ready'})()`,'workspace ready',30000);await visible('本地服务正常');await wait(350)}
 await switchFolder('choose',secondaryWorkspace);assert.equal((await facts('/projects')).total,0)
 await click('项目');await click('新建项目');await input('#project-name','B 独立项目');await click('创建项目');await waitFor(renderer,"location.hash.includes('/overview')",'B overview');await wait(350);await click('数据');await click('新建数据表');await input('#data-table-name','B 独立表');await click('创建数据表');await visible('B 独立表');await click('字段与校验','[role=tab]');await click('新增字段');await input('#field-name','标题');await input('#field-key','title');await click('应用到草稿');await waitFor(renderer,"!document.querySelector('#schema-field-drawer-form')",'B field draft applied');await click('保存字段');await visible('保存字段前核对影响');await click('确认保存字段');await waitFor(renderer,"!document.querySelector('[role=dialog]')",'B field created');await click('数据记录','[role=tab]');await click('新增行');await click('第 1 行 · 标题','[role=gridcell]',true);await renderer.command('Input.insertText',{text:'B 未保存的草稿'});await key('Tab');const bRoute=await renderer.evaluate('location.hash')
 await switchFolder('previous',workspace);await renderer.evaluate(`location.hash=${JSON.stringify(aRoute)}`);await visible('A未保存');assert.equal(await renderer.evaluate("document.body.innerText.includes('B 未保存的草稿')"),false);await capture('V10-workspace-a')
 await switchFolder('previous',secondaryWorkspace);await renderer.evaluate(`location.hash=${JSON.stringify(bRoute)}`);await visible('B 未保存的草稿');assert.equal(await renderer.evaluate("document.body.innerText.includes('A未保存')"),false);await capture('V10-workspace-b')
 await switchFolder('previous',workspace);await renderer.evaluate(`location.hash=${JSON.stringify(aRoute)}`);await visible('A未保存')
 passed('E12-workspace-switch','Two real workspaces and two UI-created drafts stay isolated; controlled chooser IPC and direct route restoration explicitly used')

 const retainedRoute=await renderer.evaluate('location.hash')
 await click('浏览器配置');await click('继续录入');assert.equal(await renderer.evaluate('location.hash'),retainedRoute);await visible('A未保存')
 await renderer.evaluate('history.back()');await visible('离开当前新增记录');await click('继续录入');await wait(250);assert.equal(await renderer.evaluate('location.hash'),retainedRoute);await visible('A未保存')
 await click('浏览器配置');await click('保留草稿并离开');await waitFor(renderer,"location.hash==='#/profiles'",'global navigation confirmed')
 await renderer.evaluate(`location.hash=${JSON.stringify(retainedRoute)}`);await visible('A未保存');await capture('V09-global-return')
 passed('E11-history','Global navigation and browser-back cancellation keep URL and draft; confirmed leave then route restoration recovers input')
 await click('放弃新增');await click('放弃新增','[role=alertdialog] button');await input('[aria-label="文本搜索"]','007');await click('搜索记录');await wait(350)
 const exportFile=join(workspace,'quick-filter.xlsx');await native.evaluate(`gridElectron.dialog.showSaveDialog=async()=>({canceled:false,filePath:${JSON.stringify(exportFile)}});true`)
 await click('更多操作');await click('导出 Excel','[role=menuitem]');await select('导出范围','当前筛选结果');await click('选择保存位置');await waitFor(renderer,"!document.querySelector('[role=dialog]')",'filtered export completed',30000)
 const exported=JSON.parse(execFileSync('uv',['run','--directory',join(root,'apps/backend'),'python','-c',`from openpyxl import load_workbook; import json; b=load_workbook(${JSON.stringify(exportFile)},data_only=True); print(json.dumps([list(r) for r in b.active.iter_rows(values_only=True)],ensure_ascii=False,default=str))`],{cwd:root,encoding:'utf8'}))
 assert.equal(exported.length,2);assert.ok(exported[1].includes('007'));assert.ok(!exported[1].includes('008'));await capture('V14-filtered-export')
 passed('E14-export','Native save-result injection + real export UI writes only the applied quick-search result, independently checked by openpyxl')
 await click('清除文本搜索')
 report.viewport=await renderer.evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio,font:getComputedStyle(document.body).fontFamily,scrollWidth:document.documentElement.scrollWidth})');assert.ok(report.viewport.scrollWidth<=report.viewport.width+1)
 report.status='partial';report.remaining=['E13-legacy-and-reimport-E2E','E15-native-IME','visual-review']
 console.log(JSON.stringify({workspace,evidence,manual},null,2))
 if(manual){await writeFile(join(evidence,'report.json'),JSON.stringify(report,null,2));await new Promise(resolve=>{process.once('SIGINT',resolve);desktop.child.once('exit',resolve)})}
}catch(error){report.status='failed';report.error=String(error);if(renderer){await writeFile(join(evidence,'failure-hit-test.json'),JSON.stringify(await renderer.evaluate(`(()=>({bodyPointer:getComputedStyle(document.body).pointerEvents,buttons:[...document.querySelectorAll('button')].filter(e=>e.textContent.trim()==='浏览器配置').map(e=>{const r=e.getBoundingClientRect();return {rect:r.toJSON(),disabled:e.disabled,pointer:getComputedStyle(e).pointerEvents,hit:document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)?.outerHTML.slice(0,800)}}),dialogs:[...document.querySelectorAll('[role=dialog],[role=alertdialog]')].map(e=>({text:e.innerText,rect:e.getBoundingClientRect().toJSON()}))}))()`),null,2)).catch(()=>{});await capture('failure').catch(()=>{});await writeFile(join(evidence,'failure-dom.txt'),await renderer.evaluate('document.body.innerText').catch(()=>''))}throw error}
finally{report.finished=new Date().toISOString();await writeFile(join(evidence,'report.json'),JSON.stringify(report,null,2));renderer?.close();native?.close();if(desktop)await stop(desktop.child);console.log(`Evidence: ${evidence}`)}
