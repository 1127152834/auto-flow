import { Button } from './button'
export function Pagination({offset,limit,total,count,onOffsetChange,disabled=false,showPage=false}: {offset:number;limit:number;total:number;count:number;onOffsetChange(offset:number):void;disabled?:boolean;showPage?:boolean}) {
 const start=total===0?0:offset+1, end=Math.min(offset+count,total)
 return <nav aria-label="分页" className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted"><span aria-live="polite">{start}–{end} / {total}</span><div className="flex items-center gap-3"><Button size={showPage?'md':'sm'} disabled={disabled || offset<=0} onClick={()=>onOffsetChange(Math.max(0,offset-limit))}>上一页</Button>{showPage?<span aria-label="当前页码">第 {Math.floor(offset/limit)+1} 页</span>:null}<Button size={showPage?'md':'sm'} disabled={disabled || offset+count>=total} onClick={()=>onOffsetChange(offset+limit)}>下一页</Button></div></nav>
}
