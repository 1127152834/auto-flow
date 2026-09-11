import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { ApiProvider } from '../../../app/ApiProvider'
import { Toaster } from '../../../shared/components/Toaster'
import { ProfileActionDialog, type ProfileAction } from './ProfileActionDialog'

function renderAction(action: ProfileAction, response = new Response(null, { status: 204 })) {
  const onClose = vi.fn()
  const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => response)
  vi.stubGlobal('fetch', fetchMock)
  render(<ApiProvider baseUrl="http://127.0.0.1:1" token="fixture-token" instanceId="fixture-instance">
    <ProfileActionDialog action={action} onClose={onClose} /><Toaster />
  </ApiProvider>)
  return { fetchMock, onClose }
}

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('duplicates only the entered name and announces success', async () => {
  const user = userEvent.setup()
  const { fetchMock, onClose } = renderAction({ kind: 'duplicate', id: 'profile/id', name: '来源' }, new Response(JSON.stringify({ id: 'copy' }), { status: 201 }))
  await user.type(screen.getByLabelText('新配置名称'), '副本')
  await user.click(screen.getByRole('button', { name: '创建副本' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
  const [, init] = fetchMock.mock.calls[0]
  expect(JSON.parse(String(init?.body))).toEqual({ name: '副本' })
  expect(await screen.findByText('配置已复制')).toBeInTheDocument()
  expect(onClose).toHaveBeenCalledWith(false)
})

it('keeps a copy dialog open with its input after a conflict', async () => {
  const user = userEvent.setup()
  const response = new Response(JSON.stringify({ error: {
    code: 'PROFILE_NAME_CONFLICT', message: '配置名称已存在', details: {}, requestId: 'request-1',
  } }), { status: 409 })
  const { onClose } = renderAction({ kind: 'duplicate', id: 'profile-1', name: '来源' }, response)
  await user.type(screen.getByLabelText('新配置名称'), '重复名称')
  await user.click(screen.getByRole('button', { name: '创建副本' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('配置名称已存在')
  expect(screen.getByLabelText('新配置名称')).toHaveValue('重复名称')
  expect(onClose).not.toHaveBeenCalled()
})

it('defaults delete focus to cancel and announces success', async () => {
  const user = userEvent.setup()
  const { fetchMock, onClose } = renderAction({ kind: 'delete', id: 'profile/id', name: '待删除' })
  expect(screen.getByRole('button', { name: '取消' })).toHaveFocus()
  await user.click(screen.getByRole('button', { name: '确认删除' }))
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
  expect(fetchMock.mock.calls[0][0]).toBe('http://127.0.0.1:1/api/v1/profiles/profile%2Fid')
  expect(await screen.findByText('配置已删除')).toBeInTheDocument()
  expect(onClose).toHaveBeenCalledWith(true)
})

it('keeps delete open after an error', async () => {
  const user = userEvent.setup()
  const response = new Response(JSON.stringify({ error: {
    code: 'PROFILE_DIRECTORY_BUSY', message: '浏览器数据正在使用', details: {}, requestId: 'request-2',
  } }), { status: 409 })
  const { onClose } = renderAction({ kind: 'delete', id: 'profile-1', name: '待删除' }, response)
  await user.click(screen.getByRole('button', { name: '确认删除' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('浏览器数据正在使用')
  expect(screen.getByRole('dialog')).toBeInTheDocument()
  expect(onClose).not.toHaveBeenCalled()
})
