import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'
// 列表级空态的唯一版式：图标 + 标题 + 说明 + 可选动作。表格行内的「暂无…」提示不用它。
export function EmptyState({icon,title,description,action,className}:{icon?:ReactNode;title:string;description?:string;action?:ReactNode;className?:string}){
 return <section role="status" className={cn('grid min-h-72 place-items-center px-6 py-10 text-center',className)}><div className="grid justify-items-center gap-3">{icon?<span aria-hidden="true" className="text-muted">{icon}</span>:null}<h2 className="m-0 text-lg font-semibold text-ink">{title}</h2>{description?<p className="m-0 max-w-prose text-sm text-muted">{description}</p>:null}{action}</div></section>
}
