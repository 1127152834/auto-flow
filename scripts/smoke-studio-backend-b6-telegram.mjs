import assert from 'node:assert/strict'
import { execFile, execFileSync } from 'node:child_process'
import { randomUUID } from 'node:crypto'
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { createServer } from 'node:https'
import { tmpdir } from 'node:os'
import { basename, delimiter, join, resolve } from 'node:path'
import { promisify } from 'node:util'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const sourceKernel = process.env.AUTOFLOW_B1_KERNEL_DIR ?? '/Users/zhangtiancheng/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2'
const evidenceRoot = join(root, 'docs/migration/studio-backend-migration/evidence/b6')
await mkdir(evidenceRoot, { recursive: true })
const evidenceDir = await mkdtemp(join(evidenceRoot, 'formal-telegram-electron-'))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-b6-telegram-'))
const cert = join(userData, 'telegram-cert.pem')
const key = join(userData, 'telegram-key.pem')
const requests = []
const checks = []
let desktop, main, studio, server, report
let respondOk = true

try {
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1', '-subj', '/CN=api.telegram.org', '-addext', 'subjectAltName=DNS:api.telegram.org', '-keyout', key, '-out', cert], { stdio: 'ignore' })
  server = createServer({ key: await readFile(key), cert: await readFile(cert) }, async (request, response) => {
    const body = Buffer.concat(await Array.fromAsync(request)).toString('utf8')
    requests.push({ path: request.url, body: JSON.parse(body) })
    response.writeHead(200, { 'content-type': 'application/json' })
    response.end(JSON.stringify({ ok: respondOk, result: respondOk ? { message_id: requests.length } : undefined }))
  })
  await new Promise(resolveListen => server.listen(0, '127.0.0.1', resolveListen))
  const port = server.address().port
  const sitecustomize = `import anyio,os,ssl\n_connect=anyio.connect_tcp\nasync def _local(remote_host,remote_port,*args,**kwargs):\n    if remote_host=='api.telegram.org' and remote_port==443: remote_host,remote_port='127.0.0.1',int(os.environ['AUTOFLOW_TELEGRAM_TEST_PORT'])\n    return await _connect(remote_host,remote_port,*args,**kwargs)\nanyio.connect_tcp=_local\n_create_context=ssl.create_default_context\ndef _context(*args,**kwargs):\n    context=_create_context(*args,**kwargs)\n    context.load_verify_locations(cafile=os.environ['AUTOFLOW_TELEGRAM_TEST_CERT'])\n    return context\nssl.create_default_context=_context\n`
  await writeFile(join(userData, 'sitecustomize.py'), sitecustomize)
  process.env.AUTOFLOW_TELEGRAM_TEST_PORT = String(port)
  process.env.AUTOFLOW_TELEGRAM_TEST_CERT = cert
  process.env.PYTHONPATH = [userData, join(root, 'apps/backend/src'), process.env.PYTHONPATH].filter(Boolean).join(delimiter)
  const { stdout: probe } = await promisify(execFile)(join(root, 'apps/backend/.venv/bin/python'), ['-c', "import asyncio,httpx\nasync def main():\n async with httpx.AsyncClient(trust_env=False) as client:\n  response=await client.post('https://api.telegram.org/botprobe/sendMessage',json={'chat_id':'probe','text':'probe'})\n  print(response.status_code,response.json()['ok'])\nasyncio.run(main())"], { env: process.env, encoding: 'utf8' })
  assert.equal(probe.trim(), '200 True')
  assert.deepEqual(requests, [{ path: '/botprobe/sendMessage', body: { chat_id: 'probe', text: 'probe' } }])
  requests.length = 0
  await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
  await mkdir(join(userData, 'data/kernels'), { recursive: true })
  execFileSync('cp', ['-cR', sourceKernel, join(userData, 'data/kernels', basename(sourceKernel))])

  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'] })
  main = desktop.cdp
  await main.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(main, "document.body?.innerText.includes('本地服务正常')", 'main readiness', 30_000)
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  const profile = await api(runtime, '/v1/profiles', { method: 'POST', body: {
    name: 'B6 Telegram 临时配置', description: '本地 TLS Bot API', startUrl: 'about:blank', locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false,
    headless: true, humanize: false, humanPreset: 'default', userAgent: null, viewportJson: null, colorScheme: 'light', extensionPathsJson: [], expertArgsJson: [],
    browserVersion: basename(sourceKernel).replace(/^chromium-/, ''), browserEdition: 'public', releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null,
  } })
  await click(main, '工作流工作台')
  const target = await poll(async () => (await (await fetch(`${desktop.debugOrigin}/json/list`)).json()).find(item => item.type === 'page' && item.url.includes('studio.html')), 'Studio target')
  studio = await connectCdp(target.webSocketDebuggerUrl)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 2560, height: 1600, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库') && document.body.innerText.includes('213')", 'approved scope')
  await waitFor(studio, `document.querySelector('[aria-label="运行浏览器配置"]')?.value === ${JSON.stringify(profile.id)}`, 'main Profile')
  checks.push('主窗口真实打开 Studio，核对 213 节点与主应用 Profile')

  await click(studio, '新建')
  await setInput(studio, 'input[placeholder="工作流名称"]', 'B6 Telegram 受控 TLS 验收')
  const nodeId = await addNode(studio, 'Telegram通知', 'notify_telegram')
  await setInput(studio, 'input[placeholder="Telegram Bot Token"]', 'fixture-bot-token')
  await setInput(studio, 'input[placeholder="Telegram Chat ID"]', 'fixture-chat')
  await setInput(studio, 'textarea[placeholder="输入消息内容"]', '项目通知中文正文')
  await click(studio, '保存')
  const saved = await poll(async () => (await api(runtime, '/workflows')).find(item => item.name === 'B6 Telegram 受控 TLS 验收'), 'saved workflow')
  assert.equal(saved.nodes[0].data.moduleType, 'notify_telegram')
  await click(studio, '新建'); await click(studio, '打开')
  await click(studio, '打开工作流 B6 Telegram 受控 TLS 验收', '[role="button"]')
  await waitFor(studio, "document.querySelectorAll('.react-flow__node').length === 1", 'reopened node')
  checks.push('真实 UI 配置、保存、切换并从 SQLite 重开 Telegram 节点')

  const succeeded = await run(runtime, saved.id, new Set())
  assert.equal(succeeded.status, 'completed', JSON.stringify(succeeded))
  assert.deepEqual(requests, [{ path: '/botfixture-bot-token/sendMessage', body: { chat_id: 'fixture-chat', text: '项目通知中文正文' } }])
  const successLogs = await api(runtime, `/workflow-runs/${succeeded.runId}/logs?cursor=0&limit=100`)
  assert.ok(successLogs.items.some(item => item.nodeId === nodeId))
  assert.ok(!JSON.stringify(successLogs).includes('fixture-bot-token'))
  checks.push('生产 executor 经真实 httpx HTTPS 校验证书、发送 Bot API JSON 一次；节点日志不泄露 Token')

  respondOk = false
  const failed = await run(runtime, saved.id, new Set([succeeded.runId]))
  assert.equal(failed.status, 'failed', JSON.stringify(failed))
  assert.equal(requests.length, 2)
  const failureLogs = await api(runtime, `/workflow-runs/${failed.runId}/logs?cursor=0&limit=100`)
  assert.ok(failureLogs.items.some(item => item.nodeId === nodeId && item.level === 'error'))
  assert.ok(!JSON.stringify(failureLogs).includes('fixture-bot-token'))
  checks.push('Bot API 返回 ok=false 时运行失败，节点级错误保留且不重复发送')

  report = { evidenceId: 'BE.notify_telegram.real-execution', checkedAt: new Date().toISOString(), result: 'passed', gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(), platform: `${process.platform}-${process.arch}`, entry: desktop.packaged ? 'packaged' : 'development-build', workflowId: saved.id, nodeId, runs: [succeeded.runId, failed.runId], checks, requests: requests.map(item => ({ path: item.path.replace('fixture-bot-token', '[redacted]'), body: item.body })), boundaries: { userDatabaseTouched: false, workspace: 'ephemeral', transport: 'local TLS with hostname and certificate verification; production executor/httpx unchanged', externalTelegramDelivery: 'not tested', platformPending: 'macOS Intel, Windows, frozen package' } }
} catch (error) {
  await writeFile(join(evidenceDir, 'failure.json'), JSON.stringify({ checkedAt: new Date().toISOString(), checks, requests: requests.map(item => ({ path: item.path.replace('fixture-bot-token', '[redacted]'), body: item.body })), error: error instanceof Error ? error.stack : String(error) }, null, 2) + '\n')
  throw error
} finally {
  studio?.close(); main?.close(); await stop(desktop?.child)
  if (server) await new Promise(resolveClose => server.close(resolveClose))
  await rm(userData, { recursive: true, force: true })
  if (report) {
    assert.ok(desktop.child.exitCode !== null || desktop.child.signalCode !== null)
    assert.equal(server.listening, false)
    report.cleanup = { electronExited: true, fixturePortClosed: true, runsTerminalAfterWorkerCleanup: true }
    await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
    console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
  }
}

async function run(runtime, workflowId, previousIds) {
  await click(studio, '运行 (F5)', '[aria-label="运行 (F5)"]')
  await click(studio, '运行 (F5)', '[role="menuitem"]')
  const run = await poll(async () => (await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(workflowId)}&cursor=0&limit=20`)).items.find(item => !previousIds.has(item.runId)), 'new run')
  return poll(async () => { const item = await api(runtime, `/workflow-runs/${run.runId}`); return ['completed', 'failed', 'stopped', 'interrupted'].includes(item.status) ? item : null }, 'run completion', 60_000)
}
async function api(runtime, path, options = {}) { const response = await fetch(`${runtime.sidecar.baseUrl}/api${path}`, { method: options.method ?? 'GET', headers: { 'x-autoflow-token': runtime.sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': randomUUID() }, body: options.body === undefined ? undefined : JSON.stringify(options.body) }); if (!response.ok) throw new Error(`${options.method ?? 'GET'} /api${path}: ${response.status} ${await response.text()}`); return response.status === 204 ? undefined : response.json() }
async function poll(read, description, timeoutMs = 20_000) { const deadline = Date.now() + timeoutMs; while (Date.now() < deadline) { const value = await read(); if (value) return value; await wait(200) } throw new Error(`timed out waiting for ${description}`) }
async function point(cdp, selector, text = '') { return waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length),text=${JSON.stringify(text)};const e=!text?rows[0]:rows.find(e=>e.getAttribute('aria-label')===text)||rows.find(e=>e.textContent.trim()===text)||rows.find(e=>e.textContent.includes(text));if(!e||e.disabled)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `unobscured ${text || selector}`) }
async function click(cdp, text, selector = 'button') { const p = await point(cdp, selector, text); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p }); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 }); await wait(100) }
async function setInput(cdp, selector, value) { const p = await point(cdp, selector); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 3 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 3 }); await cdp.command('Input.insertText', { text: value }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 }); await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 }); await wait(100) }
async function addNode(cdp, label, moduleType) { const pane = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__pane');if(!e)return null;const r=e.getBoundingClientRect();for(const y of [.2,.45,.7])for(const x of [.15,.4,.65,.9]){const p={x:r.x+r.width*x,y:r.y+r.height*y};if(document.elementFromPoint(p.x,p.y)===e)return p}return null})()`, 'workflow canvas'); await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...pane, button: 'right', clickCount: 1 }); await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...pane, button: 'right', clickCount: 1 }); await setInput(cdp, 'input[placeholder="搜索模块（支持拼音）"]', label); await click(cdp, label, '[role="button"]'); const id = await waitFor(cdp, `document.querySelector('.react-flow__node')?.dataset.id`, `${moduleType} node`); await click(cdp, '', `.react-flow__node[data-id=${JSON.stringify(id)}]`); await waitFor(cdp, `document.body.innerText.includes(${JSON.stringify(moduleType)})`, 'node configuration'); return id }
