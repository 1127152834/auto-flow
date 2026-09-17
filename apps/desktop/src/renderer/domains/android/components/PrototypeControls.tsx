import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Minus, Plus } from '@phosphor-icons/react'
export function Action({
  primary,
  children,
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { primary?: boolean }) {
  return (
    <button type="button" {...props} className={`ad-button ${primary ? 'ad-primary' : ''} ${className}`}>
      {children}
    </button>
  )
}
export function Badge({
  children,
  tone = 'green',
}: {
  children: ReactNode
  tone?: 'green' | 'brown' | 'gray' | 'blue'
}) {
  return <span className={`ad-badge ad-${tone}`}>{children}</span>
}
export function Dot({ tone = 'green' }: { tone?: string }) {
  return <span aria-hidden className={`ad-dot ad-${tone}`} />
}
export function Quantity({ value, onChange }: { value: number; onChange(value: number): void }) {
  return (
    <div className="ad-quantity">
      <button type="button" aria-label="减少数量" disabled={value <= 1} onClick={() => onChange(value - 1)}>
        <Minus size={16} />
      </button>
      <input
        aria-label="数量"
        type="number"
        min={1}
        max={20}
        value={value}
        onChange={(e) => onChange(Math.min(20, Math.max(1, Number(e.target.value) || 1)))}
      />
      <button type="button" aria-label="增加数量" disabled={value >= 20} onClick={() => onChange(value + 1)}>
        <Plus size={16} />
      </button>
    </div>
  )
}
export function Toggle({
  value,
  onChange,
  label,
  green,
}: {
  value: boolean
  onChange(value: boolean): void
  label: string
  green?: boolean
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-label={label}
      aria-checked={value}
      onClick={() => onChange(!value)}
      className={`ad-toggle ${value ? (green ? 'on green' : 'on') : ''}`}
    >
      <span />
    </button>
  )
}
export function Phone({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`ad-phone ${className}`}>{children}</div>
}
