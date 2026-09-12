import assert from 'node:assert/strict'
import { mkdtemp, mkdir, realpath, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { launchElectron, connectCdp, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const userData = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-studio-smoke-')))
const secondWorkspace = await realpath(await mkdtemp(join(tmpdir(), 'autoflow-studio-workspace-')))
await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await writeFile(join(userData, 'desktop-settings.json'), JSON.stringify({ schemaVersion: 1, currentPath: userData, previousPath: secondWorkspace, preferences: { zoom: 100, motion: 'system' } }))
const qa = join(root, 'docs/migration/automation-studio-m1-qa')
await mkdir(qa, { recursive: true })
let desktop, studio, native, devServer
const checks = []

try {
  if (process.argv.includes('--dev')) {
    const { resolveConfig } = await import('electron-vite')
    const { createServer } = await import('vite')
    const { config } = await resolveConfig({ root: join(root, 'apps/desktop') }, 'serve', 'development')
    devServer = await createServer({ ...config.renderer, root: join(root, 'apps/desktop/src/renderer'), server: { host: '127.0.0.1', port: 0 } })
    await devServer.listen()
    process.env.ELECTRON_RENDERER_URL = devServer.resolvedUrls.local[0]
  }
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'] })
  native = await connectCdp(desktop.inspectorUrl)
  await native.evaluate("globalThis.smokeElectron = process.getBuiltinModule('module').createRequire(process.cwd() + '/package.json')('electron'); true")
  let main = desktop.cdp
  await waitFor(main, `document.body?.innerText.includes('工作流工作台')`, 'main overview', 30000)
  await click(main, '', '工作流工作台', true)
  studio = await studioTarget()
  await waitFor(studio, `document.querySelector('[aria-label="添加打开网页"]') && !document.querySelector('[aria-label="添加打开网页"]').disabled`, 'catalog from real sidecar')
  assert.equal(await studio.evaluate(`document.querySelectorAll('.react-flow__node').length`), 0)
  const context = await studio.evaluate('window.autoflow.getRuntimeContext()')
  const mainContext = await main.evaluate('window.autoflow.getRuntimeContext()')
  assert.equal(context.sidecar.instanceId, mainContext.sidecar.instanceId)
  assert.equal(context.workspaceKey, mainContext.workspaceKey)
  await main.evaluate('window.autoflow.openAutomationStudio()')
  assert.equal((await targets()).filter(t => t.url.includes('view=automation-studio')).length, 1)
  checkpoint('formal empty Studio, shared sidecar/workspace, single window reuse')
  await capture('empty')

  const names = ['打开网页', '点击元素', '输入文本', '等待元素', '提取数据', '网页截图']
  for (const name of names) await click(studio, `[aria-label="添加${name}"]`)
  assert.equal(await studio.evaluate(`document.querySelectorAll('.react-flow__node').length`), 6)
  await click(studio, '.react-flow__controls-fitview')
  await wait(350)
  const ids = await studio.evaluate(`[...document.querySelectorAll('.react-flow__node')].map(n => n.dataset.id)`)
  for (let i = 0; i < ids.length - 1; i++) await drag(studio, `.react-flow__node[data-id="${ids[i]}"] .source`, `.react-flow__node[data-id="${ids[i + 1]}"] .target`)
  await waitFor(studio, `document.querySelectorAll('.react-flow__edge').length === 5`, 'six node sequential connections')
  await input(studio, '#workflow-name', 'M1 实机验收流程')
  await click(studio, `.react-flow__node[data-id="${ids[0]}"]`)
  await labeled(studio, '网页地址', 'https://example.com/{query}')
  for (let i = 1; i < 5; i++) {
    await click(studio, `.react-flow__node[data-id="${ids[i]}"]`)
    await labeled(studio, '元素选择器', i === 1 ? '#submit' : 'body')
    if (i === 2) await labeled(studio, '输入文本', '${query}')
  }
  await click(studio, '[role="tab"][data-state="inactive"]', '流程变量 0')
  await click(studio, '', '添加变量')
  await labeled(studio, '变量名', 'query')
  await studio.evaluate('document.activeElement?.blur()')
  await labeled(studio, '初始值', 'AutoFlow')
  await click(studio, '', '保存')
  await waitFor(studio, `document.querySelector('header [role=status]').innerText.includes('已保存')`, 'first real save')
  let record = await savedRecord()
  assert.equal(record.document.nodes.length, 6)
  assert.equal(record.document.edges.length, 5)
  assert.deepEqual(record.document.variables, [{ name: 'query', type: 'string', value: 'AutoFlow' }])
  assert.equal(record.document.nodes[0].config.timeoutSeconds, 60)
  assert.equal(record.issues.length, 0)
  const initialPosition = record.layout.nodes[ids[0]]
  const start = await point(studio, `.react-flow__node[data-id="${ids[0]}"]`)
  await drag(studio, `.react-flow__node[data-id="${ids[0]}"]`, { x: start.x + 40, y: start.y - 30 })
  await click(studio, '[aria-label="撤销"]')
  await click(studio, '', '保存')
  await waitFor(studio, `document.querySelector('header [role=status]').innerText.includes('已保存')`, 'one drag undo')
  assert.deepEqual((await savedRecord()).layout.nodes[ids[0]], initialPosition)
  await click(studio, '[aria-label="重做"]')
  await click(studio, '', '保存')
  await waitFor(studio, `document.querySelector('header [role=status]').innerText.includes('已保存')`, 'drag redo persisted')
  record = await savedRecord()
  assert.notDeepEqual(record.layout.nodes[ids[0]], initialPosition)
  const original = structuredClone(record)
  checkpoint('six nodes configured, connected, dragged and undo/redone through actual canvas; variable and SQLite persistence')
  await capture('saved')
  await key(studio, 'r', 4)
  await wait(250)
  assert.equal(await studio.evaluate(`document.querySelectorAll('.react-flow__node').length`), 6)
  checkpoint('Studio reload shortcut cannot discard the active document')

  // Input shortcuts stay local; canvas keyboard edits are real browser key events.
  await input(studio, '#workflow-name', 'M1 输入保护')
  await key(studio, 'Backspace', 0)
  assert.equal(await studio.evaluate(`document.querySelectorAll('.react-flow__node').length`), 6)
  await input(studio, '#workflow-name', original.document.name)
  await click(studio, `.react-flow__node[data-id="${ids[2]}"]`)
  await key(studio, 'Backspace', 0)
  await waitFor(studio, `document.querySelectorAll('.react-flow__node').length === 5`, 'node deletion')
  assert.equal(await studio.evaluate(`document.querySelectorAll('.react-flow__edge').length`), 3)
  await click(studio, '[aria-label="撤销"]')
  assert.equal(await studio.evaluate(`document.querySelectorAll('.react-flow__node').length`), 6)
  assert.equal(await studio.evaluate(`document.querySelectorAll('.react-flow__edge').length`), 5)
  await click(studio, '.react-flow__pane')
  await key(studio, 'a', 4)
  await key(studio, 'c', 4)
  await key(studio, 'v', 4)
  await waitFor(studio, `document.querySelectorAll('.react-flow__node').length === 12`, 'copy paste new nodes')
  assert.equal(await studio.evaluate(`document.querySelectorAll('.react-flow__edge').length`), 10)
  await click(studio, '[aria-label="撤销"]')
  checkpoint('input deletion protection, node deletion with incident edges, undo, copy/paste internal edges')

  await input(studio, '#workflow-name', '未保存的修改')
  await click(studio, '', '新建')
  await waitFor(studio, `document.querySelector('[role=dialog]')?.innerText.includes('保存当前流程')`, 'new draft protection')
  await click(studio, '', '取消')
  assert.equal(await studio.evaluate(`document.querySelector('#workflow-name').value`), '未保存的修改')
  await native.evaluate("smokeElectron.BrowserWindow.getAllWindows().find(w => w.webContents.getURL().includes('view=automation-studio')).close()")
  await waitFor(studio, `document.querySelector('[role=dialog]')?.innerText.includes('保存当前流程')`, 'native close protection')
  await capture('leave-confirmation')
  await click(studio, '', '取消')
  await native.evaluate("smokeElectron.BrowserWindow.getAllWindows().find(w => w.webContents.getURL().includes('view=automation-studio')).close()")
  await waitFor(studio, `Boolean(document.querySelector('[role=dialog]'))`, 'second native close')
  await click(studio, '', '保存并继续')
  await wait(500)
  assert.equal((await targets()).filter(t => t.url.includes('view=automation-studio')).length, 0)
  studio.close()
  await main.evaluate('window.autoflow.openAutomationStudio()')
  studio = await studioTarget()
  await waitFor(studio, `Boolean(document.querySelector('[aria-label="添加打开网页"]'))`, 'Studio reopened')
  await click(studio, '', '打开')
  await waitFor(studio, `document.querySelector('[role=dialog]')?.innerText.includes('未保存的修改')`, 'open saved workflow list')
  await click(studio, '', '未保存的修改', true)
  await waitFor(studio, `document.querySelectorAll('.react-flow__node').length === 6`, 'document restored')
  checkpoint('new cancel; native close cancel and save; Studio reopen/Open restores document')

  await input(studio, '#workflow-name', '恢复后草稿')
  await studio.evaluate('window.autoflow.restartSidecar()')
  await waitFor(studio, `!document.querySelector('[aria-label="工作流工作台"] button')?.disabled && document.querySelector('#workflow-name')?.value === '恢复后草稿'`, 'draft retained on sidecar restart')
  await waitFor(studio, `[...document.querySelectorAll('header button')].some(b => b.textContent.trim() === '保存' && !b.disabled)`, 'new sidecar connection')
  await click(studio, '[aria-label="撤销"]')
  assert.equal(await studio.evaluate(`document.querySelector('#workflow-name').value`), '未保存的修改')
  await click(studio, '', '保存')
  await waitFor(studio, `document.querySelector('header [role=status]').innerText.includes('已保存')`, 'save after restart')
  record = await savedRecord()
  assert.equal(record.document.id, original.document.id)
  assert.deepEqual(record.document.nodes, original.document.nodes)
  assert.deepEqual(record.document.edges, original.document.edges)
  checkpoint('same-workspace sidecar restart retains draft/undo and saves against real revision')
  await capture('restored')

  // The existing "previous workspace" choice drives the real switch without a
  // test-only IPC or a mocked database. Both directories belong to this test.
  await input(studio, '#workflow-name', '切换前草稿')
  let choice = await main.evaluate("window.autoflow.chooseWorkspace('previous')")
  assert.equal(choice.ok, true)
  await beginSwitch(choice.value.id)
  await waitFor(studio, `Boolean(document.querySelector('[role=dialog]'))`, 'workspace leave confirmation')
  await click(studio, '', '取消')
  assert.equal((await waitFor(main, 'window.smokeSwitchResult', 'cancelled switch')).ok, false)
  assert.equal(await studio.evaluate(`document.querySelector('#workflow-name').value`), '切换前草稿')
  await beginSwitch(choice.value.id)
  await waitFor(studio, `Boolean(document.querySelector('[role=dialog]'))`, 'workspace discard confirmation')
  await click(studio, '', '放弃修改')
  assert.equal((await waitFor(main, 'window.smokeSwitchResult', 'completed switch')).ok, true)
  await waitFor(studio, `document.querySelector('#workflow-name')?.value === '未命名流程' && !document.querySelector('#workflow-name').disabled`, 'new workspace editor')
  assert.equal((await studio.evaluate('window.autoflow.getRuntimeContext()')).workspaceKey, secondWorkspace)
  assert.equal(await studio.evaluate(`document.querySelectorAll('.react-flow__node').length`), 0)
  await click(studio, '', '打开')
  await waitFor(studio, `document.body.innerText.includes('还没有保存的流程')`, 'isolated workspace list')
  await click(studio, '', '关闭')
  choice = await main.evaluate("window.autoflow.chooseWorkspace('previous')")
  assert.equal((await main.evaluate(`window.autoflow.confirmWorkspace(${JSON.stringify(choice.value.id)})`)).ok, true)
  await waitFor(studio, `document.querySelector('#workflow-name') && !document.querySelector('#workflow-name').disabled`, 'original workspace reconnected')
  await click(studio, '', '打开')
  await waitFor(studio, `document.body.innerText.includes('未保存的修改')`, 'original workspace workflow')
  await click(studio, '', '未保存的修改', true)
  await waitFor(studio, `document.querySelectorAll('.react-flow__node').length === 6`, 'original workspace document')
  checkpoint('workspace cancel preserves draft; discard switch isolates lists/documents; switching back restores saved workflow')

  // Deliberately corrupt only the stopped, empty test workspace to exercise real
  // backend-start failure and rollback, retaining the draft until success.
  await rm(join(secondWorkspace, 'data/autoflow.sqlite3-wal'), { force: true })
  await rm(join(secondWorkspace, 'data/autoflow.sqlite3-shm'), { force: true })
  await writeFile(join(secondWorkspace, 'data/autoflow.sqlite3'), 'invalid sqlite fixture')
  await input(studio, '#workflow-name', '回滚保留草稿')
  await native.evaluate("smokeElectron.BrowserWindow.getAllWindows().find(w => w.webContents.getURL().includes('view=automation-studio')).minimize()")
  choice = await main.evaluate("window.autoflow.chooseWorkspace('previous')")
  await beginSwitch(choice.value.id)
  await waitFor(studio, `Boolean(document.querySelector('[role=dialog]'))`, 'rollback draft question')
  assert.equal(await native.evaluate("smokeElectron.BrowserWindow.getAllWindows().find(w => w.webContents.getURL().includes('view=automation-studio')).isMinimized()"), false)
  await click(studio, '', '放弃修改')
  const failed = await waitFor(main, 'window.smokeSwitchResult', 'failed workspace rollback', 30000)
  assert.equal(failed.ok, false)
  assert.equal(failed.error.code, 'WORKSPACE_SWITCH_ROLLED_BACK')
  await waitFor(studio, `document.querySelector('#workflow-name')?.value === '回滚保留草稿' && !document.querySelector('#workflow-name').disabled`, 'rollback preserves unlocked draft')
  assert.equal(await studio.evaluate(`document.querySelectorAll('.react-flow__node').length`), 6)
  await click(studio, '[aria-label="撤销"]')
  assert.equal(await studio.evaluate(`document.querySelector('#workflow-name').value`), '未保存的修改')
  checkpoint('minimized Studio restores before confirmation; real backend switch failure preserves draft and undo')

  await native.evaluate("smokeElectron.BrowserWindow.getAllWindows().find(w => !w.webContents.getURL().includes('view=automation-studio')).close()")
  main.close()
  await studio.evaluate('window.autoflow.restartSidecar()')
  await waitFor(studio, `[...document.querySelectorAll('header button')].some(b => b.textContent.trim() === '保存' && !b.disabled)`, 'Studio recovery with main window closed')
  await click(studio, '', '保存')
  await waitFor(studio, `document.querySelector('header [role=status]').innerText.includes('已保存')`, 'Studio saves without main window')
  await native.evaluate("smokeElectron.app.emit('activate')")
  const mainTarget = (await targets()).find(t => t.type === 'page' && !t.url.includes('view=automation-studio'))
  main = await connectCdp(mainTarget.webSocketDebuggerUrl)
  await waitFor(main, `Boolean(window.autoflow)`, 'reopened main preload')
  checkpoint('main window closes independently; Studio continues service recovery and saving')

  await input(studio, '#workflow-name', '退出时保存的流程')
  await main.evaluate('window.autoflow.quitApplication()')
  await waitFor(studio, `Boolean(document.querySelector('[role=dialog]'))`, 'quit confirmation')
  await click(studio, '', '取消')
  assert.equal(desktop.child.exitCode, null)
  const beforeQuit = await studio.evaluate('window.autoflow.getRuntimeContext()')
  record = { ...await savedRecord(), document: { ...(await savedRecord()).document, name: '退出时保存的流程' } }
  await main.evaluate('window.autoflow.quitApplication()')
  await waitFor(studio, `Boolean(document.querySelector('[role=dialog]'))`, 'second quit confirmation')
  native.close()
  await click(studio, '', '保存并继续')
  for (let i = 0; i < 150 && desktop.child.exitCode === null; i++) await wait(100)
  assert.equal(desktop.child.exitCode, 0)
  await assert.rejects(fetch(`${beforeQuit.sidecar.baseUrl}/health`, { signal: AbortSignal.timeout(1000) }))
  checkpoint('application quit cancel and save complete before sidecar shutdown')

  // Restart the entire Electron process using the same isolated workspace.
  studio.close(); main.close(); native.close(); await stop(desktop.child)
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'] })
  await waitFor(desktop.cdp, `document.body?.innerText.includes('工作流工作台')`, 'restarted main', 30000)
  await desktop.cdp.evaluate('window.autoflow.openAutomationStudio()')
  studio = await studioTarget()
  await waitFor(studio, `Boolean(document.querySelector('[aria-label="添加打开网页"]'))`, 'restarted Studio')
  await click(studio, '', '打开')
  await waitFor(studio, `document.querySelector('[role=dialog]')?.innerText.includes('退出时保存的流程')`, 'persisted workflow after app restart')
  await click(studio, '', '退出时保存的流程', true)
  await waitFor(studio, `document.querySelectorAll('.react-flow__node').length === 6`, 'workflow after app restart')
  assert.deepEqual((await savedRecord()).layout, record.layout)
  assert.deepEqual((await savedRecord()).document, record.document)
  checkpoint('full application restart restores same SQLite document and layout')

  await waitFor(studio, `!document.querySelector('[data-slot=modal-overlay]')`, 'open dialog transition completed')
  await click(studio, '[aria-label="添加打开网页"]')
  await waitFor(studio, `document.querySelectorAll('.react-flow__node').length === 7`, 'incomplete node added')
  await click(studio, '', '保存')
  await waitFor(studio, `document.querySelector('header [role=status]').innerText.includes('已保存')`, 'incomplete draft save')
  const incomplete = await savedRecord()
  const last = incomplete.document.nodes.at(-1)
  assert.equal(last.config.url, '')
  assert.ok(incomplete.issues.some(issue => issue.nodeId === last.id && issue.path.at(-1) === 'url'))
  assert.ok(incomplete.issues.some(issue => issue.code === 'DISCONNECTED_NODE'))
  await capture('incomplete')
  checkpoint('empty URL and disconnected node save as an incomplete draft with exact field issues')

  const { sidecar } = await studio.evaluate('window.autoflow.getRuntimeContext()')
  const headers = { 'x-autoflow-token': sidecar.token, 'content-type': 'application/json' }
  const external = await fetch(`${sidecar.baseUrl}/api/v1/workflows/${incomplete.document.id}`, {
    method: 'PUT', headers, body: JSON.stringify({ document: { ...incomplete.document, name: '另一编辑者的修改' }, layout: incomplete.layout, expectedRevision: incomplete.revision }),
  })
  assert.equal(external.status, 200)
  await input(studio, '#workflow-name', '冲突中保留的草稿')
  await click(studio, '', '保存')
  await waitFor(studio, `[...document.querySelectorAll('button')].some(b => b.textContent === '另存为新流程')`, 'real revision conflict')
  assert.equal(await studio.evaluate(`document.querySelector('#workflow-name').value`), '冲突中保留的草稿')
  await capture('conflict')
  await click(studio, '', '另存为新流程')
  await waitFor(studio, `document.querySelector('header [role=status]').innerText.includes('已保存')`, 'conflicting draft saved separately')
  const list = await (await fetch(`${sidecar.baseUrl}/api/v1/workflows`, { headers })).json()
  assert.equal(list.items.length, 2)
  assert.ok(list.items.some(item => item.id === incomplete.document.id && item.name === '另一编辑者的修改'))
  assert.ok(list.items.some(item => item.id !== incomplete.document.id && item.name === '冲突中保留的草稿 副本'))
  checkpoint('real external revision conflict preserves both versions through save-as-new')
  const result = { result: 'passed', entry: desktop.packaged ? 'packaged' : process.env.ELECTRON_RENDERER_URL ? 'development-url' : 'built-html', platform: process.platform, arch: process.arch, checks }
  await writeFile(join(qa, `${result.entry}.json`), JSON.stringify(result, null, 2) + '\n')
  console.log(JSON.stringify(result, null, 2))
} catch (error) {
  try { if (desktop) console.error('Main renderer:', await desktop.cdp.evaluate('({url: location.href, text: document.body?.innerText})')) } catch {}
  try { if (studio) { await capture('failure'); console.error(await studio.evaluate('document.body?.innerText')) } } catch { /* Preserve the original error. */ }
  throw error
} finally {
  studio?.close(); desktop?.cdp.close(); native?.close(); await stop(desktop?.child)
  await devServer?.close()
  await rm(userData, { recursive: true, force: true })
  await rm(secondWorkspace, { recursive: true, force: true })
}

async function beginSwitch(id) {
  await desktop.cdp.evaluate(`window.smokeSwitchResult = null; void window.autoflow.confirmWorkspace(${JSON.stringify(id)}).then(result => { window.smokeSwitchResult = result })`)
}

function checkpoint(message) { checks.push(message); console.log(message) }
async function targets() { return (await fetch(`${desktop.debugOrigin}/json/list`)).json() }
async function studioTarget() {
  for (let i = 0; i < 100; i++) { const target = (await targets()).find(t => t.type === 'page' && t.url.includes('view=automation-studio')); if (target) return connectCdp(target.webSocketDebuggerUrl); await wait(100) }
  throw new Error('Studio target not created')
}
async function evaluate(cdp, fn, ...args) { return cdp.evaluate(`(${fn})(${args.map(value => JSON.stringify(value) ?? 'null').join(',')})`) }
async function point(cdp, selector, text, prefix = false) {
  const result = await evaluate(cdp, (query, text, prefix) => {
    const el = query ? document.querySelector(query) : [...document.querySelectorAll('button')].find(n => prefix ? n.textContent.trim().startsWith(text) : n.textContent.trim() === text)
    if (!el) return null
    el.scrollIntoView({ block: 'nearest' }); const r = el.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }
  }, selector, text, prefix)
  if (!result && selector && text) return point(cdp, '', text, prefix)
  assert.ok(result, `control missing: ${selector || text}`)
  return result
}
async function click(cdp, selector, text, prefix) {
  const position = await point(cdp, selector, text, prefix)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...position, button: 'left', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...position, button: 'left', clickCount: 1 })
  await wait(100)
}
async function drag(cdp, from, to) {
  const a = await point(cdp, from), b = typeof to === 'string' ? await point(cdp, to) : to
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...a })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...a, button: 'left', buttons: 1, clickCount: 1 })
  for (let i = 1; i <= 8; i++) await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', x: a.x + (b.x - a.x) * i / 8, y: a.y + (b.y - a.y) * i / 8, button: 'left', buttons: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...b, button: 'left', clickCount: 1 })
  await wait(100)
}
async function input(cdp, selector, value) {
  assert.ok(await evaluate(cdp, (selector, value) => {
    const el = document.querySelector(selector)
    if (!(el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement)) return false
    el.focus(); Object.getOwnPropertyDescriptor(el instanceof HTMLInputElement ? HTMLInputElement.prototype : HTMLTextAreaElement.prototype, 'value').set.call(el, value)
    el.dispatchEvent(new Event('input', { bubbles: true })); return true
  }, selector, value), `input missing: ${selector}`)
  await wait(75)
}
async function labeled(cdp, label, value) {
  const selector = await evaluate(cdp, label => { const el = [...document.querySelectorAll('label')].find(n => n.textContent.trim() === label); return el?.htmlFor ? '#' + CSS.escape(el.htmlFor) : null }, label)
  assert.ok(selector, `label missing: ${label}`); await input(cdp, selector, value)
}
async function key(cdp, key, modifiers) {
  await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key, code: key.length === 1 ? `Key${key.toUpperCase()}` : key, modifiers, windowsVirtualKeyCode: key === 'Backspace' ? 8 : key.toUpperCase().charCodeAt(0) })
  await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key, modifiers }); await wait(100)
}
async function savedRecord() {
  const { sidecar } = await studio.evaluate('window.autoflow.getRuntimeContext()')
  const headers = { 'x-autoflow-token': sidecar.token }
  const response = await fetch(`${sidecar.baseUrl}/api/v1/workflows`, { headers }); assert.equal(response.status, 200)
  const list = await response.json(); assert.equal(list.items.length, 1)
  const record = await fetch(`${sidecar.baseUrl}/api/v1/workflows/${list.items[0].id}`, { headers }); assert.equal(record.status, 200); return record.json()
}
async function capture(name) {
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await wait(200)
  const { data } = await studio.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  await writeFile(join(qa, `${desktop.packaged ? 'packaged' : process.env.ELECTRON_RENDERER_URL ? 'dev' : 'built'}-${name}.png`), data, 'base64')
}
