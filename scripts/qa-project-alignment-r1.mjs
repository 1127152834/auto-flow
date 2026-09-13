import assert from 'node:assert/strict'
import { randomUUID, createHash } from 'node:crypto'
import { execFile } from 'node:child_process'
import { mkdir, mkdtemp, readFile, readdir, realpath, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, relative, resolve, isAbsolute } from 'node:path'
import { pathToFileURL } from 'node:url'
import { createInterface } from 'node:readline/promises'
import { promisify } from 'node:util'
import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

export async function assertOwnedWorkspace(owner, candidate) {
  const base = await realpath(owner), target = await realpath(candidate)
  const marker = JSON.parse(await readFile(join(base, '.r1-qa.json'), 'utf8'))
  assert.equal(marker.kind, 'autoflow-r1-qa'); assert.equal(marker.version, 1)
  const path = relative(base, target)
  assert.ok(!path.startsWith('..') && !isAbsolute(path), '只允许操作本次工具创建的隔离目录')
}

async function main() {
  const root=resolve(import.meta.dirname,'..'), manual=process.argv.includes('--manual')
  const {stdout:gitHead}=await promisify(execFile)('git',['rev-parse','HEAD'],{cwd:root})
  const scriptSha256=createHash('sha256').update(await readFile(new URL(import.meta.url))).digest('hex')
  const buildRoot=join(root,'apps/desktop/out'), buildHash=createHash('sha256')
  for(const file of (await readdir(buildRoot,{recursive:true})).filter(name=>/\.(js|css|html)$/.test(name)).sort())buildHash.update(file).update(await readFile(join(buildRoot,file)))
  const provenance={gitHead:gitHead.trim(),scriptSha256,desktopBuildSha256:buildHash.digest('hex')}
  const owner=await realpath(await mkdtemp(join(tmpdir(),'autoflow-r1-qa-')))
  await writeFile(join(owner,'.r1-qa.json'),JSON.stringify({kind:'autoflow-r1-qa',version:1}))
  const userData=join(owner,'workspace-a'), other=join(owner,'workspace-b')
  await mkdir(userData);await mkdir(other)
  for(const path of [userData,other]) await writeFile(join(path,'.autoflow-workspace.json'),JSON.stringify({schemaVersion:1,kind:'autoflow-workspace'}))
  await writeFile(join(userData,'desktop-settings.json'),JSON.stringify({schemaVersion:1,currentPath:userData,previousPath:other,preferences:{zoom:100,motion:'system'}}))
  const evidenceParent=join(root,'docs/project-management/design-alignment/acceptance/r1/runs');await mkdir(evidenceParent,{recursive:true})
  const evidence=await mkdtemp(join(evidenceParent,'run-')), checks=[], injections=[], commandErrors=[]
  await promisify(execFile)('uv',['run','--project',join(root,'apps/backend'),'python','-c',`from openpyxl import Workbook; b=Workbook(); s=b.active; s.title='资料'; s.append(['标题','链接']); s.append(['温室管理清单','https://example.com/greenhouse']); s.append(['花园记录','https://example.com/garden']); b.save(${JSON.stringify(join(owner,'sample.xlsx'))})`])
  let desktop,renderer,native,fixture,clean=false
  const report=async(result,error)=>writeFile(join(evidence,'result.json'),JSON.stringify({result,checkedAt:new Date().toISOString(),platform:process.platform,arch:process.arch,mode:manual?'manual-tool':'automatic',provenance,checks,injections,commandErrors,error,workspace:owner,excluded:['Windows','其他架构','打包应用','用户手动执行结果']},null,2)+'\n')
  const checkpoint=message=>{checks.push(message);console.log(message)}
  async function launch(){desktop=await launchElectron(root,{launchArgs:[`--user-data-dir=${userData}`,'--inspect=0'],cliArgs:[]});renderer=desktop.cdp;native=await connectCdp(desktop.inspectorUrl);await native.evaluate("globalThis.qaElectron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');qaElectron.BrowserWindow.getAllWindows()[0].setContentSize(1440,1024);true");await visible('本地服务正常',30000)}
  async function shutdown(){renderer?.close();native?.close();await stop(desktop?.child);desktop=renderer=native=undefined}
  async function visible(text,timeout=15000){return waitFor(renderer,`document.body?.innerText.includes(${JSON.stringify(text)})`,text,timeout)}
  async function api(path,options={}) {
    const context=await renderer.evaluate('window.autoflow.getRuntimeContext()');await assertOwnedWorkspace(owner,context.workspaceKey)
    const response=await fetch(`${context.sidecar.baseUrl}/api/v1${path}`,{...options,body:options.body?JSON.stringify(options.body):undefined,headers:{'x-autoflow-token':context.sidecar.token,'content-type':'application/json','Idempotency-Key':randomUUID()}})
    assert.ok(response.ok,`${options.method??'GET'} ${path}: ${response.status} ${response.ok?'':await response.text()}`);return response.json()
  }
  async function click(text,selector='button'){
    const point=await waitFor(renderer,`(()=>{const el=[...document.querySelectorAll(${JSON.stringify(selector)})].find(e=>(e.textContent.trim()===${JSON.stringify(text)}||e.getAttribute('aria-label')===${JSON.stringify(text)})&&e.getClientRects().length);if(!el||el.disabled)return null;el.scrollIntoView({block:'center'});const r=el.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return el.contains(document.elementFromPoint(x,y))?{x,y}:null})()`,text)
    for(const type of ['mousePressed','mouseReleased'])await renderer.command('Input.dispatchMouseEvent',{type,...point,button:'left',clickCount:1});await wait(120)
  }
  async function input(selector,value){await renderer.evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el)throw Error('input missing');el.focus();el.select()})()`);await renderer.command('Input.insertText',{text:value})}
  async function key(value){for(const type of ['keyDown','keyUp'])await renderer.command('Input.dispatchKeyEvent',{type,key:value,code:value});await wait(150)}
  async function route(hash){await renderer.evaluate(`location.hash=${JSON.stringify(hash)}`);await wait(250)}
  async function capture(name){const {data}=await renderer.command('Page.captureScreenshot',{format:'png'});await writeFile(join(evidence,`${name}.png`),Buffer.from(data,'base64'))}
  async function zoom(value){await native.evaluate(`qaElectron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(${value});true`);await wait(250)}
  async function fits(){assert.ok(await renderer.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),'页面不得横向撑宽');assert.ok(await renderer.evaluate(`(()=>{const input=document.querySelector('[aria-label=文本搜索]'),button=[...document.querySelectorAll('[data-query-panel-trigger]')].find(e=>e.textContent==='筛选');if(!input||!button)return true;const a=input.getBoundingClientRect(),b=button.getBoundingClientRect();return a.right<=b.left+1||b.right<=a.left+1||a.bottom<=b.top+1||b.bottom<=a.top+1})()`),'搜索框与筛选按钮不得重叠')}
  async function seed(){
    for(let index=1;index<=52;index++)await api('/projects',{method:'POST',body:{name:`R1分页${String(index).padStart(3,'0')}`,description:'工具生成的分页边界资料'}})
    const project=(await api('/projects?q=R1分页001')).items[0]
    const table=await api(`/projects/${project.projectId}/tables`,{method:'POST',body:{name:'分页资料库',description:'120 条合成记录',sourceKind:'local'}})
    const field=await api(`/projects/${project.projectId}/tables/${table.tableId}/fields`,{method:'POST',body:{definition:{key:'title',name:'标题',type:'string',required:false,validation:{}},expectedTableRevision:table.tableRevision,sourceColumnPolicy:'localOnly'}})
    for(let index=1;index<=120;index++)await api(`/projects/${project.projectId}/tables/${table.tableId}/records`,{method:'POST',body:{datasetGeneration:table.datasetGeneration,values:[{fieldId:field.field.ref.fieldId,value:`${index%2?'温室':'花园'}资料${String(index).padStart(3,'0')}`}]}})
    fixture={project,table,field:field.field};await writeFile(join(evidence,'fixtures.json'),JSON.stringify(fixture,null,2));checkpoint('生成52个未访问分页项目和120条合成记录（HTTP批量资料，不代替界面创建验收）')
  }
  async function competingEdit(){
    const hash=await renderer.evaluate('location.hash'),parts=hash.split('/'),id=parts[2];assert.ok(id,'请先打开要测试的项目')
    if(parts[3]==='data'&&parts[4]){const path=`/projects/${id}/tables/${parts[4]}`,table=await api(path);await api(path,{method:'PATCH',body:{description:`QA竞争编辑 ${Date.now()}`,expectedTableRevision:table.tableRevision}})}
    else{const path=`/projects/${id}`,project=await api(path);await api(path,{method:'PATCH',body:{description:`QA竞争编辑 ${Date.now()}`,expectedManagementRevision:project.managementRevision}})}
    checkpoint('隔离API真实竞争编辑已提交；保留当前表单草稿后点击保存验证冲突')
  }
  async function inject(kind){
    await renderer.evaluate(`(()=>{const original=window.__r1OriginalFetch??window.fetch.bind(window);window.__r1OriginalFetch=original;let armed=true,lookup=true,reads=${JSON.stringify(kind)}==='read-error'?3:1;window.__r1InjectedCount=0;window.fetch=async(input,init)=>{const path=new URL(typeof input==='string'?input:input.url,location.href).pathname,method=(init?.method??'GET').toUpperCase();const project=path.startsWith('/api/v1/projects');if(['read','read-error'].includes(${JSON.stringify(kind)})&&reads>0&&project&&method==='GET'&&!path.includes('/operations/')){reads--;window.__r1InjectedCount++;throw new TypeError('R1 QA 一次性读取失败')}if(${JSON.stringify(kind)}==='lost'&&lookup&&path.includes('/operations/by-idempotency-key/')){lookup=false;throw new TypeError('R1 QA 一次性结果查询失败')}const response=await original(input,init);if(${JSON.stringify(kind)}==='lost'&&armed&&project&&['POST','PATCH','PUT','DELETE'].includes(method)&&response.ok){armed=false;throw new TypeError('R1 QA 已提交但响应丢失')}return response};return true})()`)
    injections.push({kind,at:new Date().toISOString(),scope:'仅当前隔离renderer，fetch测试注入'});console.log(kind.startsWith('read')?'读取故障已注入；read 只失败一次，现有自动重试可恢复；readerror 覆盖本轮两次自动重试。':'下一次成功写入将丢失响应并阻断一次核验；请保存后使用页面核验原操作。')
  }
  async function restartService(){const previous=await renderer.evaluate('(async()=> (await window.autoflow.getRuntimeContext()).sidecar.instanceId)()');await renderer.evaluate('window.autoflow.restartSidecar()');await waitFor(renderer,`(async()=>{const r=await window.autoflow.getRuntimeContext();return r.sidecar.state==='ready'&&r.sidecar.instanceId!==${JSON.stringify(previous)}})()`,'service restarts',30000);await visible('本地服务正常');checkpoint('测试服务完整重启，等待新实例ready')}
  async function entries(){
    for(const [label,hash] of [['浏览器配置','profiles'],['代理管理','proxies'],['模型管理','models'],['设置','settings'],['总览','dashboard']]){
      await click(label,label==='设置'?'header button':'[aria-label=全局导航] button');await waitFor(renderer,`location.hash==='#/${hash}'&&[...document.querySelectorAll('h1')].some(e=>e.textContent===${JSON.stringify(label)})`,`${label}实际入口`);await capture(`entry-${hash}`)
    }
    const label=await renderer.evaluate("[...document.querySelectorAll('button')].find(e=>e.querySelector('strong')?.textContent==='工作流工作台').textContent.trim()")
    await click(label);await waitFor(native,'qaElectron.BrowserWindow.getAllWindows().length===2','Studio window opens',30000);await wait(1200)
    const data=await native.evaluate("(async()=>{const w=qaElectron.BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().includes('studio'));if(!w)throw Error('Studio unavailable');return (await w.webContents.capturePage()).toPNG().toString('base64')})()")
    await writeFile(join(evidence,'entry-studio.png'),Buffer.from(data,'base64'));await native.evaluate("qaElectron.BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().includes('studio')).close();true")
    checkpoint('实际顶部浏览器/代理/模型/设置/总览入口及独立Studio窗口回归（仅入口，不宣称资源完整操作通过）')
  }
  async function switchWorkspace(){await renderer.evaluate("(async()=>{const c=await window.autoflow.chooseWorkspace('previous');if(!c.ok||!c.value)throw Error('无目标');const r=await window.autoflow.confirmWorkspace(c.value.id);if(!r.ok)throw Error(r.error.message);return true})()");await visible('本地服务正常',30000);await wait(500);const current=await renderer.evaluate('(async()=> (await window.autoflow.getRuntimeContext()).workspaceKey)()');await assertOwnedWorkspace(owner,current);checkpoint('切换到工具创建的另一工作区')}
  try {
    await launch();await route('#/projects');await visible('尚无最近访问');await capture('r1-a-empty')
    if(manual){
      console.log(`R1 隔离应用已打开。测试目录：${owner}\n证据：${evidence}\n命令：seed（52/120资料，仅一次）、fixture（打开分页表）、conflict、readfail（一次失败自动重试）、readerror（本轮含重试均失败）、lost、restore（恢复fetch）、service、restart、switch、shot、entries（其他模块入口回归）、zoom200、zoom100、quit（保留目录）、clean（退出并清理本次目录）`)
      const lines=createInterface({input:process.stdin,output:process.stdout})
      for await(const raw of lines){const command=raw.trim();try{
        if(command==='seed'){if(fixture)console.log('本次已生成');else await seed()}
        else if(command==='fixture'){assert.ok(fixture,'请先seed');await route(`#/projects/${fixture.project.projectId}/data/${fixture.table.tableId}/records`)}
        else if(command==='conflict')await competingEdit()
        else if(command==='readfail')await inject('read')
        else if(command==='readerror')await inject('read-error')
        else if(command==='lost')await inject('lost')
        else if(command==='restore')await renderer.evaluate('if(window.__r1OriginalFetch)window.fetch=window.__r1OriginalFetch;true')
        else if(command==='service')await restartService()
        else if(command==='restart'){await shutdown();await launch()}
        else if(command==='switch')await switchWorkspace()
        else if(command==='entries')await entries()
        else if(command==='shot')await capture(`manual-${Date.now()}`)
        else if(command==='zoom200')await zoom(2)
        else if(command==='zoom100')await zoom(1)
        else if(command==='quit'||command==='clean'){clean=command==='clean';lines.close();break}
        else console.log('请使用上方命令。')
      }catch(error){commandErrors.push({command,error:String(error.message).replaceAll(owner,'<qa-workspace>')});console.error(error.message)}}
      await report('manual-session-ended');return
    }
    // Small core examples are created using actual controls; bulk data only exercises pagination.
    for(const name of ['R1手建A','R1手建B']){await click('新建项目');await input('#project-name',name);await click('创建项目');await visible('项目资料');await click('返回项目目录')}
    await click('查看全部项目');await click('R1手建A');await visible('项目资料');await click('返回项目目录');await click('R1手建B');await visible('项目资料');await click('返回项目目录');await click('返回最近')
    const recent=await renderer.evaluate("[...document.querySelectorAll('[aria-label=项目目录] article')].map(e=>e.innerText)");assert.ok(recent[0].includes('R1手建B'));assert.ok(recent[1].includes('R1手建A'));await capture('r1-a-recent');checkpoint('UI创建A/B并依次打开，最近B在A之前')
    await seed();await click('查看全部项目');await input('[aria-label=搜索项目]','R1分页');await waitFor(renderer,"document.querySelectorAll('[aria-label=项目目录] article').length===50",'50 server paginated cards');await click('下一页');await waitFor(renderer,"document.querySelectorAll('[aria-label=项目目录] article').length===2",'second page');await capture('r1-a-all-page2');checkpoint('真实目录服务端分页50/2')
    await route(`#/projects/${fixture.project.projectId}/data`);await visible('分页资料库');await capture('r1-b-directory');await click('打开分页资料库');await visible('温室资料');await fits();await capture('r1-c-records')
    const before=await renderer.evaluate('document.querySelector("tbody")?.innerText')
    await input('[aria-label=文本搜索]','温室');assert.equal(await renderer.evaluate('document.querySelector("tbody")?.innerText'),before);await click('搜索记录');await waitFor(renderer,"document.querySelector('tbody')?.innerText.includes('温室资料')&&!document.querySelector('tbody')?.innerText.includes('花园资料')",'applied contains search');checkpoint('指定文本字段输入不查询，提交后筛选实际记录')
    const exportPath=join(owner,'text-search.xlsx');await native.evaluate(`qaElectron.dialog.showSaveDialog=async()=>({canceled:false,filePath:${JSON.stringify(exportPath)}});true`)
    injections.push({kind:'save-dialog-selection',at:new Date().toISOString(),scope:'系统保存面板返回测试路径；真实文件IPC与写出'})
    await click('导出 Excel');await click('导出范围','[aria-label=导出范围]');await click('当前筛选结果','[role=option]');await click('选择保存位置');await waitFor(renderer,"!document.querySelector('[role=dialog]')",'search export completes',30000)
    const {stdout}=await promisify(execFile)('uv',['run','--project',join(root,'apps/backend'),'python','-c',`from openpyxl import load_workbook; import json; b=load_workbook(${JSON.stringify(exportPath)},read_only=True,data_only=True); print(json.dumps(list(b.active.values),ensure_ascii=False))`]);const exported=JSON.parse(stdout);assert.equal(exported.length,61);assert.ok(exported.slice(1).every(row=>row[0].startsWith('温室')));checkpoint('当前筛选导出真实XLSX为60条温室记录，与快捷搜索条件一致')
    for(const panel of ['筛选','排序','显示列']){await click(panel);await capture(`r1-c-${panel}`);await fits();await key('Escape');assert.equal(await renderer.evaluate('Boolean(document.querySelector("[data-af-popup]"))'),false)}
    await click('显示列');await click('标题','[role=checkbox]');await click('取消');assert.ok(await renderer.evaluate("[...document.querySelectorAll('th')].some(e=>e.innerText==='标题')"));await click('显示列');await click('标题','[role=checkbox]');await click('应用显示列');assert.equal(await renderer.evaluate("[...document.querySelectorAll('th')].some(e=>e.innerText==='标题')"),false);checkpoint('选列取消不生效、应用后隐藏字段')
    await click('显示列');await click('标题','[role=checkbox]');await click('应用显示列');await zoom(2);await fits();for(const panel of ['筛选','排序','显示列']){await click(panel);await fits();await capture(`r1-c-${panel}-200`);await key('Escape')}await zoom(1);checkpoint('1440×1024及200%三个查询浮层无应用横向撑宽')
    await restartService();await visible('温室资料');await shutdown();await launch();await route('#/projects');await visible('最近打开');await capture('r1-after-restart');checkpoint('Electron完整重启后最近访问事实持久化')
    await switchWorkspace();assert.equal((await api('/projects')).total,0);await switchWorkspace();assert.equal((await api('/projects')).total,54);checkpoint('两个真实工作区隔离并切回恢复54个项目')
    await route('#/projects');await visible('最近打开');const savedContent=await renderer.evaluate("[...document.querySelectorAll('[aria-label=项目目录] article')].map(e=>e.innerText).join('')")
    await inject('read');await click('刷新');await waitFor(renderer,'window.__r1InjectedCount===1','one failed read');await wait(3500);checkpoint('一次读取故障由现有自动重试恢复，保留旧目录内容');await inject('read-error');await click('刷新');await visible('刷新最近项目失败');assert.equal(await renderer.evaluate("[...document.querySelectorAll('[aria-label=项目目录] article')].map(e=>e.innerText).join('')"),savedContent);await capture('r1-read-failure');await click('刷新');await waitFor(renderer,"!document.body.innerText.includes('刷新最近项目失败')",'read retry')
    await inject('lost');await click('新建项目');await input('#project-name','R1响应丢失');await click('创建项目');await visible('核对保存结果');assert.equal((await api('/projects?q=R1响应丢失')).total,1);await capture('r1-lost-response');await click('核对保存结果');await visible('项目资料');assert.equal((await api('/projects?q=R1响应丢失')).total,1);checkpoint('一次读取失败保留旧目录；提交响应丢失后用原操作核验，只有一个项目事实')
    await click('编辑项目');await input('#project-description','我的未保存草稿');await competingEdit();await click('保存');await visible('基于最新内容重新编辑');assert.equal(await renderer.evaluate("document.querySelector('#project-description').value"),'我的未保存草稿');await capture('r1-real-conflict');await click('基于最新内容重新编辑');await input('#project-description','冲突处理后保存');await click('保存');await waitFor(renderer,"!document.querySelector('#project-form')",'conflict saved');checkpoint('真实竞争编辑发生409，保留输入，基于最新内容重新编辑后保存')
    await report('passed');clean=true;console.log(`R1自动验收证据：${evidence}`)
  }catch(error){try{await capture('failure');await writeFile(join(evidence,'failure-dom.json'),JSON.stringify(await renderer.evaluate("({bodyStyle:document.body.getAttribute('style'),buttons:[...document.querySelectorAll('button')].map(e=>{const r=e.getBoundingClientRect();return {name:e.getAttribute('aria-label')||e.textContent,disabled:e.disabled,rect:{x:r.x,y:r.y,w:r.width,h:r.height},hit:document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)?.outerHTML.slice(0,250)}})})"),null,2))}catch{}await report('failed',String(error.message).replaceAll(owner,'<qa-workspace>'));throw error}
  finally{await shutdown();if(clean){await assertOwnedWorkspace(owner,owner);await rm(owner,{recursive:true,force:true})}else console.log(`保留隔离资料 ${owner}；截图报告始终保留 ${evidence}`)}
}
if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href)main().catch(error=>{console.error(error);process.exitCode=1})
