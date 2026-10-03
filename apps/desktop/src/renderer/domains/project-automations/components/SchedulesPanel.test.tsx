import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { choiceTestEnvironment, chooseOption } from '../../../shared/testing/choice-user'
import { SchedulesPanel, type Schedule } from './SchedulesPanel'

choiceTestEnvironment()
afterEach(cleanup)

const schedule = (extra: Partial<Schedule> = {}): Schedule => ({
  scheduleId: 's1', projectId: 'p', automationId: 'a', kind: 'cron', cron: '0 9 * * *', timezone: 'Asia/Shanghai', overlap: 'skip',
  missed: 'latestOnly', enabled: true, parameters: {}, maxTasks: null, concurrency: 1, lastFireAt: null, revision: 1, webhookSecret: null, ...extra,
})

function api(items: Schedule[]) {
  return {
    list: vi.fn(async () => items),
    create: vi.fn(async () => schedule({ kind: 'webhook', cron: null, webhookSecret: 'secret-once' })),
    update: vi.fn(async (_id: string, body: { enabled: boolean; expectedRevision: number }) => schedule({ enabled: body.enabled, revision: 2 })),
    remove: vi.fn(async () => undefined),
    triggers: vi.fn(async () => [{ triggerId: 't1', kind: 'cron' as const, plannedAt: '2026-10-03T01:00:00+00:00', receivedAt: '2026-10-03T01:00:05Z', state: 'skipped' as const, batchId: null, reason: '上一批仍在运行，按设置跳过本次触发' }]),
  }
}

it('lists schedules in plain words and shows the recent triggers with their reason', async () => {
  const client = api([schedule()])
  render(<SchedulesPanel api={client}/>)
  expect(await screen.findByText('定时 0 9 * * *（Asia/Shanghai）')).toBeVisible()
  expect(screen.getByText('上一批未结束时跳过；错过时补跑最近一次')).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '最近触发' }))
  expect(await screen.findByText(/已跳过：上一批仍在运行/)).toBeVisible()
})

it('turns a schedule off with the current revision', async () => {
  const client = api([schedule()])
  render(<SchedulesPanel api={client}/>)
  await userEvent.click(await screen.findByRole('switch', { name: /启用调度/ }))
  await waitFor(() => expect(client.update).toHaveBeenCalledWith('s1', expect.objectContaining({ enabled: false, expectedRevision: 1 })))
})

it('creates an external-call schedule and shows its secret only once', async () => {
  const client = api([])
  const user = userEvent.setup()
  render(<SchedulesPanel api={client}/>)
  await user.click(await screen.findByRole('button', { name: '添加调度' }))
  await chooseOption(user, screen.getByRole('combobox', { name: '触发方式' }), 'webhook')
  expect(screen.queryByRole('textbox', { name: '时间表达式' })).toBeNull()
  await user.click(screen.getByRole('button', { name: '保存调度' }))
  await waitFor(() => expect(client.create).toHaveBeenCalledWith(expect.objectContaining({ kind: 'webhook', cron: null })))
  expect(await screen.findByText('secret-once')).toBeVisible()
  await user.click(screen.getByRole('button', { name: '我已保存' }))
  expect(screen.queryByText('secret-once')).toBeNull()
})
