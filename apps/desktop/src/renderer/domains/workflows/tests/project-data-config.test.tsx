import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { ProjectDataConfig } from '../components/config-panels/ProjectDataConfig'
import type { NodeData } from '../editor-store'
vi.mock('../api', () => ({ apiRequest: vi.fn(async () => ({ success: true, data: { items: [] } })) }))
it('keeps task authority out of user arguments and supports a result variable', async () => {
  const change = vi.fn()
  render(<ProjectDataConfig data={{ label: '项目数据', moduleType: 'project_data', operation: 'createRecord', arguments: {}, variableName: 'saved' } as NodeData} onChange={change} />)
  const editor = screen.getByLabelText('操作参数（JSON，值可引用变量）')
  fireEvent.change(editor, { target: { value: '{"projectId":"forged"}' } }); fireEvent.blur(editor)
  expect((await screen.findByRole('alert')).textContent).toContain('不能在参数中覆盖')
  expect(change).toHaveBeenCalledWith('argumentsValid', false)
  expect(change.mock.calls.some(([key]) => key === 'arguments')).toBe(false)
  fireEvent.change(editor, { target: { value: '{"values":{"field":"{browser_result}"}}' } }); fireEvent.blur(editor)
  await waitFor(() => expect(change).toHaveBeenCalledWith('arguments', { values: { field: '{browser_result}' } }))
})
