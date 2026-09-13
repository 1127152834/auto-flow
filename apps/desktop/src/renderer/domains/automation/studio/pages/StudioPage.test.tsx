import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { StudioPage } from './StudioPage'

it('shows the studio shell and adds a catalog node to the canvas', () => {
  render(<StudioPage />)

  expect(screen.getByRole('heading', { name: '网页自动化' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: '点击元素' })).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: /等待/ }).firstChild ?? screen.getByText('等待'))

  expect(screen.getByText('4 个节点 · 当前编辑会话')).toBeInTheDocument()
})

