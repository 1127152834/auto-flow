import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useSignatureStore } from '../../hooks/stores/signatureStore'
import { VariableInput } from './variable-input'

const tagInputLoads = vi.hoisted(() => ({ count: 0 }))
vi.mock('./TagInput', async importOriginal => {
  tagInputLoads.count += 1
  return importOriginal()
})

beforeEach(() => {
  localStorage.clear()
  window.history.replaceState(null, '', '/')
  useSignatureStore.getState().load({ inputs: [{ key: 'account', name: '账号', fields: [{ key: 'email', name: '邮箱', type: 'string' }] }] })
})
afterEach(() => {
  cleanup()
  vi.unstubAllEnvs()
  useSignatureStore.getState().reset()
})

describe('VariableInput 开关关闭（默认）', () => {
  it('不会加载标签输入框模块（编辑器代码不进入默认路径）', async () => {
    const { container } = render(<VariableInput value="{input.account.email}" onChange={() => {}} placeholder="填写" />)
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 50)) })
    expect(container.querySelector('.cm-editor')).toBeNull()
    expect(tagInputLoads.count).toBe(0)
  })

  it('仍是原生输入框，受控 value 与 fireEvent.change 照旧', () => {
    const onChange = vi.fn()
    const { container } = render(<VariableInput value="abc" onChange={onChange} placeholder="填写" id="f" />)
    expect(container.querySelector('.cm-editor')).toBeNull()
    const input = screen.getByPlaceholderText('填写') as HTMLInputElement
    expect(input.value).toBe('abc')
    expect(input.id).toBe('f')
    fireEvent.change(input, { target: { value: 'abcd' } })
    expect(onChange).toHaveBeenCalledWith('abcd')
  })

  it('多行仍是 textarea，ref 仍指向原生元素', () => {
    const ref = { current: null as HTMLInputElement | HTMLTextAreaElement | null }
    render(<VariableInput ref={ref} value="" onChange={() => {}} multiline rows={4} placeholder="多行" />)
    expect(ref.current?.tagName).toBe('TEXTAREA')
  })
})

const editorOf = (container: HTMLElement) => waitFor(() => {
  const editor = container.querySelector('.cm-editor')
  expect(editor).not.toBeNull()
  return editor as HTMLElement
})

describe('VariableInput 开关开启', () => {
  it('编辑器块加载前仍是可输入的原生输入框，加载后换成标签输入框', async () => {
    localStorage.setItem('autoflow.flags.tagInput', 'true')
    const onChange = vi.fn()
    const { container } = render(<VariableInput value="{input.account.email}" onChange={onChange} placeholder="填写" id="f" aria-label="邮箱" />)
    if (!container.querySelector('.cm-editor')) {
      const input = screen.getByPlaceholderText('填写') as HTMLInputElement
      fireEvent.change(input, { target: { value: '{input.account.email}x' } })
      expect(onChange).toHaveBeenCalledWith('{input.account.email}x')
    }
    await editorOf(container)
    expect(container.querySelector('input, textarea')).toBeNull()
    expect(container.querySelector('.cm-ref-chip')?.textContent).toBe('账号·邮箱')
    expect(container.querySelector('.cm-content')?.id).toBe('f')
    expect(container.querySelector('.cm-content')?.getAttribute('aria-label')).toBe('邮箱')
  })

  it('环境变量也能打开', async () => {
    vi.stubEnv('VITE_FLAG_TAG_INPUT', '1')
    const { container } = render(<VariableInput value="" onChange={() => {}} />)
    await editorOf(container)
  })

  it('密码类 type 与变量名输入框（disableVariableHint）保持原生输入框', async () => {
    localStorage.setItem('autoflow.flags.tagInput', 'true')
    const password = render(<VariableInput value="" onChange={() => {}} type="password" placeholder="密码" />)
    expect(password.container.querySelector('input[type="password"]')).not.toBeNull()
    password.unmount()
    const name = render(<VariableInput value="" onChange={() => {}} disableVariableHint placeholder="变量名" />)
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 50)) })
    expect(name.container.querySelector('.cm-editor')).toBeNull()
    expect(screen.getByPlaceholderText('变量名')).toBeTruthy()
  })

  it('ref 可 focus，并给出当前原文', async () => {
    localStorage.setItem('autoflow.flags.tagInput', 'true')
    const ref = { current: null as unknown as { focus(): void; value: string } }
    const { container } = render(<VariableInput ref={ref as never} value="x" onChange={() => {}} />)
    await editorOf(container)
    act(() => ref.current.focus())
    expect(ref.current.value).toBe('x')
  })

  it('多行与 disabled 透传', async () => {
    localStorage.setItem('autoflow.flags.tagInput', 'true')
    const { container } = render(<VariableInput value={'a\nb'} onChange={() => {}} multiline disabled />)
    await editorOf(container)
    expect(container.querySelectorAll('.cm-line')).toHaveLength(2)
    expect(container.querySelector('.cm-content')?.getAttribute('contenteditable')).toBe('false')
  })
})
