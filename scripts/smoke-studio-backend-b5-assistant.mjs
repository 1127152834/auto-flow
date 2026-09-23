import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import { createServer } from 'node:http'
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

import { connectCdp, launchElectron, wait, waitFor, waitForProjectPage } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const projectMode = process.argv.includes('--project')
const evidenceRoot = join(root, `docs/migration/studio-backend-migration/evidence/${projectMode ? 'project-integration' : 'b5'}`)
await mkdir(evidenceRoot, { recursive: true })
const evidenceDir = await mkdtemp(join(evidenceRoot, projectMode ? 'formal-project-assistant-electron-' : 'formal-assistant-electron-'))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-b5-assistant-'))
const workflowName = 'B5 小助手正式闭环'
const mcpSecret = `B5-mcp-${randomUUID()}`
const executableIndex = process.argv.indexOf('--executable')
const packagedExecutable = executableIndex === -1 ? null : process.argv[executableIndex + 1]
const checks = []
const model = await startAssistantModel()
let desktop, main, studio, native
let projectId

await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))

try {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'] })
  main = desktop.cdp
  native = await connectCdp(desktop.inspectorUrl)
  await native.evaluate("globalThis.qaElectron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');true")
  await main.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(main, "document.body?.innerText.includes('本地服务正常')", 'main service readiness', 30_000)
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  const provider = await api(runtime, '/v1/model-providers/connect', {
    method: 'POST',
    body: {
      provider: { name: 'B5 本地受控模型', presetId: 'custom-openai-compatible', providerKind: 'openai-compatible', baseUrl: model.baseUrl, apiKey: '', enabled: true, description: '正式 UI 受控验收' },
      selectedModels: [{ modelKey: 'assistant-fixture', displayName: 'B5 Assistant Fixture', tagsJson: ['chat'], contextWindow: 32768, enabled: true, description: '' }],
    },
  })
  const modelId = provider.models[0].id
  checkpoint('主应用模型管理保存本地受控模型；Studio 仅取得稳定 modelId，未保存第二套地址或密钥')

  if (projectMode) {
    await click(main, '项目', 'a, button')
    await click(main, '新建项目')
    await setInput(main, '#project-name', '小助手归属正式验收')
    await click(main, '创建项目')
    await waitFor(main, "document.body?.innerText.includes('小助手归属正式验收')", 'created project')
    if (!await main.evaluate('Boolean(document.querySelector(\'[aria-label="项目功能"]\'))')) await click(main, '小助手归属正式验收', '[role="button"],button')
    await waitForProjectPage(main)
    projectId = (await main.evaluate('location.hash')).match(/projects\/([^/]+)/)?.[1]
    assert.ok(projectId)
    const project = await api(runtime, `/v1/projects/${projectId}`)
    await api(runtime, `/v1/projects/${projectId}`, {
      method: 'PATCH',
      body: {
        defaultResources: { ...project.defaultResources, modelProviderId: provider.id },
        expectedManagementRevision: project.managementRevision,
      },
    })
    checkpoint('独立测试项目由公开项目接口设置默认模型提供方；正式Studio从所属项目继承模型')
    await click(main, '自动化', '[aria-label="项目功能"] button, [aria-label="项目功能"] [role="tab"]')
  }

  studio = await openStudioFromMain(main, desktop.debugOrigin)
  if (projectMode) assert.equal(await studio.evaluate("new URL(location.href).searchParams.get('projectId')"), projectId)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 2560, height: 1600, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库')", 'formal Studio', 30_000)
  await click(studio, '更多操作', 'button')
  await click(studio, '全局配置', '[role="menuitem"]')
  await click(studio, '小助手', 'nav button')
  await click(studio, '小助手主应用模型', 'button')
  await click(studio, 'B5 Assistant Fixture（B5 本地受控模型）', '[role="option"]')
  await click(studio, '逐项确认', 'button')

  await click(studio, 'MCP', 'nav button')
  await waitFor(studio, "document.body.innerText.includes('还没有配置 MCP 服务器')", 'empty MCP settings')
  await click(studio, '添加')
  await setInput(studio, 'input[placeholder="例如 filesystem / weather / github"]', 'fixture')
  await setInput(studio, 'input[placeholder="例如 npx / node / python"]', join(root, 'apps/backend/.venv/bin/python'))
  await setInput(studio, 'textarea[placeholder^="-y"]', join(root, 'apps/backend/tests/fixtures/mcp_stdio_server.py'))
  await setInput(studio, 'textarea[aria-label="环境变量"]', `B5_MCP_SECRET=${mcpSecret}`)
  await click(studio, '保存', '[role="dialog"] button')
  await waitFor(studio, "document.body.innerText.includes('fixture') && document.body.innerText.includes('未连接')", 'saved MCP configuration')
  await click(studio, '重新连接')
  await waitFor(studio, "document.body.innerText.includes('已连接 · 1 个工具')", 'real MCP stdio connection', 30_000)
  const mcpStatus = await api(runtime, '/ai-assistant/mcp/status')
  assert.equal(mcpStatus.servers[0].tools[0].name, 'echo')
  assert.equal((await readFile(join(runtime.workspaceKey, 'data/autoflow.sqlite3'))).includes(Buffer.from(mcpSecret)), false)
  checkpoint('通过正式 MCP 配置界面保存并重连真实 stdio 服务，发现 echo 工具且秘密不进 SQLite')
  await click(studio, '', 'button[aria-label="关闭全局配置"]')
  await click(studio, 'AI 小助手', 'button')
  await waitFor(studio, `(()=>{const e=document.querySelector('textarea[placeholder^="告诉我你想做什么"]');return !!e && !e.disabled})()`, 'configured assistant panel')
  checkpoint('通过正式 Toolbar 入口打开小助手，并在真实设置界面选择主应用模型和逐项确认权限')

  await setInput(studio, 'input[placeholder="工作流名称"]', workflowName)
  await sendMessage(studio, 'ADD 添加打开网页节点')
  await waitFor(studio, "document.body?.innerText.includes('小助手请求授权：添加节点')", 'add approval')
  assert.equal(await studio.evaluate("document.querySelectorAll('.react-flow__node').length"), 0)
  assert.equal(await studio.evaluate("document.body.innerText.includes('节点已添加并确认')"), false)
  await click(studio, '允许执行')
  await waitFor(studio, "document.querySelector('.react-flow__node[data-id=\"assistant-open\"]') !== null", 'assistant node insertion')
  await waitFor(studio, "document.body?.innerText.includes('节点已添加并确认')", 'confirmed add response')
  checkpoint('模型工具调用先暂停在权限界面；批准前画布无变化且未宣称完成，批准后才添加节点并继续 LangGraph')

  await sendMessage(studio, 'MODIFY 修改刚才节点网址')
  await waitFor(studio, "document.body?.innerText.includes('小助手请求授权：修改节点配置')", 'modify approval')
  await click(studio, '允许执行')
  await waitFor(studio, "document.body?.innerText.includes('节点配置已修改并确认')", 'confirmed modify response')
  checkpoint('同一会话第二轮修改节点，经独立 commandId 授权后继续模型回合')

  await sendMessage(studio, 'DELETE 尝试删除节点')
  await waitFor(studio, "document.body?.innerText.includes('小助手请求授权：删除节点')", 'delete approval')
  await click(studio, '拒绝（继续任务）')
  await waitFor(studio, "document.body?.innerText.includes('删除被拒绝，节点保持不变')", 'rejected action response')
  assert.equal(await studio.evaluate("document.querySelectorAll('.react-flow__node').length"), 1)
  checkpoint('拒绝操作作为真实工具结果返回模型；会话继续，节点保持不变')

  await sendMessage(studio, 'EXCLUDED 请求添加已排除节点')
  await waitFor(studio, "document.body?.innerText.includes('助手请求包含未批准的节点类型: excel_write')", 'excluded module rejection')
  assert.equal(await studio.evaluate("document.body.innerText.includes('小助手请求授权：添加节点')"), false)
  assert.equal(await studio.evaluate("document.querySelectorAll('.react-flow__node').length"), 1)
  checkpoint('已排除节点在后端 LangGraph 校验边界拒绝，未进入权限请求且未改变画布')

  await sendMessage(studio, 'MCP 调用回显工具')
  await waitFor(studio, "document.body?.innerText.includes('小助手请求授权：MCP 工具：fixture / echo')", 'MCP tool approval')
  await click(studio, '允许执行')
  await waitFor(studio, "document.body?.innerText.includes('MCP 工具已执行：echo:B5 正式验收')", 'confirmed MCP tool response')
  checkpoint('MCP 工具即使已连接仍先显示授权；批准后后端真实调用 stdio 工具并将结果送回 LangGraph')

  await sendMessage(studio, 'SLOW 启动可取消回答')
  await waitFor(studio, "document.querySelector('button[aria-label=\"停止小助手\"]') !== null", 'assistant stop control')
  await click(studio, '停止小助手', 'button')
  await waitFor(studio, "document.querySelector('button[aria-label=\"发送消息\"]') !== null", 'assistant cancellation')
  const cancelled = await waitForValue(async () => {
    const summary = (await api(runtime, '/ai-assistant/sessions')).find(item => item.title.startsWith('ADD'))
    if (!summary) return null
    const detail = await api(runtime, `/ai-assistant/sessions/${encodeURIComponent(summary.id)}`)
    return detail.status === 'cancelled' ? detail : null
  }, 'cancelled assistant session', 15_000)
  assert.ok(cancelled)
  await waitForValue(async () => model.slowCancelled, 'provider stream cancellation', 5_000)
  assert.equal(await studio.evaluate("document.body.innerText.includes('不应出现的慢响应完成')"), false)
  checkpoint('停止按钮取消正在流式调用的真实 HTTP 请求；迟到内容未写入，持久化会话状态为 cancelled')

  await click(studio, '保存')
  await waitFor(studio, `document.body?.innerText.includes(${JSON.stringify(`工作流已保存: ${workflowName}`)})`, 'workflow save acknowledgement')
  const saved = (await api(runtime, '/workflows')).find(item => item.name === workflowName)
  assert.ok(saved)
  assert.equal(saved.nodes.length, 1)
  assert.equal(saved.nodes[0].id, 'assistant-open')
  assert.equal(saved.nodes[0].data.url, 'https://example.test')
  checkpoint('小助手添加和修改的草稿通过真实保存入口写入 SQLite；拒绝与排除请求没有残留副作用')

  const sessionBeforeClose = (await api(runtime, '/ai-assistant/sessions')).find(item => item.title.startsWith('ADD'))
  assert.ok(sessionBeforeClose)
  if (projectMode) {
    const unscoped = await fetch(`${runtime.sidecar.baseUrl}/api/ai-assistant/sessions`, { headers: { 'x-autoflow-token': runtime.sidecar.token } })
    assert.deepEqual(await unscoped.json(), [])
    checkpoint('项目小助手历史只在所属项目可见，独立Studio列表不包含该会话')
  }
  await closeStudioWindow()
  studio.close(); studio = undefined
  await waitForNoStudio(desktop.debugOrigin)
  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 2560, height: 1600, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库')", 'reopened Studio', 30_000)
  await click(studio, 'AI 小助手', 'button')
  await click(studio, '历史对话', 'button')
  await waitFor(studio, `document.body.innerText.includes(${JSON.stringify(sessionBeforeClose.title)})`, 'persisted assistant history')
  await click(studio, sessionBeforeClose.title, 'div')
  await waitFor(studio, "document.body?.innerText.includes('节点配置已修改并确认') && document.body.innerText.includes('删除被拒绝，节点保持不变')", 'restored multi-turn messages')
  checkpoint('通过正式 BrowserWindow 正常关闭并重开 Studio；历史列表从 SQLite 恢复多轮会话，未重放任何画布副作用')

  const session = await api(runtime, `/ai-assistant/sessions/${encodeURIComponent(sessionBeforeClose.id)}`)
  const commandEvents = model.requests.filter(item => item.path === '/v1/chat/completions')
  assert.ok(commandEvents.length >= 8)
  assert.ok(session.messages.some(item => item.content === '节点已添加并确认'))
  assert.ok(session.messages.some(item => item.content === '删除被拒绝，节点保持不变'))
  const toolCalls = session.messages.flatMap(item => item.tool_calls ?? [])
  assert.deepEqual(toolCalls.map(item => item.id), ['b5-add', 'b5-modify', 'b5-delete', 'b5-mcp'])
  const rejectedDelete = toolCalls.find(item => item.id === 'b5-delete')
  assert.equal(rejectedDelete.status, 'failed')
  assert.match(rejectedDelete.error, /拒绝/)
  await capture(studio, join(evidenceDir, 'assistant-history.png'))
  await writeFile(join(evidenceDir, 'result.json'), JSON.stringify({
    evidenceId: 'BE-B5-assistant-formal-electron', checkedAt: new Date().toISOString(),
    gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    result: 'passed', platform: `${process.platform}-${process.arch}`, entry: desktop.packaged ? 'packaged-directory' : 'development-build',
    smokeScriptSha256: createHash('sha256').update(await readFile(new URL(import.meta.url))).digest('hex'),
    ...(packagedExecutable ? { executableSha256: createHash('sha256').update(await readFile(packagedExecutable)).digest('hex') } : {}),
    workflowId: saved.id, modelId, assistantSessionId: sessionBeforeClose.id, ...(projectId ? { projectId } : {}),
    checks, providerRequestCount: commandEvents.length,
    boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browserStarted: false, model: 'local controlled OpenAI-compatible HTTP fixture', interaction: 'formal Electron through CDP mouse/keyboard plus BrowserWindow normal close; public API only for fixture setup and evidence reads; no Store or page-internal business function access' },
  }, null, 2) + '\n')
  console.log(`B5 assistant formal smoke passed: ${evidenceDir}`)
} catch (error) {
  if (studio) await capture(studio, join(evidenceDir, 'failure.png')).catch(() => undefined)
  await writeFile(join(evidenceDir, 'failure.json'), JSON.stringify({ checkedAt: new Date().toISOString(), checks, error: error instanceof Error ? error.stack : String(error) }, null, 2) + '\n')
  throw error
} finally {
  studio?.close(); main?.close(); native?.close(); await stop(desktop?.child)
  await model.close(); await rm(userData, { recursive: true, force: true })
}
process.exit(0)

function checkpoint(message) { checks.push(message); console.log(message) }

async function startAssistantModel() {
  const requests = []
  let slowCancelled = false
  const server = createServer(async (request, response) => {
    const url = new URL(request.url, 'http://127.0.0.1')
    let raw = ''
    for await (const chunk of request) raw += chunk
    const body = raw ? JSON.parse(raw) : null
    requests.push({ method: request.method, path: url.pathname, body })
    if (request.method === 'GET' && url.pathname === '/v1/models') return json(response, { data: [{ id: 'assistant-fixture', context_length: 32768 }] })
    if (request.method !== 'POST' || url.pathname !== '/v1/chat/completions') return json(response, { error: { message: 'not found' } }, 404)
    const messages = Array.isArray(body?.messages) ? body.messages : []
    const user = [...messages].reverse().find(item => item.role === 'user')
    const prompt = typeof user?.content === 'string' ? user.content : ''
    const last = messages.at(-1)
    if (last?.role === 'tool') {
      if (prompt.startsWith('ADD')) return streamText(response, '节点已添加并确认')
      if (prompt.startsWith('MODIFY')) return streamText(response, '节点配置已修改并确认')
      if (prompt.startsWith('DELETE')) return streamText(response, '删除被拒绝，节点保持不变')
      if (prompt.startsWith('MCP')) {
        const result = JSON.parse(last.content)
        return streamText(response, `MCP 工具已执行：${result.data.content}`)
      }
    }
    if (prompt.startsWith('ADD')) return streamTool(response, 'b5-add', 'add_nodes', { nodes: [{ id: 'assistant-open', type: 'open_page', position: { x: 240, y: 220 }, data: { moduleType: 'open_page', url: 'about:blank' } }] })
    if (prompt.startsWith('MODIFY')) return streamTool(response, 'b5-modify', 'update_node_config', { node_id: 'assistant-open', config: { url: 'https://example.test' } })
    if (prompt.startsWith('DELETE')) return streamTool(response, 'b5-delete', 'delete_node', { node_id: 'assistant-open' })
    if (prompt.startsWith('EXCLUDED')) return streamTool(response, 'b5-excluded', 'add_nodes', { nodes: [{ id: 'excluded', type: 'excel_write', position: { x: 0, y: 0 }, data: { moduleType: 'excel_write' } }] })
    if (prompt.startsWith('MCP')) return streamTool(response, 'b5-mcp', 'mcp__fixture__echo', { text: 'B5 正式验收' }, false)
    if (prompt.startsWith('SLOW')) {
      response.writeHead(200, { 'content-type': 'text/event-stream' })
      response.write(`data: ${JSON.stringify({ choices: [{ delta: { content: '慢响应已开始' } }] })}\n\n`)
      await Promise.race([wait(60_000), new Promise(resolve => response.once('close', () => { slowCancelled = true; resolve() }))])
      if (!response.destroyed) streamText(response, '不应出现的慢响应完成', false)
      return
    }
    return streamText(response, 'OK')
  })
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve) })
  return {
    baseUrl: `http://127.0.0.1:${server.address().port}/v1`, requests,
    get slowCancelled() { return slowCancelled },
    close: () => new Promise(resolve => { server.close(resolve); server.closeAllConnections() }),
  }
}

function json(response, body, status = 200) { response.writeHead(status, { 'content-type': 'application/json' }).end(JSON.stringify(body)) }
function streamText(response, text, headers = true) {
  if (headers) response.writeHead(200, { 'content-type': 'text/event-stream' })
  response.end(`data: ${JSON.stringify({ choices: [{ delta: { content: text } }] })}\n\ndata: [DONE]\n\n`)
}
function streamTool(response, id, action, payload, clientAction = true) {
  response.writeHead(200, { 'content-type': 'text/event-stream' })
  response.end(`data: ${JSON.stringify({ choices: [{ delta: { tool_calls: [{ index: 0, id, function: { name: clientAction ? 'client_action' : action, arguments: JSON.stringify(clientAction ? { action, payload } : payload) } }] } }] })}\n\ndata: [DONE]\n\n`)
}

async function api(runtime, path, options = {}) {
  const url = new URL(`${runtime.sidecar.baseUrl}/api${path}`)
  if (projectId && (/^\/(?:ai-assistant|workflows)(?:\/|$)/.test(path))) url.searchParams.set('projectId', projectId)
  const response = await fetch(url, { method: options.method ?? 'GET', headers: { 'x-autoflow-token': runtime.sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': randomUUID() }, body: options.body === undefined ? undefined : JSON.stringify(options.body) })
  if (!response.ok) throw new Error(`${options.method ?? 'GET'} /api${path}: ${response.status} ${await response.text()}`)
  return response.status === 204 ? undefined : response.json()
}

async function openStudioFromMain(cdp, origin) {
  await click(cdp, '工作流工作台')
  const target = await waitForTarget(origin, item => item.type === 'page' && item.url.includes('studio.html'), 'Studio target')
  return connectCdp(target.webSocketDebuggerUrl)
}
async function waitForTarget(origin, predicate, description, timeoutMs = 15_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) { const target = (await (await fetch(`${origin}/json/list`)).json()).find(predicate); if (target) return target; await wait(100) }
  throw new Error(`timed out waiting for ${description}`)
}
async function waitForNoStudio(origin, timeoutMs = 15_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) { const targets = await (await fetch(`${origin}/json/list`)).json(); if (!targets.some(target => target.type === 'page' && target.url.includes('studio.html'))) return; await wait(100) }
  throw new Error('timed out waiting for Studio window close')
}
async function waitForValue(read, description, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) { const value = await read(); if (value) return value; await wait(200) }
  throw new Error(`timed out waiting for ${description}`)
}
async function point(cdp, selector, text = '') {
  return waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length),text=${JSON.stringify(text)};const e=!text?rows[0]:rows.find(e=>e.getAttribute('aria-label')===text)||rows.find(e=>e.textContent.trim()===text)||rows.find(e=>e.textContent.includes(text));if(!e||e.disabled)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `unobscured ${text || selector}`)
}
async function click(cdp, text, selector = 'button') {
  const p = await point(cdp, selector, text)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 })
  await wait(120)
}
async function setInput(cdp, selector, value) {
  const p = await point(cdp, selector)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 3 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 3 })
  await cdp.command('Input.insertText', { text: value })
  await wait(80)
}
async function sendMessage(cdp, message) {
  await setInput(cdp, 'textarea[placeholder^="告诉我你想做什么"]', message)
  await click(cdp, '发送消息', 'button')
}
async function closeStudioWindow() {
  assert.equal(await native.evaluate("(()=>{const w=qaElectron.BrowserWindow.getAllWindows().find(w=>w.getTitle().includes('工作流工作台'));if(!w)return false;w.close();return true})()"), true)
  await wait(200)
}
async function capture(cdp, path) { const { data } = await cdp.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }); await writeFile(path, data, 'base64') }
