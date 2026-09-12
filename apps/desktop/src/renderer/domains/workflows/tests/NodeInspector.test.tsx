import '@testing-library/jest-dom/vitest'
import { useState } from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { WorkflowIssue, WorkflowNode } from '../types'
import { NodeInspector } from '../components/NodeInspector'

afterEach(cleanup)

const node = (type: WorkflowNode['type'], config: Record<string, unknown> = {}): WorkflowNode => ({ id: 'node-1', type, label: '步骤', config: { timeoutSeconds: 60, ...config } })

function Harness({ initial, issues = [] }: { initial: WorkflowNode; issues?: WorkflowIssue[] }) {
  const [current, setCurrent] = useState(initial)
  return <><NodeInspector node={current} variables={[{ name: 'target', type: 'string', value: 'test' }]} issues={issues} onChange={(patch) => setCurrent((old) => ({ ...old, config: { ...old.config, ...patch } }))} onLabelChange={(label) => setCurrent((old) => ({ ...old, label }))} /><output data-testid="config">{JSON.stringify(current.config)}</output></>
}

it.each([
  ['open_page', { url: '', openMode: 'new_tab', waitUntil: 'load' }, ['网页地址', '打开方式', '页面就绪条件']],
  ['click_element', { selector: '', clickType: 'single', followNewTab: false }, ['元素选择器', '点击方式', '跟随新标签页']],
  ['input_text', { selector: '', text: '', clearBefore: true }, ['元素选择器', '输入文本', '输入前清空']],
  ['wait_element', { selector: '', waitCondition: 'visible' }, ['元素选择器', '等待条件']],
  ['get_element_info', { selector: '', attribute: 'text', variableName: 'element_value' }, ['元素选择器', '提取内容', '输出变量']],
  ['screenshot', { screenshotType: 'fullpage', savePath: '', variableName: 'screenshot_path' }, ['截图范围', '保存路径', '输出变量']],
] as const)('renders the explicit %s configuration without execution controls', (type, config, labels) => {
  render(<Harness initial={node(type, config)} />)
  for (const label of labels) expect(screen.getByLabelText(label)).toBeInTheDocument()
  expect(screen.getByLabelText('超时（秒）')).toHaveValue(60)
  expect(screen.queryByRole('button', { name: /运行|录制|调试/ })).not.toBeInTheDocument()
})

it('keeps element screenshot selection incomplete and preserves its selector between modes', async () => {
  const user = userEvent.setup()
  render(<Harness initial={node('screenshot', { screenshotType: 'fullpage', selector: '', savePath: '', variableName: 'shot' })} />)
  expect(screen.queryByLabelText('元素选择器')).not.toBeInTheDocument()
  await user.selectOptions(screen.getByLabelText('截图范围'), 'element')
  expect(screen.getByLabelText('元素选择器')).toHaveValue('')
  expect(screen.getByTestId('config')).toHaveTextContent('"screenshotType":"element"')
  await user.type(screen.getByLabelText('元素选择器'), 'xpath=//main')
  await user.selectOptions(screen.getByLabelText('截图范围'), 'viewport')
  await user.selectOptions(screen.getByLabelText('截图范围'), 'element')
  expect(screen.getByLabelText('元素选择器')).toHaveValue('xpath=//main')
})

it('inserts a literal variable reference at the selected text range', async () => {
  const user = userEvent.setup()
  render(<Harness initial={node('input_text', { selector: '#search', text: 'hello world', clearBefore: true })} />)
  expect(screen.getByRole('button', { name: '插入变量引用' })).toBeDisabled()
  const input = screen.getByLabelText('输入文本') as HTMLTextAreaElement
  await user.click(input)
  input.setSelectionRange(6, 11)
  fireEvent.select(input)
  await user.click(screen.getByRole('button', { name: '插入变量引用' }))
  await user.click(screen.getByRole('menuitem', { name: '${target}' }))
  await waitFor(() => expect(screen.getByLabelText('输入文本')).toHaveValue('hello ${target}'))
  expect(screen.getByLabelText('元素选择器')).toHaveValue('#search')
})

it('associates node issues with their fields and never fills missing defaults on mount', () => {
  const onChange = vi.fn()
  render(<NodeInspector node={{ ...node('get_element_info'), config: {} }} variables={[]} issues={[
    { nodeId: 'node-1', path: ['config', 'selector'], code: 'REQUIRED', message: '请填写选择器' },
    { nodeId: 'node-1', path: ['config', 'variableName'], code: 'DUPLICATE_OUTPUT', message: '输出变量重复' },
    { nodeId: 'other', path: ['config', 'selector'], code: 'REQUIRED', message: '其他节点的问题' },
  ]} onChange={onChange} onLabelChange={vi.fn()} />)
  expect(screen.getByLabelText('元素选择器')).toHaveAttribute('aria-invalid', 'true')
  expect(screen.getByLabelText('输出变量')).toHaveAccessibleDescription('输出变量重复')
  expect(screen.queryByText('其他节点的问题')).not.toBeInTheDocument()
  expect(screen.getByLabelText('超时（秒）')).toHaveValue(null)
  expect(onChange).not.toHaveBeenCalled()
})

it('groups text focus sessions and keeps empty text and timeout changes explicit', async () => {
  const user = userEvent.setup()
  const start = vi.fn()
  const end = vi.fn()
  const change = vi.fn()
  render(<NodeInspector node={node('input_text', { text: 'old', selector: '' })} variables={[]} issues={[]} onChange={change} onLabelChange={vi.fn()} onEditStart={start} onEditEnd={end} />)
  await user.clear(screen.getByLabelText('输入文本'))
  expect(change).toHaveBeenCalledWith({ text: '' })
  await user.tab()
  expect(start).toHaveBeenCalled()
  expect(end).toHaveBeenCalled()
  fireEvent.change(screen.getByLabelText('超时（秒）'), { target: { value: '1.5' } })
  expect(change).toHaveBeenCalledWith({ timeoutSeconds: 1.5 })
})
