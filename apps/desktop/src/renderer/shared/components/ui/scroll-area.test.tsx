import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { createRef } from 'react'
import { ScrollArea } from './scroll-area'
beforeEach(() => vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} }))
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
it('forwards focus/ref/label to the real scroll viewport and keeps content semantic', () => {
  const ref = createRef<HTMLDivElement>()
  render(<ScrollArea ref={ref} aria-label="目录滚动区" className="h-32"><ul><li>第一项</li></ul></ScrollArea>)
  expect(ref.current).toHaveAttribute('data-radix-scroll-area-viewport')
  expect(ref.current).toHaveAccessibleName('目录滚动区')
  ref.current?.focus()
  expect(ref.current).toHaveFocus()
  expect(screen.getByRole('listitem')).toHaveTextContent('第一项')
})
