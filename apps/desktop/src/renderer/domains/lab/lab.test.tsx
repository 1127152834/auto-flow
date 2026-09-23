import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { ApiClient } from '../../shared/api/client'
import { buildRequest, draftsFromQuestions } from './draft'
import { LabPage } from './pages/LabPage'
import { automationPreview } from './preview'
import { presets } from './presets'
import { readRecords, removeRecord, saveRecord } from './storage'
import type { ExperimentRecord, LayaResult } from './types'

const result: LayaResult = {
  answers: {
    department: { type: 'choice', choice: 'billing', probabilities: { billing: 0.9, technical: 0.1 }, confidence: 0.92 },
    refund_requested: { type: 'noul', noul: 0.7, probabilities: { false: 0.3, true: 0.7 }, confidence: 0.7 },
  },
  routing: { requested: 'auto', selected: 'multilingual', reason: 'non-Latin script', repo: 'convaiinnovations/laya/multilingual' },
  usage: { inputTokens: 42 }, timing: { loadMs: 12, inferenceMs: 23, totalMs: 35 },
  runtime: { checkpoint: 'multilingual', revision: '1c5edc17a7ac', device: 'cpu' },
}

beforeEach(() => {
  const values = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
    clear: () => values.clear(),
  })
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

it('validates editor input and preserves JSON structure for the API', () => {
  const preset = presets.find(item => item.id === 'charge')!
  const body = buildRequest(preset.request.model, 'json', JSON.stringify(preset.request.state), draftsFromQuestions(preset.request.questions))
  expect(body.state).toEqual(preset.request.state)
  expect(() => buildRequest('auto', 'json', '{broken', draftsFromQuestions(preset.request.questions))).toThrow('JSON')
  expect(() => buildRequest('auto', 'text', '中'.repeat(6000), draftsFromQuestions(preset.request.questions))).toThrow('16 KiB')
})

it('produces human review when below the demo threshold and stores records per workspace', () => {
  const preview = automationPreview(result, 0.85)
  expect(preview.suggestedActions).toEqual([
    { questionId: 'department', kind: 'route', target: 'billing' },
    { questionId: 'refund_requested', kind: 'human_review', reason: 'below_demo_threshold' },
  ])
  expect(preview.previewOnly).toBe(true)
  const record: ExperimentRecord = { id: 'one', createdAt: '2026-09-23T00:00:00Z', request: presets[0].request, result }
  saveRecord('workspace-a', record)
  expect(readRecords('workspace-a')).toHaveLength(1)
  expect(readRecords('workspace-b')).toHaveLength(0)
  removeRecord('workspace-a', 'one')
  expect(readRecords('workspace-a')).toHaveLength(0)
})

it('runs the decision through the shared API and manually saves it', async () => {
  const request = vi.fn(async (path: string) => path.endsWith('/status')
    ? { busy: false, models: [{ key: 'english', state: 'cached', device: null }] }
    : result)
  render(<LabPage client={{ request } as unknown as ApiClient} workspaceKey="workspace-a" />)
  fireEvent.click(screen.getByRole('button', { name: '运行 Laya 推理' }))
  await waitFor(() => expect(screen.getByText('推理结果')).toBeInTheDocument())
  expect(screen.getByText('自动化预览')).toBeInTheDocument()
  expect(request).toHaveBeenCalledWith('/api/v1/lab/laya/predict', expect.objectContaining({ method: 'POST' }))
  fireEvent.click(screen.getByRole('button', { name: '保存实验记录' }))
  expect(readRecords('workspace-a')).toHaveLength(1)
  expect(screen.getByText('已保存到本机')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('待判断内容'), { target: { value: 'Different ticket' } })
  expect(screen.queryByText('推理结果')).not.toBeInTheDocument()
  expect(readRecords('workspace-a')).toHaveLength(1)
})

it.each([
  [new Error('Laya 模型下载或加载失败，请检查网络与可用空间后重试'), 'Laya 模型下载或加载失败，请检查网络与可用空间后重试'],
  [new DOMException('API request timed out', 'TimeoutError'), '等待模型响应超时，请检查服务状态后重试'],
])('shows a model error without saving a record', async (failure, message) => {
  const request = vi.fn(async (path: string) => {
    if (path.endsWith('/status')) return { busy: false, models: [{ key: 'english', state: 'failed', device: null }] }
    throw failure
  })
  render(<LabPage client={{ request } as unknown as ApiClient} workspaceKey="workspace-a" />)
  fireEvent.click(screen.getByRole('button', { name: '运行 Laya 推理' }))
  await waitFor(() => expect(screen.getByText(message)).toBeInTheDocument())
  expect(readRecords('workspace-a')).toHaveLength(0)
})
