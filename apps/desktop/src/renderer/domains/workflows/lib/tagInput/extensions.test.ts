import { CompletionContext, completionKeymap, completionStatus } from '@codemirror/autocomplete'
import { deleteCharBackward } from '@codemirror/commands'
import { EditorSelection, EditorState } from '@codemirror/state'
import { EditorView } from '@codemirror/view'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { baseExtensions, externalChange, liveExtensions, referenceField, tagCompletionSource } from './extensions'
import type { TagSources } from './references'
import { buildTagSources } from './sources'

const sources: TagSources = buildTagSources({
  signature: [{ key: 'account', name: '账号', rest: {}, fields: [{ key: 'email', name: '邮箱', type: 'string', required: true, sensitive: false, rest: {} }] }],
  nodeOutputs: [{ nodeId: 'n1', key: 'text', name: '文本', label: '读取页面', variable: 'page', reference: 'node.n1.text', required: true, sensitive: false, named: true }],
  variables: [{ name: 'token', type: 'string' }],
  projectRefs: [],
})

const views: EditorView[] = []
afterEach(() => { views.splice(0).forEach(view => view.destroy()) })

function make(doc: string, opts: { multiline?: boolean; editable?: boolean; readOnly?: boolean; onChange?: (v: string) => void } = {}) {
  const multiline = opts.multiline ?? false
  const view = new EditorView({
    parent: document.body,
    state: EditorState.create({
      doc,
      extensions: [
        baseExtensions({ multiline, rows: 3, autocomplete: true, onDocChange: opts.onChange ?? (() => {}) }),
        liveExtensions({ sources, editable: opts.editable ?? true, readOnly: opts.readOnly ?? false, multiline }),
      ],
    }),
  })
  views.push(view)
  return view
}

const complete = (view: EditorView, pos = view.state.selection.main.head, explicit = false) =>
  tagCompletionSource(new CompletionContext(view.state, pos, explicit))

describe('chip display', () => {
  it('引用显示为业务名标签，文档仍是原始字符串', () => {
    const view = make('发送到 {input.account.email}')
    expect(view.state.doc.toString()).toBe('发送到 {input.account.email}')
    const chips = view.dom.querySelectorAll('.cm-ref-chip')
    expect(chips).toHaveLength(1)
    expect(chips[0].textContent).toBe('账号·邮箱')
    expect(view.dom.textContent).not.toContain('input.account')
  })

  it('失效引用标红并带有失效提示', () => {
    const view = make('{input.account.gone}')
    const chip = view.dom.querySelector('.cm-ref-chip-invalid')
    expect(chip?.textContent).toBe('已失效的引用')
    expect(chip?.getAttribute('title')).toContain('重新选择')
  })

  it('标签提示包含类型与来源', () => {
    const chip = make('{input.account.email}').dom.querySelector('.cm-ref-chip')!
    expect(chip.getAttribute('title')).toContain('类型：文本')
    expect(chip.getAttribute('title')).toContain('来源：流程输入')
  })

  it('粘贴含引用的文本后仍是标签，原文不变', () => {
    const view = make('')
    view.dispatch({ changes: { from: 0, insert: 'a {node.n1.text} b' }, userEvent: 'input.paste' })
    expect(view.state.doc.toString()).toBe('a {node.n1.text} b')
    expect(view.state.field(referenceField).ranges).toHaveLength(1)
    expect(view.dom.querySelector('.cm-ref-chip')?.textContent).toBe('读取页面·文本')
  })

  it('引用改变（来源更新）后标签随之刷新', () => {
    const view = make('{token}')
    expect(view.state.field(referenceField).ranges).toHaveLength(1)
    view.dispatch({ changes: { from: 0, to: 7, insert: '{nothing}' } })
    expect(view.state.field(referenceField).ranges).toHaveLength(0)
  })
})

describe('editing', () => {
  it('退格一次删除整个标签', () => {
    const text = 'x {input.account.email}'
    const view = make(text)
    view.dispatch({ selection: EditorSelection.cursor(text.length) })
    deleteCharBackward(view)
    expect(view.state.doc.toString()).toBe('x ')
  })

  it('标签是原子范围，光标不会落在标签内部', () => {
    const view = make('{token}')
    const atomic = view.state.facet(EditorView.atomicRanges).map(source => source(view))
    expect(atomic.some(set => set.size === 1)).toBe(true)
  })

  it('用户输入会通知外部，程序同步的值不会回传', () => {
    const onChange = vi.fn()
    const view = make('', { onChange })
    view.dispatch({ changes: { from: 0, insert: 'abc' }, userEvent: 'input.type' })
    expect(onChange).toHaveBeenLastCalledWith('abc')
    view.dispatch({ changes: { from: 0, to: 3, insert: 'xyz' }, annotations: externalChange.of(true) })
    expect(onChange).toHaveBeenCalledTimes(1)
  })

  it('单行输入把粘贴的换行变成空格，多行保留', () => {
    const single = make('')
    single.dispatch({ changes: { from: 0, insert: 'a\nb' }, userEvent: 'input.paste' })
    expect(single.state.doc.toString()).toBe('a b')
    const multi = make('', { multiline: true })
    multi.dispatch({ changes: { from: 0, insert: 'a\nb' }, userEvent: 'input.paste' })
    expect(multi.state.doc.toString()).toBe('a\nb')
  })

  it('外部同步的值不被单行规则改写', () => {
    const view = make('')
    view.dispatch({ changes: { from: 0, insert: 'a\nb' }, annotations: externalChange.of(true) })
    expect(view.state.doc.toString()).toBe('a\nb')
  })

  it('禁用时不可编辑，只读时拒绝修改但内容仍显示标签', () => {
    const disabled = make('{token}', { editable: false })
    expect(disabled.contentDOM.getAttribute('contenteditable')).toBe('false')
    expect(disabled.contentDOM.getAttribute('aria-disabled')).toBe('true')
    const readonly = make('{token}', { readOnly: true })
    expect(readonly.state.readOnly).toBe(true)
    expect(readonly.dom.querySelector('.cm-ref-chip')).not.toBeNull()
  })

  it('aria 与 id 属性写到可编辑区域', () => {
    const view = new EditorView({
      parent: document.body,
      state: EditorState.create({ doc: '', extensions: [baseExtensions({ multiline: false, rows: 3, autocomplete: true, onDocChange() {} }), liveExtensions({ sources, editable: true, readOnly: false, multiline: false, id: 'f1', ariaLabel: '收件人', ariaInvalid: true, placeholder: '请输入' })] }),
    })
    views.push(view)
    expect(view.contentDOM.id).toBe('f1')
    expect(view.contentDOM.getAttribute('aria-label')).toBe('收件人')
    expect(view.contentDOM.getAttribute('aria-invalid')).toBe('true')
    expect(view.contentDOM.getAttribute('aria-multiline')).toBe('false')
    expect(view.dom.querySelector('.cm-placeholder')?.textContent).toBe('请输入')
  })
})

describe('completion source', () => {
  it('输入 { 后给出三组候选：输入字段、节点输出、全局变量，带中文名与类型', () => {
    const view = make('{')
    view.dispatch({ selection: { anchor: 1 } })
    const result = complete(view)!
    expect(result.from).toBe(0)
    expect(result.options.map(o => [(o.section as { name: string }).name, o.label])).toEqual([
      ['输入字段', '账号·邮箱'], ['节点输出', '读取页面·文本'], ['全局变量', 'token'],
    ])
    expect(result.options[0].detail).toBe('文本 · 流程输入')
  })

  it('继续输入时按名称过滤，没有匹配时不弹出', () => {
    const view = make('{邮')
    expect(complete(view, 2)!.options.map(o => o.label)).toEqual(['账号·邮箱'])
    const none = make('{zzz')
    expect(complete(none, 4)).toBeNull()
  })

  it('普通文本或已闭合的花括号不触发', () => {
    expect(complete(make('abc'), 3)).toBeNull()
    expect(complete(make('{token} '), 8)).toBeNull()
  })

  it('选择后插入对应引用原文并替换已输入的部分，且通知外部', () => {
    const picked = vi.fn()
    const withPick: TagSources = { ...sources, onPick: picked }
    const view = new EditorView({
      parent: document.body,
      state: EditorState.create({ doc: 'a {邮', extensions: [baseExtensions({ multiline: false, rows: 3, autocomplete: true, onDocChange() {} }), liveExtensions({ sources: withPick, editable: true, readOnly: false, multiline: false })] }),
    })
    views.push(view)
    const result = complete(view, 4)!
    const option = result.options[0]
    ;(option.apply as (v: EditorView, c: unknown, f: number, t: number) => void)(view, option, result.from, result.to ?? 4)
    expect(view.state.doc.toString()).toBe('a {input.account.email}')
    expect(view.state.selection.main.head).toBe(view.state.doc.length)
    expect(picked).toHaveBeenCalledWith(expect.objectContaining({ raw: '{input.account.email}' }))
  })

  it('选中整个标签后候选用于替换该引用（重新选择）', () => {
    const view = make('x {input.account.gone} y')
    view.dispatch({ selection: { anchor: 2, head: 22 } })
    const result = complete(view, 22, true)!
    expect([result.from, result.to]).toEqual([2, 22])
    expect(result.options.length).toBe(3)
    const option = result.options[2]
    ;(option.apply as (v: EditorView, c: unknown, f: number, t: number) => void)(view, option, result.from, result.to!)
    expect(view.state.doc.toString()).toBe('x {token} y')
  })

  it('补全面板可只用键盘操作：键位含上下选择、回车确认、Esc 关闭，且 { 触发后面板打开', async () => {
    const view = make('')
    view.dispatch({ changes: { from: 0, insert: '{' }, selection: { anchor: 1 }, userEvent: 'input.type' })
    await vi.waitFor(() => expect(completionStatus(view.state)).toBe('active'))
    const keys = completionKeymap.map(binding => binding.key)
    expect(keys).toEqual(expect.arrayContaining(['ArrowDown', 'ArrowUp', 'Enter', 'Escape']))
  })
})
