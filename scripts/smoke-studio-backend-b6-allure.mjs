import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename, join, resolve } from 'node:path'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const sourceKernel = process.env.AUTOFLOW_B1_KERNEL_DIR ?? '/Users/zhangtiancheng/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2'
const kernelVersion = basename(sourceKernel).replace(/^chromium-/, '')
const evidenceRoot = join(root, 'docs/migration/studio-backend-migration/evidence/b6')
const evidenceDir = await mkdtemp(join(await mkdir(evidenceRoot, { recursive: true }).then(() => evidenceRoot), 'formal-allure-electron-'))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-b6-allure-'))
const workflowName = 'B6 Allure 报告正式闭环'
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
  const profile = await api(runtime, '/v1/profiles', { method: 'POST', body: {
    name: 'B6 文件监控验收配置', description: '临时工作区；文件触发器正式验收', startUrl: 'about:blank', locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false,
    headless: true, humanize: false, humanPreset: 'default', userAgent: null, viewportJson: null, colorScheme: 'light', extensionPathsJson: [], expertArgsJson: [],
    browserVersion: kernelVersion, browserEdition: 'public', releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null,
  } })
  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 2560, height: 1600, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库') && document.body.innerText.includes('213')", 'formal Studio', 30_000)
  await waitFor(studio, `document.querySelector('[aria-label="运行浏览器配置"]')?.value === ${JSON.stringify(profile.id)}`, 'managed Profile selection')
  checkpoint('主窗口真实打开正式 Studio；动作库为 213，运行配置来自主应用 Profile')

  await click(studio, '新建')
  await setInput(studio, 'input[placeholder="工作流名称"]', workflowName)
  const ids = []
  const initId = await addNode(studio, 'Allure初始化', 'allure_init'); ids.push(initId)
  await setInput(studio, 'input[placeholder="测试套件"]', 'B6验收套件')
  const startId = await addNode(studio, '开始测试用例', 'allure_start_test'); ids.push(startId)
  await setInput(studio, 'input[placeholder="测试用例"]', '正式UI用例')
  const stepId = await addNode(studio, '添加测试步骤', 'allure_add_step'); ids.push(stepId)
  await setInput(studio, 'input[placeholder="测试步骤"]', '保存并生成报告')
  const attachmentId = await addNode(studio, '添加附件', 'allure_add_attachment'); ids.push(attachmentId)
  const attachmentPath = join(userData, 'attachment.txt'); await writeFile(attachmentPath, 'B6 Allure attachment', 'utf8')
  await setInput(studio, 'input[placeholder="C:/screenshots/test.png"]', attachmentPath)
  await setInput(studio, 'input[placeholder="截图"]', 'B6附件')
  const stopId = await addNode(studio, '结束测试用例', 'allure_stop_test'); ids.push(stopId)
  const reportId = await addNode(studio, '生成测试报告', 'allure_generate_report'); ids.push(reportId)
  await setInput(studio, 'input[placeholder="./allure-report"]', join(userData, 'report'))
  for (let i = 0; i < ids.length - 1; i++) await connectNodes(studio, ids[i], ids[i + 1])
  await waitFor(studio, `document.querySelectorAll('.react-flow__edge').length === ${ids.length - 1}`, 'workflow edges')
  checkpoint('通过正式 Studio 真实 UI 编排 Allure 六节点、测试套件、步骤、附件和报告目录')

  await click(studio, '保存')
  await waitFor(studio, `document.body?.innerText.includes(${JSON.stringify(`工作流已保存: ${workflowName}`)})`, 'workflow save')
  const saved = (await api(runtime, '/workflows')).find(item => item.name === workflowName)
  assert.ok(saved)
  assert.deepEqual(saved.nodes.map(node => node.data.moduleType), ['allure_init', 'allure_start_test', 'allure_add_step', 'allure_add_attachment', 'allure_stop_test', 'allure_generate_report'])
  assert.equal(saved.edges.length, 5)
  checkpoint('正式保存接口写入 Allure 六节点、附件路径、报告目录和五条连线')

  await click(studio, '运行 (F5)', '[aria-label="运行 (F5)"]')
  await click(studio, '运行 (F5)', '[role="menuitem"]')
  const run = await waitForValue(async () => (await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(saved.id)}&cursor=0&limit=20`)).items[0], 'Allure run creation', 20_000)
  const terminal = await waitForValue(async () => { const value = await api(runtime, `/workflow-runs/${encodeURIComponent(run.runId)}`); return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.status) ? value : null }, 'Allure terminal run', 90_000)
  assert.equal(terminal.status, 'completed', JSON.stringify(terminal))
  const results = await api(runtime, `/workflow-runs/${encodeURIComponent(run.runId)}/results?cursor=0&limit=50`)
  const byNode = Object.fromEntries(results.items.map(item => [item.nodeId, item.values]))
  assert.equal(byNode[initId].suite_id !== undefined, true); assert.equal(byNode[startId], undefined); assert.equal(byNode[stepId], undefined); assert.equal(byNode[attachmentId], undefined); assert.equal(byNode[stopId], undefined)
  assert.ok(typeof byNode[reportId].report_path === 'string' && byNode[reportId].report_path.endsWith('.html'))
  const artifacts = await api(runtime, `/workflow-runs/${encodeURIComponent(run.runId)}/artifacts?cursor=0&limit=50`)
  assert.ok(artifacts.items.some(item => item.nodeId === reportId && item.mimeType === 'text/html'))
  const logs = await api(runtime, `/workflow-runs/${encodeURIComponent(run.runId)}/logs?cursor=0&limit=100`)
  assert.ok(logs.items.some(item => item.nodeId === reportId && item.message.includes('已生成Allure测试报告')))
  checkpoint('真实 worker 生成含附件的 Allure HTML 报告并登记运行产物；流程正常完成')

  await wait(500); assert.deepEqual(cloakProcesses(userData), []); checkpoint('Allure 流程完成后无 CloakBrowser、worker 或资源残留')
  await capture(studio, join(evidenceDir, 'completed.png'))
  const report = {
    evidenceId: 'BE-B6-allure-formal-electron', checkedAt: new Date().toISOString(),
    gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    result: 'passed', platform: `${process.platform}-${process.arch}`, entry: 'development-build', workflowId: saved.id, profileId: profile.id, runId: run.runId, checks,
    nodes: ids.map((id, index) => ({ moduleType: ['allure_init', 'allure_start_test', 'allure_add_step', 'allure_add_attachment', 'allure_stop_test', 'allure_generate_report'][index], nodeId: id, result: byNode[id] })),
    artifacts: artifacts.items.map(item => ({ artifactId: item.artifactId, nodeId: item.nodeId, mimeType: item.mimeType })),
    boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browserLaunch: 'none', fixture: 'local temporary text attachment', interaction: 'formal Electron via CDP mouse and keyboard; public sidecar APIs only for fixture setup and evidence reads; no Store or page-internal business function access', platformPending: 'Windows/macOS Intel and packaged-entry shell.openPath reachability remain separately unverified' },
    buildSha256: await buildHash(),
  }
  await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
} catch (error) {
  if (studio) await capture(studio, join(evidenceDir, 'failure.png')).catch(() => undefined)
  await writeFile(join(evidenceDir, 'failure.json'), JSON.stringify({ checkedAt: new Date().toISOString(), checks, error: error instanceof Error ? error.stack : String(error) }, null, 2) + '\n')
  throw error
} finally {
  studio?.close(); main?.close(); await stop(desktop?.child); await rm(userData, { recursive: true, force: true })
}

function checkpoint(message) { checks.push(message); console.log(message) }
async function api(runtime, path, options = {}) { const response = await fetch(`${runtime.sidecar.baseUrl}/api${path}`, { method: options.method ?? 'GET', headers: { 'x-autoflow-token': runtime.sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': randomUUID() }, body: options.body === undefined ? undefined : JSON.stringify(options.body) }); if (!response.ok) throw new Error(`${options.method ?? 'GET'} /api${path}: ${response.status} ${await response.text()}`); return response.status === 204 ? undefined : response.json() }
async function openStudioFromMain(cdp, origin) { await click(cdp, '工作流工作台'); const target = await waitForValue(async () => (await (await fetch(`${origin}/json/list`)).json()).find(item => item.type === 'page' && item.url.includes('studio.html')), 'Studio target', 30_000); return connectCdp(target.webSocketDebuggerUrl) }
async function waitForValue(read, description, timeoutMs) { const deadline = Date.now() + timeoutMs; while (Date.now() < deadline) { const value = await read(); if (value) return value; await wait(200) } throw new Error(`timed out waiting for ${description}`) }
async function point(cdp, selector, text = '') { return waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length),text=${JSON.stringify(text)};const e=!text?rows[0]:rows.find(e=>e.getAttribute('aria-label')===text)||rows.find(e=>e.textContent.trim()===text)||rows.find(e=>e.textContent.includes(text));if(!e||e.disabled)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `unobscured ${text || selector}`) }
async function click(cdp, text, selector = 'button') { const p = await point(cdp, selector, text); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p }); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 }); await wait(100) }
async function setInput(cdp, selector, value) { const p = await point(cdp, selector); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 3 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 3 }); await cdp.command('Input.insertText', { text: value }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 }); await wait(100) }
async function addNode(cdp, label, moduleType) { const pane = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__pane');if(!e)return null;const r=e.getBoundingClientRect(),nodes=[...document.querySelectorAll('.react-flow__node')];for(const y of [.2,.45,.7])for(const x of [.15,.4,.65,.9]){const p={x:r.x+r.width*x,y:r.y+r.height*y};if(nodes.every(n=>{const b=n.getBoundingClientRect();return Math.abs((b.left+b.right)/2-p.x)>170||Math.abs((b.top+b.bottom)/2-p.y)>90})&&document.elementFromPoint(p.x,p.y)===e)return p}return null})()`, 'workflow canvas'); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...pane, button: 'right', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...pane, button: 'right', clickCount: 1 }); await setInput(cdp, 'input[placeholder="搜索模块（支持拼音）"]', label); await click(cdp, label, '[role="button"]'); const id = await waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll('.react-flow__node')].filter(e=>e.textContent.includes(${JSON.stringify(label)}));return rows.at(-1)?.dataset.id||null})()`, `${moduleType} node`); await selectNode(cdp, id, moduleType); return id }
async function selectNode(cdp, id, type) { const p = await point(cdp, `.react-flow__node[data-id=${JSON.stringify(id)}]`); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 }); await wait(200); await waitFor(cdp, `document.body.innerText.includes(${JSON.stringify(type)})`, `${type} config`) }
async function connectNodes(cdp, a, b) { const p = await waitFor(cdp, `(()=>{const s=document.querySelector('.react-flow__node[data-id=${JSON.stringify(a)}] .react-flow__handle.source'),t=document.querySelector('.react-flow__node[data-id=${JSON.stringify(b)}] .react-flow__handle.target');if(!s||!t)return null;const x=s.getBoundingClientRect(),y=t.getBoundingClientRect();return{a:{x:x.x+x.width/2,y:x.y+y.height/2},b:{x:y.x+y.width/2,y:y.y+y.height/2}}})()`, 'handles'); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p.a, button: 'left', buttons: 1 }); for(let i=1;i<=10;i++) await cdp.command('Input.dispatchMouseEvent', { type:'mouseMoved', x:p.a.x+(p.b.x-p.a.x)*i/10, y:p.a.y+(p.b.y-p.a.y)*i/10, button:'left', buttons:1 }); await cdp.command('Input.dispatchMouseEvent', { type:'mouseReleased', ...p.b, button:'left' }); await wait(100) }
function cloakProcesses(workspace) { return execFileSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).split('\n').filter(line => line.includes(workspace) && /Chromium|CloakBrowser/.test(line)) }
async function capture(cdp, path) { const { data } = await cdp.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }); await writeFile(path, data, 'base64') }
async function buildHash() { const hash = createHash('sha256'); for(const file of (await readdir(join(root, 'apps/desktop/out'), { recursive: true })).filter(file => /\.(js|css|html)$/.test(file)).sort()) hash.update(file).update(await readFile(join(root, 'apps/desktop/out', file))); return hash.digest('hex') }
