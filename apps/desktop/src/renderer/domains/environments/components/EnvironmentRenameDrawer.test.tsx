import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { EnvironmentRenameDrawer } from './EnvironmentRenameDrawer'

afterEach(cleanup)

const drawer = (props: Partial<Parameters<typeof EnvironmentRenameDrawer>[0]> = {}) => {
  const onSubmit = vi.fn()
  const onOpenChange = vi.fn()
  render(<EnvironmentRenameDrawer open initialName="登录环境" initialNotes="主账号" saving={false} onSubmit={onSubmit} onOpenChange={onOpenChange} {...props} />)
  return { onSubmit, onOpenChange }
}

it('opens the artboard drawer prefilled with the current display name and identity facts', () => {
  drawer()
  const panel = screen.getByRole('dialog', { name: /重命名环境/ })
  expect(panel).toBeVisible()
  expect(screen.getByLabelText('环境名称')).toHaveValue('登录环境')
  expect(screen.getByLabelText('环境备注')).toHaveValue('主账号')
  expect(screen.getByText(/环境 ID 与任务引用不会改变/)).toBeVisible()
})

it('blocks submission while the name is empty or longer than the approved limit', async () => {
  const user = userEvent.setup()
  const { onSubmit } = drawer()
  const name = screen.getByLabelText('环境名称')
  await user.clear(name)
  expect(screen.getByRole('alert')).toHaveTextContent('名称需 1–36 个字符')
  expect(screen.getByRole('button', { name: '保存名称' })).toBeDisabled()
  // 输入框本身限制在 36 个字符以内，因此超长只可能来自历史遗留名称，单列一个反例。
  await user.type(name, 'x'.repeat(40))
  expect(name).toHaveValue('x'.repeat(36))
  expect(onSubmit).not.toHaveBeenCalled()
  cleanup()
  drawer({ initialName: 'x'.repeat(40) })
  expect(screen.getByRole('alert')).toHaveTextContent('名称最多 36 个字符')
  expect(screen.getByRole('button', { name: '保存名称' })).toBeDisabled()
})

it('submits the edited draft and keeps the drawer open while the write is pending', async () => {
  const user = userEvent.setup()
  drawer({ saving: true })
  expect(screen.getByRole('button', { name: '保存中…' })).toBeDisabled()
  expect(screen.getByLabelText('环境名称')).toHaveValue('登录环境')
  cleanup()
  const next = drawer()
  await user.clear(screen.getByLabelText('环境名称'))
  await user.type(screen.getByLabelText('环境名称'), '登录环境 v2')
  await user.click(screen.getByRole('button', { name: '保存名称' }))
  expect(next.onSubmit).toHaveBeenCalledWith({ name: '登录环境 v2', notes: '主账号' })
})

it('asks before discarding a dirty draft and cancels without touching the environment', async () => {
  const user = userEvent.setup()
  const { onSubmit, onOpenChange } = drawer()
  await user.click(screen.getByRole('button', { name: '取消' }))
  expect(screen.queryByText('放弃未保存的名称修改？')).not.toBeInTheDocument()
  expect(onOpenChange).toHaveBeenCalledWith(false)
  expect(onSubmit).not.toHaveBeenCalled()
  cleanup()
  const dirty = drawer()
  await user.type(screen.getByLabelText('环境名称'), '-草稿')
  await user.click(screen.getByRole('button', { name: '关闭重命名' }))
  expect(dirty.onOpenChange).not.toHaveBeenCalled()
  await user.click(await screen.findByRole('button', { name: '继续编辑' }))
  expect(dirty.onOpenChange).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button', { name: '关闭重命名' }))
  await user.click(await screen.findByRole('button', { name: '放弃修改' }))
  expect(dirty.onOpenChange).toHaveBeenCalledWith(false)
  expect(dirty.onSubmit).not.toHaveBeenCalled()
})

it('surfaces a rejected write inside the drawer instead of closing it', async () => {
  drawer({ error: '环境已被其他操作更新，请重新读取后再保存' })
  expect(screen.getByRole('dialog', { name: /重命名环境/ })).toBeVisible()
  expect(screen.getByText('环境已被其他操作更新，请重新读取后再保存')).toBeVisible()
})
