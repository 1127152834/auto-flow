import type { ComponentPropsWithRef } from 'react'
import { cn } from '../../lib/utils'
export const Table=({className,...props}:ComponentPropsWithRef<'table'>)=><table {...props} className={cn('af-table w-full border-collapse text-left',className)}/>
export const TableHeader=(props:ComponentPropsWithRef<'thead'>)=><thead {...props}/>
export const TableBody=(props:ComponentPropsWithRef<'tbody'>)=><tbody {...props}/>
export const TableRow=(props:ComponentPropsWithRef<'tr'>)=><tr {...props}/>
export const TableHead=({scope='col',...props}:ComponentPropsWithRef<'th'>)=><th {...props} scope={scope}/>
export const TableCell=(props:ComponentPropsWithRef<'td'>)=><td {...props}/>

/** Visual primitives only: queries, selection and edits stay in each domain. */
export function TableScroll({ label, className, ...props }: ComponentPropsWithRef<'div'> & { label: string }) {
  return <div role="region" aria-label={label} tabIndex={0} {...props} className={cn('af-table-scroll min-w-0 max-w-full overflow-auto', className)} />
}
