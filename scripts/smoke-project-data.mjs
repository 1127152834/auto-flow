import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, realpath, rm, writeFile, readFile, readdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { launchElectron, connectCdp, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

// Each run gets disposable data and a new evidence directory. It never opens user data.
const root = resolve(import.meta.dirname, '..')
const parent = join(root, 'docs/migration/project-data-directory-qa')
await mkdir(parent, { recursive: true })
const qa = await mkdtemp(join(parent, 'run-'))
const userData = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-data-qa-')))
const otherWorkspace = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-data-other-')))
await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await writeFile(join(userData, 'desktop-settings.json'), JSON.stringify({ schemaVersion: 1, currentPath: userData, previousPath: otherWorkspace, preferences: { zoom: 100, motion: 'system' } }))
let desktop, renderer, native
const checks = [], screenshots = [], settingsTrace = []
const provenance = { gitHead: execFileSync('git', ['rev-parse', 'HEAD'], {cwd:root,encoding:'utf8'}).trim(), dirtyFiles: execFileSync('git',['diff','--name-only','HEAD'],{cwd:root,encoding:'utf8'}).trim().split('\n').filter(Boolean), scriptSha256: createHash('sha256').update(await readFile(new URL(import.meta.url))).digest('hex') }
const buildHash=createHash('sha256');for(const file of (await readdir(join(root,'apps/desktop/out'),{recursive:true})).filter(file=>/\.(js|css|html)$/.test(file)).sort())buildHash.update(file).update(await readFile(join(root,'apps/desktop/out',file)));provenance.buildSha256=buildHash.digest('hex')
try {
  await launch()
  await click('项目'); await click('新建项目'); await input('#project-name', '数据页面验收'); await input('#project-description', '隔离的合成业务数据'); await click('创建项目'); await visible('项目资料');
  const project = (await api('/projects')).items.find(item=>item.name==='数据页面验收'); assert.ok(project); await click('数据')
  await visible('还没有数据表')
  await capture('empty')
  await click('新建数据表')
  await input('#data-table-name', '客户资料')
  await input('#data-table-description', '用于验证真实数据目录与查询')
  await click('创建数据表')
  await visible('返回数据表')
  const table = (await api(`/projects/${project.projectId}/tables`)).items[0]
  assert.equal(table.name, '客户资料')
  assert.equal(await renderer.evaluate('location.hash'), `#/projects/${project.projectId}/data/${table.tableId}/records`)
  checkpoint('UI creates a local table through real HTTP and navigates to its records route')
  await click('返回数据表'); await waitFor(renderer, `!!document.querySelector('[aria-label="更多客户资料操作"]')`, 'table edit control')
  await click('更多客户资料操作'); await click('编辑数据表', '[role=menuitem]')
  await input('#data-table-name', '我的本地修改')
  const base = `/projects/${project.projectId}/tables/${table.tableId}`
  await api(base, { method: 'PATCH', body: { name: '另一个编辑者', expectedTableRevision: table.tableRevision } })
  await click('保存修改'); await visible('载入最新资料')
  assert.equal(await renderer.evaluate("document.querySelector('#data-table-name').value"), '我的本地修改')
  await capture('conflict')
  await click('载入最新资料'); await click('重新编辑')
  await waitFor(renderer, "document.querySelector('#data-table-name')?.value === '另一个编辑者'", 'load authoritative table revision')
  await input('#data-table-name', '客户资料')
  await click('保存修改'); await waitFor(renderer, "!document.querySelector('#data-table-name')", 'table form closes')
  assert.equal((await api(base)).tableRevision, 3)
  checkpoint('real competing edit preserves the draft and requires explicit reload before resaving')

  // All data mutations below use the real UI; HTTP only reads facts or creates a competing edit.
  await click('打开数据表：客户资料'); await visible('＋ 点击新增一行'); await visible('0 条')
  await click('字段', '[role=tab]'); await click('新增字段')
  await input('#field-name', '客户名称'); await input('#field-key', 'customer')
  await click('应用到草稿'); await closed('#schema-field-drawer-form')
  assert.deepEqual((await api(`${base}/fields`)).items, [], 'applying a new field only changes the local schema draft')
  const createdFields = await commitFields(base)
  const field = createdFields.items[0]
  assert.equal(field.name, '客户名称')
  await click('编辑字段 客户名称'); await input('#field-name', '客户姓名')
  await click('应用到草稿'); await closed('#schema-field-drawer-form')
  assert.equal((await api(`${base}/fields`)).items[0].name, '客户名称', 'renaming in the drawer does not write before whole-schema confirmation')
  const renamedFields = await commitFields(base)
  assert.equal(renamedFields.items[0].name, '客户姓名')
  assert.equal(renamedFields.items[0].ref.fieldId, field.ref.fieldId, 'atomic field rename preserves the existing field identity')
  assert.equal(renamedFields.items[0].key, field.key)
  checkpoint('UI applies create/rename drafts locally, previews and atomically commits each schema; the field identity remains stable')

  await click('状态', '[role=tab]'); await click('新增状态')
  await input('#status-name', '待处理'); await click('创建状态'); await closed('#status-editor-form')
  await click('编辑状态 待处理'); await input('#status-name', '可再次使用')
  await click('保存修改'); await closed('#status-editor-form')
  const status = (await api(`${base}/statuses`)).items[0]
  assert.equal(status.name, '可再次使用')
  checkpoint('UI creates and edits a business status without changing any record status')

  await click('记录', '[role=tab]')
  await createRecord('合成客户甲')
  let records = (await api(`${base}/records?datasetGeneration=${table.datasetGeneration}`)).items
  const record = records[0]
  assert.equal(record.values.find(value => value.fieldId === field.ref.fieldId).value, '合成客户甲')
  assert.equal(record.statusId, null)
  const recordUrl = `${base}/records/${Buffer.from(record.ref.recordKey.value).toString('base64url')}`
  const getRecord = () => api(`${recordUrl}?datasetGeneration=${table.datasetGeneration}&recordKeyType=${record.ref.recordKey.type}`)
  await clickRow('合成客户甲', '查看记录')
  await waitFor(renderer,`!!document.querySelector('[data-record-page=detail]')`,'record detail page'); await click('编辑记录')
  await input(`#record-${field.ref.fieldId}`, '冲突草稿')
  await api(recordUrl, { method: 'PATCH', body: { datasetGeneration: table.datasetGeneration, recordKeyType: record.ref.recordKey.type, values: [{ fieldId: field.ref.fieldId, value: '远端修改' }], expectedContentRevision: record.contentRevision } })
  await click('保存修改'); await visible('载入最新资料')
  assert.equal(await renderer.evaluate(`document.querySelector(${JSON.stringify(`#record-${field.ref.fieldId}`)}).value`), '冲突草稿')
  await capture('record-conflict'); await click('载入最新资料'); await capture('record-conflict-comparison'); await click('重新编辑')
  await waitFor(renderer, `document.querySelector(${JSON.stringify(`#record-${field.ref.fieldId}`)})?.value==='远端修改'`, 'record conflict reload')
  await input(`#record-${field.ref.fieldId}`, '合成客户甲'); await click('保存修改'); await closed('#record')
  assert.equal((await getRecord()).contentRevision, record.contentRevision + 2)
  assert.equal((await getRecord()).statusId, null)
  await visible('清空状态')
  await click('', '[aria-label="记录业务状态"]'); await click('可再次使用', '[role=option]')
  await click('保存状态'); await waitFor(renderer,`document.querySelector('[aria-label="记录业务状态"]')?.textContent.includes('可再次使用')`,'new confirmed status baseline')
  assert.equal((await getRecord()).statusId, status.statusId)
  checkpoint('UI creates and edits a record with real conflict reload, then explicitly changes its status')
  await capture('records')

  await click('状态', '[role=tab]'); await visible('仍有 1 条记录')
  const statusUsage = await api(`${base}/statuses/usage`)
  assert.equal(statusUsage.datasetGeneration, table.datasetGeneration)
  assert.deepEqual(statusUsage.items.find(item => item.statusId === status.statusId), { statusId: status.statusId, currentRecords: 1, activeBatchOperations: 0 })
  assert.equal(await renderer.evaluate(`document.querySelector('[aria-label="删除状态 可再次使用"]')?.disabled`), true)
  assert.ok(await renderer.evaluate(`document.querySelector('[aria-label="删除状态 可再次使用"]')?.closest('tr').textContent.includes('仍有 1 条记录、0 个未完成批量操作引用')`), 'disabled deletion explains its actual current usage')
  assert.equal((await getRecord()).statusId, status.statusId)
  await capture('status-delete-blocked')
  await click('新增状态'); await input('#status-name', '临时状态'); await click('创建状态'); await closed('#status-editor-form')
  const temporary = (await api(`${base}/statuses`)).items.find(item => item.name === '临时状态')
  assert.ok(temporary)
  await click('记录', '[role=tab]'); await clickRow('合成客户甲', '查看记录'); await visible('清空状态')
  await click('', '[aria-label="记录业务状态"]'); await click('临时状态', '[role=option]'); await click('保存状态')
  await waitFor(renderer, `document.querySelector('[aria-label="记录业务状态"]')?.textContent.includes('临时状态')&&[...document.querySelectorAll('[aria-label="业务状态编辑"] button')].some(b=>b.textContent.trim()==='保存状态'&&b.disabled)`, 'temporary status assignment confirmed')
  assert.equal((await getRecord()).statusId, temporary.statusId)
  await click('状态', '[role=tab]')
  await waitFor(renderer, `(()=>{const button=document.querySelector('[aria-label="删除状态 临时状态"]');return button?.disabled&&button.closest('tr').textContent.includes('仍有 1 条记录')})()`, 'temporary status is also protected while referenced')
  await click('记录', '[role=tab]'); await clickRow('合成客户甲', '查看记录'); await visible('清空状态')
  await click('', '[aria-label="记录业务状态"]'); await click('可再次使用', '[role=option]'); await click('保存状态')
  await waitFor(renderer, `document.querySelector('[aria-label="记录业务状态"]')?.textContent.includes('可再次使用')&&[...document.querySelectorAll('[aria-label="业务状态编辑"] button')].some(b=>b.textContent.trim()==='保存状态'&&b.disabled)`, 'original record status restored before deletion')
  assert.equal((await getRecord()).statusId, status.statusId)
  await click('状态', '[role=tab]')
  assert.deepEqual((await api(`${base}/statuses/usage`)).items.find(item => item.statusId === temporary.statusId), { statusId: temporary.statusId, currentRecords: 0, activeBatchOperations: 0 })
  await click('删除状态 临时状态'); await click('检查删除影响'); await click('确认删除'); await closed('[role=dialog]')
  assert.ok(!(await api(`${base}/statuses`)).items.some(item => item.statusId === temporary.statusId))
  assert.equal((await getRecord()).statusId, status.statusId)
  checkpoint('UI blocks referenced status deletion, restores the record status to release a temporary reference, then deletes that status through the real impact-confirmed operation')

  await click('记录', '[role=tab]'); await createRecord('待删除记录')
  records = (await api(`${base}/records?datasetGeneration=${table.datasetGeneration}`)).items
  assert.equal(records.length, 2)
  await clickRow('待删除记录', '查看记录'); await waitFor(renderer,`!!document.querySelector('[data-record-page=detail]')`,'record detail page'); await click('更多记录操作'); await click('删除记录', '[role=menuitem]')
  await click('检查删除影响'); await click('删除记录', '[role=dialog] button'); await closed('[role=dialog]')
  assert.equal((await api(`${base}/records?datasetGeneration=${table.datasetGeneration}`)).items.length, 1)
  checkpoint('UI deletes the selected record after impact confirmation and retains the other record')

  // Simulate a lost acknowledgement only after the real server commits; the reload restores fetch.
  await renderer.evaluate(`(()=>{const original=window.fetch.bind(window);window.fetch=async(input,init)=>{const url=String(input?.url??input);if(url.includes('/operations/by-idempotency-key/'))throw new TypeError('QA offline lookup');const response=await original(input,init);if(url.includes('/records')&&init?.method==='POST')throw new TypeError('QA lost committed response');return response};return true})()`)
  await click('', '[data-record-action="create"]')
  await doubleClick(`[data-record-draft] [data-grid-cell="0:${field.ref.fieldId}"]`)
  await input(`[data-record-draft] textarea[aria-label=${JSON.stringify('第 1 行 · 客户姓名')}]`, '恢复后不重复新增')
  await click('保存 1 行'); await visible('查询保存结果')
  assert.equal((await api(`${base}/records?datasetGeneration=${table.datasetGeneration}`)).items.length, 2)
  await renderer.command('Page.reload')
  await visible('本地服务正常', 30000); await visible('查询保存结果')
  await click('查询保存结果'); await closed('[aria-label="新增记录保存"]')
  assert.equal((await api(`${base}/records?datasetGeneration=${table.datasetGeneration}`)).items.length, 2)
  await visible('恢复后不重复新增'); await capture('durable-edit-recovery')
  checkpoint('lost real create acknowledgement survives renderer reload and recovers the original operation without duplicate insertion')


  for (const [label, text] of [['字段', '客户姓名'], ['状态', '可再次使用'], ['来源', '数据来源'], ['设置', '基本信息']]) {
    await click(label, '[role=tab]'); await visible(text)
  }
  await click('记录', '[role=tab]'); await click('筛选'); await click('应用筛选'); await visible('合成客户甲')
  checkpoint('five actual tabs display persisted field, status, source and record facts after UI writes')
  await click('设置', '[role=tab]')
  await inputLabel('用途说明', '从设置页修改资料')
  await click('保存设置'); await settingsSaved('从设置页修改资料', base)
  assert.equal((await api(base)).description, '从设置页修改资料')
  checkpoint('inline settings edits the actual description, stays mounted after confirmation and resets to a clean baseline')

  async function createRecord(value) {
    await click('', '[data-record-action="create"]')
    await waitFor(renderer, "!!document.querySelector('[data-record-draft]')", 'inline record draft'); await capture('gallery-create-structure')
    await doubleClick(`[data-record-draft] [data-grid-cell="0:${field.ref.fieldId}"]`)
    await input(`[data-record-draft] textarea[aria-label=${JSON.stringify('第 1 行 · 客户姓名')}]`, value)
    await native.evaluate('qaElectron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(2)'); await renderer.command('Emulation.setDeviceMetricsOverride',{width:1440,height:1024,deviceScaleFactor:1,mobile:false})
    await waitFor(renderer, 'innerWidth===720&&innerHeight===512&&devicePixelRatio===2', 'record page at native 200 percent')
    await waitFor(renderer, `document.documentElement.scrollWidth<=innerWidth+1&&!document.querySelector('[role=dialog]')`, 'record grid settles inside the 200 percent viewport')
    const bounds=await renderer.evaluate(`({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth})`)
    assert.ok(bounds.scrollWidth<=bounds.width+1,`record grid widens document: ${JSON.stringify(bounds)}`)
    const frameGeometry=await renderer.evaluate(`(()=>{const header=document.querySelector('[data-table-page-frame-header]');const [left,right]=header.children;const a=left.getBoundingClientRect(),b=right.getBoundingClientRect();return {left:{x:a.x,y:a.y,width:a.width,right:a.right,bottom:a.bottom},right:{x:b.x,y:b.y,width:b.width,right:b.right,bottom:b.bottom},viewport:innerWidth}})()`)
    assert.ok(frameGeometry.left.width>=240,'title keeps a readable width at 200 percent')
    assert.ok(frameGeometry.left.bottom<=frameGeometry.right.y+1||frameGeometry.left.right<=frameGeometry.right.x+1,'header and tabs do not overlap')
    await capture('record-create-200-percent')
    await renderer.evaluate("document.querySelector('[aria-label=\"新增记录保存\"]')?.scrollIntoView({block:'end'});true")
    await wait(150)
    const footerGeometry=await renderer.evaluate(`(()=>{const footer=document.querySelector('[aria-label="新增记录保存"]');const r=footer.getBoundingClientRect();return {top:r.top,bottom:r.bottom,height:innerHeight,scrollHeight:document.documentElement.scrollHeight}})()`)
    assert.ok(footerGeometry.top>=0&&footerGeometry.bottom<=footerGeometry.height+1,'long form save footer remains in the viewport')
    await capture('record-create-200-footer')
    await renderer.evaluate('window.scrollTo(0,0);true')
    await native.evaluate('qaElectron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(1)'); await renderer.command('Emulation.setDeviceMetricsOverride',{width:1440,height:1024,deviceScaleFactor:1,mobile:false})
    await waitFor(renderer,"Boolean(document.querySelector('[data-record-draft]'))",'record draft remains after zoom reset')
    await capture('record-create'); await click('保存 1 行'); await closed('[aria-label="新增记录保存"]'); await visible(value); await capture('record-detail')
  }
  await click('设置', '[role=tab]'); await inputLabel('用途说明', '重连后保留草稿')
  const oldInstance = (await renderer.evaluate('window.autoflow.getRuntimeContext()')).sidecar.instanceId
  await renderer.evaluate('window.autoflow.restartSidecar()', 30000)
  await waitFor(renderer, `window.autoflow.getRuntimeContext().then(r=>r.sidecar.state==='ready'&&r.sidecar.instanceId!==${JSON.stringify(oldInstance)})`, 'service restart', 30000)
  await visible('本地服务正常', 30000)
  assert.equal(await renderer.evaluate(`${labelControl('用途说明')}?.value`), '重连后保留草稿')
  await click('取消更改'); await visible('放弃未保存的修改？'); await capture('leave')
  await click('继续编辑'); assert.equal(await renderer.evaluate(`${labelControl('用途说明')}?.value`), '重连后保留草稿')
  await click('保存设置'); await settingsSaved('重连后保留草稿', base)
  assert.equal((await api(base)).description, '重连后保留草稿')
  checkpoint('same-workspace real sidecar restart preserves the inline draft, cancel/continue leave protection and subsequent confirmed save')
  await click('返回数据表'); await visible('客户资料')

  await native.evaluate('qaElectron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(2)'); await renderer.command('Emulation.setDeviceMetricsOverride',{width:1440,height:1024,deviceScaleFactor:1,mobile:false})
  await waitFor(renderer, 'innerWidth<=720', 'native 200 percent zoom')
  const before = await renderer.evaluate(`({inner:innerWidth,width:document.documentElement.scrollWidth,root:document.querySelector('#root').getBoundingClientRect().width,trigger:document.querySelector('[aria-label="数据表排序"]').getBoundingClientRect().width})`)
  await click('', '[aria-label="数据表排序"]')
  await waitFor(renderer, "!!document.querySelector('[role=listbox]')", 'custom dropdown')
  const after = await renderer.evaluate(`({inner:innerWidth,width:document.documentElement.scrollWidth,root:document.querySelector('#root').getBoundingClientRect().width,trigger:document.querySelector('[aria-label="数据表排序"]').getBoundingClientRect().width})`)
  assert.ok(before.width <= before.inner + 1 && after.width <= after.inner + 1)
  assert.equal(after.inner, before.inner)
  assert.equal(after.root, before.root, 'application content width remains stable')
  assert.equal(after.trigger, before.trigger, 'select trigger width remains stable')
  await capture('zoom-200-dropdown'); await key('Escape')
  await native.evaluate('qaElectron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(1)'); await renderer.command('Emulation.setDeviceMetricsOverride',{width:1440,height:1024,deviceScaleFactor:1,mobile:false})
  checkpoint('native 200 percent zoom with custom dropdown does not widen the application')
  renderer.close(); native.close(); await stop(desktop.child); desktop = null
  await launch()
  await click('项目'); if(await renderer.evaluate("[...document.querySelectorAll('button')].some(e=>e.getAttribute('aria-label')==='查看全部项目')"))await click('查看全部项目'); await click('数据页面验收'); await click('数据'); await click('打开数据表：客户资料')
  await visible('合成客户甲'); await visible('可再次使用'); await capture('restarted')
  assert.equal((await api(base)).description, '重连后保留草稿')
  checkpoint('full Electron restart retains table edits, business records and explicit status')
  const originalWorkspace = (await renderer.evaluate('window.autoflow.getRuntimeContext()')).workspaceKey
  await switchWorkspace()
  const secondaryWorkspace = (await renderer.evaluate('window.autoflow.getRuntimeContext()')).workspaceKey
  assert.notEqual(secondaryWorkspace, originalWorkspace)
  assert.equal((await api('/projects')).total, 0)
  const separate = await api('/projects', { method: 'POST', body: { name: '第二工作区', description: '隔离事实' } })
  await renderer.evaluate(`location.hash=${JSON.stringify(`#/projects/${separate.projectId}/data`)}`)
  await visible('还没有数据表'); await click('新建数据表')
  await input('#data-table-name', '第二工作区独立表'); await click('创建数据表'); await visible('返回数据表')
  assert.equal((await api(`/projects/${separate.projectId}/tables`)).items.length, 1)
  await switchWorkspace()
  assert.equal((await renderer.evaluate('window.autoflow.getRuntimeContext()')).workspaceKey, originalWorkspace)
  await click('项目'); if(await renderer.evaluate("[...document.querySelectorAll('button')].some(e=>e.getAttribute('aria-label')==='查看全部项目')"))await click('查看全部项目'); await click('数据页面验收'); await click('数据'); await click('打开数据表：客户资料')
  await visible('合成客户甲'); assert.equal((await api('/projects')).total, 1)
  assert.equal((await api(base)).description, '重连后保留草稿')
  await capture('workspace-return')
  checkpoint('two real workspace switches isolate data tables and restore original records')
  const report = { result: 'passed', scope: 'R2 dedicated record pages and retained PM2 field/status/record commands, real UI and HTTP; service/workspace bridge invokes are E2, lost acknowledgements E4; Excel/batch/Sheets/execution not covered', platform: process.platform, arch: process.arch, checkedAt: new Date().toISOString(), provenance, screenshots, checks, settingsTrace, zoom: { before, after }, windows: 'not-run' }
  await writeFile(join(qa, 'result.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ qa, ...report }, null, 2))
} catch (error) {
  try { await capture('failure'); console.error(await renderer.evaluate('({hash:location.hash,text:document.body.innerText})')) } catch { /* preserve original failure */ }
  await writeFile(join(qa, 'failure.json'), JSON.stringify({ checks, settingsTrace, error: error.message, checkedAt: new Date().toISOString() }, null, 2))
  throw error
} finally {
  renderer?.close(); native?.close(); await stop(desktop?.child)
  await rm(userData, { recursive: true, force: true })
  await rm(otherWorkspace, { recursive: true, force: true })
}
async function launch() {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'], cliArgs: [] })
  renderer = desktop.cdp; native = await connectCdp(desktop.inspectorUrl)
  const connection = renderer, requests = new Map()
  connection.socket.addEventListener('message', event => {
    const {method, params} = JSON.parse(event.data)
    if (method === 'Network.requestWillBeSent' && params.request.method === 'PATCH' && /\/tables\/[^/?]+$/.test(params.request.url)) {
      const entry = { event: 'tablePatch', at: Date.now(), path: new URL(params.request.url).pathname, body: params.request.postData, operationKey: Object.entries(params.request.headers).find(([key]) => key.toLowerCase() === 'idempotency-key')?.[1] }
      requests.set(params.requestId, entry); settingsTrace.push(entry)
    }
    const entry = requests.get(params?.requestId)
    if (entry && method === 'Network.responseReceived') entry.status = params.response.status
    if (entry && method === 'Network.loadingFinished') void connection.command('Network.getResponseBody', {requestId: params.requestId}).then(result => { entry.response = result.body; entry.responseAt = Date.now() }).catch(error => { entry.responseReadError = error.message })
  })
  await connection.command('Network.enable')
  await native.evaluate("globalThis.qaElectron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');true")
  await renderer.command('Emulation.setDeviceMetricsOverride',{width:1440,height:1024,deviceScaleFactor:1,mobile:false}); await visible('本地服务正常', 30000)
}
function checkpoint(message) { checks.push(message); console.log(message) }
async function visible(text, timeout = 15000) { if(text==='返回数据表')return waitFor(renderer,"!!document.querySelector('[aria-label=返回数据表]')",text,timeout); return waitFor(renderer, `Boolean(document.body?.innerText.includes(${JSON.stringify(text)}))`, text, timeout) }
async function api(path, options = {}) {
  const { sidecar } = await renderer.evaluate('window.autoflow.getRuntimeContext()')
  const response = await fetch(`${sidecar.baseUrl}/api/v1${path}`, { ...options, body: options.body ? JSON.stringify(options.body) : undefined, headers: { 'x-autoflow-token': sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': crypto.randomUUID() } })
  assert.ok(response.ok, `${options.method ?? 'GET'} ${path}: ${response.status} ${response.ok ? '' : await response.text()}`)
  return response.json()
}
async function click(text, selector = 'button') {
  if (selector === '[role=tab]') text = ({'记录':'数据记录','字段':'字段与校验','状态':'数据状态','来源':'来源设置','设置':'数据表设置'})[text] ?? text
  const point = await waitFor(renderer, `(()=>{const el=[...document.querySelectorAll(${JSON.stringify(selector)})].find(e=>(!${JSON.stringify(text)}||e.textContent.trim()===${JSON.stringify(text)}||e.getAttribute('aria-label')===${JSON.stringify(text)})&&e.getBoundingClientRect().height>0);if(!el)return null;el.scrollIntoView({block:'center',behavior:'instant'});const r=el.getBoundingClientRect();const x=r.x+r.width/2,y=r.y+r.height/2;return !el.disabled&&el.contains(document.elementFromPoint(x,y))?{x,y,disabled:false,hit:true}:null})()`, `unobscured control: ${text || selector}`, 7000)
  assert.ok(point, `control missing: ${text || selector}`)
  assert.equal(point.disabled, false, `control disabled: ${text || selector}`)
  assert.equal(point.hit, true, `control obscured: ${text || selector}: ${JSON.stringify(point)}`)
  await renderer.command('Input.dispatchMouseEvent', { type: 'mouseMoved', x: point.x, y: point.y });
  await renderer.command('Input.dispatchMouseEvent', { type: 'mousePressed', x: point.x, y: point.y, button: 'left', clickCount: 1 })
  await renderer.command('Input.dispatchMouseEvent', { type: 'mouseReleased', x: point.x, y: point.y, button: 'left', clickCount: 1 }); await wait(120)
}
async function doubleClick(selector) {
  const point = await waitFor(renderer, `(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e||!e.getClientRects().length)return null;e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`, `double click: ${selector}`, 7000)
  await renderer.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...point })
  await renderer.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...point, button: 'left', clickCount: 2 })
  await renderer.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...point, button: 'left', clickCount: 2 })
  await wait(120)
}
async function input(selector, value) {
  await click('',selector)
  await renderer.evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el)throw Error('input missing');el.select()})()`)
  await renderer.command('Input.insertText',{text:value});await wait(120)
}
async function key(key) { await renderer.command('Input.dispatchKeyEvent', { type: 'keyDown', key, code: key, windowsVirtualKeyCode: key === 'Escape' ? 27 : 13 }); await renderer.command('Input.dispatchKeyEvent', { type: 'keyUp', key }); await wait(150) }
async function capture(name) {
  if(!renderer)return
  await renderer.evaluate('document.fonts.ready.then(()=>true)');await wait(180)
  const geometry=await renderer.evaluate(`({viewport:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio},scroll:{x:scrollX,y:scrollY},font:getComputedStyle(document.body).fontFamily,hash:location.hash,headings:[...document.querySelectorAll('h1')].map(n=>n.textContent)})`)
  const windowInfo=await native.evaluate('({zoom:qaElectron.BrowserWindow.getAllWindows()[0].webContents.getZoomFactor(),contentSize:qaElectron.BrowserWindow.getAllWindows()[0].getContentSize()})')
  const {data}=await renderer.command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(join(qa,`${name}.png`),data,'base64')
  screenshots.push({name:`${name}.png`,...geometry,...windowInfo,viewportType:'CDP override',at:new Date().toISOString()})
}



async function commitFields(base) {
  const before = await api(`${base}/fields`)
  await click('保存字段'); await visible('保存字段前核对影响')
  assert.deepEqual(await api(`${base}/fields`), before, 'schema preview does not commit the candidate')
  await click('确认保存字段'); await closed('[role=dialog]')
  await visible('暂无未保存修改')
  const after = await api(`${base}/fields`)
  assert.equal(after.tableRevision, before.tableRevision + 1, 'one aggregate commit advances the table revision once')
  return after
}
function labelControl(label) {
  return `(()=>{const e=[...document.querySelectorAll('label')].find(e=>e.textContent.trim()===${JSON.stringify(label)}&&e.getClientRects().length);return e?document.getElementById(e.htmlFor):null})()`
}
async function inputLabel(label, value) {
  const selector = await waitFor(renderer, `(()=>{const e=${labelControl(label)};return e?'#'+CSS.escape(e.id):null})()`, `visible ${label} control`)
  await input(selector, value)
}
async function settingsSaved(description, base) {
  try { await waitFor(renderer, `(()=>{const e=${labelControl('用途说明')},form=e?.closest('form');return e?.value===${JSON.stringify(description)}&&form?.innerText.includes('没有未保存的修改')&&[...form.querySelectorAll('button')].some(b=>b.textContent.trim()==='保存设置'&&b.disabled)})()`, 'inline settings remains mounted with the confirmed clean baseline') } catch (error) {
    const actual = await renderer.evaluate(`(()=>{const e=${labelControl('用途说明')};return {value:e?.value,form:e?.closest('form')?.innerText}})()`)
    error.message += `; settings diagnostic: ${JSON.stringify({ expected: description, actual, persisted: await api(base) })}`
    throw error
  }
  assert.ok(await renderer.evaluate(`Boolean(${labelControl('用途说明')}?.closest('form'))`), 'settings does not disappear after saving')
}

async function closed(selector) { await waitFor(renderer, `!document.querySelector(${JSON.stringify(selector)})`, 'form closes') }
async function clickRow(value, action) {
  const label = await renderer.evaluate(`(()=>{const row=[...document.querySelectorAll('tbody tr')].find(e=>e.textContent.includes(${JSON.stringify(value)}));return row?[...row.querySelectorAll('button')].find(e=>e.getAttribute('aria-label')?.startsWith(${JSON.stringify(action)}))?.getAttribute('aria-label'):null})()`)
  assert.ok(label, `row action missing: ${value} / ${action}`); await click(label)
}

async function switchWorkspace() {
  const choice = await renderer.evaluate("window.autoflow.chooseWorkspace('previous')")
  assert.ok(choice.ok && choice.value)
  const switched = await renderer.evaluate(`window.autoflow.confirmWorkspace(${JSON.stringify(choice.value.id)})`, 30000)
  assert.equal(switched.ok, true)
  await visible('本地服务正常', 30000)
}
