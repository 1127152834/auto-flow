import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value),
    removeItem: (key: string) => data.delete(key),
  })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})

import { ConfigPanel } from '../components/ConfigPanel'
import { localWorkflowApi, workflowApi } from '../api'
import { useWorkflowStore as store } from '../editor-store'
import { useGlobalConfigStore as globalConfig } from '../hooks/stores/globalConfigStore'
import type { ModuleType } from '../types/workflow'

const originalScroll = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollIntoView')
const initialGlobalConfig = structuredClone(globalConfig.getState().config)

beforeEach(() => {
  store.getState().clearWorkflow()
  globalConfig.setState({ config: structuredClone(initialGlobalConfig) })
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: vi.fn() })
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  globalConfig.setState({ config: structuredClone(initialGlobalConfig) })
  if (originalScroll) Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', originalScroll)
  else Reflect.deleteProperty(HTMLElement.prototype, 'scrollIntoView')
})

function open(type: ModuleType, data: Record<string, unknown> = {}) {
  store.getState().addNode(type, { x: 120, y: 240 }, data)
  const id = store.getState().nodes.at(-1)!.id
  const view = render(<ConfigPanel selectedNodeId={id} />)
  return { id, ...view }
}

function nodeData(id: string) {
  return store.getState().nodes.find((node) => node.id === id)!.data
}

function choose(label: string | undefined, option: string, current?: string) {
  const trigger = label
    ? screen.getByRole('combobox', { name: label })
    : screen.getAllByRole('combobox').find((item) => !current || item.textContent?.includes(current))
  expect(trigger).toBeDefined()
  fireEvent.keyDown(trigger!, { key: 'ArrowDown' })
  fireEvent.click(screen.getByRole('option', { name: option }))
}

it('NODE.inject_javascript.conditional-ui: switches the target controls and result semantics', () => {
  const { id } = open('inject_javascript')
  expect(screen.queryByPlaceholderText('URL关键词')).toBeNull()
  choose('注入模式', 'URL匹配')
  expect(screen.getByPlaceholderText('URL关键词')).toBeDefined()
  expect(screen.getByText('所有标签页的返回值将以数组形式保存到此变量')).toBeDefined()
  choose('注入模式', '指定索引')
  expect(screen.getByText('标签页索引')).toBeDefined()
  expect(screen.getByText('脚本的返回值将保存到此变量')).toBeDefined()
  expect(nodeData(id)).toMatchObject({ injectMode: 'index' })
})

it('NODE.download_file.conditional-ui: swaps selector and direct URL without losing the chosen mode', () => {
  const { id } = open('download_file')
  expect(screen.getByText('触发元素选择器')).toBeDefined()
  choose('下载方式', '直接URL下载')
  expect(screen.queryByText('触发元素选择器')).toBeNull()
  expect(screen.getByPlaceholderText('https://example.com/file.zip，支持 {变量名}')).toBeDefined()
  expect(nodeData(id).downloadMode).toBe('url')
})

it.each([
  ['browser', '浏览器抓包', '模糊匹配URL', '过滤类型'],
  ['system', '全局系统抓包', '模糊匹配IP/进程名', '目标进程名（可选）'],
  ['proxy', '代理抓包（模拟器/手机）', '模糊匹配URL，如: .m3u8', '代理端口'],
] as const)('NODE.network_capture.conditional-ui: renders %s mode fields', (mode, option, placeholder, marker) => {
  const { id } = open('network_capture', { captureMode: mode === 'browser' ? 'system' : 'browser' })
  choose('抓包模式', option)
  expect(screen.getByPlaceholderText(placeholder)).toBeDefined()
  expect(screen.getByText(marker)).toBeDefined()
  expect(nodeData(id).captureMode).toBe(mode)
})

it('NODE.set_clipboard.conditional-ui: swaps literal text and image picker branches', () => {
  const { id } = open('set_clipboard')
  expect(screen.getByText('文本内容')).toBeDefined()
  choose('内容类型', '图片')
  expect(screen.queryByText('文本内容')).toBeNull()
  expect(screen.getByText('图片路径')).toBeDefined()
  expect(nodeData(id).contentType).toBe('image')
})

it('NODE.scheduled_task.conditional-ui: switches date-time and delay inputs', () => {
  const { id } = open('scheduled_task')
  expect(screen.getByPlaceholderText('YYYY-MM-DD，如 2026-01-01')).toBeDefined()
  choose('定时方式', '延迟一段时间后执行')
  expect(screen.queryByPlaceholderText('YYYY-MM-DD，如 2026-01-01')).toBeNull()
  expect(screen.getByText('小时')).toBeDefined()
  expect(screen.getByText('分钟')).toBeDefined()
  expect(screen.getByText('秒')).toBeDefined()
  expect(nodeData(id).scheduleType).toBe('delay')
})

it('NODE.condition.conditional-ui: switches logic arity and element locator branches', () => {
  const { id } = open('condition')
  choose('判断类型', '逻辑运算（与/或/非）')
  expect(screen.getByText('条件1')).toBeDefined()
  expect(screen.getByText('条件2')).toBeDefined()
  choose('逻辑运算符', '非（NOT）—— 对条件取反')
  expect(screen.queryByText('条件1')).toBeNull()
  expect(screen.getByText('条件')).toBeDefined()
  choose('判断类型', '元素存在判断')
  expect(screen.getByText('元素选择器')).toBeDefined()
  expect(nodeData(id)).toMatchObject({ conditionType: 'element_exists', logicOperator: 'not' })
})

it('NODE.assert_checkpoint.conditional-ui: switches regex, page element and expected text branches', () => {
  const { id } = open('assert_checkpoint')
  choose('运算符', '匹配正则')
  expect(screen.getByPlaceholderText('正则表达式，如 ^\\d+$')).toBeDefined()
  choose('检查类型', '页面元素状态')
  expect(screen.getByText('元素选择器')).toBeDefined()
  expect(screen.queryByText('期望文本')).toBeNull()
  choose('元素检查', '文本包含')
  expect(screen.getByText('期望文本')).toBeDefined()
  expect(nodeData(id)).toMatchObject({ checkType: 'element', elementCheck: 'text_contains' })
})

it('NODE.input_prompt.conditional-ui: exposes checkbox, option and slider-specific inputs', () => {
  const { id } = open('input_prompt')
  choose('输入模式', '复选框')
  expect(screen.getByRole('checkbox', { name: /默认选中/ })).toBeDefined()
  choose('输入模式', '单选下拉')
  expect(screen.getByText('选项列表')).toBeDefined()
  choose('输入模式', '整数滑块')
  expect(screen.getAllByPlaceholderText('滑块必填')).toHaveLength(2)
  expect(screen.getByText('滑块模式下必须设置最小值和最大值')).toBeDefined()
  expect(nodeData(id).inputMode).toBe('slider_int')
})

it('NODE.subflow.conditional-ui: lists group and header definitions and stores stable identity plus display name', () => {
  const groupId = 'group-definition'
  const headerId = 'header-definition'
  const id = 'subflow-call'
  store.getState().loadWorkflow({
    name: '子流程选择',
    nodes: [
      { id: groupId, type: 'groupNode', position: { x: 0, y: 0 }, data: { moduleType: 'group', label: '分组子流程', isSubflow: true, subflowName: '分组子流程' } },
      { id: headerId, type: 'subflowHeaderNode', position: { x: 0, y: 200 }, data: { moduleType: 'subflow_header', label: '函数子流程', subflowName: '函数子流程' } },
      { id, type: 'moduleNode', position: { x: 300, y: 0 }, data: { moduleType: 'subflow', label: '调用子流程' } },
    ],
    edges: [],
  })
  render(<ConfigPanel selectedNodeId={id} />)
  choose('选择子流程', '[分组] 分组子流程')
  expect(nodeData(id)).toMatchObject({ subflowGroupId: groupId, subflowName: '分组子流程' })
  choose('选择子流程', '[函数头] 函数子流程')
  expect(nodeData(id)).toMatchObject({ subflowGroupId: headerId, subflowName: '函数子流程' })
})

it('NODE.subflow_header.entry: creates a callable header from both canvas entry points', () => {
  store.getState().addNode('subflow_header', { x: 0, y: 0 }, { subflowName: '画布函数' })
  store.getState().blockInsertNode(null, 'subflow_header', { subflowName: '模块条函数' })
  const [canvasHeader, blockHeader] = store.getState().nodes
  expect(canvasHeader.type).toBe('subflowHeaderNode')
  expect(blockHeader.type).toBe('subflowHeaderNode')

  const { id } = open('subflow')
  choose('选择子流程', '[函数头] 画布函数')
  expect(nodeData(id)).toMatchObject({ subflowGroupId: canvasHeader.id, subflowName: '画布函数' })
  choose('选择子流程', '[函数头] 模块条函数')
  expect(nodeData(id)).toMatchObject({ subflowGroupId: blockHeader.id, subflowName: '模块条函数' })
})

it('NODE.run_workflow_file.conditional-ui: loads choices and hides dependent result controls when not waiting', async () => {
  vi.spyOn(localWorkflowApi, 'list').mockResolvedValue({
    success: true,
    data: { workflows: [{ filename: '采集.json', name: '采集流程' }] },
  } as Awaited<ReturnType<typeof localWorkflowApi.list>>)
  const { id } = open('run_workflow_file')
  await waitFor(() => expect(screen.getAllByRole('combobox').some((item) => item.textContent?.includes('从当前工作流文件夹选择'))).toBe(true))
  choose(undefined, '采集流程', '从当前工作流文件夹选择')
  expect(nodeData(id).workflowFile).toBe('采集.json')
  expect(screen.getByText('回收它产生的变量')).toBeDefined()
  fireEvent.click(screen.getByRole('switch', { name: '等待其执行完成' }))
  expect(screen.queryByText('回收它产生的变量')).toBeNull()
  expect(screen.queryByText('它失败时中断当前工作流')).toBeNull()
  expect(nodeData(id).waitComplete).toBe(false)
})

it('NODE.run_workflow_file.project: selects only project workflows by stable id', async () => {
  window.history.replaceState({}, '', '/studio.html?projectId=project-a')
  const local = vi.spyOn(localWorkflowApi, 'list')
  vi.spyOn(workflowApi, 'list').mockResolvedValue({
    success: true,
    data: [{ id: 'child-a', name: '项目子流程' }],
  } as Awaited<ReturnType<typeof workflowApi.list>>)
  try {
    const { id } = open('run_workflow_file')
    await waitFor(() => expect(workflowApi.list).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('combobox', { name: '要运行的工作流' }))
    fireEvent.click(await screen.findByRole('option', { name: '项目子流程' }))
    expect(nodeData(id).workflowFile).toBe('child-a')
    expect(local).not.toHaveBeenCalled()
  } finally {
    window.history.replaceState({}, '', '/studio.html')
  }
})

it('NODE.string_replace.conditional-ui: changes the search contract for regular expressions', () => {
  const { id } = open('string_replace')
  expect(screen.getByText('查找内容')).toBeDefined()
  choose('替换模式', '正则表达式替换')
  expect(screen.getByText('正则表达式')).toBeDefined()
  expect(screen.getByPlaceholderText('正则表达式，如: \\d+')).toBeDefined()
  expect(nodeData(id).replaceMode).toBe('regex')
})

it.each([
  ['', ''],
  ['{limit}', '{limit}'],
  ['12', 12],
] as const)('NODE.string_split.conditional-ui: preserves maxSplit input %s as %s', (value, expected) => {
  const { id } = open('string_split', { maxSplit: 5 })
  fireEvent.change(screen.getByPlaceholderText('留空表示不限制，支持 {变量名}'), { target: { value } })
  expect(nodeData(id).maxSplit).toBe(expected)
})

it.each([
  ['', ''],
  ['{distance}', '{distance}'],
  ['240', 240],
] as const)('NODE.slider_captcha.conditional-ui: preserves targetDistance input %s as %s', (value, expected) => {
  const { id } = open('slider_captcha', { targetDistance: 100 })
  fireEvent.change(screen.getByPlaceholderText('滑动像素距离，支持 {变量名}'), { target: { value } })
  expect(nodeData(id).targetDistance).toBe(expected)
})

it('NODE.ocr_captcha.source-contract: exposes optional fill and submit branches from the frozen executor', () => {
  const { id } = open('ocr_captcha')
  expect(screen.getByText('验证码输入框选择器（可选）')).toBeDefined()
  expect(screen.getByRole('checkbox', { name: '识别后自动提交' })).toBeDefined()
  expect(screen.queryByText('提交按钮选择器')).toBeNull()
  expect(nodeData(id).variableName).toBe('captcha_text')
  fireEvent.click(screen.getByRole('checkbox', { name: '识别后自动提交' }))
  expect(screen.getByText('提交按钮选择器')).toBeDefined()
  expect(nodeData(id).autoSubmit).toBe(true)
})

it('NODE.slider_captcha.source-contract: exposes the background and gap selectors used by automatic matching', () => {
  open('slider_captcha')
  expect(screen.getByText('背景图片选择器（可选）')).toBeDefined()
  expect(screen.getByText('缺口图片选择器（可选）')).toBeDefined()
  expect(screen.queryByText('滑轨选择器')).toBeNull()
})

it.each([
  ['append', '追加元素', true, false, false],
  ['insert', '插入元素', true, true, false],
  ['remove', '删除元素', true, false, false],
  ['pop', '弹出元素', false, true, true],
  ['clear', '清空列表', false, false, false],
] as const)('NODE.list_operation.conditional-ui: exposes only fields used by %s', (action, option, value, index, result) => {
  const { id } = open('list_operation', { listAction: action === 'append' ? 'clear' : 'append' })
  choose('操作类型', option)
  expect(screen.queryByText('操作值') !== null).toBe(value)
  expect(screen.queryByText('索引位置') !== null).toBe(index)
  expect(screen.queryByText('存储弹出值到变量') !== null).toBe(result)
  expect(nodeData(id).listAction).toBe(action)
})

it.each([
  ['ai_extract', '要抽取的字段'],
  ['ai_classify', '候选类别'],
  ['ai_summarize', '摘要最大字数'],
  ['ai_translate', '目标语言'],
  ['ai_sentiment', '存储到变量'],
  ['ai_normalize', '规整类型'],
  ['ai_route', '分支选项'],
] as const)('NODE.%s.conditional-ui: mounts its dedicated AI task branch', (type, marker) => {
  open(type as ModuleType)
  expect(screen.getByText('输入文本')).toBeDefined()
  expect(screen.getByText(marker)).toBeDefined()
  expect(screen.queryByText('待去重列表')).toBeNull()
})

it('NODE.ai_dedup_semantic.conditional-ui: uses a list input instead of the shared text input', () => {
  open('ai_dedup_semantic')
  expect(screen.getByText('待去重列表')).toBeDefined()
  expect(screen.queryByText('输入文本')).toBeNull()
})

it.each(['ai_smart_scraper', 'ai_element_selector'] as const)('NODE.%s.conditional-ui: consumes only main-app managed models', async (type) => {
  open(type)
  expect(await screen.findByText('主应用模型')).toBeDefined()
  expect(screen.queryByText('API地址')).toBeNull()
  expect(screen.queryByText('API Key')).toBeNull()
  expect(screen.queryByText('Azure Endpoint')).toBeNull()
})

it('NODE.firecrawl_scrape.conditional-ui: labels waitFor with its source selector semantics', () => {
  open('firecrawl_scrape')
  expect(screen.getByText('等待选择器 (可选)')).toBeDefined()
  expect(screen.getByPlaceholderText('#content-ready，最多等待 5 秒')).toBeDefined()
})

it.each([
  ['firecrawl_scrape', ['Markdown', 'HTML', 'Screenshot']],
  ['firecrawl_crawl', ['Markdown', 'HTML']],
] as const)('NODE.%s.conditional-ui: each returned format toggles the document array', (type, formats) => {
  const { id } = open(type as ModuleType, { formats: [] })
  for (const format of formats) fireEvent.click(screen.getByRole('checkbox', { name: format }))
  expect(nodeData(id).formats).toEqual(formats.map((format) => format.toLowerCase()))
  fireEvent.click(screen.getByRole('checkbox', { name: formats[0] }))
  expect(nodeData(id).formats).toEqual(formats.slice(1).map((format) => format.toLowerCase()))
})

it('NODE.image_ocr.conditional-ui: switches file and region controls and describes recognition type', () => {
  const { id } = open('image_ocr')
  expect(screen.getByText('图片路径')).toBeDefined()
  choose('识别模式', '屏幕区域')
  expect(screen.getByText('起点坐标（左上角）')).toBeDefined()
  expect(screen.getByText('终点坐标（右下角）')).toBeDefined()
  choose('识别类型', '验证码（单行短文本）')
  expect(screen.getByText(/验证码模式：直接识别整张图/)).toBeDefined()
  expect(nodeData(id)).toMatchObject({ ocrMode: 'region', ocrType: 'captcha' })
})

it('NODE.timestamp_converter.conditional-ui: changes the input contract with the conversion direction', () => {
  const { id } = open('timestamp_converter')
  expect(screen.getByPlaceholderText('2024-01-01 12:00:00 (留空=当前时间)')).toBeDefined()
  choose(undefined, '时间戳 → 日期时间', '日期时间 → 时间戳')
  expect(screen.getByPlaceholderText('1704096000')).toBeDefined()
  expect(nodeData(id).operation).toBe('to_datetime')
})

it('NODE.python_script.conditional-ui: switches the inline editor to a file path', () => {
  const { id } = open('python_script')
  expect(screen.getByText('Python代码')).toBeDefined()
  choose(undefined, '从文件读取', '直接输入代码')
  expect(screen.queryByText('Python代码')).toBeNull()
  expect(screen.getByText('脚本文件路径')).toBeDefined()
  expect(nodeData(id).scriptMode).toBe('file')
})

it('NODE.webhook_trigger.conditional-ui: generates a stable URL and reports clipboard application', async () => {
  const writeText = vi.fn().mockResolvedValue(undefined)
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
  const { id } = open('webhook_trigger')
  const webhookId = String(nodeData(id).webhookId)
  expect(webhookId).toMatch(/^webhook_/)
  fireEvent.click(screen.getByTitle('复制URL'))
  expect(writeText).toHaveBeenCalledWith(expect.stringContaining(`/api/triggers/webhook/${webhookId}`))
  expect(screen.getByText('已复制到剪贴板')).toBeDefined()
  await act(async () => {})
})

it('NODE.file_watcher_trigger.conditional-ui: hydrates an empty node from the shared file setting', async () => {
  globalConfig.getState().updateFileTriggerConfig({ defaultWatchPath: '/fixture/watch' })
  const { id } = open('file_watcher_trigger')
  await waitFor(() => expect(nodeData(id).watchPath).toBe('/fixture/watch'))
})

it('NODE.email_trigger.conditional-ui: atomically hydrates all empty connection defaults', async () => {
  globalConfig.getState().updateEmailTriggerConfig({ imapServer: 'imap.fixture.invalid', imapPort: 1993, emailAccount: 'fixture@example.invalid', emailPassword: 'fixture-only', checkInterval: 45 })
  const { id } = open('email_trigger')
  await waitFor(() => expect(nodeData(id)).toMatchObject({ emailServer: 'imap.fixture.invalid', emailPort: 1993, emailAccount: 'fixture@example.invalid', emailPassword: 'fixture-only', checkInterval: 45 }))
})

it('NODE.api_trigger.conditional-ui: hydrates defaults and exposes the POST request body', async () => {
  globalConfig.getState().updateApiTriggerConfig({ defaultHeaders: '{"X-Fixture":"yes"}', checkInterval: 15 })
  const { id } = open('api_trigger')
  await waitFor(() => expect(nodeData(id)).toMatchObject({ headers: '{"X-Fixture":"yes"}', checkInterval: 15 }))
  choose('HTTP方法', 'POST')
  expect(screen.getByText('请求体（JSON格式）')).toBeDefined()
})

it.each([
  ['ai_generate_image', { imageApiKey: 'image-key', imageApiBase: 'https://image.fixture.invalid' }],
  ['ai_generate_video', { videoApiKey: 'video-key', videoApiBase: 'https://video.fixture.invalid' }],
] as const)('NODE.%s.conditional-ui: ignores legacy media secrets and uses the main model service', async (type, globalValues) => {
  globalConfig.getState().updateAIConfig(globalValues)
  const { id } = open(type)
  expect(screen.getByText('主应用模型')).toBeDefined()
  await waitFor(() => expect(nodeData(id).apiKey).toBeUndefined())
  expect(nodeData(id).apiBase).toBeUndefined()
  expect(screen.getByText('接口协议')).toBeDefined()
})

it('NODE.ssh_connect.conditional-ui: hydrates host identity without overriding explicit node values', async () => {
  globalConfig.setState((state) => ({ config: { ...state.config, ssh: { host: 'ssh.fixture.invalid', port: 2222, username: 'fixture-user' } } }))
  const { id } = open('ssh_connect', { host: 'node.fixture.invalid' })
  await waitFor(() => expect(nodeData(id)).toMatchObject({ host: 'node.fixture.invalid', port: 2222, username: 'fixture-user' }))
})
