import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ApiClientError } from '../../../shared/api/client'
import { useWorkflowEditor } from '../hooks/useWorkflowEditor'
import type { WorkflowApi } from '../api'
import type { WorkflowContent, WorkflowRead } from '../types'

function record(content: WorkflowContent, revision = 1): WorkflowRead { return { ...content, revision, createdAt: '2026-09-13T00:00:00Z', updatedAt: '2026-09-13T00:00:00Z', issues: [] } }
function api(): WorkflowApi { return { catalog: vi.fn(), list: vi.fn(), get: vi.fn(), create: vi.fn(async content => record(content)), save: vi.fn(async (content, revision) => record(content, revision + 1)) } }

describe('manual workflow persistence', () => {
  it('keeps edits made while a save is in flight dirty and saves them against the new revision', async () => {
    const service = api()
    let finish!: (value: WorkflowRead) => void
    service.create = vi.fn(() => new Promise<WorkflowRead>(resolve => { finish = resolve }))
    const { result } = renderHook(() => useWorkflowEditor(service, true))
    act(() => result.current.mutate(c => ({ ...c, document: { ...c.document, name: '版本 A' } })))
    const snapshot = result.current.content
    let pending!: Promise<boolean>
    act(() => { pending = result.current.save() })
    act(() => result.current.mutate(c => ({ ...c, document: { ...c.document, name: '版本 B' } })))
    await act(async () => { finish(record(snapshot)); expect(await pending).toBe(false) })
    expect(result.current.content.document.name).toBe('版本 B')
    expect(result.current.dirty).toBe(true)
    await act(async () => { expect(await result.current.save()).toBe(true) })
    expect(service.save).toHaveBeenCalledWith(expect.objectContaining({ document: expect.objectContaining({ name: '版本 B' }) }), 1)
    expect(result.current.dirty).toBe(false)
  })

  it('retains a stable identity and draft across a lost create response and retry', async () => {
    const service = api()
    vi.mocked(service.create).mockRejectedValueOnce(new Error('响应丢失'))
    const { result } = renderHook(() => useWorkflowEditor(service, true))
    act(() => result.current.mutate(c => ({ ...c, document: { ...c.document, name: '保留草稿' } })))
    const id = result.current.content.document.id
    await act(async () => { expect(await result.current.save()).toBe(false) })
    expect(result.current.dirty).toBe(true)
    await act(async () => { expect(await result.current.save()).toBe(true) })
    expect(vi.mocked(service.create).mock.calls.map(([c]) => c.document.id)).toEqual([id, id])
  })

  it('preserves dirty edits and undo when the API reconnects and prevents offline writes', async () => {
    const first = api()
    const { result, rerender } = renderHook(({ service, writable }) => useWorkflowEditor(service, writable), { initialProps: { service: first, writable: true } })
    act(() => result.current.mutate(c => ({ ...c, document: { ...c.document, name: '离线编辑' } })))
    rerender({ service: first, writable: false })
    await act(async () => { expect(await result.current.save()).toBe(false) })
    expect(first.create).not.toHaveBeenCalled()
    const second = api()
    rerender({ service: second, writable: true })
    expect(result.current.history.past).toHaveLength(1)
    expect(result.current.content.document.name).toBe('离线编辑')
    await act(async () => { await result.current.save() })
    expect(second.create).toHaveBeenCalledOnce()
  })

  it('does not clear a conflicting draft and can save it as a separate document', async () => {
    const service = api()
    const { result } = renderHook(() => useWorkflowEditor(service, true))
    await act(async () => { await result.current.save() })
    const originalId = result.current.content.document.id
    act(() => result.current.mutate(c => ({ ...c, document: { ...c.document, name: '我的修改' } })))
    service.save = vi.fn().mockRejectedValue(new ApiClientError('修改冲突', 409, 'WORKFLOW_CONFLICT'))
    await act(async () => { expect(await result.current.save()).toBe(false) })
    await waitFor(() => expect(result.current.conflict).toBe(true))
    expect(result.current.content.document.name).toBe('我的修改')
    await act(async () => { expect(await result.current.saveAsNew()).toBe(true) })
    expect(result.current.content.document.id).not.toBe(originalId)
    expect(result.current.content.document.name).toBe('我的修改 副本')
  })
})
