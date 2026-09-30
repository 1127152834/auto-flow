import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import { mkdir, mkdtemp, readFile, readdir, rm, stat, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename, join, resolve } from 'node:path'

import { connectCdp, launchElectron, wait, waitFor } from './electron-cdp.mjs'
import { stop } from './smoke-sidecar.mjs'

const root = resolve(import.meta.dirname, '..')
const gitHead = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim()
const sourceKernel = process.env.AUTOFLOW_B1_KERNEL_DIR
  ?? '/Users/zhangtiancheng/Library/Application Support/@autoflow/desktop/data/kernels/chromium-145.0.7632.109.2'
const kernelVersion = basename(sourceKernel).replace(/^chromium-/, '')
const evidenceRoot = join(root, 'docs/migration/studio-backend-migration/evidence/b4')
await mkdir(evidenceRoot, { recursive: true })
const evidenceDir = await mkdtemp(join(evidenceRoot, 'formal-table-electron-'))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-b4-table-'))
const workflowName = 'B4 表格七类型正式闭环'
const checks = []
const observedEvents = []
const approvedTypes = [
  'table_add_row', 'table_add_column', 'table_set_cell', 'table_get_cell',
  'table_export', 'table_delete_row', 'table_clear',
]
const modules = [
  {
    label: '添加行', type: 'table_add_row',
    expected: { rowData: '{"name":"甲","score":1}' },
    expectedResult: { row: { name: '甲', score: 1 }, total_rows: 1 },
    configure: cdp => setInput(cdp, 'textarea[placeholder*="列名1"]', '{"name":"甲","score":1}'),
  },
  {
    label: '添加行', type: 'table_add_row',
    expected: { rowData: '{"name":"乙","score":2}' },
    expectedResult: { row: { name: '乙', score: 2 }, total_rows: 2 },
    configure: cdp => setInput(cdp, 'textarea[placeholder*="列名1"]', '{"name":"乙","score":2}'),
  },
  {
    label: '添加列', type: 'table_add_column',
    expected: { columnName: 'status', defaultValue: '初始' },
    expectedResult: { column: 'status', default: '初始' },
    configure: async cdp => {
      await setInput(cdp, '[placeholder="新列的名称，支持 {变量名}"]', 'status')
      await setInput(cdp, '[placeholder="新列的默认值，支持 {变量名}"]', '初始')
    },
  },
  {
    label: '设置单元格', type: 'table_set_cell',
    expected: { rowIndex: '1', columnName: 'score', cellValue: '9' },
    expectedResult: { row: 1, column: 'score', value: '9' },
    configure: async cdp => {
      await setInput(cdp, '[placeholder="从0开始，支持负数和 {变量名}"]', '1')
      await setInput(cdp, '[placeholder="要设置的列名，支持 {变量名}"]', 'score')
      await setInput(cdp, '[placeholder="要设置的值，支持 {变量名}"]', '9')
    },
  },
  {
    label: '读取单元格', type: 'table_get_cell',
    expected: { rowIndex: '1', columnName: 'score', variableName: 'score_value_ui' },
    expectedResult: { value: '9' },
    configure: async cdp => {
      await setInput(cdp, '[placeholder="从0开始，支持负数和 {变量名}"]', '1')
      await setInput(cdp, '[placeholder="要获取的列名，支持 {变量名}"]', 'score')
      await setInput(cdp, '[placeholder="变量名"]', 'score_value_ui')
    },
  },
  {
    label: '导出表格', type: 'table_export',
    expected: { exportFormat: 'excel', sheetName: '正式结果', savePath: 'reports', fileNamePattern: 'table_ui_export', variableName: 'xlsx_path_ui' },
    configure: async cdp => {
      await selectNative(cdp, '#exportFormat', 'CSV (.csv)')
      await selectNative(cdp, '#exportFormat', 'Excel (.xlsx)')
      await setInput(cdp, '[placeholder="数据，支持 {变量名}"]', '正式结果')
      await setInput(cdp, 'input[placeholder^="C:"]', 'reports')
      await setInput(cdp, '[placeholder="data_{时间戳}，支持 {变量名}"]', 'table_ui_export')
      await setInput(cdp, '[placeholder="变量名"]', 'xlsx_path_ui')
    },
  },
  {
    label: '删除行', type: 'table_delete_row',
    expected: { rowIndex: '-1' },
    expectedResult: { deleted: { name: '乙', score: '9', status: '初始' }, remaining: 1 },
    configure: cdp => setInput(cdp, '[placeholder="从0开始，支持负数和 {变量名}"]', '-1'),
  },
  {
    label: '清空表格', type: 'table_clear', expected: {},
    expectedResult: { cleared_rows: 1 }, configure: async () => {},
  },
]
const executedTypes = [...new Set(modules.map(module => module.type))]
const expectedWorkflowVariables = [{ name: 'cell_value', type: 'string', scope: 'global' }]
const targetFiles = [
  'apps/backend/src/autoflow/application/workflows/executors/production.py',
  'apps/backend/src/autoflow/application/workflows/executors/table.py',
  'apps/backend/src/autoflow/domain/workflows/execution.py',
  'apps/backend/src/autoflow/infrastructure/filesystem/workflow_artifacts.py',
  'apps/backend/src/autoflow/infrastructure/filesystem/workflow_table_workbook.py',
  'apps/backend/src/autoflow/infrastructure/process/workflow_worker.py',
  'apps/backend/src/autoflow/providers/browser/workflow_worker.py',
]
const frozenFiles = ['reference/WebRPA/backend/app/executors/table.py']
const targetedTestCommand = [
  'uv', 'run', '--project', 'apps/backend', 'pytest', '-q',
  'apps/backend/tests/differential/workflows/test_b4_table_executor_parity.py',
  'apps/backend/tests/unit/workflows/test_browser_session_contract.py::test_workflow_worker_runs_table_family_and_registers_excel_artifact',
]
let desktop
let main
let studio
let native
let eventAbort
const cloakProcessesObservedDuringRun = new Set()

try {
  assert.equal(process.platform, 'darwin', 'formal evidence requires macOS')
  assert.equal(process.arch, 'arm64', 'formal evidence requires native arm64 Node/Electron')
  assert.match(gitHead, /^[0-9a-f]{40}$/)
  const targetedTestOutput = execFileSync(targetedTestCommand[0], targetedTestCommand.slice(1), { cwd: root, encoding: 'utf8' }).trim()
  const targetedTestPasses = targetedTestOutput.match(/(\d+) passed/)
  assert.ok(targetedTestPasses)
  checkpoint(`表格差异、真实 OpenPyXL 与 worker 产物测试：${targetedTestPasses[1]} passed`)

  await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
  await mkdir(join(userData, 'data', 'kernels'), { recursive: true })
  execFileSync('cp', ['-cR', sourceKernel, join(userData, 'data', 'kernels', basename(sourceKernel))])
  const browserRequirement = productionBrowserRequirement(approvedTypes)
  assert.equal(browserRequirement.workflowRequiresBrowser, false)
  assert.deepEqual(Object.values(browserRequirement.nodeRequiresBrowser), Array(approvedTypes.length).fill(false))
  checkpoint('生产执行器注册表对表格 7 类型计算 requiresBrowser=false')

  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`, '--inspect=0'] })
  assert.equal(desktop.packaged, false, 'formal B4 evidence must use the development Electron entry')
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
      name: 'B4 表格纯数据验收配置', description: '临时工作区；纯数据工作流不得启动浏览器', startUrl: 'about:blank',
      locale: 'zh-CN', timezone: 'Asia/Shanghai', geoip: false, headless: true, humanize: false,
      humanPreset: 'default', userAgent: null, viewportJson: null, colorScheme: 'light', extensionPathsJson: [], expertArgsJson: [],
      browserVersion: kernelVersion, browserEdition: 'public', releaseChannel: 'stable', proxyMode: 'none', proxyId: null, proxyPoolId: null,
    },
  })
  assert.deepEqual(await installedKernels(), [basename(sourceKernel)])
  const cloakBefore = cloakProcesses(userData)
  assert.deepEqual(cloakBefore, [])
  checkpoint('真实 sidecar 在临时工作区创建 Profile；运行前无 CloakBrowser 进程')

  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库')", 'formal Studio', 30_000)
  assert.equal(await studio.evaluate("document.body.innerText.includes('Mock 接口')"), false)
  await waitFor(studio, `document.querySelector('[aria-label="运行浏览器配置"]')?.value === ${JSON.stringify(profile.id)}`, 'managed Profile selection')
  checkpoint('主窗口通过真实点击打开正式 Studio；未直接访问 Store 或页面内部函数')

  await click(studio, '新建')
  await waitFor(studio, "document.querySelectorAll('.react-flow__node').length === 0", 'new empty workflow')
  await setInput(studio, 'input[placeholder="工作流名称"]', workflowName)

  const nodeIds = []
  for (let index = 0; index < modules.length; index++) {
    const module = modules[index]
    console.log(`UI 节点 ${index + 1}/${modules.length}: ${module.type}`)
    await addFromQuickPicker(studio, index, module.label)
    const nodeId = await waitFor(studio, `(()=>{const rows=[...document.querySelectorAll('.react-flow__node')].filter(e=>e.textContent.includes(${JSON.stringify(module.label)}));return rows.at(-1)?.dataset.id||null})()`, `node ${module.type}`)
    nodeIds.push(nodeId)
    await selectNode(studio, nodeId, module.type)
    await module.configure(studio)
    if (index === 0) await placeFirstNode(studio, nodeId)
  }
  assert.equal(new Set(nodeIds).size, modules.length)
  assert.equal(await studio.evaluate("document.querySelectorAll('.react-flow__node').length"), modules.length)
  checkpoint('通过画布原生右键菜单和配置面板添加、输入并配置 8 个节点实例，覆盖表格全部 7 类型')

  for (let index = 0; index < nodeIds.length - 1; index++) {
    await connectNodes(studio, nodeIds[index], nodeIds[index + 1])
    await waitFor(studio, `document.querySelectorAll('.react-flow__edge').length === ${index + 1}`, `workflow edge ${index + 1}`)
  }
  checkpoint('通过画布拖拽节点与连接手柄建立 add_row ×2 → add_column → set_cell → get_cell → export → delete_row → clear 共享表状态链')

  await click(studio, '执行日志')
  await click(studio, '保存')
  await waitFor(studio, `document.body?.innerText.includes(${JSON.stringify(`工作流已保存: ${workflowName}`)})`, 'workflow save acknowledgement')
  const savedList = await api(runtime, '/workflows')
  const saved = savedList.find(item => item.name === workflowName)
  assert.ok(saved)
  assert.equal(saved.revision, 1)
  assert.deepEqual(saved.variables, expectedWorkflowVariables)
  assert.deepEqual(saved.nodes.map(node => node.data.moduleType), modules.map(module => module.type))
  assert.equal(saved.edges.length, modules.length - 1)
  for (let index = 0; index < modules.length; index++) {
    const data = saved.nodes.find(node => node.id === nodeIds[index])?.data
    assert.ok(data)
    for (const [key, value] of Object.entries(modules[index].expected)) assert.deepEqual(data[key], value, `${modules[index].type}.${key}`)
  }
  checkpoint('真实 UI 保存经正式 HTTP 写入 SQLite；8 个节点实例配置和 7 条边均与输入一致')

  await closeWindowThroughOs(desktop.child.pid)
  studio.close(); studio = undefined
  await waitForNoStudio(desktop.debugOrigin)
  assert.equal((await api(runtime, `/workflows/${encodeURIComponent(saved.id)}`)).revision, 1)
  studio = await openStudioFromMain(main, desktop.debugOrigin)
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库')", 'reopened Studio', 30_000)
  if (!await studio.evaluate(`document.querySelectorAll('.react-flow__node').length === ${modules.length} && document.querySelector('input[placeholder="工作流名称"]')?.value === ${JSON.stringify(workflowName)}`)) {
    await click(studio, '打开')
    await click(studio, `打开工作流 ${workflowName}`, '[role="button"]')
  }
  await waitFor(studio, `document.querySelector('input[placeholder="工作流名称"]')?.value === ${JSON.stringify(workflowName)} && document.querySelectorAll('.react-flow__node').length === ${modules.length}`, 'persisted workflow reopen')
  assert.equal(await studio.evaluate("document.querySelectorAll('.react-flow__edge').length"), modules.length - 1)
  checkpoint('通过 macOS Cmd+W 正常关闭 Studio，再从主窗口真实点击重开并恢复已保存节点、配置和连线')

  observeCloakProcesses(userData, cloakProcessesObservedDuringRun)
  await click(studio, '运行 (F5)', '[aria-label="运行 (F5)"]')
  observeCloakProcesses(userData, cloakProcessesObservedDuringRun)
  await click(studio, '运行 (F5)', '[role="menuitem"]')
  observeCloakProcesses(userData, cloakProcessesObservedDuringRun)
  const startedRun = await waitForValue(async () => {
    const page = await api(runtime, `/workflow-runs?documentId=${encodeURIComponent(saved.id)}&cursor=0&limit=20`)
    observeCloakProcesses(userData, cloakProcessesObservedDuringRun)
    return page.items[0] ?? null
  }, 'persisted workflow run', 20_000)
  const terminalRun = await waitForValue(async () => {
    const value = await api(runtime, `/workflow-runs/${encodeURIComponent(startedRun.runId)}`)
    observeCloakProcesses(userData, cloakProcessesObservedDuringRun)
    return ['completed', 'failed', 'stopped', 'interrupted'].includes(value.status) ? value : null
  }, 'workflow terminal persistence', 60_000)
  assert.equal(terminalRun.status, 'completed')
  await waitForValue(async () => observedEvents.find(event => event.name === 'execution:completed' && event.data?.runId === startedRun.runId) ?? null, 'raw SSE terminal event', 10_000)
  await waitFor(studio, "document.body?.innerText.includes('执行完成')", 'rendered SSE terminal event', 10_000)
  for (const nodeId of nodeIds) {
    assert.ok(observedEvents.some(event => event.name === 'execution:node_complete' && event.data?.nodeId === nodeId && event.data?.success === true), `missing successful SSE completion for ${nodeId}`)
  }

  const runId = startedRun.runId
  const results = await api(runtime, `/workflow-runs/${encodeURIComponent(runId)}/results?cursor=0&limit=50`)
  assert.equal(results.items.length, modules.length)
  const valuesByNode = Object.fromEntries(nodeIds.map(nodeId => [nodeId, results.items.find(item => item.nodeId === nodeId)?.values]))
  for (let index = 0; index < modules.length; index++) {
    if (modules[index].expectedResult) assert.deepEqual(valuesByNode[nodeIds[index]], modules[index].expectedResult, `${modules[index].type} result`)
  }
  const exportNodeId = nodeIds[5]
  const exportResult = valuesByNode[exportNodeId]
  assert.equal(exportResult.rows, 2)
  assert.equal(exportResult.format, 'excel')
  assert.equal(exportResult.sheet_name, '正式结果')
  assert.match(exportResult.path, new RegExp(`/runs/${runId}/outputs/reports/table_ui_export\\.xlsx$`))
  assert.ok(exportResult.file_size > 0)

  const logs = await api(runtime, `/workflow-runs/${encodeURIComponent(runId)}/logs?cursor=0&limit=200`)
  for (const nodeId of nodeIds) assert.ok(logs.items.some(item => item.nodeId === nodeId), `missing persisted log for ${nodeId}`)
  const staticMessages = [
    '已添加数据行，当前共 1 行', '已添加数据行，当前共 2 行', "已添加列 'status'",
    '已设置 [1][score] = 9', '获取 [1][score] = 9', '已删除第 1 行，剩余 1 行', '已清空数据表格 (原有 1 行)',
  ]
  for (const message of staticMessages) assert.ok(logs.items.some(item => item.message === message), `missing HTTP log: ${message}`)
  const exportLog = logs.items.find(item => item.nodeId === exportNodeId)?.message
  assert.equal(exportLog, `已导出 2 行数据到: ${exportResult.path} (Sheet: 正式结果)`)
  checkpoint('HTTP 精确核对添加、改列、改单元格、读取、导出、删除和清空的 8 个结果与日志')

  const artifacts = await api(runtime, `/workflow-runs/${encodeURIComponent(runId)}/artifacts?cursor=0&limit=50`)
  assert.equal(artifacts.items.length, 1)
  const artifact = artifacts.items[0]
  assert.equal(artifact.nodeId, exportNodeId)
  assert.equal(artifact.mimeType, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
  assert.equal(artifact.purpose, 'result')
  assert.equal(artifact.size, exportResult.file_size)
  assert.match(artifact.sha256, /^[0-9a-f]{64}$/)
  const xlsx = await apiBytes(runtime, `/workflow-runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifact.artifactId)}`)
  assert.equal(xlsx.subarray(0, 2).toString(), 'PK')
  assert.equal(xlsx.length, artifact.size)
  assert.equal(createHash('sha256').update(xlsx).digest('hex'), artifact.sha256)
  const xlsxPath = join(evidenceDir, 'table-ui-export.xlsx')
  await writeFile(xlsxPath, xlsx)
  const workbook = inspectWorkbook(xlsxPath)
  assert.deepEqual(workbook.sheetNames, ['正式结果'])
  assert.deepEqual(workbook.values, [['name', 'score', 'status'], ['甲', 1, '初始'], ['乙', '9', '初始']])
  assert.equal(workbook.freezePanes, 'A2')
  assert.deepEqual(workbook.header, { bold: true, fontColor: '00FFFFFF', fill: '004472C4', alignment: 'center', borderStyle: 'thin', borderColor: '002F5496' })
  assert.deepEqual(workbook.dataStyle, { firstFillType: null, alternatingFill: '00F2F2F2', firstBorderStyle: 'thin', secondBorderStyle: 'thin' })
  assert.deepEqual(workbook.columnWidths, { A: 8, B: 9, C: 10 })
  assert.equal(workbook.headerHeight, 25)
  await writeFile(join(evidenceDir, 'workbook.json'), JSON.stringify(workbook, null, 2) + '\n')
  const exportSse = observedEvents.find(event => event.name === 'execution:node_complete' && event.data?.nodeId === exportNodeId)
  assert.equal(exportSse?.data?.executionId, artifact.executionId)
  checkpoint('HTTP 下载的 XLSX 可由 OpenPyXL 重开；Sheet、值、冻结窗格、表头/隔行/边框样式、列宽和哈希有效，且产物 executionId 与 SSE 导出节点完成事件一致')

  const sqlite = sqliteEvidence(userData, saved.id, runId)
  assert.deepEqual(sqlite.document, [{ id: saved.id, name: workflowName, revision: 1, nodeCount: 8, edgeCount: 7, variableCount: 1 }])
  assert.deepEqual(sqlite.run.map(({ eventCount, ...row }) => row), [{ runId, workflowId: saved.id, status: 'completed', cleanupState: 'completed', activeSlot: null, logCount: terminalRun.logCount }])
  assert.equal(sqlite.eventTypes.reduce((sum, row) => sum + row.count, 0), sqlite.run[0].eventCount)
  assert.deepEqual(sqlite.results.map(row => ({ nodeId: row.nodeId, value: row.value })), modules.map((module, index) => ({ nodeId: nodeIds[index], value: module.type === 'table_get_cell' ? valuesByNode[nodeIds[index]].value : valuesByNode[nodeIds[index]] })))
  assert.deepEqual(sqlite.logs.filter(row => row.nodeId).map(row => row.message), [...staticMessages.slice(0, 5), exportLog, ...staticMessages.slice(5)])
  assert.deepEqual(sqlite.artifacts, [{
    artifactId: artifact.artifactId, ordinal: 1, nodeId: exportNodeId,
    executionId: artifact.executionId, relativePath: sqlite.artifacts[0].relativePath,
    size: artifact.size, sha256: artifact.sha256, mimeType: artifact.mimeType,
    purpose: 'result', eventSequence: artifact.eventSequence,
  }])
  assert.match(sqlite.artifacts[0].relativePath, new RegExp(`^runs/${runId}/artifacts/exports/[0-9a-f]{32}\\.xlsx$`))
  assert.ok(sqlite.artifacts[0].eventSequence > 0)
  assert.equal(sqlite.eventTypes.find(row => row.type === 'execution:node-succeeded')?.count, modules.length)
  checkpoint('直接读取临时 autoflow.sqlite3，文档、终态、事件、8 个结果、日志与 XLSX 产物索引均和 HTTP/SSE 一致')

  await wait(400)
  const cloakDuring = [...cloakProcessesObservedDuringRun]
  const cloakAfter = cloakProcesses(userData)
  assert.deepEqual(cloakDuring, [])
  assert.deepEqual(cloakAfter, [])
  assert.deepEqual(await installedKernels(), [basename(sourceKernel)])
  checkpoint('requiresBrowser=false 的纯数据链运行前、运行中和完成后均无 CloakBrowser；运行槽已释放且 sidecar 运行清理完成')

  await capture(studio, join(evidenceDir, 'completed.png'))
  const sourceFileHashes = Object.fromEntries(await Promise.all([...frozenFiles, ...targetFiles].map(async file => [file, await fileHash(join(root, file))])))
  const targetSourceStatus = execFileSync('git', ['status', '--short', '--', ...targetFiles], { cwd: root, encoding: 'utf8' }).trim().split('\n').filter(Boolean)
  const uiNodes = approvedTypes.map(type => ({
    moduleType: type,
    status: 'executed-through-ui',
    instances: modules.flatMap((module, index) => module.type === type ? [{ nodeId: nodeIds[index], label: module.label, config: module.expected, result: valuesByNode[nodeIds[index]], logs: logs.items.filter(item => item.nodeId === nodeIds[index]).map(item => item.message) }] : []),
  }))
  const report = {
    evidenceId: 'BE-B4-table-formal-electron', checkedAt: new Date().toISOString(),
    gitHead, buildSha256: await buildHash(), workflowId: saved.id, profileId: profile.id, runId,
    result: 'passed', checks, platform: `${process.platform}-${process.arch}`, entry: 'development-build',
    commands: { build: 'npm run build', smoke: 'node scripts/smoke-studio-backend-b4-table.mjs', targetedTests: targetedTestCommand.join(' ') },
    targetedTestOutput, workflowPersistence: { revision: saved.revision, closedAndReopened: true, nodeCount: saved.nodes.length, edgeCount: saved.edges.length, variables: saved.variables },
    execution: { status: terminalRun.status, cleanupState: sqlite.run[0].cleanupState, resultCount: results.items.length, logCount: logs.items.length, observedEvents },
    sourceFileHashes, targetSourceStatus, approvedFamilySize: approvedTypes.length,
    uiExecutedTypes: executedTypes, uiNodeInstanceCount: modules.length, notUiExecutedTypes: [], uiNodes,
    httpEvidence: { results: results.items, logs: logs.items, artifacts: artifacts.items }, sqliteEvidence: sqlite,
    xlsxEvidence: { evidenceFile: 'table-ui-export.xlsx', sha256: artifact.sha256, size: artifact.size, workbook },
    artifactEventContract: { publicSse: 'execution:node_complete bound by executionId', artifactIndex: 'HTTP list/detail and SQLite workflow_run_artifacts', artifactRegisteredSseClaimed: false },
    requiresBrowserEvidence: browserRequirement,
    browserEvidence: { installedKernelEntries: [basename(sourceKernel)], cloakBrowserProcessesBefore: cloakBefore, cloakBrowserProcessesDuring: cloakDuring, cloakBrowserProcessesAfter: cloakAfter },
    workflowDataFlow: '共享 data_rows：add_row ×2 → add_column → set_cell(row 1) → get_cell(row 1) → export(2 rows) → delete_row(row -1，规范化为 row 1) → clear(1 remaining row)',
    boundaries: {
      workspace: 'ephemeral', userDatabaseTouched: false, browserLaunch: 'none (pure data)',
      interaction: 'CDP mouse and keyboard through the main window and formal Studio UI; macOS Cmd+W for close; public sidecar APIs used only for Profile setup and evidence reads; SQLite/OpenPyXL used only for evidence reads; no Store or page-internal function access',
      claim: 'all 7 registered table node types executed through the formal UI in 8 node instances; no other family is claimed by this run',
      sourceState: 'The table implementation is uncommitted in the shared working tree; gitHead, git status and source hashes are recorded without claiming the implementation belongs to gitHead.',
      uiGeneratedVariable: 'The UI auto-declared global cell_value from table_get_cell defaultData; the configured executor output name is score_value_ui. Both persisted facts are recorded without claiming cell_value was consumed.',
    },
  }

  eventAbort.abort(); eventAbort = undefined
  await wait(100)
  studio.close(); studio = undefined
  main.close(); main = undefined
  native.close(); native = undefined
  const electronPid = desktop.child.pid
  await stop(desktop.child); desktop = undefined
  await rm(userData, { recursive: true, force: true })
  await assert.rejects(() => stat(userData), { code: 'ENOENT' })
  const residualProcesses = scopedProcesses(userData)
  assert.deepEqual(residualProcesses, [])
  report.postCleanup = { electronPid, temporaryWorkspaceRemoved: true, residualProcesses }
  report.checks.push('停止本次 Electron/sidecar/worker 后删除临时工作区，按工作区路径检查无残留进程')
  await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
} catch (error) {
  let uiDiagnostic = null
  if (studio) {
    uiDiagnostic = await studio.evaluate(`(()=>({
      bodyText: document.body?.innerText.slice(0, 4000),
      nodes: [...document.querySelectorAll('.react-flow__node')].map(e => {
        const r = e.getBoundingClientRect()
        return { id: e.dataset.id, text: e.textContent, rect: { x: r.x, y: r.y, width: r.width, height: r.height } }
      }),
    }))()`).catch(reason => ({ diagnosticError: String(reason) }))
    await capture(studio, join(evidenceDir, 'blocked.png')).catch(() => undefined)
  }
  await writeFile(join(evidenceDir, 'blocked.json'), JSON.stringify({
    checkedAt: new Date().toISOString(), gitHead, checks, observedEvents,
    approvedTypes, uiDiagnostic, error: error instanceof Error ? error.stack : String(error),
  }, null, 2) + '\n')
  throw error
} finally {
  eventAbort?.abort(); studio?.close(); main?.close(); native?.close(); await stop(desktop?.child)
  await rm(userData, { recursive: true, force: true })
}

function checkpoint(message) { checks.push(message); console.log(message) }

function productionBrowserRequirement(moduleTypes) {
  const program = `import json
from autoflow.application.workflows.executors.production import build_production_executor_registry
from autoflow.application.workflows.runtime import WorkflowRuntime
types = ${JSON.stringify(moduleTypes)}
registry = build_production_executor_registry()
document = {"nodes": [{"id": str(index), "data": {"moduleType": module_type}} for index, module_type in enumerate(types)]}
print(json.dumps({"workflowRequiresBrowser": WorkflowRuntime(registry).requires_browser(document), "nodeRequiresBrowser": {module_type: registry.get(module_type).requires_browser for module_type in types}}))`
  return JSON.parse(execFileSync('uv', ['run', '--project', join(root, 'apps/backend'), 'python', '-c', program], { cwd: root, encoding: 'utf8' }))
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

async function openStudioFromMain(cdp, origin) {
  for (let attempt = 0; attempt < 3; attempt++) {
    await click(cdp, '工作流工作台')
    try {
      const target = await waitForTarget(origin, item => item.type === 'page' && item.url.includes('studio.html'), 'Studio target')
      return connectCdp(target.webSocketDebuggerUrl)
    } catch { /* dashboard can rerender after its resource refresh */ }
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

async function closeWindowThroughOs(pid) {
  assert.equal(await native.evaluate("(()=>{const w=qaElectron.BrowserWindow.getAllWindows().find(w=>w.getTitle().includes('工作流工作台'));if(!w)return false;qaElectron.app.focus({steal:true});w.show();w.focus();return true})()"), true)
  await wait(250)
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
  return waitFor(cdp, `(()=>{const rows=[...document.querySelectorAll(${JSON.stringify(selector)})].filter(e=>e.getClientRects().length),text=${JSON.stringify(text)};const e=!text?rows[0]:rows.find(e=>e.getAttribute('aria-label')===text)||rows.find(e=>e.textContent.trim()===text)||rows.find(e=>e.textContent.includes(text));if(!e||e.disabled)return null;e.scrollIntoView({block:'center',behavior:'instant'});const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;return e.contains(document.elementFromPoint(x,y))?{x,y}:null})()`, `unobscured ${text || selector}`)
}

async function click(cdp, text, selector = 'button') {
  const p = await point(cdp, selector, text)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', buttons: 1, clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', buttons: 0, clickCount: 1 })
  await wait(100)
}

async function selectNode(cdp, nodeId, moduleType) {
  for (let attempt = 0; attempt < 3; attempt++) {
    const p = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__node[data-id=${JSON.stringify(nodeId)}]');if(!e)return null;const r=e.getBoundingClientRect(),fractions=[[.5,.5],[.2,.5],[.8,.5],[.5,.2],[.5,.8],[.2,.2],[.8,.8]];for(const [xf,yf] of fractions){const x=r.x+r.width*xf,y=r.y+r.height*yf;if(e.contains(document.elementFromPoint(x,y)))return{x,y}}return null})()`, `visible node ${nodeId}`)
    await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p })
    await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', buttons: 1, clickCount: 1 })
    await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', buttons: 0, clickCount: 1 })
    await wait(180)
    const selected = await cdp.evaluate(`[...document.querySelectorAll('span')].some(e=>e.getClientRects().length&&e.textContent.trim()===${JSON.stringify(moduleType)}&&e.classList.contains('badge'))`)
    if (selected) return
  }
  throw new Error(`failed to select visible node ${moduleType} (${nodeId})`)
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

async function selectNative(cdp, selector, expectedText) {
  await click(cdp, '', selector)
  await waitFor(cdp, `document.querySelector(${JSON.stringify(selector)})?.getAttribute('data-state') === 'open'`, `${selector} dropdown open`)
  const selection = await waitFor(cdp, `(()=>{const options=[...document.querySelectorAll('[role="option"]')].filter(e=>e.getClientRects().length),target=options.findIndex(e=>e.textContent.trim()===${JSON.stringify(expectedText)}),current=options.findIndex(e=>e.getAttribute('data-state')==='checked');return target>=0&&current>=0?{target,current,count:options.length,labels:options.map(e=>e.textContent.trim())}:null})()`, `${selector} visible options`)
  assert.equal(selection.labels[selection.target], expectedText)
  const forward = selection.target > selection.current
  const key = forward ? 'ArrowDown' : 'ArrowUp'
  for (let step = 0; step < Math.abs(selection.target - selection.current); step++) {
    await press(cdp, key, { code: key, keyCode: forward ? 40 : 38 })
  }
  await press(cdp, 'Enter', { code: 'Enter', keyCode: 13 })
  await waitFor(cdp, `document.querySelector(${JSON.stringify(selector)})?.textContent.includes(${JSON.stringify(expectedText)})`, `${selector}=${expectedText}`)
}

async function press(cdp, key, { modifiers = 0, code = key, keyCode = key === 'Enter' ? 13 : 0 } = {}) {
  await cdp.command('Input.dispatchKeyEvent', { type: 'keyDown', key, code, modifiers, windowsVirtualKeyCode: keyCode })
  await cdp.command('Input.dispatchKeyEvent', { type: 'keyUp', key, code, modifiers, windowsVirtualKeyCode: keyCode })
  await wait(80)
}

async function addFromQuickPicker(cdp, index, label) {
  const row = Math.floor(index / 2), column = index % 2
  const xFraction = row === 3 ? (column ? .53 : .08) : (column ? .47 : .02)
  const target = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__pane');if(!e)return null;const r=e.getBoundingClientRect(),x=r.x+r.width*${xFraction},y=r.y+r.height*[.15,.38,.61,.80][${row}];return document.elementFromPoint(x,y)===e?{x,y}:null})()`, `empty workflow grid cell ${index + 1}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...target, button: 'right', clickCount: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...target, button: 'right', clickCount: 1 })
  await setInput(cdp, 'input[placeholder="搜索模块（支持拼音）"]', label)
  await click(cdp, label, '[role="button"]')
}

async function placeFirstNode(cdp, nodeId) {
  const points = await waitFor(cdp, `(()=>{const pane=document.querySelector('.react-flow__pane'),node=document.querySelector('.react-flow__node[data-id=${JSON.stringify(nodeId)}]');if(!pane||!node)return null;const p=pane.getBoundingClientRect(),n=node.getBoundingClientRect();return{from:{x:n.x+n.width/2,y:n.y+n.height/2},to:{x:p.x+p.width*.02+n.width/2,y:p.y+p.height*.15+n.height/2}}})()`, 'first node grid placement')
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...points.from })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...points.from, button: 'left', buttons: 1, clickCount: 1 })
  for (let step = 1; step <= 10; step++) {
    await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', x: points.from.x + (points.to.x - points.from.x) * step / 10, y: points.from.y + (points.to.y - points.from.y) * step / 10, button: 'left', buttons: 1 })
  }
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...points.to, button: 'left', buttons: 0, clickCount: 1 })
  await wait(150)
}

async function connectNodes(cdp, sourceId, targetId) {
  const points = await waitFor(cdp, `(()=>{const a=document.querySelector('.react-flow__node[data-id=${JSON.stringify(sourceId)}] .react-flow__handle.source:not([data-handleid])'),b=document.querySelector('.react-flow__node[data-id=${JSON.stringify(targetId)}] .react-flow__handle.target');if(!a||!b)return null;const ar=a.getBoundingClientRect(),br=b.getBoundingClientRect();return{a:{x:ar.x+ar.width/2,y:ar.y+ar.height/2},b:{x:br.x+br.width/2,y:br.y+br.height/2}}})()`, `handles ${sourceId} -> ${targetId}`)
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...points.a })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...points.a, button: 'left', buttons: 1, clickCount: 1 })
  for (let step = 1; step <= 12; step++) {
    await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', x: points.a.x + (points.b.x - points.a.x) * step / 12, y: points.a.y + (points.b.y - points.a.y) * step / 12, button: 'left', buttons: 1 })
    await wait(12)
  }
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...points.b, button: 'left', buttons: 0, clickCount: 1 })
  await wait(120)
}

function sqliteEvidence(workspace, workflowId, runId) {
  const database = join(workspace, 'data', 'autoflow.sqlite3')
  const workflow = sqlLiteral(workflowId), run = sqlLiteral(runId)
  const results = sqliteRows(database, `SELECT seq AS sequence,json_extract(payload,'$.nodeId') AS nodeId,json_quote(json_extract(payload,'$.payload.result.data')) AS valueJson FROM workflow_run_events WHERE run_id=${run} AND json_extract(payload,'$.type')='execution:node-succeeded' ORDER BY seq`)
    .map(({ valueJson, ...row }) => ({ ...row, value: JSON.parse(valueJson) }))
  return {
    document: sqliteRows(database, `SELECT id,name,revision,json_array_length(document,'$.nodes') AS nodeCount,json_array_length(document,'$.edges') AS edgeCount,json_array_length(document,'$.variables') AS variableCount FROM workflow_documents WHERE id=${workflow}`),
    run: sqliteRows(database, `SELECT id AS runId,workflow_id AS workflowId,json_extract(payload,'$.status') AS status,json_extract(payload,'$.cleanupState') AS cleanupState,active_slot AS activeSlot,CAST(json_extract(payload,'$.eventCount') AS INTEGER) AS eventCount,CAST(json_extract(payload,'$.logCount') AS INTEGER) AS logCount FROM workflow_runs WHERE id=${run}`),
    eventTypes: sqliteRows(database, `SELECT json_extract(payload,'$.type') AS type,COUNT(*) AS count FROM workflow_run_events WHERE run_id=${run} GROUP BY type ORDER BY type`),
    results,
    logs: sqliteRows(database, `SELECT seq AS sequence,json_extract(payload,'$.nodeId') AS nodeId,json_extract(payload,'$.payload.message') AS message FROM workflow_run_events WHERE run_id=${run} AND json_extract(payload,'$.type')='execution:log' ORDER BY seq`),
    artifacts: sqliteRows(database, `SELECT id AS artifactId,ordinal,node_id AS nodeId,execution_id AS executionId,json_extract(payload,'$.relativePath') AS relativePath,CAST(json_extract(payload,'$.size') AS INTEGER) AS size,json_extract(payload,'$.sha256') AS sha256,json_extract(payload,'$.mimeType') AS mimeType,purpose,event_seq AS eventSequence FROM workflow_run_artifacts WHERE run_id=${run} ORDER BY ordinal`),
  }
}

function sqliteRows(database, query) {
  const output = execFileSync('sqlite3', ['-json', database, query], { encoding: 'utf8' }).trim()
  return output ? JSON.parse(output) : []
}

function sqlLiteral(value) { return `'${String(value).replaceAll("'", "''")}'` }

function cloakProcesses(workspace) {
  return execFileSync('ps', ['-axo', 'command='], { encoding: 'utf8' }).split('\n').filter(line => line.includes(workspace) && /Chromium|CloakBrowser/.test(line))
}

function observeCloakProcesses(workspace, output) {
  for (const process of cloakProcesses(workspace)) output.add(process)
}

async function capture(cdp, path) {
  await cdp.evaluate('document.fonts.ready.then(()=>true)')
  const { data } = await cdp.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  await writeFile(path, data, 'base64')
}

async function installedKernels() {
  return (await readdir(join(userData, 'data', 'kernels'))).filter(name => name.startsWith('chromium-'))
}

async function fileHash(path) {
  return createHash('sha256').update(await readFile(path)).digest('hex')
}

async function buildHash() {
  const hash = createHash('sha256')
  for (const file of (await readdir(join(root, 'apps/desktop/out'), { recursive: true })).filter(file => /\.(js|css|html)$/.test(file)).sort()) {
    hash.update(file).update(await readFile(join(root, 'apps/desktop/out', file)))
  }
  return hash.digest('hex')
}


function inspectWorkbook(path) {
  const program = `import json, sys
from openpyxl import load_workbook
workbook = load_workbook(sys.argv[1], data_only=False)
sheet = workbook['正式结果']
output = {
  'sheetNames': workbook.sheetnames,
  'values': [list(row) for row in sheet.iter_rows(values_only=True)],
  'freezePanes': str(sheet.freeze_panes),
  'header': {
    'bold': sheet['A1'].font.bold,
    'fontColor': sheet['A1'].font.color.rgb,
    'fill': sheet['A1'].fill.fgColor.rgb,
    'alignment': sheet['A1'].alignment.horizontal,
    'borderStyle': sheet['A1'].border.left.style,
    'borderColor': sheet['A1'].border.left.color.rgb,
  },
  'dataStyle': {
    'firstFillType': sheet['A2'].fill.fill_type,
    'alternatingFill': sheet['A3'].fill.fgColor.rgb,
    'firstBorderStyle': sheet['A2'].border.left.style,
    'secondBorderStyle': sheet['A3'].border.left.style,
  },
  'columnWidths': {letter: sheet.column_dimensions[letter].width for letter in ('A', 'B', 'C')},
  'headerHeight': sheet.row_dimensions[1].height,
}
workbook.close()
print(json.dumps(output, ensure_ascii=False))`
  return JSON.parse(execFileSync('uv', ['run', '--project', join(root, 'apps/backend'), 'python', '-c', program, path], { cwd: root, encoding: 'utf8' }))
}

function scopedProcesses(workspace) {
  return execFileSync('ps', ['-axo', 'pid=,command='], { encoding: 'utf8' }).split('\n').filter(line => line.includes(workspace))
}
