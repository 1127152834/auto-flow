import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { choiceTestEnvironment } from '../../../shared/testing/choice-user'
import type { AutomationWrite } from '../types'
import { AutomationEditor, type AutomationEditorProps } from './AutomationEditor'

choiceTestEnvironment()
afterEach(cleanup)

const initial: AutomationWrite = {
  name: '资料整理', description: '将采集内容整理为可维护的资料记录', workflowId: 'workflow-a', inputPlan: { inputs: [] },
  parameterSchema: [
    { parameterId: 'parameter-zero', name: '数量', type: 'number', required: false, defaultValue: 0 },
    { parameterId: 'parameter-false', name: '启用', type: 'boolean', required: false, defaultValue: false },
    { parameterId: 'parameter-omitted', name: '备注', type: 'string', required: false },
  ],
  environmentPolicy: { source: 'newFromProfile' },
  runPolicy: { maxTasks: 10, concurrency: 1, maxLiveInstances: 1, continueAfterFailure: false, automaticExecutionTimeoutSeconds: 900, manualDeadlineSeconds: 900 },
}

const props = (overrides: Partial<AutomationEditorProps> = {}): AutomationEditorProps => ({
  initialValue: initial,
  resetKey: 'one',
  workflowOptions: [{ id: 'workflow-a', name: '资料整理流程', runnable: true }],
  environmentOptions: { profiles: [], proxies: [], pools: [] },
  renderInputPlan: (_value, _onChange, disabled) => <section aria-label="项目数据输入" data-disabled={disabled}>当前自动化不读取项目数据</section>,
  onSubmit: vi.fn(),
  onCancel: vi.fn(),
  ...overrides,
})

it('matches the four-tab prototype structure and renders only authorized actions', () => {
  render(<AutomationEditor {...props({ onOpenStudio: vi.fn() })}/>)
  expect(screen.getByRole('heading', { name: '资料整理' })).toBeVisible()
  expect(screen.getByRole('tablist', { name: '自动化配置页签' })).toBeVisible()
  expect(screen.getAllByRole('tab').map(tab => tab.textContent)).toEqual(['基本信息', '输入与参数', '资源与环境', '运行设置'])
  expect(screen.getByLabelText('自动化名称')).toBeVisible()
  expect(screen.getByText('关联建立后不能通过普通编辑替换工作流')).toBeVisible()
  expect(screen.getAllByRole('button', { name: '打开 Studio' })).toHaveLength(2)
  expect(screen.queryByRole('button', { name: '启动运行' })).not.toBeInTheDocument()
  expect(screen.getAllByText('最多 10 个任务')).toHaveLength(2)
})

it('keeps one unsaved draft across tabs and never submits on tab changes', async () => {
  const onSubmit = vi.fn(), onDraftStateChange = vi.fn(), user = userEvent.setup()
  render(<AutomationEditor {...props({ onSubmit, onDraftStateChange })}/>)
  await user.clear(screen.getByLabelText('自动化名称'))
  await user.type(screen.getByLabelText('自动化名称'), '新的名称')
  await user.click(screen.getByRole('tab', { name: /运行设置/ }))
  fireEvent.change(screen.getByLabelText('单任务超时（分钟）'), { target: { value: 'bad' } })
  await user.click(screen.getByRole('tab', { name: '基本信息' }))
  await user.click(screen.getByRole('tab', { name: /运行设置/ }))
  expect(screen.getByLabelText('单任务超时（分钟）')).toHaveValue('bad')
  expect(onSubmit).not.toHaveBeenCalled()
  expect(onDraftStateChange).toHaveBeenLastCalledWith({ dirty: true, valid: false })
  expect(screen.getByRole('button', { name: '保存配置' })).toBeEnabled()
})

it('submits one normalized aggregate and preserves omitted false and zero defaults', async () => {
  const onSubmit = vi.fn(), user = userEvent.setup()
  render(<AutomationEditor {...props({ onSubmit })}/>)
  await user.clear(screen.getByLabelText('自动化名称'))
  await user.type(screen.getByLabelText('自动化名称'), '  新名称  ')
  await user.click(screen.getByRole('button', { name: '保存配置' }))
  await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
  const submitted = onSubmit.mock.calls[0][0] as AutomationWrite
  expect(submitted.name).toBe('新名称')
  expect(submitted.parameterSchema[0].defaultValue).toBe(0)
  expect(submitted.parameterSchema[1].defaultValue).toBe(false)
  expect(Object.hasOwn(submitted.parameterSchema[2], 'defaultValue')).toBe(false)
})

it('resets only when resetKey changes and reports the clean RHF state', async () => {
  const onDraftStateChange = vi.fn(), p = props({ onDraftStateChange }), user = userEvent.setup()
  const view = render(<AutomationEditor {...p}/>)
  await user.clear(screen.getByLabelText('自动化名称'))
  await user.type(screen.getByLabelText('自动化名称'), '本地草稿')
  view.rerender(<AutomationEditor {...p} initialValue={{ ...initial, name: '后台刷新' }}/>)
  expect(screen.getByLabelText('自动化名称')).toHaveValue('本地草稿')
  view.rerender(<AutomationEditor {...p} initialValue={{ ...initial, name: '明确重置' }} resetKey="two"/>)
  expect(screen.getByLabelText('自动化名称')).toHaveValue('明确重置')
  await waitFor(() => expect(onDraftStateChange).toHaveBeenLastCalledWith({ dirty: false, valid: true }))
})

it('freezes all editors while saving or recovering and prevents duplicate submission', async () => {
  const onSubmit = vi.fn(), user = userEvent.setup()
  const view = render(<AutomationEditor {...props({ onSubmit })}/>)
  await user.clear(screen.getByLabelText('自动化名称'))
  await user.type(screen.getByLabelText('自动化名称'), '待保存')
  view.rerender(<AutomationEditor {...props({ onSubmit, saving: true })}/>)
  expect(screen.getByLabelText('自动化名称')).toBeDisabled()
  expect(screen.getByRole('button', { name: '保存配置' })).toBeDisabled()
  expect(screen.getByLabelText('项目数据输入')).toHaveAttribute('data-disabled', 'true')
  await user.click(screen.getByRole('button', { name: '保存配置' }))
  expect(onSubmit).not.toHaveBeenCalled()
})

it('shows tab error badges and focuses the first invalid field on save', async () => {
  const user = userEvent.setup()
  render(<AutomationEditor {...props()}/>)
  await user.clear(screen.getByLabelText('自动化名称'))
  expect(screen.getByRole('tab', { name: /基本信息/ })).toHaveTextContent('1')
  await user.click(screen.getByRole('button', { name: '保存配置' }))
  await waitFor(() => expect(screen.getByLabelText('自动化名称')).toHaveFocus())
})

it('clears only the server error whose field value changed', async () => {
  const onSubmit = vi.fn(), user = userEvent.setup()
  render(<AutomationEditor {...props({ onSubmit, serverErrors: { name: '名称已存在', workflowId: '工作流冲突' } })}/>)
  expect(screen.getByText('名称已存在')).toBeVisible()
  await user.type(screen.getByLabelText('自动化名称'), ' 新')
  expect(screen.queryByText('名称已存在')).not.toBeInTheDocument()
  expect(screen.getByRole('tab', { name: /基本信息/ })).toHaveTextContent('1')
  await user.click(screen.getByRole('button', { name: '保存配置' }))
  expect(onSubmit).not.toHaveBeenCalled()
})

it('counts a raw run-policy error and returns to its invalid control on save', async () => {
  const user = userEvent.setup()
  render(<AutomationEditor {...props()}/>)
  await user.click(screen.getByRole('tab', { name: '运行设置' }))
  fireEvent.change(screen.getByLabelText('单任务超时（分钟）'), { target: { value: 'bad' } })
  await user.click(screen.getByRole('tab', { name: '基本信息' }))
  expect(screen.getByRole('tab', { name: /运行设置/ })).toHaveTextContent('1')
  await user.click(screen.getByRole('button', { name: '保存配置' }))
  await waitFor(() => expect(screen.getByLabelText('单任务超时（分钟）')).toHaveFocus())
  expect(screen.getByLabelText('单任务超时（分钟）')).toHaveValue('bad')
})

it('shows an unknown workflow validation state unless runnable is explicit', () => {
  const view = render(<AutomationEditor {...props({ workflowOptions: [] })}/>)
  expect(screen.getByText('未能读取校验状态')).toBeVisible()
  view.rerender(<AutomationEditor {...props({ workflowOptions: [{ id: 'workflow-a', name: '资料整理流程' }] })}/>)
  expect(screen.getByText('未能读取校验状态')).toBeVisible()
  expect(screen.queryByText('可以运行')).not.toBeInTheDocument()
})

it('uses a semantic option for an unavailable workflow without exposing its identity', async () => {
  const workflowId = '11111111-2222-4333-8444-555555555555'
  render(<AutomationEditor {...props({ isNew: true, workflowOptions: [], initialValue: { ...initial, workflowId } })}/>)
  const select = screen.getByRole('combobox', { name: '关联工作流' })
  expect(select).toHaveTextContent('关联工作流暂不可用')
  await userEvent.setup().click(select)
  expect(screen.getByRole('option', { name: '关联工作流暂不可用' })).toBeVisible()
  expect(document.body.textContent).not.toContain(workflowId)
  expect(select).not.toHaveAttribute('title', expect.stringContaining(workflowId))
})

it('passes current input aliases to the saved input environment presentation', async () => {
  const inputId = '11111111-2222-4333-8444-555555555555'
  const alias = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'
  const value: AutomationWrite = {
    ...initial,
    inputPlan: { inputs: [{ inputId, alias, tableId: 'table-a', datasetGeneration: 'generation-a', mode: 'independent', required: false, fieldBindings: [], filter: { type: 'and', children: [] }, orderBy: [] }] },
    environmentPolicy: { source: 'inputEnvironment', inputId },
  }
  render(<AutomationEditor {...props({ initialValue: value })}/>)
  await userEvent.setup().click(screen.getByRole('tab', { name: '资源与环境' }))
  expect(screen.getByText(alias)).toBeVisible()
  expect(document.body.textContent).not.toContain(inputId)
})

it('links shared text controls to stable help and error messages', async () => {
  const user = userEvent.setup()
  render(<AutomationEditor {...props()}/>)
  const name = screen.getByLabelText('自动化名称'), description = screen.getByLabelText('用途说明')
  expect(name).toHaveAccessibleDescription('1–80 个字符')
  expect(description).toHaveAttribute('data-af-control')
  expect(description).toHaveAccessibleDescription('最多 1000 个字符')
  await user.clear(name)
  expect(name).toHaveAccessibleDescription('自动化名称需要 1–80 个字符')
})

it('reports an unsaved new automation as not created', async () => {
  const user = userEvent.setup()
  render(<AutomationEditor {...props({ isNew: true })}/>)
  expect(screen.getByText(/尚未创建/)).toBeVisible()
  await user.type(screen.getByLabelText('自动化名称'), '新')
  expect(screen.getByText(/新增草稿/)).toBeVisible()
  expect(screen.queryByText(/配置已保存/)).not.toBeInTheDocument()
})

it('protects unapplied input query drafts from global save and focuses their panel', async () => {
  const p = props({ renderInputPlan: (_value, _onChange, _disabled, draft) => <button aria-invalid="true" onClick={() => draft.onDraftStateChange({ dirty: true, valid: false })}>尚未应用的输入筛选</button> })
  render(<AutomationEditor {...p}/>); const user = userEvent.setup()
  await user.click(screen.getByRole('tab', { name: '输入与参数' }))
  await user.click(screen.getByRole('button', { name: '尚未应用的输入筛选' }))
  await user.click(screen.getByRole('tab', { name: '基本信息' }))
  await user.click(screen.getByRole('button', { name: '保存配置' }))
  expect(p.onSubmit).not.toHaveBeenCalled()
  await waitFor(() => expect(screen.getByRole('button', { name: '尚未应用的输入筛选' })).toHaveFocus())
})

it('saves data concurrency and instance limits together and shows their minimum', async () => {
  const onSubmit = vi.fn()
  render(<AutomationEditor {...props({ onSubmit, initialValue: { ...initial, inputPlan: { inputs: [{ inputId: 'input', alias: '资料', tableId: 'table', datasetGeneration: 'generation', mode: 'independent', required: true, fieldBindings: [], filter: { type: 'all', items: [] }, orderBy: [] }] } } })}/>)
  await userEvent.click(screen.getByRole('tab', { name: '运行设置' }))
  fireEvent.change(screen.getByLabelText('请求并发数'), { target: { value: '4' } })
  fireEvent.change(screen.getByLabelText('最大活动实例'), { target: { value: '2' } })
  expect(screen.getByLabelText('配置摘要')).toHaveTextContent('配置并发上限 2')
  fireEvent.click(screen.getByRole('button', { name: '保存配置' }))
  await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ runPolicy: expect.objectContaining({ concurrency: 4, maxLiveInstances: 2 }) })))
})

it('resets both limits to one when the last data input is removed', async () => {
  const onSubmit = vi.fn()
  render(<AutomationEditor {...props({ onSubmit, initialValue: { ...initial, runPolicy: { ...initial.runPolicy, concurrency: 4, maxLiveInstances: 2 }, inputPlan: { inputs: [{ inputId: 'input', alias: '资料', tableId: 'table', datasetGeneration: 'generation', mode: 'independent', required: true, fieldBindings: [], filter: { type: 'all', items: [] }, orderBy: [] }] } }, renderInputPlan: (_value, onChange) => <button onClick={() => onChange({ inputs: [] })}>移除数据输入</button> })}/>)
  await userEvent.click(screen.getByRole('tab', { name: '输入与参数' }))
  fireEvent.click(screen.getByRole('button', { name: '移除数据输入' }))
  await userEvent.click(screen.getByRole('tab', { name: '运行设置' }))
  expect(screen.getByLabelText('并发任务数')).toBeDisabled()
  expect(screen.getByLabelText('最大活动实例')).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: '保存配置' }))
  await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ inputPlan: { inputs: [] }, runPolicy: expect.objectContaining({ concurrency: 1, maxLiveInstances: 1 }) })))
})
