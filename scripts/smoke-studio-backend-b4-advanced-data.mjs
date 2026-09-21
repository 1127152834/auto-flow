import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises'
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
const evidenceDir = await mkdtemp(join(evidenceRoot, 'formal-advanced-electron-'))
const userData = await mkdtemp(join(tmpdir(), 'autoflow-studio-b4-advanced-'))
const workflowName = 'B4 高级数据正式闭环'
const checks = []
const observedEvents = []
const sourceFamilies = {
  'list_advanced.py': [
    'list_reverse', 'list_find', 'list_count', 'list_filter', 'list_map', 'list_merge',
    'list_flatten', 'list_chunk', 'list_remove_empty', 'list_intersection', 'list_union',
    'list_difference', 'list_cartesian_product', 'list_shuffle', 'list_sample',
  ],
  'dict_advanced.py': [
    'dict_merge', 'dict_filter', 'dict_map_values', 'dict_invert', 'dict_sort',
    'dict_deep_copy', 'dict_get_path', 'dict_flatten',
  ],
  'string_convert.py': [
    'csv_parse', 'csv_generate', 'list_to_string_advanced',
  ],
}
const moduleSpecs = [
  {
    label: '分割文本', type: 'string_split', sourceFile: 'data_structure.py', support: true,
    expected: { inputText: 'alpha,beta,alpha,,gamma', separator: ',', variableName: 'base_list' },
    expectedResult: { value: ['alpha', 'beta', 'alpha', '', 'gamma'] },
    inputs: [['[placeholder="要分割的文本，支持 {变量名}"]', 'alpha,beta,alpha,,gamma'], ['[placeholder^="如: , 或 |"]', ','], ['#variableName', 'base_list']],
  },
  {
    label: '列表反转', type: 'list_reverse', sourceFile: 'list_advanced.py',
    expected: { listVariable: 'base_list', resultVariable: 'reversed_ui' },
    expectedResult: { value: ['gamma', '', 'alpha', 'beta', 'alpha'] },
    inputs: [['[placeholder="输入列表变量名"]', 'base_list'], ['[placeholder="保存结果的变量名"]', 'reversed_ui']],
  },
  {
    label: '列表查找', type: 'list_find', sourceFile: 'list_advanced.py',
    expected: { listVariable: 'base_list', searchValue: 'beta', resultVariable: 'found_index_ui' },
    expectedResult: { value: 1 },
    inputs: [['[placeholder="输入列表变量名"]', 'base_list'], ['[placeholder="输入要查找的值"]', 'beta'], ['[placeholder="保存索引的变量名"]', 'found_index_ui']],
  },
  {
    label: '列表计数', type: 'list_count', sourceFile: 'list_advanced.py',
    expected: { listVariable: 'base_list', searchValue: 'alpha', resultVariable: 'alpha_count_ui' },
    expectedResult: { value: 2 },
    inputs: [['[placeholder="输入列表变量名"]', 'base_list'], ['[placeholder="输入要计数的值"]', 'alpha'], ['[placeholder="保存计数的变量名"]', 'alpha_count_ui']],
  },
  {
    label: '列表过滤', type: 'list_filter', sourceFile: 'list_advanced.py',
    expected: { listVariable: 'base_list', condition: "x != ''", resultVariable: 'clean_list_ui' },
    expectedResult: { value: ['alpha', 'beta', 'alpha', 'gamma'] },
    inputs: [['[placeholder="输入列表变量名"]', 'base_list'], ['[placeholder="例如：x > 10"]', "x != ''"], ['[placeholder="保存结果的变量名"]', 'clean_list_ui']],
  },
  {
    label: '列表映射', type: 'list_map', sourceFile: 'list_advanced.py',
    expected: { listVariable: 'clean_list_ui', expression: 'x.upper()', resultVariable: 'upper_list_ui' },
    expectedResult: { value: ['ALPHA', 'BETA', 'ALPHA', 'GAMMA'] },
    inputs: [['[placeholder="输入列表变量名"]', 'clean_list_ui'], ['[placeholder="例如：x * 2"]', 'x.upper()'], ['[placeholder="保存结果的变量名"]', 'upper_list_ui']],
  },
  {
    label: '列表取值', type: 'list_get', sourceFile: 'data_structure.py', support: true,
    expected: { listVariable: 'base_list', listIndex: '0', variableName: 'first_item_ui' },
    expectedResult: { value: 'alpha' },
    inputs: [['#listVariable', 'base_list'], ['[placeholder="从0开始，支持负数和 {变量名}"]', '0'], ['#variableName', 'first_item_ui']],
  },
  {
    label: '列表取值', type: 'list_get', sourceFile: 'data_structure.py', support: true,
    expected: { listVariable: 'base_list', listIndex: '4', variableName: 'last_item_ui' },
    expectedResult: { value: 'gamma' },
    inputs: [['#listVariable', 'base_list'], ['[placeholder="从0开始，支持负数和 {变量名}"]', '4'], ['#variableName', 'last_item_ui']],
  },
  {
    label: '字典操作', type: 'dict_operation', sourceFile: 'data_structure.py', support: true,
    expected: { dictVariable: 'base_dict_ui', dictKey: 'score', dictValue: '{alpha_count_ui}' },
    expectedResult: { dict: { score: '2' }, keys: ['score'] },
    inputs: [['#dictVariable', 'base_dict_ui'], ['[placeholder="键名，支持 {变量名}"]', 'score'], ['[placeholder="要设置的值，支持 {变量名}"]', '{alpha_count_ui}']],
  },
  {
    label: '字典操作', type: 'dict_operation', sourceFile: 'data_structure.py', support: true,
    expected: { dictVariable: 'base_dict_ui', dictKey: 'name', dictValue: '{first_item_ui}' },
    expectedResult: { dict: { score: '2', name: 'alpha' }, keys: ['score', 'name'] },
    inputs: [['#dictVariable', 'base_dict_ui'], ['[placeholder="键名，支持 {变量名}"]', 'name'], ['[placeholder="要设置的值，支持 {变量名}"]', '{first_item_ui}']],
  },
  {
    label: '字典操作', type: 'dict_operation', sourceFile: 'data_structure.py', support: true,
    expected: { dictVariable: 'second_dict_ui', dictKey: 'extra', dictValue: '{last_item_ui}' },
    expectedResult: { dict: { extra: 'gamma' }, keys: ['extra'] },
    inputs: [['#dictVariable', 'second_dict_ui'], ['[placeholder="键名，支持 {变量名}"]', 'extra'], ['[placeholder="要设置的值，支持 {变量名}"]', '{last_item_ui}']],
  },
  {
    label: '列表合并', type: 'list_merge', sourceFile: 'list_advanced.py',
    expected: { list1: 'base_list', list2: 'clean_list_ui', resultVariable: 'merged_list_ui' },
    expectedResult: { value: ['alpha', 'beta', 'alpha', '', 'gamma', 'alpha', 'beta', 'alpha', 'gamma'] },
    inputs: [['[placeholder="输入第一个列表变量名"]', 'base_list'], ['[placeholder="输入第二个列表变量名"]', 'clean_list_ui'], ['[placeholder="保存结果的变量名"]', 'merged_list_ui']],
  },
  {
    label: '列表分组', type: 'list_chunk', sourceFile: 'list_advanced.py',
    expected: { listVariable: 'base_list', chunkSize: '2', resultVariable: 'chunked_list_ui' },
    expectedResult: { value: [['alpha', 'beta'], ['alpha', ''], ['gamma']] },
    inputs: [['[placeholder="输入列表变量名"]', 'base_list'], ['[placeholder="每块的元素数量"]', '2'], ['[placeholder="保存结果的变量名"]', 'chunked_list_ui']],
  },
  {
    label: '列表扁平化', type: 'list_flatten', sourceFile: 'list_advanced.py',
    expected: { listVariable: 'chunked_list_ui', depth: 2, resultVariable: 'flattened_list_ui' },
    expectedResult: { value: ['alpha', 'beta', 'alpha', '', 'gamma'] },
    inputs: [['[placeholder="输入嵌套列表变量名"]', 'chunked_list_ui'], ['#depth', '2'], ['[placeholder="保存结果的变量名"]', 'flattened_list_ui']],
  },
  {
    label: '列表去空', type: 'list_remove_empty', sourceFile: 'list_advanced.py',
    expected: { listVariable: 'base_list', resultVariable: 'nonempty_list_ui' },
    expectedResult: { value: ['alpha', 'beta', 'alpha', 'gamma'] },
    inputs: [['[placeholder="输入列表变量名"]', 'base_list'], ['[placeholder="保存结果的变量名"]', 'nonempty_list_ui']],
  },
  {
    label: '列表交集', type: 'list_intersection', sourceFile: 'list_advanced.py',
    expected: { list1: 'base_list', list2: 'clean_list_ui', resultVariable: 'intersection_ui' },
    validateResult: result => assert.deepEqual(new Set(result.value), new Set(['alpha', 'beta', 'gamma'])),
    inputs: [['[placeholder="输入第一个列表变量名"]', 'base_list'], ['[placeholder="输入第二个列表变量名"]', 'clean_list_ui'], ['[placeholder="保存结果的变量名"]', 'intersection_ui']],
  },
  {
    label: '列表并集', type: 'list_union', sourceFile: 'list_advanced.py',
    expected: { list1: 'base_list', list2: 'clean_list_ui', resultVariable: 'union_ui' },
    validateResult: result => assert.deepEqual(new Set(result.value), new Set(['alpha', 'beta', '', 'gamma'])),
    inputs: [['[placeholder="输入第一个列表变量名"]', 'base_list'], ['[placeholder="输入第二个列表变量名"]', 'clean_list_ui'], ['[placeholder="保存结果的变量名"]', 'union_ui']],
  },
  {
    label: '列表差集', type: 'list_difference', sourceFile: 'list_advanced.py',
    expected: { list1: 'base_list', list2: 'clean_list_ui', resultVariable: 'difference_ui' },
    expectedResult: { value: [''] },
    inputs: [['[placeholder="输入第一个列表变量名"]', 'base_list'], ['[placeholder="输入第二个列表变量名"]', 'clean_list_ui'], ['[placeholder="保存结果的变量名"]', 'difference_ui']],
  },
  {
    label: '列表笛卡尔积', type: 'list_cartesian_product', sourceFile: 'list_advanced.py',
    expected: { list1: 'base_list', list2: 'clean_list_ui', resultVariable: 'cartesian_ui' },
    validateResult: result => { assert.equal(result.value.length, 20); assert.deepEqual(result.value[0], ['alpha', 'alpha']); assert.deepEqual(result.value.at(-1), ['gamma', 'gamma']) },
    inputs: [['[placeholder="输入第一个列表变量名"]', 'base_list'], ['[placeholder="输入第二个列表变量名"]', 'clean_list_ui'], ['[placeholder="保存结果的变量名"]', 'cartesian_ui']],
  },
  {
    label: '列表随机打乱', type: 'list_shuffle', sourceFile: 'list_advanced.py',
    expected: { listVariable: 'base_list', resultVariable: 'shuffled_ui' },
    validateResult: result => assert.deepEqual([...result.value].sort(), ['', 'alpha', 'alpha', 'beta', 'gamma'].sort()),
    inputs: [['[placeholder="输入列表变量名"]', 'base_list'], ['[placeholder="保存结果的变量名"]', 'shuffled_ui']],
  },
  {
    label: '列表采样', type: 'list_sample', sourceFile: 'list_advanced.py',
    expected: { listVariable: 'clean_list_ui', sampleSize: '2', resultVariable: 'sample_ui' },
    validateResult: result => { assert.equal(result.value.length, 2); assert.ok(result.value.every(value => ['alpha', 'beta', 'gamma'].includes(value))) },
    inputs: [['[placeholder="输入列表变量名"]', 'clean_list_ui'], ['[placeholder="要抽取的元素数量"]', '2'], ['[placeholder="保存结果的变量名"]', 'sample_ui']],
  },
  {
    label: '字典合并', type: 'dict_merge', sourceFile: 'dict_advanced.py',
    expected: { dict1: 'base_dict_ui', dict2: 'second_dict_ui', resultVariable: 'merged_dict_ui' },
    expectedResult: { score: '2', name: 'alpha', extra: 'gamma' },
    inputs: [['[placeholder="输入第一个字典变量名"]', 'base_dict_ui'], ['[placeholder="输入第二个字典变量名"]', 'second_dict_ui'], ['[placeholder="保存结果的变量名"]', 'merged_dict_ui']],
  },
  {
    label: '字典过滤', type: 'dict_filter', sourceFile: 'dict_advanced.py',
    expected: { dictVariable: 'merged_dict_ui', condition: "k != 'extra'", resultVariable: 'filtered_dict_ui' },
    expectedResult: { score: '2', name: 'alpha' },
    inputs: [['[placeholder="输入字典变量名"]', 'merged_dict_ui'], ['[placeholder="例如：v > 10"]', "k != 'extra'"], ['[placeholder="保存结果的变量名"]', 'filtered_dict_ui']],
  },
  {
    label: '字典映射值', type: 'dict_map_values', sourceFile: 'dict_advanced.py',
    expected: { dictVariable: 'filtered_dict_ui', expression: 'str(v)', resultVariable: 'mapped_dict_ui' },
    expectedResult: { score: '2', name: 'alpha' },
    inputs: [['[placeholder="输入字典变量名"]', 'filtered_dict_ui'], ['[placeholder="例如：v * 2"]', 'str(v)'], ['[placeholder="保存结果的变量名"]', 'mapped_dict_ui']],
  },
  {
    label: '字典反转', type: 'dict_invert', sourceFile: 'dict_advanced.py',
    expected: { dictVariable: 'mapped_dict_ui', resultVariable: 'inverted_dict_ui' },
    expectedResult: { '2': 'score', alpha: 'name' },
    inputs: [['[placeholder="输入字典变量名"]', 'mapped_dict_ui'], ['[placeholder="保存结果的变量名"]', 'inverted_dict_ui']],
  },
  {
    label: '字典排序', type: 'dict_sort', sourceFile: 'dict_advanced.py',
    expected: { dictVariable: 'mapped_dict_ui', sortBy: 'value', order: 'desc', resultVariable: 'sorted_dict_ui' },
    expectedResult: { score: '2', name: 'alpha' },
    inputs: [['[placeholder="输入字典变量名"]', 'mapped_dict_ui'], ['[placeholder="保存结果的变量名"]', 'sorted_dict_ui']],
    selects: [['#sortBy', '按值排序'], ['#order', '降序']],
  },
  {
    label: '字典深拷贝', type: 'dict_deep_copy', sourceFile: 'dict_advanced.py',
    expected: { dictVariable: 'merged_dict_ui', resultVariable: 'copied_dict_ui' },
    expectedResult: { score: '2', name: 'alpha', extra: 'gamma' },
    inputs: [['[placeholder="输入字典变量名"]', 'merged_dict_ui'], ['[placeholder="保存结果的变量名"]', 'copied_dict_ui']],
  },
  {
    label: '字典路径取值', type: 'dict_get_path', sourceFile: 'dict_advanced.py',
    expected: { dictVariable: 'merged_dict_ui', path: 'score', defaultValue: 'missing', resultVariable: 'path_value_ui' },
    expectedResult: { value: '2' },
    inputs: [['[placeholder="输入字典变量名"]', 'merged_dict_ui'], ['[placeholder="例如：user.profile.name"]', 'score'], ['[placeholder="路径不存在时返回的默认值"]', 'missing'], ['[placeholder="保存结果的变量名"]', 'path_value_ui']],
  },
  {
    label: '字典扁平化', type: 'dict_flatten', sourceFile: 'dict_advanced.py',
    expected: { dictVariable: 'merged_dict_ui', separator: '/', resultVariable: 'flat_dict_ui' },
    expectedResult: { score: '2', name: 'alpha', extra: 'gamma' },
    inputs: [['[placeholder="输入嵌套字典变量名"]', 'merged_dict_ui'], ['[placeholder="键路径分隔符（默认：.）"]', '/'], ['[placeholder="保存结果的变量名"]', 'flat_dict_ui']],
  },
  {
    label: 'CSV解析', type: 'csv_parse', sourceFile: 'string_convert.py',
    expected: { csvContent: 'alice;10', delimiter: ';', hasHeader: 'false', resultVariable: 'csv_rows_ui' },
    expectedResult: { value: [['alice', '10']] },
    inputs: [['[placeholder="输入CSV内容或变量"]', 'alice;10'], ['[placeholder="分隔符（默认：,）"]', ';'], ['[placeholder="保存结果的变量名"]', 'csv_rows_ui']],
    selects: [['#hasHeader', '否']],
  },
  {
    label: 'CSV生成', type: 'csv_generate', sourceFile: 'string_convert.py',
    expected: { dataVariable: 'csv_rows_ui', delimiter: '|', resultVariable: 'csv_text_ui' },
    expectedResult: { value: 'alice|10\r\n' },
    inputs: [['[placeholder="输入数据列表变量名"]', 'csv_rows_ui'], ['[placeholder="分隔符（默认：,）"]', '|'], ['[placeholder="保存结果的变量名"]', 'csv_text_ui']],
  },
  {
    label: '列表转字符串（高级）', type: 'list_to_string_advanced', sourceFile: 'string_convert.py',
    expected: { listVariable: 'clean_list_ui', separator: '|', prefix: '[', suffix: ']', resultVariable: 'summary_text_ui' },
    expectedResult: { value: '[alpha|beta|alpha|gamma]' },
    inputs: [['[placeholder="输入列表变量名"]', 'clean_list_ui'], ['[placeholder="元素之间的分隔符"]', '|'], ['[placeholder="字符串前缀"]', '['], ['[placeholder="字符串后缀"]', ']'], ['[placeholder="保存结果的变量名"]', 'summary_text_ui']],
  },
]
const modules = moduleSpecs.map(module => ({
  ...module,
  configure: async cdp => {
    for (const [selector, value] of module.inputs ?? []) await setInput(cdp, selector, value)
    for (const [selector, value] of module.selects ?? []) await selectNative(cdp, selector, value)
  },
}))
const approvedTypes = Object.values(sourceFamilies).flat()
const executedTypes = modules.map(module => module.type)
const approvedExecutedTypes = modules.filter(module => !module.support).map(module => module.type)
const notUiExecutedTypes = approvedTypes.filter(type => !approvedExecutedTypes.includes(type))
const targetFiles = [
  'apps/backend/src/autoflow/application/workflows/executors/list_advanced.py',
  'apps/backend/src/autoflow/application/workflows/executors/dict_advanced.py',
  'apps/backend/src/autoflow/application/workflows/executors/string_convert.py',
  'apps/backend/src/autoflow/application/workflows/executors/safe_expr.py',
]
const frozenFiles = [
  'reference/WebRPA/backend/app/executors/list_advanced.py',
  'reference/WebRPA/backend/app/executors/dict_advanced.py',
  'reference/WebRPA/backend/app/executors/string_convert.py',
  'reference/WebRPA/backend/app/utils/safe_expr.py',
]
let desktop
let main
let studio
let eventAbort
const cloakProcessesObservedDuringRun = new Set()

try {
assert.equal(process.platform, 'darwin', 'formal evidence requires macOS')
assert.equal(process.arch, 'arm64', 'formal evidence requires native arm64 Node/Electron')
assert.match(gitHead, /^[0-9a-f]{40}$/)
await writeFile(join(userData, '.autoflow-workspace.json'), JSON.stringify({ schemaVersion: 1, kind: 'autoflow-workspace' }))
await mkdir(join(userData, 'data', 'kernels'), { recursive: true })
execFileSync('cp', ['-cR', sourceKernel, join(userData, 'data', 'kernels', basename(sourceKernel))])
const browserRequirement = productionBrowserRequirement(executedTypes)
assert.equal(browserRequirement.workflowRequiresBrowser, false)
assert.ok(Object.values(browserRequirement.nodeRequiresBrowser).every(value => value === false))
checkpoint(`生产执行器注册表对 ${modules.length} 节点文档计算 requiresBrowser=false`)

  desktop = await launchElectron(root, { launchArgs: [`--user-data-dir=${userData}`] })
  assert.equal(desktop.packaged, false, 'formal B4 evidence must use the development Electron entry')
  main = desktop.cdp
  await main.command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1024, deviceScaleFactor: 1, mobile: false })
  await waitFor(main, "document.body?.innerText.includes('本地服务正常')", 'main service readiness', 30_000)
  const runtime = await main.evaluate('window.autoflow.getRuntimeContext()')
  assert.equal(runtime.sidecar.state, 'ready')
  eventAbort = new AbortController()
  void collectEvents(runtime, eventAbort.signal, observedEvents)

  const profile = await api(runtime, '/v1/profiles', {
    method: 'POST',
    body: {
      name: 'B4 高级数据纯数据验收配置', description: '临时工作区；纯数据工作流不得启动浏览器', startUrl: 'about:blank',
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
  await studio.command('Emulation.setDeviceMetricsOverride', { width: 3840, height: 2400, deviceScaleFactor: 1, mobile: false })
  await waitFor(studio, "document.body?.innerText.includes('模块库') && document.body.innerText.includes('213')", 'formal Studio', 30_000)
  assert.equal(await studio.evaluate("document.body.innerText.includes('Mock 接口')"), false)
  await waitFor(studio, `document.querySelector('[aria-label="运行浏览器配置"]')?.value === ${JSON.stringify(profile.id)}`, 'managed Profile selection')
  checkpoint('主窗口通过真实点击打开正式 Studio；未直接访问 Store 或页面内部函数')

  await click(studio, '新建')
  await waitFor(studio, "document.querySelectorAll('.react-flow__node').length === 0", 'new empty workflow')
  await setInput(studio, 'input[placeholder="工作流名称"]', workflowName)

  const nodeIds = []
  for (let index = 0; index < modules.length; index++) {
    const module = modules[index]
    await addFromQuickPicker(studio, index, module.label)
    const nodeId = await waitFor(studio, `(()=>{const rows=[...document.querySelectorAll('.react-flow__node')].filter(e=>e.textContent.includes(${JSON.stringify(module.label)}));return rows.at(-1)?.dataset.id||null})()`, `node ${module.type}`)
    nodeIds.push(nodeId)
    await selectNode(studio, nodeId, module.type)
    await module.configure(studio)
    await moveNode(studio, nodeId, index, modules.length)
  }
  assert.equal(new Set(nodeIds).size, modules.length)
  assert.equal(await studio.evaluate("document.querySelectorAll('.react-flow__node').length"), modules.length)
  await click(studio, '', '.react-flow__controls-fitview')
  await wait(300)
  checkpoint(`通过画布原生右键菜单和配置面板添加并配置全部 ${approvedTypes.length} 个高级数据节点及 ${modules.length - approvedTypes.length} 个数据准备节点`)

  for (let index = 0; index < nodeIds.length - 1; index++) {
    await connectNodes(studio, nodeIds[index], nodeIds[index + 1])
    await waitFor(studio, `document.querySelectorAll('.react-flow__edge').length === ${index + 1}`, `workflow edge ${index + 1}`)
  }
  checkpoint(`通过画布拖拽节点与连接手柄建立 ${modules.length} 节点、${modules.length - 1} 条边的完整数据依赖链`)

  await click(studio, '执行日志')
  await click(studio, '保存')
  await waitFor(studio, `document.body?.innerText.includes(${JSON.stringify(`工作流已保存: ${workflowName}`)})`, 'workflow save acknowledgement')
  const savedList = await api(runtime, '/workflows')
  const saved = savedList.find(item => item.name === workflowName)
  assert.ok(saved)
  assert.equal(saved.revision, 1)
  assert.deepEqual(saved.variables, [
    { name: 'split_result', type: 'string', scope: 'global' },
    { name: 'list_item', type: 'string', scope: 'global' },
    { name: 'dict_result', type: 'string', scope: 'global' },
  ])
  assert.deepEqual(saved.nodes.map(node => node.data.moduleType), executedTypes)
  assert.equal(saved.edges.length, modules.length - 1)
  for (let index = 0; index < modules.length; index++) {
    const data = saved.nodes.find(node => node.id === nodeIds[index])?.data
    assert.ok(data)
    for (const [key, value] of Object.entries(modules[index].expected)) assert.deepEqual(data[key], value, `${modules[index].type}.${key}`)
  }
  checkpoint(`真实 UI 保存经正式 HTTP 写入 SQLite；${modules.length} 个节点配置、数据变量引用和 ${modules.length - 1} 条边均与输入一致`)

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
  const nodeValues = modules.map((module, index) => results.items.find(item => item.nodeId === nodeIds[index])?.values)
  const values = Object.fromEntries(modules.map((module, index) => [module.type, nodeValues[index]]))
  for (let index = 0; index < modules.length; index++) {
    const module = modules[index]
    if (module.validateResult) module.validateResult(nodeValues[index])
    else assert.deepEqual(nodeValues[index], module.expectedResult, `${module.type} result`)
  }
  const logs = await api(runtime, `/workflow-runs/${encodeURIComponent(runId)}/logs?cursor=0&limit=200`)
  for (const nodeId of nodeIds) assert.ok(logs.items.some(item => item.nodeId === nodeId), `missing persisted log for ${nodeId}`)
  const nodeLogs = logs.items.filter(item => item.nodeId)
  assert.equal(nodeLogs.length, modules.length)
  checkpoint(`HTTP 精确核对 ${modules.length} 个结果；集合和随机分支按不变量验证，且全部节点的持久化日志完整`)

  const sqlite = sqliteEvidence(userData, saved.id, runId)
  assert.deepEqual(sqlite.document, [{ id: saved.id, name: workflowName, revision: 1, nodeCount: modules.length, edgeCount: modules.length - 1, variableCount: saved.variables.length }])
  assert.deepEqual(sqlite.run.map(({ eventCount, ...row }) => row), [{ runId, workflowId: saved.id, status: 'completed', cleanupState: 'completed', activeSlot: null, logCount: terminalRun.logCount }])
  assert.equal(sqlite.eventTypes.reduce((sum, row) => sum + row.count, 0), sqlite.run[0].eventCount)
  assert.deepEqual(
    sqlite.results.map(row => ({ nodeId: row.nodeId, value: row.value })),
    modules.map((module, index) => ({ nodeId: nodeIds[index], value: rawResultData(nodeValues[index]) })),
  )
  assert.deepEqual(sqlite.logs.filter(row => row.nodeId).map(row => row.message), nodeLogs.map(row => row.message))
  assert.equal(sqlite.eventTypes.find(row => row.type === 'execution:node-succeeded')?.count, modules.length)
  assert.equal(sqlite.eventTypes.find(row => row.type === 'execution:log')?.count, terminalRun.logCount)
  checkpoint('直接读取临时 autoflow.sqlite3，文档、终态、事件、结果与日志均和正式 HTTP 响应一致')

  await wait(400)
  const cloakDuring = [...cloakProcessesObservedDuringRun]
  const cloakAfter = cloakProcesses(userData)
  assert.deepEqual(cloakDuring, [])
  assert.deepEqual(cloakAfter, [])
  assert.deepEqual(await installedKernels(), [basename(sourceKernel)])
  checkpoint('requiresBrowser=false 的纯数据链运行前、运行中和完成后均无 CloakBrowser；运行槽已释放且 sidecar 清理完成')

  await capture(studio, join(evidenceDir, 'completed.png'))
  const sourceFileHashes = Object.fromEntries(await Promise.all([...frozenFiles, ...targetFiles].map(async file => [file, await fileHash(join(root, file))])))
  const targetSourceDirtyFiles = execFileSync('git', ['diff', '--name-only', gitHead, '--', ...targetFiles], { cwd: root, encoding: 'utf8' }).trim().split('\n').filter(Boolean)
  const uiNodes = approvedTypes.map(type => {
    const index = executedTypes.indexOf(type)
    const sourceFile = Object.entries(sourceFamilies).find(([, types]) => types.includes(type))?.[0]
    if (index === -1) return { moduleType: type, sourceFile, status: 'not-executed-through-ui' }
    const nodeId = nodeIds[index]
    return {
      moduleType: type, sourceFile, label: modules[index].label, status: 'executed-through-ui', nodeId,
      config: modules[index].expected, result: values[type],
      logs: logs.items.filter(item => item.nodeId === nodeId).map(item => item.message),
    }
  })
  const report = {
    evidenceId: 'BE-B4-advanced-data-formal-electron', checkedAt: new Date().toISOString(),
    gitHead, buildSha256: await buildHash(), workflowId: saved.id, profileId: profile.id, runId,
    result: 'passed', checks, platform: `${process.platform}-${process.arch}`, entry: 'development-build',
    workflowPersistence: { revision: saved.revision, nodeCount: saved.nodes.length, edgeCount: saved.edges.length, variables: saved.variables },
    execution: { status: terminalRun.status, cleanupState: sqlite.run[0].cleanupState, resultCount: results.items.length, logCount: logs.items.length, observedEvents },
    sourceFamilies, sourceFileHashes, targetSourceDirtyFiles, approvedFamilySize: approvedTypes.length,
    uiExecutedTypes: approvedExecutedTypes, supportTypes: modules.filter(module => module.support).map(module => module.type), notUiExecutedTypes, uiNodes, httpEvidence: { results: results.items, logs: logs.items }, sqliteEvidence: sqlite,
    requiresBrowserEvidence: browserRequirement,
    browserEvidence: { installedKernelEntries: [basename(sourceKernel)], cloakBrowserProcessesBefore: cloakBefore, cloakBrowserProcessesDuring: cloakDuring, cloakBrowserProcessesAfter: cloakAfter },
    workflowDataFlow: 'string_split.base_list → list/dict advanced operations → csv_parse/csv_generate → list_to_string_advanced.summary_text_ui',
    boundaries: {
      workspace: 'ephemeral', userDatabaseTouched: false, browserLaunch: 'none (pure data)',
      interaction: 'CDP mouse and keyboard through the main window and formal Studio UI; public sidecar APIs used only for Profile setup and evidence reads; SQLite used only for evidence reads; no Store or page-internal function access',
      claim: `${approvedExecutedTypes.length} of ${approvedTypes.length} approved advanced-data nodes executed through the formal UI; ${modules.length - approvedTypes.length} already-approved base nodes prepared typed inputs`,
    },
  }
  await writeFile(join(evidenceDir, 'result.json'), JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({ evidenceDir, ...report }, null, 2))
} catch (error) {
  await writeFile(join(evidenceDir, 'blocked.json'), JSON.stringify({
    checkedAt: new Date().toISOString(), gitHead, checks, observedEvents,
    executedTypes, approvedExecutedTypes, notUiExecutedTypes, error: error instanceof Error ? error.stack : String(error),
  }, null, 2) + '\n')
  throw error
} finally {
  eventAbort?.abort(); studio?.close(); main?.close(); await stop(desktop?.child)
  await rm(userData, { recursive: true, force: true })
}

function checkpoint(message) { checks.push(message); console.log(message) }

function rawResultData(values) {
  return values && Object.keys(values).length === 1 && Object.hasOwn(values, 'value') ? values.value : values
}

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
  for (let step = 0; step < (selection.target - selection.current + selection.count) % selection.count; step++) {
    await press(cdp, 'ArrowDown', { code: 'ArrowDown', keyCode: 40 })
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
  const target = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__pane');if(!e)return null;const r=e.getBoundingClientRect(),ys=[.18+${JSON.stringify(index)}*.12,.25,.4,.55,.7],xs=[.38,.55,.7,.25];for(const yf of ys)for(const xf of xs){const x=r.x+r.width*xf,y=r.y+r.height*Math.min(yf,.78);if(document.elementFromPoint(x,y)===e)return{x,y}}return null})()`, 'unobscured workflow canvas')
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
    await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', x: points.a.x + (points.b.x - points.a.x) * step / 12, y: points.a.y + (points.b.y - points.a.y) * step / 12, button: 'left', buttons: 1 })
    await wait(12)
  }
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...points.b, button: 'left', buttons: 0, clickCount: 1 })
  await wait(120)
}

async function moveNode(cdp, nodeId, index, count) {
  const pane = await cdp.evaluate(`(()=>{const r=document.querySelector('.react-flow__pane').getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height}})()`)
  const from = await waitFor(cdp, `(()=>{const e=document.querySelector('.react-flow__node[data-id=${JSON.stringify(nodeId)}]');if(!e)return null;const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2}})()`, `node position ${nodeId}`)
  const columns = count > 24 ? 4 : count > 8 ? 3 : 1
  const rows = Math.ceil(count / columns)
  const column = index % columns
  const row = Math.floor(index / columns)
  const to = {
    x: pane.x + pane.width * (.08 + column * (.84 / Math.max(1, columns - 1))),
    y: pane.y + 220 + row * ((pane.height - 440) / Math.max(1, rows - 1)),
  }
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', ...from })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...from, button: 'left', buttons: 1, clickCount: 1 })
  for (let step = 1; step <= 10; step++) await cdp.command('Input.dispatchMouseEvent', { type: 'mouseMoved', x: from.x + (to.x - from.x) * step / 10, y: from.y + (to.y - from.y) * step / 10, button: 'left', buttons: 1 })
  await cdp.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...to, button: 'left', buttons: 0, clickCount: 1 })
  await wait(100)
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
