import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { randomUUID } from 'node:crypto'
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename, join, resolve } from 'node:path'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const gitHead = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim()
const sourceKernel = process.env.AUTOFLOW_B1_KERNEL_DIR
  ?? '/Users/zhangtiancheng/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2'
const kernelVersion = basename(sourceKernel).replace(/^chromium-/, '')
const evidenceRoot = join(root, 'docs/migration/studio-backend-migration/evidence/b3')
await mkdir(evidenceRoot, { recursive: true })
const evidenceDir = await mkdtemp(join(evidenceRoot, 'formal-control-flow-electron-'))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-b3-control-flow-'))
const workflowName = 'B3 控制流正式闭环'
const checks = []
const observedEvents = []
let desktop
let main
let native
let studio
let eventAbort

try {
  assert.equal(process.platform, 'darwin', 'formal evidence requires macOS')
  assert.equal(process.arch, 'arm64', 'formal evidence requires native arm64 Node/Electron')
  await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
  await mkdir(join(userData, 'data', 'kernels'), { recursive: true })
  execFileSync('cp', ['-cR', sourceKernel, join(userData, 'data', 'kernels', basename(sourceKernel))])

  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'] })
  assert.equal(desktop.packaged, false)
  main = desktop.cdp
  native = await connectCdp(desktop.inspectorUrl)
  await native.evaluate("globalThis.qaElectron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');true")
  await main.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(main, "document.body?.innerText.includes('本地服务正常')", 'main service readiness', 30_000)
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  eventAbort = new AbortController()
  void collectEvents(runtime, eventAbort.signal, observedEvents)
  const profile = await api(runtime, '/v1/profiles', {
    method: 'POST',
    body: {
      name: 'B3 控制流纯数据验收配置', description: '临时工作区；控制流不得启动浏览器', startUrl: 'about:blank',
      locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false, headless: true, humanize: false,
      humanPreset: 'default', userAgent: null, viewportJson: null, colorScheme: 'light', extensionPathsJson: [], expertArgsJson: [],
      browserVersion: kernelVersion, browserEdition: 'public', releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null,
    },
  })
  assert.deepEqual(cloakProcesses(userData), [])
  checkpoint('真实 sidecar 使用临时工作区和主应用 Profile；运行前无 CloakBrowser 进程')

  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库') && document.body.innerText.includes('227')", 'formal Studio', 30_000)
  await waitFor(studio, `document.querySelector('[aria-label="运行浏览器配置"]')?.value === ${JSON.stringify(profile.id)}`, 'managed Profile selection')
  await click(studio, '新建')
  await waitFor(studio, "document.querySelectorAll('.react-flow__node').length === 0", 'new empty workflow')
  await setInput(studio, 'input[placeholder="工作流名称"]', workflowName)
  await click(studio, '模块条')

  await addBlock(studio, '添加模块', '设置变量')
  await setInput(studio, '[placeholder="变量名"]', 'total')
  await setInput(studio, '[placeholder="变量的值"]', '0')

  await addBlock(studio, '添加模块', '循环')
  await setInput(studio, '[placeholder="输入循环次数或变量"]', '3')
  await setInput(studio, '[placeholder="索引变量名（默认：index）"]', 'loop_index')

  await addBlock(studio, '添加循环体步骤', '自增自减')
  await setInput(studio, '[placeholder="要操作的变量名"]', 'total')
  await setInput(studio, '[placeholder="每次增加或减少的值"]', '1')

  await addBlock(studio, '添加模块', '条件判断')
  await setInputAt(studio, '[placeholder="输入变量 {变量名} 或字面量"]', 0, '{total}')
  await setInputAt(studio, '[placeholder="输入变量 {变量名} 或字面量"]', 1, '3')

  await addBlock(studio, '添加「是」分支步骤', '设置变量')
  await setInput(studio, '[placeholder="变量名"]', 'outcome')
  await setInput(studio, '[placeholder="变量的值"]', 'passed')

  await addBlock(studio, '添加「否」分支步骤', '设置变量')
  await setInput(studio, '[placeholder="变量名"]', 'outcome')
  await setInput(studio, '[placeholder="变量的值"]', 'failed')

  await addBlock(studio, '添加模块', '设置变量')
  await setInput(studio, '[placeholder="变量名"]', 'finished')
  await setInput(studio, '[placeholder="变量的值"]', '1')
  checkpoint('通过模块条真实点击完成初始化、三轮循环、真假分支和汇合后的尾节点')

  await click(studio, '流程图')
  const subflowInnerId = await addCanvasNode(studio, '设置变量', { xRatio: 0.82, yRatio: 0.12 })
  await setInput(studio, '[placeholder="变量名"]', 'inside')
  await setInput(studio, '[placeholder="变量的值"]', '42')

  const headerId = await addCanvasNode(studio, '分组', { xRatio: 0.65, yRatio: 0.05 })
  await click(studio, '', '[role="switch"]')
  await setInput(studio, '[placeholder="子流程名称"]', '正式子流程')
  await resizeGroup(studio, headerId, 100, 0)

  const subflowCallId = await addCanvasNode(studio, '子流程')
  await selectNative(studio, '#subflowGroupId', '[分组] 正式子流程')
  const subflowTailId = await addCanvasNode(studio, '设置变量', { xRatio: 0.12, yRatio: 0.32 })
  await setInput(studio, '[placeholder="变量名"]', 'subflow_finished')
  await setInput(studio, '[placeholder="变量的值"]', '1')
  await connectNodes(studio, subflowCallId, subflowTailId)
  checkpoint('通过流程图真实右键入口创建子流程分组、组内步骤和独立调用；调用按稳定节点 ID 绑定')

  await click(studio, '保存')
  await waitFor(studio, `document.body?.innerText.includes(${JSON.stringify(`工作流已保存: ${workflowName}`)})`, 'workflow save acknowledgement')
  const saved = (await api(runtime, '/workflows')).find(item => item.name === workflowName)
  assert.ok(saved)
  const byType = type => saved.nodes.filter(node => node.data.moduleType === type)
  assert.equal(byType('loop').length, 1)
  assert.equal(byType('condition').length, 1)
  assert.equal(byType('group').length, 1)
  assert.equal(byType('subflow').length, 1)
  assert.equal(saved.nodes.find(node => node.id === subflowCallId)?.data.subflowGroupId, headerId)
  const group = saved.nodes.find(node => node.id === headerId)
  const inner = saved.nodes.find(node => node.id === subflowInnerId)
  assert.ok(inner.position.x >= group.position.x && inner.position.x <= group.position.x + group.data.width)
  assert.ok(inner.position.y >= group.position.y && inner.position.y <= group.position.y + group.data.height)
  assert.ok(saved.edges.some(edge => edge.sourceHandle === 'true'))
  assert.ok(saved.edges.some(edge => edge.sourceHandle === 'false'))
  assert.ok(saved.edges.some(edge => edge.sourceHandle === 'loop'))
  assert.ok(saved.edges.some(edge => edge.sourceHandle === 'done'))
  assert.ok(saved.edges.some(edge => edge.source === subflowCallId && edge.target === subflowTailId))
  checkpoint('真实 HTTP/SQLite 文档包含条件双分支、循环双出口、子流程定义与独立调用')

  const savedNodeCount = saved.nodes.length
  const savedEdgeCount = saved.edges.length
  await closeWindowThroughOs()
  studio.close(); studio = undefined
  await waitForNoStudio(desktop.debugOrigin)
  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库')", 'reopened Studio', 30_000)
  if (!await studio.evaluate(`document.querySelector('input[placeholder="工作流名称"]')?.value === ${JSON.stringify(workflowName)}`)) {
    await click(studio, '打开')
    await click(studio, `打开工作流 ${workflowName}`, '[role="button"]')
  }
  await waitFor(studio, `document.querySelector('input[placeholder="工作流名称"]')?.value === ${JSON.stringify(workflowName)} && document.querySelectorAll('.react-flow__node').length === ${savedNodeCount}`, 'persisted workflow reopen')
  assert.equal(await studio.evaluate("document.querySelectorAll('.react-flow__edge').length"), savedEdgeCount)
  checkpoint('macOS Cmd+W 正常关闭后从主窗口重开，节点、结构和配置全部恢复')

  await click(studio, '运行 (F5)', '[aria-label="运行 (F5)"]')
  await click(studio, '运行 (F5)', '[role="menuitem"]')
  const startedRun = await waitForValue(async () => {
    const page = await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(saved.id)}&cursor=0&limit=20`)
    return page.items[0] ?? null
  }, 'persisted workflow run', 20_000)
  const terminalRun = await waitForValue(async () => {
    const value = await api(runtime, `/workflow-runs/${encodeURIComponent(startedRun.runId)}`)
    return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.status) ? value : null
  }, 'workflow terminal persistence', 60_000)
  assert.equal(terminalRun.status, 'completed')
  await waitFor(studio, "document.body?.innerText.includes('执行完成')", 'rendered terminal event', 10_000)

  const results = await api(runtime, `/workflow-runs/${encodeURIComponent(startedRun.runId)}/results?cursor=0&limit=200`)
  const logs = await api(runtime, `/workflow-runs/${encodeURIComponent(startedRun.runId)}/logs?cursor=0&limit=500`)
  const incrementId = byType('increment_decrement')[0].id
  const conditionId = byType('condition')[0].id
  const branchNodes = byType('set_variable').filter(node => ['passed', 'failed'].includes(node.data.variableValue))
  const trueId = branchNodes.find(node => node.data.variableValue === 'passed').id
  const falseId = branchNodes.find(node => node.data.variableValue === 'failed').id
  const incrementResults = results.items.filter(item => item.nodeId === incrementId)
  assert.deepEqual(incrementResults.map(item => item.values.new_value), [1, 2, 3])
  assert.deepEqual(incrementResults.map(item => item.executionContext.loops[0].iteration), [1, 2, 3])
  assert.equal(results.items.filter(item => item.nodeId === conditionId).length, 1)
  assert.equal(results.items.filter(item => item.nodeId === trueId).length, 1)
  assert.equal(results.items.filter(item => item.nodeId === falseId).length, 0)
  const innerResult = results.items.find(item => item.nodeId === subflowInnerId)
  assert.deepEqual(innerResult.executionContext.scopes, [{ kind: 'subflow', id: headerId, name: '正式子流程' }])
  const callResult = results.items.find(item => item.nodeId === subflowCallId)
  assert.deepEqual(callResult.values, { subflow: '正式子流程', executed_nodes: 1, failed_nodes: 0 })
  const subflowTailResult = results.items.find(item => item.nodeId === subflowTailId)
  assert.deepEqual(subflowTailResult.executionContext.loops, [])
  assert.equal(new Set(results.items.map(item => item.executionId)).size, results.items.length)
  assert.ok(logs.items.some(item => item.nodeId === trueId && item.message.includes('outcome = passed')))
  assert.equal(logs.items.some(item => item.nodeId === falseId), false)
  assert.ok(observedEvents.some(event => event.name === 'execution:completed' && event.data?.runId === startedRun.runId))
  checkpoint('真实 worker 完成三轮循环、真分支和子流程；假分支无副作用，结果按 executionId、轮次与作用域持久化')

  assert.deepEqual(cloakProcesses(userData), [])
  const sqlite = sqliteEvidence(userData, saved.id, startedRun.runId)
  assert.equal(sqlite.document[0].nodeCount, savedNodeCount)
  assert.equal(sqlite.run[0].status, 'completed')
  assert.equal(sqlite.run[0].cleanupState, 'completed')
  assert.equal(sqlite.run[0].activeSlot, null)
  await capture(studio, join(evidenceDir, 'completed.png'))
  const report = {
    evidenceId: 'BE-B3-formal-control-flow-electron', checkedAt: new Date().toISOString(), gitHead,
    result: 'passed', platform: `${process.platform}-${process.arch}`, entry: 'development-build',
    workflowId: saved.id, profileId: profile.id, runId: startedRun.runId, checks,
    workflowPersistence: { revision: saved.revision, nodeCount: savedNodeCount, edgeCount: savedEdgeCount },
    execution: { status: terminalRun.status, resultCount: results.items.length, logCount: logs.items.length },
    assertions: {
      loopValues: incrementResults.map(item => item.values.new_value),
      loopIterations: incrementResults.map(item => item.executionContext.loops[0].iteration),
      selectedBranch: 'true', skippedBranchNodeId: falseId,
      subflowScope: innerResult.executionContext.scopes,
      parallelStartNodes: [byType('set_variable').find(node => node.data.variableName === 'total').id, subflowCallId],
    },
    httpEvidence: { results: results.items, logs: logs.items }, sqliteEvidence: sqlite,
    browserEvidence: { cloakBrowserProcessesAfter: cloakProcesses(userData) },
    boundaries: {
      workspace: 'ephemeral', userDatabaseTouched: false, browserLaunch: 'none (pure data)',
      interaction: 'main window and formal Studio UI through CDP mouse/keyboard plus macOS Cmd+W; public APIs and SQLite only read evidence after UI actions; no Store or page-internal business function access',
      parallelMeaning: 'the persisted graph has separate top-level control-flow and subflow-call entry nodes; the production scheduler executes start nodes concurrently',
    },
  }
  await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
} catch (error) {
  await writeFile(join(evidenceDir, 'blocked.json'), JSON.stringify({ checkedAt: new Date().toISOString(), gitHead, checks, observedEvents, error: error instanceof Error ? error.stack : String(error) }, null, 2) + '\n')
  throw error
} finally {
  eventAbort?.abort(); studio?.close(); main?.close(); native?.close(); await stop(desktop?.child)
  await rm(userData, { recursive: true, force: true })
}

function checkpoint(message) { checks.push(message); console.log(message) }

async function api(runtime, path, options = {}) {
  const response = await fetch(`${runtime.sidecar.baseUrl}/api${path}`, {
    method: options.method ?? 'GET',
    headers: { 'x-autoflow-token': runtime.sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': randomUUID() },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })
  if (!response.ok) throw new Error(`${options.method ?? 'GET'} /api${path}: ${response.status} ${await response.text()}`)
  return response.status === 204 ? undefined : response.json()
}

async function collectEvents(runtime, signal, output) {
  try {
    const response = await fetch(`${runtime.sidecar.baseUrl}/api/events/stream?afterSeq=0`, { headers: { 'x-autoflow-token': runtime.sidecar.token }, signal })
    const reader = response.body.getReader(), decoder = new TextDecoder()
    let buffer = ''
    while (!signal.aborted) {
      const { done, value } = await reader.read()
      if (done) return
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
      let boundary
      while ((boundary = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2)
        let id = '', name = 'message', data = ''
        for (const line of frame.split('\n')) {
          if (line.startsWith('id:')) id = line.slice(3).trim()
          else if (line.startsWith('event:')) name = line.slice(6).trim()
          else if (line.startsWith('data:')) data += line.slice(5).trim()
        }
        if (id) output.push({ id: Number(id), name, data: data ? JSON.parse(data) : null })
      }
    }
  } catch (error) { if (!signal.aborted) output.push({ name: 'collector:error', data: String(error) }) }
}

async function openStudioFromMain(cdp, origin) {
  await click(cdp, '工作流工作台')
  const target = await waitForValue(async () => {
    const targets = await (await fetch(`${origin}/json/list`)).json()
    return targets.find(item => item.type === 'page' && item.url.includes('studio.html')) ?? null
  }, 'Studio target', 15_000)
  return connectCdp(target.webSocketDebuggerUrl)
}

async function waitForNoStudio(origin, timeoutMs = 15_000) {
  await waitForValue(async () => {
    const targets = await (await fetch(`${origin}/json/list`)).json()
    return targets.some(target => target.type === 'page' && target.url.includes('studio.html')) ? null : true
  }, 'Studio window close', timeoutMs)
}

async function closeWindowThroughOs() {
  for (let attempt = 0; attempt < 3; attempt++) {
    const exists = await native.evaluate("(()=>{const w=qaElectron.BrowserWindow.getAllWindows().find(w=>w.getTitle().includes('工作流工作台'));if(!w)return false;qaElectron.app.focus({steal:true});w.show();w.focus();return true})()")
    if (!exists) return
    await wait(250)
    execFileSync('osascript', ['-e', 'tell application "System Events" to keystroke "w" using command down'])
    await wait(500)
    if (!await native.evaluate("qaElectron.BrowserWindow.getAllWindows().some(w=>w.getTitle().includes('工作流工作台'))")) return
    if (await studio.evaluate("[...document.querySelectorAll('button')].some(e=>e.getClientRects().length&&e.textContent.includes('保存后继续'))")) {
      await click(studio, '保存后继续')
      await wait(700)
    }
  }
}

async function waitForValue(read, description, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  let last
  while (Date.now() < deadline) {
    last = await read()
    if (last) return last
    await wait(150)
  }
  throw new Error(`timed out waiting for ${description}: ${JSON.stringify(last)}`)
}

async function point(cdp, selector, text = '') {
  return waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length),text=${JSON.stringify(text)};const e=!text?rows[0]:rows.find(e=>e.getAttribute('aria-label')===text)||rows.find(e=>e.textContent.trim()===text)||rows.find(e=>e.textContent.includes(text));if(!e||e.disabled)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `unobscured ${text || selector}`)
}

async function click(cdp, text, selector = 'button') {
  const p = await point(cdp, selector, text)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', buttons: 1, clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', buttons: 0, clickCount: 1 })
  await wait(100)
}

async function setInput(cdp, selector, value) { return setInputAt(cdp, selector, 0, value) }

async function setInputAt(cdp, selector, index, value) {
  const p = await waitFor(cdp, `(()=>{const e=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length)[${index}];if(!e)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, `${selector}[${index}]`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 3 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 3 })
  await cdp.command('Input.insertText', { text: value })
  await press(cdp, 'Tab', { code: 'Tab', keyCode: 9 })
}

async function selectNative(cdp, selector, expectedText) {
  await click(cdp, '', selector)
  const selection = await waitFor(cdp, `(()=>{const options=[...document.querySelectorAll('[role="option"]')].filter(e=>e.getClientRects().length),target=options.findIndex(e=>e.textContent.trim()===${JSON.stringify(expectedText)}),current=options.findIndex(e=>e.getAttribute('data-state')==='checked');return target>=0&&current>=0?{target,current}:null})()`, `${selector} option`)
  const key = selection.target > selection.current ? 'ArrowDown' : 'ArrowUp'
  for (let index = 0; index < Math.abs(selection.target - selection.current); index++) await press(cdp, key, { code: key, keyCode: key === 'ArrowDown' ? 40 : 38 })
  await press(cdp, 'Enter', { code: 'Enter', keyCode: 13 })
}

async function press(cdp, key, { code = key, keyCode = 0 } = {}) {
  await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key, code, windowsVirtualKeyCode: keyCode })
  await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key, code, windowsVirtualKeyCode: keyCode })
  await wait(60)
}

async function addBlock(cdp, slotText, label) {
  const before = await cdp.evaluate("[...document.querySelectorAll('[data-block-id]')].map(e=>e.getAttribute('data-block-id'))")
  await click(cdp, slotText, 'div')
  await setInput(cdp, 'input[placeholder="搜索模块（支持拼音）"]', label)
  await click(cdp, label)
  const nodeId = await waitFor(cdp, `(()=>{const before=new Set(${JSON.stringify(before)});return[...document.querySelectorAll('[data-block-id]')].map(e=>e.getAttribute('data-block-id')).find(id=>!before.has(id))||null})()`, `new ${label} block`)
  await click(cdp, '', `[data-block-id="${nodeId}"]`)
  return nodeId
}

async function addCanvasNode(cdp, label, position) {
  const before = await cdp.evaluate("[...document.querySelectorAll('.react-flow__node')].map(e=>e.getAttribute('data-id'))")
  const target = position
    ? await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__pane');if(!e)return null;const r=e.getBoundingClientRect(),x=r.x+r.width*${position.xRatio},y=r.y+r.height*${position.yRatio};return document.elementFromPoint(x,y)===e?{x,y}:null})()`, `empty positioned canvas point for ${label}`)
    : await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__pane');if(!e)return null;const r=e.getBoundingClientRect();for(let row=1;row<8;row++)for(let col=1;col<10;col++){const x=r.x+r.width*col/10,y=r.y+r.height*row/8;if(document.elementFromPoint(x,y)===e)return{x,y}}return null})()`, `empty canvas point for ${label}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...target, button: 'right', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...target, button: 'right', clickCount: 1 })
  await setInput(cdp, 'input[placeholder="搜索模块（支持拼音）"]', label)
  await click(cdp, label, '[role="button"]')
  return waitFor(cdp, `(()=>{const before=new Set(${JSON.stringify(before)});return[...document.querySelectorAll('.react-flow__node')].map(e=>e.getAttribute('data-id')).find(id=>!before.has(id))||null})()`, `new ${label} node`)
}

async function resizeGroup(cdp, groupId, dx, dy) {
  await click(cdp, '', `.react-flow__node[data-id="${groupId}"]`)
  const from = await waitFor(cdp, `(()=>{const root=document.querySelector('.react-flow__node[data-id=${JSON.stringify(groupId)}]');if(!root)return null;const e=[...root.querySelectorAll('.react-flow__resize-control')].find(e=>e.classList.contains('right')&&e.classList.contains('bottom'));if(!e)return null;const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, `resize handle ${groupId}`)
  const to = { x: from.x + dx, y: from.y + dy }
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...from })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...from, button: 'left', buttons: 1, clickCount: 1 })
  for (let step = 1; step <= 12; step++) await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', x: from.x + dx * step / 12, y: from.y + dy * step / 12, button: 'left', buttons: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...to, button: 'left', buttons: 0, clickCount: 1 })
  await wait(120)
}

async function connectNodes(cdp, sourceId, targetId) {
  const points = await waitFor(cdp, `(()=>{const a=document.querySelector('.react-flow__node[data-id=${JSON.stringify(sourceId)}] .react-flow__handle.source:not([data-handleid])'),b=document.querySelector('.react-flow__node[data-id=${JSON.stringify(targetId)}] .react-flow__handle.target');if(!a||!b)return null;const ar=a.getBoundingClientRect(),br=b.getBoundingClientRect();return{a:{x:ar.x+ar.width/2,y:ar.y+ar.height/2},b:{x:br.x+br.width/2,y:br.y+br.height/2}}})()`, `handles ${sourceId} -> ${targetId}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...points.a })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...points.a, button: 'left', buttons: 1, clickCount: 1 })
  for (let step = 1; step <= 12; step++) await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', x: points.a.x + (points.b.x - points.a.x) * step / 12, y: points.a.y + (points.b.y - points.a.y) * step / 12, button: 'left', buttons: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...points.b, button: 'left', buttons: 0, clickCount: 1 })
  await wait(100)
}

function sqliteEvidence(workspace, workflowId, runId) {
  const database = join(workspace, 'data', 'autoflow.sqlite3'), workflow = sqlLiteral(workflowId), run = sqlLiteral(runId)
  return {
    document: sqliteRows(database, `SELECT id,revision,json_array_length(document,'$.nodes') AS nodeCount,json_array_length(document,'$.edges') AS edgeCount FROM workflow_documents WHERE id=${workflow}`),
    run: sqliteRows(database, `SELECT id AS runId,json_extract(payload,'$.status') AS status,json_extract(payload,'$.cleanupState') AS cleanupState,active_slot AS activeSlot FROM workflow_runs WHERE id=${run}`),
  }
}

function sqliteRows(database, query) {
  const output = execFileSync('sqlite3', ['-json', database, query], { encoding: 'utf8' }).trim()
  return output ? JSON.parse(output) : []
}
function sqlLiteral(value) { return `'${String(value).replaceAll("'", "''")}'` }
function cloakProcesses(workspace) { return execFileSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).split('\n').filter(line => line.includes(workspace) && /Chromium|CloakBrowser/.test(line)) }
async function capture(cdp, path) { await cdp.evaluate('document.fonts.ready.then(()=>true)'); const { data } = await cdp.command('Page.captureScreenshot', { format: 'png' }); await writeFile(path, data, 'base64') }
