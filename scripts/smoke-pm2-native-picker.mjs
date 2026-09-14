// Run with a native UI operator: select the printed fixture, cancel once, then select it.
// No dialog results are injected. Only disposable workspace and workbook paths are used.
import assert from 'node:assert/strict'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { mkdtemp, mkdir, realpath, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { launchElectron, waitFor, wait } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'
const root = resolve(import.meta.dirname, '..'), run = promisify(execFile)
const workspace = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-native-picker-')))
const fixture = join(workspace, 'native.xlsx')
const parent = join(root, 'docs/migration/pm2-native-picker-qa'); await mkdir(parent, { recursive: true })
const qa = await mkdtemp(join(parent, 'run-'))
await writeFile(join(workspace, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await run('uv', ['run', '--project', join(root, 'apps/backend'), 'python', '-c', `from openpyxl import Workbook; b=Workbook(); s=b.active; s.append(['编号']); s.append(['001']); b.save(${JSON.stringify(fixture)})`])
let app
try {
  app = await launchElectron(root, { launchArgs: [`--user-data-dir=${workspace}`], cliArgs: [] })
  const page = app.cdp
  // Native modal panels can pause renderer evaluation until the operator responds.
  const operatorPage = { evaluate: expression => page.evaluate(expression, 180000) }
  await waitFor(page, `window.autoflow?.getRuntimeContext().then(r=>r.sidecar.state==='ready')`, 'service ready', 30000)
  const context = await page.evaluate('window.autoflow.getRuntimeContext()')
  const response = await fetch(`${context.sidecar.baseUrl}/api/v1/projects`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'x-autoflow-token': context.sidecar.token, 'Idempotency-Key': crypto.randomUUID() }, body: JSON.stringify({ name: '原生文件面板验收', description: '隔离合成数据' }) })
  assert.equal(response.status, 201); const project = await response.json()
  console.log(JSON.stringify({ pid: app.child.pid, fixture, instructions: 'Operate the real open panel: cancel first, then select the fixture. Then cancel the save panel.' }))
  await page.evaluate(`globalThis.nativePickerResult={};window.autoflow.chooseExcelInput(${JSON.stringify(project.projectId)}).then(r=>nativePickerResult.cancel=r);true`)
  await waitFor(operatorPage, 'nativePickerResult.cancel', 'operator cancels native open panel', 180000)
  assert.deepEqual(await page.evaluate('nativePickerResult.cancel'), { ok: true, value: null })
  await page.evaluate(`window.autoflow.chooseExcelInput(${JSON.stringify(project.projectId)}).then(r=>nativePickerResult.selection=r);true`)
  await waitFor(operatorPage, 'nativePickerResult.selection', 'operator selects native workbook', 180000)
  const selected = await page.evaluate('nativePickerResult.selection')
  assert.equal(selected.ok, true); assert.equal(selected.value.displayName, 'native.xlsx')
  assert.equal('path' in selected.value, false); assert.equal(typeof selected.value.selectionToken, 'string')
  await page.evaluate(`window.autoflow.chooseXlsxOutput(${JSON.stringify(project.projectId)},'native-export.xlsx').then(r=>nativePickerResult.saveCancel=r);true`)
  await waitFor(operatorPage, 'nativePickerResult.saveCancel', 'operator cancels native save panel', 180000)
  assert.deepEqual(await page.evaluate('nativePickerResult.saveCancel'), { ok: true, value: null })
  await page.evaluate(`location.hash=${JSON.stringify(`#/projects/${project.projectId}/data`)}`)
  await wait(400)
  const { data } = await page.command('Page.captureScreenshot', { format: 'png' })
  await writeFile(join(qa, 'after-native-picker.png'), data, 'base64')
  const report = { result: 'passed', platform: process.platform, arch: process.arch, checkedAt: new Date().toISOString(), scope: 'Unmodified native macOS open/save panels with an active UI operator; actual Electron IPC and token registration', checks: ['native open cancellation returns successful null', 'native workbook selection returns an opaque token and display name without a path', 'native save cancellation returns successful null'], excludes: ['native save publication; covered separately through injected panel results in the full export workflow'] }
  await writeFile(join(qa, 'result.json'), JSON.stringify(report, null, 2) + '\n'); console.log(JSON.stringify({ qa, ...report }))
} finally { app?.cdp.close(); await stop(app?.child); await rm(workspace, { recursive: true, force: true }) }
