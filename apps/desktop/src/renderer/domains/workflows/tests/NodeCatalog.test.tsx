import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { NodeDefinition } from '../types'
import { NodeCatalog } from '../components/NodeCatalog'

afterEach(cleanup)

const items: NodeDefinition[] = [
  { type: 'open_page', title: '打开网页', description: '打开一个网页', category: 'browser', defaultConfig: { url: '' }, configSchema: {}, inputPorts: ['in'], outputPorts: ['out'], runnable: false },
  { type: 'screenshot', title: '网页截图', description: '保存网页截图', category: 'browser', defaultConfig: {}, configSchema: {}, inputPorts: ['in'], outputPorts: ['out'], runnable: false },
]

it('filters by Chinese title or type, and adds only the selected catalog type', async () => {
  const user = userEvent.setup()
  const onAdd = vi.fn()
  render(<NodeCatalog items={items} onAdd={onAdd} />)
  await user.type(screen.getByRole('textbox', { name: '搜索动作' }), '截图')
  expect(screen.queryByRole('button', { name: '添加打开网页' })).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '添加网页截图' }))
  expect(onAdd).toHaveBeenCalledWith('screenshot')
  await user.clear(screen.getByRole('textbox', { name: '搜索动作' }))
  await user.type(screen.getByRole('textbox', { name: '搜索动作' }), 'OPEN_')
  expect(screen.getByRole('button', { name: '添加打开网页' })).toBeVisible()
  expect(screen.queryByRole('button', { name: '添加网页截图' })).not.toBeInTheDocument()
})

it('exports a catalog type for canvas drop, and blocks additions when locked', () => {
  const onAdd = vi.fn()
  const dataTransfer = { setData: vi.fn(), effectAllowed: '' }
  const { rerender } = render(<NodeCatalog items={items} onAdd={onAdd} />)
  fireEvent.dragStart(screen.getByRole('button', { name: '添加打开网页' }), { dataTransfer })
  expect(dataTransfer.setData).toHaveBeenCalledWith('application/autoflow-node', 'open_page')
  expect(dataTransfer.effectAllowed).toBe('copy')
  rerender(<NodeCatalog items={items} onAdd={onAdd} disabled />)
  expect(screen.getByRole('button', { name: '添加打开网页' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '添加打开网页' })).toHaveAttribute('draggable', 'false')
  fireEvent.click(screen.getByRole('button', { name: '添加打开网页' }))
  expect(onAdd).not.toHaveBeenCalled()
})
