import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { useState } from 'react'
import { RunPolicyEditor } from './RunPolicyEditor'
import type { RunPolicy } from './policy-types'

afterEach(cleanup)
const policy: RunPolicy = { maxTasks: 10, concurrency: 1, maxLiveInstances: 1, continueAfterFailure: false, automaticExecutionTimeoutSeconds: 900, manualDeadlineSeconds: 7200 }

it('edits max tasks and converts displayed minutes back to seconds without losing hidden fields', () => {
  const onChange = vi.fn()
  render(<RunPolicyEditor value={policy} onChange={onChange} />)
  expect(screen.getByLabelText('单任务超时（分钟）')).toHaveValue('15')
  fireEvent.change(screen.getByLabelText('最大任务数'), { target: { value: '20' } })
  expect(onChange).toHaveBeenLastCalledWith({ ...policy, maxTasks: 20 })
  fireEvent.change(screen.getByLabelText('单任务超时（分钟）'), { target: { value: '2.5' } })
  expect(onChange).toHaveBeenLastCalledWith({ ...policy, automaticExecutionTimeoutSeconds: 150 })
  expect(onChange.mock.calls.at(-1)?.[0].manualDeadlineSeconds).toBe(7200)
})

it('shows fixed serial limits and maps the stop-after-failure wording to continueAfterFailure', () => {
  const onChange = vi.fn()
  render(<RunPolicyEditor value={policy} onChange={onChange} />)
  expect(screen.getByLabelText('并发任务数')).toHaveValue(1)
  expect(screen.getByLabelText('并发任务数')).toBeDisabled()
  expect(screen.getByText('当前版本按顺序执行')).toBeVisible()
  fireEvent.click(screen.getByRole('switch', { name: '某个任务失败后停止创建后续任务' }))
  expect(onChange).toHaveBeenCalledWith({ ...policy, continueAfterFailure: true })
})

it('shows the fixed cleanup policy and keeps environment retention unavailable', () => {
  const onChange = vi.fn()
  render(<RunPolicyEditor value={policy} onChange={onChange} />)
  expect(screen.getByRole('radio', { name: '关闭并清理临时环境' })).toBeChecked()
  expect(screen.getByRole('radio', { name: '保留环境（暂未开放）' })).toBeDisabled()
  expect(screen.getByText('当前按最大任务数执行；无限运行暂未开放')).toBeVisible()
  expect(screen.getByText('每个任务使用独立临时环境')).toBeVisible()
  fireEvent.click(screen.getByRole('radio', { name: '保留环境（暂未开放）' }))
  expect(onChange).not.toHaveBeenCalled()
})

it('retains invalid drafts and reports finite positive and range errors without emitting', () => {
  const onChange = vi.fn()
  render(<RunPolicyEditor value={policy} onChange={onChange} />)
  const timeout = screen.getByLabelText('单任务超时（分钟）')
  fireEvent.change(timeout, { target: { value: 'abc' } })
  expect(timeout).toHaveValue('abc')
  expect(screen.getByRole('alert')).toHaveTextContent('请输入有限的正数')
  fireEvent.change(screen.getByLabelText('最大任务数'), { target: { value: '101' } })
  expect(screen.getByText(/1–100/)).toHaveAttribute('role', 'alert')
  expect(onChange).not.toHaveBeenCalled()
})

it('honors disabled and external field errors', () => {
  const onChange = vi.fn()
  render(<RunPolicyEditor value={policy} onChange={onChange} disabled errors={{ maxTasks: '服务端拒绝该任务数' }} />)
  expect(screen.getByRole('alert')).toHaveTextContent('服务端拒绝该任务数')
  expect(screen.getByLabelText('最大任务数')).toBeDisabled()
  expect(screen.getByLabelText('单任务超时（分钟）')).toBeDisabled()
  expect(screen.getByRole('switch')).toBeDisabled()
  expect(screen.getByLabelText('最大任务数')).toHaveAccessibleDescription('服务端拒绝该任务数')
})

it('reports invalid drafts to the parent and reset restores both controlled fields', () => {
  function Fixture() {
    const [draft, setDraft] = useState({ dirty: false, valid: true })
    const [resetKey, setResetKey] = useState(0)
    return <><RunPolicyEditor value={policy} onChange={() => undefined} resetKey={resetKey} onDraftStateChange={setDraft}/><button disabled={!draft.dirty || !draft.valid}>保存</button><button onClick={() => setResetKey(key => key + 1)}>取消</button></>
  }
  render(<Fixture />)
  fireEvent.change(screen.getByLabelText('单任务超时（分钟）'), { target: { value: 'bad' } })
  expect(screen.getByRole('button', { name: '保存' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: '取消' }))
  expect(screen.getByLabelText('单任务超时（分钟）')).toHaveValue('15')
})

it('keeps the whole editor invalid when max tasks changes after a bad timeout draft', () => {
  function Fixture() {
    const [value, setValue] = useState(policy)
    const [draft, setDraft] = useState({ dirty: false, valid: true })
    return <><RunPolicyEditor value={value} onChange={setValue} onDraftStateChange={setDraft}/><button disabled={!draft.valid}>保存</button></>
  }
  render(<Fixture />)
  fireEvent.change(screen.getByLabelText('单任务超时（分钟）'), { target: { value: 'bad' } })
  fireEvent.change(screen.getByLabelText('最大任务数'), { target: { value: '20' } })
  expect(screen.getByLabelText('单任务超时（分钟）')).toHaveValue('bad')
  expect(screen.getByRole('button', { name: '保存' })).toBeDisabled()
})

it('keeps decimal minutes while a controlled parent echoes each typed value', async () => {
  function Fixture() {
    const [value, setValue] = useState(policy)
    return <RunPolicyEditor value={value} onChange={setValue}/>
  }
  render(<Fixture />)
  const input = screen.getByLabelText('单任务超时（分钟）')
  const user = userEvent.setup()
  await user.clear(input)
  await user.type(input, '2.5')
  expect(input).toHaveValue('2.5')
  expect(screen.getByText('单任务最长 2.5 分钟')).toBeVisible()
})

it('does not notify again merely because an inline callback gets a new identity', () => {
  let notifications = 0
  function Fixture() {
    const [, setState] = useState({ dirty: false, valid: true })
    return <RunPolicyEditor value={policy} onChange={() => undefined} onDraftStateChange={state => { notifications += 1; setState({ ...state }) }}/>
  }
  render(<Fixture />)
  expect(notifications).toBe(1)
})

it('rejects a minutes value whose conversion to seconds overflows', () => {
  const onChange = vi.fn(), onDraftStateChange = vi.fn()
  render(<RunPolicyEditor value={policy} onChange={onChange} onDraftStateChange={onDraftStateChange}/>)
  fireEvent.change(screen.getByLabelText('单任务超时（分钟）'), { target: { value: '1e308' } })
  expect(onChange).not.toHaveBeenCalled()
  expect(onDraftStateChange).toHaveBeenLastCalledWith({ dirty: true, valid: false })
})

it('edits both data concurrency limits and keeps a bad sibling draft invalid', () => {
  function Fixture() {
    const [value, setValue] = useState({ ...policy, concurrency: 4, maxLiveInstances: 2 })
    const [draft, setDraft] = useState({ dirty: false, valid: true })
    return <><RunPolicyEditor dataBatch value={value} onChange={setValue} onDraftStateChange={setDraft}/><button disabled={!draft.valid}>保存</button></>
  }
  render(<Fixture/>)
  expect(screen.getByLabelText('请求并发数')).toHaveValue('4')
  expect(screen.getByLabelText('最大活动实例')).toHaveValue('2')
  expect(screen.getByText('配置并发上限 2')).toBeVisible()
  fireEvent.change(screen.getByLabelText('请求并发数'), { target: { value: '101' } })
  fireEvent.change(screen.getByLabelText('最大活动实例'), { target: { value: '3' } })
  expect(screen.getByLabelText('请求并发数')).toHaveValue('101')
  expect(screen.getByRole('button', { name: '保存' })).toBeDisabled()
  fireEvent.change(screen.getByLabelText('请求并发数'), { target: { value: '2' } })
  expect(screen.getByRole('button', { name: '保存' })).toBeEnabled()
})
