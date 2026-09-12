import type { ComponentPropsWithRef } from 'react'
import { cn } from '../../lib/utils'
export const Table=({className,...props}:ComponentPropsWithRef<'table'>)=><table {...props} className={cn('w-full border-collapse text-left text-sm text-ink',className)}/>
export const TableHeader=(props:ComponentPropsWithRef<'thead'>)=><thead {...props}/>
export const TableBody=(props:ComponentPropsWithRef<'tbody'>)=><tbody {...props}/>
export const TableRow=({className,...props}:ComponentPropsWithRef<'tr'>)=><tr {...props} className={cn('border-b border-line last:border-0 hover:bg-surface-hover',className)}/>
export const TableHead=({className,scope='col',...props}:ComponentPropsWithRef<'th'>)=><th {...props} scope={scope} className={cn('bg-surface-subtle px-3 py-3 font-medium text-muted',className)}/>
export const TableCell=({className,...props}:ComponentPropsWithRef<'td'>)=><td {...props} className={cn('px-3 py-3 align-top',className)}/>
