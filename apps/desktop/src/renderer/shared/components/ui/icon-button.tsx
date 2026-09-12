import { Button, type ButtonProps } from './button'
import { Spinner } from './spinner'
import { cn } from '../../lib/utils'

type IconButtonProps = Omit<ButtonProps, 'loadingText'> & { 'aria-label': string }
export function IconButton({ size = 'md', loading, children, className, ...props }: IconButtonProps) {
  return <Button {...props} size={size} disabled={props.disabled || loading} aria-busy={loading || props['aria-busy']}
    className={cn(size === 'sm' ? 'w-[var(--control-sm)] p-0' : 'w-[var(--control-md)] p-0', className)}>
    <span className="grid place-items-center"><span aria-hidden="true" className={cn('col-start-1 row-start-1 inline-flex', loading && 'opacity-0')}>{children}</span>{loading ? <Spinner className="col-start-1 row-start-1" /> : null}</span>
  </Button>
}
