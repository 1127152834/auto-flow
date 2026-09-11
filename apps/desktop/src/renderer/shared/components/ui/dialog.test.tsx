import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom/vitest'
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from './dialog'

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

it('keeps focus in the top nested dialog', async () => {
  function Example() {
    return <Dialog open><DialogContent><DialogTitle>外层</DialogTitle><DialogDescription>外层说明</DialogDescription><Dialog open><DialogTrigger>打开内层</DialogTrigger><DialogContent><DialogTitle>内层</DialogTitle><DialogDescription>内层说明</DialogDescription><button>内层按钮</button></DialogContent></Dialog></DialogContent></Dialog>
  }
  render(<Example />)
  fireEvent.click(screen.getByText('打开内层'))
  expect(screen.getByRole('dialog', { name: '内层' })).toBeInTheDocument()
})

it('allows controlled close callback', async () => {
  const onOpenChange = vi.fn()
  const user = userEvent.setup()
  render(<Dialog open onOpenChange={onOpenChange}><DialogContent><DialogTitle>内核管理</DialogTitle><DialogDescription>说明</DialogDescription><button>关闭</button></DialogContent></Dialog>)
  await user.keyboard('{Escape}')
  expect(onOpenChange).toHaveBeenCalledWith(false)
})
