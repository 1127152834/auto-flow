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

export async function main(options={}) {
  const root=resolve(import.meta.dirname,'..'), manual=options.manual??process.argv.includes('--manual'), visualDirectory=options.visualDirectory??process.argv.includes('--visual-directory'), recordPages=options.recordPages??process.argv.includes('--record-pages')
  const {stdout:gitHead}=await promisify(execFile)('git',['rev-parse','HEAD'],{cwd:root})
  const scriptSha256=createHash('sha256').update(await readFile(new URL(import.meta.url))).digest('hex')
  const buildRoot=join(root,'apps/desktop/out'), buildHash=createHash('sha256')
  for(const file of (await readdir(buildRoot,{recursive:true})).filter(name=>/\.(js|css|html)$/.test(name)).sort())buildHash.update(file).update(await readFile(join(buildRoot,file)))
  const {stdout:workingChanges}=await promisify(execFile)('git',['diff','--name-only','HEAD'],{cwd:root})
  const provenance={gitHead:gitHead.trim(),dirtyFiles:workingChanges.trim().split('\n').filter(Boolean),scriptSha256,desktopBuildSha256:buildHash.digest('hex')}
  const owner=await realpath(await mkdtemp(join(tmpdir(),'autoflow-r1-qa-')))
  await writeFile(join(owner,'.r1-qa.json'),JSON.stringify({kind:'autoflow-r1-qa',version:1}))
  const userData=join(owner,'workspace-a'), other=join(owner,'workspace-b')
  await mkdir(userData);await mkdir(other)
  for(const path of [userData,other]) await writeFile(join(path,'.autoflow-workspace.json'),JSON.stringify({schemaVersion:1,kind:'autoflow-workspace'}))
  await writeFile(join(userData,'desktop-settings.json'),JSON.stringify({schemaVersion:1,currentPath:userData,previousPath:other,preferences:{zoom:100,motion:'system'}}))
  const evidenceParent=join(root,`docs/project-management/design-alignment/acceptance/${recordPages?'r2':'r1'}/runs`);await mkdir(evidenceParent,{recursive:true})
  const evidence=await mkdtemp(join(evidenceParent,'run-')), checks=[], injections=[], commandErrors=[], screenshots=[]
  await promisify(execFile)('uv',['run','--project',join(root,'apps/backend'),'python','-c',`from openpyxl import Workbook; b=Workbook(); s=b.active; s.title='资料'; s.append(['标题','链接']); s.append(['温室管理清单','https://example.com/greenhouse']); s.append(['花园记录','https://example.com/garden']); b.save(${JSON.stringify(join(owner,'sample.xlsx'))})`])
  let desktop,renderer,native,fixture,clean=false
  const report=async(result,error)=>writeFile(join(evidence,'result.json'),JSON.stringify({result,checkedAt:new Date().toISOString(),platform:process.platform,arch:process.arch,mode:manual?'manual-tool':recordPages?'record-pages':visualDirectory?'visual-directory':'automatic',visualReview:'pending',provenance,checks,injections,commandErrors,screenshots,error,workspace:owner,excluded:['Windows','其他架构','打包应用','用户手动执行结果']},null,2)+'\n')
  const checkpoint=message=>{checks.push(message);console.log(message)}
  async function launch(){desktop=await launchElectron(root,{launchArgs:[`--user-data-dir=${userData}`,'--inspect=0'],cliArgs:[]});renderer=desktop.cdp;native=await connectCdp(desktop.inspectorUrl);await native.evaluate("globalThis.qaElectron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');qaElectron.BrowserWindow.getAllWindows()[0].setContentSize(1440,1024);true");await visible('本地服务正常',30000);if(!manual){await renderer.command('Emulation.setDeviceMetricsOverride',{width:1440,height:1024,deviceScaleFactor:1,mobile:false});assert.deepEqual(await renderer.evaluate('({w:innerWidth,h:innerHeight})'),{w:1440,h:1024})}}
  async function shutdown(){renderer?.close();native?.close();await stop(desktop?.child);desktop=renderer=native=undefined}
  async function visible(text,timeout=15000){return waitFor(renderer,`document.body?.innerText.includes(${JSON.stringify(text)})`,text,timeout)}
  async function api(path,options={}) {
    const context=await renderer.evaluate('window.autoflow.getRuntimeContext()');await assertOwnedWorkspace(owner,context.workspaceKey)
    const response=await fetch(`${context.sidecar.baseUrl}/api/v1${path}`,{...options,body:options.body?JSON.stringify(options.body):undefined,headers:{'x-autoflow-token':context.sidecar.token,'content-type':'application/json','Idempotency-Key':randomUUID()}})
    assert.ok(response.ok,`${options.method??'GET'} ${path}: ${response.status} ${response.ok?'':await response.text()}`);return response.json()
  }
  async function click(text,selector='button'){
    const point=await waitFor(renderer,`(()=>{const matches=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>(${JSON.stringify(text)}===''||e.textContent.trim()===${JSON.stringify(text)}||e.getAttribute('aria-label')===${JSON.stringify(text)})&&e.getClientRects().length);if(matches.length!==1)return null;const el=matches[0];if(el.disabled)return null;el.scrollIntoView({block:'center'});const r=el.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return el.contains(document.elementFromPoint(x,y))?{x,y}:null})()`,text)
    for(const type of ['mousePressed','mouseReleased'])await renderer.command('Input.dispatchMouseEvent',{type,...point,button:'left',clickCount:1});await wait(120)
  }
  async function input(selector,value){await renderer.evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el)throw Error('input missing');el.focus();el.select()})()`);await renderer.command('Input.insertText',{text:value})}
  async function key(value){for(const type of ['keyDown','keyUp'])await renderer.command('Input.dispatchKeyEvent',{type,key:value,code:value});await wait(150)}
  async function route(hash){await renderer.evaluate(`location.hash=${JSON.stringify(hash)}`);await wait(250)}
  async function capture(name, source={stateSource:'mixed-unclassified',navigation:'notClassified',level:'unclassified'}) {
    await renderer.evaluate('document.fonts.ready.then(()=>true)')
    const state=await renderer.evaluate(`({route:location.hash,viewport:{width:innerWidth,height:innerHeight},dpr:devicePixelRatio,fonts:document.fonts.status})`)
    let geometry=null, previous=''
    for(let attempt=0;attempt<15;attempt++){
      const current=await renderer.evaluate(`JSON.stringify([...document.querySelectorAll('h1,article,[data-table-detail] thead,[data-af-popup],[role=status][data-tone]')].map(e=>{const r=e.getBoundingClientRect();return {tag:e.tagName,label:e.getAttribute('aria-label'),text:e.textContent.slice(0,80),x:r.x,y:r.y,w:r.width,h:r.height}}))`)
      if(current===previous){geometry=JSON.parse(current);break}previous=current;await wait(100)
    }
    assert.ok(geometry,'截图前布局必须稳定')
    await renderer.command('DOM.enable');await renderer.command('CSS.enable')
    const {root:dom}=await renderer.command('DOM.getDocument')
    const {nodeId}=await renderer.command('DOM.querySelector',{nodeId:dom.nodeId,selector:'h1'})
    const platformFonts=nodeId?(await renderer.command('CSS.getPlatformFontsForNode',{nodeId})).fonts:[]
    const zoomFactor=await native.evaluate('qaElectron.BrowserWindow.getAllWindows()[0].webContents.getZoomFactor()')
    const windowContentSize=await native.evaluate('qaElectron.BrowserWindow.getAllWindows()[0].getContentSize()')
    const {data}=await renderer.command('Page.captureScreenshot',{format:'png'})
    await writeFile(join(evidence,`${name}.png`),Buffer.from(data,'base64'))
    screenshots.push({id:name,file:`${name}.png`,...source,...state,zoom:zoomFactor,windowContentSize,viewportMode:!manual?'CDP desktop viewport override (physical macOS work area limited)':'native',platformFonts,geometry,checks:[...checks],visualReview:'pending'})
  }
  async function directoryGeometry() {
    const geometry=await renderer.evaluate(`(()=>{const box=e=>{const r=e.getBoundingClientRect();return {tag:e.tagName,label:e.getAttribute('aria-label'),text:e.textContent.slice(0,80),x:r.x,y:r.y,w:r.width,h:r.height}};return {h1:document.querySelectorAll('h1').length,width:innerWidth,scrollWidth:document.documentElement.scrollWidth,cards:[...document.querySelectorAll('[aria-label=项目目录] article')].map(e=>({card:box(e),icon:e.querySelector('[data-project-icon]')?box(e.querySelector('[data-project-icon]')):null,info:e.querySelector('[data-project-info]')?box(e.querySelector('[data-project-info]')):null,menu:e.querySelector('[data-project-menu]')?box(e.querySelector('[data-project-menu]')):null}))}})()`)
    assert.equal(geometry.h1,1,'项目目录只有一个主标题')
    assert.ok(geometry.scrollWidth<=geometry.width+1,'项目目录无全页横向溢出')
    for(const item of geometry.cards){assert.ok(item.icon&&item.info&&item.menu,'项目图标/信息/菜单区域存在');assert.ok(item.icon.x+item.icon.w<=item.info.x+1,'图标在业务信息左侧');assert.ok(item.menu.x+item.menu.w/2>item.card.x+item.card.w*2/3,'更多菜单位于卡片右侧');assert.ok(item.menu.y+item.menu.h/2<item.card.y+item.card.h/2,'更多菜单位于卡片上半部')}
    await writeFile(join(evidence,`directory-geometry-${Date.now()}.json`),JSON.stringify(geometry,null,2));return geometry
  }
  async function visualDirectoryFlow() {
    const source={stateSource:'ui',navigation:'pointer',level:'E1',reference:'R1-A'}
    const created=['内容采集项目','客户跟进项目'], longName='🧪'.repeat(36)
    for(const name of created){await click('新建项目');await input('#project-name',name);await input('#project-description',name==='内容采集项目'?'自动采集电商商品信息并生成结构化数据':'管理客户信息并自动生成跟进记录');await click('创建项目');await visible('项目资料');await click('返回项目目录')}
    await click('查看全部项目');await click(created[0]);await visible('项目资料');await click('返回项目目录');await click(created[1]);await visible('项目资料');await click('返回项目目录');await click('返回最近')
    await directoryGeometry();checkpoint('E1: UI创建/打开A再B，目录结构图标/信息/更多几何通过')
    const names=await renderer.evaluate("[...document.querySelectorAll('[aria-label=项目目录] article')].map(e=>e.textContent)");assert.ok(names[0].includes(created[1])&&names[1].includes(created[0]))
    await waitFor(renderer,"!document.querySelector('[role=status][data-tone]')",'目录正常态通知自然退出');await capture('VR-A01-recent',source)
    const before=await renderer.evaluate('location.hash');await click(`更多${created[1]}操作`);await click('编辑项目','[role=menuitem]');await visible('编辑项目');assert.equal(await renderer.evaluate('location.hash'),before);await click('取消');checkpoint('E1: 更多编辑打开表单不导航')
    await api('/projects',{method:'POST',body:{name:longName,description:'用于长文本边界。API准备，不代表UI创建通过。'}})
    await click('查看全部项目');await visible(longName);await directoryGeometry();await capture('VR-A02-all',{...source,stateSource:'ui-with-api-fixture',setupLevel:'E2',fixture:'第三个长名称项目经API预置，E1仅证明UI搜索/进入全部路径'})
    await input('[aria-label=搜索项目]','不存在的资料');await visible('没有匹配的项目');await capture('VR-A04-no-match',source);await input('[aria-label=搜索项目]','');await visible(created[0]);await click('返回最近')
    assert.equal(await renderer.evaluate(`[...document.querySelectorAll('[aria-label=项目目录] article')].some(e=>e.textContent.includes(${JSON.stringify(longName)}))`),false);checkpoint('E1: 未访问项目仅在全部目录可见；UI无匹配可恢复')
    await click('查看全部项目');await click(longName);await visible('项目资料');await click('返回项目目录');await click('返回最近')
    await zoom(2);assert.deepEqual(await renderer.evaluate('({w:innerWidth,h:innerHeight,dpr:devicePixelRatio})'),{w:720,h:512,dpr:2},'200%逻辑视口与DPR');await renderer.evaluate("document.querySelector('[aria-label=项目目录] article').scrollIntoView({block:'center'})");await directoryGeometry();assert.ok(await renderer.evaluate(`(()=>{const e=[...document.querySelectorAll('button[title]')].find(e=>e.title===${JSON.stringify(longName)})?.querySelector('span.truncate');return e&&e.scrollWidth>e.clientWidth&&getComputedStyle(e).textOverflow==='ellipsis'})()`),'边界fixture必须实际触发名称省略');checkpoint('E1: 36个补充平面字符名称在200%实际触发尾部省略，完整title保留');await capture('VR-A01-recent-200',{...source,stateSource:'ui-with-api-fixture',setupLevel:'E2',fixture:'长名fixture经UI打开成为最近记录'});await zoom(1)
    await report('passed');clean=true;console.log(`VR1目录E2E通过，视觉审查待填：${evidence}`)
  }
  async function zoom(value){await native.evaluate(`qaElectron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(${value});true`);if(!manual)await renderer.command('Emulation.setDeviceMetricsOverride',{width:1440,height:1024,deviceScaleFactor:1,mobile:false});await wait(250)}
  async function fits(){assert.ok(await renderer.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),'页面不得横向撑宽');assert.ok(await renderer.evaluate(`(()=>{const input=document.querySelector('[aria-label=文本搜索]'),button=[...document.querySelectorAll('[data-query-panel-trigger]')].find(e=>e.textContent==='筛选');if(!input||!button)return true;const a=input.getBoundingClientRect(),b=button.getBoundingClientRect();return a.right<=b.left+1||b.right<=a.left+1||a.bottom<=b.top+1||b.bottom<=a.top+1})()`),'搜索框与筛选按钮不得重叠')}
  async function seed(){
    for(let index=1;index<=52;index++)await api('/projects',{method:'POST',body:{name:`R1分页${String(index).padStart(3,'0')}`,description:'工具生成的分页边界资料'}})
    const project=(await api('/projects?q=R1分页001')).items[0]
    const table=await api(`/projects/${project.projectId}/tables`,{method:'POST',body:{name:'分页资料库',description:'120 条合成记录',sourceKind:'local'}})
    const field=await api(`/projects/${project.projectId}/tables/${table.tableId}/fields`,{method:'POST',body:{definition:{key:'title',name:'标题',type:'string',required:false,validation:{}},expectedTableRevision:table.tableRevision,sourceColumnPolicy:'localOnly'}})
    for(let index=1;index<=120;index++)await api(`/projects/${project.projectId}/tables/${table.tableId}/records`,{method:'POST',body:{datasetGeneration:table.datasetGeneration,values:[{fieldId:field.field.ref.fieldId,value:`${index%2?'温室':'花园'}资料${String(index).padStart(3,'0')}`}]}})
    fixture={project,table,field:field.field};await writeFile(join(evidence,'fixtures.json'),JSON.stringify(fixture,null,2));checkpoint('生成52个未访问分页项目和120条合成记录（HTTP批量资料，不代替界面创建验收）')
  }
  async function uiDataFlow() {
    const source={stateSource:'ui',navigation:'pointer',level:'E1',reference:'R1-B/R1-C'}
    await click('查看全部项目');await click('R1手建A');await visible('项目资料');await click('数据','[aria-label=项目功能] button');await visible('还没有数据表');await capture('r1-b-empty',source)
    for(const [name,description] of [['资料库','存储采集的基础信息'],['较长说明的本地数据表','这是一张用于验证卡片信息和操作对齐的数据表，描述内容跨越两行时底部操作仍应对齐。']]){
      await click('新建数据表');await input('#data-table-name',name);await input('#data-table-description',description);await click('创建数据表');await visible('返回数据表');await click('返回数据表');await visible(name)
    }
    await waitFor(renderer,"!document.querySelector('[role=status][data-tone]')",'正常态通知自然退出');await capture('r1-b-two-local-tables',source);await click('打开资料库');await visible('还没有记录');await click('字段','[role=tab]')
    for(const [name,keyName,type] of [['标题','title','文本'],['文章链接','url','文本'],['发布日期','published','日期'],['已检查','checked','布尔'],['优先级','priority','数字']]){
      await click('新建字段');await input('#field-name',name);await input('#field-key',keyName);if(type!=='文本'){await click('','#field-type');await click(type,'[role=option]')}await click('创建字段');await waitFor(renderer,"!document.querySelector('#field-editor-form')",'field saved')
    }
    await click('状态','[role=tab]');for(const name of ['已核对','待补充']){await click('新建状态');await input('#status-name',name);await click('创建状态');await waitFor(renderer,"!document.querySelector('#status-editor-form')",'status saved')}
    const project=(await api('/projects?q=R1手建A')).items[0],table=(await api(`/projects/${project.projectId}/tables`)).items.find(t=>t.name==='资料库'),base=`/projects/${project.projectId}/tables/${table.tableId}`,fields=(await api(`${base}/fields`)).items
    await click('记录','[role=tab]')
    for(let index=0;index<3;index++){
      await click('新增记录');await visible('新增记录');if(recordPages&&index===0)await capture('r2-create-normal',{stateSource:'ui',navigation:'pointer',level:'E1',reference:'R2-B'})
      for(const field of fields){await click('',`[aria-label="${field.name}值状态"]`);if(index===2&&field.name==='发布日期'){await click('清空','[role=option]');continue}await click('填写值','[role=option]');if(field.type==='boolean'){await click('',`[aria-label="${field.name}"]`);await click(index===0?'是':'否','[role=option]')}else{const value=field.name==='标题'?['温室管理清单','智能温室控制方案🌱','温室种植技术要点'+ 'A'.repeat(100)][index]:field.name==='文章链接'?(index===2?'':`https://example.com/article/${index+1}`):field.type==='date'?'2026-09-13':String(index);await input(`#record-${field.ref.fieldId}`,value)}}
      if(recordPages&&index===0)await capture('r2-create-dirty',{stateSource:'ui',navigation:'keyboard',level:'E1',reference:'R2-B'})
      if(recordPages&&index===0){await renderer.evaluate(`(()=>{const original=window.fetch.bind(window);window.fetch=async(...args)=>{const input=args[0],method=(args[1]?.method??'GET').toUpperCase(),path=typeof input==='string'?input:input.url;if(method==='POST'&&path.includes('/records')){window.fetch=original;const response=await original(...args);await new Promise(resolve=>window.__r2ReleaseWrite=resolve);return response}return original(...args)};true})()`);injections.push({kind:'delayed-real-record-write-response',at:new Date().toISOString(),scope:'E4，仅延迟真实写响应'});await click('创建记录');await visible('正在保存…');await capture('r2-create-saving',{stateSource:'fault-injection',navigation:'pointer',level:'E4',reference:'R2-B',injection:'真实记录POST完成后仅延迟response'});await renderer.evaluate('window.__r2ReleaseWrite();true')}else await click('创建记录')
      await waitFor(renderer,"document.querySelector('[data-record-page=detail]')",'record detail after create');if(recordPages&&index===0)await capture('r2-detail',{stateSource:'ui',navigation:'pointer',level:'E1',reference:'R2-A'});await click('返回记录列表');await waitFor(renderer,"document.querySelector('tbody')",'record list after create')
    }
    await waitFor(renderer,"[...document.querySelectorAll('[role=status][data-tone=success]')].some(e=>e.textContent.includes('记录已创建')&&e.getBoundingClientRect().width>0)",'真实记录创建成功通知');await capture('r1-d-record-created-toast',source);assert.ok(await renderer.evaluate("[...document.querySelectorAll('[role=status][data-tone=success]')].some(e=>e.textContent.includes('记录已创建'))"),'捕获时成功通知仍存在')
    const statusAction=await renderer.evaluate("[...document.querySelectorAll('tbody tr')].find(e=>e.textContent.includes('温室管理清单')).querySelector('[aria-label^=修改状态]').getAttribute('aria-label')")
    await click(statusAction);await click('','[aria-label="记录业务状态"]');await click('已核对','[role=option]');await click('保存状态');await waitFor(renderer,"!document.querySelector('[role=dialog]')",'status saved')
    if(await renderer.evaluate("Boolean(document.querySelector('[data-record-page=detail]'))")){await click('返回记录列表');await waitFor(renderer,"document.querySelector('tbody')",'record list after status')}
    const records=(await api(`${base}/records?datasetGeneration=${table.datasetGeneration}`)).items;assert.equal(records.length,3);assert.equal(records.filter(r=>r.statusId!==null).length,1)
    await waitFor(renderer,"!document.querySelector('[role=status][data-tone]')",'正常态通知自然退出');const tablePoint=await renderer.evaluate("(()=>{const r=document.querySelector('[aria-label^=记录表格]').getBoundingClientRect();return {x:r.left+100,y:r.top+70}})()");await renderer.command('Input.dispatchMouseEvent',{type:'mouseWheel',...tablePoint,deltaX:-2000,deltaY:0});await fits();const identityWidth=await renderer.evaluate("[...document.querySelectorAll('thead th')].find(e=>e.textContent==='记录身份').getBoundingClientRect().width");assert.ok(Math.abs(identityWidth-112)<=1,'记录身份实际宽度112px');await writeFile(join(evidence,'record-identity-geometry.json'),JSON.stringify({identityWidth}));await capture('r1-c-business-records',source);await click('选择本页记录','[role=checkbox]');await visible('已选择 3 条');await capture('r1-c-selected',source);await click('清空选择')
    const mainWidth=await renderer.evaluate("document.querySelector('main').getBoundingClientRect().width")
    for(const [panel,maxWidth] of [['筛选',512],['排序',400],['显示列',288]]){
      await click(panel);const box=await renderer.evaluate("(()=>{const e=document.querySelector('[data-af-popup]'),r=e.getBoundingClientRect();return {width:r.width,height:r.height,viewport:innerHeight,main:document.querySelector('main').getBoundingClientRect().width}})()");assert.ok(box.width<=maxWidth+1);assert.ok(box.height<=box.viewport);assert.ok(Math.abs(box.main-mainWidth)<=1);await writeFile(join(evidence,`popup-${panel}-geometry.json`),JSON.stringify({mainWidth,...box}));await capture(`r1-c-business-${panel}`,source)
      if(panel==='筛选'){
        await click('','[data-af-popup] [role=combobox]');await key('Escape');assert.ok(await renderer.evaluate("Boolean(document.querySelector('[data-af-popup]'))"),'第一Escape保留筛选浮层');await key('Escape');assert.equal(await renderer.evaluate("Boolean(document.querySelector('[data-af-popup]'))"),false);assert.equal(await renderer.evaluate("document.activeElement?.getAttribute('aria-label')"),'筛选')
      }else await key('Escape')
    }
    await click('筛选');await click('添加字段条件');await click('','[aria-label="filter.items.0运算符"]');await click('包含','[role=option]');await input('[id="filter.items.0-value"]','温室');await capture('r1-c-filter-populated',source);await zoom(2);await fits();const footerBox=await renderer.evaluate("(()=>{const e=[...document.querySelectorAll('[data-af-popup] button')].find(e=>e.textContent==='应用筛选'),r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,height:innerHeight}})()");assert.ok(footerBox.top>=0&&footerBox.bottom<=footerBox.height,'200%已配置筛选应用底栏可见');await writeFile(join(evidence,'filter-footer-200.json'),JSON.stringify(footerBox));await capture('r1-c-filter-populated-200',source);await zoom(1);await click('取消','[data-af-popup] button');await click('排序');await click('添加排序');await capture('r1-c-sort-populated',source);await click('取消','[data-af-popup] button')
    await click('显示列');for(const field of fields)await click(field.name,'[data-af-popup] [role=checkbox]');await click('应用显示列','[data-af-popup] button');const zeroWidth=await renderer.evaluate("document.querySelector('thead [data-column-width]').getBoundingClientRect().width");assert.ok(Math.abs(zeroWidth-112)<=1,'零业务列身份宽112px');await capture('r1-c-zero-business-columns',source);await writeFile(join(evidence,'zero-column-geometry.json'),JSON.stringify({identityWidth:zeroWidth}));await click('显示列');for(const field of [...fields].reverse())await click(field.name,'[data-af-popup] [role=checkbox]');await click('应用显示列','[data-af-popup] button');assert.equal(await renderer.evaluate("document.querySelector('[aria-label=显示列]').getAttribute('data-query-applied')"),'false','恢复全部列无误标记')
    checkpoint('E1: UI建立两表、五字段四类型、两业务状态及三条记录；核对实际状态事实，选中/Toast/浮层几何和嵌套Escape截图完成')
    if(recordPages)return {project,table,base,fields,records}
    await click('返回项目目录');await click('返回最近')
  }
  async function recordPagesFlow(){
    const data=await uiDataFlow(),source={stateSource:'ui',navigation:'pointer',level:'E1',reference:'R2-A/R2-B/R2-C'}
    const viewLabel=await renderer.evaluate(`(()=>{const row=[...document.querySelectorAll('tbody tr')].find(e=>e.textContent.includes('温室管理清单'));return row?.querySelector('[aria-label^=查看记录]')?.getAttribute('aria-label')})()`);assert.ok(viewLabel)
    await renderer.evaluate(`(()=>{const original=window.fetch.bind(window);window.fetch=async(...args)=>{const input=args[0],method=(args[1]?.method??'GET').toUpperCase(),path=typeof input==='string'?input:input.url;if(method==='GET'&&path.includes('/records/')){window.fetch=original;await new Promise(resolve=>window.__r2ReleaseRead=resolve)}return original(...args)};true})()`);injections.push({kind:'delayed-real-record-read',at:new Date().toISOString(),scope:'E4，仅延迟真实记录GET'});await click(viewLabel);await visible('正在加载记录');await capture('r2-detail-loading',{stateSource:'fault-injection',navigation:'pointer',level:'E4',reference:'R2-A',injection:'仅延迟真实记录GET'});await renderer.evaluate('window.__r2ReleaseRead();true')
    await visible('记录详情');await waitFor(renderer,"!document.querySelector('[role=status][data-tone]')",'详情正常态通知自然退出');await capture('r2-detail-normal',source)
    await click('编辑记录');await visible('编辑记录');await capture('r2-edit-normal',{...source,reference:'R2-C'});const title=data.fields.find(field=>field.name==='标题');await input(`#record-${title.ref.fieldId}`,'温室管理清单（修订）');await capture('r2-edit-dirty',{...source,reference:'R2-C'});await click('保存修改');await visible('记录详情');await waitFor(renderer,"document.body.innerText.includes('温室管理清单（修订）')",'编辑结果显示')
    await click('','[aria-label="记录业务状态"]');const selectGeometry=await renderer.evaluate(`(()=>{const trigger=document.querySelector('[aria-label="记录业务状态"]'),popup=document.querySelector('[data-af-popup]'),a=trigger.getBoundingClientRect(),b=popup.getBoundingClientRect();return {triggerWidth:a.width,popupWidth:b.width,viewport:innerWidth}})()`);assert.ok(selectGeometry.popupWidth<=selectGeometry.viewport&&selectGeometry.popupWidth>=selectGeometry.triggerWidth-1,'状态Select宽度受视口限制且不窄于触发器');await writeFile(join(evidence,'r2-select-geometry.json'),JSON.stringify(selectGeometry,null,2));await key('Escape');await renderer.evaluate(`document.querySelector('[aria-label="记录业务状态"]').focus()`);await key('Enter');assert.ok(await renderer.evaluate("Boolean(document.querySelector('[data-af-popup]'))"),'键盘打开状态Select');await key('Escape');assert.equal(await renderer.evaluate("document.activeElement?.getAttribute('aria-label')"),'记录业务状态');checkpoint('E1: 状态Select键盘打开、Escape关闭并归还焦点');await click('','[aria-label="记录业务状态"]');await click('待补充','[role=option]');await click('保存状态');await waitFor(renderer,`document.querySelector('[aria-label="记录业务状态"]')?.textContent.includes('待补充')`,'状态保存');await click('清空状态');await waitFor(renderer,`document.querySelector('[aria-label="记录业务状态"]')?.textContent.includes('未设置')`,'状态清空')
    const validHash=await renderer.evaluate('location.hash'),missing=Buffer.from('R2不存在记录','utf8').toString('base64url');await route(`#/projects/${data.project.projectId}/data/${data.table.tableId}/records/${data.table.datasetGeneration}/text/${missing}`);await visible('记录不存在');await capture('r2-detail-404',{stateSource:'direct-route',navigation:'address',level:'E2',reference:'R2-A',fixture:'不存在typed identity'});await route(validHash);await visible('记录详情')
    await click('返回记录列表');await inject('read-error');await click(viewLabel);await waitFor(renderer,"document.querySelector('[data-record-page=detail] [role=alert]')",'记录读取错误');await capture('r2-detail-read-error',{stateSource:'fault-injection',navigation:'pointer',level:'E4',reference:'R2-A',injection:'当前记录真实GET连续读取故障'});await renderer.evaluate('if(window.__r1OriginalFetch)window.fetch=window.__r1OriginalFetch;true');await click('重试');await waitFor(renderer,"document.querySelector('[aria-label=基本信息]')",'记录读取重试恢复')
    await zoom(2);await capture('r2-detail-200',{...source,navigation:'keyboard'});await key('Tab');checkpoint('E1: 200%记录详情可见且键盘焦点可推进');await zoom(1);await click('返回记录列表');checkpoint('E1: UI新增→详情→编辑→保存→状态设置/clear→返回完整记录流程')
    await report('passed');clean=true;console.log(`R2记录页E2E证据（视觉审查pending）：${evidence}`)
  }
  async function competingEdit(){
    const hash=await renderer.evaluate('location.hash'),parts=hash.split('/'),id=parts[2];assert.ok(id,'请先打开要测试的项目')
    if(parts[3]==='data'&&parts[4]){const path=`/projects/${id}/tables/${parts[4]}`,table=await api(path);await api(path,{method:'PATCH',body:{description:`QA竞争编辑 ${Date.now()}`,expectedTableRevision:table.tableRevision}})}
    else{const path=`/projects/${id}`,project=await api(path);await api(path,{method:'PATCH',body:{description:`QA竞争编辑 ${Date.now()}`,expectedManagementRevision:project.managementRevision}})}
    checkpoint('隔离API真实竞争编辑已提交；保留当前表单草稿后点击保存验证冲突')
  }
  async function competingRecordEdit(){
    const hash=await renderer.evaluate('location.hash'),parts=hash.replace(/^#\//,'').split('/');assert.ok(parts[4]==='records'&&parts[7],'请先打开记录详情或编辑页')
    const [projectId,tableId,generation,type,key]=[parts[1],parts[3],parts[5],parts[6],parts[7]],base=`/projects/${projectId}/tables/${tableId}`,record=await api(`${base}/records/${key}?datasetGeneration=${generation}&recordKeyType=${type}`),fields=(await api(`${base}/fields`)).items
    const field=fields.find(item=>item.writable&&!item.formula&&record.values.find(value=>value.fieldId===item.ref.fieldId)?.readable!==false);assert.ok(field,'当前记录没有可竞争修改字段');await api(`${base}/records/${key}`,{method:'PATCH',body:{datasetGeneration:generation,recordKeyType:type,expectedContentRevision:record.contentRevision,values:[{fieldId:field.ref.fieldId,value:`QA竞争记录 ${Date.now()}`}]}});checkpoint('E2: 隔离API完成记录竞争修改；当前UI草稿仍保留待保存')
  }
  async function injectReadonly(){
    await renderer.evaluate(`(()=>{const original=window.__r1OriginalFetch??window.fetch.bind(window);window.__r1OriginalFetch=original;window.fetch=async(input,init)=>{const method=(init?.method??'GET').toUpperCase();if(['POST','PATCH','PUT','DELETE'].includes(method))return new Response(JSON.stringify({detail:'R2 QA 只读注入'}),{status:403,headers:{'content-type':'application/json'}});return original(input,init)};true})()`);injections.push({kind:'readonly-write-rejection',at:new Date().toISOString(),scope:'E4，仅当前隔离renderer拦截写请求'});console.log('E4只读写拒绝已注入；restore 恢复真实fetch。')
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
    await launch();
    if(!manual){
      await renderer.command('Emulation.setDeviceMetricsOverride',{width:1440,height:1024,deviceScaleFactor:1,mobile:false});await wait(100)
      assert.deepEqual(await renderer.evaluate('({w:innerWidth,h:innerHeight})'),{w:1440,h:1024},'实际renderer视口基准')
    }
    if(!manual)await renderer.evaluate(`(()=>{const original=window.fetch.bind(window);window.__r1ReleaseRead=null;window.fetch=async(...args)=>{const input=args[0],path=typeof input==='string'?input:input.url;if(path.includes('/api/v1/projects')){window.fetch=original;await new Promise(resolve=>window.__r1ReleaseRead=resolve)}return original(...args)};return true})()`)
    await click('项目','[aria-label=全局导航] button');if(!manual){await visible('正在加载项目');await capture('r1-a-loading',{stateSource:'fault-injection',navigation:'pointer',level:'E4',reference:'R1-A',injection:'仅延迟首次真实项目GET；释放后请求真实后端，不伪造响应'});await renderer.evaluate('window.__r1ReleaseRead();true')}await visible('尚无最近访问');await capture('r1-a-empty',{stateSource:'ui',navigation:'pointer',level:'E1',reference:'R1-A'})
    if(visualDirectory){await visualDirectoryFlow();return}
    if(manual){
      console.log(`R1/R2 隔离应用已打开。测试目录：${owner}\n证据：${evidence}\n命令：seed（52/120资料，仅一次）、fixture（打开分页表）、conflict、recordconflict（当前记录竞争修改，E2）、readonly（写请求只读拒绝，E4）、readfail（一次失败自动重试）、readerror（本轮含重试均失败）、lost、restore（恢复fetch）、service、restart、switch、shot、entries（其他模块入口回归）、zoom200、zoom100、quit（保留目录）、clean（退出并清理本次目录）`)
      const lines=createInterface({input:process.stdin,output:process.stdout})
      for await(const raw of lines){const command=raw.trim();try{
        if(command==='seed'){if(fixture)console.log('本次已生成');else await seed()}
        else if(command==='fixture'){assert.ok(fixture,'请先seed');await route(`#/projects/${fixture.project.projectId}/data/${fixture.table.tableId}/records`)}
        else if(command==='conflict')await competingEdit()
        else if(command==='recordconflict')await competingRecordEdit()
        else if(command==='readonly')await injectReadonly()
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
    const recent=await renderer.evaluate("[...document.querySelectorAll('[aria-label=项目目录] article')].map(e=>e.innerText)");assert.ok(recent[0].includes('R1手建B'));assert.ok(recent[1].includes('R1手建A'));await capture('r1-a-recent',{stateSource:'ui',navigation:'pointer',level:'E1',reference:'R1-A'});checkpoint('UI创建A/B并依次打开，最近B在A之前')
    if(recordPages){await recordPagesFlow();return}
    await uiDataFlow();await seed();await click('查看全部项目');await input('[aria-label=搜索项目]','R1分页');await waitFor(renderer,"document.querySelectorAll('[aria-label=项目目录] article').length===50",'50 server paginated cards');await click('下一页');await waitFor(renderer,"document.querySelectorAll('[aria-label=项目目录] article').length===2",'second page');await capture('r1-a-all-page2',{stateSource:'ui-with-api-fixture',navigation:'pointer',level:'E1',setupLevel:'E2',reference:'R1-A'});checkpoint('真实目录服务端分页50/2')
    await input('[aria-label=搜索项目]','R1分页001');await click('R1分页001');await visible('项目资料');await click('数据','[aria-label=项目功能] button');await visible('分页资料库');await capture('r1-b-directory',{stateSource:'ui-with-api-fixture',navigation:'pointer',level:'E1',setupLevel:'E2',reference:'R1-B'});await click('打开分页资料库');await visible('温室资料');await fits();assert.ok(await renderer.evaluate("document.querySelector('thead').getBoundingClientRect().top<=380"),'记录表头位于紧凑预算内');await capture('r1-c-records',{stateSource:'ui-with-api-fixture',navigation:'pointer',level:'E1',setupLevel:'E2',reference:'R1-C'})
    const before=await renderer.evaluate('document.querySelector("tbody")?.innerText')
    await input('[aria-label=文本搜索]','温室');assert.equal(await renderer.evaluate('document.querySelector("tbody")?.innerText'),before);await click('搜索记录');await waitFor(renderer,"document.querySelector('tbody')?.innerText.includes('温室资料')&&!document.querySelector('tbody')?.innerText.includes('花园资料')",'applied contains search');checkpoint('指定文本字段输入不查询，提交后筛选实际记录')
    const exportPath=join(owner,'text-search.xlsx');await native.evaluate(`qaElectron.dialog.showSaveDialog=async()=>({canceled:false,filePath:${JSON.stringify(exportPath)}});true`)
    injections.push({kind:'save-dialog-selection',at:new Date().toISOString(),scope:'系统保存面板返回测试路径；真实文件IPC与写出'})
    await click('导出 Excel');await click('导出范围','[aria-label=导出范围]');await click('当前筛选结果','[role=option]');await click('选择保存位置');await waitFor(renderer,"!document.querySelector('[role=dialog]')",'search export completes',30000)
    const {stdout}=await promisify(execFile)('uv',['run','--project',join(root,'apps/backend'),'python','-c',`from openpyxl import load_workbook; import json; b=load_workbook(${JSON.stringify(exportPath)},read_only=True,data_only=True); print(json.dumps(list(b.active.values),ensure_ascii=False))`]);const exported=JSON.parse(stdout);assert.equal(exported.length,61);assert.ok(exported.slice(1).every(row=>row[0].startsWith('温室')));checkpoint('当前筛选导出真实XLSX为60条温室记录，与快捷搜索条件一致')
    for(const panel of ['筛选','排序','显示列']){await click(panel);await capture(`r1-c-${panel}`,{stateSource:'ui-with-api-fixture',navigation:'pointer',level:'E1',setupLevel:'E2',reference:'R1-C'});await fits();await key('Escape');assert.equal(await renderer.evaluate('Boolean(document.querySelector("[data-af-popup]"))'),false)}
    await click('显示列');await click('标题','[role=checkbox]');await click('取消');assert.ok(await renderer.evaluate("[...document.querySelectorAll('th')].some(e=>e.innerText==='标题')"));await click('显示列');await click('标题','[role=checkbox]');await click('应用显示列');assert.equal(await renderer.evaluate("[...document.querySelectorAll('th')].some(e=>e.innerText==='标题')"),false);checkpoint('选列取消不生效、应用后隐藏字段')
    await click('显示列');await click('标题','[role=checkbox]');await click('应用显示列');await zoom(2);await fits();for(const panel of ['筛选','排序','显示列']){await click(panel);await fits();await capture(`r1-c-${panel}-200`,{stateSource:'ui-with-api-fixture',navigation:'pointer',level:'E1',setupLevel:'E2',reference:'R1-C'});await key('Escape')}await zoom(1);checkpoint('1440×1024及200%三个查询浮层无应用横向撑宽')
    await restartService();await visible('温室资料');await shutdown();await launch();await click('项目','[aria-label=全局导航] button');await visible('最近打开');await capture('r1-after-restart');checkpoint('Electron完整重启后最近访问事实持久化')
    await switchWorkspace();assert.equal((await api('/projects')).total,0);await switchWorkspace();assert.equal((await api('/projects')).total,54);checkpoint('两个真实工作区隔离并切回恢复54个项目')
    await route('#/projects');await visible('最近打开');const savedContent=await renderer.evaluate("[...document.querySelectorAll('[aria-label=项目目录] article')].map(e=>e.innerText).join('')")
    await inject('read');await click('刷新');await waitFor(renderer,'window.__r1InjectedCount===1','one failed read');await wait(3500);checkpoint('一次读取故障由现有自动重试恢复，保留旧目录内容');await inject('read-error');await click('刷新');await visible('刷新最近项目失败');assert.equal(await renderer.evaluate("[...document.querySelectorAll('[aria-label=项目目录] article')].map(e=>e.innerText).join('')"),savedContent);await capture('r1-read-failure',{stateSource:'fault-injection',navigation:'pointer',level:'E4',reference:'R1-A',injection:'读取故障注入'});await click('刷新');await waitFor(renderer,"!document.body.innerText.includes('刷新最近项目失败')",'read retry')
    await inject('lost');await click('新建项目');await input('#project-name','R1响应丢失');await click('创建项目');await visible('核对保存结果');assert.equal((await api('/projects?q=R1响应丢失')).total,1);await capture('r1-lost-response',{stateSource:'fault-injection',navigation:'pointer',level:'E4',reference:'R1-A',injection:'提交后响应丢失注入'});await click('核对保存结果');await visible('项目资料');assert.equal((await api('/projects?q=R1响应丢失')).total,1);checkpoint('一次读取失败保留旧目录；提交响应丢失后用原操作核验，只有一个项目事实')
    await click('编辑项目');await input('#project-description','我的未保存草稿');await competingEdit();await click('保存');await visible('基于最新内容重新编辑');assert.equal(await renderer.evaluate("document.querySelector('#project-description').value"),'我的未保存草稿');await capture('r1-real-conflict',{stateSource:'ui-with-api-competition',navigation:'pointer',level:'E1',setupLevel:'E2',reference:'R1-A'});await click('基于最新内容重新编辑');await input('#project-description','冲突处理后保存');await click('保存');await waitFor(renderer,"!document.querySelector('#project-form')",'conflict saved');checkpoint('真实竞争编辑发生409，保留输入，基于最新内容重新编辑后保存')
    await report('passed');clean=true;console.log(`R1自动验收证据：${evidence}`)
  }catch(error){try{await capture('failure');await writeFile(join(evidence,'failure-dom.json'),JSON.stringify(await renderer.evaluate("({bodyStyle:document.body.getAttribute('style'),buttons:[...document.querySelectorAll('button')].map(e=>{const r=e.getBoundingClientRect();return {name:e.getAttribute('aria-label')||e.textContent,disabled:e.disabled,rect:{x:r.x,y:r.y,w:r.width,h:r.height},hit:document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)?.outerHTML.slice(0,250)}})})"),null,2))}catch{}await report('failed',String(error.message).replaceAll(owner,'<qa-workspace>'));throw error}
  finally{await shutdown();if(clean){await assertOwnedWorkspace(owner,owner);await rm(owner,{recursive:true,force:true})}else console.log(`保留隔离资料 ${owner}；截图报告始终保留 ${evidence}`)}
}
if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href)main().catch(error=>{console.error(error);process.exitCode=1})
