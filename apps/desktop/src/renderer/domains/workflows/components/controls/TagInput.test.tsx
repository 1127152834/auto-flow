import { act, cleanup, render, screen } from '@testing-library/react'
import { EditorView } from '@codemirror/view'
import * as React from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { findInternalIds } from '../../../../shared/testing/internal-id-scan'
import { buildTagSources } from '../../lib/tagInput/sources'
import { TagInput, type TagInputHandle } from './TagInput'

const sources = buildTagSources({
  signature: [{ key: 'account', name: '账号', rest: {}, fields: [{ key: 'email', name: '邮箱', type: 'string', required: true, sensitive: false, sample: 'a@b.com', rest: {} }] }],
  nodeOutputs: [],
  variables: [{ name: 'token', type: 'string' }],
  projectRefs: [],
})

afterEach(cleanup)

const viewOf = (container: HTMLElement) => EditorView.findFromDOM(container.querySelector('.cm-editor') as HTMLElement)!

describe('TagInput', () => {
  it('把引用显示为业务名标签，不泄漏内部标识', () => {
    const { container } = render(<TagInput value="发给 {input.account.email} 和 {input.account.old}" onChange={() => {}} sources={sources} />)
    const chips = [...container.querySelectorAll('.cm-ref-chip')]
    expect(chips.map(c => c.textContent)).toEqual(['账号·邮箱', '已失效的引用'])
    expect(chips[1].classList.contains('cm-ref-chip-invalid')).toBe(true)
    expect(findInternalIds(container)).toEqual([])
  })

  it('旧式项目数据引用也显示为业务名，界面上看不到内部编号', () => {
    const id = '3f2b8c1e-9a4d-4e6f-8b7a-1c2d3e4f5a6b'
    const legacy = buildTagSources({ signature: [], nodeOutputs: [], variables: [], projectRefs: [], automationInputs: [{ inputId: id, alias: '客户', fields: [{ fieldId: 'f1', alias: '姓名', type: 'string' }] }] })
    const { container } = render(<TagInput value={`{PROJECT_INPUTS['${id}']['values']['f1']}`} onChange={() => {}} sources={legacy} />)
    expect(container.querySelector('.cm-ref-chip')?.textContent).toBe('客户·姓名')
    expect(findInternalIds(container)).toEqual([])
  })

  it('受控 value 往返：输入通知外部，外部改值同步到编辑器且不回传', () => {
    const onChange = vi.fn()
    const { container, rerender } = render(<TagInput value="" onChange={onChange} sources={sources} />)
    const view = viewOf(container)
    act(() => { view.dispatch({ changes: { from: 0, insert: '{token}' }, userEvent: 'input.type' }) })
    expect(onChange).toHaveBeenCalledWith('{token}')
    rerender(<TagInput value="{input.account.email}" onChange={onChange} sources={sources} />)
    expect(view.state.doc.toString()).toBe('{input.account.email}')
    expect(container.querySelector('.cm-ref-chip')?.textContent).toBe('账号·邮箱')
    expect(onChange).toHaveBeenCalledTimes(1)
  })

  it('引用来源变化后标签随之更新', () => {
    const { container, rerender } = render(<TagInput value="{input.account.email}" onChange={() => {}} sources={{ context: {}, candidates: [] }} />)
    expect(container.querySelector('.cm-ref-chip')?.textContent).toBe('已失效的引用')
    rerender(<TagInput value="{input.account.email}" onChange={() => {}} sources={sources} />)
    expect(container.querySelector('.cm-ref-chip')?.textContent).toBe('账号·邮箱')
  })

  it('占位符、id 与无障碍属性', () => {
    const { container } = render(<TagInput value="" onChange={() => {}} sources={sources} placeholder="请输入收件人" id="to" aria-label="收件人" aria-invalid />)
    const content = container.querySelector('.cm-content')!
    expect(container.querySelector('.cm-placeholder')?.textContent).toBe('请输入收件人')
    expect(content.id).toBe('to')
    expect(content.getAttribute('aria-label')).toBe('收件人')
    expect(content.getAttribute('aria-invalid')).toBe('true')
  })

  it('禁用时不可编辑，只读时改不动内容', () => {
    const onChange = vi.fn()
    const disabled = render(<TagInput value="abc" onChange={onChange} sources={sources} disabled />)
    expect(disabled.container.querySelector('.cm-content')?.getAttribute('contenteditable')).toBe('false')
    disabled.unmount()
    const readonly = render(<TagInput value="{token}" onChange={onChange} sources={sources} readOnly />)
    const view = viewOf(readonly.container)
    expect(view.state.readOnly).toBe(true)
    expect(readonly.container.querySelector('.cm-ref-chip')).not.toBeNull()
  })

  it('禁用后恢复可编辑', () => {
    const { container, rerender } = render(<TagInput value="" onChange={() => {}} sources={sources} disabled />)
    rerender(<TagInput value="" onChange={() => {}} sources={sources} />)
    expect(container.querySelector('.cm-content')?.getAttribute('contenteditable')).toBe('true')
  })

  it('多行模式保留换行', () => {
    const { container } = render(<TagInput value={'第一行\n{token}'} onChange={() => {}} sources={sources} multiline rows={4} />)
    expect(container.querySelectorAll('.cm-line')).toHaveLength(2)
    expect(container.querySelector('.cm-ref-chip')?.textContent).toBe('token')
  })

  it('ref 暴露 focus 与当前原文', () => {
    const ref = React.createRef<TagInputHandle>()
    render(<TagInput ref={ref} value="{token}" onChange={() => {}} sources={sources} />)
    expect(ref.current?.value).toBe('{token}')
    act(() => ref.current?.focus())
    expect(document.activeElement).toBe(ref.current?.element)
  })

  it('点击失效标签选中整个引用，作为被替换的范围', () => {
    const { container } = render(<TagInput value="{input.account.old}" onChange={() => {}} sources={sources} />)
    const view = viewOf(container)
    const chip = container.querySelector('.cm-ref-chip-invalid')!
    act(() => { chip.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true })) })
    const selection = view.state.selection.main
    expect([selection.from, selection.to]).toEqual([0, '{input.account.old}'.length])
  })

  it('没有可见的标签文字泄漏到屏幕阅读器之外的位置（chip 带 aria-label）', () => {
    render(<TagInput value="{input.account.email}" onChange={() => {}} sources={sources} />)
    expect(screen.getByLabelText(/账号·邮箱，类型：文本/)).toBeTruthy()
  })
})
