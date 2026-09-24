import assert from 'node:assert/strict'
import { execFileSync, spawn } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import { mkdir, mkdtemp, readFile, rm, stat, writeFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import { tmpdir } from 'node:os'
import { basename, join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const gitHead = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim()
const sourceKernel = process.env.AUTOFLOW_B1_KERNEL_DIR
  ?? '/Users/zhangtiancheng/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2'
const kernelVersion = basename(sourceKernel).replace(/^chromium-/, '')
const complexDebugOnly = process.env.AUTOFLOW_B8_COMPLEX_DEBUG_ONLY === '1'
const restartRecoveryOnly = process.env.AUTOFLOW_B8_RESTART_RECOVERY_ONLY === '1'
const projectInteractionOnly = process.env.AUTOFLOW_PROJECT_INTERACTION_TASK === '1'
const projectMathOnly = process.env.AUTOFLOW_PROJECT_MATH_TASK === '1'
const projectUtilityOnly = process.env.AUTOFLOW_PROJECT_UTILITY_TASK === '1'
const projectWebBasicOnly = process.env.AUTOFLOW_PROJECT_WEB_BASIC_TASK === '1'
const projectPageLoadOnly = process.env.AUTOFLOW_PROJECT_PAGE_LOAD_TASK === '1'
const projectAdvancedOnly = process.env.AUTOFLOW_PROJECT_ADVANCED_BROWSER_TASK === '1'
const projectTabSwitchOnly = process.env.AUTOFLOW_PROJECT_TAB_SWITCH_TASK === '1'
const projectVariableOnly = process.env.AUTOFLOW_PROJECT_VARIABLE_TASK === '1'
const projectListExportOnly = process.env.AUTOFLOW_PROJECT_LIST_EXPORT_TASK === '1'
const projectLogOnly = process.env.AUTOFLOW_PROJECT_LOG_TASK === '1'
const projectTableOnly = process.env.AUTOFLOW_PROJECT_TABLE_TASK === '1'
const projectHttpOnly = process.env.AUTOFLOW_PROJECT_HTTP_TASK === '1'
const projectControlPrimitivesOnly = process.env.AUTOFLOW_PROJECT_CONTROL_PRIMITIVES_TASK === '1'
const projectNetworkOnly = process.env.AUTOFLOW_PROJECT_NETWORK_TASK === '1'
const projectAllureOnly = process.env.AUTOFLOW_PROJECT_ALLURE_TASK === '1'
const projectElementChangeOnly = process.env.AUTOFLOW_PROJECT_ELEMENT_CHANGE_TASK === '1'
const projectFileWatcherOnly = process.env.AUTOFLOW_PROJECT_FILE_WATCHER_TASK === '1'
const projectProcessOnly = process.env.AUTOFLOW_PROJECT_PROCESS_TASK === '1'
const projectFirecrawlOnly = process.env.AUTOFLOW_PROJECT_FIRECRAWL_TASK === '1'
const projectBase64Only = process.env.AUTOFLOW_PROJECT_BASE64_TASK === '1'
const projectTimingOnly = process.env.AUTOFLOW_PROJECT_TIMING_TASK === '1'
const projectSshOnly = process.env.AUTOFLOW_PROJECT_SSH_TASK === '1'
const projectFamilyOnly = projectMathOnly || projectUtilityOnly || projectWebBasicOnly || projectPageLoadOnly || projectAdvancedOnly || projectTabSwitchOnly || projectVariableOnly || projectListExportOnly || projectLogOnly || projectTableOnly || projectHttpOnly || projectControlPrimitivesOnly || projectNetworkOnly || projectAllureOnly
const projectTaskOnly = process.env.AUTOFLOW_B3_PROJECT_TASK === '1' || projectInteractionOnly || projectFamilyOnly || projectSshOnly || projectTimingOnly || projectBase64Only || projectFirecrawlOnly || projectProcessOnly || projectFileWatcherOnly || projectElementChangeOnly
const focusedB8 = complexDebugOnly || restartRecoveryOnly
const evidenceRoot = join(root, `docs/migration/studio-backend-migration/evidence/${projectTaskOnly ? 'project-integration' : focusedB8 ? 'b8' : 'b3'}`)
await mkdir(evidenceRoot, { recursive: true })
const evidenceDir = await mkdtemp(join(evidenceRoot, projectInteractionOnly ? 'formal-project-interaction-electron-' : projectElementChangeOnly ? 'formal-project-element-change-electron-' : projectFileWatcherOnly ? 'formal-project-file-watcher-electron-' : projectProcessOnly ? 'formal-project-process-electron-' : projectFirecrawlOnly ? 'formal-project-firecrawl-electron-' : projectBase64Only ? 'formal-project-base64-electron-' : projectTimingOnly ? 'formal-project-timing-electron-' : projectSshOnly ? 'formal-project-ssh-electron-' : projectMathOnly ? 'formal-project-math-electron-' : projectUtilityOnly ? 'formal-project-utility-electron-' : projectWebBasicOnly ? 'formal-project-web-basic-electron-' : projectPageLoadOnly ? 'formal-project-page-load-electron-' : projectAdvancedOnly ? 'formal-project-advanced-browser-electron-' : projectTabSwitchOnly ? 'formal-project-tab-switch-electron-' : projectVariableOnly ? 'formal-project-variable-electron-' : projectListExportOnly ? 'formal-project-list-export-electron-' : projectLogOnly ? 'formal-project-log-electron-' : projectTableOnly ? 'formal-project-table-electron-' : projectHttpOnly ? 'formal-project-http-electron-' : projectControlPrimitivesOnly ? 'formal-project-control-primitives-electron-' : projectNetworkOnly ? 'formal-project-network-electron-' : projectAllureOnly ? 'formal-project-allure-electron-' : projectTaskOnly ? 'formal-project-control-electron-' : restartRecoveryOnly ? 'formal-restart-recovery-electron-' : complexDebugOnly ? 'formal-complex-debug-electron-' : 'formal-control-flow-electron-'))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-b3-control-flow-'))
const workflowName = 'B3 控制流正式闭环'
const checks = []
const observedEvents = []
let desktop
let main
let native
let studio
let eventAbort
let projectId
let httpFixture
let httpOrigin
let sshFixture
let sshFixtureError = ''
let sshCredential
let runtime
const httpRequests = []
class EvidenceComplete extends Error {}

try {
  let sshServer
  if (projectSshOnly) {
    const statusPath = join(userData, 'ssh-status.json')
    sshFixture = spawn(join(root, 'apps/backend/.venv/bin/python'), ['tests/integration/test_b6_ssh_worker.py', '--root', join(userData, 'remote-host'), '--status', statusPath], {
      cwd: join(root, 'apps/backend'), env: { ...process.env, PYTHONPATH: 'src' }, stdio: ['pipe', 'ignore', 'pipe'],
    })
    sshFixture.stderr.on('data', data => { sshFixtureError += data.toString() })
    sshServer = await waitForValue(async () => {
      if (sshFixture.exitCode !== null) throw new Error(`SSH fixture exited: ${sshFixtureError}`)
      return readFile(statusPath, 'utf8').then(JSON.parse).catch(() => null)
    }, 'project loopback SSH server', 10_000)
  }
  if (projectHttpOnly) {
    httpFixture = createServer(async (request, response) => {
      const body = []
      for await (const chunk of request) body.push(chunk)
      const value = body.length ? JSON.parse(Buffer.concat(body).toString('utf8')) : null
      httpRequests.push([request.method, request.url, value])
      const result = request.url === '/poll'
        ? { data: { status: httpRequests.filter(item => item[1] === '/poll').length > 1 ? 'ready' : 'pending' } }
        : request.url === '/api' ? { accepted: '甲' } : { accepted: value }
      const bytes = Buffer.from(JSON.stringify(result))
      response.writeHead(200, { 'content-type': 'application/json', 'content-length': bytes.length })
      response.end(bytes)
    })
    await new Promise(resolve => httpFixture.listen(0, '127.0.0.1', resolve))
    httpOrigin = `http://127.0.0.1:${httpFixture.address().port}`
  }
  if (projectNetworkOnly) {
    const page = await readFile(join(root, 'apps/backend/tests/fixtures/workflow-project-network-monitor.html'))
    httpFixture = createServer((request, response) => {
      httpRequests.push([request.method, request.url])
      const api = request.url?.startsWith('/api/orders')
      const body = api ? Buffer.from('{"ok":true}') : page
      response.writeHead(200, { 'content-type': api ? 'application/json' : 'text/html; charset=utf-8', 'content-length': body.length })
      response.end(body)
    })
    await new Promise(resolve => httpFixture.listen(0, '127.0.0.1', resolve))
    httpOrigin = `http://127.0.0.1:${httpFixture.address().port}`
  }
  if (projectFirecrawlOnly) {
    const page = await readFile(join(root, 'apps/backend/tests/fixtures/workflow-project-crawl.html'))
    httpFixture = createServer((request, response) => {
      httpRequests.push([request.method, request.url])
      const sitemap = request.url === '/sitemap.xml'
      const body = sitemap ? Buffer.from(`<urlset><url><loc>${httpOrigin}/crawl/from-map</loc></url></urlset>`) : page
      response.writeHead(200, { 'content-type': sitemap ? 'application/xml' : 'text/html; charset=utf-8', 'content-length': body.length })
      response.end(body)
    })
    await new Promise(resolve => httpFixture.listen(0, '127.0.0.1', resolve))
    httpOrigin = `http://127.0.0.1:${httpFixture.address().port}`
  }
  assert.equal(process.platform, 'darwin', 'formal evidence requires macOS')
  assert.equal(process.arch, 'arm64', 'formal evidence requires native arm64 Node/Electron')
  await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
  await mkdir(join(userData, 'data', 'kernels'), { recursive: true })
  execFileSync('cp', ['-cR', sourceKernel, join(userData, 'data', 'kernels', basename(sourceKernel))])

  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'] })
  main = desktop.cdp
  native = await connectCdp(desktop.inspectorUrl)
  await native.evaluate("globalThis.qaElectron=process.getBuiltinModule('module').createRequire(process.cwd()+'/package.json')('electron');true")
  await main.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(main, "document.body?.innerText.includes('本地服务正常')", 'main service readiness', 30_000)
  runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  eventAbort = new AbortController()
  void collectEvents(runtime, eventAbort.signal, observedEvents)
  const profile = await api(runtime, '/v1/profiles', {
    method: 'POST',
    body: {
      name: 'B3 控制流纯数据验收配置', description: '临时工作区；控制流不得启动浏览器', startUrl: 'about:blank',
      locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false, headless: true, humanize: false,
      humanPreset: 'default', userAgent: null, viewportJson: null, colorScheme: 'light', extensionPathsJson: [], expertArgsJson: [],
      browserVersion: kernelVersion, browserEdition: 'public', releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null,
    },
  })
  assert.deepEqual(cloakProcesses(userData), [])
  checkpoint('真实 sidecar 使用临时工作区和主应用 Profile；运行前无 CloakBrowser 进程')

  if (projectTaskOnly) {
    await click(main, '项目', 'a, button')
    await click(main, '新建项目')
    await setInput(main, '#project-name', '控制流项目任务验收')
    await click(main, '创建项目')
    await waitFor(main, "document.body?.innerText.includes('控制流项目任务验收')", 'control project')
    if (!await main.evaluate('Boolean(document.querySelector(\'[aria-label="项目功能"]\'))')) await click(main, '控制流项目任务验收', '[role="button"],button')
    await waitFor(main, 'Boolean(document.querySelector(\'[aria-label="项目功能"]\'))', 'project page')
    projectId = (await main.evaluate('location.hash')).match(/projects\/([^/]+)/)?.[1]
    assert.ok(projectId)
    const project = await api(runtime, `/v1/projects/${projectId}`)
    await api(runtime, `/v1/projects/${projectId}`, { method: 'PATCH', body: { expectedManagementRevision: project.managementRevision, defaultResources: { ...project.defaultResources, profileId: profile.id } } })
    await click(main, '自动化', '[aria-label="项目功能"] button,[aria-label="项目功能"] [role="tab"]')
  }

  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库') && document.body.innerText.includes('213')", 'formal Studio', 30_000)
  await waitFor(studio, `document.querySelector('[aria-label="运行浏览器配置"]')?.value === ${JSON.stringify(profile.id)}`, 'managed Profile selection')
  if (projectInteractionOnly) {
    const name = '项目输入与JS交互验收'
    const code = 'function main(vars) { const end = Date.now() + 4000; while(Date.now() < end) {} vars.count = (vars.count || 0) + 1; return Number(vars.answer) * 2; }'
    await newWorkflow(studio, name)
    // WebRPA only writes back existing variables. Declare the counter through UI.
    await addGlobalVariable(studio, 'count', 'number', '0')
    await showBlockView(studio)
    await addBlock(studio, '添加模块', '用户输入')
    await selectNative(studio, '#inputMode', '整数')
    await setVariableNameInput(studio, '#variableName', 'answer')
    await setInput(studio, '[placeholder="输入框的标题"]', '项目交互实测')
    await addBlock(studio, '添加模块', 'JS脚本')
    await click(studio, '打开代码编辑器', 'div')
    await waitFor(studio, "Boolean(document.querySelector('.monaco-editor'))", 'JS editor')
    await click(studio, '', '.monaco-editor .view-lines')
    await studio.command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'a', code: 'KeyA', windowsVirtualKeyCode: 65, modifiers: 4, commands: ['selectAll'] })
    await studio.command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'a', code: 'KeyA', windowsVirtualKeyCode: 65, modifiers: 4 })
    await studio.command('Input.insertText', { text: code })
    await click(studio, '保存', 'div.fixed button')
    await setVariableNameInput(studio, '#resultVariable', 'doubled')
    await addBlock(studio, '添加模块', '打印日志')
    await setInput(studio, '[placeholder="要打印的日志信息"]', '交互完成:{answer}:{doubled}:{count}')
    await click(studio, '保存')
    const saved = await waitForValue(async () => (await api(runtime, `/workflows?projectId=${projectId}`)).find(item => item.name === name), 'interaction workflow saved', 15_000)
    assert.deepEqual(saved.nodes.map(node => node.data.moduleType), ['input_prompt', 'js_script', 'print_log'])
    assert.equal(saved.nodes[1].data.code, code)
    assert.ok(saved.variables.some(variable => variable.name === 'count' && variable.type === 'number' && variable.value === 0))
    await closeWindowThroughOs()
    studio.close(); studio = undefined
    await waitForNoStudio(desktop.debugOrigin)
    await click(main, '新建自动化')
    await setInput(main, '[aria-label="自动化名称"]', name)
    await selectAutomationWorkflow(main, name, saved.id)
    await click(main, '保存配置')
    await waitFor(main, "document.body?.innerText.includes('自动化已创建')", 'interaction automation')
    // The saved automation detail owns the linked Studio entry.
    studio = await openStudioFromMain(main, desktop.debugOrigin, '打开 Studio')
    await click(main, '启动运行')
    await click(main, '启动 1 个任务')
    await waitFor(main, "document.querySelector('[role=dialog]')?.innerText.includes('项目交互实测')", 'project input request', 30_000)
    await capture(main, join(evidenceDir, 'project-input.png'))
    await setInput(main, '[role=dialog] input[type=number]', '21')
    await click(main, '确定', '[role=dialog] button')
    await waitForValue(async () => (await api(runtime, '/v1/project-run-interactions')).some(item => item.type === 'execution:js_script' && item.status === 'claimed'), 'JS claimed before main close', 15_000)
    await native.evaluate("(()=>{const w=qaElectron.BrowserWindow.getAllWindows().find(w=>!w.getTitle().includes('工作流工作台'));qaElectron.app.focus({steal:true});w.show();w.focus();return true})()")
    execFileSync('osascript', ['-e', 'tell application "System Events" to keystroke "w" using command down'])
    await waitForValue(async () => native.evaluate("(()=>{const w=qaElectron.BrowserWindow.getAllWindows().find(w=>!w.getTitle().includes('工作流工作台'));return w && !w.isVisible() && !w.isDestroyed()})()"), 'main hidden without disposing JS', 5000)
    const batch = (await api(runtime, `/v1/projects/${projectId}/batches?pageSize=20`)).items[0]
    const terminal = await waitForValue(async () => { const value = await api(runtime, `/v1/projects/${projectId}/batches/${batch.batchId}`); return value.batch.status === 'completed' || value.batch.status === 'failed' ? value : null }, 'interactive task completion', 45_000)
    assert.equal(terminal.statusCounts.succeeded, 1, JSON.stringify(terminal))
    const task = (await api(runtime, `/v1/projects/${projectId}/tasks?batchId=${batch.batchId}`)).items[0]
    const outputs = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/outputs?pageSize=100`)
    assert.equal(outputs.items.find(item => item.name === 'answer')?.value, 21)
    assert.equal(outputs.items.find(item => item.name === 'doubled')?.value, 42)
    const logs = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/logs?pageSize=100`)
    assert.ok(logs.items.some(item => item.message === '交互完成:21:42:1'), JSON.stringify(logs))
    assert.deepEqual(await api(runtime, '/v1/project-run-interactions'), [])
    await closeWindowThroughOs()
    studio.close(); studio = undefined
    await waitForValue(async () => native.evaluate("qaElectron.BrowserWindow.getAllWindows().some(w=>!w.getTitle().includes('工作流工作台')&&w.isVisible())"), 'main restored after Studio closes', 5000)
    await click(main, '查看任务')
    await click(main, '输入与输出', '[role=tab]')
    await waitFor(main, "document.body.innerText.includes('doubled')", 'persisted interaction outputs')
    await capture(main, join(evidenceDir, 'project-interaction-output.png'))
    checkpoint('真实UI编排保存重开，主窗口输入21；原JS Worker只执行一次，正常关主窗口期间继续，输出42和持久日志，关Studio后主窗口恢复')
    assert.deepEqual(cloakProcesses(userData), [])
    const report = { evidenceId: 'BE-project-interaction-formal-electron', result: 'passed', checkedAt: new Date().toISOString(), gitHead, platform: `${process.platform}-${process.arch}`, entry: desktop.packaged ? 'packaged-directory' : 'development-build', projectId, workflowId: saved.id, taskId: task.taskId, checks, boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browserStarted: false, interaction: 'real UI mouse/keyboard; original renderer JS Worker; API fixtures and evidence reads only' } }
    await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
    console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
    throw new EvidenceComplete()
  }
  if (projectSshOnly) {
    const name = '项目 SSH 文件往返任务验收'
    const credentialName = `项目SSH验收-${randomUUID()}`
    const credentialReference = `{{cred:${credentialName}.password}}`
    const uploadPath = join(userData, 'ssh-upload.bin')
    const downloadPath = join(userData, 'ssh-download.bin')
    const content = Buffer.from(`项目 SSH 文件往返\n${randomUUID()}\n`)
    await writeFile(uploadPath, content)
    await api(runtime, '/credentials', { method: 'POST', body: { name: credentialName, fields: { password: 'secret' } } })
    sshCredential = credentialName
    await newWorkflow(studio, name)
    await showBlockView(studio)
    await addBlock(studio, '添加模块', 'SSH连接')
    await setInput(studio, '[placeholder="192.168.1.100"]', '127.0.0.1')
    await setInput(studio, 'input[inputmode="numeric"]', String(sshServer.port))
    await setInput(studio, '[placeholder="root"]', 'tester')
    await setInput(studio, '[placeholder="请输入密码（或使用密钥文件）"]', credentialReference)
    await addBlock(studio, '添加模块', 'SSH执行命令')
    await setInput(studio, 'textarea[placeholder="ls -la"]', 'printf ok')
    await addBlock(studio, '添加模块', 'SSH上传文件')
    await setInput(studio, '[placeholder="C:/data/file.txt"]', uploadPath)
    await setInput(studio, '[placeholder="/home/user/file.txt"]', '/remote/roundtrip.bin')
    await addBlock(studio, '添加模块', 'SSH下载文件')
    await setInput(studio, '[placeholder="/home/user/file.txt"]', '/remote/roundtrip.bin')
    await setInput(studio, '[placeholder="C:/data/file.txt"]', downloadPath)
    await addBlock(studio, '添加模块', 'SSH断开连接')
    await click(studio, '保存')
    const saved = await waitForValue(async () => (await api(runtime, `/workflows?projectId=${projectId}`)).find(item => item.name === name), 'project SSH saved', 15_000)
    assert.deepEqual(saved.nodes.map(node => node.data.moduleType), ['ssh_connect', 'ssh_execute_command', 'ssh_upload_file', 'ssh_download_file', 'ssh_disconnect'])
    assert.equal(saved.edges.length, 4)
    assert.ok(JSON.stringify(saved).includes(credentialReference))
    assert.ok(!JSON.stringify(saved).includes('"password":"secret"'))
    checkpoint('正式 Studio 真实输入五个 SSH 节点并保存项目文档；密码字段仅持久化主应用凭据引用')
    await closeWindowThroughOs()
    studio.close(); studio = undefined
    await waitForNoStudio(desktop.debugOrigin)
    await click(main, '新建自动化')
    await setInput(main, '[aria-label="自动化名称"]', '项目 SSH 自动化')
    await selectAutomationWorkflow(main, name, saved.id)
    await click(main, '保存配置')
    await waitFor(main, "document.body?.innerText.includes('自动化已创建')", 'project SSH automation')
    await click(main, '启动运行')
    await waitFor(main, "document.body?.innerText.includes('启动自动化')", 'project SSH batch dialog')
    await click(main, '启动 1 个任务')
    await waitFor(main, "document.body?.innerText.includes('本批次任务')", 'project SSH batch')
    const batch = (await api(runtime, `/v1/projects/${projectId}/batches?pageSize=20`)).items[0]
    const terminal = await waitForValue(async () => { const value = await api(runtime, `/v1/projects/${projectId}/batches/${batch.batchId}`); return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.batch.status) ? value : null }, 'project SSH terminal', 90_000)
    const task = (await api(runtime, `/v1/projects/${projectId}/tasks?batchId=${batch.batchId}`)).items[0]
    const attempts = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/node-attempts?pageSize=100`)
    assert.equal(terminal.statusCounts.succeeded, 1, JSON.stringify({ terminal, task, attempts }))
    assert.equal(attempts.items.filter(item => item.status === 'succeeded').length, 5)
    const outputs = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/outputs?pageSize=100`)
    assert.equal(outputs.items.find(item => item.name === 'ssh_output')?.value, 'ok\n')
    assert.equal(outputs.items.find(item => item.name === 'ssh_exit_code')?.value, 0)
    assert.deepEqual(await readFile(join(userData, 'remote-host/remote/roundtrip.bin')), content)
    assert.deepEqual(await readFile(downloadPath), content)
    const artifacts = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/artifacts?pageSize=100`)
    assert.equal(artifacts.total, 1)
    const response = await fetch(`${runtime.sidecar.baseUrl}${artifacts.items[0].contentUrl}`, { headers: { 'x-autoflow-token': runtime.sidecar.token } })
    const bytes = Buffer.from(await response.arrayBuffer())
    assert.equal(response.status, 200)
    assert.deepEqual(bytes, content)
    assert.equal(createHash('sha256').update(bytes).digest('hex'), artifacts.items[0].sha256)
    const logs = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/logs?pageSize=100`)
    assert.ok(!JSON.stringify(logs).includes('secret'))
    await click(main, '查看任务')
    await click(main, '异常与证据', '[role="tab"]')
    await waitFor(main, "document.body?.innerText.includes('文件与图片产物')", 'project SSH artifact')
    await capture(main, join(evidenceDir, 'project-ssh-task.png'))
    assert.deepEqual(cloakProcesses(userData), [])
    await api(runtime, `/credentials/${encodeURIComponent(credentialName)}`, { method: 'DELETE' })
    sshCredential = undefined
    const sshCleanup = await waitForValue(async () => {
      const state = JSON.parse(await readFile(join(userData, 'ssh-status.json'), 'utf8'))
      return state.connections > 0 && state.activeConnections === 0 && state.commands.length === 1 && state.commands.every(code => code === 0) ? state : null
    }, 'SSH connections and remote command cleanup', 5_000)
    checkpoint('项目任务真实 SSH 命令和 SFTP 文件往返完成；下载产物、变量与日志可查，连接及进程已清理')
    const report = { evidenceId: 'BE-project-ssh-formal-electron', result: 'passed', checkedAt: new Date().toISOString(), gitHead, platform: `${process.platform}-${process.arch}`, entry: desktop.packaged ? 'packaged-directory' : 'development-build', projectId, workflowId: saved.id, batchId: batch.batchId, taskId: task.taskId, checks, sshCleanup, sha256: createHash('sha256').update(content).digest('hex'), boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browserStarted: false, server: 'real loopback SSH/SFTP', interaction: 'formal Electron mouse/keyboard; APIs only fixture setup and evidence reads' } }
    await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
    console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
    throw new EvidenceComplete()
  }
  if (projectElementChangeOnly) {
    const name = '项目网页元素变化任务验收'
    const fixturePath = join(userData, 'element-change.html')
    await newWorkflow(studio, name)
    await showBlockView(studio)
    await addBlock(studio, '添加模块', '打开网页')
    await setInput(studio, 'input[placeholder="https://example.com"]', pathToFileURL(fixturePath).href)
    await addBlock(studio, '添加模块', '元素变化触发器')
    await setInput(studio, '[placeholder="如: .comment-list 或 #messages"]', '#list')
    await setVariableNameInput(studio, '[placeholder="new_element_selector"]', 'new_selector')
    await setVariableNameInput(studio, '[placeholder="element_change_info"]', 'change_info')
    await addBlock(studio, '添加模块', '打印日志')
    await setInput(studio, '[placeholder="要打印的日志信息"]', "检测到: {change_info['newElementText']}")
    await click(studio, '保存')
    const saved = await waitForValue(async () => (await api(runtime, `/workflows?projectId=${projectId}`)).find(item => item.name === name), 'project DOM watcher saved', 15_000)
    assert.deepEqual(saved.nodes.map(node => node.data.moduleType), ['open_page', 'element_change_trigger', 'print_log'])
    assert.equal(saved.nodes[1].data.selector, '#list')
    assert.equal(saved.edges.length, 2)
    await closeWindowThroughOs()
    studio.close(); studio = undefined
    await waitForNoStudio(desktop.debugOrigin)
    checkpoint('正式 Studio 真实 UI 编排网页、元素变化监听和后继变量日志，保存后正常关窗')
    await click(main, '新建自动化')
    await setInput(main, '[aria-label="自动化名称"]', '项目网页监听自动化')
    await selectAutomationWorkflow(main, name, saved.id)
    await click(main, '保存配置')
    await waitFor(main, "document.body?.innerText.includes('自动化已创建')", 'DOM watcher automation')
    const tasks = []
    for (const action of ['mutation', 'stop']) {
      await writeFile(fixturePath, '<!doctype html><meta charset="utf-8"><div id="list"><span>初始</span></div>' + (action === 'mutation' ? "<script>setInterval(()=>{const p=document.createElement('p');p.id='added';p.textContent='新增内容';document.querySelector('#list').appendChild(p)},1000)</script>" : ''))
      if (tasks.length) {
        await click(main, '自动化', '[aria-label="项目功能"] button,[aria-label="项目功能"] [role="tab"]')
        await click(main, '打开')
      }
      await click(main, '启动运行')
      await waitFor(main, "document.body?.innerText.includes('启动自动化')", 'DOM watcher batch dialog')
      await click(main, '启动 1 个任务')
      await waitFor(main, "document.body?.innerText.includes('本批次任务')", 'DOM watcher batch')
      const batch = (await api(runtime, `/v1/projects/${projectId}/batches?pageSize=20`)).items[0]
      const task = await waitForValue(async () => (await api(runtime, `/v1/projects/${projectId}/tasks?batchId=${batch.batchId}`)).items[0], 'DOM watcher task', 10_000)
      if (action === 'stop') {
        await waitForValue(async () => (await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/node-attempts?pageSize=100`)).items.some(item => item.nodeId === saved.nodes[1].id && item.status === 'running'), 'real DOM observer waiting', 30_000)
        await click(main, '停止批次')
        await click(main, '确认停止')
      }
      const terminal = await waitForValue(async () => { const value = await api(runtime, `/v1/projects/${projectId}/batches/${batch.batchId}`); return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.batch.status) ? value : null }, 'DOM watcher terminal', 40_000)
      const outputs = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/outputs?pageSize=100`)
      const attempts = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/node-attempts?pageSize=100`)
      const taskDetail = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}`)
      await writeFile(join(evidenceDir, `task-${action}.json`), JSON.stringify({ terminal, taskDetail, attempts, outputs }, null, 2) + '\n')
      if (action === 'mutation') {
        assert.equal(terminal.statusCounts.succeeded, 1, JSON.stringify({ terminal, attempts }))
        const values = Object.fromEntries(outputs.items.map(item => [item.name, item.value]))
        assert.equal(values.new_selector, '#added')
        assert.equal(values.change_info.addedCount, 1)
        assert.equal(values.change_info.newElementText, '新增内容')
        assert.equal(attempts.items.filter(item => item.status === 'succeeded').length, 3)
        const logs = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/logs?pageSize=100`)
        assert.ok(logs.items.some(item => item.message === '检测到: 新增内容'), JSON.stringify(logs))
      } else {
        assert.equal(terminal.statusCounts.cancelled, 1, JSON.stringify({ terminal, taskDetail, attempts }))
        assert.equal(outputs.items.length, 0)
        assert.equal(attempts.items.length, 2)
      }
      assert.deepEqual(cloakProcesses(userData), [])
      await waitForValue(async () => {
        const detail = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}`)
        return detail.cleanup.status === 'succeeded' ? detail : null
      }, 'terminal environment copy cleanup', 40_000)
      const copies = sqliteRows(join(userData, 'data', 'autoflow.sqlite3'), `SELECT id,state FROM project_environment_instances WHERE active_task_id=${sqlLiteral(task.taskId)}`)
      assert.equal(copies.length, 1)
      assert.equal(copies[0].state, 'cleaned')
      await assert.rejects(stat(join(userData, 'workspace', 'environments', 'instances', copies[0].id)), { code: 'ENOENT' })
      tasks.push({ action, batchId: batch.batchId, taskId: task.taskId, environmentInstanceId: copies[0].id, cleanup: 'succeeded' })
      await click(main, '查看任务')
      await waitFor(main, "document.body?.innerText.includes('临时环境已清理，无法再保留此工作副本') && ![...document.querySelectorAll('button')].some(el => el.textContent === '结束并保留')", 'cleanup displayed without invalid retention action')
      await click(main, '输入与输出', '[role="tab"]')
      await main.command('Input.dispatchMouseEvent', { type: 'mouseWheel', x: 1150, y: 800, deltaX: 0, deltaY: 300 })
      await wait(150)
      await capture(main, join(evidenceDir, `element-change-${action}.png`))
    }
    checkpoint('项目真实 CloakBrowser 监听 DOM 变化并持久化双输出和后继日志；再次运行监听中真实 UI 停止、无后继且浏览器清理')
    const report = { evidenceId: 'BE-project-element-change-formal-electron', result: 'passed', checkedAt: new Date().toISOString(), gitHead, platform: `${process.platform}-${process.arch}`, entry: desktop.packaged ? 'packaged-directory' : 'development-build', projectId, workflowId: saved.id, tasks, checks, boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browser: 'real CloakBrowser, project default Profile', interaction: 'formal UI mouse/keyboard; local controlled page; API setup and evidence reads only' } }
    await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
    console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
    throw new EvidenceComplete()
  }
  if (projectFileWatcherOnly) {
    const name = '项目文件监控任务验收'
    const watched = join(userData, 'watched')
    await mkdir(watched)
    await newWorkflow(studio, name)
    await showBlockView(studio)
    await addBlock(studio, '添加模块', '文件监控触发器')
    await setInput(studio, 'input[placeholder^="如: C:"]', watched)
    await setInput(studio, '[placeholder="如: *.txt 或 report_*.xlsx"]', '*.txt')
    await setVariableNameInput(studio, '[placeholder="如: file_event"]', 'changed_file')
    await addBlock(studio, '添加模块', '打印日志')
    await setInput(studio, '[placeholder="要打印的日志信息"]', "收到文件: {changed_file['fileName']}")
    await click(studio, '保存')
    const saved = await waitForValue(async () => (await api(runtime, `/workflows?projectId=${projectId}`)).find(item => item.name === name), 'project file watcher saved', 15_000)
    assert.deepEqual(saved.nodes.map(node => node.data.moduleType), ['file_watcher_trigger', 'print_log'])
    assert.equal(saved.nodes[0].data.watchPath, watched)
    assert.equal(saved.nodes[0].data.saveToVariable, 'changed_file')
    assert.equal(saved.edges.length, 1)
    await closeWindowThroughOs()
    studio.close(); studio = undefined
    await waitForNoStudio(desktop.debugOrigin)
    checkpoint('正式 Studio 真实 UI 编排监控路径、文件模式、输出变量和后继日志，保存后正常关闭')
    await click(main, '新建自动化')
    await setInput(main, '[aria-label="自动化名称"]', '项目文件监控自动化')
    await selectAutomationWorkflow(main, name, saved.id)
    await click(main, '保存配置')
    await waitFor(main, "document.body?.innerText.includes('自动化已创建')", 'file watcher automation')
    const tasks = []
    for (const action of ['created', 'stop']) {
      if (tasks.length) {
        await click(main, '自动化', '[aria-label="项目功能"] button,[aria-label="项目功能"] [role="tab"]')
        await click(main, '打开')
      }
      await click(main, '启动运行')
      await waitFor(main, "document.body?.innerText.includes('启动自动化')", 'file watcher batch dialog')
      await click(main, '启动 1 个任务')
      await waitFor(main, "document.body?.innerText.includes('本批次任务')", 'file watcher batch')
      const batch = (await api(runtime, `/v1/projects/${projectId}/batches?pageSize=20`)).items[0]
      const task = await waitForValue(async () => (await api(runtime, `/v1/projects/${projectId}/tasks?batchId=${batch.batchId}`)).items[0], 'file watcher task', 10_000)
      await waitForValue(async () => (await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/node-attempts?pageSize=100`)).items.some(item => item.status === 'running'), 'file watcher started', 15_000)
      await wait(1200)
      if (action === 'created') {
        await writeFile(join(watched, 'ignored.log'), 'ignore')
        await wait(1200)
        const active = await api(runtime, `/v1/projects/${projectId}/batches/${batch.batchId}`)
        assert.equal(active.statusCounts.succeeded, 0)
        await writeFile(join(watched, '目标.txt'), 'created')
      } else {
        await click(main, '停止批次')
        await click(main, '确认停止')
      }
      const terminal = await waitForValue(async () => { const value = await api(runtime, `/v1/projects/${projectId}/batches/${batch.batchId}`); return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.batch.status) ? value : null }, 'file watcher terminal', 20_000)
      const attempts = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/node-attempts?pageSize=100`)
      const outputs = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/outputs?pageSize=100`)
      if (action === 'created') {
        assert.equal(terminal.statusCounts.succeeded, 1)
        assert.equal(attempts.items.filter(item => item.status === 'succeeded').length, 2)
        const result = outputs.items.find(item => item.name === 'changed_file')?.value
        assert.equal(result?.eventType, 'created')
        assert.equal(result?.fileName, '目标.txt')
        assert.equal(result?.filePath, join(watched, '目标.txt'))
        const logs = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/logs?pageSize=100`)
        assert.ok(logs.items.some(item => item.message === '收到文件: 目标.txt'), JSON.stringify(logs))
      } else {
        assert.equal(terminal.statusCounts.cancelled, 1)
        assert.equal(outputs.items.length, 0)
        assert.equal(attempts.items.length, 1)
      }
      tasks.push({ action, batchId: batch.batchId, taskId: task.taskId })
      await click(main, '查看任务')
      await click(main, '输入与输出', '[role="tab"]')
      await main.command('Input.dispatchMouseEvent', { type: 'mouseWheel', x: 1150, y: 800, deltaX: 0, deltaY: 300 })
      await wait(150)
      await capture(main, join(evidenceDir, `file-watcher-${action}.png`))
    }
    assert.deepEqual(cloakProcesses(userData), [])
    checkpoint('项目真实文件事件持久化并执行后继日志，通配符排除无关文件；再次运行经真实 UI 停止且无后继输出')
    const report = { evidenceId: 'BE-project-file-watcher-formal-electron', result: 'passed', checkedAt: new Date().toISOString(), gitHead, platform: `${process.platform}-${process.arch}`, entry: desktop.packaged ? 'packaged-directory' : 'development-build', projectId, workflowId: saved.id, tasks, checks, boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browserStarted: false, interaction: 'formal UI mouse/keyboard; filesystem events are local fixtures; API setup and evidence reads only' } }
    await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
    console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
    throw new EvidenceComplete()
  }
  if (projectProcessOnly) {
    const name = '项目命令与 Python 任务验收'
    const code = "import sys, os\nprint('脚本乙')\nprint('诊断丙', file=sys.stderr)\nreturn dict(command=vars.command_output, value=42, stdin=sys.stdin.read(), inherited=[name for name in ['AUTOFLOW_INSTANCE_TOKEN', 'AUTOFLOW_HOST_TOKEN'] if name in os.environ])"
    await newWorkflow(studio, name)
    await showBlockView(studio)
    await addBlock(studio, '添加模块', '执行命令')
    await setInput(studio, '[placeholder="要执行的命令，支持 {变量名}"]', "printf '命令甲'")
    await setVariableNameInput(studio, '[placeholder="存储命令输出的变量名"]', 'command_output')
    await addBlock(studio, '添加模块', 'Python脚本')
    await click(studio, '打开代码编辑器', 'div')
    await waitFor(studio, "document.body?.innerText.includes('Python 代码编辑器')", 'Python code editor')
    await click(studio, '', '.monaco-editor .view-lines')
    await studio.command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'a', code: 'KeyA', windowsVirtualKeyCode: 65, modifiers: 4, commands: ['selectAll'] })
    await studio.command('Input.dispatchKeyEvent', { type: 'keyUp', key: 'a', code: 'KeyA', windowsVirtualKeyCode: 65, modifiers: 4 })
    await studio.command('Input.insertText', { text: code })
    await click(studio, '保存', 'div.fixed button')
    await waitFor(studio, "!document.body?.innerText.includes('Python 代码编辑器')", 'Python editor saved')
    for (const [field, variable] of [['result', 'answer'], ['stdout', 'stdout'], ['stderr', 'stderr'], ['return_code', 'exit_code']]) {
      await setVariableNameInput(studio, `input[placeholder="${field}"]`, variable)
    }
    await click(studio, '保存')
    const saved = await waitForValue(async () => (await api(runtime, `/workflows?projectId=${projectId}`)).find(item => item.name === name), 'project process saved', 15_000)
    assert.deepEqual(saved.nodes.map(node => node.data.moduleType), ['run_command', 'python_script'])
    assert.equal(saved.nodes[1].data.scriptContent, code)
    assert.notEqual(saved.nodes[1].data.useBuiltinPython, false)
    assert.equal(saved.edges.length, 1)
    await closeWindowThroughOs()
    studio.close(); studio = undefined
    await waitForNoStudio(desktop.debugOrigin)
    checkpoint('正式 Studio 真实 UI 编排命令和内置 Python，代码编辑器输入及保存内容一致，正常关闭工作台')
    await click(main, '新建自动化')
    await setInput(main, '[aria-label="自动化名称"]', '项目脚本自动化')
    await selectAutomationWorkflow(main, name, saved.id)
    await click(main, '保存配置')
    await waitFor(main, "document.body?.innerText.includes('自动化已创建')", 'project process automation')
    await click(main, '启动运行')
    await waitFor(main, "document.body?.innerText.includes('启动自动化')", 'project process batch dialog')
    await click(main, '启动 1 个任务')
    await waitFor(main, "document.body?.innerText.includes('本批次任务')", 'project process batch')
    const batch = (await api(runtime, `/v1/projects/${projectId}/batches?pageSize=20`)).items[0]
    const terminal = await waitForValue(async () => { const value = await api(runtime, `/v1/projects/${projectId}/batches/${batch.batchId}`); return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.batch.status) ? value : null }, 'project process terminal', 90_000)
    const task = (await api(runtime, `/v1/projects/${projectId}/tasks?batchId=${batch.batchId}`)).items[0]
    const attempts = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/node-attempts?pageSize=100`)
    assert.equal(terminal.statusCounts.succeeded, 1, JSON.stringify({ terminal, task, attempts }))
    assert.equal(attempts.items.filter(item => item.status === 'succeeded').length, 2)
    const outputs = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/outputs?pageSize=100`)
    assert.deepEqual(Object.fromEntries(outputs.items.map(item => [item.name, item.value])), { command_output: '命令甲', stdout: '脚本乙', stderr: '诊断丙', exit_code: 0, answer: { command: '命令甲', value: 42, stdin: '', inherited: [] } })
    await click(main, '查看任务')
    await click(main, '输入与输出', '[role="tab"]')
    await waitFor(main, "document.body?.innerText.includes('脚本乙') && document.body.innerText.includes('诊断丙')", 'project persisted script outputs')
    await main.command('Input.dispatchMouseEvent', { type: 'mouseWheel', x: 1150, y: 800, deltaX: 0, deltaY: 380 })
    await wait(150)
    await capture(main, join(evidenceDir, 'project-process-task.png'))
    assert.deepEqual(cloakProcesses(userData), [])
    checkpoint('真实命令输出传入内置 Python；stdout、stderr、退出码和返回对象完整持久化，任务页可查')
    const report = { evidenceId: 'BE-project-process-formal-electron', result: 'passed', checkedAt: new Date().toISOString(), gitHead, platform: `${process.platform}-${process.arch}`, entry: desktop.packaged ? 'packaged-directory' : 'development-build', projectId, workflowId: saved.id, batchId: batch.batchId, taskId: task.taskId, checks, boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browserStarted: false, python: 'built-in runtime, no external interpreter path', interaction: 'formal UI mouse/keyboard; API fixture setup and evidence reads only' } }
    await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
    console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
    throw new EvidenceComplete()
  }
  if (projectFirecrawlOnly) {
    const name = '项目网页采集任务验收'
    await newWorkflow(studio, name)
    await showBlockView(studio)
    for (const [label, variable] of [['AI单页数据抓取', 'scraped'], ['AI网站链接抓取', 'links'], ['AI全站数据抓取', 'pages']]) {
      await addBlock(studio, '添加模块', label)
      await setInput(studio, '[placeholder="https://example.com，支持 {变量名}"]', `${httpOrigin}/crawl/start`)
      await setVariableNameInput(studio, '#variableName', variable)
      if (variable === 'scraped') {
        await setInput(studio, '#timeout', '60000')
        await click(studio, 'HTML', 'span')
        await click(studio, 'Screenshot', 'span')
      } else if (variable === 'links') {
        await setInput(studio, '[placeholder="只返回包含关键词的链接，支持 {变量名}"]', '/crawl/')
        await selectNative(studio, '#ignoreSitemap', '否')
      } else {
        await setInput(studio, '#maxDepth', '1')
        await setInput(studio, '#limit', '2')
        await selectNative(studio, '#ignoreSitemap', '是')
      }
    }
    await click(studio, '保存')
    const saved = await waitForValue(async () => (await api(runtime, `/workflows?projectId=${projectId}`)).find(item => item.name === name), 'project crawl saved', 15_000)
    assert.deepEqual(saved.nodes.map(node => node.data.moduleType), ['firecrawl_scrape', 'firecrawl_map', 'firecrawl_crawl'])
    assert.equal(saved.nodes[1].data.ignoreSitemap, false)
    assert.equal(saved.nodes[2].data.ignoreSitemap, true)
    assert.equal(saved.edges.length, 2)
    checkpoint('正式 Studio 真实 UI 配置三类网页采集，保存到项目并正常关闭工作台')
    await closeWindowThroughOs()
    studio.close(); studio = undefined
    await waitForNoStudio(desktop.debugOrigin)
    await click(main, '新建自动化')
    await setInput(main, '[aria-label="自动化名称"]', '项目网页采集自动化')
    await selectAutomationWorkflow(main, name, saved.id)
    await click(main, '保存配置')
    await waitFor(main, "document.body?.innerText.includes('自动化已创建')", 'project crawl automation')
    await click(main, '启动运行')
    await waitFor(main, "document.body?.innerText.includes('启动自动化')", 'project crawl batch dialog')
    await click(main, '启动 1 个任务')
    await waitFor(main, "document.body?.innerText.includes('本批次任务')", 'project crawl batch')
    const batch = (await api(runtime, `/v1/projects/${projectId}/batches?pageSize=20`)).items[0]
    let sawBrowser = false
    const terminal = await waitForValue(async () => {
      sawBrowser ||= cloakProcesses(userData).length > 0
      const value = await api(runtime, `/v1/projects/${projectId}/batches/${batch.batchId}`)
      return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.batch.status) ? value : null
    }, 'project crawl terminal', 120_000)
    const task = (await api(runtime, `/v1/projects/${projectId}/tasks?batchId=${batch.batchId}`)).items[0]
    const attempts = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/node-attempts?pageSize=100`)
    assert.equal(terminal.statusCounts.succeeded, 1, JSON.stringify({ terminal, task, attempts }))
    assert.equal(attempts.items.filter(item => item.status === 'succeeded').length, 3)
    assert.ok(sawBrowser)
    const outputs = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/outputs?pageSize=100`)
    const values = Object.fromEntries(outputs.items.map(item => [item.name, item.value]))
    assert.ok(values.scraped.markdown.includes('项目采集正文'))
    assert.ok(!values.scraped.html.includes('<nav>'))
    assert.ok(!values.scraped.html.includes('must-not-be-extracted'))
    assert.deepEqual(values.links, [`${httpOrigin}/crawl/child`, `${httpOrigin}/crawl/from-map`])
    assert.deepEqual(values.pages.map(item => item.url), [`${httpOrigin}/crawl/start`, `${httpOrigin}/crawl/child`])
    const artifacts = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/artifacts?pageSize=100`)
    assert.equal(artifacts.total, 1)
    const response = await fetch(`${runtime.sidecar.baseUrl}${artifacts.items[0].contentUrl}`, { headers: { 'x-autoflow-token': runtime.sidecar.token } })
    assert.equal(response.status, 200)
    const bytes = Buffer.from(await response.arrayBuffer())
    assert.deepEqual([...bytes.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10])
    assert.equal(createHash('sha256').update(bytes).digest('hex'), artifacts.items[0].sha256)
    assert.ok(httpRequests.some(item => item[1] === '/sitemap.xml'))
    await click(main, '查看任务')
    await click(main, '异常与证据', '[role="tab"]')
    await waitFor(main, "[...document.querySelectorAll('h3')].some(el=>el.textContent==='节点输出截图')", 'result screenshot title')
    assert.ok(!(await main.evaluate("[...document.querySelectorAll('h3')].some(el=>el.textContent==='失败时页面截图')")))
    await waitFor(main, "document.body?.innerText.includes('已清理')", 'work copy cleanup displayed', 40_000)
    await capture(main, join(evidenceDir, 'project-firecrawl-task.png'))
    assert.deepEqual(cloakProcesses(userData), [])
    checkpoint('项目默认 Profile 启动真实 CloakBrowser；三类结果及 PNG 完整登记，浏览器清理完成')
    const report = { evidenceId: 'BE-project-firecrawl-formal-electron', result: 'passed', checkedAt: new Date().toISOString(), gitHead, platform: `${process.platform}-${process.arch}`, entry: desktop.packaged ? 'packaged-directory' : 'development-build', projectId, workflowId: saved.id, batchId: batch.batchId, taskId: task.taskId, checks, httpRequests, boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browser: 'real CloakBrowser', interaction: 'formal UI mouse/keyboard; API fixture setup and evidence reads only' } }
    await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
    console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
    throw new EvidenceComplete()
  }
  if (projectBase64Only) {
    const name = '项目 Base64 全模式任务验收'
    const inputPath = join(userData, 'base64-input.txt')
    const outputPath = join(userData, 'decoded')
    await writeFile(inputPath, '文件甲')
    await newWorkflow(studio, name)
    await showBlockView(studio)
    for (const [mode, valueField, value, variable] of [
      ['文本编码为Base64', '要编码的文本，支持 {变量名}', '文本乙', 'encoded'],
      ['Base64解码为文本', '要解码的Base64字符串，支持 {变量名}', '{encoded}', 'decoded'],
      ['文件转Base64', '选择要转换的文件，支持 {变量名}', inputPath, 'file_data'],
      ['Base64转文件', 'Base64编码的数据，支持 {变量名}', '{file_data}', 'file_path'],
    ]) {
      await addBlock(studio, '添加模块', 'Base64编解码')
      await selectNative(studio, '#operation', mode)
      await setInput(studio, `[placeholder="${valueField}"]`, value)
      await setVariableNameInput(studio, '#variableName', variable)
      if (variable === 'file_path') {
        await setInput(studio, '[placeholder="文件保存目录，支持 {变量名}"]', outputPath)
        await setInput(studio, '[placeholder="output.png，支持 {变量名}"]', 'output.txt')
      }
    }
    await click(studio, '保存')
    const saved = await waitForValue(async () => (await api(runtime, `/workflows?projectId=${projectId}`)).find(item => item.name === name), 'project base64 saved', 15_000)
    assert.equal(saved.nodes.length, 4)
    assert.equal(saved.edges.length, 3)
    assert.deepEqual(saved.nodes.map(node => node.data.operation ?? 'encode'), ['encode', 'decode', 'file_to_base64', 'base64_to_file'])
    checkpoint('正式 Studio 真实 UI 配置 Base64 文本编码、解码、文件读取和文件写入四模式并保存')
    await closeWindowThroughOs()
    studio.close(); studio = undefined
    await waitForNoStudio(desktop.debugOrigin)
    await click(main, '新建自动化')
    await setInput(main, '[aria-label="自动化名称"]', '项目 Base64 自动化')
    await selectAutomationWorkflow(main, name, saved.id)
    await click(main, '保存配置')
    await waitFor(main, "document.body?.innerText.includes('自动化已创建')", 'project base64 automation')
    await click(main, '启动运行')
    await waitFor(main, "document.body?.innerText.includes('启动自动化')", 'project base64 batch dialog')
    await click(main, '启动 1 个任务')
    await waitFor(main, "document.body?.innerText.includes('本批次任务')", 'project base64 batch')
    const batch = (await api(runtime, `/v1/projects/${projectId}/batches?pageSize=20`)).items[0]
    const terminal = await waitForValue(async () => { const value = await api(runtime, `/v1/projects/${projectId}/batches/${batch.batchId}`); return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.batch.status) ? value : null }, 'project base64 terminal', 30_000)
    const task = (await api(runtime, `/v1/projects/${projectId}/tasks?batchId=${batch.batchId}`)).items[0]
    assert.equal(terminal.statusCounts.succeeded, 1, JSON.stringify({ terminal, task }))
    const outputs = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/outputs?pageSize=100`)
    const values = Object.fromEntries(outputs.items.map(item => [item.name, item.value]))
    assert.equal(values.encoded, Buffer.from('文本乙').toString('base64'))
    assert.equal(values.decoded, '文本乙')
    assert.equal(values.file_data, 'data:text/plain;base64,' + Buffer.from('文件甲').toString('base64'))
    assert.equal(await readFile(values.file_path, 'utf8'), '文件甲')
    const artifacts = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/artifacts?pageSize=100`)
    assert.equal(artifacts.total, 1)
    const response = await fetch(`${runtime.sidecar.baseUrl}${artifacts.items[0].contentUrl}`, { headers: { 'x-autoflow-token': runtime.sidecar.token } })
    assert.equal(response.status, 200)
    assert.equal(await response.text(), '文件甲')
    await click(main, '查看任务')
    await click(main, '异常与证据', '[role="tab"]')
    await capture(main, join(evidenceDir, 'project-base64-task.png'))
    assert.deepEqual(cloakProcesses(userData), [])
    checkpoint('项目任务真实完成四模式，文本往返一致，文件产物和下载内容一致，无浏览器占用')
    const report = { evidenceId: 'BE-project-base64-formal-electron', result: 'passed', checkedAt: new Date().toISOString(), gitHead, platform: `${process.platform}-${process.arch}`, entry: desktop.packaged ? 'packaged-directory' : 'development-build', projectId, workflowId: saved.id, batchId: batch.batchId, taskId: task.taskId, checks, boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browserStarted: false, interaction: 'formal UI mouse/keyboard; API fixture setup and evidence reads only' } }
    await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
    console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
    throw new EvidenceComplete()
  }
  if (projectTimingOnly) {
    const name = '项目定时概率分支任务验收'
    await newWorkflow(studio, name)
    const timer = await addCanvasNode(studio, '定时任务', { xRatio: 0.1, yRatio: 0.2 })
    await setInput(studio, '[placeholder="YYYY-MM-DD，如 2026-01-01"]', '2000-01-01')
    await setInput(studio, '[placeholder="HH:MM 或 HH:MM:SS，如 09:30"]', '00:00')
    const choice = await addCanvasNode(studio, '概率触发器', { xRatio: 0.45, yRatio: 0.2 })
    await setInput(studio, 'input[inputmode="numeric"]', '100')
    const first = await addCanvasNode(studio, '打印日志', { xRatio: 0.05, yRatio: 0.67 })
    await setInput(studio, '[placeholder="要打印的日志信息"]', '选择路径一')
    const second = await addCanvasNode(studio, '打印日志', { xRatio: 0.5, yRatio: 0.67 })
    await setInput(studio, '[placeholder="要打印的日志信息"]', '选择路径二')
    await connectNodes(studio, timer, choice)
    await connectNodes(studio, choice, first, 'path1')
    await connectNodes(studio, choice, second, 'path2')
    await click(studio, '保存')
    const saved = await waitForValue(async () => (await api(runtime, `/workflows?projectId=${projectId}`)).find(item => item.name === name), 'project timer saved', 15_000)
    assert.equal(saved.nodes.length, 4)
    assert.equal(saved.edges.length, 3)
    assert.deepEqual(saved.edges.filter(edge => edge.source === choice).map(edge => edge.sourceHandle).sort(), ['path1', 'path2'])
    checkpoint('正式 Studio 真实 UI 配置日期等待、概率及两个分支连线并保存项目流程')
    await closeWindowThroughOs()
    studio.close(); studio = undefined
    await waitForNoStudio(desktop.debugOrigin)
    await click(main, '新建自动化')
    await setInput(main, '[aria-label="自动化名称"]', '项目定时概率自动化')
    await selectAutomationWorkflow(main, name, saved.id)
    await click(main, '保存配置')
    await waitFor(main, "document.body?.innerText.includes('自动化已创建')", 'project timer automation')
    await click(main, '启动运行')
    await waitFor(main, "document.body?.innerText.includes('启动自动化')", 'project timer batch dialog')
    await click(main, '启动 1 个任务')
    await waitFor(main, "document.body?.innerText.includes('本批次任务')", 'project timer batch')
    const batch = (await api(runtime, `/v1/projects/${projectId}/batches?pageSize=20`)).items[0]
    const terminal = await waitForValue(async () => { const value = await api(runtime, `/v1/projects/${projectId}/batches/${batch.batchId}`); return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.batch.status) ? value : null }, 'project timer terminal', 30_000)
    const task = (await api(runtime, `/v1/projects/${projectId}/tasks?batchId=${batch.batchId}`)).items[0]
    assert.equal(terminal.statusCounts.succeeded, 1, JSON.stringify({ terminal, task }))
    const attempts = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/node-attempts?pageSize=100`)
    assert.deepEqual(attempts.items.filter(item => item.status === 'succeeded').map(item => item.nodeId).sort(), [timer, choice, first].sort())
    assert.ok(!attempts.items.some(item => item.nodeId === second))
    const logs = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/logs?pageSize=100`)
    assert.ok(logs.items.some(item => item.message === '选择路径一'))
    assert.ok(!logs.items.some(item => item.message === '选择路径二'))
    await click(main, '查看任务')
    await capture(main, join(evidenceDir, 'project-timing-task.png'))
    assert.deepEqual(cloakProcesses(userData), [])
    checkpoint('项目任务读取保存图并真实执行定时器和概率路径一；路径二没有日志或执行记录，无浏览器占用')
    const report = { evidenceId: 'BE-project-timing-formal-electron', result: 'passed', checkedAt: new Date().toISOString(), gitHead, platform: `${process.platform}-${process.arch}`, entry: desktop.packaged ? 'packaged-directory' : 'development-build', projectId, workflowId: saved.id, batchId: batch.batchId, taskId: task.taskId, checks, boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browserStarted: false, interaction: 'formal UI mouse/keyboard; API fixture setup and evidence reads only' } }
    await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
    console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
    throw new EvidenceComplete()
  }
  if (projectFamilyOnly) {
    const name = projectMathOnly ? '项目列表与数学任务验收' : projectUtilityOnly ? '项目实用工具任务验收' : projectWebBasicOnly ? '项目基础网页任务验收' : projectAdvancedOnly ? '项目高级网页与产物任务验收' : projectTabSwitchOnly ? '项目标签页切换任务验收' : projectVariableOnly ? '项目变量处理任务验收' : projectListExportOnly ? '项目列表导出任务验收' : projectLogOnly ? '项目日志任务验收' : projectTableOnly ? '项目表格提取与导出任务验收' : projectHttpOnly ? '项目HTTP节点任务验收' : projectControlPrimitivesOnly ? '项目等待断言停止任务验收' : projectNetworkOnly ? '项目网页网络采集任务验收' : projectAllureOnly ? '项目Allure报告任务验收' : '项目页面加载任务验收'
    await newWorkflow(studio, name)
    if (projectMathOnly) await addGlobalVariable(studio, 'items', 'array', '[1,2,3]')
    if (projectVariableOnly) await addGlobalVariable(studio, 'payload', 'string', '{"items":[{"name":"甲"},{"name":"乙"}]}')
    if (projectListExportOnly) await addGlobalVariable(studio, 'items', 'array', '["甲","乙"]')
    await showBlockView(studio)
    if (projectMathOnly) {
      await addBlock(studio, '添加模块', '列表求和')
      await setInput(studio, '[placeholder="输入列表变量名"]', 'items')
      await setInput(studio, '[placeholder="保存结果的变量名"]', 'sum_value')
      await addBlock(studio, '添加模块', '四舍五入')
      await setInput(studio, '[placeholder="输入数值或变量"]', '{sum_value}')
      await setInput(studio, '[placeholder="保存结果的变量名"]', 'rounded')
      await addBlock(studio, '添加模块', '绝对值')
      await setInput(studio, '[placeholder="输入数值或变量"]', '-7')
      await setInput(studio, '[placeholder="保存结果的变量名"]', 'absolute')
    } else if (projectUtilityOnly) {
      await addBlock(studio, '添加模块', 'URL编解码')
      await setInput(studio, '[placeholder="要编码或解码的文本"]', '中文 A')
      await setInput(studio, '[placeholder="url_result"]', 'encoded')
      await addBlock(studio, '添加模块', 'MD5加密')
      await setInput(studio, '[placeholder="要加密的文本"]', '{encoded}')
      await setInput(studio, '[placeholder="md5_hash"]', 'digest')
      await addBlock(studio, '添加模块', 'SHA加密')
      await setInput(studio, '[placeholder="要加密的文本"]', '{digest}')
      await setInput(studio, '[placeholder="sha_hash"]', 'final_sha')
    } else if (projectWebBasicOnly) {
      await addBlock(studio, '添加模块', '打开网页')
      await setInput(studio, '[placeholder="https://example.com"]', pathToFileURL(join(root, 'apps/backend/tests/fixtures/workflow-page.html')).href)
      await addBlock(studio, '添加模块', '操作已打开的网页')
      await setInput(studio, '[placeholder="页面标题或URL的部分内容"]', 'AutoFlow B1 受控页面')
      await addBlock(studio, '添加模块', '等待元素')
      await setInput(studio, '[placeholder="例如: #element, .class"]', '#workflow-submit')
      await addBlock(studio, '添加模块', '悬停元素')
      await setInput(studio, '[placeholder="例如: #element, .hover-target"]', '#workflow-submit')
      await setInput(studio, '#hoverDuration', '0')
      await addBlock(studio, '添加模块', '提取数据')
      await setInput(studio, '[placeholder="例如: #title, .content"]', '#workflow-submit')
      await setInput(studio, '[placeholder="变量名"]', 'button_label')
    } else if (projectAdvancedOnly) {
      await addBlock(studio, '添加模块', '打开网页')
      await setInput(studio, '[placeholder="https://example.com"]', pathToFileURL(join(root, 'apps/backend/tests/fixtures/workflow-b2-web-actions.html')).href)
      await addBlock(studio, '添加模块', '下拉选择')
      await setInput(studio, '[placeholder="select#dropdown"]', '#choice')
      await setInput(studio, '[placeholder="要选择的值，支持 {变量名}"]', 'second')
      await addBlock(studio, '添加模块', '勾选框')
      await setInput(studio, 'input[placeholder*="checkbox"]', '#enabled')
      await addBlock(studio, '添加模块', '保存图片')
      await setInput(studio, '[placeholder="img.target"]', '#fixture-image')
      await setInput(studio, '[placeholder="保存文件路径的变量名"]', 'saved_image')
      await addBlock(studio, '添加模块', '下载文件')
      await setInput(studio, '[placeholder="a.download-btn"]', '#download-link')
      await setInput(studio, '[placeholder="保存文件路径的变量名"]', 'downloaded_file')
      await addBlock(studio, '添加模块', '获取子元素')
      await setInput(studio, '[placeholder="div.parent"]', '#children')
      await setInput(studio, '[placeholder="存储子元素选择器列表的变量名"]', 'children')
    } else if (projectTabSwitchOnly) {
      await addBlock(studio, '添加模块', '打开网页')
      await setInput(studio, '[placeholder="https://example.com"]', pathToFileURL(join(root, 'apps/backend/tests/fixtures/workflow-page.html')).href)
      await selectNative(studio, '#openMode', '当前标签页')
      await addBlock(studio, '添加模块', '打开网页')
      await setInput(studio, '[placeholder="https://example.com"]', pathToFileURL(join(root, 'apps/backend/tests/fixtures/workflow-b2-web-actions.html')).href)
      await addBlock(studio, '添加模块', '切换标签页')
      await selectNative(studio, '#switchMode', '按标题切换')
      await setInput(studio, '[placeholder="输入标签页标题"]', 'AutoFlow B1 受控页面')
      await setInput(studio, '[placeholder="tab_title"]', 'first_title')
      await addBlock(studio, '添加模块', '提取数据')
      await setInput(studio, '[placeholder="例如: #title, .content"]', '#workflow-submit')
      await setInput(studio, '[placeholder="变量名"]', 'first_button')
      await addBlock(studio, '添加模块', '切换标签页')
      await selectNative(studio, '#switchMode', '切换到最后一个')
      await setInput(studio, '[placeholder="tab_title"]', 'last_title')
      await addBlock(studio, '添加模块', '提取数据')
      await setInput(studio, '[placeholder="例如: #title, .content"]', '#child-a')
      await setInput(studio, '[placeholder="变量名"]', 'last_child')
    } else if (projectVariableOnly) {
      await addBlock(studio, '添加模块', 'JSON解析')
      await setInput(studio, '[placeholder="填写变量名，如: jsonData"]', 'payload')
      await setInput(studio, '[placeholder="$.data.items[0].name，支持 {变量名}"]', '$.items[1].name')
      await setVariableNameInput(studio, '#variableName', 'parsed')
      await addBlock(studio, '添加模块', '随机数')
      await setInput(studio, '[placeholder="最小值，支持 {变量名}"]', '7')
      await setInput(studio, '[placeholder="最大值，支持 {变量名}"]', '7')
      await setVariableNameInput(studio, '#variableName', 'pick')
      await addBlock(studio, '添加模块', '获取时间')
      await selectNative(studio, '#timeFormat', '仅日期')
      await setVariableNameInput(studio, '#variableName', 'today')
    } else if (projectListExportOnly) {
      await addBlock(studio, '添加模块', '列表导出')
      await setInput(studio, '#listVariable', 'items')
      await setInput(studio, '[placeholder^="D:"]', 'exports/items.txt')
      await addBlock(studio, '添加模块', '列表导出')
      await setInput(studio, '#listVariable', 'items')
      await setInput(studio, '[placeholder^="D:"]', 'exports/items.txt')
      await selectNative(studio, '#appendMode', '追加写入')
    } else if (projectLogOnly) {
      await addBlock(studio, '添加模块', '打印日志')
      await setInput(studio, '[placeholder="要打印的日志信息"]', '业务完成')
      await selectNative(studio, '#logLevel', '成功')
      await addBlock(studio, '添加模块', '导出日志')
      await setInput(studio, '[placeholder="C:/logs/workflow_log.txt"]', 'logs/run.txt')
      await setVariableNameInput(studio, '[placeholder="export_result"]', 'log_file')
    } else if (projectTableOnly) {
      await addBlock(studio, '添加模块', '打开网页')
      await setInput(studio, '[placeholder="https://example.com"]', pathToFileURL(join(root, 'apps/backend/tests/fixtures/workflow-b2-remaining-browser.html')).href)
      await addBlock(studio, '添加模块', '表格数据提取')
      await setInput(studio, '[placeholder="例如: table, #dataTable, .data-grid"]', '#orders-table')
      await setVariableNameInput(studio, '#variableName', 'orders')
      await click(studio, '', '#exportToExcel')
      await setInput(studio, '[placeholder="留空使用默认路径 table_data.xlsx"]', 'reports/extracted.xlsx')
      await addBlock(studio, '添加模块', '添加行')
      await setInput(studio, '[placeholder*="列名1"]', '{"订单":"A-001","金额":88}')
      await addBlock(studio, '添加模块', '添加列')
      await setInput(studio, '[placeholder="新列的名称，支持 {变量名}"]', '状态')
      await setInput(studio, '[placeholder="新列的默认值，支持 {变量名}"]', '待处理')
      await addBlock(studio, '添加模块', '设置单元格')
      await setInput(studio, '[placeholder="要设置的列名，支持 {变量名}"]', '状态')
      await setInput(studio, '[placeholder="要设置的值，支持 {变量名}"]', '已完成')
      await addBlock(studio, '添加模块', '读取单元格')
      await setInput(studio, '[placeholder="要获取的列名，支持 {变量名}"]', '状态')
      await setVariableNameInput(studio, '#variableName', 'state')
      await addBlock(studio, '添加模块', '导出表格')
      await setInput(studio, '[placeholder^="C:"]', 'reports/processed.xlsx')
      await setVariableNameInput(studio, '#variableName', 'excel_path')
      await addBlock(studio, '添加模块', '导出表格')
      await selectNative(studio, '#exportFormat', 'CSV')
      await setInput(studio, '[placeholder^="C:"]', 'reports/processed.csv')
      await setVariableNameInput(studio, '#variableName', 'csv_path')
      await addBlock(studio, '添加模块', '删除行')
      await addBlock(studio, '添加模块', '清空表格')
    } else if (projectHttpOnly) {
      await addBlock(studio, '添加模块', 'API触发器')
      await setInput(studio, '[placeholder="如: https://api.example.com/status"]', `${httpOrigin}/poll`)
      await setInput(studio, '[placeholder="如: data.status 或 $.result.code"]', '$.data.status')
      await setInput(studio, '[placeholder="如: success 或 200"]', 'ready')
      await setInput(studio, '#checkInterval', '1')
      await setInput(studio, '#timeout', '5')
      await setVariableNameInput(studio, '#saveToVariable', 'trigger_data')
      await addBlock(studio, '添加模块', 'HTTP请求')
      await setInput(studio, '[placeholder^="https://api.example.com/data"]', `${httpOrigin}/api`)
      await setVariableNameInput(studio, '#variableName', 'api_result')
      await addBlock(studio, '添加模块', 'Webhook请求')
      await setInput(studio, '[placeholder="https://api.example.com/webhook"]', `${httpOrigin}/hook`)
      await setInput(studio, 'textarea[placeholder*="key"]', '{"source":"studio"}')
      await addBlock(studio, '添加模块', 'Webhook通知')
      await setInput(studio, '[placeholder="Webhook URL"]', `${httpOrigin}/notify`)
      await setInput(studio, 'textarea[placeholder*="通知内容"]', '{"message":"完成"}')
    } else if (projectControlPrimitivesOnly) {
      await addBlock(studio, '添加模块', '固定等待')
      await setInput(studio, '[placeholder="例如: 1 或 2.5"]', '0.01')
      await addBlock(studio, '添加模块', '断言/检查点')
      await setInput(studio, '[placeholder="要校验的值，支持 {变量名}"]', '42')
      await setInput(studio, '[placeholder="期望对照的值，支持 {变量名}"]', '42')
      await setVariableNameInput(studio, '[placeholder="存储断言结果布尔值，如 assert_passed"]', 'checked')
      await addBlock(studio, '添加模块', '强制停止工作流执行')
      await setInput(studio, '#stopReason', '业务结束')
      await addBlock(studio, '添加模块', '设置变量')
      await setInput(studio, '[placeholder="变量名"]', 'must_not_run')
      await setInput(studio, '[placeholder="变量的值"]', 'unexpected')
    } else if (projectAllureOnly) {
      await addBlock(studio, '添加模块', 'Allure初始化')
      await setInput(studio, '[placeholder="测试套件"]', '项目报告套件')
      await addBlock(studio, '添加模块', '开始测试用例')
      await setInput(studio, '[placeholder="测试用例"]', '项目任务用例')
      await addBlock(studio, '添加模块', '添加测试步骤')
      await setInput(studio, '[placeholder="测试步骤"]', '报告生成步骤')
      await addBlock(studio, '添加模块', '添加附件')
      const attachmentPath = join(userData, 'allure-attachment.txt')
      await writeFile(attachmentPath, '项目 Allure 附件内容', 'utf8')
      await setInput(studio, '[placeholder="C:/screenshots/test.png"]', attachmentPath)
      await setInput(studio, '[placeholder="截图"]', '项目附件')
      await addBlock(studio, '添加模块', '结束测试用例')
      await addBlock(studio, '添加模块', '生成测试报告')
      await setInput(studio, '[placeholder="./allure-report"]', 'reports')
    } else if (projectNetworkOnly) {
      await addBlock(studio, '添加模块', '打开网页')
      await setInput(studio, '[placeholder="https://example.com"]', `${httpOrigin}/network-monitor`)
      await addBlock(studio, '添加模块', '开始网络监听')
      await setInput(studio, '[placeholder="监听器唯一标识，默认: default"]', 'orders')
      await addBlock(studio, '添加模块', '点击元素')
      await setInput(studio, '[placeholder="例如: #button, .submit"]', '#request-orders')
      await addBlock(studio, '添加模块', '等待API请求')
      await setInput(studio, '[placeholder="监听器唯一标识，默认: default"]', 'orders')
      await setInput(studio, '[placeholder^="如: /api/user"]', '/api/orders')
      await setVariableNameInput(studio, '[placeholder="存储请求信息的变量名"]', 'first_request')
      await addBlock(studio, '添加模块', '停止网络监听')
      await setInput(studio, '[placeholder="监听器唯一标识，默认: default"]', 'orders')
      await setVariableNameInput(studio, '[placeholder="存储所有捕获请求的变量名"]', 'all_requests')
      await addBlock(studio, '添加模块', '网络抓包')
      await setInput(studio, '[placeholder="模糊匹配URL"]', '/api/orders')
      await setInput(studio, '#captureDuration', '4')
      await setVariableNameInput(studio, '[placeholder="存储捕获结果的变量名"]', 'captured_urls')
    } else {
      await addBlock(studio, '添加模块', '打开网页')
      await setInput(studio, '[placeholder="https://example.com"]', pathToFileURL(join(root, 'apps/backend/tests/fixtures/workflow-page.html')).href)
      await addBlock(studio, '添加模块', '等待页面加载完成')
      await addBlock(studio, '添加模块', '网页是否加载完成')
      await setInput(studio, '[placeholder="page_loaded"]', 'page_ready')
    }
    await click(studio, '保存')
    const saved = await waitForValue(async () => (await api(runtime, `/workflows?projectId=${projectId}`)).find(item => item.name === name), 'project math saved', 15_000)
    assert.ok(saved && saved.projectId === projectId)
    assert.deepEqual(saved.nodes.map(node => node.data.moduleType), projectMathOnly ? ['list_sum', 'math_round', 'math_abs'] : projectUtilityOnly ? ['url_encode_decode', 'md5_encrypt', 'sha_encrypt'] : projectWebBasicOnly ? ['open_page', 'use_opened_page', 'wait_element', 'hover_element', 'get_element_info'] : projectAdvancedOnly ? ['open_page', 'select_dropdown', 'set_checkbox', 'save_image', 'download_file', 'get_child_elements'] : projectTabSwitchOnly ? ['open_page', 'open_page', 'switch_tab', 'get_element_info', 'switch_tab', 'get_element_info'] : projectVariableOnly ? ['json_parse', 'random_number', 'get_time'] : projectListExportOnly ? ['list_export', 'list_export'] : projectLogOnly ? ['print_log', 'export_log'] : projectTableOnly ? ['open_page', 'extract_table_data', 'table_add_row', 'table_add_column', 'table_set_cell', 'table_get_cell', 'table_export', 'table_export', 'table_delete_row', 'table_clear'] : projectHttpOnly ? ['api_trigger', 'api_request', 'webhook_request', 'notify_webhook'] : projectControlPrimitivesOnly ? ['wait', 'assert_checkpoint', 'stop_workflow', 'set_variable'] : projectNetworkOnly ? ['open_page', 'network_monitor_start', 'click_element', 'network_monitor_wait', 'network_monitor_stop', 'network_capture'] : projectAllureOnly ? ['allure_init', 'allure_start_test', 'allure_add_step', 'allure_add_attachment', 'allure_stop_test', 'allure_generate_report'] : ['open_page', 'wait_page_load', 'page_load_complete'])
    if (projectTabSwitchOnly) {
      assert.equal(saved.nodes[2].data.switchMode, 'title')
      assert.equal(saved.nodes[4].data.switchMode, 'last')
    }
    if (projectVariableOnly) assert.deepEqual(saved.nodes.map(node => node.data.variableName), ['parsed', 'pick', 'today'])
    if (projectMathOnly) assert.equal(saved.nodes[1].data.resultVariable, 'rounded')
    assert.equal(saved.edges.length, projectTableOnly ? 9 : projectAllureOnly || projectNetworkOnly || projectAdvancedOnly || projectTabSwitchOnly ? 5 : projectHttpOnly || projectControlPrimitivesOnly ? 3 : projectListExportOnly || projectLogOnly ? 1 : projectWebBasicOnly ? 4 : 2)
    if (projectListExportOnly) assert.deepEqual(saved.nodes.map(node => node.data.appendMode ?? false), [false, true])
    if (projectAllureOnly) checkpoint('正式项目 Studio 经真实 UI 配置并保存 Allure 六节点、附件与报告目录')
    else if (projectNetworkOnly) checkpoint('正式项目 Studio 经真实 UI 配置并保存网页打开、网络监听、点击、请求等待、停止监听及抓包流程')
    else
    checkpoint(projectMathOnly ? '正式项目 Studio 通过真实 UI 配置并保存列表求和、四舍五入和绝对值顺序流程' : projectUtilityOnly ? '正式项目 Studio 通过真实 UI 配置并保存 URL 编码、MD5 和 SHA 顺序流程' : projectWebBasicOnly ? '正式项目 Studio 通过真实 UI 配置并保存网页打开、匹配、等待、悬停和提取顺序流程' : projectAdvancedOnly ? '正式项目 Studio 通过真实 UI 配置并保存下拉选择、勾选、图片、下载和子元素流程' : projectTabSwitchOnly ? '正式项目 Studio 通过真实 UI 配置并保存打开两个页面、按标题和最后一页切换、分别提取元素的流程' : projectVariableOnly ? '正式项目 Studio 通过真实 UI 声明变量并保存 JSON解析、随机数和时间流程' : projectListExportOnly ? '正式项目 Studio 通过真实 UI 声明列表变量并保存覆盖、追加两个列表导出节点' : projectLogOnly ? '正式项目 Studio 通过真实 UI 配置并保存打印日志与导出日志流程' : projectTableOnly ? '正式项目 Studio 通过真实 UI 配置并保存网页表格提取、数据表操作与文件导出流程' : projectHttpOnly ? '正式项目 Studio 通过真实 UI 配置并保存 API 轮询、HTTP 请求、Webhook 请求与通知流程' : projectControlPrimitivesOnly ? '正式项目 Studio 通过真实 UI 配置并保存等待、断言检查点、停止流程及停止后的步骤' : '正式项目 Studio 通过真实 UI 配置并保存页面加载等待与状态检查流程')
    await closeWindowThroughOs()
    studio.close(); studio = undefined
    await waitForNoStudio(desktop.debugOrigin)
    await click(main, '新建自动化')
    await setInput(main, '[aria-label="自动化名称"]', projectMathOnly ? '项目纯数据节点自动化' : projectUtilityOnly ? '项目工具节点自动化' : projectWebBasicOnly ? '项目基础网页节点自动化' : projectAdvancedOnly ? '项目高级网页节点自动化' : projectTabSwitchOnly ? '项目标签页节点自动化' : projectVariableOnly ? '项目变量节点自动化' : projectListExportOnly ? '项目列表导出节点自动化' : projectLogOnly ? '项目日志节点自动化' : projectTableOnly ? '项目表格节点自动化' : projectHttpOnly ? '项目HTTP节点自动化' : projectControlPrimitivesOnly ? '项目等待断言停止节点自动化' : projectNetworkOnly ? '项目网页网络采集节点自动化' : projectAllureOnly ? '项目Allure报告节点自动化' : '项目页面加载节点自动化')
    await selectAutomationWorkflow(main, name, saved.id)
    await click(main, '保存配置')
    await waitFor(main, "document.body?.innerText.includes('自动化已创建')", 'project math automation')
    await click(main, '启动运行')
    await waitFor(main, "document.body?.innerText.includes('启动自动化')", 'project math batch dialog')
    await click(main, '启动 1 个任务')
    await waitFor(main, "document.body?.innerText.includes('本批次任务')", 'project math batch')
    const sawCloakBrowser = (projectWebBasicOnly || projectPageLoadOnly || projectAdvancedOnly || projectTabSwitchOnly || projectTableOnly || projectNetworkOnly) ? await waitForValue(async () => cloakProcesses(userData).length > 0 ? true : null, 'project CloakBrowser process', 30_000) : false
    const batch = (await api(runtime, `/v1/projects/${projectId}/batches?pageSize=20`)).items[0]
    const terminal = await waitForValue(async () => { const value = await api(runtime, `/v1/projects/${projectId}/batches/${batch.batchId}`); return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.batch.status) ? value : null }, 'project family terminal', 90_000)
    const task = (await api(runtime, `/v1/projects/${projectId}/tasks?batchId=${batch.batchId}`)).items[0]
    const attempts = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/node-attempts?pageSize=100`)
    assert.equal(terminal.statusCounts.succeeded, 1, JSON.stringify({ terminal, task, attempts, variables: saved.variables, nodes: saved.nodes }))
    assert.equal(attempts.items.filter(item => item.status === 'succeeded').length, projectTableOnly ? 10 : projectHttpOnly ? 4 : projectControlPrimitivesOnly ? 3 : projectListExportOnly || projectLogOnly ? 2 : projectAdvancedOnly || projectTabSwitchOnly || projectNetworkOnly || projectAllureOnly ? 6 : projectWebBasicOnly ? 5 : 3)
    const outputs = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/outputs?pageSize=100`)
    const encoded = encodeURIComponent('中文 A')
    const digest = createHash('md5').update(encoded).digest('hex')
    const outputExpectations = projectMathOnly ? [['sum_value', 6], ['rounded', 6], ['absolute', 7]] : projectUtilityOnly ? [['encoded', encoded], ['digest', digest], ['final_sha', createHash('sha256').update(digest).digest('hex')]] : projectWebBasicOnly ? [['button_label', '确认']] : projectAdvancedOnly ? [['children', ['#child-a', '#child-b']]] : projectTabSwitchOnly ? [['first_title', 'AutoFlow B1 受控页面'], ['first_button', '确认'], ['last_title', 'AutoFlow B2 网页动作受控页面'], ['last_child', '甲']] : projectVariableOnly ? [['parsed', '乙'], ['pick', 7]] : projectControlPrimitivesOnly ? [['checked', true]] : projectNetworkOnly || projectAllureOnly ? [] : projectListExportOnly || projectLogOnly || projectTableOnly || projectHttpOnly ? [] : [['page_ready', true]]
    for (const [variable, expected] of outputExpectations) {
      assert.ok(outputs.items.some(item => item.name === variable && (Array.isArray(expected) ? JSON.stringify(item.value) === JSON.stringify(expected) : item.value === expected)), JSON.stringify({ variable, expected, outputs: outputs.items, nodes: saved.nodes }))
    }
    if (projectVariableOnly) assert.match(outputs.items.find(item => item.name === 'today')?.value ?? '', /^\d{4}-\d{2}-\d{2}$/)
    if (projectListExportOnly) {
      const artifacts = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/artifacts?pageSize=100`)
      assert.equal(artifacts.total, 2)
      assert.deepEqual(artifacts.items.map(item => item.kind), ['file', 'file'])
      for (const [index, item] of artifacts.items.entries()) {
        const response = await fetch(`${runtime.sidecar.baseUrl}${item.contentUrl}`, { headers: { 'x-autoflow-token': runtime.sidecar.token } })
        assert.equal(response.status, 200)
        const bytes = Buffer.from(await response.arrayBuffer())
        assert.equal(bytes.toString('utf8'), index === 0 ? '甲\n乙' : '甲\n乙\n甲\n乙')
        assert.equal(createHash('sha256').update(bytes).digest('hex'), item.sha256)
      }
      checkpoint('两个列表导出节点分别登记覆盖与追加的不可变文件快照，正式内容接口的字节与 SHA-256 一致')
    }
    if (projectTableOnly) {
      assert.deepEqual(outputs.items.find(item => item.name === 'orders')?.value, [['订单', '金额'], ['A-001', '88'], ['A-002', '99']])
      assert.equal(outputs.items.find(item => item.name === 'state')?.value, '已完成')
      assert.match(outputs.items.find(item => item.name === 'excel_path')?.value ?? '', /processed\.xlsx$/)
      assert.match(outputs.items.find(item => item.name === 'csv_path')?.value ?? '', /processed\.csv$/)
      const artifacts = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/artifacts?pageSize=100`)
      assert.equal(artifacts.total, 3)
      assert.deepEqual(artifacts.items.map(item => item.kind), ['file', 'file', 'file'])
      const contents = []
      for (const item of artifacts.items) {
        const response = await fetch(`${runtime.sidecar.baseUrl}${item.contentUrl}`, { headers: { 'x-autoflow-token': runtime.sidecar.token } })
        assert.equal(response.status, 200)
        const bytes = Buffer.from(await response.arrayBuffer())
        assert.equal(createHash('sha256').update(bytes).digest('hex'), item.sha256)
        contents.push(bytes)
      }
      assert.deepEqual(contents.slice(0, 2).map(bytes => bytes.subarray(0, 4).toString('hex')), ['504b0304', '504b0304'])
      assert.match(contents[2].toString('utf8'), /A-001,88,已完成/)
      checkpoint('真实 CloakBrowser 表格提取、数据表编辑及三份 XLSX/CSV 产物内容与 SHA-256 验证通过')
    }
    if (projectHttpOnly) {
      assert.deepEqual(httpRequests, [
        ['GET', '/poll', null], ['GET', '/poll', null], ['GET', '/api', null],
        ['POST', '/hook', { source: 'studio' }], ['POST', '/notify', { message: '完成' }],
      ])
      assert.deepEqual(outputs.items.find(item => item.name === 'trigger_data')?.value, { data: { status: 'ready' } })
      assert.deepEqual(outputs.items.find(item => item.name === 'api_result')?.value, { accepted: '甲' })
      checkpoint('项目真实 worker 轮询本地 API 两次后执行 HTTP、Webhook 请求和通知，输出与服务接收请求一致')
    }
    if (projectControlPrimitivesOnly) {
      assert.equal(attempts.total, 3)
      assert.ok(!attempts.items.some(item => item.nodeId === saved.nodes[3].id))
      assert.ok(!outputs.items.some(item => item.name === 'must_not_run'))
      checkpoint('断言结果持久化为布尔值；停止节点后的变量写入没有执行')
    }
    if (projectNetworkOnly) {
      const captured = outputs.items.find(item => item.name === 'captured_urls')?.value
      const first = outputs.items.find(item => item.name === 'first_request')?.value
      const all = outputs.items.find(item => item.name === 'all_requests')?.value
      assert.ok(Array.isArray(captured) && captured.length === 1 && captured[0].includes('/api/orders'))
      assert.ok(Array.isArray(all) && all.length === 1)
      assert.equal(first?.method, 'GET')
      assert.equal(first?.headers?.authorization, '[已隐藏]')
      assert.ok(httpRequests.filter(item => item[1]?.startsWith('/api/orders')).length >= 2)
      assert.ok(!JSON.stringify(outputs.items).includes('fixture-secret'))
      checkpoint('项目任务在真实 CloakBrowser 中捕获两次受控请求，三个变量和脱敏内容均可持久读取')
    }
    if (projectAllureOnly) {
      const artifacts = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/artifacts?pageSize=100`)
      assert.equal(artifacts.total, 1)
      assert.equal(artifacts.items[0].kind, 'file')
      const artifact = artifacts.items[0]
      const response = await fetch(`${runtime.sidecar.baseUrl}${artifact.contentUrl}`, { headers: { 'x-autoflow-token': runtime.sidecar.token } })
      assert.equal(response.status, 200)
      const bytes = Buffer.from(await response.arrayBuffer())
      assert.equal(createHash('sha256').update(bytes).digest('hex'), artifact.sha256)
      const html = bytes.toString('utf8')
      for (const marker of ['项目报告套件', '项目任务用例', '报告生成步骤', '项目附件']) assert.ok(html.includes(marker), marker)
      checkpoint('项目 Allure HTML 报告登记为不可变文件，正式内容接口与 SHA-256 和测试附件对应')
    }
    if (projectLogOnly) {
      const logs = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/logs?level=success`)
      assert.ok(logs.items.some(item => item.message === '业务完成' && item.isUserLog === true))
      const artifactPage = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/artifacts?pageSize=100`)
      assert.equal(artifactPage.total, 1)
      const artifact = artifactPage.items[0]
      assert.equal(artifact.kind, 'file')
      const response = await fetch(`${runtime.sidecar.baseUrl}${artifact.contentUrl}`, { headers: { 'x-autoflow-token': runtime.sidecar.token } })
      assert.equal(response.status, 200)
      const bytes = Buffer.from(await response.arrayBuffer())
      assert.match(bytes.toString('utf8'), /\[SUCCESS\] 业务完成/)
      assert.equal(createHash('sha256').update(bytes).digest('hex'), artifact.sha256)
      assert.equal(outputs.items.find(item => item.name === 'log_file')?.value?.log_count, 1)
      checkpoint('项目任务日志按成功级别可检索，导出文件及哈希与节点输出对应')
    }
    if (projectAdvancedOnly) {
      const artifacts = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/artifacts?pageSize=100`)
      assert.equal(artifacts.total, 2)
      assert.deepEqual(new Set(artifacts.items.map(item => item.kind)), new Set(['file', 'image']))
      for (const item of artifacts.items) {
        const response = await fetch(`${runtime.sidecar.baseUrl}${item.contentUrl}`, { headers: { 'x-autoflow-token': runtime.sidecar.token } })
        assert.equal(response.status, 200)
        const bytes = Buffer.from(await response.arrayBuffer())
        assert.equal(createHash('sha256').update(bytes).digest('hex'), item.sha256)
        if (item.kind === 'file') {
          assert.equal(item.fileName, 'fixture-download.txt')
          assert.equal(bytes.toString('utf8'), 'AutoFlow 下载')
        } else {
          assert.equal(item.fileName, 'saved_image.png')
          assert.equal(bytes.subarray(0, 8).toString('hex'), '89504e470d0a1a0a')
        }
      }
      checkpoint('项目任务的下载文件和保存图片以登记产物的类型、文件名、哈希和内容接口完整读取')
    }
    await click(main, '查看任务')
    await click(main, projectListExportOnly || projectTableOnly || projectAllureOnly ? '异常与证据' : projectLogOnly ? '日志' : '输入与输出', '[role="tab"]')
    await waitFor(main, `document.body?.innerText.includes(${JSON.stringify(projectListExportOnly || projectTableOnly || projectAllureOnly ? '文件与图片产物' : projectLogOnly ? '业务完成' : projectHttpOnly ? 'api_result' : projectNetworkOnly ? 'captured_urls' : outputExpectations.at(-1)[0])})`, 'project family output')
    if (projectAllureOnly) assert.equal(await main.evaluate("[...document.querySelectorAll('button')].filter(button => button.getAttribute('aria-label')?.startsWith('下载文件：')).length"), 1)
    if (projectListExportOnly || projectTableOnly) assert.equal(await main.evaluate("[...document.querySelectorAll('button')].filter(button => button.getAttribute('aria-label')?.startsWith('下载文件：')).length"), projectTableOnly ? 3 : 2)
    if (projectLogOnly) {
      await selectNative(main, '[aria-label="筛选日志级别"]', '成功')
      await waitFor(main, "document.querySelector('[aria-label=\"筛选日志级别\"]')?.getAttribute('data-choice-value') === 'success'", 'success log filter')
    }
    if (projectAdvancedOnly) {
      await waitFor(main, "Boolean([...document.querySelectorAll('button')].find(button => button.textContent?.trim() === '查看图片'))", 'project saved image action')
      await click(main, '查看图片')
      await waitFor(main, "Boolean(document.querySelector('[role=dialog] img[alt*=保存图片]'))", 'project saved image preview')
    }
    await capture(main, join(evidenceDir, projectMathOnly ? 'project-math-task.png' : projectUtilityOnly ? 'project-utility-task.png' : projectWebBasicOnly ? 'project-web-basic-task.png' : projectAdvancedOnly ? 'project-advanced-browser-task.png' : projectTabSwitchOnly ? 'project-tab-switch-task.png' : projectVariableOnly ? 'project-variable-task.png' : projectListExportOnly ? 'project-list-export-task.png' : projectLogOnly ? 'project-log-task.png' : projectTableOnly ? 'project-table-task.png' : projectHttpOnly ? 'project-http-task.png' : projectControlPrimitivesOnly ? 'project-control-primitives-task.png' : projectNetworkOnly ? 'project-network-task.png' : projectAllureOnly ? 'project-allure-task.png' : 'project-page-load-task.png'))
    assert.deepEqual(cloakProcesses(userData), [])
    if (projectAllureOnly) checkpoint('正式项目任务页列出可下载 Allure HTML，未启动 CloakBrowser，临时工作区未触碰用户数据')
    else if (projectNetworkOnly) checkpoint('正式项目任务页展示网络采集输出，CloakBrowser 已关闭，临时工作区未触碰用户数据')
    else
    checkpoint(projectMathOnly ? '正式项目任务真实 worker 产出三个数值和持久节点记录，未启动 CloakBrowser' : projectUtilityOnly ? '正式项目任务真实 worker 产出编码与摘要并持久化节点记录，未启动 CloakBrowser' : projectWebBasicOnly ? '正式项目任务使用项目默认 Profile 启动 CloakBrowser、执行网页动作、持久化输出并清理进程' : projectAdvancedOnly ? '正式项目任务使用默认 Profile 完成高级网页动作、下载和图片产物，正式任务页可预览且浏览器已清理' : projectTabSwitchOnly ? '正式项目任务使用默认 Profile 在真实 CloakBrowser 切换标签页，分别读取元素并清理进程' : projectVariableOnly ? '正式项目任务真实 worker 产出JSON、数值与日期，未启动 CloakBrowser' : projectListExportOnly ? '正式项目任务完成两次列表导出，任务页列出两个可下载产物且未启动 CloakBrowser' : projectLogOnly ? '正式项目任务持久化用户日志和导出文件，任务页可筛选成功日志且未启动 CloakBrowser' : projectTableOnly ? '正式项目任务通过默认 Profile 真实提取网页表格并导出三份可下载文件，浏览器已清理' : projectHttpOnly ? '正式项目任务真实调用本地网络服务、持久化两项响应变量及四节点状态，未启动 CloakBrowser' : projectControlPrimitivesOnly ? '正式项目任务真实执行等待和断言，在停止节点终止后继步骤，记录仍可查看且无浏览器残留' : '正式项目任务真实 CloakBrowser 等待页面并持久化加载状态，清理进程')
    const report = { evidenceId: projectMathOnly ? 'BE-project-math-formal-electron' : projectUtilityOnly ? 'BE-project-utility-formal-electron' : projectWebBasicOnly ? 'BE-project-web-basic-formal-electron' : projectAdvancedOnly ? 'BE-project-advanced-browser-formal-electron' : projectTabSwitchOnly ? 'BE-project-tab-switch-formal-electron' : projectVariableOnly ? 'BE-project-variable-formal-electron' : projectListExportOnly ? 'BE-project-list-export-formal-electron' : projectLogOnly ? 'BE-project-log-formal-electron' : projectTableOnly ? 'BE-project-table-formal-electron' : projectHttpOnly ? 'BE-project-http-formal-electron' : projectControlPrimitivesOnly ? 'BE-project-control-primitives-formal-electron' : projectNetworkOnly ? 'BE-project-network-formal-electron' : projectAllureOnly ? 'BE-project-allure-formal-electron' : 'BE-project-page-load-formal-electron', result: 'passed', checkedAt: new Date().toISOString(), gitHead, platform: `${process.platform}-${process.arch}`, entry: desktop.packaged ? 'packaged-directory' : 'development-build', projectId, workflowId: saved.id, batchId: batch.batchId, taskId: task.taskId, sawCloakBrowser, checks, ...(projectHttpOnly || projectNetworkOnly ? { requestTrace: httpRequests } : {}), boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browserStarted: sawCloakBrowser, interaction: 'formal Electron mouse/keyboard; API only fixture setup and evidence reads' } }
    await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
    console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
    throw new EvidenceComplete()
  }
  await click(studio, '新建')
  await waitFor(studio, "document.querySelectorAll('.react-flow__node').length === 0", 'new empty workflow')
  await setInput(studio, 'input[placeholder="工作流名称"]', workflowName)
  await showBlockView(studio)

  await addBlock(studio, '添加模块', '设置变量')
  await setInput(studio, '[placeholder="变量名"]', 'total')
  await setInput(studio, '[placeholder="变量的值"]', '0')

  await addBlock(studio, '添加模块', '循环')
  await setInput(studio, '[placeholder="输入循环次数或变量"]', '3')
  await setInput(studio, '[placeholder="索引变量名（默认：index）"]', 'loop_index')

  await addBlock(studio, '添加循环体步骤', '自增自减')
  await setInput(studio, '[placeholder="要操作的变量名"]', 'total')
  await setInput(studio, '[placeholder="每次增加或减少的值"]', '1')

  await addBlock(studio, '添加模块', '条件判断')
  await setInputAt(studio, '[placeholder="输入变量 {变量名} 或字面量"]', 0, '{total}')
  await setInputAt(studio, '[placeholder="输入变量 {变量名} 或字面量"]', 1, '3')

  await addBlock(studio, '添加「是」分支步骤', '设置变量')
  await setInput(studio, '[placeholder="变量名"]', 'outcome')
  await setInput(studio, '[placeholder="变量的值"]', 'passed')

  await addBlock(studio, '添加「否」分支步骤', '设置变量')
  await setInput(studio, '[placeholder="变量名"]', 'outcome')
  await setInput(studio, '[placeholder="变量的值"]', 'failed')

  await addBlock(studio, '添加模块', '设置变量')
  await setInput(studio, '[placeholder="变量名"]', 'finished')
  await setInput(studio, '[placeholder="变量的值"]', '1')
  checkpoint('通过模块条真实点击完成初始化、三轮循环、真假分支和汇合后的尾节点')

  if (projectTaskOnly) {
    await click(studio, '保存')
    await waitFor(studio, `document.body?.innerText.includes(${JSON.stringify(`工作流已保存: ${workflowName}`)})`, 'project control saved')
    const saved = (await api(runtime, `/workflows?projectId=${projectId}`)).find(item => item.name === workflowName)
    assert.ok(saved && saved.projectId === projectId)
    assert.ok(saved.edges.some(edge => edge.sourceHandle === 'true'))
    assert.ok(saved.edges.some(edge => edge.sourceHandle === 'false'))
    assert.ok(saved.edges.some(edge => edge.sourceHandle === 'loop'))
    assert.ok(saved.edges.some(edge => edge.sourceHandle === 'done'))

    const extendedName = 'B3 项目遍历与循环控制正式闭环'
    await newWorkflow(studio, extendedName)
    await addGlobalVariable(studio, 'items', 'array', '[10,20]')
    await addGlobalVariable(studio, 'mapping', 'object', '{"a":1,"b":2}')
    await showBlockView(studio)
    const extendedNodes = {}
    extendedNodes.initialize = await addBlock(studio, '添加模块', '设置变量')
    await setInput(studio, '[placeholder="变量名"]', 'visited')
    await setInput(studio, '[placeholder="变量的值"]', '0')
    extendedNodes.foreach = await addBlock(studio, '添加模块', '遍历列表')
    await setInput(studio, '[placeholder="输入列表变量名"]', 'items')
    extendedNodes.listIncrement = await addLoopBodyBlock(studio, extendedNodes.foreach, '自增自减')
    await setInput(studio, '[placeholder="要操作的变量名"]', 'visited')
    await setInput(studio, '[placeholder="每次增加或减少的值"]', '1')
    extendedNodes.branch = await addLoopBodyBlock(studio, extendedNodes.foreach, '条件判断')
    await setInputAt(studio, '[placeholder="输入变量 {变量名} 或字面量"]', 0, '{item}')
    await setInputAt(studio, '[placeholder="输入变量 {变量名} 或字面量"]', 1, '10')
    extendedNodes.trueBranch = await addBlock(studio, '添加「是」分支步骤', '设置变量')
    await setInput(studio, '[placeholder="变量名"]', 'route')
    await setInput(studio, '[placeholder="变量的值"]', 'ten')
    extendedNodes.falseBranch = await addBlock(studio, '添加「否」分支步骤', '设置变量')
    await setInput(studio, '[placeholder="变量名"]', 'route')
    await setInput(studio, '[placeholder="变量的值"]', 'other')
    extendedNodes.foreachDict = await addBlock(studio, '添加模块', '遍历字典')
    await setInput(studio, '[placeholder="输入字典变量名"]', 'mapping')
    extendedNodes.dictIncrement = await addLoopBodyBlock(studio, extendedNodes.foreachDict, '自增自减')
    await setInput(studio, '[placeholder="要操作的变量名"]', 'visited')
    await setInput(studio, '[placeholder="每次增加或减少的值"]', '1')
    extendedNodes.infinite = await addBlock(studio, '添加模块', '无限循环')
    extendedNodes.break = await addLoopBodyBlock(studio, extendedNodes.infinite, '跳出循环')
    extendedNodes.loop = await addBlock(studio, '添加模块', '循环')
    await setInput(studio, '[placeholder="输入循环次数或变量"]', '2')
    extendedNodes.continue = await addLoopBodyBlock(studio, extendedNodes.loop, '跳过当前循环')
    extendedNodes.skipped = await addLoopBodyBlock(studio, extendedNodes.loop, '自增自减')
    await setInput(studio, '[placeholder="要操作的变量名"]', 'visited')
    await setInput(studio, '[placeholder="每次增加或减少的值"]', '100')
    extendedNodes.tail = await addBlock(studio, '添加模块', '设置变量')
    await setInput(studio, '[placeholder="变量名"]', 'after_controls')
    await setInput(studio, '[placeholder="变量的值"]', '{visited}')
    await click(studio, '保存')
    const extended = await waitForValue(async () => {
      const found = (await api(runtime, `/workflows?projectId=${projectId}`)).find(item => item.name === extendedName)
      if (found) return found
      const error = await studio.evaluate("[...document.querySelectorAll('*')].find(e=>e.getClientRects().length&&e.textContent?.startsWith('保存失败:'))?.textContent||''")
      assert.equal(error, '', error)
      return null
    }, 'extended project control saved', 15_000)
    assert.ok(extended && extended.projectId === projectId)

    const subflowName = 'B3 项目画布子流程正式闭环'
    await newWorkflow(studio, subflowName)
    await click(studio, '流程图')
    const subflowInnerId = await addCanvasNode(studio, '设置变量', { xRatio: 0.82, yRatio: 0.12 })
    await setInput(studio, '[placeholder="变量名"]', 'inner_answer')
    await setInput(studio, '[placeholder="变量的值"]', '42')
    const subflowPageId = await addCanvasNode(studio, '打开网页', { xRatio: 0.82, yRatio: 0.45 })
    await setInput(studio, '[placeholder="https://example.com"]', pathToFileURL(join(root, 'apps/backend/tests/fixtures/workflow-page.html')).href)
    await connectNodes(studio, subflowInnerId, subflowPageId)
    const subflowGroupId = await addCanvasNode(studio, '分组', { xRatio: 0.65, yRatio: 0.05 })
    await click(studio, '', '[role="switch"]')
    await setInput(studio, '[placeholder="子流程名称"]', '项目组内流程')
    await resizeGroup(studio, subflowGroupId, 100, 300)
    const subflowCallId = await addCanvasNode(studio, '子流程')
    await selectNative(studio, '#subflowGroupId', '[分组] 项目组内流程')
    const subflowTailId = await addCanvasNode(studio, '设置变量', { xRatio: 0.12, yRatio: 0.32 })
    await setInput(studio, '[placeholder="变量名"]', 'subflow_result')
    await setInput(studio, '[placeholder="变量的值"]', '{inner_answer}')
    await connectNodes(studio, subflowCallId, subflowTailId)
    await click(studio, '保存')
    const subflow = await waitForValue(async () => (await api(runtime, `/workflows?projectId=${projectId}`)).find(item => item.name === subflowName), 'project subflow saved', 15_000)
    assert.equal(subflow.nodes.find(node => node.id === subflowCallId)?.data.subflowGroupId, subflowGroupId)
    assert.ok(subflow.nodes.some(node => node.id === subflowInnerId))
    const subflowGroup = subflow.nodes.find(node => node.id === subflowGroupId)
    const subflowPage = subflow.nodes.find(node => node.id === subflowPageId)
    assert.ok(subflowGroup && subflowPage)
    assert.ok(subflowPage.position.x >= subflowGroup.position.x && subflowPage.position.x <= subflowGroup.position.x + subflowGroup.data.width)
    assert.ok(subflowPage.position.y >= subflowGroup.position.y && subflowPage.position.y <= subflowGroup.position.y + subflowGroup.data.height)

    await newWorkflow(studio, 'B3 项目模块定义')
    await click(studio, '模块条')
    await addBlock(studio, '添加模块', '设置变量')
    await setInput(studio, '[placeholder="变量名"]', 'module_output')
    await setInput(studio, '[placeholder="变量的值"]', '42')
    await click(studio, '保存')
    await waitForValue(async () => (await api(runtime, `/workflows?projectId=${projectId}`)).find(item => item.name === 'B3 项目模块定义'), 'project module definition saved', 15_000)
    await clickRect(studio, "[...document.querySelectorAll('button')].find(e=>e.textContent.trim()==='自定义'&&e.parentElement?.textContent.includes('内置'))", 'project custom module tab')
    await clickRect(studio, "[...document.querySelector('input[placeholder=\"搜索自定义模块...\"]')?.closest('.flex.flex-col.h-full')?.querySelectorAll('button')||[]].find(e=>e.textContent.trim()==='创建模块')", 'create project custom module')
    await setInput(studio, '[role="dialog"] #name', 'b3_project_custom_module')
    await setInput(studio, '[role="dialog"] #displayName', 'B3 正式自定义模块')
    await click(studio, '添加输出', '[role="dialog"] button')
    await setInput(studio, '[role="dialog"] [placeholder="outputName"]', 'module_output')
    await click(studio, '创建模块', '[role="dialog"] button')
    const projectModule = await waitForValue(async () => (await api(runtime, '/custom-modules')).modules.find(item => item.name === 'b3_project_custom_module'), 'project custom module', 15_000)
    const moduleCallName = 'B3 项目自定义模块正式闭环'
    await newWorkflow(studio, moduleCallName)
    await click(studio, '流程图')
    await clickRect(studio, "[...document.querySelectorAll('button')].find(e=>e.textContent.trim()==='自定义'&&e.parentElement?.textContent.includes('内置'))", 'project custom module card tab')
    const moduleCallId = await dropCustomModule(studio, projectModule)
    const moduleTailId = await addCanvasNode(studio, '设置变量', { xRatio: 0.12, yRatio: 0.32 })
    await setInput(studio, '[placeholder="变量名"]', 'project_module_result')
    await setInput(studio, '[placeholder="变量的值"]', '{module_output}')
    await connectNodes(studio, moduleCallId, moduleTailId)
    await click(studio, '保存')
    const moduleCall = await waitForValue(async () => (await api(runtime, `/workflows?projectId=${projectId}`)).find(item => item.name === moduleCallName), 'project module call saved', 15_000)
    assert.equal(moduleCall.nodes.find(node => node.id === moduleCallId)?.data.customModuleId, projectModule.id)
    const nestedChildName = 'B3 项目被调用工作流'
    await newWorkflow(studio, nestedChildName)
    await showBlockView(studio)
    await addBlock(studio, '添加模块', '打开网页')
    await setInput(studio, '[placeholder="https://example.com"]', pathToFileURL(join(root, 'apps/backend/tests/fixtures/workflow-page.html')).href)
    await addBlock(studio, '添加模块', '设置变量')
    await setInput(studio, '[placeholder="变量名"]', 'child_value')
    await setInput(studio, '[placeholder="变量的值"]', '42')
    await click(studio, '保存')
    const nestedChild = await waitForValue(async () => (await api(runtime, `/workflows?projectId=${projectId}`)).find(item => item.name === nestedChildName), 'project child workflow saved', 15_000)
    const nestedCallerName = 'B3 项目跨工作流调用'
    await newWorkflow(studio, nestedCallerName)
    await showBlockView(studio)
    const nestedCallId = await addBlock(studio, '添加模块', '运行其它工作流')
    await selectNative(studio, '#workflowFilePicker', nestedChildName)
    const nestedTailId = await addBlock(studio, '添加模块', '设置变量')
    await setInput(studio, '[placeholder="变量名"]', 'project_nested_result')
    await setInput(studio, '[placeholder="变量的值"]', '{child_value}')
    await click(studio, '保存')
    const nestedCaller = await waitForValue(async () => (await api(runtime, `/workflows?projectId=${projectId}`)).find(item => item.name === nestedCallerName), 'project caller workflow saved', 15_000)
    assert.equal(nestedCaller.nodes.find(node => node.id === nestedCallId)?.data.workflowFile, nestedChild.id)
    checkpoint('正式项目 Studio 真实界面创建自定义模块、声明输出、拖入项目流程并持久化')
    await closeWindowThroughOs()
    studio.close(); studio = undefined
    await waitForNoStudio(desktop.debugOrigin)
    await click(main, '新建自动化')
    await setInput(main, '[aria-label="自动化名称"]', '控制流项目自动化')
    await selectAutomationWorkflow(main, workflowName, saved.id)
    await click(main, '保存配置')
    await waitFor(main, "document.body?.innerText.includes('自动化已创建')", 'control automation')
    await click(main, '启动运行')
    await waitFor(main, "document.body?.innerText.includes('启动自动化')", 'control batch dialog')
    await click(main, '启动 1 个任务')
    await waitFor(main, "document.body?.innerText.includes('本批次任务')", 'control batch')
    const batch = (await api(runtime, `/v1/projects/${projectId}/batches?pageSize=20`)).items[0]
    const terminal = await waitForValue(async () => { const value = await api(runtime, `/v1/projects/${projectId}/batches/${batch.batchId}`); return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.batch.status) ? value : null }, 'control task terminal', 60_000)
    assert.equal(terminal.statusCounts.succeeded, 1, JSON.stringify(terminal))
    const task = (await api(runtime, `/v1/projects/${projectId}/tasks?batchId=${batch.batchId}`)).items[0]
    const attempts = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/node-attempts?pageSize=100`)
    const names = Object.fromEntries(saved.nodes.map(node => [node.id, node.data.moduleType]))
    const succeeded = attempts.items.filter(item => item.status === 'succeeded')
    assert.equal(succeeded.filter(item => names[item.nodeId] === 'increment_decrement').length, 3)
    assert.equal(succeeded.filter(item => names[item.nodeId] === 'condition').length, 1)
    const outputs = await api(runtime, `/v1/projects/${projectId}/tasks/${task.taskId}/outputs?pageSize=100`)
    assert.ok(outputs.items.some(item => item.name === 'outcome' && item.value === 'passed'))
    assert.ok(!outputs.items.some(item => item.name === 'outcome' && item.value === 'failed'))
    await click(main, '查看任务')
    await click(main, '输入与输出', '[role="tab"]')
    await waitFor(main, "document.body?.innerText.includes('passed')", 'project control output')
    await capture(main, join(evidenceDir, 'project-control-task.png'))
    assert.deepEqual(cloakProcesses(userData), [])
    checkpoint('正式项目批次真实worker执行三轮循环与条件真分支，假分支无副作用；输出、尝试记录和进程清理通过')

    await click(main, '自动化', '[aria-label="项目功能"] button,[aria-label="项目功能"] [role="tab"]')
    await click(main, '新建自动化')
    await setInput(main, '[aria-label="自动化名称"]', '项目遍历与循环控制自动化')
    await selectAutomationWorkflow(main, extendedName, extended.id)
    await click(main, '保存配置')
    await waitFor(main, "document.body?.innerText.includes('自动化已创建')", 'extended control automation')
    await click(main, '启动运行')
    await waitFor(main, "document.body?.innerText.includes('启动自动化')", 'extended control batch dialog')
    await click(main, '启动 1 个任务')
    await waitFor(main, "document.body?.innerText.includes('本批次任务')", 'extended control batch')
    const extendedBatch = (await api(runtime, `/v1/projects/${projectId}/batches?pageSize=20`)).items[0]
    const extendedTerminal = await waitForValue(async () => { const value = await api(runtime, `/v1/projects/${projectId}/batches/${extendedBatch.batchId}`); return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.batch.status) ? value : null }, 'extended control terminal', 60_000)
    assert.equal(extendedTerminal.statusCounts.succeeded, 1, JSON.stringify(extendedTerminal))
    const extendedTask = (await api(runtime, `/v1/projects/${projectId}/tasks?batchId=${extendedBatch.batchId}`)).items[0]
    const extendedAttempts = await api(runtime, `/v1/projects/${projectId}/tasks/${extendedTask.taskId}/node-attempts?pageSize=100`)
    const countAttempts = nodeId => extendedAttempts.items.filter(item => item.nodeId === nodeId && item.status === 'succeeded').length
    assert.equal(countAttempts(extendedNodes.listIncrement), 2)
    assert.equal(countAttempts(extendedNodes.branch), 2)
    assert.equal(countAttempts(extendedNodes.trueBranch), 1)
    assert.equal(countAttempts(extendedNodes.falseBranch), 1)
    assert.equal(countAttempts(extendedNodes.dictIncrement), 2)
    assert.equal(countAttempts(extendedNodes.break), 1)
    assert.equal(countAttempts(extendedNodes.continue), 2)
    assert.equal(countAttempts(extendedNodes.skipped), 0)
    assert.equal(countAttempts(extendedNodes.tail), 1)
    const extendedOutputs = await api(runtime, `/v1/projects/${projectId}/tasks/${extendedTask.taskId}/outputs?pageSize=100`)
    assert.ok(extendedOutputs.items.some(item => item.name === 'after_controls' && item.value === 4), JSON.stringify(extendedOutputs))
    await click(main, '查看任务')
    await click(main, '输入与输出', '[role="tab"]')
    await waitFor(main, "document.body?.innerText.includes('after_controls')", 'extended control output')
    await capture(main, join(evidenceDir, 'project-extended-control-task.png'))
    assert.deepEqual(cloakProcesses(userData), [])
    checkpoint('正式项目批次真实worker执行列表内嵌条件的真假分支、字典遍历、无限循环退出与两轮跳过；被跳过节点无尝试，最终值为4')

    await click(main, '自动化', '[aria-label="项目功能"] button,[aria-label="项目功能"] [role="tab"]')
    await click(main, '新建自动化')
    await setInput(main, '[aria-label="自动化名称"]', '项目画布子流程自动化')
    await selectAutomationWorkflow(main, subflowName, subflow.id)
    await click(main, '保存配置')
    await waitFor(main, "document.body?.innerText.includes('自动化已创建')", 'project subflow automation')
    await click(main, '启动运行')
    await waitFor(main, "document.body?.innerText.includes('启动自动化')", 'project subflow batch dialog')
    await click(main, '启动 1 个任务')
    await waitFor(main, "document.body?.innerText.includes('本批次任务')", 'project subflow batch')
    const subflowBatch = (await api(runtime, `/v1/projects/${projectId}/batches?pageSize=20`)).items[0]
    const subflowTerminal = await waitForValue(async () => { const value = await api(runtime, `/v1/projects/${projectId}/batches/${subflowBatch.batchId}`); return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.batch.status) ? value : null }, 'project subflow terminal', 60_000)
    assert.equal(subflowTerminal.statusCounts.succeeded, 1, JSON.stringify(subflowTerminal))
    const subflowTask = (await api(runtime, `/v1/projects/${projectId}/tasks?batchId=${subflowBatch.batchId}`)).items[0]
    const subflowAttempts = await api(runtime, `/v1/projects/${projectId}/tasks/${subflowTask.taskId}/node-attempts?pageSize=100`)
    const completedSubflowNodes = subflowAttempts.items.filter(item => item.status === 'succeeded').map(item => item.nodeId)
    assert.equal(completedSubflowNodes.length, 4)
    assert.deepEqual(new Set(completedSubflowNodes), new Set([subflowInnerId, subflowPageId, subflowCallId, subflowTailId]))
    const subflowOutputs = await api(runtime, `/v1/projects/${projectId}/tasks/${subflowTask.taskId}/outputs?pageSize=100`)
    assert.ok(subflowOutputs.items.some(item => item.name === 'subflow_result' && item.value === 42), JSON.stringify(subflowOutputs))
    await click(main, '查看任务')
    await click(main, '输入与输出', '[role="tab"]')
    await waitFor(main, "document.body?.innerText.includes('subflow_result')", 'project subflow output')
    await capture(main, join(evidenceDir, 'project-subflow-task.png'))
    assert.deepEqual(cloakProcesses(userData), [])
    checkpoint('正式项目任务真实执行画布分组子流程，组内导航受控网页，变量传给尾节点输出42；CloakBrowser清理完成')

    await click(main, '自动化', '[aria-label="项目功能"] button,[aria-label="项目功能"] [role="tab"]')
    await click(main, '新建自动化')
    await setInput(main, '[aria-label="自动化名称"]', '项目自定义模块自动化')
    await selectAutomationWorkflow(main, moduleCallName, moduleCall.id)
    await click(main, '保存配置')
    await click(main, '启动运行')
    await click(main, '启动 1 个任务')
    await waitFor(main, "document.body?.innerText.includes('本批次任务')", 'project module batch')
    const moduleBatch = (await api(runtime, `/v1/projects/${projectId}/batches?pageSize=20`)).items[0]
    const moduleTerminal = await waitForValue(async () => { const value = await api(runtime, `/v1/projects/${projectId}/batches/${moduleBatch.batchId}`); return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.batch.status) ? value : null }, 'project module terminal', 60_000)
    assert.equal(moduleTerminal.statusCounts.succeeded, 1, JSON.stringify(moduleTerminal))
    const moduleTask = (await api(runtime, `/v1/projects/${projectId}/tasks?batchId=${moduleBatch.batchId}`)).items[0]
    const moduleAttempts = await api(runtime, `/v1/projects/${projectId}/tasks/${moduleTask.taskId}/node-attempts?pageSize=100`)
    assert.ok(moduleAttempts.items.some(item => item.nodeId === moduleCallId && item.status === 'succeeded'))
    assert.ok(moduleAttempts.items.some(item => item.nodeId !== moduleCallId && item.nodeId !== moduleTailId && item.status === 'succeeded' && item.executionContext?.scopes.some(scope => scope.kind === 'customModule' && scope.id === projectModule.id)))
    const moduleOutputs = await api(runtime, `/v1/projects/${projectId}/tasks/${moduleTask.taskId}/outputs?pageSize=100`)
    assert.ok(moduleOutputs.items.some(item => item.name === 'project_module_result' && item.value === 42), JSON.stringify(moduleOutputs))
    await click(main, '查看任务')
    await click(main, '输入与输出', '[role="tab"]')
    await waitFor(main, "document.body?.innerText.includes('project_module_result')", 'project module output')
    await capture(main, join(evidenceDir, 'project-custom-module-task.png'))
    assert.deepEqual(cloakProcesses(userData), [])
    checkpoint('正式项目任务使用冻结自定义模块独立执行，子节点上下文、输出和资源清理持久化')
    await click(main, '自动化', '[aria-label="项目功能"] button,[aria-label="项目功能"] [role="tab"]')
    await click(main, '新建自动化')
    await setInput(main, '[aria-label="自动化名称"]', '项目跨工作流自动化')
    await selectAutomationWorkflow(main, nestedCallerName, nestedCaller.id)
    await click(main, '保存配置')
    await click(main, '启动运行')
    await click(main, '启动 1 个任务')
    await waitFor(main, "document.body?.innerText.includes('本批次任务')", 'project nested workflow batch')
    const nestedBatch = (await api(runtime, `/v1/projects/${projectId}/batches?pageSize=20`)).items[0]
    const nestedTerminal = await waitForValue(async () => { const value = await api(runtime, `/v1/projects/${projectId}/batches/${nestedBatch.batchId}`); return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.batch.status) ? value : null }, 'project nested workflow terminal', 60_000)
    assert.equal(nestedTerminal.statusCounts.succeeded, 1, JSON.stringify(nestedTerminal))
    const nestedTask = (await api(runtime, `/v1/projects/${projectId}/tasks?batchId=${nestedBatch.batchId}`)).items[0]
    const nestedAttempts = await api(runtime, `/v1/projects/${projectId}/tasks/${nestedTask.taskId}/node-attempts?pageSize=100`)
    assert.ok(nestedAttempts.items.some(item => item.nodeId === nestedCallId && item.status === 'succeeded'))
    assert.ok(nestedAttempts.items.some(item => item.nodeId !== nestedCallId && item.nodeId !== nestedTailId && item.status === 'succeeded' && item.executionContext?.scopes.some(scope => scope.kind === 'workflow' && scope.id === nestedChild.id)))
    const nestedOutputs = await api(runtime, `/v1/projects/${projectId}/tasks/${nestedTask.taskId}/outputs?pageSize=100`)
    assert.ok(nestedOutputs.items.some(item => item.name === 'project_nested_result' && item.value === 42), JSON.stringify(nestedOutputs))
    await click(main, '查看任务')
    await click(main, '输入与输出', '[role="tab"]')
    await waitFor(main, "document.body?.innerText.includes('project_nested_result')", 'project nested workflow output')
    await capture(main, join(evidenceDir, 'project-nested-workflow-task.png'))
    assert.deepEqual(cloakProcesses(userData), [])
    checkpoint('正式项目 Studio 选择项目内子工作流并保存，项目任务独立运行、回收变量和子节点上下文，worker 清理完成')
    const report = { evidenceId: 'BE-project-control-flow-formal-electron', result: 'passed', checkedAt: new Date().toISOString(), gitHead, platform: `${process.platform}-${process.arch}`, entry: desktop.packaged ? 'packaged-directory' : 'development-build', projectId, workflowIds: [saved.id, extended.id, subflow.id, moduleCall.id, nestedChild.id, nestedCaller.id], batchIds: [batch.batchId, extendedBatch.batchId, subflowBatch.batchId, moduleBatch.batchId, nestedBatch.batchId], taskIds: [task.taskId, extendedTask.taskId, subflowTask.taskId, moduleTask.taskId, nestedTask.taskId], checks, boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browserStarted: true, interaction: 'formal Electron mouse/keyboard; API only fixture setup and evidence reads' } }
    await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
    console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
    throw new EvidenceComplete()
  }

  await click(studio, '流程图')
  const subflowInnerId = await addCanvasNode(studio, '设置变量', { xRatio: 0.82, yRatio: 0.12 })
  await setInput(studio, '[placeholder="变量名"]', 'inside')
  await setInput(studio, '[placeholder="变量的值"]', '42')

  const headerId = await addCanvasNode(studio, '分组', { xRatio: 0.65, yRatio: 0.05 })
  await click(studio, '', '[role="switch"]')
  await setInput(studio, '[placeholder="子流程名称"]', '正式子流程')
  await resizeGroup(studio, headerId, 100, 0)

  const subflowCallId = await addCanvasNode(studio, '子流程')
  await selectNative(studio, '#subflowGroupId', '[分组] 正式子流程')
  const subflowTailId = await addCanvasNode(studio, '设置变量', { xRatio: 0.12, yRatio: 0.32 })
  await setInput(studio, '[placeholder="变量名"]', 'subflow_finished')
  await setInput(studio, '[placeholder="变量的值"]', '1')
  await connectNodes(studio, subflowCallId, subflowTailId)
  checkpoint('通过流程图真实右键入口创建子流程分组、组内步骤和独立调用；调用按稳定节点 ID 绑定')

  await click(studio, '保存')
  await waitFor(studio, `document.body?.innerText.includes(${JSON.stringify(`工作流已保存: ${workflowName}`)})`, 'workflow save acknowledgement')
  const saved = (await api(runtime, '/workflows')).find(item => item.name === workflowName)
  assert.ok(saved)
  const byType = type => saved.nodes.filter(node => node.data.moduleType === type)
  assert.equal(byType('loop').length, 1)
  assert.equal(byType('condition').length, 1)
  assert.equal(byType('group').length, 1)
  assert.equal(byType('subflow').length, 1)
  assert.equal(saved.nodes.find(node => node.id === subflowCallId)?.data.subflowGroupId, headerId)
  const group = saved.nodes.find(node => node.id === headerId)
  const inner = saved.nodes.find(node => node.id === subflowInnerId)
  assert.ok(inner.position.x >= group.position.x && inner.position.x <= group.position.x + group.data.width)
  assert.ok(inner.position.y >= group.position.y && inner.position.y <= group.position.y + group.data.height)
  assert.ok(saved.edges.some(edge => edge.sourceHandle === 'true'))
  assert.ok(saved.edges.some(edge => edge.sourceHandle === 'false'))
  assert.ok(saved.edges.some(edge => edge.sourceHandle === 'loop'))
  assert.ok(saved.edges.some(edge => edge.sourceHandle === 'done'))
  assert.ok(saved.edges.some(edge => edge.source === subflowCallId && edge.target === subflowTailId))
  checkpoint('真实 HTTP/SQLite 文档包含条件双分支、循环双出口、子流程定义与独立调用')

  const savedNodeCount = saved.nodes.length
  const savedEdgeCount = saved.edges.length
  await closeWindowThroughOs()
  studio.close(); studio = undefined
  await waitForNoStudio(desktop.debugOrigin)
  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库')", 'reopened Studio', 30_000)
  if (!await studio.evaluate(`document.querySelector('input[placeholder="工作流名称"]')?.value === ${JSON.stringify(workflowName)}`)) {
    await click(studio, '打开')
    await click(studio, `打开工作流 ${workflowName}`, '[role="button"]')
  }
  await waitFor(studio, `document.querySelector('input[placeholder="工作流名称"]')?.value === ${JSON.stringify(workflowName)} && document.querySelectorAll('.react-flow__node').length === ${savedNodeCount}`, 'persisted workflow reopen')
  assert.equal(await studio.evaluate("document.querySelectorAll('.react-flow__edge').length"), savedEdgeCount)
  checkpoint('macOS Cmd+W 正常关闭后从主窗口重开，节点、结构和配置全部恢复')

  if (restartRecoveryOnly) {
    const incrementId = byType('increment_decrement')[0].id
    const pausedRun = await runToCanvasNode(studio, runtime, saved.id, incrementId)
    const resultsBeforeCrash = await readRunResults(runtime, pausedRun.runId)
    const previousInstance = runtime.sidecar.instanceId
    const sidecarPid = listeningPid(runtime.sidecar.baseUrl)
    process.kill(sidecarPid, 'SIGKILL')
    await waitFor(main, `(async()=>{const r=await window.autoflow.getRuntimeContext();return r.sidecar.state==='failed'})()`, 'sidecar crash observed', 15_000)
    await waitFor(studio, "document.body.innerText.includes('服务连接不可用，当前草稿仍保留')", 'Studio offline state', 15_000)
    await capture(studio, join(evidenceDir, 'sidecar-crashed.png'))
    checkpoint('调试暂停期间强制终止 sidecar；Studio 保留当前文档并明确进入离线状态')

    await click(main, '设置')
    await waitFor(main, "document.body.innerText.includes('启动失败')", 'failed sidecar settings')
    await click(main, '重启服务')
    const recoveredRuntime = await waitFor(main, `(async()=>{const r=await window.autoflow.getRuntimeContext();return r.sidecar.state==='ready'&&r.sidecar.instanceId!==${JSON.stringify(previousInstance)}?r:null})()`, 'restarted sidecar', 30_000)
    await waitFor(studio, "document.body.innerText.includes('模块库')", 'Studio reconnect', 30_000)
    const interrupted = await api(recoveredRuntime, `/workflow-runs/${encodeURIComponent(pausedRun.runId)}`)
    assert.equal(interrupted.status, 'interrupted')
    assert.equal(interrupted.error.code, 'RUN_INTERRUPTED')
    const resultsAfterRestart = await readRunResults(recoveredRuntime, pausedRun.runId)
    assert.deepEqual(resultsAfterRestart, resultsBeforeCrash)
    assert.equal(resultsAfterRestart.some(item => item.nodeId === incrementId), false)
    await waitFor(studio, `String(document.querySelector('[aria-label="运行日志记录"]')?.textContent||'').includes('interrupted')`, 'interrupted run history', 15_000)
    await waitForRunReady(studio)
    await capture(studio, join(evidenceDir, 'interrupted-run-restored.png'))
    const recoveryEvents = sqliteRows(join(userData, 'data', 'autoflow.sqlite3'), `SELECT seq,json_extract(payload,'$.type') AS type,json_extract(payload,'$.payload.reason') AS reason FROM workflow_run_events WHERE run_id=${sqlLiteral(pausedRun.runId)} AND json_extract(payload,'$.type')='execution:interrupted'`)
    assert.deepEqual(recoveryEvents.map(item => item.reason), ['service-restarted'])
    checkpoint('通过主窗口设置真实重启 sidecar；旧运行恢复为 interrupted，历史和日志可读，暂停节点未重放')

    const report = {
      evidenceId: 'BE-B8-formal-restart-recovery-electron', checkedAt: new Date().toISOString(), gitHead,
      result: 'passed', platform: `${process.platform}-${process.arch}`, entry: desktop.packaged ? 'packaged-directory' : 'development-build',
      workflowId: saved.id, profileId: profile.id, runId: pausedRun.runId,
      sidecar: { crashedPid: sidecarPid, previousInstance, recoveredInstance: recoveredRuntime.sidecar.instanceId },
      assertions: { status: interrupted.status, errorCode: interrupted.error.code, resultCount: resultsAfterRestart.length, recoveryEvents }, checks,
      boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browserLaunch: 'none (pure data)', interaction: 'formal main and Studio UI through CDP mouse and keyboard; SIGKILL only injects the sidecar crash; no Store access' },
    }
    await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
    console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
    throw new EvidenceComplete()
  }

  if (complexDebugOnly) {
    const loopId = byType('loop')[0].id
    const incrementId = byType('increment_decrement')[0].id
    const loopRun = await runToCanvasNode(studio, runtime, saved.id, incrementId)
    await waitFor(studio, `document.querySelector('[aria-label="调试执行上下文"]')?.textContent.includes(${JSON.stringify(`${loopId} 第 1 轮`)})`, 'loop debug context', 10_000)
    await capture(studio, join(evidenceDir, 'loop-target-paused.png'))
    await click(studio, '继续')
    assert.equal((await waitForTerminal(runtime, loopRun.runId)).status, 'completed')
    const loopResults = await readRunResults(runtime, loopRun.runId)
    assert.deepEqual(loopResults.filter(item => item.nodeId === incrementId).map(item => item.executionContext.loops[0].iteration), [1, 2, 3])
    assert.equal(observedEvents.filter(event => event.name === 'execution:paused' && event.data?.runId === loopRun.runId && event.data?.reason === 'target').length, 1)
    checkpoint('正式 UI 运行至循环体首轮前暂停，显示轮次上下文；继续后三轮完成且目标不重复暂停')

    await waitForRunReady(studio)
    const branchNodes = byType('set_variable').filter(node => ['passed', 'failed'].includes(node.data.variableValue))
    const trueId = branchNodes.find(node => node.data.variableValue === 'passed').id
    const falseId = branchNodes.find(node => node.data.variableValue === 'failed').id
    const trueRun = await runToCanvasNode(studio, runtime, saved.id, trueId)
    await capture(studio, join(evidenceDir, 'condition-true-paused.png'))
    await click(studio, '继续')
    assert.equal((await waitForTerminal(runtime, trueRun.runId)).status, 'completed')
    const trueResults = await readRunResults(runtime, trueRun.runId)
    assert.equal(trueResults.filter(item => item.nodeId === trueId).length, 1)
    assert.equal(trueResults.filter(item => item.nodeId === falseId).length, 0)
    checkpoint('正式 UI 在条件真分支目标前暂停；继续后仅真分支执行，假分支无结果和副作用')

    await waitForRunReady(studio)
    const falseWorkflowName = 'B8 条件假分支调试闭环'
    await newWorkflow(studio, falseWorkflowName)
    await click(studio, '模块条')
    await addBlock(studio, '添加模块', '设置变量')
    await setInput(studio, '[placeholder="变量名"]', 'flag')
    await setInput(studio, '[placeholder="变量的值"]', 'no')
    await addBlock(studio, '添加模块', '条件判断')
    await setInputAt(studio, '[placeholder="输入变量 {变量名} 或字面量"]', 0, '{flag}')
    await setInputAt(studio, '[placeholder="输入变量 {变量名} 或字面量"]', 1, 'yes')
    const falseTrueId = await addBlock(studio, '添加「是」分支步骤', '设置变量')
    await setInput(studio, '[placeholder="变量名"]', 'path')
    await setInput(studio, '[placeholder="变量的值"]', 'true')
    const falseTargetId = await addBlock(studio, '添加「否」分支步骤', '设置变量')
    await setInput(studio, '[placeholder="变量名"]', 'path')
    await setInput(studio, '[placeholder="变量的值"]', 'false')
    const falseWorkflow = await saveWorkflow(studio, runtime, falseWorkflowName)
    const falseRun = await runToCanvasNode(studio, runtime, falseWorkflow.id, falseTargetId)
    await capture(studio, join(evidenceDir, 'condition-false-paused.png'))
    await click(studio, '继续')
    assert.equal((await waitForTerminal(runtime, falseRun.runId)).status, 'completed')
    const falseResults = await readRunResults(runtime, falseRun.runId)
    assert.equal(falseResults.filter(item => item.nodeId === falseTargetId).length, 1)
    assert.equal(falseResults.filter(item => item.nodeId === falseTrueId).length, 0)
    checkpoint('正式 UI 在条件假分支目标前暂停；继续后仅假分支执行，真分支无结果和副作用')

    await waitForRunReady(studio)
    const parallelWorkflowName = 'B8 并行断点调试闭环'
    await newWorkflow(studio, parallelWorkflowName)
    await click(studio, '流程图')
    const parallelA = await addCanvasNode(studio, '设置变量', { xRatio: 0.25, yRatio: 0.2 })
    await setInput(studio, '[placeholder="变量名"]', 'parallel_a')
    await setInput(studio, '[placeholder="变量的值"]', '1')
    const parallelB = await addCanvasNode(studio, '设置变量', { xRatio: 0.75, yRatio: 0.2 })
    await setInput(studio, '[placeholder="变量名"]', 'parallel_b')
    await setInput(studio, '[placeholder="变量的值"]', '1')
    const parallelWorkflow = await saveWorkflow(studio, runtime, parallelWorkflowName)
    await toggleBreakpoint(studio, parallelA)
    await toggleBreakpoint(studio, parallelB)
    const parallelRun = await startWorkflow(studio, runtime, parallelWorkflow.id)
    const firstPause = await waitForPauseEvent(observedEvents, parallelRun.runId, 1)
    assert.ok([parallelA, parallelB].includes(firstPause.node_id))
    assert.deepEqual(await readRunResults(runtime, parallelRun.runId), [])
    await capture(studio, join(evidenceDir, 'parallel-first-paused.png'))
    await click(studio, '继续')
    const secondPause = await waitForPauseEvent(observedEvents, parallelRun.runId, 2)
    assert.notEqual(secondPause.pauseId, firstPause.pauseId)
    assert.notEqual(secondPause.node_id, firstPause.node_id)
    const betweenPauseResults = await readRunResults(runtime, parallelRun.runId)
    assert.deepEqual(betweenPauseResults.map(item => item.nodeId), [firstPause.node_id])
    await click(studio, '继续')
    assert.equal((await waitForTerminal(runtime, parallelRun.runId)).status, 'completed')
    const parallelResults = await readRunResults(runtime, parallelRun.runId)
    assert.deepEqual(new Set(parallelResults.map(item => item.nodeId)), new Set([parallelA, parallelB]))
    checkpoint('正式 UI 的两个并行起点均设置断点；首个暂停时零节点已执行，继续后仅首节点完成且第二节点暂停，再继续后两节点完成')

    const report = {
      evidenceId: 'BE-B8-formal-complex-debug-electron', checkedAt: new Date().toISOString(), gitHead,
      result: 'passed', platform: `${process.platform}-${process.arch}`, entry: desktop.packaged ? 'packaged-directory' : 'development-build',
      workflowId: saved.id, profileId: profile.id,
      runIds: [loopRun.runId, trueRun.runId, falseRun.runId, parallelRun.runId], checks,
      assertions: {
        loopTarget: incrementId, loopIterations: [1, 2, 3],
        conditionTrue: { target: trueId, skipped: falseId },
        conditionFalse: { target: falseTargetId, skipped: falseTrueId },
        parallel: { nodes: [parallelA, parallelB], pauseOrder: [firstPause.node_id, secondPause.node_id] },
      },
      boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browserLaunch: 'none (pure data)', interaction: 'formal Studio UI through CDP mouse and keyboard plus macOS Cmd+W; no Store access' },
    }
    await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
    console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
    throw new EvidenceComplete()
  }

  await click(studio, '运行 (F5)', '[aria-label="运行 (F5)"]')
  await click(studio, '运行 (F5)', '[role="menuitem"]')
  const startedRun = await waitForValue(async () => {
    const page = await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(saved.id)}&cursor=0&limit=20`)
    return page.items[0] ?? null
  }, 'persisted workflow run', 20_000)
  const terminalRun = await waitForValue(async () => {
    const value = await api(runtime, `/workflow-runs/${encodeURIComponent(startedRun.runId)}`)
    return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.status) ? value : null
  }, 'workflow terminal persistence', 60_000)
  assert.equal(terminalRun.status, 'completed')
  await waitFor(studio, "document.body?.innerText.includes('执行完成')", 'rendered terminal event', 10_000)

  const results = await api(runtime, `/workflow-runs/${encodeURIComponent(startedRun.runId)}/results?cursor=0&limit=200`)
  const logs = await api(runtime, `/workflow-runs/${encodeURIComponent(startedRun.runId)}/logs?cursor=0&limit=500`)
  const incrementId = byType('increment_decrement')[0].id
  const conditionId = byType('condition')[0].id
  const branchNodes = byType('set_variable').filter(node => ['passed', 'failed'].includes(node.data.variableValue))
  const trueId = branchNodes.find(node => node.data.variableValue === 'passed').id
  const falseId = branchNodes.find(node => node.data.variableValue === 'failed').id
  const incrementResults = results.items.filter(item => item.nodeId === incrementId)
  assert.deepEqual(incrementResults.map(item => item.values.new_value), [1, 2, 3])
  assert.deepEqual(incrementResults.map(item => item.executionContext.loops[0].iteration), [1, 2, 3])
  assert.equal(results.items.filter(item => item.nodeId === conditionId).length, 1)
  assert.equal(results.items.filter(item => item.nodeId === trueId).length, 1)
  assert.equal(results.items.filter(item => item.nodeId === falseId).length, 0)
  const innerResult = results.items.find(item => item.nodeId === subflowInnerId)
  assert.deepEqual(innerResult.executionContext.scopes, [{ kind: 'subflow', id: headerId, name: '正式子流程' }])
  const callResult = results.items.find(item => item.nodeId === subflowCallId)
  assert.deepEqual(callResult.values, { subflow: '正式子流程', executed_nodes: 1, failed_nodes: 0 })
  const subflowTailResult = results.items.find(item => item.nodeId === subflowTailId)
  assert.deepEqual(subflowTailResult.executionContext.loops, [])
  assert.equal(new Set(results.items.map(item => item.executionId)).size, results.items.length)
  assert.ok(logs.items.some(item => item.nodeId === trueId && item.message.includes('outcome = passed')))
  assert.equal(logs.items.some(item => item.nodeId === falseId), false)
  assert.ok(observedEvents.some(event => event.name === 'execution:completed' && event.data?.runId === startedRun.runId))
  checkpoint('真实 worker 完成三轮循环、真分支和子流程；假分支无副作用，结果按 executionId、轮次与作用域持久化')

  assert.deepEqual(cloakProcesses(userData), [])
  const sqlite = sqliteEvidence(userData, saved.id, startedRun.runId)
  assert.equal(sqlite.document[0].nodeCount, savedNodeCount)
  assert.equal(sqlite.run[0].status, 'completed')
  assert.equal(sqlite.run[0].cleanupState, 'completed')
  assert.equal(sqlite.run[0].activeSlot, null)

  const recursiveName = 'B3 递归变量正式闭环'
  await newWorkflow(studio, recursiveName)
  await addGlobalVariable(studio, 'nested_data', 'object', '{"users":[{"name":"甲"},{"name":"乙"}],"index":1}')
  await click(studio, '模块条')
  const recursiveNodes = {}
  recursiveNodes.resolve = await addBlock(studio, '添加模块', '设置变量')
  await setInput(studio, '[placeholder="变量名"]', 'nested_value')
  await setInput(studio, '[placeholder="变量的值"]', '{nested_data[users][{nested_data[index]}][name]}')
  recursiveNodes.assert = await addBlock(studio, '添加模块', '断言/检查点')
  await setInput(studio, '[placeholder="要校验的值，支持 {变量名}"]', '{nested_value}')
  await setInput(studio, '[placeholder="期望对照的值，支持 {变量名}"]', '乙')
  const recursiveWorkflow = await saveWorkflow(studio, runtime, recursiveName)
  const recursiveRun = await startWorkflow(studio, runtime, recursiveWorkflow.id)
  const recursiveTerminal = await waitForTerminal(runtime, recursiveRun.runId)
  assert.equal(recursiveTerminal.status, 'completed')
  const recursiveResults = await api(runtime, `/workflow-runs/${encodeURIComponent(recursiveRun.runId)}/results?cursor=0&limit=20`)
  assert.equal(recursiveResults.items.find(item => item.nodeId === recursiveNodes.resolve)?.values.value, '乙')
  assert.equal(recursiveResults.items.find(item => item.nodeId === recursiveNodes.assert)?.values.passed, true)
  checkpoint('正式 UI 保存对象初值，并解析列表、字典和嵌套索引变量后通过断言')

  const childName = 'B3 子工作流目标'
  await newWorkflow(studio, childName)
  await click(studio, '流程图')
  const childNodeId = await addCanvasNode(studio, '设置变量')
  await setInput(studio, '[placeholder="变量名"]', 'child_value')
  await setInput(studio, '[placeholder="变量的值"]', 'child_done')
  const childWorkflow = await saveWorkflow(studio, runtime, childName)

  const utilityName = 'B3 变量交互与依赖正式闭环'
  await newWorkflow(studio, utilityName)
  await addGlobalVariable(studio, 'json_data', 'string', '{"data":{"name":"AutoFlow"}}')
  const utilityNodes = {}

  utilityNodes.json_parse = await addCanvasNode(studio, 'JSON解析')
  await setInput(studio, '[placeholder="填写变量名，如: jsonData"]', 'json_data')
  await setInput(studio, '[placeholder="$.data.items[0].name，支持 {变量名}"]', '$.data.name')
  await setInput(studio, '#variableName', 'parsed_name')

  utilityNodes.base64 = await addCanvasNode(studio, 'Base64编解码')
  await setInput(studio, 'textarea[placeholder="要编码的文本，支持 {变量名}"]', '{parsed_name}')
  await setInput(studio, '#variableName', 'encoded_name')

  utilityNodes.random_number = await addCanvasNode(studio, '随机数')
  await setInput(studio, '[placeholder="最小值，支持 {变量名}"]', '7')
  await setInput(studio, '[placeholder="最大值，支持 {变量名}"]', '7')
  await setInput(studio, '#variableName', 'fixed_random')

  utilityNodes.get_time = await addCanvasNode(studio, '获取时间')
  await setInput(studio, '#variableName', 'captured_time')

  utilityNodes.assert_checkpoint = await addCanvasNode(studio, '断言/检查点')
  await setInput(studio, '[placeholder="要校验的值，支持 {变量名}"]', '{encoded_name}')
  await setInput(studio, '[placeholder="期望对照的值，支持 {变量名}"]', 'QXV0b0Zsb3c=')
  await setInput(studio, '[placeholder="存储断言结果布尔值，如 assert_passed"]', 'assert_passed')

  utilityNodes.wait = await addCanvasNode(studio, '固定等待')
  await setInput(studio, '#duration', '0.01')

  utilityNodes.input_prompt = await addCanvasNode(studio, '用户输入')
  await setInput(studio, '#variableName', 'operator_answer')
  await setInput(studio, '[placeholder="输入框的标题"]', 'B3 正式输入')
  await setInput(studio, '[placeholder="输入框的提示信息"]', '请输入验收值')

  utilityNodes.run_workflow_file = await addCanvasNode(studio, '运行其它工作流')
  await setInput(studio, '[placeholder="工作流文件名，如 数据采集.json，支持 {变量名}"]', childName)
  await setInput(studio, '[placeholder="sub_workflow_result"]', 'child_result')

  utilityNodes.note = await addCanvasNode(studio, '便签')
  await setInput(studio, 'textarea[placeholder="在这里输入便签内容..."]', 'B3 正式便签，不参与执行')

  const utilityChain = ['json_parse', 'base64', 'random_number', 'get_time', 'assert_checkpoint', 'wait', 'input_prompt', 'run_workflow_file']
  for (let index = 0; index < utilityChain.length - 1; index++) {
    await connectNodes(studio, utilityNodes[utilityChain[index]], utilityNodes[utilityChain[index + 1]])
  }
  const utilityWorkflow = await saveWorkflow(studio, runtime, utilityName)
  const utilityRun = await startWorkflow(studio, runtime, utilityWorkflow.id)
  await waitFor(studio, `document.querySelector('[role="dialog"]')?.getAttribute('aria-label') === 'B3 正式输入'`, 'input prompt dialog', 20_000)
  await setInput(studio, '[role="dialog"] input[type="text"]', '正式输入值')
  await click(studio, '确定', '[role="dialog"] button')
  const utilityTerminal = await waitForTerminal(runtime, utilityRun.runId)
  assert.equal(utilityTerminal.status, 'completed')
  const utilityResults = await api(runtime, `/workflow-runs/${encodeURIComponent(utilityRun.runId)}/results?cursor=0&limit=100`)
  const utilityLogs = await api(runtime, `/workflow-runs/${encodeURIComponent(utilityRun.runId)}/logs?cursor=0&limit=200`)
  const utilityByNode = Object.fromEntries(utilityResults.items.map(item => [item.nodeId, item]))
  for (const type of utilityChain.filter(type => type !== 'wait')) assert.ok(utilityByNode[utilityNodes[type]], `missing ${type} result`)
  assert.ok(utilityLogs.items.some(item => item.nodeId === utilityNodes.wait && item.message.includes('已等待')))
  assert.equal(utilityByNode[utilityNodes.json_parse].values.value, 'AutoFlow')
  assert.equal(utilityByNode[utilityNodes.base64].values.value, 'QXV0b0Zsb3c=')
  assert.equal(utilityByNode[utilityNodes.random_number].values.value, 7)
  assert.equal(utilityByNode[utilityNodes.assert_checkpoint].values.passed, true)
  assert.equal(utilityByNode[utilityNodes.input_prompt].values.value, '正式输入值')
  assert.equal(utilityResults.items.some(item => item.nodeId === utilityNodes.note), false)
  assert.ok(utilityResults.items.some(item => item.nodeId === childNodeId && item.executionContext.scopes.some(scope => scope.kind === 'workflow')))
  checkpoint('正式 UI 完成 JSON、Base64、随机数、时间、断言、等待、用户输入、运行其它工作流和便签的保存与真实执行')

  const foreachName = 'B3 列表字典循环正式闭环'
  await newWorkflow(studio, foreachName)
  await click(studio, '模块条')
  const foreachNodes = {}
  foreachNodes.listFirst = await addBlock(studio, '添加模块', '列表操作')
  await setInput(studio, '[placeholder="填写变量名，如: myList"]', 'items')
  await setInput(studio, '[placeholder="要添加/删除的值，支持 {变量名}"]', '10')
  foreachNodes.listSecond = await addBlock(studio, '添加模块', '列表操作')
  await setInput(studio, '[placeholder="填写变量名，如: myList"]', 'items')
  await setInput(studio, '[placeholder="要添加/删除的值，支持 {变量名}"]', '20')
  foreachNodes.dictFirst = await addBlock(studio, '添加模块', '字典操作')
  await setInput(studio, '[placeholder="填写变量名，如: myDict"]', 'mapping')
  await setInput(studio, '[placeholder="键名，支持 {变量名}"]', 'a')
  await setInput(studio, '[placeholder="要设置的值，支持 {变量名}"]', '1')
  foreachNodes.dictSecond = await addBlock(studio, '添加模块', '字典操作')
  await setInput(studio, '[placeholder="填写变量名，如: myDict"]', 'mapping')
  await setInput(studio, '[placeholder="键名，支持 {变量名}"]', 'b')
  await setInput(studio, '[placeholder="要设置的值，支持 {变量名}"]', '2')
  foreachNodes.initialize = await addBlock(studio, '添加模块', '设置变量')
  await setInput(studio, '[placeholder="变量名"]', 'visited')
  await setInput(studio, '[placeholder="变量的值"]', '0')
  foreachNodes.foreach = await addBlock(studio, '添加模块', '遍历列表')
  await setInput(studio, '[placeholder="输入列表变量名"]', 'items')
  await setInput(studio, '[placeholder="元素变量名（默认：item）"]', 'current_item')
  foreachNodes.foreachIncrement = await addLoopBodyBlock(studio, foreachNodes.foreach, '自增自减')
  await setInput(studio, '[placeholder="要操作的变量名"]', 'visited')
  await setInput(studio, '[placeholder="每次增加或减少的值"]', '1')
  foreachNodes.foreachDict = await addBlock(studio, '添加模块', '遍历字典')
  await setInput(studio, '[placeholder="输入字典变量名"]', 'mapping')
  await setInput(studio, '[placeholder="键变量名（默认：key）"]', 'current_key')
  await setInput(studio, '[placeholder="值变量名（默认：value）"]', 'current_value')
  foreachNodes.dictIncrement = await addLoopBodyBlock(studio, foreachNodes.foreachDict, '自增自减')
  await setInput(studio, '[placeholder="要操作的变量名"]', 'visited')
  await setInput(studio, '[placeholder="每次增加或减少的值"]', '1')
  foreachNodes.assert = await addBlock(studio, '添加模块', '断言/检查点')
  await setInput(studio, '[placeholder="要校验的值，支持 {变量名}"]', '{visited}')
  await setInput(studio, '[placeholder="期望对照的值，支持 {变量名}"]', '4')
  const foreachWorkflow = await saveWorkflow(studio, runtime, foreachName)
  const foreachRun = await startWorkflow(studio, runtime, foreachWorkflow.id)
  const foreachTerminal = await waitForTerminal(runtime, foreachRun.runId)
  assert.equal(foreachTerminal.status, 'completed')
  const foreachResults = await api(runtime, `/workflow-runs/${encodeURIComponent(foreachRun.runId)}/results?cursor=0&limit=100`)
  assert.deepEqual(foreachResults.items.filter(item => item.nodeId === foreachNodes.foreachIncrement).map(item => item.values.new_value), [1, 2])
  assert.deepEqual(foreachResults.items.filter(item => item.nodeId === foreachNodes.dictIncrement).map(item => item.values.new_value), [3, 4])
  assert.equal(foreachResults.items.find(item => item.nodeId === foreachNodes.assert)?.values.passed, true)
  checkpoint('正式模块条完成列表和字典循环；两类循环各执行两轮并累积到 4')

  const breakName = 'B3 无限循环退出正式闭环'
  await newWorkflow(studio, breakName)
  await click(studio, '模块条')
  const breakNodes = {}
  breakNodes.loop = await addBlock(studio, '添加模块', '无限循环')
  breakNodes.break = await addLoopBodyBlock(studio, breakNodes.loop, '跳出循环')
  breakNodes.tail = await addBlock(studio, '添加模块', '设置变量')
  await setInput(studio, '[placeholder="变量名"]', 'after_break')
  await setInput(studio, '[placeholder="变量的值"]', '1')
  const breakWorkflow = await saveWorkflow(studio, runtime, breakName)
  const breakRun = await startWorkflow(studio, runtime, breakWorkflow.id)
  const breakTerminal = await waitForTerminal(runtime, breakRun.runId)
  assert.equal(breakTerminal.status, 'completed')
  const breakResults = await api(runtime, `/workflow-runs/${encodeURIComponent(breakRun.runId)}/results?cursor=0&limit=100`)
  const breakLogs = await api(runtime, `/workflow-runs/${encodeURIComponent(breakRun.runId)}/logs?cursor=0&limit=100`)
  assert.equal(breakLogs.items.filter(item => item.nodeId === breakNodes.break && item.message.includes('跳出循环')).length, 1)
  assert.equal(breakResults.items.find(item => item.nodeId === breakNodes.tail)?.values.value, 1)
  checkpoint('正式模块条完成无限循环、跳出循环和循环完成路径；退出后尾节点只执行一次')

  const continueName = 'B3 跳过当前循环正式闭环'
  await newWorkflow(studio, continueName)
  await click(studio, '模块条')
  const continueNodes = {}
  continueNodes.initialize = await addBlock(studio, '添加模块', '设置变量')
  await setInput(studio, '[placeholder="变量名"]', 'skipped')
  await setInput(studio, '[placeholder="变量的值"]', '0')
  continueNodes.loop = await addBlock(studio, '添加模块', '循环')
  await setInput(studio, '[placeholder="输入循环次数或变量"]', '2')
  continueNodes.continue = await addLoopBodyBlock(studio, continueNodes.loop, '跳过当前循环')
  continueNodes.skipped = await addLoopBodyBlock(studio, continueNodes.loop, '自增自减')
  await setInput(studio, '[placeholder="要操作的变量名"]', 'skipped')
  await setInput(studio, '[placeholder="每次增加或减少的值"]', '1')
  continueNodes.tail = await addBlock(studio, '添加模块', '设置变量')
  await setInput(studio, '[placeholder="变量名"]', 'after_continue')
  await setInput(studio, '[placeholder="变量的值"]', '1')
  const continueWorkflow = await saveWorkflow(studio, runtime, continueName)
  const continueRun = await startWorkflow(studio, runtime, continueWorkflow.id)
  const continueTerminal = await waitForTerminal(runtime, continueRun.runId)
  assert.equal(continueTerminal.status, 'completed')
  const continueResults = await api(runtime, `/workflow-runs/${encodeURIComponent(continueRun.runId)}/results?cursor=0&limit=100`)
  const continueLogs = await api(runtime, `/workflow-runs/${encodeURIComponent(continueRun.runId)}/logs?cursor=0&limit=100`)
  assert.equal(continueLogs.items.filter(item => item.nodeId === continueNodes.continue && item.message.includes('继续下一次循环')).length, 2)
  assert.equal(continueResults.items.some(item => item.nodeId === continueNodes.skipped), false)
  assert.equal(continueResults.items.find(item => item.nodeId === continueNodes.tail)?.values.value, 1)
  checkpoint('正式模块条完成跳过当前循环；每轮剩余节点均未执行，循环完成路径继续执行')

  const stopName = 'B3 强制停止正式闭环'
  await newWorkflow(studio, stopName)
  await click(studio, '模块条')
  const stopNodes = {}
  stopNodes.stop = await addBlock(studio, '添加模块', '强制停止工作流执行')
  await setInput(studio, '[placeholder="输入停止原因，将显示在日志中"]', 'B3 正式停止')
  stopNodes.tail = await addBlock(studio, '添加模块', '设置变量')
  await setInput(studio, '[placeholder="变量名"]', 'should_not_run')
  await setInput(studio, '[placeholder="变量的值"]', '1')
  const stopWorkflow = await saveWorkflow(studio, runtime, stopName)
  const stopRun = await startWorkflow(studio, runtime, stopWorkflow.id)
  const stopTerminal = await waitForTerminal(runtime, stopRun.runId)
  assert.equal(stopTerminal.status, 'completed')
  const stopResults = await api(runtime, `/workflow-runs/${encodeURIComponent(stopRun.runId)}/results?cursor=0&limit=100`)
  const stopLogs = await api(runtime, `/workflow-runs/${encodeURIComponent(stopRun.runId)}/logs?cursor=0&limit=100`)
  assert.ok(stopLogs.items.some(item => item.nodeId === stopNodes.stop && item.message.includes('B3 正式停止')))
  assert.equal(stopResults.items.some(item => item.nodeId === stopNodes.tail), false)
  checkpoint('正式模块条完成强制停止；停止原因持久化，后续节点没有执行')

  const customDefinitionName = 'B3 自定义模块定义画布'
  await newWorkflow(studio, customDefinitionName)
  await click(studio, '模块条')
  await addBlock(studio, '添加模块', '设置变量')
  await setInput(studio, '[placeholder="变量名"]', 'module_output')
  await setInput(studio, '[placeholder="变量的值"]', '42')
  await saveWorkflow(studio, runtime, customDefinitionName)
  await clickRect(studio, "[...document.querySelectorAll('button')].find(e=>e.textContent.trim()==='自定义'&&e.parentElement?.textContent.includes('内置'))", 'custom module tab')
  await waitFor(studio, "Boolean(document.querySelector('input[placeholder=\"搜索自定义模块...\"]')?.getClientRects().length)", 'custom module list')
  await clickRect(studio, "[...document.querySelector('input[placeholder=\"搜索自定义模块...\"]')?.closest('.flex.flex-col.h-full')?.querySelectorAll('button')||[]].find(e=>e.textContent.trim()==='创建模块')", 'create custom module')
  await waitFor(studio, "Boolean([...document.querySelectorAll('[role=dialog]')].find(e=>e.textContent.includes('创建自定义模块')))", 'create custom module dialog')
  await setInput(studio, '[role="dialog"] #name', 'b3_formal_custom_module')
  await setInput(studio, '[role="dialog"] #displayName', 'B3 正式自定义模块')
  await click(studio, '添加输出', '[role="dialog"] button')
  await setInput(studio, '[role="dialog"] [placeholder="outputName"]', 'module_output')
  await setInput(studio, '[role="dialog"] [placeholder="输出标签"]', '正式输出')
  await click(studio, '创建模块', '[role="dialog"] button')
  const customModule = await waitForValue(async () => {
    const page = await api(runtime, '/custom-modules')
    return page.modules.find(module => module.name === 'b3_formal_custom_module') ?? null
  }, 'persisted custom module', 15_000)

  const customCallName = 'B3 自定义模块调用正式闭环'
  await newWorkflow(studio, customCallName)
  await click(studio, '流程图')
  await clickRect(studio, "[...document.querySelectorAll('button')].find(e=>e.textContent.trim()==='自定义'&&e.parentElement?.textContent.includes('内置'))", 'custom module tab in flow view')
  await waitFor(studio, `Boolean([...document.querySelectorAll('[draggable="true"]')].find(e=>e.textContent.includes(${JSON.stringify('B3 正式自定义模块')})))`, 'created custom module card')
  const customCallNodeId = await dropCustomModule(studio, customModule)
  const customCallWorkflow = await saveWorkflow(studio, runtime, customCallName)
  assert.equal(customCallWorkflow.nodes.find(node => node.id === customCallNodeId)?.data.customModuleId, customModule.id)
  const customCallRun = await startWorkflow(studio, runtime, customCallWorkflow.id)
  const customCallTerminal = await waitForTerminal(runtime, customCallRun.runId)
  assert.equal(customCallTerminal.status, 'completed')
  const customCallResults = await api(runtime, `/workflow-runs/${encodeURIComponent(customCallRun.runId)}/results?cursor=0&limit=100`)
  const customOuter = customCallResults.items.find(item => item.nodeId === customCallNodeId)
  assert.equal(customOuter?.values.outputs.module_output, 42)
  assert.equal(customOuter?.values.executed_nodes, 1)
  assert.ok(customCallResults.items.some(item => item.executionContext.scopes.some(scope => scope.kind === 'customModule' && scope.id === customModule.id)))
  checkpoint('正式 UI 从当前画布创建自定义模块、声明输出、拖入新流程并由生产 worker 隔离执行')

  const uiStopName = 'B3 千轮纯变量停止正式闭环'
  await newWorkflow(studio, uiStopName)
  await click(studio, '模块条')
  const uiStopNodes = {}
  uiStopNodes.initialize = await addBlock(studio, '添加模块', '设置变量')
  await setInput(studio, '[placeholder="变量名"]', 'ui_stop_counter')
  await setInput(studio, '[placeholder="变量的值"]', '0')
  uiStopNodes.loop = await addBlock(studio, '添加模块', '循环')
  await setInput(studio, '[placeholder="输入循环次数或变量"]', '1000')
  uiStopNodes.increment = await addLoopBodyBlock(studio, uiStopNodes.loop, '自增自减')
  await setInput(studio, '[placeholder="要操作的变量名"]', 'ui_stop_counter')
  await setInput(studio, '[placeholder="每次增加或减少的值"]', '1')
  for (let index = 2; index <= 5; index++) {
    uiStopNodes[`increment${index}`] = await addLoopBodyBlock(studio, uiStopNodes.loop, '自增自减')
    await setInput(studio, '[placeholder="要操作的变量名"]', 'ui_stop_counter')
    await setInput(studio, '[placeholder="每次增加或减少的值"]', '1')
  }
  uiStopNodes.tail = await addBlock(studio, '添加模块', '设置变量')
  await setInput(studio, '[placeholder="变量名"]', 'ui_stop_tail')
  await setInput(studio, '[placeholder="变量的值"]', '1')
  const uiStopWorkflow = await saveWorkflow(studio, runtime, uiStopName)
  const uiStopRun = await startWorkflow(studio, runtime, uiStopWorkflow.id)
  await click(studio, '停止')
  const uiStopTerminal = await waitForTerminal(runtime, uiStopRun.runId)
  assert.equal(uiStopTerminal.status, 'stopped')
  const uiStopSqlite = sqliteEvidence(userData, uiStopWorkflow.id, uiStopRun.runId)
  assert.equal(uiStopSqlite.run[0]?.cleanupState, 'completed')
  assert.equal(uiStopSqlite.run[0]?.activeSlot, null)
  const uiStopResults = await readRunResults(runtime, uiStopRun.runId)
  assert.equal(uiStopResults.some(item => item.nodeId === uiStopNodes.tail), false)
  const uiStopIncrementIds = new Set(Object.entries(uiStopNodes).filter(([key]) => key.startsWith('increment')).map(([, value]) => value))
  assert.ok(uiStopResults.filter(item => uiStopIncrementIds.has(item.nodeId)).length < 5000)
  const stoppedCount = uiStopResults.length
  await wait(300)
  assert.equal((await readRunResults(runtime, uiStopRun.runId)).length, stoppedCount)
  checkpoint('正式 UI 在 1,000 轮纯变量流程中点击停止；后继未调度、结果停止增长且资源清理完成')

  await capture(studio, join(evidenceDir, 'completed.png'))
  const report = {
    evidenceId: 'BE-B3-formal-control-flow-electron', checkedAt: new Date().toISOString(), gitHead,
    result: 'passed', platform: `${process.platform}-${process.arch}`, entry: 'development-build',
    workflowId: saved.id, profileId: profile.id, runId: startedRun.runId, checks,
    workflowPersistence: { revision: saved.revision, nodeCount: savedNodeCount, edgeCount: savedEdgeCount },
    execution: { status: terminalRun.status, resultCount: results.items.length, logCount: logs.items.length },
    assertions: {
      loopValues: incrementResults.map(item => item.values.new_value),
      loopIterations: incrementResults.map(item => item.executionContext.loops[0].iteration),
      selectedBranch: 'true', skippedBranchNodeId: falseId,
      subflowScope: innerResult.executionContext.scopes,
      parallelStartNodes: [byType('set_variable').find(node => node.data.variableName === 'total').id, subflowCallId],
    },
    httpEvidence: { results: results.items, logs: logs.items }, sqliteEvidence: sqlite,
    additionalEvidence: {
      childWorkflowId: childWorkflow.id,
      utilityWorkflowId: utilityWorkflow.id,
      utilityRunId: utilityRun.runId,
      utilityNodeIds: utilityNodes,
      utilityResultCount: utilityResults.items.length,
      foreach: { workflowId: foreachWorkflow.id, runId: foreachRun.runId, nodeIds: foreachNodes },
      breakLoop: { workflowId: breakWorkflow.id, runId: breakRun.runId, nodeIds: breakNodes },
      continueLoop: { workflowId: continueWorkflow.id, runId: continueRun.runId, nodeIds: continueNodes },
      stopWorkflow: { workflowId: stopWorkflow.id, runId: stopRun.runId, nodeIds: stopNodes },
      recursiveVariables: { workflowId: recursiveWorkflow.id, runId: recursiveRun.runId, nodeIds: recursiveNodes },
      customModule: { moduleId: customModule.id, workflowId: customCallWorkflow.id, runId: customCallRun.runId, nodeId: customCallNodeId },
      uiStop: { workflowId: uiStopWorkflow.id, runId: uiStopRun.runId, nodeIds: uiStopNodes, resultCount: stoppedCount, sqlite: uiStopSqlite },
    },
    browserEvidence: { cloakBrowserProcessesAfter: cloakProcesses(userData) },
    boundaries: {
      workspace: 'ephemeral', userDatabaseTouched: false, browserLaunch: 'none (pure data)',
      interaction: 'main window and formal Studio UI through CDP mouse/keyboard plus macOS Cmd+W; public APIs and SQLite only read evidence after UI actions; no Store or page-internal business function access',
      parallelMeaning: 'the persisted graph has separate top-level control-flow and subflow-call entry nodes; the production scheduler executes start nodes concurrently',
    },
  }
  await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
} catch (error) {
  if (error instanceof EvidenceComplete) {
    // The focused evidence mode completed before the broader B3 matrix.
  } else {
  if (studio) {
    await capture(studio, join(evidenceDir, 'blocked-studio.png')).catch(() => {})
    await writeFile(join(evidenceDir, 'blocked-studio.txt'), await studio.evaluate('document.body.innerText').catch(() => 'unavailable')).catch(() => {})
  } else if (main) {
    await capture(main, join(evidenceDir, 'blocked-main.png')).catch(() => {})
    await writeFile(join(evidenceDir, 'blocked-main.txt'), await main.evaluate('document.body.innerText').catch(() => 'unavailable')).catch(() => {})
  }
  const ui = studio ? await studio.evaluate("[...document.querySelectorAll('button')].filter(e=>e.textContent.trim()==='模块条').map(e=>({html:e.outerHTML.slice(0,500),visible:Boolean(e.getClientRects().length),rect:(()=>{const r=e.getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height}})()}))").catch(() => []) : []
  await writeFile(join(evidenceDir, 'blocked.json'), JSON.stringify({ checkedAt: new Date().toISOString(), gitHead, checks, observedEvents, ui, error: error instanceof Error ? error.stack : String(error) }, null, 2) + '\n')
  throw error
  }
} finally {
  if (sshCredential && runtime) {
    await api(runtime, `/credentials/${encodeURIComponent(sshCredential)}`, { method: 'DELETE' }).catch(error => console.error('SSH fixture credential cleanup failed', error.message))
  }
  eventAbort?.abort(); studio?.close(); main?.close(); native?.close(); await stop(desktop?.child)
  sshFixture?.stdin.end(); await stop(sshFixture)
  await rm(userData, { recursive: true, force: true })
  if (httpFixture) {
    httpFixture.closeAllConnections()
    await new Promise(resolve => httpFixture.close(resolve))
  }
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
  } catch (error) { if (!signal.aborted) output.push({ name: 'collector:error', data: String(error) }) }
}

async function openStudioFromMain(cdp, origin, label = '工作流工作台') {
  await click(cdp, label)
  const target = await waitForValue(async () => {
    const targets = await (await fetch(`${origin}/json/list`)).json()
    return targets.find(item => item.type === 'page' && item.url.includes('studio.html')) ?? null
  }, 'Studio target', 15_000)
  return connectCdp(target.webSocketDebuggerUrl)
}

async function waitForNoStudio(origin, timeoutMs = 15_000) {
  await waitForValue(async () => {
    const targets = await (await fetch(`${origin}/json/list`)).json()
    return targets.some(target => target.type === 'page' && target.url.includes('studio.html')) ? null : true
  }, 'Studio window close', timeoutMs)
}

async function newWorkflow(cdp, name) {
  await click(cdp, '新建')
  await waitFor(cdp, "document.querySelectorAll('.react-flow__node').length === 0", `new workflow ${name}`)
  await setInput(cdp, 'input[placeholder="工作流名称"]', name)
}

async function showBlockView(cdp) {
  for (let attempt = 0; attempt < 3; attempt++) {
    await click(cdp, '模块条')
    if (await cdp.evaluate("document.body.innerText.includes('添加模块')")) return
    await wait(150)
  }
  throw new Error('模块条视图未显示添加模块入口')
}

async function addGlobalVariable(cdp, name, type, value) {
  if (await cdp.evaluate("Boolean(document.querySelector('button[title=\"展开\"]')?.getClientRects().length)")) await click(cdp, '', 'button[title="展开"]')
  await click(cdp, '全局变量')
  await waitFor(cdp, "[...document.querySelectorAll('button')].some(e=>e.getClientRects().length&&e.textContent.trim()==='添加变量')", 'global variable editor')
  await click(cdp, '添加变量')
  await setInput(cdp, 'input[placeholder="变量名"]', name)
  if (type !== 'string') await selectNative(cdp, '[aria-label="变量类型"]', ({ array: '列表', object: '字典', number: '数字', boolean: '布尔' })[type])
  await setInput(cdp, `input[placeholder=${JSON.stringify(({ string: '值', array: '[]', object: '{}', number: '0' })[type])}]`, value)
  await click(cdp, '确认添加变量', 'button')
}

async function saveWorkflow(cdp, runtime, name) {
  await click(cdp, '保存')
  return waitForValue(async () => {
    const saved = (await api(runtime, '/workflows')).find(item => item.name === name)
    if (saved) return saved
    const failure = await cdp.evaluate("[...document.querySelectorAll('*')].find(e=>e.getClientRects().length&&e.textContent?.startsWith('保存失败:'))?.textContent||''")
    assert.equal(failure, '', failure)
    return null
  }, `save ${name}`, 15_000)
}

async function startWorkflow(cdp, runtime, documentId) {
  await click(cdp, '运行 (F5)', '[aria-label="运行 (F5)"]')
  await click(cdp, '运行 (F5)', '[role="menuitem"]')
  return waitForValue(async () => {
    const page = await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(documentId)}&cursor=0&limit=20`)
    return page.items[0] ?? null
  }, `run ${documentId}`, 20_000)
}

async function runToCanvasNode(cdp, runtime, documentId, nodeId) {
  await click(cdp, '流程图')
  const existing = new Set((await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(documentId)}&cursor=0&limit=20`)).items.map(item => item.runId))
  const nodePoint = await point(cdp, `.react-flow__node[data-id=${JSON.stringify(nodeId)}]`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...nodePoint })
  await wait(150)
  const button = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__node[data-id=${JSON.stringify(nodeId)}] button[data-tip="运行至此节点（保留前置上下文）"]');if(!e)return null;const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, `run-to button ${nodeId}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...button })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...button, button: 'left', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...button, button: 'left', clickCount: 1 })
  const run = await waitForValue(async () => {
    const page = await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(documentId)}&cursor=0&limit=20`)
    return page.items.find(item => !existing.has(item.runId)) ?? null
  }, `run-to ${nodeId}`, 20_000)
  await waitForValue(async () => (await api(runtime, `/workflow-runs/${encodeURIComponent(run.runId)}`)).status === 'paused' ? run : null, `pause at ${nodeId}`, 30_000)
  return run
}

async function toggleBreakpoint(cdp, nodeId) {
  await click(cdp, '流程图')
  const nodePoint = await point(cdp, `.react-flow__node[data-id=${JSON.stringify(nodeId)}]`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...nodePoint })
  const button = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__node[data-id=${JSON.stringify(nodeId)}] button[data-tip="设置断点（运行到此暂停）"]');if(!e)return null;const r=e.getBoundingClientRect();return{x:r.right-2,y:r.y+r.height/2}})()`, `breakpoint button ${nodeId}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...button, button: 'left', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...button, button: 'left', clickCount: 1 })
  await waitFor(cdp, `Boolean(document.querySelector('.react-flow__node[data-id=${JSON.stringify(nodeId)}] button[data-tip="移除断点"]'))`, `breakpoint enabled ${nodeId}`)
}

async function waitForPauseEvent(events, runId, count) {
  return waitForValue(() => {
    const pauses = events.filter(event => event.name === 'execution:paused' && event.data?.runId === runId)
    return pauses.length >= count ? pauses[count - 1].data : null
  }, `pause ${count} for ${runId}`, 30_000)
}

async function waitForRunReady(cdp) {
  await waitFor(cdp, "Boolean(document.querySelector('[aria-label=\"运行 (F5)\"]')?.getClientRects().length)", 'Studio run controls ready', 15_000)
}

async function waitForTerminal(runtime, runId) {
  return waitForValue(async () => {
    const value = await api(runtime, `/workflow-runs/${encodeURIComponent(runId)}`)
    return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.status) ? value : null
  }, `terminal run ${runId}`, 60_000)
}

async function readRunResults(runtime, runId) {
  const items = []
  let cursor = 0
  do {
    const page = await api(runtime, `/workflow-runs/${encodeURIComponent(runId)}/results?cursor=${cursor}&limit=500`)
    items.push(...page.items)
    cursor = page.nextCursor
  } while (cursor !== null)
  return items
}

async function closeWindowThroughOs() {
  for (let attempt = 0; attempt < 3; attempt++) {
    const exists = await native.evaluate("(()=>{const w=qaElectron.BrowserWindow.getAllWindows().find(w=>w.getTitle().includes('工作流工作台'));if(!w)return false;qaElectron.app.focus({steal:true});w.show();w.focus();return true})()")
    if (!exists) return
    await wait(250)
    execFileSync('osascript', ['-e', 'tell application "System Events" to keystroke "w" using command down'])
    await wait(500)
    if (!await native.evaluate("qaElectron.BrowserWindow.getAllWindows().some(w=>w.getTitle().includes('工作流工作台'))")) return
    if (await studio.evaluate("[...document.querySelectorAll('button')].some(e=>e.getClientRects().length&&e.textContent.includes('保存后继续'))")) {
      await click(studio, '保存后继续')
      await wait(700)
    }
  }
  if (await native.evaluate("qaElectron.BrowserWindow.getAllWindows().some(w=>w.getTitle().includes('工作流工作台'))")) {
    execFileSync('osascript', ['-e', 'tell application "System Events"', '-e', `tell (first application process whose unix id is ${desktop.child.pid})`, '-e', 'click (first button of (first window whose name contains "工作流工作台") whose subrole is "AXCloseButton")', '-e', 'end tell', '-e', 'end tell'])
    await wait(500)
  }
}

async function waitForValue(read, description, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  let last
  while (Date.now() < deadline) {
    last = await read()
    if (last) return last
    await wait(150)
  }
  throw new Error(`timed out waiting for ${description}: ${JSON.stringify(last)}`)
}

async function point(cdp, selector, text = '') {
  return waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length),text=${JSON.stringify(text)};const e=!text?rows[0]:rows.find(e=>e.getAttribute('aria-label')===text)||rows.find(e=>e.textContent.trim()===text)||rows.find(e=>e.textContent.includes(text));if(!e||e.disabled)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect();for(const py of [.5,.25,.75])for(const px of [.5,.25,.75]){const x=r.x+r.width*px,y=r.y+r.height*py;if(e.contains(document.elementFromPoint(x,y)))return{x,y}}return null})()`, `unobscured ${text || selector}`)
}

async function click(cdp, text, selector = 'button') {
  const p = await point(cdp, selector, text)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', buttons: 1, clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', buttons: 0, clickCount: 1 })
  await wait(100)
}

async function clickRect(cdp, expression, description) {
  const p = await waitFor(cdp, `(()=>{const e=${expression};if(!e||e.disabled)return null;const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, description)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', buttons: 1, clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', buttons: 0, clickCount: 1 })
  await wait(100)
}

async function setInput(cdp, selector, value) { return setInputAt(cdp, selector, 0, value) }
async function setVariableNameInput(cdp, selector, value) { return setInputAt(cdp, selector, 0, value, { dismissSuggestions: true }) }

async function setInputAt(cdp, selector, index, value, { dismissSuggestions = false } = {}) {
  const p = await waitFor(cdp, `(()=>{const e=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length)[${index}];if(!e)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, `${selector}[${index}]`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 3 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 3 })
  await cdp.command('Input.insertText', { text: value })
  if (dismissSuggestions) await press(cdp, 'Escape')
  await press(cdp, 'Tab', { code: 'Tab', keyCode: 9 })
}

async function selectNative(cdp, selector, expectedText) {
  for (let attempt = 0; attempt < 3; attempt++) {
    if (!await cdp.evaluate(`document.querySelector(${JSON.stringify(selector)})?.getAttribute('data-state')==='open'`)) await click(cdp, '', selector)
    try {
      await waitFor(cdp, `Boolean([...document.querySelectorAll('[role="option"]')].some(e=>e.getClientRects().length&&e.textContent.includes(${JSON.stringify(expectedText)})))`, `${selector} option`, 3_000)
      await click(cdp, expectedText, '[role="option"]')
      await waitFor(cdp, `document.querySelector(${JSON.stringify(selector)})?.textContent.includes(${JSON.stringify(expectedText)})`, `${selector} selected`, 3_000)
      return
    } catch {
      continue // A surrounding form refresh can close the select before the option is applied.
    }
  }
  throw new Error(`${selector} could not select ${expectedText}`)
}

async function selectAutomationWorkflow(cdp, name, id) {
  const selected = `[role="combobox"][aria-label="关联工作流"][data-choice-value=${JSON.stringify(id)}]`
  const combo = '[role="combobox"][aria-label="关联工作流"]'
  for (let attempt = 0; attempt < 3; attempt++) {
    if (!await cdp.evaluate(`document.querySelector(${JSON.stringify(combo)})?.getAttribute('data-state')==='open'`)) await click(cdp, '', combo)
    try {
      await waitFor(cdp, `Boolean([...document.querySelectorAll('[role="option"]')].some(e=>e.getClientRects().length&&e.textContent.trim()===${JSON.stringify(name)}))`, `workflow option ${name}`, 4_000)
    } catch {
      continue // Loading the project workflow list can replace and close the open select.
    }
    await click(cdp, name, '[role="option"]')
    await waitFor(cdp, `Boolean(document.querySelector(${JSON.stringify(selected)}))`, `selected workflow ${name}`)
    return
  }
  const state = await cdp.evaluate(`({open:document.querySelector(${JSON.stringify(combo)})?.getAttribute('data-state'),options:[...document.querySelectorAll('[role="option"]')].map(e=>e.textContent.trim())})`)
  throw new Error(`workflow option ${name} unavailable: ${JSON.stringify(state)}`)
}

async function press(cdp, key, { code = key, keyCode = 0 } = {}) {
  await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key, code, windowsVirtualKeyCode: keyCode })
  await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key, code, windowsVirtualKeyCode: keyCode })
  await wait(60)
}

async function addBlock(cdp, slotText, label) {
  const before = await cdp.evaluate("[...document.querySelectorAll('[data-block-id]')].map(e=>e.getAttribute('data-block-id'))")
  if (!await cdp.evaluate("Boolean(document.querySelector('input[placeholder=\"搜索模块（支持拼音）\"]')?.getClientRects().length)")) await click(cdp, slotText, 'div')
  await setInput(cdp, 'input[placeholder="搜索模块（支持拼音）"]', label)
  await click(cdp, label)
  const nodeId = await waitFor(cdp, `(()=>{const before=new Set(${JSON.stringify(before)});return[...document.querySelectorAll('[data-block-id]')].map(e=>e.getAttribute('data-block-id')).find(id=>!before.has(id))||null})()`, `new ${label} block`)
  await click(cdp, '', `[data-block-id="${nodeId}"]`)
  return nodeId
}

async function addLoopBodyBlock(cdp, loopId, label) {
  const before = await cdp.evaluate("[...document.querySelectorAll('[data-block-id]')].map(e=>e.getAttribute('data-block-id'))")
  const p = await waitFor(cdp, `(()=>{let root=document.querySelector('[data-block-id=${JSON.stringify(loopId)}]')?.parentElement;while(root){const e=[...root.querySelectorAll('div')].find(e=>e.getClientRects().length&&e.textContent.trim()==='添加循环体步骤');if(e){const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}}root=root.parentElement}return null})()`, `loop body slot ${loopId}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 })
  await setInput(cdp, 'input[placeholder="搜索模块（支持拼音）"]', label)
  await click(cdp, label)
  const nodeId = await waitFor(cdp, `(()=>{const before=new Set(${JSON.stringify(before)});return[...document.querySelectorAll('[data-block-id]')].map(e=>e.getAttribute('data-block-id')).find(id=>!before.has(id))||null})()`, `new ${label} block in ${loopId}`)
  await click(cdp, '', `[data-block-id="${nodeId}"]`)
  return nodeId
}

async function addCanvasNode(cdp, label, position) {
  const before = await cdp.evaluate("[...document.querySelectorAll('.react-flow__node')].map(e=>e.getAttribute('data-id'))")
  const target = position
    ? await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__pane');if(!e)return null;const r=e.getBoundingClientRect(),x=r.x+r.width*${position.xRatio},y=r.y+r.height*${position.yRatio};return document.elementFromPoint(x,y)===e?{x,y}:null})()`, `empty positioned canvas point for ${label}`)
    : await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__pane');if(!e)return null;const r=e.getBoundingClientRect();for(let row=1;row<8;row++)for(let col=1;col<10;col++){const x=r.x+r.width*col/10,y=r.y+r.height*row/8;if(document.elementFromPoint(x,y)===e)return{x,y}}return null})()`, `empty canvas point for ${label}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...target, button: 'right', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...target, button: 'right', clickCount: 1 })
  await setInput(cdp, 'input[placeholder="搜索模块（支持拼音）"]', label)
  await click(cdp, label, '[role="button"]')
  return waitFor(cdp, `(()=>{const before=new Set(${JSON.stringify(before)});return[...document.querySelectorAll('.react-flow__node')].map(e=>e.getAttribute('data-id')).find(id=>!before.has(id))||null})()`, `new ${label} node`)
}

async function dropCustomModule(cdp, module) {
  const before = await cdp.evaluate("[...document.querySelectorAll('.react-flow__node')].map(e=>e.getAttribute('data-id'))")
  const points = await waitFor(cdp, `(()=>{const source=[...document.querySelectorAll('[draggable="true"]')].find(e=>e.textContent.includes(${JSON.stringify('B3 正式自定义模块')})),target=document.querySelector('.react-flow__pane');if(!source||!target)return null;const a=source.getBoundingClientRect(),b=target.getBoundingClientRect();for(let row=1;row<8;row++)for(let col=1;col<10;col++){const x=b.x+b.width*col/10,y=b.y+b.height*row/8;if(document.elementFromPoint(x,y)===target)return{a:{x:a.x+a.width/2,y:a.y+a.height/2},b:{x,y}}}return null})()`, 'custom module drag points')
  const data = {
    items: [{ mimeType: 'application/reactflow', data: JSON.stringify({ type: 'custom_module', moduleId: module.id, moduleName: module.name, displayName: module.display_name, icon: module.icon, color: module.color, description: module.description }) }],
    dragOperationsMask: 16,
  }
  await cdp.command('Input.dispatchDragEvent', { type: 'dragEnter', ...points.b, data })
  await cdp.command('Input.dispatchDragEvent', { type: 'dragOver', ...points.b, data })
  await cdp.command('Input.dispatchDragEvent', { type: 'drop', ...points.b, data })
  return waitFor(cdp, `(()=>{const before=new Set(${JSON.stringify(before)});return[...document.querySelectorAll('.react-flow__node')].map(e=>e.getAttribute('data-id')).find(id=>!before.has(id))||null})()`, 'custom module canvas node')
}

async function resizeGroup(cdp, groupId, dx, dy) {
  await click(cdp, '', `.react-flow__node[data-id="${groupId}"]`)
  const from = await waitFor(cdp, `(()=>{const root=document.querySelector('.react-flow__node[data-id=${JSON.stringify(groupId)}]');if(!root)return null;const e=[...root.querySelectorAll('.react-flow__resize-control')].find(e=>e.classList.contains('right')&&e.classList.contains('bottom'));if(!e)return null;const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, `resize handle ${groupId}`)
  const to = { x: from.x + dx, y: from.y + dy }
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...from })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...from, button: 'left', buttons: 1, clickCount: 1 })
  for (let step = 1; step <= 12; step++) await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', x: from.x + dx * step / 12, y: from.y + dy * step / 12, button: 'left', buttons: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...to, button: 'left', buttons: 0, clickCount: 1 })
  await wait(120)
}

async function connectNodes(cdp, sourceId, targetId, handleId) {
  const handleSelector = handleId ? `[data-handleid="${handleId}"]` : ':not([data-handleid])'
  const points = await waitFor(cdp, `(()=>{const a=document.querySelector('.react-flow__node[data-id=${JSON.stringify(sourceId)}] .react-flow__handle.source${handleSelector}'),b=document.querySelector('.react-flow__node[data-id=${JSON.stringify(targetId)}] .react-flow__handle.target');if(!a||!b)return null;const ar=a.getBoundingClientRect(),br=b.getBoundingClientRect();return{a:{x:ar.x+ar.width/2,y:ar.y+ar.height/2},b:{x:br.x+br.width/2,y:br.y+br.height/2}}})()`, `handles ${sourceId} -> ${targetId}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...points.a })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...points.a, button: 'left', buttons: 1, clickCount: 1 })
  for (let step = 1; step <= 12; step++) await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', x: points.a.x + (points.b.x - points.a.x) * step / 12, y: points.a.y + (points.b.y - points.a.y) * step / 12, button: 'left', buttons: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...points.b, button: 'left', buttons: 0, clickCount: 1 })
  await wait(100)
}

function sqliteEvidence(workspace, workflowId, runId) {
  const database = join(workspace, 'data', 'autoflow.sqlite3'), workflow = sqlLiteral(workflowId), run = sqlLiteral(runId)
  return {
    document: sqliteRows(database, `SELECT id,revision,json_array_length(document,'$.nodes') AS nodeCount,json_array_length(document,'$.edges') AS edgeCount FROM workflow_documents WHERE id=${workflow}`),
    run: sqliteRows(database, `SELECT id AS runId,json_extract(payload,'$.status') AS status,json_extract(payload,'$.cleanupState') AS cleanupState,active_slot AS activeSlot FROM workflow_runs WHERE id=${run}`),
  }
}

function sqliteRows(database, query) {
  const output = execFileSync('sqlite3', ['-json', database, query], { encoding: 'utf8' }).trim()
  return output ? JSON.parse(output) : []
}
function sqlLiteral(value) { return `'${String(value).replaceAll("'", "''")}'` }
function listeningPid(baseUrl) {
  const port = new URL(baseUrl).port
  const output = execFileSync('lsof', ['-nP', `-iTCP:${port}`, '-sTCP:LISTEN', '-t'], { encoding: 'utf8' }).trim()
  const pid = Number(output.split(/\s+/)[0])
  assert.ok(Number.isSafeInteger(pid) && pid > 0, `sidecar listener not found on ${port}`)
  return pid
}
function cloakProcesses(workspace) { return execFileSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).split('\n').filter(line => line.includes(workspace) && /Chromium|CloakBrowser/.test(line)) }
async function capture(cdp, path) { await cdp.evaluate('document.fonts.ready.then(()=>true)'); const { data } = await cdp.command('Page.captureScreenshot', { format: 'png' }); await writeFile(path, data, 'base64') }
