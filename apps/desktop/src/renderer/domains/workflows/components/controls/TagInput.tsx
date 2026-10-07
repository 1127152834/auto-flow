import * as React from 'react'
import { Compartment, EditorState } from '@codemirror/state'
import { EditorView } from '@codemirror/view'
import { cn } from '../../lib/utils'
import { baseExtensions, externalChange, liveExtensions } from '../../lib/tagInput/extensions'
import { EMPTY_SOURCES, type TagSources } from '../../lib/tagInput/references'

export interface TagInputHandle {
  focus(): void
  blur(): void
  /** The saved text, with references in their original form. */
  readonly value: string
  readonly element: HTMLElement | null
}

export interface TagInputProps {
  value: string
  onChange: (value: string) => void
  sources?: TagSources
  multiline?: boolean
  rows?: number
  placeholder?: string
  disabled?: boolean
  readOnly?: boolean
  id?: string
  className?: string
  /** Turns off the `{` completion list. */
  disableCompletion?: boolean
  'aria-label'?: string
  'aria-invalid'?: boolean | 'true' | 'false'
  onFocus?: () => void
  onBlur?: () => void
}

/** Text field that shows data references as business-named tags while the saved value stays the plain string. */
export const TagInput = React.forwardRef<TagInputHandle, TagInputProps>(function TagInput(props, ref) {
  const { value, onChange, sources = EMPTY_SOURCES, multiline = false, rows = 3, placeholder, disabled = false, readOnly = false, id, className, disableCompletion = false } = props
  const ariaInvalid = props['aria-invalid'] === true || props['aria-invalid'] === 'true'
  const host = React.useRef<HTMLDivElement>(null)
  const viewRef = React.useRef<EditorView | null>(null)
  const live = React.useRef(new Compartment())
  const onChangeRef = React.useRef(onChange)
  onChangeRef.current = onChange
  const valueRef = React.useRef(value)
  valueRef.current = value
  const liveOptions = { sources, editable: !disabled, readOnly, placeholder, id, ariaLabel: props['aria-label'], ariaInvalid, multiline }
  const liveRef = React.useRef(liveOptions)
  liveRef.current = liveOptions

  React.useEffect(() => {
    const view = new EditorView({
      parent: host.current!,
      state: EditorState.create({
        doc: valueRef.current,
        extensions: [
          baseExtensions({ multiline, rows, autocomplete: !disableCompletion, onDocChange: text => onChangeRef.current(text) }),
          live.current.of(liveExtensions(liveRef.current)),
        ],
      }),
    })
    viewRef.current = view
    return () => { view.destroy(); viewRef.current = null }
  }, [multiline, rows, disableCompletion])

  React.useEffect(() => {
    const view = viewRef.current
    if (view && view.state.doc.toString() !== value) {
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: value }, annotations: externalChange.of(true) })
    }
  }, [value, multiline, rows, disableCompletion])

  const { ariaLabel, ...rest } = liveOptions
  React.useEffect(() => {
    viewRef.current?.dispatch({ effects: live.current.reconfigure(liveExtensions(liveRef.current)) })
  }, [rest.sources, rest.editable, rest.readOnly, rest.placeholder, rest.id, ariaLabel, rest.ariaInvalid, rest.multiline, multiline, rows, disableCompletion])

  React.useImperativeHandle(ref, () => ({
    focus: () => viewRef.current?.focus(),
    blur: () => viewRef.current?.contentDOM.blur(),
    get value() { return viewRef.current?.state.doc.toString() ?? valueRef.current },
    get element() { return viewRef.current?.contentDOM ?? null },
  }), [])

  return <div ref={host} className={cn('relative w-full min-w-0', className)} onFocus={props.onFocus} onBlur={props.onBlur} />
})
TagInput.displayName = 'TagInput'
