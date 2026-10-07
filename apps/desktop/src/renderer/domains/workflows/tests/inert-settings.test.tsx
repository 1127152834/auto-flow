import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const values = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (k: string) => values.get(k) ?? null, setItem: (k: string, v: string) => values.set(k, v), removeItem: (k: string) => values.delete(k) })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})
import { ConfigPanel } from '../components/ConfigPanel'
import { expandAdvanced } from './expand-advanced'
import { useWorkflowStore as store } from '../editor-store'
import { describeInertSettings, findInertSettings, inertKeys } from '../lib/inertSettings'

Element.prototype.scrollIntoView = vi.fn()
beforeEach(() => { store.getState().clearWorkflow() })
afterEach(cleanup)

it('hides the old retry and timeout actions, offers the old error policy only as a candidate, and keeps the timeout', () => {
  store.getState().addNode('close_page', { x: 0, y: 0 })
  const id = store.getState().nodes[0].id
  store.getState().updateNodeData(id, { retryCount: 3, timeoutAction: 'skip', errorPolicy: { mode: 'retry-self', maxRetries: 2, interval: 0, onExhausted: 'stop' } })
  render(<ConfigPanel selectedNodeId={id} />)
  expandAdvanced()
  expect(screen.getByText('超时时间 (秒)')).toBeInTheDocument()
  for (const label of ['运行超时后', '重试次数', '重试耗尽后', '重试间隔（秒）', '退避策略']) expect(screen.queryByText(label)).toBeNull()
  // Remediation M2 R2-12: the unified control is visible, and the old settings are a not-yet-active candidate.
  expect(screen.getByText('出错时')).toBeInTheDocument()
  expect(screen.getByRole('status', { name: '未生效的出错设置' })).toHaveTextContent('尚未生效')
  const saved = JSON.parse(store.getState().exportWorkflow()).nodes[0].data
  expect(saved).toMatchObject({ retryCount: 3, timeoutAction: 'skip', errorPolicy: { mode: 'retry-self' } })
})

it('reports only settings that would have changed behaviour', () => {
  const found = findInertSettings([
    { id: 'a', data: { moduleType: 'click_element', label: '点击提交', retryCount: 2, retryDelay: 1, timeoutAction: 'retry' } },
    { id: 'b', data: { moduleType: 'click_element', retryCount: 0, retryDelay: 5, timeoutAction: 'stop', errorPolicy: { mode: 'stop' } } },
    { id: 'c', data: { moduleType: 'loop', config: { onTimeout: 'skip', errorPolicy: { mode: 'continue' } } } },
    { id: 'd', data: { moduleType: 'open_page', onTimeout: 'skip' } },
  ])
  expect(found).toEqual([
    { nodeId: 'a', label: '点击提交', keys: ['retryCount', 'retryDelay', 'timeoutAction'] },
    { nodeId: 'c', label: 'loop', keys: ['errorPolicy', 'onTimeout'] },
  ])
  expect(describeInertSettings(found)).toBe('以下旧设置不会自动生效，可在「出错时」查看转换建议并启用：「点击提交」重试次数、重试间隔、运行超时后；「loop」出错时、循环超时后')
})

it('treats null like an unset value, matching the backend rule', () => {
  expect(inertKeys({ retryCount: 1, retryDelay: null, errorPolicy: { mode: null } }, 'click_element')).toEqual(['retryCount'])
})
