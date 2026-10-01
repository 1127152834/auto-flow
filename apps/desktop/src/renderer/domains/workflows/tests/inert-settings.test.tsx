import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const values = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (k: string) => values.get(k) ?? null, setItem: (k: string, v: string) => values.set(k, v), removeItem: (k: string) => values.delete(k) })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})
import { ConfigPanel } from '../components/ConfigPanel'
import { useWorkflowStore as store } from '../editor-store'
import { featureFlags } from '../lib/featureFlags'
import { describeInertSettings, findInertSettings } from '../lib/inertSettings'

Element.prototype.scrollIntoView = vi.fn()
beforeEach(() => { featureFlags.nodeRetryPolicy = false; store.getState().clearWorkflow() })
afterEach(cleanup)

it('hides retry, error policy and timeout actions by default but keeps the timeout itself', () => {
  store.getState().addNode('close_page', { x: 0, y: 0 })
  const id = store.getState().nodes[0].id
  store.getState().updateNodeData(id, { retryCount: 3, timeoutAction: 'skip', errorPolicy: { mode: 'retry-self', maxRetries: 2, interval: 0, onExhausted: 'stop' } })
  render(<ConfigPanel selectedNodeId={id} />)
  expect(screen.getByText('超时时间 (秒)')).toBeInTheDocument()
  for (const label of ['出错时', '运行超时后', '重试次数', '重试耗尽后', '重试间隔（秒）', '退避策略']) expect(screen.queryByText(label)).toBeNull()
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
  expect(describeInertSettings(found)).toBe('以下设置尚未生效，运行时会被忽略：「点击提交」重试次数、重试间隔、运行超时后；「loop」出错时、循环超时后')
})
