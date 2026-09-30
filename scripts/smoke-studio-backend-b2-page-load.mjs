import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import { mkdir, mkdtemp, readFile, readdir, rm, stat, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename, join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const sourceKernel = process.env.AUTOFLOW_B1_KERNEL_DIR
  ?? '/Users/zhangtiancheng/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2'
const kernelVersion = basename(sourceKernel).replace(/^chromium-/, '')
const evidenceRoot = join(root, 'docs/migration/studio-backend-migration/evidence/b2')
await mkdir(evidenceRoot, { recursive: true })
const evidenceDir = await mkdtemp(join(evidenceRoot, 'formal-electron-'))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-b2-'))
const pageUrl = pathToFileURL(join(root, 'apps/backend/tests/fixtures/workflow-page.html')).href
const checks = []
const observedEvents = []
let desktop
let main
let studio
let eventAbort

await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await mkdir(join(userData, 'data', 'kernels'), { recursive: true })
execFileSync('cp', ['-cR', sourceKernel, join(userData, 'data', 'kernels', basename(sourceKernel))])

try {
  const packageAssessment = await assessDirectoryPackage()
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`] })
  assert.equal(desktop.packaged, false, 'B2 formal development evidence must use the freshly built development entry')
  main = desktop.cdp
  await main.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(main, "document.body?.innerText.includes('本地服务正常')", 'main service readiness', 30_000)
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  assert.equal(runtime.sidecar.state, 'ready')
  eventAbort = new AbortController()
  void collectEvents(runtime, eventAbort.signal, observedEvents)

  const profile = await api(runtime, '/v1/profiles', {
    method: 'POST',
    body: {
      name: 'B2 页面加载正式验收配置', description: '隔离工作区中的 CloakBrowser 配置', startUrl: 'about:blank',
      locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false, headless: false, humanize: false,
      humanPreset: 'default', userAgent: null, viewportJson: { width: 1280, height: 720 }, colorScheme: 'light',
      extensionPathsJson: [], expertArgsJson: [], browserVersion: kernelVersion, browserEdition: 'public',
      releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null,
    },
  })
  checkpoint('真实 sidecar 在临时工作区创建 CloakBrowser Profile')

  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库')", 'formal Studio', 30_000)
  assert.equal(await studio.evaluate("document.body.innerText.includes('Mock 接口')"), false)
  await waitFor(studio, `document.querySelector('[aria-label="运行浏览器配置"]')?.value === ${JSON.stringify(profile.id)}`, 'managed Profile selection')
  checkpoint('主窗口通过真实点击打开正式 Studio，并选择真实 sidecar Profile')

  await click(studio, '新建')
  await waitFor(studio, "document.querySelectorAll('.react-flow__node').length === 0", 'new empty workflow')
  await setInput(studio, 'input[placeholder="工作流名称"]', 'B2 页面加载正式闭环')

  const variableConsumerUrl = `${pageUrl}?page_ready={page_ready}`
  const modules = [
    { label: '打开网页', type: 'open_page', url: pageUrl },
    { label: '等待页面加载完成', type: 'wait_page_load' },
    { label: '网页是否加载完成', type: 'page_load_complete' },
    { label: '打开网页', type: 'open_page', url: variableConsumerUrl },
  ]
  const nodeIds = []
  for (let index = 0; index < modules.length; index++) {
    const { label, type, url } = modules[index]
    await addFromQuickPicker(studio, index, label)
    const node = await waitFor(studio, `(()=>{const rows=[...document.querySelectorAll('.react-flow__node')].filter(e=>e.textContent.includes(${JSON.stringify(label)}));return rows.at(-1)?.dataset.id||null})()`, `node ${type}`)
    nodeIds.push(node)
    await click(studio, label, `.react-flow__node[data-id=${JSON.stringify(node)}] .font-semibold`)
    if (type === 'open_page') {
      await setInput(studio, '[placeholder="https://example.com"]', url)
    } else if (type === 'wait_page_load') {
      await selectOption(studio, '#waitUntil', 'DOM加载完成')
      await setInput(studio, '#timeout', '5')
    } else if (type === 'page_load_complete') {
      await selectOption(studio, '#checkState', 'DOM加载完成')
      await setInput(studio, '#saveToVariable', 'page_ready')
    }
  }
  assert.equal(new Set(nodeIds).size, 4)
  assert.equal(await studio.evaluate("document.querySelectorAll('.react-flow__node').length"), 4)
  checkpoint('通过画布原生右键菜单和配置面板添加、配置页面加载链；未直接修改 Store')

  await arrangeNodes(studio, nodeIds)
  for (let index = 0; index < nodeIds.length - 1; index++) await connectNodes(studio, nodeIds[index], nodeIds[index + 1])
  await waitFor(studio, "document.querySelectorAll('.react-flow__edge').length === 3", 'three workflow edges')
  checkpoint('通过画布连接手柄建立 open_page → wait_page_load → page_load_complete → open_page 变量消费链')

  await click(studio, '保存')
  await waitFor(studio, "document.body?.innerText.includes('工作流已保存: B2 页面加载正式闭环')", 'workflow save acknowledgement')
  const savedList = await api(runtime, '/workflows')
  const saved = savedList.find(item => item.name === 'B2 页面加载正式闭环')
  assert.ok(saved)
  assert.equal(saved.revision, 1)
  assert.equal(saved.nodes.length, 4)
  assert.equal(saved.edges.length, 3)
  const savedWait = saved.nodes.find(node => node.id === nodeIds[1])?.data
  const savedComplete = saved.nodes.find(node => node.id === nodeIds[2])?.data
  assert.equal(savedWait?.moduleType, 'wait_page_load')
  assert.equal(savedWait?.waitUntil, 'domcontentloaded')
  assert.equal(savedWait?.timeout, 5)
  assert.equal(savedComplete?.moduleType, 'page_load_complete')
  assert.equal(savedComplete?.checkState, 'domcontentloaded')
  assert.equal(savedComplete?.saveToVariable, 'page_ready')
  assert.equal(saved.nodes.find(node => node.id === nodeIds[3])?.data.url, variableConsumerUrl)
  checkpoint('正式保存经真实 HTTP 写入 SQLite，页面加载节点配置与 UI 输入一致')

  await click(studio, '运行 (F5)', '[aria-label="运行 (F5)"]')
  await click(studio, '运行 (F5)', '[role="menuitem"]')
  const startedRun = await waitForValue(async () => {
    const page = await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(saved.id)}&cursor=0&limit=20`)
    return page.items[0] ?? null
  }, 'persisted workflow run', 20_000)
  const terminalRun = await waitForValue(async () => {
    const value = await api(runtime, `/workflow-runs/${encodeURIComponent(startedRun.runId)}`)
    return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.status) ? value : null
  }, 'workflow terminal persistence', 120_000)
  assert.equal(terminalRun.status, 'completed')
  await waitForValue(async () => observedEvents.find(event => event.name === 'execution:completed' && event.data?.runId === startedRun.runId) ?? null, 'raw SSE terminal event', 10_000)
  await waitFor(studio, "document.body?.innerText.includes('执行完成')", 'rendered SSE terminal event', 10_000)

  const results = await api(runtime, `/workflow-runs/${encodeURIComponent(startedRun.runId)}/results?cursor=0&limit=50`)
  const statusResult = results.items.find(item => item.nodeId === nodeIds[2])
  assert.deepEqual(statusResult?.values, { loaded: true })
  const logs = await api(runtime, `/workflow-runs/${encodeURIComponent(startedRun.runId)}/logs?cursor=0&limit=200`)
  assert.ok(logs.items.some(item => item.nodeId === nodeIds[1] && item.message === '页面已加载完成（domcontentloaded）'))
  assert.ok(logs.items.some(item => item.nodeId === nodeIds[2] && item.message === '页面加载状态: 已完成（domcontentloaded）'))
  assert.ok(logs.items.some(item => item.nodeId === nodeIds[3] && item.message === `已打开网页: ${pageUrl}?page_ready=True`))
  checkpoint('真实 CloakBrowser 完成页面等待与状态检查；page_ready 被后续节点解析，结果和两条正式日志均已持久化')

  await waitForValue(async () => cloakProcesses(userData).length === 0 ? true : null, 'CloakBrowser process cleanup', 15_000)
  checkpoint('运行终态后 CloakBrowser 进程树和临时会话均已清理')

  await capture(studio, join(evidenceDir, 'completed.png'))
  const report = {
    evidenceId: 'BE-B2-page-load-formal-electron', checkedAt: new Date().toISOString(),
    gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    buildSha256: await buildHash(), workflowId: saved.id, profileId: profile.id, runId: startedRun.runId,
    result: 'passed', checks, platform: `${process.platform}-${process.arch}`, entry: 'development-build',
    pageLoad: {
      waitNodeId: nodeIds[1], completeNodeId: nodeIds[2], outputVariable: 'page_ready',
      completeResult: statusResult.values, consumedByOpenPageLog: `已打开网页: ${pageUrl}?page_ready=True`,
      logs: logs.items.filter(item => [nodeIds[1], nodeIds[2], nodeIds[3]].includes(item.nodeId)).map(item => item.message),
    },
    directoryPackage: packageAssessment,
    boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browser: 'CloakBrowser only', interaction: 'CDP mouse and keyboard through the formal Studio UI; no Store access' },
  }
  await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
} catch (error) {
  if (studio) await capture(studio, join(evidenceDir, 'failure.png')).catch(() => undefined)
  await writeFile(join(evidenceDir, 'failure.json'), JSON.stringify({ checkedAt: new Date().toISOString(), checks, observedEvents, error: error instanceof Error ? error.stack : String(error) }, null, 2) + '\n')
  throw error
} finally {
  eventAbort?.abort(); studio?.close(); main?.close(); await stop(desktop?.child)
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
    if (!response.ok || !response.body) throw new Error(`event stream ${response.status}`)
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
  } catch (error) {
    if (!signal.aborted) output.push({ name: 'collector:error', data: String(error) })
  }
}

async function openStudioFromMain(cdp, origin) {
  for (let attempt = 0; attempt < 3; attempt++) {
    await click(cdp, '工作流工作台')
    try {
      const target = await waitForTarget(origin, item => item.type === 'page' && item.url.includes('studio.html'), 'Studio target')
      return connectCdp(target.webSocketDebuggerUrl)
    } catch { /* dashboard can rerender after its resource refresh */ }
  }
  throw new Error('正式 Studio 窗口未能从主界面打开')
}

async function waitForTarget(origin, predicate, description, timeoutMs = 15_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const targets = await (await fetch(`${origin}/json/list`)).json()
    const target = targets.find(predicate)
    if (target) return target
    await wait(100)
  }
  throw new Error(`timed out waiting for ${description}`)
}

async function waitForValue(read, description, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  let last
  while (Date.now() < deadline) {
    last = await read()
    if (last) return last
    await wait(250)
  }
  throw new Error(`timed out waiting for ${description}: ${JSON.stringify(last)}`)
}

async function point(cdp, selector, text = '') {
  return waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length),text=${JSON.stringify(text)};const e=!text?rows[0]:rows.find(e=>e.getAttribute('aria-label')===text)||rows.find(e=>e.textContent.trim()===text)||rows.find(e=>e.textContent.includes(text));if(!e||e.disabled)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `unobscured ${text || selector}`)
}

async function click(cdp, text, selector = 'button') {
  const p = await point(cdp, selector, text)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 })
  await wait(100)
}

async function setInput(cdp, selector, value) {
  const p = await point(cdp, selector)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 3 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 3 })
  await cdp.command('Input.insertText', { text: value })
  await press(cdp, 'Tab', { code: 'Tab', keyCode: 9 })
  await wait(100)
}

async function press(cdp, key, { modifiers = 0, code = key, keyCode = key === 'Enter' ? 13 : 0 } = {}) {
  await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key, code, modifiers, windowsVirtualKeyCode: keyCode })
  await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key, code, modifiers, windowsVirtualKeyCode: keyCode })
  await wait(80)
}

async function selectOption(cdp, selector, label) {
  await click(cdp, '', selector)
  await click(cdp, label, '[role="option"]')
  await waitFor(cdp, `document.querySelector(${JSON.stringify(selector)})?.textContent.includes(${JSON.stringify(label)})`, `${selector} option ${label}`)
}

async function addFromQuickPicker(cdp, index, label) {
  const target = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__pane');if(!e)return null;const r=e.getBoundingClientRect(),ys=[.2+${JSON.stringify(index)}*.13,.25,.4,.55,.7],xs=[.42,.58,.7,.3];for(const yf of ys)for(const xf of xs){const x=r.x+r.width*xf,y=r.y+r.height*Math.min(yf,.78);if(document.elementFromPoint(x,y)===e)return{x,y}}return null})()`, 'unobscured workflow canvas')
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...target, button: 'right', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...target, button: 'right', clickCount: 1 })
  await setInput(cdp, 'input[placeholder="搜索模块（支持拼音）"]', label)
  await click(cdp, label, '[role="button"]')
}

async function connectNodes(cdp, sourceId, targetId) {
  const points = await waitFor(cdp, `(()=>{const a=document.querySelector('.react-flow__node[data-id=${JSON.stringify(sourceId)}] .react-flow__handle.source:not([data-handleid])'),b=document.querySelector('.react-flow__node[data-id=${JSON.stringify(targetId)}] .react-flow__handle.target');if(!a||!b)return null;const ar=a.getBoundingClientRect(),br=b.getBoundingClientRect();return{a:{x:ar.x+ar.width/2,y:ar.y+ar.height/2},b:{x:br.x+br.width/2,y:br.y+br.height/2}}})()`, `handles ${sourceId} -> ${targetId}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...points.a })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...points.a, button: 'left', buttons: 1, clickCount: 1 })
  for (let step = 1; step <= 12; step++) {
    await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', x: points.a.x + (points.b.x - points.a.x) * step / 12, y: points.a.y + (points.b.y - points.a.y) * step / 12, button: 'left', buttons: 1 })
    await wait(12)
  }
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...points.b, button: 'left', buttons: 0, clickCount: 1 })
  await wait(120)
}

async function arrangeNodes(cdp, nodeIds) {
  const pane = await cdp.evaluate(`(()=>{const r=document.querySelector('.react-flow__pane').getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height}})()`)
  const targets = nodeIds.map((_, index) => ({ x: pane.x + pane.width * .46, y: pane.y + 65 + index * ((pane.height - 130) / Math.max(1, nodeIds.length - 1)) }))
  for (let index = nodeIds.length - 1; index >= 0; index--) {
    const from = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__node[data-id=${JSON.stringify(nodeIds[index])}]');if(!e)return null;const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, `node position ${nodeIds[index]}`)
    const to = targets[index]
    await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...from })
    await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...from, button: 'left', buttons: 1, clickCount: 1 })
    for (let step = 1; step <= 10; step++) await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', x: from.x + (to.x - from.x) * step / 10, y: from.y + (to.y - from.y) * step / 10, button: 'left', buttons: 1 })
    await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...to, button: 'left', buttons: 0, clickCount: 1 })
    await wait(100)
  }
}

function cloakProcesses(workspace) {
  return execFileSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).split('\n').filter(line => line.includes(workspace) && /Chromium|CloakBrowser/.test(line))
}

async function capture(cdp, path) {
  await cdp.evaluate('document.fonts.ready.then(()=>true)')
  const { data } = await cdp.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  await writeFile(path, data, 'base64')
}

async function buildHash() {
  const hash = createHash('sha256')
  for (const file of (await readdir(join(root, 'apps/desktop/out'), { recursive: true })).filter(file => /\.(js|css|html)$/.test(file)).sort()) {
    hash.update(file).update(await readFile(join(root, 'apps/desktop/out', file)))
  }
  return hash.digest('hex')
}

async function assessDirectoryPackage() {
  const backend = join(root, 'apps/desktop/dist/mac-arm64/AutoFlow.app/Contents/Resources/backend/autoflow-backend')
  const sources = [
    'apps/backend/src/autoflow/application/workflows/executors/page_load.py',
    'apps/backend/src/autoflow/application/workflows/executors/production.py',
    'apps/backend/src/autoflow/bootstrap/workflows.py',
    'apps/backend/src/autoflow/providers/browser/workflow_worker.py',
  ].map(path => join(root, path))
  let packaged
  try { packaged = await stat(backend) } catch { return { status: 'absent', backend } }
  const sourceStats = await Promise.all(sources.map(async path => ({ path, info: await stat(path) })))
  const newest = sourceStats.reduce((left, right) => left.info.mtimeMs >= right.info.mtimeMs ? left : right)
  return {
    status: packaged.mtimeMs >= newest.info.mtimeMs ? 'eligible-for-separate-packaged-run' : 'needs-rebuild',
    backend, backendModifiedAt: packaged.mtime.toISOString(), newestB2Source: newest.path,
    newestB2SourceModifiedAt: newest.info.mtime.toISOString(),
    reason: packaged.mtimeMs >= newest.info.mtimeMs ? '目录包不早于 B2 源码；仍需单独执行 packaged E2E' : '目录包后端早于 B2 执行器/注册/接线路径，不能作为 B2 通过证据',
  }
}
