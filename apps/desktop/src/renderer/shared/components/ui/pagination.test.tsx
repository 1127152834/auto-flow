import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, it, expect, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { Pagination } from './pagination'
afterEach(cleanup)
it('keeps empty, first and last page boundaries and reports the actual page count', async () => {
 const user = userEvent.setup(), change = vi.fn()
 const {rerender} = render(<Pagination offset={0} limit={20} count={0} total={0} onOffsetChange={change} />)
 expect(screen.getByText('0–0 / 0')).toBeInTheDocument(); expect(screen.getByRole('button',{name:'下一页'})).toBeDisabled()
 rerender(<Pagination offset={20} limit={20} count={3} total={23} onOffsetChange={change} />)
 expect(screen.getByText('21–23 / 23')).toBeInTheDocument(); expect(screen.getByRole('button',{name:'下一页'})).toBeDisabled()
 await user.click(screen.getByRole('button',{name:'上一页'})); expect(change).toHaveBeenCalledWith(0)
})
