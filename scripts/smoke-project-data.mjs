import assert from 'node:assert/strict'
import { mkdtemp, mkdir, realpath, rm, writeFile } from 'node:fs/promises'
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
await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
let desktop, renderer, native
const checks = []
try {
  await launch()
  const project = await api('/projects', { method: 'POST', body: { name: '数据页面验收', description: '隔离的合成业务数据' } })
  await renderer.evaluate(`location.hash=${JSON.stringify(`#/projects/${project.projectId}/data`)}`)
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
  await click('返回数据表'); await waitFor(renderer, `!!document.querySelector('[aria-label="编辑客户资料"]')`, 'table edit control')
  await click('编辑客户资料')
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

  // Fields/statuses/records are setup through real APIs. This does not claim UI editing coverage for them.
  const field = await api(`${base}/fields`, { method: 'POST', body: { expectedTableRevision: 3, sourceColumnPolicy: 'localOnly', definition: { key: 'customer', name: '客户名称', type: 'string', required: false, validation: {} } } })
  const status = await api(`${base}/statuses`, { method: 'POST', body: { name: '可再次使用', color: '#748467', order: 0, expectedTableRevision: field.tableRevision } })
  const record = await api(`${base}/records`, { method: 'POST', body: { datasetGeneration: table.datasetGeneration, values: [{ fieldId: field.field.ref.fieldId, value: '合成客户甲' }] } })
  await api(`${base}/records/${Buffer.from(record.ref.recordKey.value).toString('base64url')}/status`, { method: 'PUT', body: { datasetGeneration: table.datasetGeneration, recordKeyType: 'uuid', expectedStatusRevision: record.statusRevision, statusId: status.statusId } })
  await click('打开客户资料'); await visible('合成客户甲'); await visible('可再次使用')
  await capture('records')
  for (const [label, text] of [['字段', '客户名称'], ['状态', '可再次使用'], ['来源', '身份规则'], ['设置', '数据代次']]) {
    await click(label, '[role=tab]'); await visible(text)
  }
  await click('记录', '[role=tab]')
  await click('应用筛选'); await visible('合成客户甲')
  checkpoint('five actual tabs display API-backed table, field, status, source and record facts')
  await click('返回数据表'); await waitFor(renderer, `!!document.querySelector('[aria-label="编辑客户资料"]')`, 'table edit control')
  await click('编辑客户资料'); await input('#data-table-description', '重连后保留草稿')
  const oldInstance = (await renderer.evaluate('window.autoflow.getRuntimeContext()')).sidecar.instanceId
  await renderer.evaluate('window.autoflow.restartSidecar()', 30000)
  await waitFor(renderer, `window.autoflow.getRuntimeContext().then(r=>r.sidecar.state==='ready'&&r.sidecar.instanceId!==${JSON.stringify(oldInstance)})`, 'service restart', 30000)
  await visible('本地服务正常', 30000)
  assert.equal(await renderer.evaluate("document.querySelector('#data-table-description')?.value"), '重连后保留草稿')
  await key('Escape'); await visible('放弃未保存的修改？'); await capture('leave')
  await click('继续编辑'); await click('保存修改')
  await waitFor(renderer, "!document.querySelector('#data-table-description')", 'save after reconnect')
  assert.equal((await api(base)).description, '重连后保留草稿')
  checkpoint('same-workspace real sidecar restart preserves draft, Escape protection and subsequent save')

  await native.evaluate('qaElectron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(2)')
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
  await native.evaluate('qaElectron.BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(1)')
  checkpoint('native 200 percent zoom with custom dropdown does not widen the application')
  renderer.close(); native.close(); await stop(desktop.child); desktop = null
  await launch()
  await renderer.evaluate(`location.hash=${JSON.stringify(`#/projects/${project.projectId}/data/${table.tableId}/records`)}`)
  await visible('合成客户甲'); await visible('可再次使用'); await capture('restarted')
  assert.equal((await api(base)).description, '重连后保留草稿')
  checkpoint('full Electron restart retains table edits, business records and explicit status')
  const report = { result: 'passed', scope: 'PM2 directory create/read/update and table read/navigation slice; field/status/record editing UI, Excel, batch status, Sheets and execution not covered', platform: process.platform, arch: process.arch, checkedAt: new Date().toISOString(), checks, zoom: { before, after }, windows: 'not-run' }
  await writeFile(join(qa, 'result.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ qa, ...report }, null, 2))
} catch (error) {
  try { await capture('failure'); console.error(await renderer.evaluate('({hash:location.hash,text:document.body.innerText})')) } catch { /* preserve original failure */ }
  await writeFile(join(qa, 'failure.json'), JSON.stringify({ checks, error: error.message, checkedAt: new Date().toISOString() }, null, 2))
  throw error
} finally {
  renderer?.close(); native?.close(); await stop(desktop?.child)
  await rm(userData, { recursive: true, force: true })
}
async function launch() {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'], cliArgs: [] })
  renderer = desktop.cdp; native = await connectCdp(desktop.inspectorUrl)
  await native.evaluate("globalThis.qaElectron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');true")
  await visible('本地服务正常', 30000)
}
function checkpoint(message) { checks.push(message); console.log(message) }
async function visible(text, timeout = 15000) { return waitFor(renderer, `Boolean(document.body?.innerText.includes(${JSON.stringify(text)}))`, text, timeout) }
async function api(path, options = {}) {
  const { sidecar } = await renderer.evaluate('window.autoflow.getRuntimeContext()')
  const response = await fetch(`${sidecar.baseUrl}/api/v1${path}`, { ...options, body: options.body ? JSON.stringify(options.body) : undefined, headers: { 'x-autoflow-token': sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': crypto.randomUUID() } })
  assert.ok(response.ok, `${options.method ?? 'GET'} ${path}: ${response.status} ${response.ok ? '' : await response.text()}`)
  return response.json()
}
async function click(text, selector = 'button') {
  const point = await renderer.evaluate(`(()=>{const el=[...document.querySelectorAll(${JSON.stringify(selector)})].find(e=>(!${JSON.stringify(text)}||e.textContent.trim()===${JSON.stringify(text)}||e.getAttribute('aria-label')===${JSON.stringify(text)})&&e.getBoundingClientRect().height>0);if(!el)return null;el.scrollIntoView({block:'nearest'});const r=el.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`)
  assert.ok(point, `control missing: ${text || selector}`)
  await renderer.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...point, button: 'left', clickCount: 1 })
  await renderer.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...point, button: 'left', clickCount: 1 }); await wait(120)
}
async function input(selector, value) {
  assert.equal(await renderer.evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el)return false;el.focus();Object.getOwnPropertyDescriptor(el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,'value').set.call(el,${JSON.stringify(value)});el.dispatchEvent(new Event('input',{bubbles:true}));return true})()`), true); await wait(120)
}
async function key(key) { await renderer.command('Input.dispatchKeyEvent', { type: 'keyDown', key, code: key, windowsVirtualKeyCode: key === 'Escape' ? 27 : 13 }); await renderer.command('Input.dispatchKeyEvent', { type: 'keyUp', key }); await wait(150) }
async function capture(name) { if (!renderer) return; const { data } = await renderer.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }); await writeFile(join(qa, `${name}.png`), data, 'base64') }
