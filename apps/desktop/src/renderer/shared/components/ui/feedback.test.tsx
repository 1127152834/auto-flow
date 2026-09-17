import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, it, expect } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { Progress } from './progress'
import { Alert } from './alert'
import { EmptyState } from './empty-state'
afterEach(cleanup)
it('distinguishes unknown progress from a measured percentage',()=>{
 const {rerender}=render(<Progress value={null} aria-label="下载" />)
 expect(screen.getByRole('progressbar')).not.toHaveAttribute('aria-valuenow')
 rerender(<Progress value={62} aria-label="下载" />)
 expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow','62')
})
it('shows errors alongside cached content and provides an empty-state action',()=>{
 render(<><Alert tone="error" title="刷新失败">已有数据仍可用</Alert><p>缓存记录</p><EmptyState title="没有匹配项" action={<button>清除搜索</button>} /></>)
 expect(screen.getByRole('alert')).toHaveTextContent('刷新失败'); expect(screen.getByText('缓存记录')).toBeVisible(); expect(screen.getByRole('button')).toHaveTextContent('清除搜索')
})
