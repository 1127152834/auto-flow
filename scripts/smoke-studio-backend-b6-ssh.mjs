import assert from 'node:assert/strict'
import { execFileSync, spawn } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename, join, resolve } from 'node:path'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const sourceKernel = process.env.AUTOFLOW_B1_KERNEL_DIR ?? '/Users/zhangtiancheng/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2'
const evidenceRoot = join(root, 'docs/migration/studio-backend-migration/evidence/b6')
await mkdir(evidenceRoot, { recursive: true })
const evidenceDir = await mkdtemp(join(evidenceRoot, 'formal-ssh-electron-'))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-b6-ssh-'))
const statusPath = join(userData, 'ssh-status.json')
const uploadPath = join(userData, 'upload.bin')
const downloadPath = join(userData, 'download.bin')
const content = Buffer.from(`SSH真实文件往返\n${randomUUID()}\n`)
const workflowName = 'B6 SSH 五节点正式闭环'
const types = ['ssh_connect', 'ssh_execute_command', 'ssh_upload_file', 'ssh_download_file', 'ssh_disconnect']
const checks = []
let desktop, main, studio, fixture, native
let fixtureError = ''

try {
  await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
  await mkdir(join(userData, 'data/kernels'), { recursive: true })
  execFileSync('cp', ['-cR', sourceKernel, join(userData, 'data/kernels', basename(sourceKernel))])
  await writeFile(uploadPath, content)
  fixture = spawn(join(root, 'apps/backend/.venv/bin/python'), ['tests/integration/test_b6_ssh_worker.py', '--root', join(userData, 'remote-host'), '--status', statusPath], {
    cwd: join(root, 'apps/backend'), env: { ...process.env, PYTHONPATH: 'src' }, stdio: ['pipe', 'ignore', 'pipe'],
  })
  fixture.stderr.on('data', data => { fixtureError += data.toString() })
  const server = await waitForValue(async () => {
    if (fixture.exitCode !== null) throw new Error(`SSH fixture exited: ${fixtureError}`)
    return readFile(statusPath, 'utf8').then(JSON.parse).catch(() => null)
  }, 'loopback SSH server', 10_000)

  assert.equal(process.platform, 'darwin', 'This native-close UI script requires macOS; other platforms remain pending')
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'] })
  main = desktop.cdp
  native = await connectCdp(desktop.inspectorUrl)
  await native.evaluate("globalThis.qaElectron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');true")
  await main.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(main, "document.body?.innerText.includes('本地服务正常')", 'main readiness', 30_000)
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  const profile = await api(runtime, '/v1/profiles', { method: 'POST', body: {
    name: 'B6 SSH 专项临时配置', description: '本流程只访问回环 SSH 服务，不启动浏览器', startUrl: 'about:blank', locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false,
    headless: true, humanize: false, humanPreset: 'default', userAgent: null, viewportJson: null, colorScheme: 'light', extensionPathsJson: [], expertArgsJson: [],
    browserVersion: basename(sourceKernel).replace(/^chromium-/, ''), browserEdition: 'public', releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null,
  } })
  await click(main, '工作流工作台')
  const target = await waitForValue(async () => (await (await fetch(`${desktop.debugOrigin}/json/list`)).json()).find(t => t.type === 'page' && t.url.includes('studio.html')), 'Studio target', 30_000)
  studio = await connectCdp(target.webSocketDebuggerUrl)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 2560, height: 1600, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库') && document.body.innerText.includes('213')", 'Studio scope', 30_000)
  await waitFor(studio, `document.querySelector('[aria-label="运行浏览器配置"]')?.value === ${JSON.stringify(profile.id)}`, 'main Profile')
  checkpoint('主窗口真实点击进入 Studio；213 节点范围及主应用 Profile 就绪')
  await click(studio, '新建')
  await setInput(studio, 'input[placeholder="工作流名称"]', workflowName)
  const ids = []
  ids.push(await addNode(studio, 'SSH连接', types[0]))
  await setInput(studio, 'input[placeholder="192.168.1.100"]', '127.0.0.1')
  await setInput(studio, 'input[inputmode="numeric"]', String(server.port))
  await setInput(studio, 'input[placeholder="root"]', 'tester')
  await setInput(studio, 'input[placeholder="请输入密码（或使用密钥文件）"]', 'secret')
  ids.push(await addNode(studio, 'SSH执行命令', types[1]))
  await setInput(studio, 'textarea[placeholder="ls -la"]', 'printf ok')
  ids.push(await addNode(studio, 'SSH上传文件', types[2]))
  await setInput(studio, 'input[placeholder="C:/data/file.txt"]', uploadPath)
  await setInput(studio, 'input[placeholder="/home/user/file.txt"]', '/remote/roundtrip.bin')
  ids.push(await addNode(studio, 'SSH下载文件', types[3]))
  await setInput(studio, 'input[placeholder="/home/user/file.txt"]', '/remote/roundtrip.bin')
  await setInput(studio, 'input[placeholder="C:/data/file.txt"]', downloadPath)
  ids.push(await addNode(studio, 'SSH断开连接', types[4]))
  for (let index = 0; index < ids.length - 1; index++) await connectNodes(studio, ids[index], ids[index + 1])
  await waitFor(studio, "document.querySelectorAll('.react-flow__edge').length === 4", 'four SSH edges')
  await click(studio, '保存')
  await waitFor(studio, `document.body.innerText.includes(${JSON.stringify(`工作流已保存: ${workflowName}`)})`, 'save')
  const saved = (await api(runtime, '/workflows')).find(item => item.name === workflowName)
  assert.ok(saved)
  assert.deepEqual(saved.nodes.map(n => n.data.moduleType), types)
  assert.equal(saved.nodes[0].data.port, server.port)
  checkpoint('五节点通过画布添加、真实输入、四条手柄连线和保存完成；没有 API 注入流程')

  assert.equal(await native.evaluate("(()=>{const w=qaElectron.BrowserWindow.getAllWindows().find(w=>w.getTitle().includes('工作流工作台'));if(!w)return false;qaElectron.app.focus({steal:true});w.show();w.focus();return true})()"), true)
  await wait(250)
  execFileSync('osascript', ['-e', 'tell application "System Events"', '-e', `tell (first application process whose unix id is ${desktop.child.pid})`, '-e', 'click (first button of (first window whose name contains "工作流工作台") whose subrole is "AXCloseButton")', '-e', 'end tell', '-e', 'end tell'])
  await waitForValue(async () => !(await (await fetch(`${desktop.debugOrigin}/json/list`)).json()).some(t => t.type === 'page' && t.url.includes('studio.html')), 'native Studio close', 15_000)
  studio.close()
  await click(main, '工作流工作台')
  const reopened = await waitForValue(async () => (await (await fetch(`${desktop.debugOrigin}/json/list`)).json()).find(t => t.type === 'page' && t.url.includes('studio.html')), 'reopened Studio', 30_000)
  studio = await connectCdp(reopened.webSocketDebuggerUrl)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 2560, height: 1600, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库')", 'reopened editor', 30_000)
  if (!await studio.evaluate(`document.querySelector('input[placeholder="工作流名称"]')?.value === ${JSON.stringify(workflowName)} && document.querySelectorAll('.react-flow__node').length === 5`)) {
    await click(studio, '打开')
    await click(studio, `打开工作流 ${workflowName}`, '[role="button"]')
  }
  await waitFor(studio, "document.querySelectorAll('.react-flow__node').length === 5 && document.querySelectorAll('.react-flow__edge').length === 4", 'persisted five nodes')
  checkpoint('真实点击原生关闭按钮后重开 Studio，从持久文档恢复五节点和四条连线')

  await click(studio, '运行 (F5)', '[aria-label="运行 (F5)"]')
  await click(studio, '运行 (F5)', '[role="menuitem"]')
  const run = await waitForValue(async () => (await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(saved.id)}&cursor=0&limit=20`)).items[0], 'run', 20_000)
  const terminal = await waitForValue(async () => {
    const current = await api(runtime, `/workflow-runs/${run.runId}`)
    return ['completed', 'failed', 'stopped', 'interrupted'].includes(current.status) ? current : null
  }, 'SSH completion', 60_000)
  assert.equal(terminal.status, 'completed', JSON.stringify(terminal))
  const results = await api(runtime, `/workflow-runs/${run.runId}/results?cursor=0&limit=20`)
  const command = results.items.find(item => item.nodeId === ids[1])
  assert.deepEqual(command.values, { output: 'ok\n', error: '', exit_code: 0 })
  assert.deepEqual(await readFile(join(userData, 'remote-host/remote/roundtrip.bin')), content)
  assert.deepEqual(await readFile(downloadPath), content)
  const logs = await api(runtime, `/workflow-runs/${run.runId}/logs?cursor=0&limit=100`)
  for (const id of ids) assert.ok(logs.items.some(item => item.nodeId === id), `missing logs: ${id}`)
  assert.ok(!JSON.stringify(logs).includes('secret'))
  const serverFinal = await waitForValue(async () => {
    const value = JSON.parse(await readFile(statusPath, 'utf8'))
    return value.connections === 1 && value.activeConnections === 0 && value.commands.length === 1 && value.commands[0] === 0 ? value : null
  }, 'SSH disconnect and command process cleanup', 10_000)
  const processes = execFileSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).split('\n').filter(line => line.includes(userData) && /Chromium|CloakBrowser|autoflow\.providers\.browser\.workflow_worker/.test(line))
  assert.deepEqual(processes, [])
  checkpoint('真实独立 worker 完成 SSH 握手、命令子进程、磁盘 SFTP 往返和断开；日志持久化且连接已清理')
  await capture(studio, join(evidenceDir, 'completed.png'))
  const report = {
    evidenceId: 'BE-B6-ssh-formal-electron', checkedAt: new Date().toISOString(), result: 'passed',
    gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    platform: `${process.platform}-${process.arch}`, entry: desktop.packaged ? 'packaged' : 'development-build',
    workflowId: saved.id, runId: run.runId, profileId: profile.id, checks, server: serverFinal,
    nodes: types.map((moduleType, index) => ({ moduleType, nodeId: ids[index] })), commandResult: command.values,
    file: { bytes: content.length, sha256: createHash('sha256').update(content).digest('hex') }, buildSha256: await buildHash(),
    boundaries: { userDatabaseTouched: false, workspace: 'ephemeral', server: 'real loopback SSH/SFTP with temporary disk files and allowlisted command subprocess', interaction: 'CDP clicks/typing/edge drag; APIs only Profile fixture creation and evidence reads; no Store writes', pending: 'Electron failure/stop variants, Windows, macOS Intel; backend failure/stop evidence lives in test_b6_ssh_worker.py' },
  }
  await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
} catch (error) {
  if (studio) await capture(studio, join(evidenceDir, 'failure.png')).catch(() => undefined)
  await writeFile(join(evidenceDir, 'failure.json'), JSON.stringify({ checkedAt: new Date().toISOString(), checks, fixtureError, error: error instanceof Error ? error.stack : String(error) }, null, 2) + '\n')
  throw error
} finally {
  studio?.close(); main?.close(); native?.close(); await stop(desktop?.child)
  fixture?.stdin.end(); await stop(fixture)
  await rm(userData, { recursive: true, force: true })
}

function checkpoint(message) { checks.push(message); console.log(message) }
async function api(runtime, path, options = {}) { const response = await fetch(`${runtime.sidecar.baseUrl}/api${path}`, { method: options.method ?? 'GET', headers: { 'x-autoflow-token': runtime.sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': randomUUID() }, body: options.body === undefined ? undefined : JSON.stringify(options.body) }); if (!response.ok) throw new Error(`${options.method ?? 'GET'} /api${path}: ${response.status} ${await response.text()}`); return response.status === 204 ? undefined : response.json() }
async function waitForValue(read, description, timeoutMs) { const deadline = Date.now() + timeoutMs; while (Date.now() < deadline) { const value = await read(); if (value) return value; await wait(200) } throw new Error(`timed out waiting for ${description}`) }
async function point(cdp, selector, text = '') { return waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length),text=${JSON.stringify(text)};const e=!text?rows[0]:rows.find(e=>e.getAttribute('aria-label')===text)||rows.find(e=>e.textContent.trim()===text)||rows.find(e=>e.textContent.includes(text));if(!e||e.disabled)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `unobscured ${text || selector}`) }
async function click(cdp, text, selector = 'button') { const p = await point(cdp, selector, text); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p }); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 }); await wait(100) }
async function setInput(cdp, selector, value) { const p = await point(cdp, selector); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 3 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 3 }); await cdp.command('Input.insertText', { text: value }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 }); await wait(100) }
async function addNode(cdp, label, moduleType) { const pane = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__pane');if(!e)return null;const r=e.getBoundingClientRect(),nodes=[...document.querySelectorAll('.react-flow__node')];for(const y of [.2,.45,.7])for(const x of [.15,.4,.65,.9]){const p={x:r.x+r.width*x,y:r.y+r.height*y};if(nodes.every(n=>{const b=n.getBoundingClientRect();return Math.abs((b.left+b.right)/2-p.x)>170||Math.abs((b.top+b.bottom)/2-p.y)>90})&&document.elementFromPoint(p.x,p.y)===e)return p}return null})()`, 'workflow canvas'); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...pane, button: 'right', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...pane, button: 'right', clickCount: 1 }); await setInput(cdp, 'input[placeholder="搜索模块（支持拼音）"]', label); await click(cdp, label, '[role="button"]'); const id = await waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll('.react-flow__node')].filter(e=>e.textContent.includes(${JSON.stringify(label)}));return rows.at(-1)?.dataset.id||null})()`, `${moduleType} node`); await click(cdp, '', `.react-flow__node[data-id=${JSON.stringify(id)}]`); await waitFor(cdp, `document.body.innerText.includes(${JSON.stringify(moduleType)})`, 'node configuration'); return id }
async function connectNodes(cdp, a, b) { const p = await waitFor(cdp, `(()=>{const s=document.querySelector('.react-flow__node[data-id=${JSON.stringify(a)}] .react-flow__handle.source'),t=document.querySelector('.react-flow__node[data-id=${JSON.stringify(b)}] .react-flow__handle.target');if(!s||!t)return null;const x=s.getBoundingClientRect(),y=t.getBoundingClientRect();return{a:{x:x.x+x.width/2,y:x.y+x.height/2},b:{x:y.x+y.width/2,y:y.y+y.height/2}}})()`, 'handles'); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p.a, button: 'left', buttons: 1 }); for(let i=1;i<=10;i++) await cdp.command('Input.dispatchMouseEvent', { type:'mouseMoved', x:p.a.x+(p.b.x-p.a.x)*i/10, y:p.a.y+(p.b.y-p.a.y)*i/10, button:'left', buttons:1 }); await cdp.command('Input.dispatchMouseEvent', { type:'mouseReleased', ...p.b, button:'left' }); await wait(100) }
async function capture(cdp, path) { const { data } = await cdp.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }); await writeFile(path, data, 'base64') }
async function buildHash() { const hash = createHash('sha256'); for(const file of (await readdir(join(root, 'apps/desktop/out'), { recursive: true })).filter(file => /\.(js|css|html)$/.test(file)).sort()) hash.update(file).update(await readFile(join(root, 'apps/desktop/out', file))); return hash.digest('hex') }
