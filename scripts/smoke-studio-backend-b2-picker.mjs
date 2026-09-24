import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { randomUUID } from 'node:crypto'
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import { tmpdir } from 'node:os'
import { basename, join, resolve } from 'node:path'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const sourceKernel = process.env.AUTOFLOW_B1_KERNEL_DIR
  ?? '/Users/zhangtiancheng/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2'
const kernelVersion = basename(sourceKernel).replace(/^chromium-/, '')
const evidenceRoot = join(root, 'docs/migration/studio-backend-migration/evidence/b2')
await mkdir(evidenceRoot, { recursive: true })
const evidenceDir = await mkdtemp(join(evidenceRoot, 'formal-picker-electron-'))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-b2-picker-'))
const checks = []
let clickCount = 0
let desktop, main, studio

const fixture = Buffer.from(`<!doctype html><meta charset="utf-8"><title>AutoFlow 拾取页</title>
<button id="pick-target">正式拾取目标</button><output id="count">0</output>
<script>
pick_target = document.getElementById('pick-target'); count = document.getElementById('count');
pick_target.addEventListener('click', () => { count.textContent = String(Number(count.textContent) + 1); fetch('/clicked', {method:'POST'}); });
setInterval(() => { if (window.__elementPickerActive && !window.__formalPickerSent) { window.__formalPickerSent = true; const r=pick_target.getBoundingClientRect(); pick_target.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,metaKey:true,clientX:r.x+r.width/2,clientY:r.y+r.height/2})); } }, 100);
</script>`)
const server = createServer((request, response) => {
  if (request.url === '/clicked' && request.method === 'POST') {
    clickCount += 1
    response.writeHead(204).end()
    return
  }
  response.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'content-length': fixture.length })
  response.end(fixture)
})
await new Promise((resolveListen, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolveListen) })
const address = server.address()
assert.ok(address && typeof address === 'object')
const fixtureUrl = `http://127.0.0.1:${address.port}/picker`

await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await mkdir(join(userData, 'data', 'kernels'), { recursive: true })
execFileSync('cp', ['-cR', sourceKernel, join(userData, 'data', 'kernels', basename(sourceKernel))])

try {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'] })
  main = desktop.cdp
  await main.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(main, "document.body?.innerText.includes('本地服务正常')", 'main service readiness', 30_000)
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  const profile = await api(runtime, '/v1/profiles', {
    method: 'POST', body: {
      name: 'B2 正式拾取验收配置', description: '隔离工作区中的 CloakBrowser 配置', startUrl: 'about:blank',
      locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false, headless: true, humanize: false,
      humanPreset: 'default', userAgent: null, viewportJson: { width: 1280, height: 720 }, colorScheme: 'light',
      extensionPathsJson: [], expertArgsJson: [], browserVersion: kernelVersion, browserEdition: 'public',
      releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null,
    },
  })
  checkpoint('临时工作区创建真实 CloakBrowser Profile')

  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 3000, height: 1800, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库')", 'formal Studio', 30_000)
  await waitFor(studio, `document.querySelector('[aria-label="运行浏览器配置"]')?.value === ${JSON.stringify(profile.id)}`, 'managed Profile selection')
  await click(studio, '新建')
  await setInput(studio, 'input[placeholder="工作流名称"]', 'B2 正式拾取闭环')

  await addFromQuickPicker(studio, 0, '打开网页')
  const openNode = await latestNode(studio, '打开网页')
  await selectNode(studio, openNode, 'open_page')
  await setInput(studio, '[placeholder="https://example.com"]', fixtureUrl)
  await selectOption(studio, '#openMode', '当前标签页')

  await addFromQuickPicker(studio, 1, '点击元素')
  const clickNode = await latestNode(studio, '点击元素')
  await selectNode(studio, clickNode, 'click_element')
  const selectorControls = 'div.flex.gap-2:has(input[placeholder="例如: #button, .submit"])'
  await click(studio, '', `${selectorControls} button:first-of-type`)
  await setInput(studio, 'input[placeholder="留空则使用当前页面，或输入新URL"]', fixtureUrl)
  await click(studio, '启动选择器')
  await waitFor(studio, "document.body?.innerText.includes('元素选择器已启动')", 'picker start acknowledgement', 30_000)
  await waitFor(studio, "document.querySelector('input[placeholder=\"例如: #button, .submit\"]')?.value === '#pick-target'", 'picked selector applied', 30_000)
  assert.equal(clickCount, 0, 'picker click must not trigger page action')
  checkpoint('通过正式配置面板启动真实拾取，定位写回点击节点且页面动作被拦截')

  await waitFor(studio, `(()=>{const e=document.querySelector(${JSON.stringify(`${selectorControls} button:nth-of-type(2)`)});return e&&!e.disabled})()`, 'picker cleanup before selector test', 15_000)
  await click(studio, '', `${selectorControls} button:nth-of-type(2)`)
  await waitFor(studio, "document.body?.innerText.includes('命中 1 个元素')", 'selector test result', 15_000)
  checkpoint('正式 Studio 测试定位命中真实页面并返回数量')

  await click(studio, '', '.react-flow__controls-fitview')
  await connectNodes(studio, openNode, clickNode)
  await click(studio, '保存')
  await waitFor(studio, "document.body?.innerText.includes('工作流已保存: B2 正式拾取闭环')", 'workflow save acknowledgement')
  const saved = (await api(runtime, '/workflows')).find(item => item.name === 'B2 正式拾取闭环')
  assert.ok(saved)
  assert.equal(saved.nodes.find(node => node.id === clickNode)?.data.selector, '#pick-target')
  assert.equal((await api(runtime, `/v1/profiles/${encodeURIComponent(profile.id)}`)).headless, true)
  checkpoint('拾取结果经真实 HTTP/SQLite 保存')

  const blockedRun = await apiResponse(runtime, `/workflows/${encodeURIComponent(saved.id)}/execute`, {
    method: 'POST', body: { runId: randomUUID(), documentId: saved.id, profileId: profile.id },
  })
  assert.equal(blockedRun.status, 409)
  assert.equal((await api(runtime, '/browser/status')).isOpen, true)
  checkpoint('拾取会话占用期间真实运行被原子拒绝，Profile原始无头配置未被修改')

  await click(studio, '自动化浏览器', '[aria-label="自动化浏览器"]')
  await waitFor(studio, "document.body?.innerText.includes('关闭浏览器')", 'browser session dialog')
  await click(studio, '关闭浏览器')
  await waitFor(studio, "document.body?.innerText.includes('打开浏览器')", 'inspection browser closed', 30_000)
  await click(studio, '', '.modern-dialog-header button')
  checkpoint('拾取浏览器经正式 UI 关闭并完成清理')

  await click(studio, '运行 (F5)', '[aria-label="运行 (F5)"]')
  await click(studio, '运行 (F5)', '[role="menuitem"]')
  const started = await waitForValue(async () => (await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(saved.id)}&cursor=0&limit=20`)).items[0] ?? null, 'workflow run', 20_000)
  const terminal = await waitForValue(async () => {
    const run = await api(runtime, `/workflow-runs/${encodeURIComponent(started.runId)}`)
    return ['completed', 'failed', 'stopped', 'interrupted'].includes(run.status) ? run : null
  }, 'workflow terminal state', 120_000)
  assert.equal(terminal.status, 'completed')
  await waitForValue(async () => clickCount === 1 ? true : null, 'independent workflow click', 10_000)
  checkpoint('关闭拾取会话后，独立 CloakBrowser 运行保存流程并点击同一元素')

  await capture(studio, join(evidenceDir, 'completed.png'))
  const report = {
    evidenceId: 'BE-B2-picker-formal-electron', checkedAt: new Date().toISOString(),
    gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    result: 'passed', platform: `${process.platform}-${process.arch}`, entry: 'development-build',
    workflowId: saved.id, profileId: profile.id, runId: started.runId, selector: '#pick-target', clickCount, checks,
    boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browser: 'CloakBrowser only', interaction: 'formal Studio UI through CDP; picker event executes inside the real CloakBrowser fixture; no Store access' },
  }
  await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
} catch (error) {
  if (studio) await capture(studio, join(evidenceDir, 'failure.png')).catch(() => undefined)
  await writeFile(join(evidenceDir, 'failure.json'), JSON.stringify({ checkedAt: new Date().toISOString(), checks, error: error instanceof Error ? error.stack : String(error) }, null, 2) + '\n')
  throw error
} finally {
  studio?.close(); main?.close(); await stop(desktop?.child)
  await new Promise(resolveClose => server.close(resolveClose))
  await rm(userData, { recursive: true, force: true })
}

function checkpoint(message) { checks.push(message); console.log(message) }

async function api(runtime, path, options = {}) {
  const response = await apiResponse(runtime, path, options)
  if (!response.ok) throw new Error(`${options.method ?? 'GET'} /api${path}: ${response.status} ${await response.text()}`)
  return response.status === 204 ? undefined : response.json()
}

function apiResponse(runtime, path, options = {}) {
  return fetch(`${runtime.sidecar.baseUrl}/api${path}`, {
    method: options.method ?? 'GET',
    headers: { 'x-autoflow-token': runtime.sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': randomUUID() },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })
}

async function openStudioFromMain(cdp, origin) {
  for (let attempt = 0; attempt < 3; attempt++) {
    await click(cdp, '工作流工作台')
    try {
      const target = await waitForValue(async () => (await (await fetch(`${origin}/json/list`)).json()).find(item => item.type === 'page' && item.url.includes('studio.html')) ?? null, 'Studio target', 8_000)
      return connectCdp(target.webSocketDebuggerUrl)
    } catch { /* the dashboard can rerender while its resource status refreshes */ }
  }
  throw new Error('正式 Studio 窗口未能从主界面打开')
}

async function waitForValue(read, description, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  let last
  while (Date.now() < deadline) { last = await read(); if (last) return last; await wait(200) }
  throw new Error(`timed out waiting for ${description}: ${JSON.stringify(last)}`)
}

async function point(cdp, selector, text = '') {
  return waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length),text=${JSON.stringify(text)};const e=!text?rows[0]:rows.find(e=>e.getAttribute('aria-label')===text)||rows.find(e=>e.textContent.trim()===text)||rows.find(e=>e.textContent.includes(text));if(!e||e.disabled)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `unobscured ${text || selector}`)
}

async function click(cdp, text, selector = 'button') {
  const p = await point(cdp, selector, text)
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

async function addFromQuickPicker(cdp, index, label) {
  const target = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__pane');if(!e)return null;const r=e.getBoundingClientRect(),x=r.x+r.width*.5,y=r.y+r.height*(.3+${index}*.15);return document.elementFromPoint(x,y)===e?{x,y}:null})()`, 'workflow canvas')
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...target, button: 'right', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...target, button: 'right', clickCount: 1 })
  await setInput(cdp, 'input[placeholder="搜索模块（支持拼音）"]', label)
  await click(cdp, label, '[role="button"]')
}

async function latestNode(cdp, label) {
  return waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll('.react-flow__node')].filter(e=>e.textContent.includes(${JSON.stringify(label)}));return rows.at(-1)?.dataset.id||null})()`, `${label} node`)
}

async function selectNode(cdp, nodeId, moduleType) {
  const p = await point(cdp, `.react-flow__node[data-id=${JSON.stringify(nodeId)}]`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 })
  await waitFor(cdp, `[...document.querySelectorAll('span')].some(e=>e.getClientRects().length&&e.textContent.trim()===${JSON.stringify(moduleType)}&&e.classList.contains('badge'))`, `${moduleType} config`)
}

async function selectOption(cdp, selector, label) {
  await click(cdp, '', selector); await click(cdp, label, '[role="option"]')
}

async function connectNodes(cdp, sourceId, targetId) {
  const points = await waitFor(cdp, `(()=>{const a=document.querySelector('.react-flow__node[data-id=${JSON.stringify(sourceId)}] .react-flow__handle.source:not([data-handleid])'),b=document.querySelector('.react-flow__node[data-id=${JSON.stringify(targetId)}] .react-flow__handle.target');if(!a||!b)return null;const ar=a.getBoundingClientRect(),br=b.getBoundingClientRect();return{a:{x:ar.x+ar.width/2,y:ar.y+ar.height/2},b:{x:br.x+br.width/2,y:br.y+br.height/2}}})()`, 'workflow handles')
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...points.a, button: 'left', buttons: 1, clickCount: 1 })
  for (let step = 1; step <= 10; step++) await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', x: points.a.x + (points.b.x - points.a.x) * step / 10, y: points.a.y + (points.b.y - points.a.y) * step / 10, button: 'left', buttons: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...points.b, button: 'left', buttons: 0, clickCount: 1 })
  await waitFor(cdp, "document.querySelectorAll('.react-flow__edge').length === 1", 'workflow edge')
}

async function capture(cdp, path) {
  const { data } = await cdp.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  await writeFile(path, data, 'base64')
}
