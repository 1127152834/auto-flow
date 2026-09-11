import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { Modal } from './Modal'

afterEach(cleanup)

function Fixture({ closeDisabled = false }: { closeDisabled?: boolean }) {
  const [open, setOpen] = useState(false)
  const [nested, setNested] = useState(false)
  const [showOpener, setShowOpener] = useState(true)
  return <main aria-label="模型页面">
    {showOpener ? <button onClick={() => setOpen(true)}>编辑模型</button> : null}
    <Modal open={open} onOpenChange={setOpen} title="编辑模型" closeDisabled={closeDisabled}>
      <button onClick={() => setShowOpener(false)}>移除入口</button>
      <button onClick={() => setNested(true)}>从目录移除</button>
      <Modal open={nested} onOpenChange={setNested} title="删除模型" footer={<button onClick={() => setNested(false)}>取消</button>}>
        仅影响本地目录
      </Modal>
    </Modal>
  </main>
}

describe('Modal', () => {
  it('closes through Escape, overlay, and close button when unlocked', async () => {
    const user = userEvent.setup()
    const onOpenChange = vi.fn()
    const { rerender } = render(<Modal open onOpenChange={onOpenChange} title="连接信息">正文</Modal>)
    await user.keyboard('{Escape}')
    expect(onOpenChange).toHaveBeenLastCalledWith(false)

    onOpenChange.mockClear()
    fireEvent.pointerDown(document.querySelector('[data-slot="modal-overlay"]')!)
    fireEvent.click(document.querySelector('[data-slot="modal-overlay"]')!)
    expect(onOpenChange).toHaveBeenCalledWith(false)

    onOpenChange.mockClear()
    await user.click(screen.getByRole('button', { name: '关闭' }))
    expect(onOpenChange).toHaveBeenCalledWith(false)

    rerender(<Modal open onOpenChange={onOpenChange} title="连接信息" closeDisabled>正文</Modal>)
    onOpenChange.mockClear()
    await user.keyboard('{Escape}')
    fireEvent.pointerDown(document.querySelector('[data-slot="modal-overlay"]')!)
    expect(onOpenChange).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: '正在处理，请稍候' })).toBeDisabled()
  })

  it('keeps the parent mounted and returns focus after cancelling a nested confirmation', async () => {
    const user = userEvent.setup()
    render(<Fixture />)
    await user.click(screen.getByRole('button', { name: '编辑模型' }))
    const childOpener = screen.getByRole('button', { name: '从目录移除' })
    await user.click(childOpener)
    await user.click(within(screen.getByRole('dialog', { name: '删除模型' })).getByRole('button', { name: '取消' }))
    await waitFor(() => expect(childOpener).toHaveFocus())
    expect(screen.getByRole('dialog', { name: '编辑模型' })).toBeInTheDocument()
  })

  it('returns focus to the page when the opener was removed', async () => {
    const user = userEvent.setup()
    render(<Fixture />)
    const page = screen.getByRole('main', { name: '模型页面' })
    await user.click(screen.getByRole('button', { name: '编辑模型' }))
    await user.click(screen.getByRole('button', { name: '移除入口' }))
    await user.keyboard('{Escape}')
    await waitFor(() => expect(page).toHaveFocus())
    expect(page).not.toHaveAttribute('tabindex')
  })

  it('preserves the new focus target during a rapid close and reopen', async () => {
    const user = userEvent.setup()
    function RapidFixture() {
      const [open, setOpen] = useState(false)
      return <main>
        <button onClick={() => setOpen(true)}>入口一</button>
        <button onClick={() => setOpen(true)}>入口二</button>
        <Modal open={open} onOpenChange={setOpen} title="快速重开"><button onClick={() => setOpen(false)}>立即关闭</button></Modal>
      </main>
    }
    render(<RapidFixture />)
    const first = screen.getByRole('button', { name: '入口一' })
    const second = screen.getByRole('button', { name: '入口二' })
    act(() => { first.focus(); first.click() })
    act(() => screen.getByRole('button', { name: '立即关闭' }).click())
    act(() => { second.focus(); second.click() })
    await user.keyboard('{Escape}')
    await waitFor(() => expect(second).toHaveFocus())
  })
})
