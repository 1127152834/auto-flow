import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { credentialApi } from '../api'
import { DataSidebar } from '../components/DataSidebar'
import { useWorkflowStore } from '../editor-store'
import { useDataSelectionStore } from '../hooks/stores/dataSelectionStore'
import { useSignatureStore } from '../hooks/stores/signatureStore'

const writeText = vi.fn().mockResolvedValue(undefined)
const selected = () => useDataSelectionStore.getState().selectedReference

beforeEach(() => {
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
  writeText.mockClear()
  useDataSelectionStore.getState().clear()
  useSignatureStore.getState().reset()
  useSignatureStore.getState().load({ inputs: [{ key: 'account', name: '账号信息', fields: [{ key: 'phone', name: '手机号', type: 'string', required: true, sensitive: false }] }] })
  vi.spyOn(credentialApi, 'list').mockResolvedValue({ success: true, data: { success: true, credentials: [{ name: '邮箱账号', created_at: '', updated_at: '', fields: [] }] } } as never)
  useWorkflowStore.setState({ nodes: [], edges: [], variables: [] })
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('数据侧栏选中', () => {
  it('点击数据行：写入选中引用并仍然复制，再次点击取消', async () => {
    render(<DataSidebar />)
    const row = screen.getByRole('button', { name: /手机号/ })
    await act(async () => { fireEvent.click(row) })
    expect(selected()).toBe('{input.account.phone}')
    expect(writeText).toHaveBeenCalledWith('{input.account.phone}')
    expect(row.getAttribute('aria-pressed')).toBe('true')
    await act(async () => { fireEvent.click(row) })
    expect(selected()).toBeNull()
    expect(row.getAttribute('aria-pressed')).toBe('false')
  })

  it('Esc 取消选中；离开侧栏也会清除', async () => {
    const { unmount } = render(<DataSidebar />)
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: /手机号/ })) })
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(selected()).toBeNull()
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: /手机号/ })) })
    unmount()
    expect(selected()).toBeNull()
  })

  it('凭据只复制名称，不进入选中', async () => {
    render(<DataSidebar />)
    const row = await screen.findByRole('button', { name: /邮箱账号/ })
    await act(async () => { fireEvent.click(row) })
    expect(writeText).toHaveBeenCalledWith('邮箱账号')
    expect(selected()).toBeNull()
  })
})
