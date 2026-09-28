import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ProjectEndConfig } from './ProjectEndConfig'

vi.mock('../../api/config', () => ({ getStudioOpenContext: () => ({ projectId: 'project-test' }) }))
vi.mock('../controls/variable-input', () => ({ VariableInput: ({ value, onChange }: { value: string; onChange: (value: string) => void }) => <input aria-label="额外记录目标" value={value} onChange={event => onChange(event.target.value)} /> }))

describe('项目 End 配置', () => {
  it('默认不保留，显式启用保存及关联配置', () => {
    const onChange = vi.fn()
    render(<ProjectEndConfig data={{ moduleType: 'project_end', label: '项目结束' }} onChange={onChange} />)
    expect(screen.queryByLabelText('保存方式')).toBeNull()
    fireEvent.click(screen.getByLabelText('保留当前环境并关联记录'))
    expect(onChange).toHaveBeenCalledWith('retainEnvironment', true)
  })
  it('允许排除输入、选择写入输出并显式授权替换', () => {
    const onChange = vi.fn()
    render(<ProjectEndConfig data={{ moduleType: 'project_end', label: '项目结束', retainEnvironment: true }} onChange={onChange} />)
    fireEvent.change(screen.getByLabelText('关联输入标识（逗号分隔）'), { target: { value: 'account' } })
    expect(onChange).toHaveBeenCalledWith('inputIds', ['account'])
    fireEvent.change(screen.getByLabelText('关联输入标识（逗号分隔）'), { target: { value: '' } })
    expect(onChange).toHaveBeenCalledWith('inputIds', [])
    fireEvent.click(screen.getByLabelText('允许替换所选记录已有的环境关联'))
    expect(onChange).toHaveBeenCalledWith('replaceAllowed', true)
    expect(screen.getByText(/零目标时只保存环境/)).toBeTruthy()
  })

  it('准确回显静态记录目标并以数组形状清空', () => {
    const onChange = vi.fn()
    const targets = [{ recordRef: { projectId: 'project-test', tableId: 'accounts', recordId: 'row-1' } }]
    render(<ProjectEndConfig data={{ moduleType: 'project_end', label: '项目结束', retainEnvironment: true, recordTargets: targets }} onChange={onChange} />)

    expect(JSON.parse((screen.getByRole('textbox', { name: '静态记录目标' }) as HTMLTextAreaElement).value)).toEqual(targets)
    fireEvent.click(screen.getByRole('button', { name: '清空记录目标' }))
    expect(onChange).toHaveBeenCalledWith('recordTargets', [])
    expect(onChange).not.toHaveBeenCalledWith('recordTargets', expect.any(String))
  })
})
