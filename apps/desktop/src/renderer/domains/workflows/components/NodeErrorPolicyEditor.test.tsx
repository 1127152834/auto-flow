import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { choiceTestEnvironment } from '../../../shared/testing/choice-user'
import { NodeErrorPolicyEditor } from './NodeErrorPolicyEditor'

choiceTestEnvironment()
afterEach(cleanup)
// The editor's dropdown is a Radix select: open it and pick the visible option.
async function pick(user: ReturnType<typeof userEvent.setup>, label: string, option: string) {
  await user.click(screen.getByLabelText(label))
  await user.click(await screen.findByRole('option', { name: option }))
}
const targets = [{ id: 'login', label: '登录' }]
const legacyCleared = { retryCount: undefined, retryDelay: undefined, retryBackoff: undefined, retryExhaustedAction: undefined, timeoutAction: undefined }

it('offers old settings as a candidate that only applies after enabling it', () => {
  const onChange = vi.fn()
  render(<NodeErrorPolicyEditor data={{ retryCount: 2, retryDelay: 3 }} targets={targets} onChange={onChange}/>)
  expect(screen.getByRole('status')).toHaveTextContent('以前保存的设置“出错时重试 2 次”尚未生效')
  expect(screen.getByLabelText('出错时')).toHaveTextContent('失败即停（默认）')
  fireEvent.click(screen.getByRole('button', { name: '启用这项设置' }))
  expect(onChange).toHaveBeenCalledWith({ ...legacyCleared, errorPolicy: expect.objectContaining({ version: 2, onError: 'retry', maxRetries: 2 }) })
})

it('creates, edits and clears a version-2 policy', async () => {
  const onChange = vi.fn(), user = userEvent.setup()
  const view = render(<NodeErrorPolicyEditor data={{}} targets={targets} onChange={onChange}/>)
  await pick(user, '出错时', '跳到指定模块重新执行')
  expect(onChange).toHaveBeenLastCalledWith({ ...legacyCleared, errorPolicy: expect.objectContaining({ onError: 'goto', maxRetries: 1, gotoNodeId: null }) })
  view.unmount()
  const policy = { version: 2, onError: 'goto', maxRetries: 1, backoff: { kind: 'fixed', initialSeconds: 0, maxSeconds: 0, jitter: false }, retryOn: 'any', gotoNodeId: null, onExhausted: 'stop' }
  render(<NodeErrorPolicyEditor data={{ errorPolicy: policy }} targets={targets} onChange={onChange}/>)
  expect(screen.queryByRole('status')).toBeNull()
  await pick(user, '出错后跳到', '登录')
  expect(onChange).toHaveBeenLastCalledWith({ ...legacyCleared, errorPolicy: { ...policy, gotoNodeId: 'login' } })
  await pick(user, '出错时', '失败即停（默认）')
  expect(onChange).toHaveBeenLastCalledWith({ ...legacyCleared, errorPolicy: undefined })
})
