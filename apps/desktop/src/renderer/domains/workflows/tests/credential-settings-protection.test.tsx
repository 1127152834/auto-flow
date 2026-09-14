import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { CredentialSettings } from '../components/CredentialSettings'
import { configureStudioConnection } from '../api/config'
const credential = { name: 'fixture', description: '', fields: [{ key: 'value', masked: '•••' }], created_at: '', updated_at: '' }
const fetcher = vi.fn<typeof fetch>()
let restore = () => {}
beforeEach(() => {
  fetcher.mockReset().mockResolvedValue(Response.json({ success: true, credentials: [credential], mock: true }))
  restore = configureStudioConnection('http://credentials.fixture', fetcher)
})
afterEach(() => { cleanup(); restore() })
async function editNew() {
  render(<CredentialSettings />)
  await screen.findByText('fixture', { exact: true })
  fireEvent.click(screen.getByRole('button', { name: '新增凭据' }))
  fireEvent.change(screen.getByPlaceholderText('如：我的邮箱'), { target: { value: 'new-fixture' } })
  fireEvent.change(screen.getByPlaceholderText('值'), { target: { value: 'dummy-value' } })
}
it.each(['http', 'business', 'malformed', 'rejected'])('shows retryable %s list failure without pretending the vault is empty', async mode => {
  fetcher.mockImplementationOnce(async () => {
    if (mode === 'rejected') throw new TypeError('Failed to fetch')
    return Response.json(mode === 'malformed' ? { success: true, credentials: [{}] } : { success: false, error: '不可读' }, { status: mode === 'http' ? 503 : 200 })
  })
  render(<CredentialSettings />)
  await screen.findByRole('alert')
  expect(screen.queryByText(/还没有凭据/)).toBeNull()
  expect((screen.getByRole('button', { name: '新增凭据' }) as HTMLButtonElement).disabled).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: '刷新凭据' }))
  await screen.findByText('fixture', { exact: true })
})
it.each([{}, { success: 'true' }])('preserves fields after unconfirmed save %j', async body => {
  await editNew()
  fetcher.mockResolvedValueOnce(Response.json(body))
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  await screen.findByText(/保存失败/)
  expect(screen.getByPlaceholderText('值')).toHaveProperty('value', 'dummy-value')
})
it('blocks duplicate trimmed field names instead of silently overwriting one', async () => {
  await editNew()
  fireEvent.click(screen.getByRole('button', { name: '添加字段' }))
  const names = screen.getAllByPlaceholderText('字段名 如 value/password/api_key')
  fireEvent.change(names[1], { target: { value: ' value ' } })
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  await screen.findByText(/字段名重复/)
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0)
})
it('serializes saving and locks the submitted fields until failure is acknowledged', async () => {
  await editNew()
  let resolve!: (value: Response) => void
  fetcher.mockImplementationOnce(() => new Promise(done => { resolve = done }))
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
  expect((screen.getByPlaceholderText('值') as HTMLInputElement).closest('fieldset')?.disabled).toBe(true)
  await act(async () => resolve(Response.json({ success: false, error: '不可写' })))
  await screen.findByText(/保存失败：不可写/)
  fireEvent.click(screen.getByRole('button', { name: '确定' }))
  await waitFor(() => expect((screen.getByRole('button', { name: '保存' }) as HTMLButtonElement).disabled).toBe(false))
})
it('shows failed deletion without silently refreshing away the outcome', async () => {
  render(<CredentialSettings />)
  await screen.findByText('fixture', { exact: true })
  fireEvent.click(screen.getByRole('button', { name: '删除凭据 fixture' }))
  fetcher.mockResolvedValueOnce(Response.json({ success: false, error: '删除失败' }))
  fireEvent.click(screen.getByRole('button', { name: '删除' }))
  await screen.findByText(/删除失败/)
  expect(screen.getByText('fixture', { exact: true })).toBeTruthy()
})

it('retains a draft after service replacement without forwarding it or accepting the old save', async () => {
  await editNew()
  let resolve!: (value: Response) => void
  fetcher.mockImplementationOnce(() => new Promise(done => { resolve = done }))
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  const next = vi.fn(async () => Response.json({ success: true, credentials: [{ ...credential, name: 'next-fixture' }], mock: true }))
  let restoreNext = () => {}
  act(() => { restoreNext = configureStudioConnection('http://next.fixture', next) })
  try {
    await act(async () => resolve(Response.json({ success: true })))
    expect(screen.getByPlaceholderText('值')).toHaveProperty('value', 'dummy-value')
    expect((screen.getByRole('button', { name: '保存' }) as HTMLButtonElement).disabled).toBe(true)
    expect(next).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '取消' }))
    fireEvent.click(screen.getByRole('button', { name: '刷新凭据' }))
    await screen.findByText('next-fixture', { exact: true })
    expect(next).toHaveBeenCalledOnce()
  } finally { cleanup(); restoreNext() }
})
it('does not apply a stale list after a newer service has loaded', async () => {
  let resolve!: (value: Response) => void
  fetcher.mockImplementationOnce(() => new Promise(done => { resolve = done }))
  render(<CredentialSettings />)
  const next = vi.fn(async () => Response.json({ success: true, credentials: [{ ...credential, name: 'next-fixture' }] }))
  let restoreNext = () => {}
  act(() => { restoreNext = configureStudioConnection('http://next.fixture', next) })
  try {
    fireEvent.click(screen.getByRole('button', { name: '刷新凭据' }))
    await screen.findByText('next-fixture', { exact: true })
    await act(async () => resolve(Response.json({ success: true, credentials: [credential] })))
    expect(screen.queryByText('fixture', { exact: true })).toBeNull()
  } finally { cleanup(); restoreNext() }
})
it('describes mock metadata storage without claiming real encryption or credential validation', async () => {
  render(<CredentialSettings />)
  await screen.findByText(/当前为 Mock：仅保存名称和打码字段信息/)
  expect(screen.queryByText(/Fernet/)).toBeNull()
})
it('rejects a blank field name rather than discarding its entered value', async () => {
  await editNew()
  fireEvent.change(screen.getByPlaceholderText('字段名 如 value/password/api_key'), { target: { value: ' ' } })
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  await screen.findByText('字段名不能为空')
  expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0)
})
