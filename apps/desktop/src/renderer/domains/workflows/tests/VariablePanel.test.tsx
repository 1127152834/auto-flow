import '@testing-library/jest-dom/vitest'
import { chooseOption, choiceTestEnvironment } from '../../../shared/testing/choice-user'

choiceTestEnvironment()
import { useState } from 'react'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { WorkflowVariable } from '../types'
import { VariablePanel } from '../components/VariablePanel'

afterEach(cleanup)

function Harness({ initial = [] }: { initial?: WorkflowVariable[] }) {
  const [variables, setVariables] = useState(initial)
  const [visible, setVisible] = useState(true)
  return <>{visible ? <VariablePanel variables={variables} onChange={setVariables} onRename={(oldName, name) => setVariables((old) => old.map((item) => item.name === oldName ? { ...item, name } : item))} onDelete={(name) => setVariables((old) => old.filter((item) => item.name !== name))} /> : null}<button onClick={() => setVisible((old) => !old)}>切换面板</button><output data-testid="variables">{JSON.stringify(variables)}</output></>
}

it('adds distinct names and edits all five variable types', async () => {
  const user = userEvent.setup()
  render(<Harness />)
  await user.click(screen.getByRole('button', { name: '添加变量' }))
  await user.type(screen.getByLabelText('初始值'), 'hello')
  expect(screen.getByTestId('variables')).toHaveTextContent('"value":"hello"')
  await chooseOption(user, screen.getByLabelText('类型'), 'number')
  expect(screen.getByLabelText('初始值')).toHaveValue('hello')
  fireEvent.change(screen.getByLabelText('初始值'), { target: { value: '2.5' } })
  expect(screen.getByTestId('variables')).toHaveTextContent('"value":2.5')
  await chooseOption(user, screen.getByLabelText('类型'), 'boolean')
  await chooseOption(user, screen.getByLabelText('初始值'), 'false')
  expect(screen.getByTestId('variables')).toHaveTextContent('"value":false')
  await chooseOption(user, screen.getByLabelText('类型'), 'array')
  fireEvent.change(screen.getByLabelText('初始值'), { target: { value: '[1, 2]' } })
  expect(screen.getByTestId('variables')).toHaveTextContent('"value":[1,2]')
  await chooseOption(user, screen.getByLabelText('类型'), 'object')
  fireEvent.change(screen.getByLabelText('初始值'), { target: { value: '{"ok":true}' } })
  expect(screen.getByTestId('variables')).toHaveTextContent('"value":{"ok":true}')
  await user.click(screen.getByRole('button', { name: '添加变量' }))
  expect(screen.getByTestId('variables')).toHaveTextContent('"name":"variable_2"')
})

it('preserves invalid JSON in the document and restores it after the panel remounts', async () => {
  const user = userEvent.setup()
  render(<Harness initial={[{ name: 'data', type: 'object', value: {} }]} />)
  fireEvent.change(screen.getByLabelText('初始值'), { target: { value: '{"unfinished":' } })
  expect(screen.getByLabelText('初始值')).toHaveAttribute('aria-invalid', 'true')
  expect(screen.getByTestId('variables')).toHaveTextContent('"value":"{\\"unfinished\\":"')
  await user.click(screen.getByRole('button', { name: '切换面板' }))
  await user.click(screen.getByRole('button', { name: '切换面板' }))
  expect(screen.getByLabelText('初始值')).toHaveValue('{"unfinished":')
  fireEvent.change(screen.getByLabelText('初始值'), { target: { value: '{"finished": 1}' } })
  expect(screen.getByLabelText('初始值')).not.toHaveAttribute('aria-invalid', 'true')
  expect(screen.getByTestId('variables')).toHaveTextContent('"value":{"finished":1}')
})

it('commits a valid rename once and keeps invalid names visible without replacing existing variables', async () => {
  const user = userEvent.setup()
  const rename = vi.fn()
  render(<VariablePanel variables={[{ name: 'first', type: 'string', value: '' }, { name: 'second', type: 'string', value: '' }]} onChange={vi.fn()} onRename={rename} onDelete={vi.fn()} />)
  const first = within(screen.getByLabelText('变量 first'))
  await user.clear(first.getByLabelText('变量名'))
  await user.type(first.getByLabelText('变量名'), 'second')
  await user.tab()
  expect(first.getByLabelText('变量名')).toHaveValue('second')
  expect(first.getByRole('alert')).toHaveTextContent('已存在同名变量')
  expect(rename).not.toHaveBeenCalled()
  await user.clear(first.getByLabelText('变量名'))
  await user.type(first.getByLabelText('变量名'), 'renamed{Enter}')
  expect(rename).toHaveBeenCalledOnce()
  expect(rename).toHaveBeenCalledWith('first', 'renamed')
})

it('delegates deletion to the document coordinator and respects the workspace lock', async () => {
  const user = userEvent.setup()
  const remove = vi.fn()
  const props = { variables: [{ name: 'target', type: 'string' as const, value: 'saved' }], onChange: vi.fn(), onRename: vi.fn(), onDelete: remove }
  const { rerender } = render(<VariablePanel {...props} />)
  await user.click(screen.getByRole('button', { name: '删除变量 target' }))
  expect(remove).toHaveBeenCalledWith('target')
  expect(screen.getByLabelText('初始值')).toHaveValue('saved')
  rerender(<VariablePanel {...props} disabled />)
  expect(screen.getByLabelText('变量名')).toBeDisabled()
  expect(screen.getByLabelText('初始值')).toBeDisabled()
  expect(screen.getByRole('button', { name: '删除变量 target' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '添加变量' })).toBeDisabled()
})
