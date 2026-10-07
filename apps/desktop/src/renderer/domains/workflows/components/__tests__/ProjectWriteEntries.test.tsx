import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it } from 'vitest'
import { parseProjectWriteDrag, projectWriteDefaults } from '../../lib/moduleCatalog'
import { useProjectInputs, type ProjectAutomation } from '../../project-inputs'
import { ProjectWriteEntries, useProjectWriteEntries } from '../ProjectWriteEntries'

const labels = ['更新当前记录', '设置状态', '新增记录', '查询记录']
function Entries({ query }: { query: string }) {
  return <ProjectWriteEntries entries={useProjectWriteEntries(query)} />
}
beforeEach(() => useProjectInputs.setState({ automation: { automationId: 'a', projectId: 'p' } as unknown as ProjectAutomation }))
afterEach(() => { cleanup(); useProjectInputs.setState({ automation: null }) })

it('lists the four write-back entries and drags a payload that resolves to a preset project_data node', () => {
  render(<Entries query="" />)
  for (const label of labels) expect(screen.getByText(label)).toBeTruthy()
  const store: Record<string, string> = {}
  fireEvent.dragStart(screen.getByText('设置状态'), { dataTransfer: { setData: (k: string, v: string) => { store[k] = v }, effectAllowed: '' } })
  const entry = parseProjectWriteDrag(store['application/reactflow'])
  expect(projectWriteDefaults(entry!).operation).toBe('setRecordStatus')
  expect(parseProjectWriteDrag('wait')).toBeNull()
  expect(parseProjectWriteDrag('{"type":"custom_module","moduleId":"x"}')).toBeNull()
})

it('filters entries with the shared search: Chinese, pinyin, initials, English, any case', () => {
  const found = (query: string) => { cleanup(); render(<Entries query={query} />); return labels.filter(label => screen.queryByText(label)) }
  expect(found('新增')).toEqual(['新增记录'])
  expect(found('xinzeng')).toEqual(['新增记录'])
  expect(found('CXJL')).toEqual(['查询记录'])
  expect(found('SETRECORDSTATUS')).toEqual(['设置状态'])
  expect(found('项目数据')).toEqual(labels)
  expect(found('完全不存在')).toEqual([])
})

it('is hidden when the workflow was not opened from a project', () => {
  useProjectInputs.setState({ automation: null })
  render(<Entries query="" />)
  expect(screen.queryByTestId('project-write-entries')).toBeNull()
})
