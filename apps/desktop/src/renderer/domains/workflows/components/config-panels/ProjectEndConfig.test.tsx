import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ProjectEndConfig } from './ProjectEndConfig'
import { useProjectInputs } from '../../project-inputs'
import { useSignatureStore } from '../../hooks/stores/signatureStore'

vi.mock('../../api/config', () => ({ getStudioOpenContext: () => ({ projectId: 'project-test' }) }))
vi.mock('../controls/variable-input', () => ({ VariableInput: ({ value, onChange, ...rest }: { value: string; onChange: (value: string) => void }) => <input aria-label={(rest as { 'aria-label'?: string })['aria-label'] ?? '额外记录目标'} value={value} onChange={event => onChange(event.target.value)} /> }))

const plan = (inputs: unknown[]) => useProjectInputs.setState({ automation: { inputPlan: { inputs } } as never })

describe('项目 End 配置', () => {
  afterEach(cleanup)
  beforeEach(() => { useProjectInputs.setState({ automation: null }); useSignatureStore.getState().reset() })
  it('默认不保留，显式启用保存及关联配置', () => {
    const onChange = vi.fn()
    render(<ProjectEndConfig data={{ moduleType: 'project_end', label: '项目结束' }} onChange={onChange} />)
    expect(screen.queryByLabelText('保存方式')).toBeNull()
    fireEvent.click(screen.getByLabelText('保留当前身份的登录状态'))
    expect(onChange).toHaveBeenCalledWith('retainEnvironment', true)
  })
  it('业务结果可选成功、失败或按变量，并回显变量', () => {
    const onChange = vi.fn()
    const { rerender } = render(<ProjectEndConfig data={{ moduleType: 'project_end', label: '项目结束', businessResult: '{login_result}' }} onChange={onChange} />)
    expect((screen.getByLabelText('结果变量') as HTMLInputElement).value).toBe('{login_result}')
    rerender(<ProjectEndConfig data={{ moduleType: 'project_end', label: '项目结束', businessResult: 'failed' }} onChange={onChange} />)
    expect(screen.queryByLabelText('结果变量')).toBeNull()
    fireEvent.keyDown(screen.getByLabelText('业务结果'), { key: 'ArrowDown' })
    fireEvent.keyDown(screen.getByRole('option', { name: '按变量' }), { key: 'Enter' })
    expect(onChange).toHaveBeenCalledWith('businessResult', '')
  })

  it('说明试跑时保留登录状态会被拒绝', () => {
    render(<ProjectEndConfig data={{ moduleType: 'project_end', label: '项目结束' }} onChange={vi.fn()} />)
    expect(screen.getByText(/试跑（仅预览）时保留登录状态会被拒绝/)).toBeTruthy()
  })

  it('用勾选关联输入分组，显示分组名称，且不再有逗号文本框', () => {
    useSignatureStore.getState().load({ inputs: [{ key: 'account', name: '登录账号', fields: [] }] })
    plan([{ inputId: 'in-1', alias: '账号表', signatureInput: 'account' }, { inputId: 'in-2', alias: '代理表' }])
    const onChange = vi.fn()
    render(<ProjectEndConfig data={{ moduleType: 'project_end', label: '项目结束', retainEnvironment: true, inputIds: ['in-1'] }} onChange={onChange} />)
    expect(screen.queryByLabelText(/逗号分隔/)).toBeNull()
    expect((screen.getByLabelText('登录账号') as HTMLInputElement).checked).toBe(true)
    expect((screen.getByLabelText('代理表') as HTMLInputElement).checked).toBe(false)
    expect((screen.getByLabelText('全部可写输入') as HTMLInputElement).checked).toBe(false)
    fireEvent.click(screen.getByLabelText('代理表'))
    expect(onChange).toHaveBeenCalledWith('inputIds', ['in-1', 'in-2'])
    fireEvent.click(screen.getByLabelText('登录账号'))
    expect(onChange).toHaveBeenCalledWith('inputIds', [])
  })

  it('未设置时表示全部输入，勾选全部可写输入写回空值，取消则为不关联', () => {
    plan([{ inputId: 'in-1', alias: '账号表' }])
    const onChange = vi.fn()
    const { rerender } = render(<ProjectEndConfig data={{ moduleType: 'project_end', label: '项目结束', retainEnvironment: true }} onChange={onChange} />)
    expect((screen.getByLabelText('全部可写输入') as HTMLInputElement).checked).toBe(true)
    expect((screen.getByLabelText('账号表') as HTMLInputElement).checked).toBe(true)
    fireEvent.click(screen.getByLabelText('全部可写输入'))
    expect(onChange).toHaveBeenCalledWith('inputIds', [])
    rerender(<ProjectEndConfig data={{ moduleType: 'project_end', label: '项目结束', retainEnvironment: true, inputIds: [] }} onChange={onChange} />)
    fireEvent.click(screen.getByLabelText('全部可写输入'))
    expect(onChange).toHaveBeenCalledWith('inputIds', null)
    fireEvent.click(screen.getByLabelText('账号表'))
    expect(onChange).toHaveBeenCalledWith('inputIds', ['in-1'])
  })

  it('允许显式授权替换', () => {
    const onChange = vi.fn()
    render(<ProjectEndConfig data={{ moduleType: 'project_end', label: '项目结束', retainEnvironment: true }} onChange={onChange} />)
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
