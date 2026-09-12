import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom/vitest'
import { createRef, useState } from 'react'
import { SearchInput } from './search-input'
afterEach(cleanup)
it('clears once, restores input focus and does not submit', async () => {
  const cleared = vi.fn(), submitted = vi.fn(e => e.preventDefault()), ref = createRef<HTMLInputElement>()
  function Case() { const [value, setValue] = useState('本地'); return <form onSubmit={submitted}><SearchInput ref={ref} aria-label="搜索配置" value={value} onChange={e => setValue(e.target.value)} onClear={() => { cleared(); setValue('') }} /></form> }
  render(<Case />)
  await userEvent.click(screen.getByRole('button', { name: '清除搜索' }))
  expect(cleared).toHaveBeenCalledTimes(1)
  expect(ref.current).toHaveValue('')
  expect(ref.current).toHaveFocus()
  expect(submitted).not.toHaveBeenCalled()
  expect(screen.queryByRole('button', { name: '清除搜索' })).not.toBeInTheDocument()
})
it('read-only and disabled search do not expose a clear action; loading retains value', () => {
  render(<><SearchInput aria-label="只读搜索" value="保留" onClear={vi.fn()} readOnly /><SearchInput aria-label="禁用搜索" value="保留" onClear={vi.fn()} disabled loading /></>)
  expect(screen.queryByRole('button', { name: '清除搜索' })).not.toBeInTheDocument()
  expect(screen.getByRole('searchbox', { name: '禁用搜索' })).toHaveValue('保留')
  expect(screen.getByRole('searchbox', { name: '禁用搜索' })).toHaveAttribute('aria-busy', 'true')
})
