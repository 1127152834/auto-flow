import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { StrictMode, useState } from 'react'
import { afterEach, expect, it, vi } from 'vitest'
import { ParameterEditor } from './ParameterEditor'
import type { ParameterDefinition } from './policy-types'

afterEach(cleanup)

const parameters: ParameterDefinition[] = [
  { parameterId: '00000000-0000-4000-8000-000000000001', name: '关键词', type: 'string', required: true },
  { parameterId: '00000000-0000-4000-8000-000000000002', name: '页数', type: 'number', required: false, defaultValue: 3 },
  { parameterId: '00000000-0000-4000-8000-000000000003', name: '正文', type: 'boolean', required: false, defaultValue: false },
]

it('adds, renames, reorders and removes without changing existing stable ids', () => {
  const onChange = vi.fn()
  vi.stubGlobal('crypto', { randomUUID: () => '00000000-0000-4000-8000-000000000099' })
  const view = render(<ParameterEditor value={parameters} onChange={onChange} />)

  fireEvent.change(screen.getByLabelText('参数名称 关键词'), { target: { value: '搜索词' } })
  expect(onChange).toHaveBeenLastCalledWith([{ ...parameters[0], name: '搜索词' }, parameters[1], parameters[2]])

  fireEvent.click(screen.getByRole('button', { name: '上移参数 页数' }))
  expect(onChange).toHaveBeenLastCalledWith([parameters[1], parameters[0], parameters[2]])

  fireEvent.click(screen.getByRole('button', { name: '移除参数 页数' }))
  expect(onChange).toHaveBeenLastCalledWith([parameters[0], parameters[2]])

  fireEvent.click(screen.getByRole('button', { name: '新增参数' }))
  expect(onChange).toHaveBeenLastCalledWith([...parameters, {
    parameterId: '00000000-0000-4000-8000-000000000099', name: '', type: 'string', required: false,
  }])
  view.unmount()
  vi.unstubAllGlobals()
})

it('preserves omitted, false, zero, empty string and null defaults distinctly', () => {
  const values: ParameterDefinition[] = [
    { parameterId: 'a', name: '省略', type: 'string', required: false },
    { parameterId: 'b', name: '空串', type: 'string', required: false, defaultValue: '' },
    { parameterId: 'c', name: '零', type: 'number', required: false, defaultValue: 0 },
    { parameterId: 'd', name: '假', type: 'boolean', required: false, defaultValue: false },
    { parameterId: 'e', name: '空值', type: 'string', required: false, defaultValue: null },
  ]
  render(<ParameterEditor value={values} onChange={vi.fn()} />)
  expect(screen.getByLabelText('默认值 省略')).toHaveAttribute('data-default-presence', 'omitted')
  expect(screen.getByLabelText('默认值 空串')).toHaveAttribute('data-default-presence', 'provided')
  expect(screen.getByLabelText('默认值 零')).toHaveValue('0')
  expect(screen.getByLabelText('默认值 假')).toHaveAttribute('data-choice-value', 'false')
  expect(screen.getByLabelText('默认值 空值')).toHaveAttribute('data-default-presence', 'null')
})

it('keeps an invalid numeric draft visible without coercing or emitting it', () => {
  const onChange = vi.fn()
  render(<ParameterEditor value={[parameters[1]]} onChange={onChange} />)
  const input = screen.getByLabelText('默认值 页数')
  fireEvent.change(input, { target: { value: '3x' } })
  expect(input).toHaveValue('3x')
  expect(screen.getByRole('alert')).toHaveTextContent('请输入有效数字')
  expect(onChange).not.toHaveBeenCalled()
})

it('reports an invalid draft to the parent save gate and reset restores the controlled value', () => {
  function Fixture() {
    const [draft, setDraft] = useState({ dirty: false, valid: true })
    const [resetKey, setResetKey] = useState(0)
    return <><ParameterEditor value={[parameters[1]]} onChange={() => undefined} resetKey={resetKey} onDraftStateChange={setDraft}/><button disabled={!draft.dirty || !draft.valid}>保存</button><button onClick={() => setResetKey(key => key + 1)}>取消</button></>
  }
  render(<Fixture />)
  fireEvent.change(screen.getByLabelText('默认值 页数'), { target: { value: 'wrong' } })
  expect(screen.getByRole('button', { name: '保存' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: '取消' }))
  expect(screen.getByLabelText('默认值 页数')).toHaveValue('3')
  expect(screen.queryByText('请输入有效数字')).toBeNull()
})

it('keeps row A invalid and the parent blocked while row B changes and moves', () => {
  function Fixture() {
    const [items, setItems] = useState(parameters.slice(0, 2))
    const [draft, setDraft] = useState({ dirty: false, valid: true })
    return <><ParameterEditor value={items} onChange={setItems} onDraftStateChange={setDraft}/><button disabled={!draft.valid}>保存</button></>
  }
  render(<Fixture />)
  fireEvent.change(screen.getByLabelText('默认值 页数'), { target: { value: 'wrong' } })
  fireEvent.change(screen.getByLabelText('参数名称 关键词'), { target: { value: '搜索词' } })
  expect(screen.getByLabelText('默认值 页数')).toHaveValue('wrong')
  fireEvent.click(screen.getByRole('button', { name: '上移参数 页数' }))
  expect(screen.getByLabelText('默认值 页数')).toHaveValue('wrong')
  expect(screen.getByRole('button', { name: '保存' })).toBeDisabled()
})

it.each([false, true])('keeps a valid decimal raw value with controlled echoes (StrictMode=%s)', async strict => {
  function Fixture() {
    const [items, setItems] = useState([parameters[1]])
    return <ParameterEditor value={items} onChange={setItems}/>
  }
  render(strict ? <StrictMode><Fixture /></StrictMode> : <Fixture />)
  const input = screen.getByLabelText('默认值 页数')
  await userEvent.setup().clear(input)
  const user = userEvent.setup()
  await user.type(input, '2.')
  expect(input).toHaveValue('2.')
  await user.type(input, '5')
  expect(input).toHaveValue('2.5')
  expect(input).not.toHaveAttribute('aria-invalid', 'true')
  expect(screen.queryByRole('alert')).toBeNull()
})

it('does not notify again merely because an inline callback gets a new identity', () => {
  let notifications = 0
  function Fixture() {
    const [, setState] = useState({ dirty: false, valid: true })
    return <ParameterEditor value={parameters} onChange={() => undefined} onDraftStateChange={state => { notifications += 1; setState({ ...state }) }}/>
  }
  render(<Fixture />)
  expect(notifications).toBe(1)
})

it('clears stale numeric drafts on explicit null and external value changes', () => {
  const onChange = vi.fn()
  const view = render(<ParameterEditor value={[parameters[1]]} onChange={onChange} />)
  fireEvent.change(screen.getByLabelText('默认值 页数'), { target: { value: 'wrong' } })
  fireEvent.click(screen.getByRole('button', { name: '设为空值' }))
  view.rerender(<ParameterEditor value={[{ ...parameters[1], defaultValue: null }]} onChange={onChange} />)
  expect(screen.getByLabelText('默认值 页数')).toHaveValue('')
  view.rerender(<ParameterEditor value={[{ ...parameters[1], defaultValue: 8 }]} onChange={onChange} />)
  expect(screen.getByLabelText('默认值 页数')).toHaveValue('8')
})

it('shows a type mismatch without silently converting the existing default', () => {
  render(<ParameterEditor value={[{ ...parameters[1], type: 'string', defaultValue: 3 }]} onChange={vi.fn()} />)
  expect(screen.getByLabelText('默认值 页数')).toHaveValue('3')
  expect(screen.getByRole('alert')).toHaveTextContent('默认值类型与参数类型不一致')
  expect(screen.getByLabelText('默认值 页数')).toHaveAccessibleDescription('默认值类型与参数类型不一致，请修正或清除')
})

it('renders supplied field errors and disables every edit action', () => {
  const onChange = vi.fn()
  render(<ParameterEditor value={parameters} onChange={onChange} disabled errors={{ [`${parameters[0].parameterId}.name`]: '参数名称重复' }} />)
  expect(screen.getByRole('alert')).toHaveTextContent('参数名称重复')
  expect(screen.getByLabelText('参数名称 关键词')).toHaveAccessibleDescription('参数名称重复')
  for (const control of within(screen.getByRole('region', { name: '启动参数列表' })).getAllByRole('button')) expect(control).toBeDisabled()
  expect(screen.getByLabelText('参数名称 关键词')).toBeDisabled()
})

it('edits optional parameter descriptions without providing a default or changing identity', () => {
  const onChange = vi.fn()
  render(<ParameterEditor value={[parameters[0]]} onChange={onChange} />)
  fireEvent.change(screen.getByLabelText('参数说明 关键词'), { target: { value: '用于筛选资料' } })
  expect(onChange).toHaveBeenCalledWith([{ ...parameters[0], description: '用于筛选资料' }])
})
