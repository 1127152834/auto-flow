import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it } from 'vitest'
import { ModuleSidebar } from '../components/ModuleSidebar'
import { useLayoutStore } from '../hooks/stores/layoutStore'
import { useProjectInputs, type ProjectAutomation } from '../project-inputs'

beforeEach(() => { localStorage.clear(); useLayoutStore.getState().resetLayout() })
afterEach(() => { cleanup(); useProjectInputs.setState({ automation: null }) })

const search = (text: string) => fireEvent.change(screen.getByPlaceholderText('搜索模块/拼音/英文...'), { target: { value: text } })

it('a search that only matches a write-back entry shows it and no empty state', () => {
  useProjectInputs.setState({ automation: { automationId: 'a', projectId: 'p' } as unknown as ProjectAutomation })
  render(<ModuleSidebar />)
  search('SETRECORDSTATUS')
  expect(screen.getByText('设置状态')).toBeTruthy()
  expect(screen.queryByText('未找到匹配的模块')).toBeNull()
})

it('outside a project there are no write-back entries and the empty state is shown', () => {
  render(<ModuleSidebar />)
  search('SETRECORDSTATUS')
  expect(screen.queryByTestId('project-write-entries')).toBeNull()
  expect(screen.getByText('未找到匹配的模块')).toBeTruthy()
})
