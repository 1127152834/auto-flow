import type { HTMLAttributes } from 'react'
import { cn } from '../../lib/utils'
export function Alert({title,tone='info',children,className,...props}:HTMLAttributes<HTMLDivElement>&{tone?:'info'|'error'|'success'|'warning'}){
 return <div {...props} role={tone==='error'?'alert':'status'} className={cn('rounded-control border p-3 text-sm',tone==='error'?'border-danger/30 bg-danger/5 text-danger':tone==='success'?'border-success/30 bg-success/5 text-success':tone==='warning'?'border-warning/30 bg-warning/5 text-warning':'border-line bg-surface-subtle text-ink',className)}>{title?<p className="font-semibold">{title}</p>:null}{children}</div>
}
