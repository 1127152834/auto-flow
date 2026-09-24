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
const evidenceDir = await mkdtemp(join(evidenceRoot, 'formal-web-basic-electron-'))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-b2-web-basic-'))
const pageUrl = pathToFileURL(join(root, 'apps/backend/tests/fixtures/workflow-page.html')).href
const actionsPageUrl = pathToFileURL(join(root, 'apps/backend/tests/fixtures/workflow-b2-web-actions.html')).href
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
  const packageAssessment = await assessDirectoryPackage()
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'] })
  assert.equal(desktop.packaged, false, 'B2 web basic formal development evidence must use the freshly built development entry')
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
      name: 'B2 基础网页动作正式验收配置', description: '隔离工作区中的 CloakBrowser 配置', startUrl: 'about:blank',
      locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false, headless: false, humanize: false,
      humanPreset: 'default', userAgent: null, viewportJson: { width: 1280, height: 720 }, colorScheme: 'light',
      extensionPathsJson: [], expertArgsJson: [], browserVersion: kernelVersion, browserEdition: 'public',
      releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null,
    },
  })
  checkpoint('真实 sidecar 在临时工作区创建 CloakBrowser Profile')

  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 3840, height: 2400, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库')", 'formal Studio', 30_000)
  assert.equal(await studio.evaluate("document.body.innerText.includes('Mock 接口')"), false)
  await waitFor(studio, `document.querySelector('[aria-label="运行浏览器配置"]')?.value === ${JSON.stringify(profile.id)}`, 'managed Profile selection')
  checkpoint('主窗口通过真实点击打开正式 Studio，并选择真实 sidecar Profile')

  await click(studio, '新建')
  await waitFor(studio, "document.querySelectorAll('.react-flow__node').length === 0", 'new empty workflow')

  const workflowName = 'B2 基础网页动作正式闭环'
  const modules = [
    { label: '打开网页', type: 'open_page', inputs: [['[placeholder="https://example.com"]', pageUrl]], selects: [['#openMode', '当前标签页']] },
    { label: '操作已打开的网页', type: 'use_opened_page', inputs: [['[placeholder="页面标题或URL的部分内容"]', 'AutoFlow B1 受控页面']] },
    { label: '等待元素', type: 'wait_element', inputs: [['[placeholder="例如: #element, .class"]', '#workflow-input'], ['#waitTimeout', '5']] },
    { label: '悬停元素', type: 'hover_element', inputs: [['[placeholder="例如: #element, .hover-target"]', '#workflow-submit'], ['#hoverDuration', '0']] },
    { label: 'JS脚本注入', type: 'inject_javascript', inputs: [['[placeholder="变量名(可选)"]', 'injected_title']], code: "setTimeout(() => alert('AutoFlow dialog'), 100); return document.title" },
    { label: '处理弹窗', type: 'handle_dialog', inputs: [['[placeholder="变量名(可选)"]', 'dialog_message']] },
    { label: '刷新页面', type: 'refresh_page' },
    { label: '打开网页', type: 'open_page', inputs: [['[placeholder="https://example.com"]', actionsPageUrl]], selects: [['#openMode', '当前标签页']] },
    { label: '后退', type: 'go_back' },
    { label: '前进', type: 'go_forward' },
    { label: '后退', type: 'go_back' },
    { label: '切换iframe', type: 'switch_iframe', inputs: [[`[placeholder="iframe[src*='example.com']"]`, '#workflow-frame']], selects: [['#locateBy', '选择器']] },
    { label: '等待元素', type: 'wait_element', inputs: [['[placeholder="例如: #element, .class"]', '#frame-value'], ['#waitTimeout', '5']] },
    { label: '切换回主页面', type: 'switch_to_main' },
    { label: '关闭网页', type: 'close_page' },
  ]
  const familyTypes = ['use_opened_page', 'close_page', 'refresh_page', 'go_back', 'go_forward', 'switch_iframe', 'switch_to_main', 'hover_element', 'handle_dialog', 'inject_javascript', 'wait_element']
  await setInput(studio, 'input[placeholder="工作流名称"]', workflowName)

  const nodeIds = []
  for (let index = 0; index < modules.length; index++) {
    const module = modules[index]
    await addFromQuickPicker(studio, index, module.label)
    const node = await waitFor(studio, `(()=>{const rows=[...document.querySelectorAll('.react-flow__node')].filter(e=>e.textContent.includes(${JSON.stringify(module.label)}));return rows.at(-1)?.dataset.id||null})()`, `node ${module.type}`)
    nodeIds.push(node)
    await selectNode(studio, node, module.type)
    for (const [selector, value] of module.selects ?? []) await selectOption(studio, selector, value)
    for (const [selector, value] of module.inputs ?? []) await setInput(studio, selector, value)
    await moveNode(studio, node, index, modules.length)
  }
  assert.equal(new Set(nodeIds).size, modules.length)
  assert.equal(await studio.evaluate("document.querySelectorAll('.react-flow__node').length"), modules.length)
  checkpoint(`通过正式 Studio UI 添加并配置 ${familyTypes.length} 类基础网页节点及 4 个导航/iframe 支撑实例`)

  await click(studio, '', '.react-flow__controls-fitview')
  await wait(500)
  for (let index = 0; index < nodeIds.length - 1; index++) {
    await connectNodes(studio, nodeIds[index], nodeIds[index + 1])
    await waitFor(studio, `document.querySelectorAll('.react-flow__edge').length === ${index + 1}`, `workflow edge ${index + 1}`)
  }
  checkpoint('通过画布节点与连接手柄建立真实页面、导航历史、弹窗和 iframe 顺序链')

  await selectNode(studio, nodeIds[4], 'inject_javascript')
  await setInjectCode(studio, modules[4].code)
  checkpoint('连线完成后通过 Monaco 代码编辑器写入弹窗脚本，避免编辑器关闭重置画布视口')

  await click(studio, '保存')
  await waitFor(studio, `document.body?.innerText.includes(${JSON.stringify(`工作流已保存: ${workflowName}`)})`, 'workflow save acknowledgement')
  const savedList = await api(runtime, '/workflows')
  const saved = savedList.find(item => item.name === workflowName)
  assert.ok(saved)
  assert.equal(saved.revision, 1)
  assert.equal(saved.nodes.length, modules.length)
  assert.equal(saved.edges.length, modules.length - 1)
  assert.deepEqual([...new Set(saved.nodes.map(node => node.data.moduleType).filter(type => familyTypes.includes(type)))].sort(), [...familyTypes].sort())
  assert.equal(saved.nodes.find(node => node.id === nodeIds[1])?.data.pageIdentifier, 'AutoFlow B1 受控页面')
  assert.equal(saved.nodes.find(node => node.id === nodeIds[4])?.data.javascriptCode, modules[4].code)
  assert.equal(saved.nodes.find(node => node.id === nodeIds[5])?.data.saveMessage, 'dialog_message')
  assert.equal(saved.nodes.find(node => node.id === nodeIds[11])?.data.iframeSelector, '#workflow-frame')
  checkpoint('真实 HTTP/SQLite 保存完整基础网页配置，包含代码编辑器、弹窗变量和 iframe 选择器')

  await wait(500)
  await closeWindowNormally()
  const closeState = await waitForValue(async () => {
    const targets = await (await fetch(`${desktop.debugOrigin}/json/list`)).json()
    if (!targets.some(target => target.type === 'page' && target.url.includes('studio.html'))) return 'closed'
    return await studio.evaluate("document.body?.innerText.includes('保存当前工作流？')") ? 'prompt' : null
  }, 'native Studio close response', 10_000)
  if (closeState === 'prompt') await click(studio, '保存后继续')
  await waitForNoStudio(desktop.debugOrigin)
  studio.close(); studio = undefined
  const postCloseSaved = await api(runtime, `/workflows/${encodeURIComponent(saved.id)}`)
  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 3840, height: 2400, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库')", 'reopened Studio', 30_000)
  if (!await studio.evaluate(`document.querySelectorAll('.react-flow__node').length === ${modules.length} && document.querySelector('input[placeholder="工作流名称"]')?.value === ${JSON.stringify(workflowName)}`)) {
    await click(studio, '打开')
    await click(studio, `打开工作流 ${workflowName}`, '[role="button"]')
  }
  await waitFor(studio, `document.querySelectorAll('.react-flow__node').length === ${modules.length} && document.querySelectorAll('.react-flow__edge').length === ${modules.length - 1}`, 'persisted web basic workflow reopen')
  checkpoint(`通过 BrowserWindow.close 正常关闭并重开 Studio，修订 ${postCloseSaved.revision} 的节点、配置和连线从 SQLite 恢复；系统级 Cmd+W 由 B1 独立证据覆盖`)

  await click(studio, '运行 (F5)', '[aria-label="运行 (F5)"]')
  await click(studio, '运行 (F5)', '[role="menuitem"]')
  const startedRun = await waitForValue(async () => {
    const page = await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(saved.id)}&cursor=0&limit=20`)
    return page.items[0] ?? null
  }, 'persisted workflow run', 20_000)
  const sawCloakBrowser = await waitForValue(async () => cloakProcesses(userData).length > 0 ? cloakProcesses(userData) : null, 'CloakBrowser process launch', 30_000)
  const terminalRun = await waitForValue(async () => {
    const value = await api(runtime, `/workflow-runs/${encodeURIComponent(startedRun.runId)}`)
    return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.status) ? value : null
  }, 'workflow terminal persistence', 120_000)
  assert.equal(terminalRun.status, 'completed')
  await waitForValue(async () => observedEvents.find(event => event.name === 'execution:completed' && event.data?.runId === startedRun.runId) ?? null, 'raw SSE terminal event', 10_000)
  await waitFor(studio, "document.body?.innerText.includes('执行完成')", 'rendered SSE terminal event', 10_000)

  const results = await api(runtime, `/workflow-runs/${encodeURIComponent(startedRun.runId)}/results?cursor=0&limit=100`)
  const resultNodeIds = [nodeIds[1], nodeIds[2], nodeIds[4], nodeIds[5], nodeIds[12]]
  assert.deepEqual(results.items.map(item => item.nodeId), resultNodeIds)
  for (const nodeId of nodeIds) assert.ok(observedEvents.some(event => event.name === 'execution:node_complete' && event.data?.nodeId === nodeId && event.data?.success === true), `missing successful completion for ${nodeId}`)
  const injectResult = results.items.find(item => item.nodeId === nodeIds[4])
  const dialogResult = results.items.find(item => item.nodeId === nodeIds[5])
  assert.equal(injectResult.values?.results?.[0]?.result, 'AutoFlow B1 受控页面')
  assert.equal(dialogResult.values?.handled, true)
  assert.equal(dialogResult.values?.message, 'AutoFlow dialog')
  const logs = await api(runtime, `/workflow-runs/${encodeURIComponent(startedRun.runId)}/logs?cursor=0&limit=200`)
  for (const nodeId of nodeIds) assert.ok(logs.items.some(item => item.nodeId === nodeId), `missing persisted log for ${nodeId}`)
  checkpoint(`真实 CloakBrowser 执行全部 ${familyTypes.length} 类基础网页节点；弹窗、导航历史和 iframe 结果均已持久化`)

  await waitForValue(async () => cloakProcesses(userData).length === 0 ? true : null, 'CloakBrowser process cleanup', 15_000)
  checkpoint('关闭网页后运行仍完成统一清理，CloakBrowser 进程树与资源占用释放')

  await capture(studio, join(evidenceDir, 'completed.png'))
  const report = {
    evidenceId: 'BE-B2-web-basic-formal-electron', checkedAt: new Date().toISOString(),
    gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    buildSha256: await buildHash(), workflowId: saved.id, profileId: profile.id, runId: startedRun.runId,
    result: 'passed', checks, platform: `${process.platform}-${process.arch}`, entry: 'development-build',
    webBasic: { familyTypes, moduleTypes: modules.map(module => module.type), nodeIds, resultCount: results.items.length, logCount: logs.items.length, injectResult: injectResult.values, dialogResult: dialogResult.values, cloakBrowserProcessesObserved: sawCloakBrowser },
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

async function waitForNoStudio(origin, timeoutMs = 15_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const targets = await (await fetch(`${origin}/json/list`)).json()
    if (!targets.some(target => target.type === 'page' && target.url.includes('studio.html'))) return
    await wait(100)
  }
  throw new Error('timed out waiting for Studio window close')
}

async function closeWindowNormally() {
  assert.equal(await native.evaluate("(()=>{const w=qaElectron.BrowserWindow.getAllWindows().find(w=>w.getTitle().includes('工作流工作台'));if(!w)return false;w.close();return true})()"), true)
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

async function selectNode(cdp, nodeId, moduleType) {
  for (let attempt = 0; attempt < 3; attempt++) {
    const p = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__node[data-id=${JSON.stringify(nodeId)}]');if(!e)return null;const r=e.getBoundingClientRect(),fractions=[[.5,.5],[.2,.5],[.8,.5],[.5,.2],[.5,.8]];for(const [xf,yf] of fractions){const x=r.x+r.width*xf,y=r.y+r.height*yf;if(e.contains(document.elementFromPoint(x,y)))return{x,y}}return null})()`, `visible node ${nodeId}`)
    await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p })
    await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 })
    await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 })
    await wait(150)
    if (await cdp.evaluate(`[...document.querySelectorAll('span')].some(e=>e.getClientRects().length&&e.textContent.trim()===${JSON.stringify(moduleType)}&&e.classList.contains('badge'))`)) return
  }
  throw new Error(`failed to select ${moduleType} (${nodeId})`)
}

async function setInjectCode(cdp, code) {
  await click(cdp, '打开代码编辑器', 'div')
  await waitFor(cdp, "document.body?.innerText.includes('JavaScript 脚本注入编辑器') && Boolean(document.querySelector('.monaco-editor'))", 'JavaScript editor')
  await click(cdp, '', '.monaco-editor')
  await press(cdp, 'a', { modifiers: 4, code: 'KeyA', keyCode: 65 })
  await cdp.command('Input.insertText', { text: code })
  await click(cdp, '保存', 'div[style*="2147483646"] button')
  await waitFor(cdp, "!document.body?.innerText.includes('JavaScript 脚本注入编辑器')", 'JavaScript editor close')
  await waitFor(cdp, `document.querySelector('#javascriptCode')?.value === ${JSON.stringify(code)}`, 'saved JavaScript code in node panel')
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

async function moveNode(cdp, nodeId, index, count) {
  const pane = await cdp.evaluate(`(()=>{const r=document.querySelector('.react-flow__pane').getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height}})()`)
  const from = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__node[data-id=${JSON.stringify(nodeId)}]');if(!e)return null;const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, `node position ${nodeId}`)
  const columns = 3, rows = Math.ceil(count / columns), column = index % columns, row = Math.floor(index / columns)
  const to = { x: pane.x + pane.width * (.12 + column * .38), y: pane.y + 260 + row * ((pane.height - 520) / Math.max(1, rows - 1)) }
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...from })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...from, button: 'left', buttons: 1, clickCount: 1 })
  for (let step = 1; step <= 10; step++) await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', x: from.x + (to.x - from.x) * step / 10, y: from.y + (to.y - from.y) * step / 10, button: 'left', buttons: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...to, button: 'left', buttons: 0, clickCount: 1 })
  await wait(100)
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
    'apps/backend/src/autoflow/application/workflows/executors/web_basic.py',
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
