// CodeMirror 6 extensions for the tag input. The document is always the plain saved string;
// references are only drawn as atomic tags on top of it.
import { autocompletion, startCompletion, type Completion, type CompletionContext, type CompletionResult } from '@codemirror/autocomplete'
import { defaultKeymap, history, historyKeymap, insertNewline } from '@codemirror/commands'
import { Annotation, EditorState, Facet, StateField, Transaction, type Extension } from '@codemirror/state'
import { Decoration, EditorView, WidgetType, keymap, placeholder as placeholderExtension, type DecorationSet } from '@codemirror/view'
import { EMPTY_SOURCES, findReferenceRanges, referenceTooltip, typeLabel, type RefPart, type RefRange, type TagGroup, type TagSources } from './references'
import { filterCandidates } from './sources'

export const tagSources = Facet.define<TagSources, TagSources>({ combine: values => values[values.length - 1] ?? EMPTY_SOURCES })
/** Marks a change that came from the `value` prop, so it is neither echoed to onChange nor reshaped. */
export const externalChange = Annotation.define<boolean>()

export const GROUP_NAMES: Record<TagGroup, string> = { input: '输入字段', node: '节点输出', variable: '全局变量' }
const GROUP_RANK: Record<TagGroup, number> = { input: 0, node: 1, variable: 2 }

class ReferenceWidget extends WidgetType {
  constructor(readonly part: RefPart) { super() }
  eq(other: ReferenceWidget) {
    return other.part.raw === this.part.raw && other.part.display === this.part.display && other.part.valid === this.part.valid && referenceTooltip(other.part) === referenceTooltip(this.part)
  }
  toDOM() {
    const chip = document.createElement('span')
    chip.className = this.part.valid ? 'cm-ref-chip' : 'cm-ref-chip cm-ref-chip-invalid'
    chip.textContent = this.part.display
    const tip = referenceTooltip(this.part)
    chip.title = tip
    chip.setAttribute('aria-label', tip.replace(/\n/g, '，'))
    chip.dataset.valid = String(this.part.valid)
    return chip
  }
  ignoreEvent() { return false }
}

type RefState = { ranges: RefRange[]; set: DecorationSet }
function build(state: EditorState): RefState {
  const ranges = findReferenceRanges(state.doc.toString(), state.facet(tagSources))
  const set = Decoration.set(ranges.map(range => Decoration.replace({ widget: new ReferenceWidget(range.part) }).range(range.from, range.to)))
  return { ranges, set }
}

export const referenceField = StateField.define<RefState>({
  create: build,
  update: (value, tr) => tr.docChanged || tr.startState.facet(tagSources) !== tr.state.facet(tagSources) ? build(tr.state) : value,
  provide: field => [
    EditorView.decorations.from(field, value => value.set),
    EditorView.atomicRanges.of(view => view.state.field(field).set),
  ],
})

/** Completion list: right after `{`, or when a whole reference is selected to swap it for another. */
export function tagCompletionSource(context: CompletionContext): CompletionResult | null {
  const sources = context.state.facet(tagSources)
  const selection = context.state.selection.main
  const chip = selection.empty ? undefined : context.state.field(referenceField).ranges.find(range => range.from === selection.from && range.to === selection.to)
  let from: number, to: number, query = ''
  if (chip) { from = chip.from; to = chip.to } else {
    const match = context.matchBefore(/\{[^{}\n]*$/)
    if (!match) return null
    from = match.from; to = context.pos; query = match.text.slice(1)
  }
  const options = filterCandidates(sources.candidates, query).map<Completion>(candidate => ({
    label: candidate.label,
    detail: [candidate.type && typeLabel(candidate.type), candidate.hint].filter(Boolean).join(' · ') || undefined,
    type: candidate.group,
    section: { name: GROUP_NAMES[candidate.group], rank: GROUP_RANK[candidate.group] },
    apply: (view, _completion, start, end) => {
      view.dispatch({ changes: { from: start, to: end, insert: candidate.raw }, selection: { anchor: start + candidate.raw.length }, userEvent: 'input.complete' })
      sources.onPick?.(candidate)
    },
  }))
  return options.length ? { from, to, options, filter: false } : null
}

/** A single-line field turns pasted line breaks into spaces. */
const singleLineFilter = EditorState.transactionFilter.of(tr => {
  if (!tr.docChanged || tr.annotation(externalChange) || tr.newDoc.lines === 1) return tr
  const changes: { from: number; to: number; insert: string }[] = []
  tr.changes.iterChanges((from, to, _fromB, _toB, inserted) => changes.push({ from, to, insert: inserted.toString().replace(/\n/g, ' ') }))
  return [{ changes, selection: tr.selection, effects: tr.effects, userEvent: tr.annotation(Transaction.userEvent) }]
})

const reselectInvalid = EditorView.domEventHandlers({
  mousedown(event, view) {
    const chip = (event.target as HTMLElement | null)?.closest?.('.cm-ref-chip-invalid')
    if (!chip || view.state.readOnly || !view.state.facet(EditorView.editable)) return false
    const at = view.posAtDOM(chip)
    const range = view.state.field(referenceField).ranges.find(item => item.from === at)
    if (!range) return false
    event.preventDefault()
    view.dispatch({ selection: { anchor: range.from, head: range.to } })
    view.focus()
    startCompletion(view)
    return true
  },
})

const theme = EditorView.theme({
  '&': { fontSize: '13px', backgroundColor: 'transparent', color: 'inherit', borderRadius: '6px', border: '1px solid var(--color-control-border)' },
  '&.cm-focused': { outline: 'none', borderColor: 'var(--color-focus)', boxShadow: '0 0 0 1px var(--color-focus)' },
  '.cm-scroller': { fontFamily: 'inherit', lineHeight: '1.5' },
  '.cm-content': { padding: '7px 12px', caretColor: 'currentColor' },
  '.cm-line': { padding: '0' },
  '.cm-placeholder': { color: 'var(--color-subtle)' },
  '&.cm-single .cm-scroller': { overflowX: 'auto', overflowY: 'hidden', scrollbarWidth: 'none' },
  '&.cm-single .cm-content': { whiteSpace: 'pre', minHeight: '34px' },
  '&.cm-disabled': { opacity: '0.5', cursor: 'not-allowed' },
  '.cm-ref-chip': {
    display: 'inline-block', maxWidth: '100%', verticalAlign: 'bottom', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
    margin: '0 1px', padding: '0 6px', borderRadius: '4px', fontSize: '13px', lineHeight: '1.45',
    backgroundColor: 'var(--color-clay-soft)', color: 'var(--color-clay-strong)', border: '1px solid var(--color-clay)',
  },
  '.cm-ref-chip-invalid': {
    backgroundColor: 'var(--color-danger-soft)', color: 'var(--color-danger-strong)', borderColor: 'var(--color-danger)', cursor: 'pointer',
  },
  '.cm-tooltip.cm-tooltip-autocomplete': { backgroundColor: 'var(--color-surface)', color: 'var(--color-ink)', border: '1px solid var(--color-line)', borderRadius: '6px', overflow: 'hidden', boxShadow: 'var(--shadow-popup)' },
  '.cm-tooltip-autocomplete ul': { fontFamily: 'inherit', fontSize: '13px', maxHeight: '240px', minWidth: '220px' },
  '.cm-tooltip-autocomplete ul li': { padding: '4px 8px', display: 'flex', gap: '8px', alignItems: 'baseline' },
  '.cm-tooltip-autocomplete ul li[aria-selected]': { backgroundColor: 'var(--color-clay-soft)', color: 'var(--color-clay-strong)' },
  '.cm-completionDetail': { marginLeft: 'auto', fontStyle: 'normal', color: 'var(--color-muted)', fontSize: '13px', whiteSpace: 'nowrap' },
  '.cm-completionIcon': { display: 'none' },
  '.cm-completionSection': { padding: '4px 8px 2px', fontSize: '13px', color: 'var(--color-muted)', borderBottom: 'none' },
})

export type TagLiveOptions = {
  sources: TagSources
  editable: boolean
  readOnly: boolean
  placeholder?: string
  id?: string
  ariaLabel?: string
  ariaInvalid?: boolean
  multiline: boolean
}

/** Everything that follows props; swapped in through a Compartment. */
export function liveExtensions(o: TagLiveOptions): Extension {
  const attributes: Record<string, string> = { 'aria-multiline': String(o.multiline), 'aria-readonly': String(o.readOnly || !o.editable) }
  if (o.id) attributes.id = o.id
  if (o.ariaLabel) attributes['aria-label'] = o.ariaLabel
  if (o.ariaInvalid) attributes['aria-invalid'] = 'true'
  if (!o.editable) attributes['aria-disabled'] = 'true'
  return [
    tagSources.of(o.sources),
    EditorView.editable.of(o.editable),
    EditorState.readOnly.of(o.readOnly),
    EditorView.contentAttributes.of(attributes),
    EditorView.editorAttributes.of({ class: [o.multiline ? 'cm-multi' : 'cm-single', o.editable ? '' : 'cm-disabled'].join(' ').trim() }),
    o.placeholder ? placeholderExtension(o.placeholder) : [],
  ]
}

/** Props-independent part. `rows` only sets the minimum height of a multi-line field. */
export function baseExtensions(options: { multiline: boolean; rows: number; autocomplete: boolean; onDocChange: (value: string) => void }): Extension {
  const keys = defaultKeymap.filter(binding => binding.key !== 'Enter')
  return [
    history(),
    referenceField,
    reselectInvalid,
    theme,
    options.autocomplete ? autocompletion({ override: [tagCompletionSource], icons: false }) : [],
    keymap.of([{ key: 'Enter', run: options.multiline ? insertNewline : () => true }, ...keys, ...historyKeymap]),
    options.multiline ? [EditorView.lineWrapping, EditorView.theme({ '.cm-content': { minHeight: `${options.rows * 19.5 + 14}px` } })] : singleLineFilter,
    EditorView.updateListener.of(update => {
      if (update.docChanged && !update.transactions.some(tr => tr.annotation(externalChange))) options.onDocChange(update.state.doc.toString())
    }),
  ]
}
