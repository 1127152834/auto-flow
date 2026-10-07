import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { useProjectInputs, type ProjectAutomation } from '../../project-inputs'
import { ModulePicker } from '../BlockFlowView'

afterEach(() => { cleanup(); useProjectInputs.setState({ automation: null }) })

it('offers the four write-back entries inside a project and adds a preset project_data node', () => {
  useProjectInputs.setState({ automation: { automationId: 'a', projectId: 'p' } as unknown as ProjectAutomation })
  const pick = vi.fn()
  render(<ModulePicker x={0} y={0} onPick={pick} onClose={vi.fn()} />)
  for (const label of ['更新当前记录', '设置状态', '新增记录', '查询记录']) expect(screen.getByText(label)).toBeTruthy()
  fireEvent.click(screen.getByText('设置状态'))
  expect(pick).toHaveBeenCalledWith('project_data', expect.objectContaining({ operation: 'setRecordStatus' }))
  fireEvent.change(screen.getByPlaceholderText('搜索模块（支持拼音）'), { target: { value: 'xinzeng' } })
  expect(screen.queryByText('设置状态')).toBeNull()
  expect(screen.getByText('新增记录')).toBeTruthy()
  expect(screen.queryByText('无匹配模块')).toBeNull()
})

it('hides them outside a project', () => {
  render(<ModulePicker x={0} y={0} onPick={vi.fn()} onClose={vi.fn()} />)
  expect(screen.queryByText('设置状态')).toBeNull()
})
