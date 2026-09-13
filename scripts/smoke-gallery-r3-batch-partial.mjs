import assert from 'node:assert/strict'
import { createHash, randomUUID } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { cp, readFile, readdir, mkdtemp, mkdir, realpath, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

// E2: HTTP scale fixture and competing edit; selection, preview, acceptance and recovery use actual UI.
const root = resolve(import.meta.dirname, '..'), nativeMode = false
const evidenceRoot = join(root, 'docs/project-management/design-alignment/acceptance/gallery-r3/batch-partial')
await mkdir(evidenceRoot, { recursive: true })
const qa = await mkdtemp(join(evidenceRoot, 'run-'))
const workspace = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-r3-batch-')))
await writeFile(join(workspace, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await writeFile(join(workspace, 'desktop-settings.json'), JSON.stringify({ schemaVersion: 1, currentPath: workspace, previousPath: null, preferences: { zoom: 100, motion: 'system' } }))
const checks = [], captures = [], requests = []
const hash = createHash('sha256')
for (const file of (await readdir(join(root, 'apps/desktop/out'), { recursive: true })).filter(f => /\.(js|css|html)$/.test(f)).sort()) hash.update(file).update(await readFile(join(root, 'apps/desktop/out', file)))
const provenance = { gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(), buildSha256: hash.digest('hex'), scriptSha256: createHash('sha256').update(await readFile(new URL(import.meta.url))).digest('hex') }
let desktop, renderer, native, base, projectId, tableId, generation
try {
  await launch()
  projectId = (await api('/projects', { method: 'POST', body: { name: '批量部分冲突 E2', description: '专用临时工作区真实规模 fixture' } })).projectId
  let table = await api(`/projects/${projectId}/tables`, { method: 'POST', body: { name: '120 条分块核验', description: '真实 UI 冻结选择与预检后竞争', sourceKind: 'local' } })
  tableId = table.tableId; generation = table.datasetGeneration; base = `/projects/${projectId}/tables/${tableId}`
  const field = (await api(`${base}/fields`, { method: 'POST', body: { definition: { key: 'name', name: '测试名称', type: 'string', required: false, validation: {} }, expectedTableRevision: table.tableRevision, sourceColumnPolicy: 'localOnly' } })).field
  const statuses = []
  for (const [order, name] of ['目标状态', '并发状态'].entries()) {
    table = await api(base)
    statuses.push((await api(`${base}/statuses`, { method: 'POST', body: { name, color: order ? '#ef4444' : '#22c55e', order, expectedTableRevision: table.tableRevision } })))
  }
  for (let index = 1; index <= 120; index++) await api(`${base}/records`, { method: 'POST', body: { datasetGeneration: generation, values: [{ fieldId: field.ref.fieldId, value: `批量记录 ${String(index).padStart(3, '0')}` }] } })
  checkpoint('E2 real HTTP fixture: project, local table, one field, two statuses and 120 records')
  await openTable()
  for (const [index, rows] of [50, 50, 20].entries()) {
    await waitFor(renderer, `document.querySelectorAll('tbody tr').length===${rows}`, `page ${index + 1} row count`)
    await click('选择本页记录', '[aria-label="选择本页记录"]')
    await visible(`已选择 ${Math.min((index + 1) * 50, 120)} 条`)
    if (index < 2) await click('下一页')
  }
  await click('批量设置状态'); await select('目标状态', '目标状态'); await click('预检批量状态'); await visible('预检完成，共 120 条')
  const preview = requests.findLast(r => r.path.endsWith('/record-status-batches/preview'))
  assert.ok(preview?.body); assert.equal(preview.body.targets.length, 120); assert.equal(preview.body.blockSize, 100)
  await capture('preview-120')
  const target = preview.body.targets[0], recordPath = `${base}/records/${Buffer.from(target.recordRef.recordKey.value, 'utf8').toString('base64url')}`
  await api(`${recordPath}/status`, { method: 'PUT', body: { datasetGeneration: generation, recordKeyType: target.recordRef.recordKey.type, statusId: statuses[1].statusId, expectedStatusRevision: target.expectedStatusRevision, expectedFromStatusId: null } })
  checkpoint('E2 real competing single-record status PUT after UI preview; first frozen block contains the changed status revision')
  await click('确认开始'); await visible('操作未全部完成', 30000); await visible('已修改 20 条'); await visible('冲突 100 条'); await assertPartialDescription(); await capture('partial-100-conflicts-20-changed')
  const saved = await renderer.evaluate(`Object.entries(localStorage).filter(([key])=>key.startsWith('autoflow:status-batch:')).map(([key,value])=>({storageKey:key,...JSON.parse(value)}))`)
  assert.equal(saved.length, 1); const key = saved[0].key
  const lookup = `/projects/${projectId}/operations/by-idempotency-key/${key}`
  const operation = await api(lookup)
  assert.equal(operation.status, 'failed'); assert.equal(operation.result.changedCount, 20); assert.equal(operation.result.conflictCount, 100); assert.equal(operation.result.notStartedCount, 0)
  const before = await facts()
  verify(before, preview.body.targets, statuses, target)
  await writeFile(join(qa, 'partial-facts.json'), JSON.stringify({ previewRequest: preview.body, operation, records: before }, null, 2))
  checkpoint('UI reports 100 conflicts / 20 changed; GET proves first 100 block had no batch writes and second 20 committed once')
  renderer.close(); native.close(); await stop(desktop.child); desktop = renderer = native = undefined
  await launch(); await openTable(); await click('选择本页记录', '[aria-label="选择本页记录"]'); await click('批量设置状态')
  await visible('操作未全部完成', 30000); await visible('已修改 20 条'); await visible('冲突 100 条'); await assertPartialDescription(); await capture('restarted-original-progress')
  await click('刷新结果'); await visible('冲突 100 条')
  const recovered = await api(lookup), after = await facts()
  assert.equal(recovered.operationId, operation.operationId); assert.deepEqual(recovered.result, operation.result)
  assert.deepEqual(after, before)
  assert.equal(requests.filter(r => r.path.endsWith('/record-status-batches') && r.method === 'POST').length, 1)
  checkpoint('Fresh Electron and sidecar recovered the original terminal operation in UI; refresh performed no second start and all record revisions stayed identical')
  await writeFile(join(qa, 'result.json'), JSON.stringify({ result: 'passed', evidenceClass: 'E2 scale fixture and real competing writer; E1 UI batch flow', checkedAt: new Date().toISOString(), provenance, checks, captures, operationId: operation.operationId, requests }, null, 2))
  console.log(JSON.stringify({ result: 'passed', evidence: qa, checks }, null, 2))
} catch (error) {
  try { await capture('failure') } catch {}
  try { await cp(join(workspace, 'logs'), join(qa, 'workspace-logs'), { recursive: true }) } catch {}
  try { await cp(join(workspace, 'data'), join(qa, 'workspace-data'), { recursive: true }) } catch {}
  await writeFile(join(qa, 'failure.json'), JSON.stringify({ result: 'failed', error: String(error.stack ?? error), provenance, checks, captures, requests }, null, 2))
  console.error('Evidence retained:', qa); throw error
} finally { renderer?.close(); native?.close(); await stop(desktop?.child); await rm(workspace, { recursive: true, force: true }) }

async function launch() {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${workspace}`, '--inspect=0'], cliArgs: [] }); renderer = desktop.cdp; native = await connectCdp(desktop.inspectorUrl)
  renderer.socket.addEventListener('message', event => { const { method, params } = JSON.parse(event.data); if (method === 'Network.requestWillBeSent' && (params.request.url.includes('/record-status-batches') || params.request.url.includes('/operations/'))) requests.push({ method: params.request.method, path: new URL(params.request.url).pathname, requestId: params.requestId, body: params.request.postData ? JSON.parse(params.request.postData) : undefined }); if (method === 'Network.responseReceived') { const entry = requests.find(r => r.requestId === params.requestId); if (entry) entry.status = params.response.status } if (method === 'Network.loadingFinished') { const entry = requests.find(r => r.requestId === params.requestId); if (entry) void renderer.command('Network.getResponseBody', { requestId: params.requestId }).then(r => { entry.response = r.body }).catch(() => {}) } })
  await renderer.command('Network.enable')
  await native.evaluate("globalThis.qaElectron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');qaElectron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(1);true")
  await renderer.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false }); await visible('本地服务正常', 30000)
}
async function openTable() { await click('项目'); await renderer.evaluate(`location.hash=${JSON.stringify(`#/projects/${projectId}/data/${tableId}/records`)}`); await visible('120 条分块核验'); await waitFor(renderer, `document.querySelectorAll('tbody tr').length>0`, 'records loaded') }
async function assertPartialDescription() {
  await visible('本次操作共 120 条记录');
  await visible('部分记录发生冲突，已提交的修改已保留；请查看分块结果。');
  await visible('记录状态已变化，本块未修改。请重新选择记录后再处理。');
  const text = await renderer.evaluate(`document.querySelector('[role=dialog]')?.innerText`);
  assert.ok(!text.includes('One or more blocks conflicted'));
  assert.ok(!text.includes('Record status was modified'));
}
async function facts() { const items = []; for (let page = 1; page <= 3; page++) items.push(...(await api(`${base}/records?datasetGeneration=${generation}&page=${page}&pageSize=50`)).items); assert.equal(items.length, 120); return items }
function verify(records, targets, statuses, concurrent) {
  const byKey = new Map(records.map(r => [JSON.stringify(r.ref.recordKey), r]))
  targets.forEach((t, index) => { const record = byKey.get(JSON.stringify(t.recordRef.recordKey)); assert.ok(record); const raced = JSON.stringify(t.recordRef.recordKey) === JSON.stringify(concurrent.recordRef.recordKey); assert.equal(record.statusId, index >= 100 ? statuses[0].statusId : raced ? statuses[1].statusId : null); assert.equal(record.statusRevision, t.expectedStatusRevision + (index >= 100 || raced ? 1 : 0)) })
}
function checkpoint(message) { checks.push(message); console.log(message) }
async function capture(name) {
  await renderer.evaluate('document.fonts.ready.then(()=>true)')
  const metadata = await renderer.evaluate(`({width:innerWidth,height:innerHeight,dpr:devicePixelRatio,font:getComputedStyle(document.body).fontFamily,fontsStatus:document.fonts.status,url:location.hash})`)
  metadata.zoom = await native.evaluate('qaElectron.BrowserWindow.getAllWindows()[0].webContents.getZoomFactor()')
  assert.equal(metadata.width, 1440); assert.equal(metadata.height, 1024); assert.equal(metadata.dpr, 1); assert.equal(metadata.zoom, 1)
  const { data } = await renderer.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }); await writeFile(join(qa, `${name}.png`), data, 'base64'); captures.push({ name, ...metadata })
}
async function api(path, options={}) { const {sidecar}=await renderer.evaluate('window.autoflow.getRuntimeContext()'); const response=await fetch(`${sidecar.baseUrl}/api/v1${path}`,{...options,body:options.body?JSON.stringify(options.body):undefined,headers:{'x-autoflow-token':sidecar.token,'content-type':'application/json','Idempotency-Key':randomUUID()}}); assert.ok(response.ok,`${options.method??'GET'} ${path}: ${response.status}`); return response.json() }
async function visible(text,timeout=15000) { if(nativeMode&&text==='导出目标已存在')timeout=Math.max(timeout,180000); if(text==='返回数据表')return waitFor(renderer,"!!document.querySelector('[aria-label=返回数据表]')",text,timeout); return waitFor(renderer,`document.body?.innerText.includes(${JSON.stringify(text)})`,text,timeout) }
async function click(text,selector='button') { if(selector==='[role=tab]')text=({记录:'数据记录',字段:'字段与校验',状态:'数据状态',来源:'来源设置',设置:'数据表设置'})[text]??text; if(selector==='button' && ['批量设置状态','导出 Excel','重新导入 Excel'].includes(text) && await renderer.evaluate("!!document.querySelector('[aria-label=更多操作]')")){await click('更多操作');selector='[role=menuitem]'} const expression=`(()=>{const e=[...document.querySelectorAll(${JSON.stringify(selector)})].find(x=>(x.textContent.trim()===${JSON.stringify(text)}||x.getAttribute('aria-label')===${JSON.stringify(text)})&&x.getClientRects().length&&!x.disabled&&x.getAttribute('aria-disabled')!=='true');if(!e)return null;e.scrollIntoView({block:'center',inline:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2,hit=document.elementFromPoint(x,y);return hit&&(hit===e||e.contains(hit))?{x,y}:null})()`; const point=await waitFor(renderer,expression,`clickable ${text}`,nativeMode&&text==='检查文件'?180000:7000); await renderer.command('Input.dispatchMouseEvent',{type:'mouseMoved',...point}); await renderer.command('Input.dispatchMouseEvent',{type:'mousePressed',...point,button:'left',clickCount:1}); await renderer.command('Input.dispatchMouseEvent',{type:'mouseReleased',...point,button:'left',clickCount:1}); await wait(150) }
async function select(label,option) { await click(label,`[aria-label=${JSON.stringify(label)}]`); const point=await renderer.evaluate(`(()=>{const e=[...document.querySelectorAll('[role=option]')].find(x=>x.textContent.includes(${JSON.stringify(option)})&&x.getClientRects().length);if(!e)return null;const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`); assert.ok(point,`option missing: ${option}`); await renderer.command('Input.dispatchMouseEvent',{type:'mouseMoved',...point}); await renderer.command('Input.dispatchMouseEvent',{type:'mousePressed',...point,button:'left',clickCount:1}); await renderer.command('Input.dispatchMouseEvent',{type:'mouseReleased',...point,button:'left',clickCount:1}); await wait(120) }
