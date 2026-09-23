import assert from 'node:assert/strict'
import { execFileSync, spawn } from 'node:child_process'
import { randomUUID } from 'node:crypto'
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename, delimiter, join, resolve } from 'node:path'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const sourceKernel = process.env.AUTOFLOW_B1_KERNEL_DIR ?? '/Users/zhangtiancheng/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2'
const evidenceRoot = join(root, 'docs/migration/studio-backend-migration/evidence/b6')
await mkdir(evidenceRoot, { recursive: true })
const evidenceDir = await mkdtemp(join(evidenceRoot, 'formal-mail-electron-'))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-b6-mail-'))
const fixtureStatus = join(userData, 'mail-status.json')
const checks = []
let desktop, main, studio, fixture
let fixtureError = ''

try {
  await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
  await mkdir(join(userData, 'data/kernels'), { recursive: true })
  await mkdir(join(userData, 'mail-fixture'))
  execFileSync('cp', ['-cR', sourceKernel, join(userData, 'data/kernels', basename(sourceKernel))])
  fixture = spawn(join(root, 'apps/backend/.venv/bin/python'), [join(root, 'scripts/fixtures/studio-mail-server.py'), join(userData, 'mail-fixture'), fixtureStatus], {
    cwd: join(root, 'apps/backend'), env: { ...process.env, PYTHONPATH: [join(root, 'apps/backend/tests/integration'), join(root, 'apps/backend/src')].join(delimiter) }, stdio: ['ignore', 'ignore', 'pipe'],
  })
  fixture.stderr.on('data', chunk => { fixtureError += chunk.toString() })
  const server = await waitForValue(async () => {
    if (fixture.exitCode !== null) throw new Error(`邮件服务退出: ${fixtureError}`)
    return readFile(fixtureStatus, 'utf8').then(JSON.parse).catch(() => null)
  }, 'real loopback TLS SMTP/IMAP', 10_000)
  const sitecustomize = `import os,socket\n_original=socket.create_connection\ndef _local(address,*args,**kwargs):\n    if address==('smtp.qq.com',465): address=('127.0.0.1',int(os.environ['AUTOFLOW_MAIL_TEST_PORT']))\n    return _original(address,*args,**kwargs)\nsocket.create_connection=_local\n`
  await writeFile(join(userData, 'sitecustomize.py'), sitecustomize)
  process.env.AUTOFLOW_MAIL_TEST_PORT = String(server.smtpPort)
  process.env.PYTHONPATH = [userData, join(root, 'apps/backend/src'), process.env.PYTHONPATH].filter(Boolean).join(delimiter)

  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'] })
  main = desktop.cdp
  await main.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(main, "document.body?.innerText.includes('本地服务正常')", 'main readiness', 30_000)
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  const profile = await api(runtime, '/v1/profiles', { method: 'POST', body: {
    name: 'B6 邮件临时配置', description: '真实本地 TLS 邮件服务，不启动浏览器', startUrl: 'about:blank', locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false,
    headless: true, humanize: false, humanPreset: 'default', userAgent: null, viewportJson: null, colorScheme: 'light', extensionPathsJson: [], expertArgsJson: [],
    browserVersion: basename(sourceKernel).replace(/^chromium-/, ''), browserEdition: 'public', releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null,
  } })
  await click(main, '工作流工作台')
  const target = await waitForValue(async () => (await (await fetch(`${desktop.debugOrigin}/json/list`)).json()).find(t => t.type === 'page' && t.url.includes('studio.html')), 'Studio target', 30_000)
  studio = await connectCdp(target.webSocketDebuggerUrl)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 2560, height: 1600, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库') && document.body.innerText.includes('213')", 'approved scope', 30_000)
  await waitFor(studio, `document.querySelector('[aria-label="运行浏览器配置"]')?.value === ${JSON.stringify(profile.id)}`, 'main Profile')
  checks.push('主窗口真实点击打开 Studio；213 节点和主应用 Profile 已核对')

  const send = await createFlow('B6 真实 TLS 发邮件正式闭环', '发送邮件', 'send_email', [
    ['input[placeholder="your@qq.com，支持 {变量名}"]', 'sender@qq.com'],
    ['input[placeholder="邮箱SMTP授权码，支持 {变量名}"]', 'fixture-secret'],
    ['input[placeholder="recipient@example.com，支持 {变量名}"]', 'recipient@example.test'],
    ['input[placeholder="邮件标题，支持 {变量名}"]', '中文主题'],
    ['textarea[placeholder="邮件正文，支持 {变量名}"]', '正文第一行\n.正文第二行'],
  ])
  const sent = await runFlow(send)
  assert.equal(sent.status, 'completed', JSON.stringify(sent))
  const sentResults = await api(runtime, `/workflow-runs/${sent.runId}/results?cursor=0&limit=20`)
  assert.ok(sentResults.items.some(item => item.nodeId === send.nodeId && JSON.stringify(item.values).includes('recipient@example.test')))
  const delivery = await waitForValue(async () => {
    const value = JSON.parse(await readFile(fixtureStatus, 'utf8'))
    return value.messages.length === 1 && value.smtpDisconnected ? value : null
  }, 'SMTP DATA and QUIT', 10_000)
  const mime = Buffer.from(delivery.messages[0], 'base64').toString('utf8')
  assert.match(mime, /Subject: =\?utf-8\?/i)
  assert.match(mime, /recipient@example\.test/)
  assert.match(mime, /\.正文第二行/)
  assert.deepEqual(delivery.errors, [])
  checks.push('正式 Studio 发送节点使用生产 smtplib，通过真实 TLS SMTP 完成认证、MIME 正文和断开；日志未泄露授权码')

  const receive = await createFlow('B6 真实 TLS 收邮件正式闭环', '邮件触发器', 'email_trigger', [
    ['input[placeholder="如: imap.qq.com"]', '127.0.0.1'],
    ['input#emailPort', String(server.imapPort)],
    ['input[placeholder="如: your@email.com"]', 'reader@example.test'],
    ['input[placeholder="邮箱密码或授权码"]', 'fixture-secret'],
    ['input[placeholder="如: sender@example.com"]', 'sender@'],
    ['input[placeholder="如: 订单通知"]', '完成'],
    ['input#timeout', '8'],
    ['input[placeholder="如: email_data"]', 'mail'],
  ])
  const received = await runFlow(receive)
  assert.equal(received.status, 'completed', JSON.stringify(received))
  const receivedResults = await api(runtime, `/workflow-runs/${received.runId}/results?cursor=0&limit=20`)
  assert.ok(receivedResults.items.some(item => item.nodeId === receive.nodeId && JSON.stringify(item.values).includes('订单完成 4')))
  const inbox = JSON.parse(await readFile(fixtureStatus, 'utf8'))
  assert.equal(inbox.imapDisconnected, true)
  assert.deepEqual(inbox.imapFlags, ['3 +FLAGS (\\Seen)', '4 +FLAGS (\\Seen)'])
  assert.deepEqual(inbox.errors, [])
  checks.push('正式 Studio 邮件触发器从真实 TLS IMAP 筛选两封，标记已读并在独立 worker 结束前关闭连接')

  const report = { evidenceId: 'BE-B6-mail-formal-electron', checkedAt: new Date().toISOString(), result: 'passed',
    gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    platform: `${process.platform}-${process.arch}`, entry: desktop.packaged ? 'packaged' : 'development-build',
    workflows: [send, receive], runs: [sent.runId, received.runId], profileId: profile.id, checks,
    transport: { smtpCommands: delivery.smtpCommands, imapCommands: inbox.imapCommands, flags: inbox.imapFlags, mimeBytes: Buffer.byteLength(mime) },
    boundaries: { userDatabaseTouched: false, workspace: 'ephemeral', realTransport: 'loopback TLS SMTP/IMAP; production executors and stdlib clients unchanged', outsideProviderDelivery: 'not tested', platformPending: 'macOS Intel, Windows, frozen package' },
  }
  await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
} catch (error) {
  const visibleText = studio ? await studio.evaluate('document.body?.innerText').catch(() => '') : ''
  await writeFile(join(evidenceDir, 'failure.json'), JSON.stringify({ checkedAt: new Date().toISOString(), checks, visibleText, fixtureError, error: error instanceof Error ? error.stack : String(error) }, null, 2) + '\n')
  throw error
} finally {
  studio?.close(); main?.close(); await stop(desktop?.child); await stop(fixture)
  await rm(userData, { recursive: true, force: true })
}

async function createFlow(name, label, type, fields) {
  await click(studio, '新建')
  await setInput(studio, 'input[placeholder="工作流名称"]', name)
  const id = await addNode(studio, label, type)
  for (const [selector, value] of fields) await setInput(studio, selector, value)
  await click(studio, '保存')
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  const saved = await waitForValue(async () => (await api(runtime, '/workflows')).find(item => item.name === name), 'saved workflow', 20_000)
  assert.equal(saved.nodes.length, 1)
  assert.equal(saved.nodes[0].data.moduleType, type)
  await click(studio, '新建')
  await click(studio, '打开')
  await click(studio, `打开工作流 ${name}`, '[role="button"]')
  await waitFor(studio, "document.querySelectorAll('.react-flow__node').length === 1", 'reopened node')
  checks.push(`${name}：真实 UI 配置、保存、切换、重开并从 SQLite 恢复`)
  return { workflowId: saved.id, name, nodeId: id, type }
}
async function runFlow(flow) {
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  await click(studio, '运行 (F5)', '[aria-label="运行 (F5)"]')
  await click(studio, '运行 (F5)', '[role="menuitem"]')
  const run = await waitForValue(async () => (await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(flow.workflowId)}&cursor=0&limit=20`)).items[0], 'run', 20_000)
  const done = await waitForValue(async () => { const value = await api(runtime, `/workflow-runs/${run.runId}`); return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.status) ? value : null }, 'run completion', 60_000)
  const logs = await api(runtime, `/workflow-runs/${run.runId}/logs?cursor=0&limit=100`)
  assert.ok(logs.items.some(item => item.nodeId === flow.nodeId))
  assert.ok(!JSON.stringify(logs).includes('fixture-secret'))
  return { runId: run.runId, status: done.status, error: done.error }
}
async function api(runtime, path, options = {}) { const response = await fetch(`${runtime.sidecar.baseUrl}/api${path}`, { method: options.method ?? 'GET', headers: { 'x-autoflow-token': runtime.sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': randomUUID() }, body: options.body === undefined ? undefined : JSON.stringify(options.body) }); if (!response.ok) throw new Error(`${options.method ?? 'GET'} /api${path}: ${response.status} ${await response.text()}`); return response.status === 204 ? undefined : response.json() }
async function waitForValue(read, description, timeoutMs) { const deadline = Date.now() + timeoutMs; while (Date.now() < deadline) { const value = await read(); if (value) return value; await wait(200) } throw new Error(`timed out waiting for ${description}`) }
async function point(cdp, selector, text = '') { return waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length),text=${JSON.stringify(text)};const e=!text?rows[0]:rows.find(e=>e.getAttribute('aria-label')===text)||rows.find(e=>e.textContent.trim()===text)||rows.find(e=>e.textContent.includes(text));if(!e||e.disabled)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `unobscured ${text || selector}`) }
async function click(cdp, text, selector = 'button') { const p = await point(cdp, selector, text); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p }); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 }); await wait(100) }
async function setInput(cdp, selector, value) { const p = await point(cdp, selector); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 3 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 3 }); await cdp.command('Input.insertText', { text: value }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 }); await wait(100) }
async function addNode(cdp, label, moduleType) { const pane = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__pane');if(!e)return null;const r=e.getBoundingClientRect();for(const y of [.2,.45,.7])for(const x of [.15,.4,.65,.9]){const p={x:r.x+r.width*x,y:r.y+r.height*y};if(document.elementFromPoint(p.x,p.y)===e)return p}return null})()`, 'workflow canvas'); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...pane, button: 'right', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...pane, button: 'right', clickCount: 1 }); await setInput(cdp, 'input[placeholder="搜索模块（支持拼音）"]', label); await click(cdp, label, '[role="button"]'); const id = await waitFor(cdp, `document.querySelector('.react-flow__node')?.dataset.id`, `${moduleType} node`); await click(cdp, '', `.react-flow__node[data-id=${JSON.stringify(id)}]`); await waitFor(cdp, `document.body.innerText.includes(${JSON.stringify(moduleType)})`, 'node configuration'); return id }
