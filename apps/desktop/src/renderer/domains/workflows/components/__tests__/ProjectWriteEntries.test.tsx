import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'

afterEach(cleanup)
import { parseProjectWriteDrag, projectWriteDefaults } from '../../lib/moduleCatalog'
import { ProjectWriteEntries } from '../ProjectWriteEntries'

it('lists the four write-back entries and drags a payload that resolves to a preset project_data node', () => {
  render(<ProjectWriteEntries query="" />)
  for (const label of ['更新当前记录', '设置状态', '新增记录', '查询记录']) expect(screen.getByText(label)).toBeTruthy()
  const store: Record<string, string> = {}
  fireEvent.dragStart(screen.getByText('设置状态'), { dataTransfer: { setData: (k: string, v: string) => { store[k] = v }, effectAllowed: '' } })
  const entry = parseProjectWriteDrag(store['application/reactflow'])
  expect(projectWriteDefaults(entry!).operation).toBe('setRecordStatus')
  expect(parseProjectWriteDrag('wait')).toBeNull()
  expect(parseProjectWriteDrag('{"type":"custom_module","moduleId":"x"}')).toBeNull()
})

it('filters entries by the search text', () => {
  render(<ProjectWriteEntries query="新增" />)
  expect(screen.getByText('新增记录')).toBeTruthy()
  expect(screen.queryByText('设置状态')).toBeNull()
})
