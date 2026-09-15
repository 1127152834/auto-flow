import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import { mkdtemp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import { tmpdir } from 'node:os'
import { basename, dirname, join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const sourceKernel = process.env.AUTOFLOW_B1_KERNEL_DIR
  ?? '/Users/zhangtiancheng/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2'
const kernelVersion = basename(sourceKernel).replace(/^chromium-/, '')
const evidenceRoot = join(root, 'docs/migration/studio-backend-migration/evidence/b1')
const evidenceDir = await mkdtemp(join(evidenceRoot, 'formal-electron-'))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-b1-'))
const pageUrl = pathToFileURL(join(root, 'apps/backend/tests/fixtures/workflow-page.html')).href
const slowServer = createServer(() => undefined)
await new Promise((resolve, reject) => {
  slowServer.once('error', reject)
  slowServer.listen(0, '127.0.0.1', resolve)
})
const slowUrl = `http://127.0.0.1:${slowServer.address().port}/pending-navigation`
const checks = []
const observedEvents = []
let desktop
let main
let studio
let native
let eventAbort

await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await mkdir(join(userData, 'data', 'kernels'), { recursive: true })
execFileSync('cp', ['-cR', sourceKernel, join(userData, 'data', 'kernels', basename(sourceKernel))])

try {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'] })
  main = desktop.cdp
  native = await connectCdp(desktop.inspectorUrl)
  await native.evaluate("globalThis.qaElectron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');true")
  await main.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(main, "document.body?.innerText.includes('本地服务正常')", 'main service readiness', 30_000)
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  assert.equal(runtime.sidecar.state, 'ready')
  eventAbort = new AbortController()
  void collectEvents(runtime, eventAbort.signal, observedEvents)

  const profile = await api(runtime, '/v1/profiles', {
    method: 'POST',
    body: {
      name: 'B1 正式验收配置', description: '隔离工作区中的 CloakBrowser 配置', startUrl: 'about:blank',
      locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false, headless: false, humanize: false,
      humanPreset: 'default', userAgent: null, viewportJson: { width: 1280, height: 720 }, colorScheme: 'light',
      extensionPathsJson: [], expertArgsJson: [], browserVersion: kernelVersion, browserEdition: 'public',
      releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null,
    },
  })
  checkpoint('主应用真实服务在临时工作区创建 CloakBrowser Profile')

  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库') && document.body.innerText.includes('227')", 'formal Studio', 30_000)
  assert.equal(await studio.evaluate("document.body.innerText.includes('Mock 接口')"), false)
  await waitFor(studio, `document.querySelector('[aria-label="运行浏览器配置"]')?.value === ${JSON.stringify(profile.id)}`, 'managed Profile selection')
  checkpoint('主窗口通过真实点击打开正式 Studio，Studio 只读取主应用 Profile')

  await click(studio, '新建')
  await waitFor(studio, "document.querySelectorAll('.react-flow__node').length === 0", 'new empty workflow')
  checkpoint('通过正式新建入口创建空工作流')

  await setInput(studio, 'input[placeholder="工作流名称"]', 'B1 五节点正式闭环')
  const modules = [
    ['打开网页', 'open_page', { placeholder: 'https://example.com', value: pageUrl }],
    ['输入文本', 'input_text', { placeholder: '例如: #input, .text-field', value: '#workflow-input', extra: ['textarea[placeholder="要输入的文本内容"]', '真实 CloakBrowser 五节点'] }],
    ['点击元素', 'click_element', { placeholder: '例如: #button, .submit', value: '.workflow-action' }],
    ['提取数据', 'get_element_info', { placeholder: '例如: #title, .content', value: '#workflow-output', extra: ['#variableName', 'result'] }],
    ['网页截图', 'screenshot', { placeholder: null, value: null }],
  ]
  const nodeIds = []
  for (let index = 0; index < modules.length; index++) {
    const [label, type, config] = modules[index]
    await addFromQuickPicker(studio, index, label)
    const node = await waitFor(studio, `(()=>{const rows=[...document.querySelectorAll('.react-flow__node')].filter(e=>e.textContent.includes(${JSON.stringify(label)}));const e=rows.at(-1);return e?.dataset.id||null})()`, `node ${type}`)
    nodeIds.push(node)
    await click(studio, '', `.react-flow__node[data-id=${JSON.stringify(node)}]`)
    if (config.placeholder) await setInput(studio, `[placeholder=${JSON.stringify(config.placeholder)}]`, config.value)
    if (config.extra) await setInput(studio, config.extra[0], config.extra[1])
  }
  assert.equal(new Set(nodeIds).size, 5)
  assert.equal(await studio.evaluate("document.querySelectorAll('.react-flow__node').length"), 5)
  checkpoint('通过画布原生右键菜单逐一添加并配置五个节点，没有直接修改 Store')

  await arrangeNodes(studio, nodeIds)
  for (let index = 0; index < nodeIds.length - 1; index++) await connectNodes(studio, nodeIds[index], nodeIds[index + 1])
  await waitFor(studio, "document.querySelectorAll('.react-flow__edge').length === 4", 'four workflow edges')
  checkpoint('通过画布连接手柄建立五节点顺序链')

  await click(studio, '保存')
  await waitFor(studio, "document.body?.innerText.includes('工作流已保存: B1 五节点正式闭环')", 'workflow save acknowledgement')
  const savedList = await api(runtime, '/workflows')
  const saved = savedList.find(item => item.name === 'B1 五节点正式闭环')
  assert.ok(saved)
  assert.equal(saved.revision, 1)
  assert.equal(saved.nodes.length, 5)
  assert.equal(saved.edges.length, 4)
  checkpoint('正式保存经真实 HTTP 写入 SQLite，返回修订 1')

  await setInput(studio, 'input[placeholder="工作流名称"]', 'B1 五节点正式闭环 · 关窗保存')
  await closeWindowThroughOs(desktop.child.pid)
  await waitFor(studio, "document.body?.innerText.includes('保存当前工作流？')", 'normal-close draft prompt')
  await click(studio, '取消')
  assert.equal(await hasStudioTarget(desktop.debugOrigin), true)
  assert.equal(await studio.evaluate("document.querySelector('input[placeholder=\"工作流名称\"]')?.value"), 'B1 五节点正式闭环 · 关窗保存')
  assert.equal((await api(runtime, `/workflows/${encodeURIComponent(saved.id)}`)).revision, 1)
  checkpoint('通过 macOS 系统级 Cmd+W 触发正常关窗离开协调；取消后窗口、草稿和已保存修订均保持不变')

  await closeWindowThroughOs(desktop.child.pid)
  await waitFor(studio, "document.body?.innerText.includes('保存当前工作流？')", 'second normal-close draft prompt')
  await click(studio, '保存后继续')
  studio.close(); studio = undefined
  await waitForNoStudio(desktop.debugOrigin)
  const closedSaved = await waitForValue(async () => {
    const value = await api(runtime, `/workflows/${encodeURIComponent(saved.id)}`)
    return value.revision === 2 && value.name === 'B1 五节点正式闭环 · 关窗保存' ? value : null
  }, 'normal-close saved revision', 10_000)
  checkpoint('再次通过系统级 Cmd+W 并选择保存后继续；保存成功后窗口才关闭，SQLite 修订递增')
  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库')", 'reopened Studio', 30_000)
  await click(studio, '打开')
  await click(studio, '打开工作流 B1 五节点正式闭环 · 关窗保存', '[role="button"]')
  await waitFor(studio, "document.querySelector('input[placeholder=\"工作流名称\"]')?.value === 'B1 五节点正式闭环 · 关窗保存' && document.querySelectorAll('.react-flow__node').length === 5", 'persisted workflow reopen')
  assert.equal(await studio.evaluate("document.querySelectorAll('.react-flow__edge').length"), 4)
  assert.equal(closedSaved.nodes.length, 5)
  assert.equal(closedSaved.edges.length, 4)
  checkpoint('正常关闭并重开正式窗口后，从 SQLite 恢复名称、节点、配置和连线')

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
  const runId = startedRun.runId
  const results = await api(runtime, `/workflow-runs/${encodeURIComponent(runId)}/results?cursor=0&limit=50`)
  assert.equal(results.items.find(item => item.nodeId === nodeIds[3])?.values.value, '真实 CloakBrowser 五节点')
  const artifacts = await api(runtime, `/workflow-runs/${encodeURIComponent(runId)}/artifacts?cursor=0&limit=50`)
  assert.equal(artifacts.items.length, 1)
  assert.equal(artifacts.items[0].mimeType, 'image/png')
  const png = await apiBytes(runtime, `/workflow-runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifacts.items[0].artifactId)}`)
  assert.deepEqual([...png.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10])
  checkpoint('正式 UI 启动真实 CloakBrowser：输入、首个匹配点击、提取值、PNG 与终态均已持久化')

  await wait(800)
  const leaked = execFileSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).split('\n').filter(line => line.includes(userData) && /Chromium|CloakBrowser/.test(line))
  assert.deepEqual(leaked, [])
  checkpoint('运行终态后 CloakBrowser 进程树和临时会话均已清理')

  await click(studio, '', `.react-flow__node[data-id=${JSON.stringify(nodeIds[0])}]`)
  await setInput(studio, '[placeholder="https://example.com"]', slowUrl)
  await click(studio, '运行 (F5)', '[aria-label="运行 (F5)"]')
  await click(studio, '运行 (F5)', '[role="menuitem"]')
  const stoppedRun = await waitForValue(async () => {
    const page = await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(saved.id)}&cursor=0&limit=20`)
    const candidate = page.items.find(item => item.runId !== runId)
    if (!candidate) return null
    const detail = await api(runtime, `/workflow-runs/${encodeURIComponent(candidate.runId)}`)
    return detail.status === 'running' ? detail : null
  }, 'second active run', 20_000)
  await closeWindowThroughOs(desktop.child.pid)
  await waitFor(studio, "document.body?.innerText.includes('结束活跃会话后离开？')", 'active-run normal-close prompt')
  await click(studio, '取消')
  assert.equal(await hasStudioTarget(desktop.debugOrigin), true)
  assert.equal((await api(runtime, `/workflow-runs/${encodeURIComponent(stoppedRun.runId)}`)).status, 'running')
  assert.equal((await api(runtime, `/workflows/${encodeURIComponent(saved.id)}`)).revision, 2)
  checkpoint('活跃运行与未保存草稿并存时取消正常关窗，浏览器运行、窗口、草稿和已保存文档均保持原状态')

  await closeWindowThroughOs(desktop.child.pid)
  await waitFor(studio, "document.body?.innerText.includes('结束活跃会话后离开？')", 'second active-run normal-close prompt')
  await click(studio, '放弃修改并结束会话')
  studio.close(); studio = undefined
  await waitForNoStudio(desktop.debugOrigin, 30_000)
  const stopped = await waitForValue(async () => {
    const value = await api(runtime, `/workflow-runs/${encodeURIComponent(stoppedRun.runId)}`)
    return value.status === 'stopped' ? value : null
  }, 'normal-close stopped run cleanup', 30_000)
  assert.equal(stopped.status, 'stopped')
  assert.equal((await api(runtime, `/workflows/${encodeURIComponent(saved.id)}`)).revision, 2)
  await waitForValue(async () => {
    const processes = execFileSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).split('\n').filter(line => line.includes(userData) && /Chromium|CloakBrowser/.test(line))
    return processes.length === 0 ? true : null
  }, 'normal-close browser cleanup', 10_000)
  checkpoint('放弃草稿并结束活跃运行后，先确认 stopped 与清理完成，再关闭 Studio；保存修订未被草稿覆盖')

  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库')", 'final reopened Studio', 30_000)

  const packageBoundary = desktop.packaged ? await verifyPackageBoundary() : null
  if (packageBoundary) checkpoint('目录包未携带冻结源码路径、Mock 服务或 Vite 开发地址')

  await capture(studio, join(evidenceDir, 'completed.png'))
  const report = {
    evidenceId: 'BE-B1-formal-electron', checkedAt: new Date().toISOString(),
    gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    buildSha256: await buildHash(), workflowId: saved.id, profileId: profile.id, runId, stoppedRunId: stoppedRun.runId,
    result: 'passed', checks, platform: `${process.platform}-${process.arch}`,
    entry: desktop.packaged ? 'packaged-directory' : 'development-build', packageBoundary,
    boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browser: 'CloakBrowser only', interaction: 'CDP mouse and keyboard plus macOS system-level Command-W close shortcut; no Store access' },
  }
  await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
} catch (error) {
  if (studio) await capture(studio, join(evidenceDir, 'failure.png')).catch(() => undefined)
  await writeFile(join(evidenceDir, 'failure.json'), JSON.stringify({ checkedAt: new Date().toISOString(), checks, observedEvents, error: error instanceof Error ? error.stack : String(error) }, null, 2) + '\n')
  throw error
} finally {
  eventAbort?.abort(); studio?.close(); main?.close(); native?.close(); await stop(desktop?.child)
  slowServer.closeAllConnections()
  await new Promise(resolve => slowServer.close(resolve))
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

async function apiBytes(runtime, path) {
  const response = await fetch(`${runtime.sidecar.baseUrl}/api${path}`, { headers: { 'x-autoflow-token': runtime.sidecar.token } })
  assert.ok(response.ok, `GET /api${path}: ${response.status}`)
  return Buffer.from(await response.arrayBuffer())
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

async function connectStudio(origin) {
  const target = await waitForTarget(origin, item => item.type === 'page' && item.url.includes('studio.html'), 'Studio target')
  return connectCdp(target.webSocketDebuggerUrl)
}

async function openStudioFromMain(cdp, origin) {
  for (let attempt = 0; attempt < 3; attempt++) {
    await click(cdp, '工作流工作台')
    try { return await connectStudio(origin) } catch { /* dashboard can rerender after its resource refresh */ }
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

async function waitForNoStudio(origin, timeoutMs = 15_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const targets = await (await fetch(`${origin}/json/list`)).json()
    if (!targets.some(target => target.type === 'page' && target.url.includes('studio.html'))) return
    await wait(100)
  }
  throw new Error('timed out waiting for Studio window close')
}

async function hasStudioTarget(origin) {
  const targets = await (await fetch(`${origin}/json/list`)).json()
  return targets.some(target => target.type === 'page' && target.url.includes('studio.html'))
}

async function closeWindowThroughOs(pid) {
  assert.equal(process.platform, 'darwin', '原生窗口关闭验收目前只在 macOS 实机执行；其他平台必须单独记录')
  assert.equal(await native.evaluate("(()=>{const w=qaElectron.BrowserWindow.getAllWindows().find(w=>w.getTitle().includes('工作流工作台'));if(!w)return false;qaElectron.app.focus({steal:true});w.show();w.focus();return true})()"), true)
  await wait(250)
  execFileSync('osascript', [
    '-e', 'tell application "System Events"',
    '-e', `set targetProcess to first application process whose unix id is ${pid}`,
    '-e', 'set frontmost of targetProcess to true',
    '-e', 'keystroke "w" using command down',
    '-e', 'end tell',
  ])
  await wait(150)
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
    await cdp.command('Input.dispatchMouseEvent', {
      type: 'mouseMoved', x: points.a.x + (points.b.x - points.a.x) * step / 12,
      y: points.a.y + (points.b.y - points.a.y) * step / 12, button: 'left', buttons: 1,
    })
    await wait(12)
  }
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...points.b, button: 'left', buttons: 0, clickCount: 1 })
  await wait(120)
}

async function arrangeNodes(cdp, nodeIds) {
  const pane = await cdp.evaluate(`(()=>{const r=document.querySelector('.react-flow__pane').getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height}})()`)
  const targets = nodeIds.map((_, index) => ({ x: pane.x + pane.width * .46, y: pane.y + 65 + index * ((pane.height - 130) / 4) }))
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

async function verifyPackageBoundary() {
  const executableIndex = process.argv.indexOf('--executable')
  assert.notEqual(executableIndex, -1)
  const executable = resolve(process.argv[executableIndex + 1])
  const resources = resolve(dirname(executable), '../Resources')
  const extractDir = await mkdtemp(join(tmpdir(), 'autoflow-b1-asar-'))
  const needles = ['reference/WebRPA', '127.0.0.1:5175', 'StudioMockTools', 'api/mock-server']
  try {
    execFileSync(join(root, 'node_modules/.bin/asar'), ['extract', join(resources, 'app.asar'), extractDir])
    const hits = []
    for (const base of [extractDir, join(resources, 'backend')]) {
      for (const file of await readdir(base, { recursive: true })) {
        const path = join(base, file)
        let data
        try { data = await readFile(path) } catch { continue }
        for (const needle of needles) if (data.includes(Buffer.from(needle))) hits.push({ file: path.slice(base.length + 1), needle })
      }
    }
    assert.deepEqual(hits, [])
    return { resources, forbiddenReferences: hits, scannedNeedles: needles }
  } finally {
    await rm(extractDir, { recursive: true, force: true })
  }
}
