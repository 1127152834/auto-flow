import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom/vitest'
import { Dialog, DialogTrigger, DialogContent, DialogTitle } from './dialog'
import { AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogTitle, AlertDialogDescription, AlertDialogCancel } from './alert-dialog'

afterEach(cleanup)
it('assigns three distinct modal layers and a popup host inside each focus scope', async () => {
  const user = userEvent.setup()
  render(<Dialog><DialogTrigger>新建配置</DialogTrigger><DialogContent aria-describedby={undefined}>
    <DialogTitle>配置</DialogTitle><Dialog><DialogTrigger>管理内核</DialogTrigger><DialogContent aria-describedby={undefined}>
      <DialogTitle>内核</DialogTitle><AlertDialog><AlertDialogTrigger>删除内核</AlertDialogTrigger><AlertDialogContent>
        <AlertDialogTitle>确认删除</AlertDialogTitle><AlertDialogDescription>只用于验证，不删除文件。</AlertDialogDescription><AlertDialogCancel>取消</AlertDialogCancel>
      </AlertDialogContent></AlertDialog>
    </DialogContent></Dialog>
  </DialogContent></Dialog>)
  await user.click(screen.getByRole('button', { name: '新建配置' }))
  const outer = screen.getByRole('dialog', { name: '配置' })
  expect(outer).toHaveAttribute('data-overlay-depth', '0')
  expect(outer.querySelector('[data-overlay-host]')).not.toBeNull()
  await user.click(screen.getByRole('button', { name: '管理内核' }))
  const inner = screen.getByRole('dialog', { name: '内核' })
  expect(inner).toHaveAttribute('data-overlay-depth', '1')
  await user.click(screen.getByRole('button', { name: '删除内核' }))
  expect(screen.getByRole('alertdialog')).toHaveAttribute('data-overlay-depth', '2')
  expect(screen.getByRole('button', { name: '取消' })).toHaveFocus()
  await user.keyboard('{Escape}')
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '删除内核' })).toHaveFocus()
  await user.keyboard('{Escape}')
  expect(screen.getByRole('button', { name: '管理内核' })).toHaveFocus()
})
