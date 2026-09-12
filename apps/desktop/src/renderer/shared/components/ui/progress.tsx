import type { HTMLAttributes } from 'react'
import { cn } from '../../lib/utils'
export function Progress({value,className,...props}: Omit<HTMLAttributes<HTMLDivElement>,'children'> & {value:number|null}) {
 const amount=value===null?null:Math.max(0,Math.min(100,value))
 return <div {...props} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={amount??undefined} className={cn('h-2 overflow-hidden rounded-full bg-surface-subtle',className)}><div className="h-full rounded-full bg-clay transition-[width] duration-300 ease-linear" style={{width:amount===null?'33%':`${amount}%`}} /></div>
}
