import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { useBatchCommand } from '../hooks'
import { RunCommandNotice } from './RunCommandNotice'

afterEach(cleanup)

type Command = ReturnType<typeof useBatchCommand>

function command(type: 'start' | 'stop' | 'forceStop', notAccepted: boolean): Command {
  const body = type === 'start'
    ? { expectedAutomationRevision: 1, parameters: {} }
    : { expectedStatusRevision: 1, reason: '用户操作' }
  const target = type === 'start' ? { automationId: 'automation' } : { batchId: 'batch' }
  return {
    busy: false,
    recovering: true,
    notAccepted,
    invalidRecovery: false,
    error: undefined,
    restoredCommand: { type, ...target, body, key: 'key' },
    locked: vi.fn(),
    start: vi.fn(),
    stop: vi.fn(),
    forceStop: vi.fn(),
    lookup: vi.fn(),
    retry: vi.fn(),
    acknowledgeAccepted: vi.fn(),
    discardNotAccepted: vi.fn(),
    discardInvalidRecovery: vi.fn(),
  } as Command
}

describe.each([
  ['start', '启动'],
  ['stop', '停止'],
  ['forceStop', '强制停止'],
] as const)('%s command notice', (type, label) => {
  it('names the operation when its result needs recovery', () => {
    render(<RunCommandNotice command={command(type, false)} />)
    expect(screen.getByRole('alert')).toHaveTextContent(`批次${label}请求已接受，正在核对${label}结果。`)
  })

  it('names the operation when the original request was not accepted', () => {
    render(<RunCommandNotice command={command(type, true)} />)
    expect(screen.getByRole('alert')).toHaveTextContent(`原${label}请求尚未接受，可以使用原操作身份重试或继续编辑。`)
  })
})

it('uses neutral wording while the current command type is not recoverable', () => {
  const current = { ...command('start', false), restoredCommand: null }
  render(<RunCommandNotice command={current} />)
  expect(screen.getByRole('alert')).toHaveTextContent('批次操作已接受，正在核对结果。')
  expect(screen.getByRole('alert')).not.toHaveTextContent(/启动|创建/)
})
