import assert from 'node:assert/strict'
import { createHash, randomUUID } from 'node:crypto'
import { execFile } from 'node:child_process'
import { readFile, readdir, mkdtemp, mkdir, realpath, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { promisify } from 'node:util'
import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const run = promisify(execFile), root = resolve(import.meta.dirname, '..')
const nativeMode = process.argv.includes('--native')
const pickerMode = nativeMode ? 'native-dialogs-external-operator' : 'injected-dialog-results-E4'
const evidenceRoot = join(root, 'docs/migration/pm2-detail-qa'); await mkdir(evidenceRoot, { recursive: true })
const qa = await mkdtemp(join(evidenceRoot, 'run-')), workspace = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-pm2-detail-')))
const original = join(workspace, 'original.xlsx'), replacement = join(workspace, 'replacement.xlsx'), output = join(workspace, 'filtered.xlsx')
const large = join(workspace, 'large-10000.xlsx')
await writeFile(join(workspace, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await workbook(original, [['姓名','编号','城市'],['Alice','001','上海'],['Bob','002','北京'],['Amy','003','深圳']])
await workbook(replacement, [['姓名','编号','城市'],['Alice 新','001','杭州'],['Bob 新','002','北京'],['Amy 新','003','深圳']])
const sourceDigest = await digest(original), checks = [], captures = []
const { stdout: gitHead } = await run('git', ['rev-parse', 'HEAD'], { cwd: root })
const buildHash = createHash('sha256'), buildRoot = join(root, 'apps/desktop/out')
for (const name of (await readdir(buildRoot, { recursive: true })).filter(name => /\.(js|css|html)$/.test(name)).sort()) buildHash.update(name).update(await readFile(join(buildRoot, name)))
const provenance = { gitHead: gitHead.trim(), desktopBuildSha256: buildHash.digest('hex'), scriptSha256: await digest(new URL(import.meta.url)) }
let desktop, renderer, native, projectId, tableId
try {
  await launch(); await visible('本地服务正常', 30000)
  projectId = (await api('/projects', { method: 'POST', body: { name: 'PM2 详情验收', description: '' } })).projectId
  await renderer.evaluate(`location.hash=${JSON.stringify(`#/projects/${projectId}/data`)}`); await visible('还没有数据表')
  await setPicker(original, output); await createTable('详情流程表')
  let table = await onlyTable(); tableId = table.tableId
  await openDetail(); await createStatus('已核对')
  await selectPage(); await click('批量设置状态'); await select('目标状态', '已核对'); await click('预检批量状态'); await click('确认开始'); await terminal()
  let records = await recordFacts(); assert.equal(records.length, 3); assert.ok(records.every(value => value.statusId))
  checkpoint('selected the current page in the real table UI and durably set every record status')
  await closeDialog(); await selectPage(); await click('批量设置状态'); await click('预检批量状态'); await click('确认开始'); await terminal()
  records = await recordFacts(); assert.ok(records.every(value => value.statusId === null)); checkpoint('cleared the same frozen selection status and verified status facts through GET')

  await closeDialog(); await applyNameFilter('A'); await click('导出 Excel'); await select('导出范围', '当前筛选结果')
  await click('编号', '[aria-label="编号"]'); await click('城市', '[aria-label="城市"]'); await click('包含业务状态', '[aria-label="包含业务状态"]')
  await setZoom(2); await assertDialogFits('export-200-percent'); await setZoom(1)
  await click('选择保存位置'); await workflowClosed('导出 Excel', 30000); await verifyExport(output, ['Alice','Amy']); checkpoint('exported the applied filter with one selected data column and verified the XLSX independently with openpyxl')
  await closeDialog(); await click('导出 Excel'); await click('选择保存位置'); await visible('导出目标已存在'); checkpoint('a repeated save target was rejected instead of overwriting the first export')
  await closeDialog(); await selectPage(); await click('批量设置状态'); await select('目标状态','已核对'); await click('预检批量状态'); await click('确认开始'); await terminal(); await closeDialog()
  records=await recordFacts(); assert.equal(records.filter(value=>value.statusId).length,2); const oldRef=records[0].ref
  await setPicker(replacement, output); table = await onlyTable(); const oldGeneration = table.datasetGeneration
  await click('重新导入 Excel'); await visible('用 Excel 替换数据表'); await setZoom(2); await assertDialogFits('replace-200-percent'); await setZoom(1); await chooseExcelFile(); await click('检查文件'); await select('工作表', '客户'); await click('继续字段映射'); await selectAt('列映射',0,'现有字段：姓名'); await selectAt('列映射',1,'现有字段：编号'); await selectAt('列映射',2,'现有字段：城市'); await click('继续导入'); await visible('3 条原记录将被替换。'); await click('确认并开始导入'); await waitFor(renderer,`Object.keys(localStorage).some(key=>key.startsWith('autoflow:excel-import:'))`,'durable replace identity after click',3000); await workflowClosed('用 Excel 替换数据表', 30000)
  table = await onlyTable(); assert.notEqual(table.datasetGeneration, oldGeneration); assert.equal(await digest(original), sourceDigest)
  records = await recordFacts(); assert.deepEqual(records.map(value => value.values[0]?.value).sort(), ['Alice 新','Amy 新','Bob 新']); assert.ok(records.every(value=>value.statusId===null))
  const stale=await apiResponse(`/projects/${projectId}/tables/${tableId}/records/${base64url(oldRef.recordKey.value)}?datasetGeneration=${encodeURIComponent(oldGeneration)}&recordKeyType=${oldRef.recordKey.type}`); assert.equal(stale.status,410)
  checkpoint('replaced through explicit existing-field mapping and impact review; generation advanced, statuses reset, the old generation/key returned 410, and the source workbook stayed byte-identical')

  renderer.close(); native.close(); await stop(desktop.child); desktop = renderer = native = undefined
  await launch(); await visible('本地服务正常', 30000); table = await onlyTable(); assert.equal(table.tableId, tableId); await openDetail(); await visible('Alice 新')
  assert.deepEqual((await recordFacts()).map(value => value.values[0]?.value).sort(), ['Alice 新','Amy 新','Bob 新'])
  checkpoint('a fresh Electron and sidecar instance returned the durable replacement and export-era table facts')
  await capture('detail-after-reconnect')
  await largeWorkbook(large); await setPicker(large, output); await renderer.evaluate(`location.hash=${JSON.stringify(`#/projects/${projectId}/data`)}`); await visible('详情流程表')
  const started=performance.now(); await createTable('一万行性能表','数据'); const importMs=Math.round(performance.now()-started)
  const largeTable=(await api(`/projects/${projectId}/tables`)).items.find(value=>value.name==='一万行性能表'); assert.ok(largeTable); assert.equal(largeTable.recordCount,10000)
  tableId=largeTable.tableId; await openDetail('一万行性能表'); await waitFor(renderer,`document.querySelectorAll('tbody tr [aria-label^=编辑记录]').length===50`,'first 50-row page',30000)
  const first=await renderer.evaluate(`document.querySelector('tbody tr')?.innerText`); const pageStarted=performance.now(); await click('下一页'); await waitFor(renderer,`document.querySelectorAll('tbody tr [aria-label^=编辑记录]').length===50&&document.querySelector('tbody tr')?.innerText!==${JSON.stringify(first)}`,'second 50-row page'); const pageMs=Math.round(performance.now()-pageStarted)
  const layout=await renderer.evaluate(`(()=>{const cell=[...document.querySelectorAll('tbody td')].find(e=>e.innerText.includes('记录'));const text=cell?.querySelector('[title]');return{pageFits:document.documentElement.scrollWidth<=innerWidth+1,truncated:Boolean(text&&text.scrollWidth>text.clientWidth)}})()`); assert.equal(layout.pageFits,true); assert.equal(layout.truncated,true); await capture('large-10000-second-page')
  checkpoint(`imported an actual 10000-row workbook through the directory UI in ${importMs} ms; rendered 50 rows per page and changed the first row on next-page navigation in ${pageMs} ms`)
  const report = { result: 'passed', checkedAt: new Date().toISOString(), pickerMode, provenance, captureMetadata: 'capture-metadata.json', scope: nativeMode ? 'PM2 detail flows; original system open/save dialogs retained for external operator interaction, renderer UI, IPC proof, HTTP, SQLite and workbook I/O real' : 'PM2 detail flows; system open/save panel results injected, renderer UI, IPC proof, HTTP, SQLite and workbook I/O real', checks, excluded: nativeMode ? ['user-performed manual acceptance; native dialogs operated separately by the coordinator'] : ['manual native file-panel interaction'] }
  await writeFile(join(qa, 'result.json'), JSON.stringify(report, null, 2) + '\n'); console.log(JSON.stringify({ evidence: qa.replace(root, '.'), ...report }, null, 2))
} catch (error) {
  try { await capture('failure') } catch {}
  const message = String(error?.message ?? error).replaceAll(workspace, '<temporary-workspace>').replaceAll(root, '<repository>')
  await writeFile(join(qa, 'failure.json'), JSON.stringify({ result: 'failed', checkedAt: new Date().toISOString(), pickerMode, provenance, captureMetadata: captures.length ? 'capture-metadata.json' : null, checks, error: message }, null, 2) + '\n'); throw error
} finally { renderer?.close(); native?.close(); await stop(desktop?.child); await rm(workspace, { recursive: true, force: true }) }

async function launch() { desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${workspace}`, '--inspect=0'], cliArgs: [] }); renderer = desktop.cdp; native = await connectCdp(desktop.inspectorUrl); await native.evaluate("globalThis.qaElectron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');true") }
async function setPicker(input, save) { if (nativeMode) { console.log(JSON.stringify({ event: 'native-file-panel-targets', pickerMode, input, save, pid: desktop.child.pid })); return } await native.evaluate(`qaElectron.dialog.showOpenDialog=async()=>({canceled:false,filePaths:[${JSON.stringify(input)}]});qaElectron.dialog.showSaveDialog=async()=>({canceled:false,filePath:${JSON.stringify(save)}});true`) }
async function createTable(name,sheet='客户') { await click('从 Excel 导入'); await chooseExcelFile(); await click('检查文件'); await select('工作表',sheet); await click('继续字段映射'); await click('继续导入'); await input('[aria-label="数据表名称"]',name); await click('确认并开始导入'); await waitFor(renderer, `!document.body.innerText.includes('从 Excel 新建数据表')&&document.body.innerText.includes(${JSON.stringify(name)})`, name, 30000) }
async function chooseExcelFile() { const label=await renderer.evaluate(`document.body.innerText.includes('重新选择文件')?'重新选择文件':'选择 Excel 文件'`); await click(label) }
async function openDetail(name='详情流程表') { await renderer.evaluate(`location.hash=${JSON.stringify(`#/projects/${projectId}/data/${tableId}/records`)}`); await visible(name) }
async function createStatus(name) { await click('状态','[role=tab]'); await click('新增状态'); await input('#status-name',name); await click('创建状态'); await waitFor(renderer,"!document.querySelector('#status-editor-form')",'status creation confirmed'); await visible(name); const saved=(await api(`/projects/${projectId}/tables/${tableId}/statuses`)).items.find(status=>status.name===name); assert.ok(saved,'created status is persisted'); await click('记录','[role=tab]') }
async function selectPage() { await waitFor(renderer, `(()=>{const e=document.querySelector('[aria-label="选择本页记录"]');return Boolean(e&&!e.disabled&&e.getAttribute('aria-disabled')!=='true')})()`, 'selectable current record page'); await click('选择本页记录', '[aria-label="选择本页记录"]') }
async function applyNameFilter(value) { await click('筛选'); await click('高级条件'); await click('添加字段条件'); await inputLabel('比较值',value); await select('filter.items.0运算符','开头是'); await click('应用筛选'); await wait(300) }
async function onlyTable() { const items=(await api(`/projects/${projectId}/tables`)).items; assert.equal(items.length,1); return items[0] }
async function recordFacts() { const table=await onlyTable(); return (await api(`/projects/${projectId}/tables/${tableId}/records?datasetGeneration=${table.datasetGeneration}`)).items }
async function terminal(timeout=20000) { await waitFor(renderer, `document.body.innerText.includes('操作已完成')||document.body.innerText.includes('操作未全部完成')`, 'terminal operation', timeout); assert.ok(await renderer.evaluate(`document.body.innerText.includes('操作已完成')`)); await capture(`terminal-${checks.length}`) }
async function closeDialog() { if(await renderer.evaluate(`Boolean(document.querySelector('[role=dialog] [aria-label="关闭"]'))`)) await click('关闭','[role=dialog] [aria-label="关闭"]'); else if(await renderer.evaluate(`Boolean([...document.querySelectorAll('[role=dialog] button')].find(x=>x.textContent.trim()==='关闭'&&x.getClientRects().length))`)) await click('关闭','[role=dialog] button'); else { await renderer.command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'}); await renderer.command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape'}); await waitFor(renderer,`!document.querySelector('[role=dialog]')`,'dialog closes with Escape') } }
async function api(path, options={}) { const {sidecar}=await renderer.evaluate('window.autoflow.getRuntimeContext()'); const response=await fetch(`${sidecar.baseUrl}/api/v1${path}`,{...options,body:options.body?JSON.stringify(options.body):undefined,headers:{'x-autoflow-token':sidecar.token,'content-type':'application/json','Idempotency-Key':randomUUID()}}); assert.ok(response.ok,`${options.method??'GET'} ${path}: ${response.status}`); return response.json() }
async function apiResponse(path) { const {sidecar}=await renderer.evaluate('window.autoflow.getRuntimeContext()'); return fetch(`${sidecar.baseUrl}/api/v1${path}`,{headers:{'x-autoflow-token':sidecar.token}}) }
async function workbook(path, rows) { await run('uv',['run','--project',join(root,'apps/backend'),'python','-c',`from openpyxl import Workbook; b=Workbook(); s=b.active; s.title='客户'; [s.append(r) for r in ${JSON.stringify(rows)}]; b.save(${JSON.stringify(path)})`]) }
async function largeWorkbook(path) { await run('uv',['run','--project',join(root,'apps/backend'),'python','-c',`from openpyxl import Workbook; b=Workbook(write_only=True); s=b.create_sheet('数据'); s.append(['长文本']); [s.append([(('记录%05d-'%i)+'长'*240)]) for i in range(10000)]; b.save(${JSON.stringify(path)})`]) }
async function verifyExport(path, expectedNames) { const {stdout}=await run('uv',['run','--project',join(root,'apps/backend'),'python','-c',`from openpyxl import load_workbook; import json; s=load_workbook(${JSON.stringify(path)},read_only=True,data_only=True).active; print(json.dumps([list(r) for r in s.iter_rows(values_only=True)],ensure_ascii=False))`]), rows=JSON.parse(stdout); assert.deepEqual(rows[0],['姓名']); assert.deepEqual(rows.slice(1).map(row=>row[0]).sort(),[...expectedNames].sort()) }
async function digest(path) { return createHash('sha256').update(await readFile(path)).digest('hex') }
function base64url(value) { return Buffer.from(value,'utf8').toString('base64url') }
function checkpoint(value) { checks.push(value); console.log(value) }
async function visible(text,timeout=15000) { if(nativeMode&&text==='导出目标已存在')timeout=Math.max(timeout,180000); if(text==='返回数据表')return waitFor(renderer,"!!document.querySelector('[aria-label=返回数据表]')",text,timeout); return waitFor(renderer,`document.body?.innerText.includes(${JSON.stringify(text)})`,text,timeout) }
async function click(text,selector='button') { if(selector==='[role=tab]')text=({记录:'数据记录',字段:'字段与校验',状态:'数据状态',来源:'来源设置',设置:'数据表设置'})[text]??text; if(selector==='button' && ['批量设置状态','导出 Excel','重新导入 Excel'].includes(text) && await renderer.evaluate("!!document.querySelector('[aria-label=更多操作]')")){await click('更多操作');selector='[role=menuitem]'} const expression=`(()=>{const e=[...document.querySelectorAll(${JSON.stringify(selector)})].find(x=>(x.textContent.trim()===${JSON.stringify(text)}||x.getAttribute('aria-label')===${JSON.stringify(text)})&&x.getClientRects().length&&!x.disabled&&x.getAttribute('aria-disabled')!=='true');if(!e)return null;e.scrollIntoView({block:'center',inline:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2,hit=document.elementFromPoint(x,y);return hit&&(hit===e||e.contains(hit))?{x,y}:null})()`; const point=await waitFor(renderer,expression,`clickable ${text}`,nativeMode&&text==='检查文件'?180000:7000); await renderer.command('Input.dispatchMouseEvent',{type:'mouseMoved',...point}); await renderer.command('Input.dispatchMouseEvent',{type:'mousePressed',...point,button:'left',clickCount:1}); await renderer.command('Input.dispatchMouseEvent',{type:'mouseReleased',...point,button:'left',clickCount:1}); await wait(150) }
async function input(selector,value) { assert.equal(await renderer.evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)return false;e.focus();const p=e instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(p,'value').set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}));return true})()`),true); await wait(100) }
async function inputLabel(label,value) { const selector=await renderer.evaluate(`(()=>{const e=[...document.querySelectorAll('label')].find(x=>x.textContent.trim().startsWith(${JSON.stringify(label)}));return e?.htmlFor?'#'+CSS.escape(e.htmlFor):null})()`); assert.ok(selector,`input label missing: ${label}`); await input(selector,value) }
async function select(label,option) { await click(label,`[aria-label=${JSON.stringify(label)}]`); const point=await renderer.evaluate(`(()=>{const e=[...document.querySelectorAll('[role=option]')].find(x=>x.textContent.includes(${JSON.stringify(option)})&&x.getClientRects().length);if(!e)return null;const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`); assert.ok(point,`option missing: ${option}`); await renderer.command('Input.dispatchMouseEvent',{type:'mouseMoved',...point}); await renderer.command('Input.dispatchMouseEvent',{type:'mousePressed',...point,button:'left',clickCount:1}); await renderer.command('Input.dispatchMouseEvent',{type:'mouseReleased',...point,button:'left',clickCount:1}); await wait(120) }
async function selectAt(label,index,option) { const point=await waitFor(renderer,`(()=>{const e=[...document.querySelectorAll('[aria-label=${label}]')][${index}];if(!e)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`,`select ${label} ${index}`); await renderer.command('Input.dispatchMouseEvent',{type:'mouseMoved',...point}); await renderer.command('Input.dispatchMouseEvent',{type:'mousePressed',...point,button:'left',clickCount:1}); await renderer.command('Input.dispatchMouseEvent',{type:'mouseReleased',...point,button:'left',clickCount:1}); await wait(120); const choice=await waitFor(renderer,`(()=>{const e=[...document.querySelectorAll('[role=option]')].find(x=>x.textContent.includes(${JSON.stringify(option)})&&x.getClientRects().length);if(!e)return null;const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`,`option ${option}`); await renderer.command('Input.dispatchMouseEvent',{type:'mouseMoved',...choice}); await renderer.command('Input.dispatchMouseEvent',{type:'mousePressed',...choice,button:'left',clickCount:1}); await renderer.command('Input.dispatchMouseEvent',{type:'mouseReleased',...choice,button:'left',clickCount:1}); await wait(120) }
async function capture(name) {
  if (!renderer) return
  const actual = await renderer.evaluate(`({route:location.hash,viewport:{width:innerWidth,height:innerHeight},dpr:devicePixelRatio,fonts:{status:document.fonts.status,bodyFontFamily:getComputedStyle(document.body).fontFamily,bodyFontSize:getComputedStyle(document.body).fontSize}})`)
  const windowState = await native.evaluate(`(()=>{const wc=qaElectron.webContents.getAllWebContents().find(x=>x.getType()==='window');return {zoom:wc.getZoomFactor(),windowContentBounds:qaElectron.BrowserWindow.fromWebContents(wc).getContentBounds()}})()`)
  const { data } = await renderer.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }), png = Buffer.from(data, 'base64'), file = `${name}.png`
  await writeFile(join(qa, file), png)
  captures.push({ file, capturedAt: new Date().toISOString(), ...actual, ...windowState, image: { width: png.readUInt32BE(16), height: png.readUInt32BE(20), sha256: createHash('sha256').update(png).digest('hex') } })
  await writeFile(join(qa, 'capture-metadata.json'), JSON.stringify({ provenance, pickerMode, captures }, null, 2) + '\n')
}
async function workflowClosed(title,timeout) { await waitFor(renderer,`!document.querySelector('[role=dialog]')`,`${title} closes after success`,nativeMode&&title==='导出 Excel'?Math.max(timeout??0,180000):timeout) }
async function setZoom(factor) { await native.evaluate(`(()=>{const wc=qaElectron.webContents.getAllWebContents().find(x=>x.getType()==='window');if(!wc)return false;wc.setZoomFactor(${factor});return true})()`); await renderer.evaluate(`new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`); await waitFor(renderer,`innerWidth>${factor===1?1200:600}`,'zoomed viewport settles'); await wait(250) }
async function assertDialogFits(name) { const value=await renderer.evaluate(`(()=>{const e=document.querySelector('[role=dialog]'),r=e?.getBoundingClientRect(),region=e?.querySelector('[role=region]');return{viewport:innerWidth,page:document.documentElement.scrollWidth,left:r?.left,right:r?.right,internalScroll:Boolean(region&&['auto','scroll'].includes(getComputedStyle(region).overflowY))}})()`); assert.ok(value.page<=value.viewport+1,`${name} page overflow: ${JSON.stringify(value)}`); assert.ok(value.left>=-1&&value.right<=value.viewport+1,`${name} dialog overflow: ${JSON.stringify(value)}`); assert.ok(value.internalScroll,`${name} dialog lacks its internal vertical scroll region`); await capture(name) }
