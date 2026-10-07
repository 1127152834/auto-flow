import { useId, type ReactNode } from 'react'

export type ConfigFieldControlProps = {
  id: string
  'aria-invalid'?: true
  'aria-describedby'?: string
}

type Props = {
  label: string
  error?: string | null
  hint?: string
  children: (control: ConfigFieldControlProps) => ReactNode
}

/** 字段包装：标签、控件、提示与字段下方错误；error 为空时不渲染任何占位。 */
export function ConfigField({ label, error, hint, children }: Props) {
  const uid = useId()
  const id = `${uid}-control`
  const errorId = `${uid}-error`
  const hintId = `${uid}-hint`
  const describedBy = [hint ? hintId : '', error ? errorId : ''].filter(Boolean).join(' ') || undefined
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-xs font-medium">{label}</label>
      {children({ id, ...(error ? { 'aria-invalid': true as const } : {}), 'aria-describedby': describedBy })}
      {hint && <p id={hintId} className="text-xs text-muted-foreground">{hint}</p>}
      {error && <p id={errorId} role="alert" className="text-xs text-danger">{error}</p>}
    </div>
  )
}
