import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { randomUUID } from 'node:crypto'
import { createServer } from 'node:net'
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename, join, resolve } from 'node:path'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const sourceKernel = process.env.AUTOFLOW_B1_KERNEL_DIR ?? '/Users/zhangtiancheng/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2'
const evidenceRoot = join(root, 'docs/migration/studio-backend-migration/evidence/b6')
await mkdir(evidenceRoot, { recursive: true })
const evidenceDir = await mkdtemp(join(evidenceRoot, 'formal-network-sharing-electron-'))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-b6-sharing-'))
const ports = await Promise.all(Array.from({ length: 3 }, () => freePort()))
const [folderPort, filePort, screenPort] = ports
const folder = join(userData, 'shared-folder')
const file = join(userData, 'shared-file.txt')
const marker = `AutoFlow 网络共享验收 ${randomUUID()}`
const checks = []
let desktop, main, studio

try {
  assert.equal(process.platform, 'darwin', '当前脚本只在 macOS 实机验证，其他平台单独记账')
  await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
  await mkdir(join(userData, 'data/kernels'), { recursive: true })
  execFileSync('cp', ['-cR', sourceKernel, join(userData, 'data/kernels', basename(sourceKernel))])
  await mkdir(folder)
  await writeFile(join(folder, 'item.txt'), marker)
  await writeFile(file, marker)

  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'] })
  main = desktop.cdp
  await main.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(main, "document.body?.innerText.includes('本地服务正常')", 'main readiness', 30_000)
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  const profile = await api(runtime, '/v1/profiles', { method: 'POST', body: {
    name: 'B6 网络共享临时配置', description: '纯系统节点，不启动浏览器', startUrl: 'about:blank', locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false,
    headless: true, humanize: false, humanPreset: 'default', userAgent: null, viewportJson: null, colorScheme: 'light', extensionPathsJson: [], expertArgsJson: [],
    browserVersion: basename(sourceKernel).replace(/^chromium-/, ''), browserEdition: 'public', releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null,
  } })
  await click(main, '工作流工作台')
  const target = await waitForValue(async () => (await (await fetch(`${desktop.debugOrigin}/json/list`)).json()).find(t => t.type === 'page' && t.url.includes('studio.html')), 'Studio target', 30_000)
  studio = await connectCdp(target.webSocketDebuggerUrl)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 2560, height: 1600, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库') && document.body.innerText.includes('213')", 'approved Studio scope', 30_000)
  await waitFor(studio, `document.querySelector('[aria-label="运行浏览器配置"]')?.value === ${JSON.stringify(profile.id)}`, 'main Profile')
  checks.push('主窗口真实点击打开正式 Studio；213 节点和主应用 Profile 均已核对')

  const start = await createFlow('B6 共享启动正式闭环', [
    ['文件夹网络共享', 'share_folder', [['input[placeholder="选择要共享的文件夹"]', folder], ['input[inputmode="numeric"]', String(folderPort)]]],
    ['文件网络共享', 'share_file', [['input[placeholder="选择要共享的文件"]', file], ['input[inputmode="numeric"]', String(filePort)]]],
    ['开始屏幕共享', 'start_screen_share', [['input[inputmode="numeric"]', String(screenPort)]]],
  ])
  const started = await runFlow(start)
  assert.equal(started.status, 'completed', JSON.stringify(started))
  const folderList = await fetch(`http://127.0.0.1:${folderPort}/api/list`, { signal: AbortSignal.timeout(5_000) })
  assert.equal(folderList.status, 200)
  assert.match(await folderList.text(), /item\.txt/)
  const downloaded = await fetch(`http://127.0.0.1:${folderPort}/download/item.txt`, { signal: AbortSignal.timeout(5_000) })
  assert.equal(await downloaded.text(), marker)
  const single = await fetch(`http://127.0.0.1:${filePort}/download`, { signal: AbortSignal.timeout(5_000) })
  assert.equal(await single.text(), marker)
  const frame = await waitForValue(async () => {
    const response = await fetch(`http://127.0.0.1:${screenPort}/frame`, { signal: AbortSignal.timeout(5_000) })
    const bytes = Buffer.from(await response.arrayBuffer())
    return response.status === 200 && bytes.subarray(0, 3).equals(Buffer.from([0xff, 0xd8, 0xff])) ? bytes.length : null
  }, 'real captured JPEG frame', 15_000)
  checks.push('独立 worker 运行结束后，宿主仍提供文件夹列表、原文下载及真实屏幕 JPEG 帧')

  const stopping = await createFlow('B6 共享停止正式闭环', [
    ['停止网络共享', 'stop_share', [['input[inputmode="numeric"]', String(folderPort)]]],
    ['停止网络共享', 'stop_share', [['input[inputmode="numeric"]', String(filePort)]]],
    ['停止屏幕共享', 'stop_screen_share', [['input[inputmode="numeric"]', String(screenPort)]]],
  ])
  const stopped = await runFlow(stopping)
  assert.equal(stopped.status, 'completed', JSON.stringify(stopped))
  for (const port of ports) await waitForValue(async () => {
    try { await fetch(`http://127.0.0.1:${port}/`, { signal: AbortSignal.timeout(1_000) }); return null }
    catch { return true }
  }, `port ${port} closed`, 10_000)
  checks.push('通过正式 UI 停止两个文件共享与屏幕共享；三个端口均已关闭')

  const report = {
    evidenceId: 'BE-B6-network-sharing-formal-electron', checkedAt: new Date().toISOString(), result: 'passed',
    gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    platform: `${process.platform}-${process.arch}`, entry: desktop.packaged ? 'packaged' : 'development-build',
    workflows: [start, stopping], runs: [started.runId, stopped.runId], profileId: profile.id, ports,
    downloadedBytes: Buffer.byteLength(marker), frameBytes: frame, checks,
    boundaries: { userDatabaseTouched: false, workspace: 'ephemeral', interaction: 'CDP mouse and keyboard; service APIs only for Profile fixture and post-run evidence', pending: 'Windows/macOS Intel, macOS permission denial, and second LAN device remain separately unverified' },
  }
  await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
} catch (error) {
  const visibleText = studio ? await studio.evaluate('document.body?.innerText').catch(() => '') : ''
  if (studio) {
    const { data } = await studio.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }).catch(() => ({ data: null }))
    if (data) await writeFile(join(evidenceDir, 'failure.png'), data, 'base64')
  }
  await writeFile(join(evidenceDir, 'failure.json'), JSON.stringify({ checkedAt: new Date().toISOString(), checks, visibleText, error: error instanceof Error ? error.stack : String(error) }, null, 2) + '\n')
  throw error
} finally {
  studio?.close(); main?.close(); await stop(desktop?.child)
  await rm(userData, { recursive: true, force: true })
}

async function createFlow(name, nodes) {
  await click(studio, '新建')
  await setInput(studio, 'input[placeholder="工作流名称"]', name)
  const ids = []
  for (const [label, type, fields] of nodes) {
    ids.push(await addNode(studio, label, type))
    for (const [selector, value] of fields) await setInput(studio, selector, value)
  }
  for (let index = 0; index < ids.length - 1; index++) await connectNodes(studio, ids[index], ids[index + 1])
  await click(studio, '保存')
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  const saved = await waitForValue(async () => (await api(runtime, '/workflows')).find(item => item.name === name), 'saved workflow', 20_000)
  assert.ok(saved)
  assert.deepEqual(saved.nodes.map(node => node.data.moduleType), nodes.map(([, type]) => type))
  assert.equal(saved.edges.length, nodes.length - 1)
  await click(studio, '新建')
  await click(studio, '打开')
  await click(studio, `打开工作流 ${name}`, '[role="button"]')
  await waitFor(studio, `document.querySelectorAll('.react-flow__node').length === ${nodes.length}`, 'reopened nodes')
  checks.push(`${name}：真实界面配置、保存、切换并重开，节点与连线已从 SQLite 恢复`)
  return { workflowId: saved.id, name, nodes: ids }
}

async function runFlow(flow) {
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  await click(studio, '运行 (F5)', '[aria-label="运行 (F5)"]')
  await click(studio, '运行 (F5)', '[role="menuitem"]')
  const run = await waitForValue(async () => (await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(flow.workflowId)}&cursor=0&limit=20`)).items[0], 'run', 20_000)
  const done = await waitForValue(async () => {
    const value = await api(runtime, `/workflow-runs/${run.runId}`)
    return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.status) ? value : null
  }, 'run completion', 60_000)
  const logs = await api(runtime, `/workflow-runs/${run.runId}/logs?cursor=0&limit=100`)
  for (const id of flow.nodes) assert.ok(logs.items.some(item => item.nodeId === id), `missing log for ${id}`)
  return { runId: run.runId, status: done.status, error: done.error }
}

async function freePort() { const server = createServer(); await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); const port = server.address().port; await new Promise(resolve => server.close(resolve)); return port }
async function api(runtime, path, options = {}) { const response = await fetch(`${runtime.sidecar.baseUrl}/api${path}`, { method: options.method ?? 'GET', headers: { 'x-autoflow-token': runtime.sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': randomUUID() }, body: options.body === undefined ? undefined : JSON.stringify(options.body) }); if (!response.ok) throw new Error(`${options.method ?? 'GET'} /api${path}: ${response.status} ${await response.text()}`); return response.status === 204 ? undefined : response.json() }
async function waitForValue(read, description, timeoutMs) { const deadline = Date.now() + timeoutMs; while (Date.now() < deadline) { const value = await read(); if (value) return value; await wait(200) } throw new Error(`timed out waiting for ${description}`) }
async function point(cdp, selector, text = '') { return waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length),text=${JSON.stringify(text)};const e=!text?rows[0]:rows.find(e=>e.getAttribute('aria-label')===text)||rows.find(e=>e.textContent.trim()===text)||rows.find(e=>e.textContent.includes(text));if(!e||e.disabled)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `unobscured ${text || selector}`) }
async function click(cdp, text, selector = 'button') { const p = await point(cdp, selector, text); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p }); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 }); await wait(100) }
async function setInput(cdp, selector, value) { const p = await point(cdp, selector); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 3 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 3 }); await cdp.command('Input.insertText', { text: value }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 }); await wait(100) }
async function addNode(cdp, label, moduleType) { const pane = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__pane');if(!e)return null;const r=e.getBoundingClientRect(),nodes=[...document.querySelectorAll('.react-flow__node')];for(const y of [.2,.45,.7])for(const x of [.15,.4,.65,.9]){const p={x:r.x+r.width*x,y:r.y+r.height*y};if(nodes.every(n=>{const b=n.getBoundingClientRect();return Math.abs((b.left+b.right)/2-p.x)>170||Math.abs((b.top+b.bottom)/2-p.y)>90})&&document.elementFromPoint(p.x,p.y)===e)return p}return null})()`, 'workflow canvas'); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...pane, button: 'right', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...pane, button: 'right', clickCount: 1 }); await setInput(cdp, 'input[placeholder="搜索模块（支持拼音）"]', label); await click(cdp, label, '[role="button"]'); const id = await waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll('.react-flow__node')].filter(e=>e.textContent.includes(${JSON.stringify(label)}));return rows.at(-1)?.dataset.id||null})()`, `${moduleType} node`); await click(cdp, '', `.react-flow__node[data-id=${JSON.stringify(id)}]`); await waitFor(cdp, `document.body.innerText.includes(${JSON.stringify(moduleType)})`, 'node configuration'); return id }
async function connectNodes(cdp, a, b) { const p = await waitFor(cdp, `(()=>{const s=document.querySelector('.react-flow__node[data-id=${JSON.stringify(a)}] .react-flow__handle.source'),t=document.querySelector('.react-flow__node[data-id=${JSON.stringify(b)}] .react-flow__handle.target');if(!s||!t)return null;const x=s.getBoundingClientRect(),y=t.getBoundingClientRect();return{a:{x:x.x+x.width/2,y:x.y+x.height/2},b:{x:y.x+y.width/2,y:y.y+y.height/2}}})()`, 'handles'); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p.a, button: 'left', buttons: 1 }); for(let i=1;i<=10;i++) await cdp.command('Input.dispatchMouseEvent', { type:'mouseMoved', x:p.a.x+(p.b.x-p.a.x)*i/10, y:p.a.y+(p.b.y-p.a.y)*i/10, button:'left', buttons:1 }); await cdp.command('Input.dispatchMouseEvent', { type:'mouseReleased', ...p.b, button:'left' }); await wait(100) }
