import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import { mkdtemp, mkdir, readFile, readdir, rename, rm, writeFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import { tmpdir } from 'node:os'
import { basename, dirname, join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const sourceKernel = process.env.AUTOFLOW_B1_KERNEL_DIR
  ?? '/Users/zhangtiancheng/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2'
const kernelVersion = basename(sourceKernel).replace(/^chromium-/, '')
const failedPauseOnly = process.env.AUTOFLOW_B8_FAILED_PAUSE_ONLY === '1'
const runToOnly = process.env.AUTOFLOW_B8_RUN_TO_ONLY === '1'
const b8Only = failedPauseOnly || runToOnly
const projectMode = process.env.AUTOFLOW_B1_PROJECT === '1'
const evidenceRoot = join(root, `docs/migration/studio-backend-migration/evidence/${projectMode ? 'project-integration' : b8Only ? 'b8' : 'b1'}`)
const evidencePrefix = failedPauseOnly ? 'formal-failed-pause-electron-' : runToOnly ? 'formal-run-to-electron-' : 'formal-electron-'
const evidenceDir = await mkdtemp(join(evidenceRoot, evidencePrefix))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-b1-'))
const pageUrl = pathToFileURL(join(root, 'apps/backend/tests/fixtures/workflow-page.html')).href
const slowServer = createServer(() => undefined)
await new Promise((resolve, reject) => {
  slowServer.once('error', reject)
  slowServer.listen(0, '127.0.0.1', resolve)
})
const slowUrl = `http://127.0.0.1:${slowServer.address().port}/pending-navigation`
const isolatedKernel = join(userData, 'data', 'kernels', basename(sourceKernel))
const unavailableKernel = `${isolatedKernel}.unavailable`
const checks = []
const observedEvents = []
let desktop
let main
let studio
let native
let eventAbort
let kernelMoved = false
let projectId = null

await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await mkdir(join(userData, 'data', 'kernels'), { recursive: true })
execFileSync('cp', ['-cR', sourceKernel, join(userData, 'data', 'kernels', basename(sourceKernel))])

try {
  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'] })
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
      name: 'B1 正式验收配置', description: '隔离工作区中的 CloakBrowser 配置', startUrl: 'about:blank',
      locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false, headless: false, humanize: false,
      humanPreset: 'default', userAgent: null, viewportJson: { width: 1280, height: 720 }, colorScheme: 'light',
      extensionPathsJson: [], expertArgsJson: [], browserVersion: kernelVersion, browserEdition: 'public',
      releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null,
    },
  })
  checkpoint('主应用真实服务在临时工作区创建 CloakBrowser Profile')

  if (projectMode) {
    await click(main, '项目', 'a, button')
    await click(main, '新建项目')
    await setInput(main, '#project-name', 'Studio 五节点项目验收')
    await click(main, '创建项目')
    await waitFor(main, "document.body?.innerText.includes('Studio 五节点项目验收')", 'project created')
    if (!await main.evaluate('Boolean(document.querySelector(\'[aria-label="项目功能"]\'))')) await click(main, 'Studio 五节点项目验收', '[role="button"],button')
    await waitFor(main, 'Boolean(document.querySelector(\'[aria-label="项目功能"]\'))', 'project page')
    projectId = (await main.evaluate('location.hash')).match(/projects\/([^/]+)/)?.[1]
    assert.ok(projectId)
    await click(main, '自动化', '[aria-label="项目功能"] button,[aria-label="项目功能"] [role="tab"]')
    await waitFor(main, "document.body?.innerText.includes('还没有自动化')", 'empty project automation directory')
    checkpoint('正式项目 UI 新建项目，由项目自动化目录进入 Studio')
  }

  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库') && document.body.innerText.includes('213')", 'formal Studio', 30_000)
  assert.equal(await studio.evaluate("document.body.innerText.includes('Mock 接口')"), false)
  await waitFor(studio, `document.querySelector('[aria-label="运行浏览器配置"]')?.value === ${JSON.stringify(profile.id)}`, 'managed Profile selection')
  checkpoint('主窗口通过真实点击打开正式 Studio，Studio 只读取主应用 Profile')

  await click(studio, '新建')
  await waitFor(studio, "document.querySelectorAll('.react-flow__node').length === 0", 'new empty workflow')
  checkpoint('通过正式新建入口创建空工作流')

  await setInput(studio, 'input[placeholder="工作流名称"]', 'B1 五节点正式闭环')
  const modules = [
    ['打开网页', 'open_page', { placeholder: 'https://example.com', value: pageUrl }],
    ['输入文本', 'input_text', { placeholder: '例如: #input, .text-field', value: '#workflow-input', extra: ['textarea[placeholder="要输入的文本内容"]', '真实 CloakBrowser 五节点'] }],
    ['点击元素', 'click_element', { placeholder: '例如: #button, .submit', value: '.workflow-action' }],
    ['提取数据', 'get_element_info', { placeholder: '例如: #title, .content', value: '#workflow-output', extra: ['#variableName', 'result'] }],
    ['网页截图', 'screenshot', { placeholder: null, value: null }],
  ]
  const nodeIds = []
  for (let index = 0; index < modules.length; index++) {
    const [label, type, config] = modules[index]
    await addFromQuickPicker(studio, index, label)
    const node = await waitFor(studio, `(()=>{const rows=[...document.querySelectorAll('.react-flow__node')].filter(e=>e.textContent.includes(${JSON.stringify(label)}));const e=rows.at(-1);return e?.dataset.id||null})()`, `node ${type}`)
    nodeIds.push(node)
    await click(studio, '', `.react-flow__node[data-id=${JSON.stringify(node)}]`)
    if (config.placeholder) await setInput(studio, `[placeholder=${JSON.stringify(config.placeholder)}]`, config.value)
    if (config.extra) await setInput(studio, config.extra[0], config.extra[1])
  }
  assert.equal(new Set(nodeIds).size, 5)
  assert.equal(await studio.evaluate("document.querySelectorAll('.react-flow__node').length"), 5)
  checkpoint('通过画布原生右键菜单逐一添加并配置五个节点，没有直接修改 Store')

  await arrangeNodes(studio, nodeIds)
  for (let index = 0; index < nodeIds.length - 1; index++) await connectNodes(studio, nodeIds[index], nodeIds[index + 1])
  await waitFor(studio, "document.querySelectorAll('.react-flow__edge').length === 4", 'four workflow edges')
  checkpoint('通过画布连接手柄建立五节点顺序链')

  await click(studio, '保存')
  await waitFor(studio, "document.body?.innerText.includes('工作流已保存: B1 五节点正式闭环')", 'workflow save acknowledgement')
  const savedList = await api(runtime, '/workflows')
  const saved = savedList.find(item => item.name === 'B1 五节点正式闭环')
  assert.ok(saved)
  assert.equal(saved.revision, 1)
  assert.equal(saved.nodes.length, 5)
  assert.equal(saved.edges.length, 4)
  if (projectMode) assert.equal(saved.projectId, projectId)
  checkpoint('正式保存经真实 HTTP 写入 SQLite，返回修订 1')

  if (runToOnly) {
    const runId = await verifyRunToTarget({
      studio, runtime, saved, nodeIds, userData, evidenceDir, observedEvents,
    })
    const report = {
      evidenceId: 'BE-B8-run-to-formal-electron', checkedAt: new Date().toISOString(),
      gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
      buildSha256: await buildHash(), workflowId: saved.id, profileId: profile.id, runId,
      result: 'passed', checks, platform: `${process.platform}-${process.arch}`, entry: 'development-build',
      boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browser: 'CloakBrowser only', interaction: 'CDP mouse and keyboard; no Store access' },
    }
    await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
    console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
  } else if (failedPauseOnly) {
    const failedRunId = await verifyFailedPause({
      studio, runtime, saved, nodeId: nodeIds[2], priorRunIds: [], userData, evidenceDir, observedEvents,
    })
    const report = {
      evidenceId: 'BE-B8-failed-pause-formal-electron', checkedAt: new Date().toISOString(),
      gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
      buildSha256: await buildHash(), workflowId: saved.id, profileId: profile.id, failedRunId,
      result: 'passed', checks, platform: `${process.platform}-${process.arch}`, entry: 'development-build',
      boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browser: 'CloakBrowser only', interaction: 'CDP mouse and keyboard; no Store access' },
    }
    await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
    console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
  } else {
  await setInput(studio, 'input[placeholder="工作流名称"]', 'B1 五节点正式闭环 · 关窗保存')
  await closeWindowThroughOs(desktop.child.pid)
  await waitFor(studio, "document.body?.innerText.includes('保存当前工作流？')", 'normal-close draft prompt')
  await click(studio, '取消')
  assert.equal(await hasStudioTarget(desktop.debugOrigin), true)
  assert.equal(await studio.evaluate("document.querySelector('input[placeholder=\"工作流名称\"]')?.value"), 'B1 五节点正式闭环 · 关窗保存')
  assert.equal((await api(runtime, `/workflows/${encodeURIComponent(saved.id)}`)).revision, 1)
  checkpoint(`通过 macOS ${projectMode ? '原生窗口关闭按钮' : '系统级 Cmd+W'}触发正常关窗离开协调；取消后窗口、草稿和已保存修订均保持不变`)

  await closeWindowThroughOs(desktop.child.pid)
  await waitFor(studio, "document.body?.innerText.includes('保存当前工作流？')", 'second normal-close draft prompt')
  await click(studio, '保存后继续')
  studio.close(); studio = undefined
  await waitForNoStudio(desktop.debugOrigin)
  const closedSaved = await waitForValue(async () => {
    const value = await api(runtime, `/workflows/${encodeURIComponent(saved.id)}`)
    return value.revision === 2 && value.name === 'B1 五节点正式闭环 · 关窗保存' ? value : null
  }, 'normal-close saved revision', 10_000)
  checkpoint('再次正常关闭并选择保存后继续；保存成功后窗口才关闭，SQLite 修订递增')
  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库')", 'reopened Studio', 30_000)
  if (!await studio.evaluate("document.querySelectorAll('.react-flow__node').length === 5 && document.querySelector('input[placeholder=\"工作流名称\"]')?.value === 'B1 五节点正式闭环 · 关窗保存'")) {
    await click(studio, '打开')
    await click(studio, '打开工作流 B1 五节点正式闭环 · 关窗保存', '[role="button"]')
  }
  await waitFor(studio, "document.querySelector('input[placeholder=\"工作流名称\"]')?.value === 'B1 五节点正式闭环 · 关窗保存' && document.querySelectorAll('.react-flow__node').length === 5", 'persisted workflow reopen')
  assert.equal(await studio.evaluate("document.querySelectorAll('.react-flow__edge').length"), 4)
  assert.equal(closedSaved.nodes.length, 5)
  assert.equal(closedSaved.edges.length, 4)
  checkpoint('正常关闭并重开正式窗口后，从 SQLite 恢复名称、节点、配置和连线')

  await click(studio, '运行 (F5)', '[aria-label="运行 (F5)"]')
  await click(studio, '运行 (F5)', '[role="menuitem"]')
  const startedRun = await waitForValue(async () => {
    const page = await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(saved.id)}&cursor=0&limit=20`)
    return page.items[0] ?? null
  }, 'persisted workflow run', 20_000)
  const terminalRun = await waitForValue(async () => {
    const value = await api(runtime, `/workflow-runs/${encodeURIComponent(startedRun.runId)}`)
    return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.status) ? value : null
  }, 'workflow terminal persistence', 120_000)
  assert.equal(terminalRun.status, 'completed')
  if (projectMode) assert.equal(terminalRun.projectId, projectId)
  await waitForValue(async () => observedEvents.find(event => event.name === 'execution:completed' && event.data?.runId === startedRun.runId) ?? null, 'raw SSE terminal event', 10_000)
  await click(studio, '执行日志')
  await waitFor(studio, "document.body?.innerText.includes('执行完成')", 'rendered SSE terminal event', 10_000)
  const runId = startedRun.runId
  const results = await api(runtime, `/workflow-runs/${encodeURIComponent(runId)}/results?cursor=0&limit=50`)
  assert.equal(results.items.find(item => item.nodeId === nodeIds[3])?.values.value, '真实 CloakBrowser 五节点')
  const artifacts = await api(runtime, `/workflow-runs/${encodeURIComponent(runId)}/artifacts?cursor=0&limit=50`)
  assert.equal(artifacts.items.length, 1)
  assert.equal(artifacts.items[0].mimeType, 'image/png')
  const png = await apiBytes(runtime, `/workflow-runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifacts.items[0].artifactId)}`)
  assert.deepEqual([...png.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10])
  checkpoint('正式 UI 启动真实 CloakBrowser：输入、首个匹配点击、提取值、PNG 与终态均已持久化')

  await wait(800)
  const leaked = execFileSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).split('\n').filter(line => line.includes(userData) && /Chromium|CloakBrowser/.test(line))
  assert.deepEqual(leaked, [])
  checkpoint('运行终态后 CloakBrowser 进程树和临时会话均已清理')

  if (projectMode && process.env.AUTOFLOW_B1_ASSETS === '1') {
    const assetPage = await api(runtime, `/v1/projects/${projectId}/run-assets?runId=${runId}&limit=50`)
    const extracted = assetPage.items.find(item => item.kind === 'result' && item.nodeId === nodeIds[3])
    const screenshot = assetPage.items.find(item => item.kind === 'file' && item.mimeType === 'image/png')
    assert.ok(extracted && screenshot)
    await click(main, '数据', '[aria-label="项目功能"] button,[aria-label="项目功能"] [role="tab"]')
    await click(main, '自动化运行数据', 'summary')
    await click(main, `预览 ${extracted.assetId}`, 'button')
    await waitFor(main, "document.querySelector('[aria-label=运行数据详情]')?.innerText.includes('真实 CloakBrowser 五节点')", 'project result preview')
    await capture(main, join(evidenceDir, 'project-result-preview.png'))
    await click(main, `日志 ${extracted.assetId}`, 'button')
    await waitFor(main, `document.querySelector('[aria-label=运行数据详情]')?.innerText.includes(${JSON.stringify(extracted.executionId)}) && document.querySelector('[aria-label=运行数据详情] pre')?.textContent.includes('message')`, 'originating node execution logs')
    await click(main, `预览 ${screenshot.assetId}`, 'button')
    await waitFor(main, "(()=>{const image=document.querySelector('[aria-label=运行数据详情] img');return image?.complete&&image.naturalWidth>0})()", 'project PNG preview')
    await capture(main, join(evidenceDir, 'project-image-preview.png'))
    const downloads = join(userData, 'asset-downloads')
    await mkdir(downloads)
    // Isolate the native download destination; the download itself is a real UI click.
    await native.evaluate(`qaElectron.session.defaultSession.setDownloadPath(${JSON.stringify(downloads)});globalThis.qaDownloads=[];qaElectron.session.defaultSession.on('will-download',(_event,item)=>{const record={name:item.getFilename(),state:item.getState()};qaDownloads.push(record);item.on('done',(_event,state)=>{record.state=state;record.path=item.getSavePath()})});true`)
    await click(main, `下载 ${screenshot.assetId}`, 'button')
    execFileSync('osascript', ['-e', 'tell application "System Events"', '-e', `tell (first application process whose unix id is ${desktop.child.pid})`, '-e', 'repeat 50 times', '-e', 'if exists button "保存" of splitter group 1 of sheet 1 of window "AutoFlow" then exit repeat', '-e', 'delay 0.1', '-e', 'end repeat', '-e', 'click button "保存" of splitter group 1 of sheet 1 of window "AutoFlow"', '-e', 'end tell', '-e', 'end tell'])
    const downloaded = await waitForValue(async () => {
      const files = (await readdir(downloads)).filter(file => file.endsWith('.png'))
      return files.length ? readFile(join(downloads, files[0])).catch(() => null) : null
    }, 'native artifact download', 15000)
    assert.deepEqual(downloaded, png)
    checkpoint('项目数据页真实点击读取提取值、对应节点执行日志和 PNG 预览；下载文件与运行登记产物字节一致')
    await click(main, '自动化', '[aria-label="项目功能"] button,[aria-label="项目功能"] [role="tab"]')
  }

  const failedRunId = await verifyFailedPause({
    studio, runtime, saved, nodeId: nodeIds[2], priorRunIds: [runId], userData, evidenceDir, observedEvents,
  })

  await click(studio, '', `.react-flow__node[data-id=${JSON.stringify(nodeIds[0])}]`)
  await setInput(studio, '[placeholder="https://example.com"]', slowUrl)
  await click(studio, '运行 (F5)', '[aria-label="运行 (F5)"]')
  await click(studio, '运行 (F5)', '[role="menuitem"]')
  const stoppedRun = await waitForValue(async () => {
    const page = await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(saved.id)}&cursor=0&limit=20`)
    const candidate = page.items.find(item => item.runId !== runId && item.runId !== failedRunId)
    if (!candidate) return null
    const detail = await api(runtime, `/workflow-runs/${encodeURIComponent(candidate.runId)}`)
    return detail.status === 'running' ? detail : null
  }, 'second active run', 20_000)
  await closeWindowThroughOs(desktop.child.pid)
  await waitFor(studio, "document.body?.innerText.includes('结束活跃会话后离开？')", 'active-run normal-close prompt')
  await click(studio, '取消')
  assert.equal(await hasStudioTarget(desktop.debugOrigin), true)
  assert.equal((await api(runtime, `/workflow-runs/${encodeURIComponent(stoppedRun.runId)}`)).status, 'running')
  assert.equal((await api(runtime, `/workflows/${encodeURIComponent(saved.id)}`)).revision, 2)
  checkpoint('活跃运行与未保存草稿并存时取消正常关窗，浏览器运行、窗口、草稿和已保存文档均保持原状态')

  await closeWindowThroughOs(desktop.child.pid)
  await waitFor(studio, "document.body?.innerText.includes('结束活跃会话后离开？')", 'second active-run normal-close prompt')
  await click(studio, '放弃修改并结束会话')
  studio.close(); studio = undefined
  await waitForNoStudio(desktop.debugOrigin, 30_000)
  const stopped = await waitForValue(async () => {
    const value = await api(runtime, `/workflow-runs/${encodeURIComponent(stoppedRun.runId)}`)
    return value.status === 'stopped' ? value : null
  }, 'normal-close stopped run cleanup', 30_000)
  assert.equal(stopped.status, 'stopped')
  if (projectMode) {
    assert.equal(stopped.projectId, projectId)
    assert.equal((await api(runtime, `/workflow-runs/${encodeURIComponent(failedRunId)}`)).projectId, projectId)
    checkpoint('成功、失败调试及停止运行均持久化同一个项目归属')
  }
  assert.equal((await api(runtime, `/workflows/${encodeURIComponent(saved.id)}`)).revision, 2)
  await waitForValue(async () => {
    const processes = execFileSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).split('\n').filter(line => line.includes(userData) && /Chromium|CloakBrowser/.test(line))
    return processes.length === 0 ? true : null
  }, 'normal-close browser cleanup', 10_000)
  checkpoint('放弃草稿并结束活跃运行后，先确认 stopped 与清理完成，再关闭 Studio；保存修订未被草稿覆盖')

  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库')", 'final reopened Studio', 30_000)

  await click(studio, '打开')
  await click(studio, '打开工作流 B1 五节点正式闭环 · 关窗保存', '[role="button"]')
  await waitFor(studio, "document.querySelectorAll('.react-flow__node').length === 5", 'workflow before start failure')
  const beforeStartFailure = await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(saved.id)}&cursor=0&limit=20`)
  await rename(isolatedKernel, unavailableKernel)
  kernelMoved = true
  await click(studio, '运行 (F5)', '[aria-label="运行 (F5)"]')
  await click(studio, '运行 (F5)', '[role="menuitem"]')
  await waitFor(studio, "document.querySelector('[aria-label=\"运行 (F5)\"]') && !document.body?.innerText.includes('等待启动确认')", 'missing kernel request rejected', 10_000)
  const afterStartFailure = await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(saved.id)}&cursor=0&limit=20`)
  assert.deepEqual(afterStartFailure.items.map(item => item.runId).sort(), beforeStartFailure.items.map(item => item.runId).sort())
  assert.deepEqual(execFileSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).split('\n').filter(line => line.includes(userData) && /Chromium|CloakBrowser/.test(line)), [])
  await rename(unavailableKernel, isolatedKernel)
  kernelMoved = false
  checkpoint('从正式 UI 触发内核缺失启动失败：未创建运行、未启动浏览器且未遗留资源占用')

  const packageBoundary = desktop.packaged ? await verifyPackageBoundary() : null
  if (packageBoundary) checkpoint('目录包未携带冻结源码路径、Mock 服务或 Vite 开发地址')

  await capture(studio, join(evidenceDir, 'completed.png'))
  if (projectMode) {
    await click(studio, '执行日志')
    await click(studio, '', '[aria-label="运行日志记录"]')
    await waitFor(studio, "(()=>{const labels=[...document.querySelectorAll('[role=option]')].map(e=>e.textContent);return labels.length===3&&['completed','failed','stopped'].every(status=>labels.some(label=>label.includes(status)))})()", 'own project run history')
    await click(studio, 'completed', '[role="option"]')
    await waitFor(studio, "document.body.innerText.includes('执行完成')", 'completed run history logs')
    await closeWindowThroughOs(desktop.child.pid)
    studio.close(); studio = undefined
    await waitForNoStudio(desktop.debugOrigin, 30_000)
    await click(main, '项目', 'a, button')
    await click(main, '新建项目')
    await setInput(main, '#project-name', 'Studio 历史隔离验收')
    await click(main, '创建项目')
    await waitFor(main, "document.body?.innerText.includes('Studio 历史隔离验收')", 'second project created')
    if (!await main.evaluate('Boolean(document.querySelector(\'[aria-label="项目功能"]\'))')) await click(main, 'Studio 历史隔离验收', '[role="button"],button')
    await waitFor(main, 'Boolean(document.querySelector(\'[aria-label="项目功能"]\'))', 'second project page')
    const otherProjectId = (await main.evaluate('location.hash')).match(/projects\/([^/]+)/)?.[1]
    assert.ok(otherProjectId && otherProjectId !== projectId)
    await click(main, '自动化', '[aria-label="项目功能"] button,[aria-label="项目功能"] [role="tab"]')
    studio = await openStudioFromMain(main, desktop.debugOrigin)
    await studio.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
    await waitFor(studio, "document.body?.innerText.includes('模块库')", 'second project Studio')
    await click(studio, '执行日志')
    await waitFor(studio, "document.querySelector('[aria-label=\"运行日志记录\"]')?.textContent.includes('暂无运行记录')", 'second project empty run history')
    await click(studio, '', '[aria-label="运行日志记录"]')
    await wait(1000)
    assert.deepEqual(await studio.evaluate("[...document.querySelectorAll('[role=option]')].map(e=>e.textContent)"), ['暂无运行记录'])
    await press(studio, 'Escape', { code: 'Escape', keyCode: 27 })
    assert.equal(await studio.evaluate("document.body.innerText.includes('B1 五节点正式闭环')"), false)
    assert.equal((await api(runtime, `/workflow-runs?projectId=${otherProjectId}`)).total, 0)
    assert.equal((await api(runtime, `/workflow-runs?projectId=${projectId}`)).total, 3)
    await capture(studio, join(evidenceDir, 'other-project-empty-history.png'))
    checkpoint('正式 UI 的原项目可查三次运行；进入第二项目后历史列表与回放日志均不泄露原项目运行，原记录仍持久化')
  }
  const buildArtifacts = desktop.packaged ? await packagedBuildHashes() : null
  const report = {
    evidenceId: 'BE-B1-formal-electron', checkedAt: new Date().toISOString(),
    gitHead: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    buildGitHead: process.env.AUTOFLOW_B1_BUILD_GIT_HEAD ?? null,
    sourceTreeSha256: process.env.AUTOFLOW_B1_SOURCE_TREE_SHA256 ?? null,
    buildSha256: buildArtifacts?.appAsarSha256 ?? await buildHash(), buildArtifacts,
    projectId, workflowId: saved.id, profileId: profile.id, runId, failedRunId, stoppedRunId: stoppedRun.runId,
    result: 'passed', checks, platform: `${process.platform}-${process.arch}`,
    entry: desktop.packaged ? 'packaged-directory' : 'development-build', packageBoundary,
    boundaries: { workspace: 'ephemeral', userDatabaseTouched: false, browser: 'CloakBrowser only', interaction: `CDP mouse and keyboard plus macOS ${projectMode ? 'native window close button' : 'system-level Command-W close shortcut'}; no Store access` },
  }
  await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
  }
} catch (error) {
  if (main) { await capture(main, join(evidenceDir, 'main-failure.png')).catch(() => undefined); await writeFile(join(evidenceDir, 'main-failure.txt'), String(await main.evaluate('document.body.innerText').catch(() => 'unavailable'))).catch(() => undefined) }
  if (studio) await capture(studio, join(evidenceDir, 'failure.png')).catch(() => undefined)
  await writeFile(join(evidenceDir, 'failure.json'), JSON.stringify({ checkedAt: new Date().toISOString(), checks, observedEvents, error: error instanceof Error ? error.stack : String(error) }, null, 2) + '\n')
  throw error
} finally {
  eventAbort?.abort(); studio?.close(); main?.close(); native?.close(); await stop(desktop?.child)
  if (kernelMoved) await rename(unavailableKernel, isolatedKernel).catch(() => undefined)
  slowServer.closeAllConnections()
  await new Promise(resolve => slowServer.close(resolve))
  await rm(userData, { recursive: true, force: true })
}

function checkpoint(message) { checks.push(message); console.log(message) }

async function verifyRunToTarget({ studio, runtime, saved, nodeIds, userData, evidenceDir, observedEvents }) {
  const targetId = nodeIds[2]
  const nodePoint = await point(studio, `.react-flow__node[data-id=${JSON.stringify(targetId)}]`)
  await studio.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...nodePoint })
  await wait(150)
  const button = await waitFor(studio, `(()=>{const e=document.querySelector('.react-flow__node[data-id=${JSON.stringify(targetId)}] button[data-tip="运行至此节点（保留前置上下文）"]');if(!e)return null;const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, 'run-to-target button')
  await studio.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...button })
  await studio.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...button, button: 'left', clickCount: 1 })
  await studio.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...button, button: 'left', clickCount: 1 })
  const started = await waitForValue(async () => {
    const page = await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(saved.id)}&cursor=0&limit=20`)
    return page.items[0] ?? null
  }, 'run-to-target run', 20_000)
  const paused = await waitForValue(async () => {
    const value = await api(runtime, `/workflow-runs/${encodeURIComponent(started.runId)}`)
    return value.status === 'paused' ? value : null
  }, 'run-to-target pause', 30_000)
  assert.equal(paused.profileSnapshot.runOptions.runToNodeId, targetId)
  await waitFor(studio, "document.body?.innerText.includes('运行至此暂停') && document.body.innerText.includes('已到达调试目标')", 'rendered target pause', 10_000)
  const beforeTarget = observedEvents.filter(event => event.data?.runId === started.runId)
  assert.deepEqual(beforeTarget.filter(event => event.name === 'execution:node_start').map(event => event.data.nodeId), nodeIds.slice(0, 2))
  assert.equal(beforeTarget.some(event => event.name === 'execution:node_start' && event.data.nodeId === targetId), false)
  checkpoint('通过节点悬停入口真实执行前置网页动作，并在目标节点首次调度前暂停')
  await capture(studio, join(evidenceDir, 'run-to-target-paused.png'))
  await click(studio, '继续')
  const terminal = await waitForValue(async () => {
    const value = await api(runtime, `/workflow-runs/${encodeURIComponent(started.runId)}`)
    return value.status === 'completed' ? value : null
  }, 'run-to-target completion', 120_000)
  assert.equal(terminal.status, 'completed')
  const targetPauses = observedEvents.filter(event => event.name === 'execution:paused' && event.data?.runId === started.runId && event.data?.reason === 'target')
  assert.equal(targetPauses.length, 1)
  const allLogs = await api(runtime, `/workflow-runs/${encodeURIComponent(started.runId)}/logs?cursor=0&limit=500`)
  const targetLog = allLogs.items.find(item => item.nodeId === targetId && item.executionId)
  assert.ok(targetLog?.executionId)
  const filteredLogs = await api(runtime, `/workflow-runs/${encodeURIComponent(started.runId)}/logs?cursor=0&limit=500&executionId=${encodeURIComponent(targetLog.executionId)}`)
  assert.ok(filteredLogs.total > 0)
  assert.equal(filteredLogs.items.every(item => item.executionId === targetLog.executionId), true)
  await setInput(studio, '[aria-label="按执行标识筛选日志"]', targetLog.executionId)
  await waitFor(studio, `(()=>{const value=document.querySelector('[aria-label="按执行标识筛选日志"]')?.value;return value===${JSON.stringify(targetLog.executionId)}&&document.body.innerText.includes(${JSON.stringify(`${filteredLogs.total}/${filteredLogs.total}`)})})()`, 'execution identity log filter')
  checkpoint('正式日志面板按 executionId 查询完整持久化记录，并与服务端筛选结果一致')
  await capture(studio, join(evidenceDir, 'execution-log-filter.png'))
  await waitForValue(async () => {
    const processes = execFileSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).split('\n').filter(line => line.includes(userData) && /Chromium|CloakBrowser/.test(line))
    return processes.length === 0 ? true : null
  }, 'run-to-target browser cleanup', 10_000)
  checkpoint('继续后目标只暂停一次，剩余节点完成，CloakBrowser 与 worker 完成清理')
  return started.runId
}

async function verifyFailedPause({ studio, runtime, saved, nodeId, priorRunIds, userData, evidenceDir, observedEvents }) {
  await click(studio, '', `.react-flow__node[data-id=${JSON.stringify(nodeId)}]`)
  await setInput(studio, '[placeholder="例如: #button, .submit"]', '[')
  const nodePoint = await point(studio, `.react-flow__node[data-id=${JSON.stringify(nodeId)}]`)
  await studio.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...nodePoint })
  await wait(150)
  const breakpointPoint = await waitFor(studio, `(()=>{const e=document.querySelector('.react-flow__node[data-id=${JSON.stringify(nodeId)}] button[data-tip="设置断点（运行到此暂停）"]');if(!e)return null;const r=e.getBoundingClientRect();return{x:r.right-2,y:r.y+r.height/2}})()`, 'breakpoint button edge')
  await studio.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...breakpointPoint })
  await studio.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...breakpointPoint, button: 'left', clickCount: 1 })
  await studio.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...breakpointPoint, button: 'left', clickCount: 1 })
  await wait(100)
  await waitFor(studio, `Boolean(document.querySelector('.react-flow__node[data-id=${JSON.stringify(nodeId)}] button[data-tip="移除断点"]'))`, 'breakpoint activation')
  await click(studio, '运行 (F5)', '[aria-label="运行 (F5)"]')
  await click(studio, '运行 (F5)', '[role="menuitem"]')
  const failedRun = await waitForValue(async () => {
    const page = await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(saved.id)}&cursor=0&limit=20`)
    return page.items.find(item => !priorRunIds.includes(item.runId)) ?? null
  }, 'invalid-selector debug run', 20_000)
  await waitFor(studio, "document.body?.innerText.includes('断点暂停')", 'debug breakpoint before invalid selector', 30_000)
  await click(studio, '继续')
  const failedPaused = await waitForValue(async () => {
    const value = await api(runtime, `/workflow-runs/${encodeURIComponent(failedRun.runId)}`)
    return value.status === 'failed_paused' ? value : null
  }, 'invalid-selector failed pause', 30_000)
  assert.equal(failedPaused.error.nodeId, nodeId)
  await waitFor(studio, "document.body?.innerText.includes('失败暂停') && document.body.innerText.includes('失败现场只读')", 'rendered failed debug inspection', 10_000)
  assert.ok(execFileSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).split('\n').some(line => line.includes(userData) && /Chromium|CloakBrowser/.test(line)))
  checkpoint('真实 Debug 在无效选择器失败后保留可见 CloakBrowser、变量和失败节点，继续与单步入口不可用')
  await capture(studio, join(evidenceDir, 'failed-paused.png'))
  await click(studio, '结束调试')
  const failedTerminal = await waitForValue(async () => {
    const value = await api(runtime, `/workflow-runs/${encodeURIComponent(failedRun.runId)}`)
    return value.status === 'failed' ? value : null
  }, 'invalid-selector failed terminal after debug cleanup', 30_000)
  assert.equal(failedTerminal.error.nodeId, nodeId)
  await waitForValue(async () => observedEvents.find(event => event.name === 'execution:completed' && event.data?.runId === failedRun.runId && event.data?.result?.status === 'failed') ?? null, 'raw SSE failed terminal event', 10_000)
  await waitForValue(async () => {
    const processes = execFileSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).split('\n').filter(line => line.includes(userData) && /Chromium|CloakBrowser/.test(line))
    return processes.length === 0 ? true : null
  }, 'failed debug browser cleanup', 10_000)
  await setInput(studio, '[placeholder="例如: #button, .submit"]', '.workflow-action')
  checkpoint('结束失败调试后保持 failed 终态和原失败节点；浏览器、worker 与运行占用完成清理')
  return failedRun.runId
}

async function api(runtime, path, options = {}) {
  const response = await fetch(`${runtime.sidecar.baseUrl}/api${path}`, {
    method: options.method ?? 'GET',
    headers: { 'x-autoflow-token': runtime.sidecar.token, 'content-type': 'application/json', 'Idempotency-Key': randomUUID() },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })
  if (!response.ok) throw new Error(`${options.method ?? 'GET'} /api${path}: ${response.status} ${await response.text()}`)
  return response.status === 204 ? undefined : response.json()
}

async function apiBytes(runtime, path) {
  const response = await fetch(`${runtime.sidecar.baseUrl}/api${path}`, { headers: { 'x-autoflow-token': runtime.sidecar.token } })
  assert.ok(response.ok, `GET /api${path}: ${response.status}`)
  return Buffer.from(await response.arrayBuffer())
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

async function connectStudio(origin) {
  const target = await waitForTarget(origin, item => item.type === 'page' && item.url.includes('studio.html'), 'Studio target')
  return connectCdp(target.webSocketDebuggerUrl)
}

async function openStudioFromMain(cdp, origin) {
  for (let attempt = 0; attempt < 3; attempt++) {
    await click(cdp, '工作流工作台')
    try { return await connectStudio(origin) } catch { /* dashboard can rerender after its resource refresh */ }
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

async function hasStudioTarget(origin) {
  const targets = await (await fetch(`${origin}/json/list`)).json()
  return targets.some(target => target.type === 'page' && target.url.includes('studio.html'))
}

async function closeWindowThroughOs(pid) {
  assert.equal(process.platform, 'darwin', '原生窗口关闭验收目前只在 macOS 实机执行；其他平台必须单独记录')
  assert.equal(await native.evaluate("(()=>{const w=qaElectron.BrowserWindow.getAllWindows().find(w=>w.getTitle().includes('工作流工作台'));if(!w)return false;qaElectron.app.focus({steal:true});w.show();w.focus();return true})()"), true)
  await wait(250)
  if (projectMode) {
    execFileSync('osascript', ['-e', 'tell application "System Events"', '-e', `tell (first application process whose unix id is ${pid})`, '-e', 'click (first button of (first window whose name contains "工作流工作台") whose subrole is "AXCloseButton")', '-e', 'end tell', '-e', 'end tell'])
    return
  }
  execFileSync('osascript', [
    '-e', 'tell application "System Events"',
    '-e', `set targetProcess to first application process whose unix id is ${pid}`,
    '-e', 'set frontmost of targetProcess to true',
    '-e', 'keystroke "w" using command down',
    '-e', 'end tell',
  ])
  await wait(150)
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
  return waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length),text=${JSON.stringify(text)};const e=!text?rows[0]:rows.find(e=>e.getAttribute('aria-label')===text)||rows.find(e=>e.textContent.trim()===text)||rows.find(e=>e.textContent.includes(text));if(!e||e.disabled)return null;e.scrollIntoView({block:'nearest',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `unobscured ${text || selector}`)
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
    await cdp.command('Input.dispatchMouseEvent', {
      type: 'mouseMoved', x: points.a.x + (points.b.x - points.a.x) * step / 12,
      y: points.a.y + (points.b.y - points.a.y) * step / 12, button: 'left', buttons: 1,
    })
    await wait(12)
  }
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...points.b, button: 'left', buttons: 0, clickCount: 1 })
  await wait(120)
}

async function arrangeNodes(cdp, nodeIds) {
  // Use the real zoom controls before arranging: fit animations and oversized
  // overlapping cards can otherwise make a drag hit a different node's handle.
  await wait(500)
  for (let index = 0; index < 10; index++) {
    if (await cdp.evaluate("Math.max(...[...document.querySelectorAll('.react-flow__node')].map(e=>e.getBoundingClientRect().height)) < 65")) break
    await click(cdp, '', '.react-flow__controls-zoomout')
    await wait(250)
  }
  assert.ok(await cdp.evaluate("Math.max(...[...document.querySelectorAll('.react-flow__node')].map(e=>e.getBoundingClientRect().height)) < 65"), 'real zoom control makes cards small enough to avoid overlapping handles')
  const pane = await cdp.evaluate(`(()=>{const r=document.querySelector('.react-flow__pane').getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height}})()`)
  const targets = nodeIds.map((_, index) => ({ x: pane.x + pane.width * .46, y: pane.y + 65 + index * ((pane.height - 130) / 4) }))
  for (let index = nodeIds.length - 1; index >= 0; index--) {
    const from = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__node[data-id=${JSON.stringify(nodeIds[index])}]');if(!e)return null;const r=e.getBoundingClientRect();for(const yf of [.5,.3,.7])for(const xf of [.5,.2,.8]){const x=r.x+r.width*xf,y=r.y+r.height*yf;const hit=document.elementFromPoint(x,y);if(hit?.closest('.react-flow__node')===e&&!hit.closest('.react-flow__handle'))return{x,y,dx:x-r.x-r.width/2,dy:y-r.y-r.height/2}}return null})()`, `unobscured node position ${nodeIds[index]}`)
    const to = targets[index]
    to.x += from.dx; to.y += from.dy
    await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...from })
    await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...from, button: 'left', buttons: 1, clickCount: 1 })
    for (let step = 1; step <= 10; step++) await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', x: from.x + (to.x - from.x) * step / 10, y: from.y + (to.y - from.y) * step / 10, button: 'left', buttons: 1 })
    await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...to, button: 'left', buttons: 0, clickCount: 1 })
    await wait(100)
  }
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

async function packagedBuildHashes() {
  const executableIndex = process.argv.indexOf('--executable')
  assert.notEqual(executableIndex, -1)
  const resources = resolve(dirname(resolve(process.argv[executableIndex + 1])), '../Resources')
  return {
    appAsarSha256: await fileHash(join(resources, 'app.asar')),
    backendExecutableSha256: await fileHash(join(resources, 'backend', 'autoflow-backend')),
  }
}

async function fileHash(path) {
  return createHash('sha256').update(await readFile(path)).digest('hex')
}

async function verifyPackageBoundary() {
  const executableIndex = process.argv.indexOf('--executable')
  assert.notEqual(executableIndex, -1)
  const executable = resolve(process.argv[executableIndex + 1])
  const resources = resolve(dirname(executable), '../Resources')
  const extractDir = await mkdtemp(join(tmpdir(), 'autoflow-b1-asar-'))
  const needles = ['reference/WebRPA', '127.0.0.1:5175', 'StudioMockTools', 'api/mock-server']
  try {
    execFileSync(join(root, 'node_modules/.bin/asar'), ['extract', join(resources, 'app.asar'), extractDir])
    const hits = []
    for (const base of [extractDir, join(resources, 'backend')]) {
      for (const file of await readdir(base, { recursive: true })) {
        const path = join(base, file)
        let data
        try { data = await readFile(path) } catch { continue }
        for (const needle of needles) if (data.includes(Buffer.from(needle))) hits.push({ file: path.slice(base.length + 1), needle })
      }
    }
    assert.deepEqual(hits, [])
    return { resources, forbiddenReferences: hits, scannedNeedles: needles }
  } finally {
    await rm(extractDir, { recursive: true, force: true })
  }
}
