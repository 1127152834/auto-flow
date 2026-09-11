import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom/vitest'
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from './dialog'

afterEach(cleanup)

it('Escape closes the top dialog and returns focus', async () => {
  const user = userEvent.setup()
  render(<Dialog><DialogTrigger>管理内核</DialogTrigger><DialogContent><DialogTitle>内核管理</DialogTitle><DialogDescription>本机内核</DialogDescription><button>刷新版本列表</button></DialogContent></Dialog>)
  await user.click(screen.getByText('管理内核'))
  await user.keyboard('{Escape}')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.getByText('管理内核')).toHaveFocus()
})

it('busy dialogs ignore Escape and outside interaction', async () => {
  const user = userEvent.setup()
  render(<Dialog open busy><DialogTrigger>管理内核</DialogTrigger><DialogContent><DialogTitle>内核管理</DialogTitle><DialogDescription>本机内核</DialogDescription><button>刷新版本列表</button></DialogContent></Dialog>)
  expect(screen.getByRole('dialog')).toBeInTheDocument()
  await user.keyboard('{Escape}')
  expect(screen.getByRole('dialog')).toBeInTheDocument()
  fireEvent.pointerDown(document.body)
  expect(screen.getByRole('dialog')).toBeInTheDocument()
})

it('busy dialogs block DialogClose and controlled onOpenChange(false)', async () => {
  const user = userEvent.setup()
  const onOpenChange = vi.fn()
  render(<Dialog open busy onOpenChange={onOpenChange}><DialogContent><DialogTitle>内核管理</DialogTitle><DialogDescription>本机内核</DialogDescription><DialogClose>关闭</DialogClose></DialogContent></Dialog>)
  await user.click(screen.getByRole('button', { name: '关闭' }))
  expect(screen.getByRole('dialog')).toBeInTheDocument()
  expect(onOpenChange).not.toHaveBeenCalledWith(false)
})

it('keeps focus in the top nested dialog', async () => {
  const user = userEvent.setup()
  function Example() {
    return <Dialog open><DialogContent><DialogTitle>外层</DialogTitle><DialogDescription>外层说明</DialogDescription><Dialog><DialogTrigger>打开内层</DialogTrigger><DialogContent><DialogTitle>内层</DialogTitle><DialogDescription>内层说明</DialogDescription><button>内层按钮</button><DialogClose>关闭内层</DialogClose></DialogContent></Dialog></DialogContent></Dialog>
  }
  render(<Example />)
  fireEvent.click(screen.getByText('打开内层'))
  expect(screen.getByRole('dialog', { name: '内层' })).toBeInTheDocument()
  await waitFor(() => expect(within(screen.getByRole('dialog', { name: '内层' })).queryByRole('button', { name: '内层按钮' })).toHaveFocus())
  await user.keyboard('{Escape}')
  expect(screen.queryByRole('dialog', { name: '内层' })).not.toBeInTheDocument()
  await waitFor(() => expect(screen.getByText('打开内层')).toHaveFocus())
  expect(screen.getByRole('dialog', { name: '外层' })).toBeInTheDocument()
  return
})

it('allows controlled close callback', async () => {
  const onOpenChange = vi.fn()
  const user = userEvent.setup()
  render(<Dialog open onOpenChange={onOpenChange}><DialogContent><DialogTitle>内核管理</DialogTitle><DialogDescription>说明</DialogDescription><button>关闭</button></DialogContent></Dialog>)
  await user.keyboard('{Escape}')
  expect(onOpenChange).toHaveBeenCalledWith(false)
})
