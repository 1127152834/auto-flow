import { Button } from './button'
export function Pagination({offset,limit,total,count,onOffsetChange,disabled=false}: {offset:number;limit:number;total:number;count:number;onOffsetChange(offset:number):void;disabled?:boolean}) {
 const start=total===0?0:offset+1, end=Math.min(offset+count,total)
 return <nav aria-label="分页" className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted"><span aria-live="polite">{start}–{end} / {total}</span><div className="flex gap-2"><Button size="sm" disabled={disabled || offset<=0} onClick={()=>onOffsetChange(Math.max(0,offset-limit))}>上一页</Button><Button size="sm" disabled={disabled || offset+count>=total} onClick={()=>onOffsetChange(offset+limit)}>下一页</Button></div></nav>
}
