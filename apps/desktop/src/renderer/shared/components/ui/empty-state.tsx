import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'
export function EmptyState({title,description,action,className}:{title:string;description?:string;action?:ReactNode;className?:string}){
 return <section role="status" className={cn('grid justify-items-center gap-3 rounded-card border border-dashed border-control-border bg-surface px-6 py-10 text-center',className)}><h2 className="text-lg font-semibold text-ink">{title}</h2>{description?<p className="max-w-prose text-sm text-muted">{description}</p>:null}{action}</section>
}
