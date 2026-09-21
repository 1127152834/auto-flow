import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename, join, resolve } from 'node:path'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const sourceKernel = process.env.AUTOFLOW_B1_KERNEL_DIR
  ?? '/Users/zhangtiancheng/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2'
const kernelVersion = basename(sourceKernel).replace(/^chromium-/, '')
const evidenceRoot = join(root, 'docs/migration/studio-backend-migration/evidence/b6')
const evidenceDir = await mkdtemp(join(await mkdir(evidenceRoot, { recursive: true }).then(() => evidenceRoot), 'formal-desktop-platform-electron-'))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-b6-desktop-platform-'))
const workflowName = 'B6 桌面平台正式闭环'
const clipboardMarker = `AUTOFLOW_B6_CLIPBOARD_${randomUUID()}`
const checks = []
let desktop, main, studio

await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await mkdir(join(userData, 'data', 'kernels'), { recursive: true })
execFileSync('cp', ['-cR', sourceKernel, join(userData, 'data', 'kernels', basename(sourceKernel))])

try {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`] })
  main = desktop.cdp
  await main.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(main, "document.body?.innerText.includes('本地服务正常')", 'main service readiness', 30_000)
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  const profile = await api(runtime, '/v1/profiles', {
    method: 'POST',
    body: {
      name: 'B6 命令日志验收配置', description: '临时工作区；本流程不启动浏览器', startUrl: 'about:blank',
      locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false, headless: true, humanize: false,
      humanPreset: 'default', userAgent: null, viewportJson: null, colorScheme: 'light', extensionPathsJson: [], expertArgsJson: [],
      browserVersion: kernelVersion, browserEdition: 'public', releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null,
    },
  })
  assert.deepEqual(cloakProcesses(userData), [])

  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 2560, height: 1600, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库') && document.body.innerText.includes('213')", 'formal Studio', 30_000)
  await waitFor(studio, `document.querySelector('[aria-label="运行浏览器配置"]')?.value === ${JSON.stringify(profile.id)}`, 'managed Profile selection')
  checkpoint('主窗口真实点击打开正式 Studio；动作库为 213，运行配置来自主应用 Profile')

  await click(studio, '新建')
  await setInput(studio, 'input[placeholder="工作流名称"]', workflowName)

  const setClipboardId = await addNode(studio, 0, '写入剪贴板', 'set_clipboard')
  await setInput(studio, 'textarea[placeholder="要复制到剪贴板的文本，支持 {变量名}"]', clipboardMarker)

  const getClipboardId = await addNode(studio, 1, '读取剪贴板', 'get_clipboard')
  await setInput(studio, 'input[placeholder="存储剪贴板内容的变量名"]', 'clipboard_value')

  const printId = await addNode(studio, 2, '打印日志', 'print_log')
  await setInput(studio, 'input[placeholder="要打印的日志信息"]', '剪贴板结果={clipboard_value}')

  const soundId = await addNode(studio, 3, '提示音', 'play_sound')
  const notificationId = await addNode(studio, 4, '系统消息', 'system_notification')
  await setInput(studio, 'input[placeholder="通知的标题"]', 'AutoFlow 验收')
  await setInput(studio, 'input[placeholder="通知的详细内容"]', '平台节点已完成')

  await connectNodes(studio, setClipboardId, getClipboardId)
  await connectNodes(studio, getClipboardId, printId)
  await connectNodes(studio, printId, soundId)
  await connectNodes(studio, soundId, notificationId)
  await waitFor(studio, "document.querySelectorAll('.react-flow__edge').length === 4", 'workflow edges')
  checkpoint('通过正式 Studio 真实 UI 添加并配置剪贴板、日志、提示音和系统通知节点')

  await click(studio, '保存')
  await waitFor(studio, `document.body?.innerText.includes(${JSON.stringify(`工作流已保存: ${workflowName}`)})`, 'workflow save')
  const saved = (await api(runtime, '/workflows')).find(item => item.name === workflowName)
  assert.ok(saved)
  assert.deepEqual(saved.nodes.map(node => node.data.moduleType), ['set_clipboard', 'get_clipboard', 'print_log', 'play_sound', 'system_notification'])
  assert.equal(saved.edges.length, 4)
  checkpoint('正式保存接口把五个桌面节点、四条连线和字段配置写入临时 SQLite')

  await click(studio, '运行 (F5)', '[aria-label="运行 (F5)"]')
  await click(studio, '运行 (F5)', '[role="menuitem"]')
  const run = await waitForValue(async () => (await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(saved.id)}&cursor=0&limit=20`)).items[0], 'run creation', 20_000)
  const terminal = await waitForValue(async () => {
    const value = await api(runtime, `/workflow-runs/${encodeURIComponent(run.runId)}`)
    return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.status) ? value : null
  }, 'terminal run', 60_000)
  assert.equal(terminal.status, 'completed')
  await waitFor(studio, "document.body?.innerText.includes('执行完成')", 'rendered completion', 10_000)

  const results = await api(runtime, `/workflow-runs/${encodeURIComponent(run.runId)}/results?cursor=0&limit=20`)
  const byNode = Object.fromEntries(results.items.map(item => [item.nodeId, item.values]))
  assert.deepEqual(byNode[soundId], { count: 1 })
  assert.deepEqual(byNode[notificationId], { title: 'AutoFlow 验收', message: '平台节点已完成', duration: 5 })
  const clipboardCheck = await studio.evaluate("window.autoflow.runStudioPlatformAction({ action: 'clipboard_read_text' })")
  assert.equal(clipboardCheck.ok, true)
  assert.equal(clipboardCheck.value.value, clipboardMarker)

  const logs = await api(runtime, `/workflow-runs/${encodeURIComponent(run.runId)}/logs?cursor=0&limit=50`)
  assert.ok(logs.items.some(item => item.nodeId === setClipboardId))
  assert.ok(logs.items.some(item => item.nodeId === getClipboardId))
  assert.ok(logs.items.some(item => item.nodeId === printId))
  assert.ok(logs.items.some(item => item.nodeId === soundId && item.message.includes('已播放 1 次提示音')))
  assert.ok(logs.items.some(item => item.nodeId === notificationId && item.message.includes('已显示系统通知')))
  assert.equal(JSON.stringify(logs).includes(clipboardMarker), false)
  checkpoint('真实 worker 通过 Electron 平台桥写入并读取系统剪贴板，播放提示音并显示系统通知；变量和日志均核验')

  await wait(500)
  assert.deepEqual(cloakProcesses(userData), [])
  checkpoint('纯系统工具流程未启动 CloakBrowser，运行结束后无子进程或浏览器残留')

  await capture(studio, join(evidenceDir, 'completed.png'))
  const report = {
    evidenceId: 'BE-B6-desktop-platform-formal-electron', checkedAt: new Date().toISOString(),
    gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    result: 'passed', platform: `${process.platform}-${process.arch}`, entry: 'development-build',
    workflowId: saved.id, profileId: profile.id, runId: run.runId, checks,
    nodes: [
      { moduleType: 'set_clipboard', nodeId: setClipboardId, result: byNode[setClipboardId] },
      { moduleType: 'get_clipboard', nodeId: getClipboardId, result: byNode[getClipboardId] },
      { moduleType: 'print_log', nodeId: printId, result: byNode[printId] },
      { moduleType: 'play_sound', nodeId: soundId, result: byNode[soundId] },
      { moduleType: 'system_notification', nodeId: notificationId, result: byNode[notificationId] },
    ],
    buildSha256: await buildHash(),
    boundaries: {
      workspace: 'ephemeral', userDatabaseTouched: false, browserLaunch: 'none',
      clipboard: 'random marker written and read through native Electron clipboard; no user data',
      interaction: 'formal Electron via CDP mouse and keyboard; public sidecar APIs only for fixture setup and evidence reads; no Store or page-internal business function access',
      platformPending: 'Windows native clipboard/notification and prompt sound remain separately unverified',
    },
  }
  await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
} catch (error) {
  if (studio) await capture(studio, join(evidenceDir, 'failure.png')).catch(() => undefined)
  await writeFile(join(evidenceDir, 'failure.json'), JSON.stringify({ checkedAt: new Date().toISOString(), checks, error: error instanceof Error ? error.stack : String(error) }, null, 2) + '\n')
  throw error
} finally {
  studio?.close(); main?.close(); await stop(desktop?.child)
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

async function artifactText(runtime, runId, artifactId) {
  const response = await fetch(`${runtime.sidecar.baseUrl}/api/workflow-runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactId)}`, { headers: { 'x-autoflow-token': runtime.sidecar.token } })
  if (!response.ok) throw new Error(`artifact read: ${response.status} ${await response.text()}`)
  return response.text()
}

async function openStudioFromMain(cdp, origin) {
  await click(cdp, '工作流工作台')
  const target = await waitForValue(async () => (await (await fetch(`${origin}/json/list`)).json()).find(item => item.type === 'page' && item.url.includes('studio.html')), 'Studio target', 20_000)
  return connectCdp(target.webSocketDebuggerUrl)
}

async function waitForValue(read, description, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const value = await read()
    if (value) return value
    await wait(200)
  }
  throw new Error(`timed out waiting for ${description}`)
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
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 3 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 3 })
  await cdp.command('Input.insertText', { text: value })
  await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
  await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
  await wait(100)
}

async function addNode(cdp, index, label, moduleType) {
  const pane = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__pane');if(!e)return null;const r=e.getBoundingClientRect();for(let yi=1;yi<9;yi++)for(let xi=1;xi<9;xi++){const x=r.x+r.width*xi/10,y=r.y+r.height*yi/10,hit=document.elementFromPoint(x,y);if(hit&&e.contains(hit)&&!hit.closest('.react-flow__node')&&!hit.closest('[role=dialog]'))return{x,y}}return null})()`, 'workflow canvas')
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...pane, button: 'right', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...pane, button: 'right', clickCount: 1 })
  await setInput(cdp, 'input[placeholder="搜索模块（支持拼音）"]', label)
  await click(cdp, label, '[role="button"]')
  const nodeId = await waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll('.react-flow__node')].filter(e=>e.textContent.includes(${JSON.stringify(label)}));return rows.at(-1)?.dataset.id||null})()`, `${moduleType} node`)
  await moveNode(cdp, nodeId, index)
  await selectNode(cdp, nodeId, moduleType)
  return nodeId
}

async function selectNode(cdp, nodeId, moduleType) {
  const p = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__node[data-id=${JSON.stringify(nodeId)}]');if(!e)return null;const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, `node ${nodeId}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 })
  await waitFor(cdp, `[...document.querySelectorAll('span')].some(e=>e.getClientRects().length&&e.textContent.trim()===${JSON.stringify(moduleType)}&&e.classList.contains('badge'))`, `${moduleType} config`)
}

async function moveNode(cdp, nodeId, index) {
  const from = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__node[data-id=${JSON.stringify(nodeId)}]');if(!e)return null;const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, `node position ${nodeId}`)
  const pane = await cdp.evaluate("(()=>{const r=document.querySelector('.react-flow__pane').getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height}})()")
  const to = { x: pane.x + pane.width * .35, y: pane.y + 240 + index * 260 }
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...from, button: 'left', buttons: 1, clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...to, button: 'left', buttons: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...to, button: 'left', buttons: 0, clickCount: 1 })
  await wait(100)
}

async function connectNodes(cdp, sourceId, targetId) {
  const points = await waitFor(cdp, `(()=>{const a=document.querySelector('.react-flow__node[data-id=${JSON.stringify(sourceId)}] .react-flow__handle.source:not([data-handleid])'),b=document.querySelector('.react-flow__node[data-id=${JSON.stringify(targetId)}] .react-flow__handle.target');if(!a||!b)return null;const ar=a.getBoundingClientRect(),br=b.getBoundingClientRect();return{a:{x:ar.x+ar.width/2,y:ar.y+ar.height/2},b:{x:br.x+br.width/2,y:br.y+br.height/2}}})()`, `handles ${sourceId} -> ${targetId}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...points.a, button: 'left', buttons: 1, clickCount: 1 })
  for (let step = 1; step <= 10; step++) await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', x: points.a.x + (points.b.x - points.a.x) * step / 10, y: points.a.y + (points.b.y - points.a.y) * step / 10, button: 'left', buttons: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...points.b, button: 'left', buttons: 0, clickCount: 1 })
  await wait(120)
}

function cloakProcesses(workspace) {
  return execFileSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).split('\n').filter(line => line.includes(workspace) && /Chromium|CloakBrowser/.test(line))
}

async function capture(cdp, path) {
  const { data } = await cdp.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  await writeFile(path, data, 'base64')
}

async function buildHash() {
  const hash = createHash('sha256')
  for (const file of (await readdir(join(root, 'apps/desktop/out'), { recursive: true })).filter(file => /\.(js|css|html)$/.test(file)).sort()) hash.update(file).update(await readFile(join(root, 'apps/desktop/out', file)))
  return hash.digest('hex')
}
