import { Eye, EyeSlash } from '@phosphor-icons/react'
import { useState } from 'react'
import { Input, type InputProps } from './input'
import { IconButton } from './icon-button'
import { cn } from '../../lib/utils'

type PasswordInputProps = Omit<InputProps, 'type'> & { allowReveal?: boolean }
export function PasswordInput({ allowReveal = false, className, ...props }: PasswordInputProps) {
  const [visible, setVisible] = useState(false)
  const revealed = allowReveal && visible
  return <div className="relative min-w-0">
    <Input {...props} type={revealed ? 'text' : 'password'} className={cn(allowReveal && 'pr-10', className)} />
    {allowReveal ? <span className="absolute inset-y-0 right-1 flex items-center"><IconButton aria-label={revealed ? '隐藏密码' : '显示密码'} aria-pressed={revealed} size="sm" variant="ghost" disabled={props.disabled}
      onMouseDown={event => event.preventDefault()} onClick={() => setVisible(!visible)}>{revealed ? <EyeSlash size={16} /> : <Eye size={16} />}</IconButton></span> : null}
  </div>
}
