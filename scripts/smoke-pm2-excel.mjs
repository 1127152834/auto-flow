import assert from 'node:assert/strict'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { mkdtemp, mkdir, realpath, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { launchElectron, connectCdp, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const run = promisify(execFile)
const root = resolve(import.meta.dirname, '..')
const evidenceRoot = join(root, 'docs/migration/pm2-excel-qa')
await mkdir(evidenceRoot, { recursive: true })
const qa = await mkdtemp(join(evidenceRoot, 'run-'))
const workspace = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-pm2-excel-')))
const workbook = join(workspace, 'fixture.xlsx')
await writeFile(join(workspace, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await run('uv', ['run', '--project', join(root, 'apps/backend'), 'python', '-c', `from openpyxl import Workbook
b=Workbook(); a=b.active; a.title='忽略'; a.append(['无关']); a.append(['skip'])
s=b.create_sheet('客户'); s.append(['姓名','编号']); s.append(['张三','001']); s.append(['李四','002']); b.save(${JSON.stringify(workbook)})`])
let desktop, renderer, native
const checks = []
try {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${workspace}`, '--inspect=0'], cliArgs: [] })
  renderer = desktop.cdp; native = await connectCdp(desktop.inspectorUrl)
  await native.evaluate("globalThis.qaElectron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');true")
  await native.evaluate(`qaElectron.dialog.showOpenDialog=async()=>({canceled:false,filePaths:[${JSON.stringify(workbook)}]});true`)
  await visible('本地服务正常', 30000)
  const project = await api('/projects', { method: 'POST', body: { name: 'Excel 验收项目', description: '' } })
  await renderer.evaluate(`location.hash=${JSON.stringify(`#/projects/${project.projectId}/data`)}`)
  await visible('还没有数据表'); await capture('directory-empty')
  await verifyGlobalNavigation(project.projectId)
  await verifyKeyboardClose()
  await setZoom(2)
  await assertNoHorizontalOverflow('200% directory')
  await click('从 Excel 导入'); await visible('从 Excel 新建数据表')
  await assertNoHorizontalOverflow('200% import wizard'); await capture('directory-import-200-percent')
  await pressEscape(); await waitFor(renderer, `!document.body.innerText.includes('从 Excel 新建数据表')`, 'Escape closes Excel wizard')
  await setZoom(1)
  checkpoint('directory and import wizard stayed within the viewport at 200% zoom')
  await importTable('客户一')
  let tables = (await api(`/projects/${project.projectId}/tables`)).items
  assert.equal(tables.length, 1); assert.equal(tables[0].sourceKind, 'excel'); assert.equal(tables[0].recordCount, 2)
  let records = (await api(`/projects/${project.projectId}/tables/${tables[0].tableId}/records?datasetGeneration=${tables[0].datasetGeneration}`)).items
  assert.equal(records.length, 2)
  checkpoint('first Excel table used injected system picker result, real IPC/file inspection/HTTP import, and persisted two records')
  await renderer.evaluate(`location.hash=${JSON.stringify(`#/projects/${project.projectId}/data`)}`); await visible('客户一'); await capture('first-import')
  await importTable('客户二')
  tables = (await api(`/projects/${project.projectId}/tables`)).items
  assert.deepEqual(new Set(tables.map(item => item.name)), new Set(['客户一', '客户二']))
  assert.ok(tables.every(item => item.sourceKind === 'excel' && item.recordCount === 2))
  checkpoint('directory reopened the same real workflow for a second independent Excel import')
  await renderer.evaluate(`location.hash=${JSON.stringify(`#/projects/${project.projectId}/data`)}`); await visible('客户二'); await capture('directory-two-imports')
  renderer.close(); native.close(); await stop(desktop.child)
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${workspace}`, '--inspect=0'], cliArgs: [] })
  renderer = desktop.cdp; native = await connectCdp(desktop.inspectorUrl)
  await visible('本地服务正常', 30000)
  tables = (await api(`/projects/${project.projectId}/tables`)).items
  assert.deepEqual(new Set(tables.map(item => item.name)), new Set(['客户一', '客户二']))
  assert.ok(tables.every(item => item.sourceKind === 'excel' && item.recordCount === 2))
  await renderer.evaluate(`location.hash=${JSON.stringify(`#/projects/${project.projectId}/data`)}`); await visible('客户一'); await visible('客户二'); await capture('cold-restart-two-imports')
  checkpoint('a fresh Electron and sidecar process retained both imported tables and their persisted API facts')
  const report = {
    result: 'passed',
    scope: 'PM2 directory create-from-Excel only; system file panel result injected, all renderer UI, IPC registration/proof, HTTP, workbook reads and SQLite writes were real',
    checkedAt: new Date().toISOString(), checks,
    excluded: ['native picker manual interaction', 'existing-table replacement', 'detail-page editing'],
  }
  await writeFile(join(qa, 'result.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ evidence: qa.replace(root, '.'), ...report }, null, 2))
} catch (error) {
  try { await capture('failure') } catch { /* retain the original failure */ }
  const message = String(error?.message ?? error).replaceAll(workspace, '<temporary-workspace>').replaceAll(root, '<repository>')
  await writeFile(join(qa, 'failure.json'), JSON.stringify({ result: 'failed', checkedAt: new Date().toISOString(), checks, error: message }, null, 2) + '\n')
  throw error
} finally {
  renderer?.close(); native?.close(); await stop(desktop?.child)
  await rm(workspace, { recursive: true, force: true })
}

async function importTable(name) {
  await click('从 Excel 导入'); await visible('从 Excel 新建数据表')
  const picker = await renderer.evaluate(`document.body.innerText.includes('重新选择文件')?'重新选择文件':'选择 Excel 文件'`)
  await click(picker); await click('检查文件')
  await waitFor(renderer, `!!document.querySelector('[aria-label="工作表"]')`, 'multi-sheet inspection')
  const width = await viewportWidth(); await openSelect('工作表'); assert.equal(await viewportWidth(), width, 'opening native Select changed viewport width'); await chooseOption('客户'); assert.equal(await viewportWidth(), width, 'closing native Select changed viewport width')
  await click('继续字段映射'); await visible('字段映射'); await click('继续导入')
  await input('[aria-label="数据表名称"]', name); await click('确认并开始导入'); await waitFor(renderer, `!document.body.innerText.includes('从 Excel 新建数据表')&&document.body.innerText.includes(${JSON.stringify(name)})`, `directory contains ${name}`, 30000); await capture(`import-${name}`)
}
function checkpoint(message) { checks.push(message); console.log(message) }
async function visible(text, timeout = 15000) { return waitFor(renderer, `Boolean(document.body?.innerText.includes(${JSON.stringify(text)}))`, text, timeout) }
async function api(path, options = {}) {
  const { sidecar } = await renderer.evaluate('window.autoflow.getRuntimeContext()')
  const response = await fetch(`${sidecar.baseUrl}/api/v1${path}`, { ...options, body: options.body ? JSON.stringify(options.body) : undefined, headers: { 'x-autoflow-token': sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': crypto.randomUUID() } })
  assert.ok(response.ok, `${options.method ?? 'GET'} ${path}: ${response.status}`); return response.json()
}
async function click(text, selector = 'button') {
  const point = await renderer.evaluate(`(()=>{const e=[...document.querySelectorAll(${JSON.stringify(selector)})].find(x=>(x.textContent.trim()===${JSON.stringify(text)}||x.getAttribute('aria-label')===${JSON.stringify(text)})&&x.getClientRects().length);if(!e)return null;e.scrollIntoView({block:'nearest'});const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`)
  assert.ok(point, `control missing: ${text}`); await renderer.command('Input.dispatchMouseEvent',{type:'mousePressed',...point,button:'left',clickCount:1}); await renderer.command('Input.dispatchMouseEvent',{type:'mouseReleased',...point,button:'left',clickCount:1}); await wait(150)
}
async function input(selector, value) { assert.equal(await renderer.evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)return false;e.focus();Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}));return true})()`),true); await wait(100) }
async function select(label, option) {
  await openSelect(label); await chooseOption(option)
}
async function openSelect(label) { await click(label, `[aria-label=${JSON.stringify(label)}]`) }
async function chooseOption(option) {
  const point=await renderer.evaluate(`(()=>{const e=[...document.querySelectorAll('[role=option]')].find(x=>x.textContent.includes(${JSON.stringify(option)})&&x.getClientRects().length);if(!e)return null;const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`)
  assert.ok(point,`option missing: ${option}`); await renderer.command('Input.dispatchMouseEvent',{type:'mousePressed',...point,button:'left',clickCount:1}); await renderer.command('Input.dispatchMouseEvent',{type:'mouseReleased',...point,button:'left',clickCount:1}); await wait(120)
}
async function verifyKeyboardClose() {
  await click('从 Excel 导入'); await visible('从 Excel 新建数据表'); await pressEscape()
  await waitFor(renderer, `!document.body.innerText.includes('从 Excel 新建数据表')`, 'Escape closes new Excel wizard')
  assert.equal(await renderer.evaluate(`document.activeElement?.textContent?.trim()`), '从 Excel 导入')
  checkpoint('Escape closed the new Excel wizard and restored focus to its directory entry')
}
async function verifyGlobalNavigation(projectId) {
  for (const [control, heading] of [['总览','总览'],['浏览器配置','浏览器配置'],['代理管理','代理管理'],['模型管理','模型管理'],['设置','设置']]) {
    await click(control); await waitFor(renderer, `Boolean([...document.querySelectorAll('h1,h2')].find(x=>x.textContent.trim()===${JSON.stringify(heading)}))`, `${heading} opens`)
  }
  await renderer.evaluate(`location.hash=${JSON.stringify(`#/projects/${projectId}/data`)}`); await visible('还没有数据表')
  checkpoint('global overview, browser, proxy, model and settings entries opened and returned to the project directory without mutating resources')
}
async function setZoom(factor) {
  await native.evaluate(`(()=>{const wc=qaElectron.webContents.getAllWebContents().find(x=>x.getType()==='window');if(!wc)return false;wc.setZoomFactor(${factor});return true})()`)
  await wait(250)
}
async function assertNoHorizontalOverflow(label) {
  const dimensions = await renderer.evaluate(`({viewport:document.documentElement.clientWidth,page:document.documentElement.scrollWidth,dialog:(()=>{const e=document.querySelector('[role=dialog]');if(!e)return null;const r=e.getBoundingClientRect();return{left:r.left,right:r.right,width:r.width}})()})`)
  assert.ok(dimensions.page <= dimensions.viewport + 1, `${label} horizontally overflowed: ${JSON.stringify(dimensions)}`)
  if (dimensions.dialog) assert.ok(dimensions.dialog.left >= -1 && dimensions.dialog.right <= dimensions.viewport + 1, `${label} dialog exceeded viewport: ${JSON.stringify(dimensions)}`)
}
async function viewportWidth() { return renderer.evaluate('document.documentElement.clientWidth') }
async function pressEscape() { await renderer.command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'}); await renderer.command('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape'}); await wait(150) }
async function capture(name) { if (!renderer) return; const { data } = await renderer.command('Page.captureScreenshot',{format:'png',captureBeyondViewport:false}); await writeFile(join(qa,`${name}.png`),data,'base64') }
