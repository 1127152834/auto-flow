import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, it, expect } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { Tabs, TabsList, TabsTrigger, TabsContent } from './tabs'
afterEach(cleanup)
it('keeps focus and selection separate until keyboard activation', async () => {
  const user = userEvent.setup()
  render(<Tabs defaultValue="a"><TabsList aria-label="页签"><TabsTrigger value="a">甲</TabsTrigger><TabsTrigger value="b">乙</TabsTrigger></TabsList><TabsContent value="a">第一面板</TabsContent><TabsContent value="b">第二面板</TabsContent></Tabs>)
  screen.getByRole('tab', { name: '甲' }).focus()
  await user.keyboard('{ArrowRight}')
  expect(screen.getByRole('tab', { name: '乙' })).toHaveFocus()
  expect(screen.getByRole('tab', { name: '甲' })).toHaveAttribute('aria-selected','true')
  await user.keyboard('{Enter}')
  expect(screen.getByRole('tabpanel')).toHaveTextContent('第二面板')
})
