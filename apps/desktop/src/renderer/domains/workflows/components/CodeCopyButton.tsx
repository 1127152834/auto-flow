import {useEffect,useRef,useState} from 'react'
import {Check,Copy} from 'lucide-react'
import {Button} from './controls/button'

/** Owned by one mounted editor value; closing or editing discards late acknowledgements. */
export function CodeCopyButton({text}:{text:string}) {
  const [status,setStatus]=useState<'idle'|'pending'|'copied'>('idle')
  const [error,setError]=useState<string|null>(null)
  const active=useRef(true)
  const pending=useRef(false)
  const timer=useRef<ReturnType<typeof setTimeout>|null>(null)
  useEffect(()=>{
    active.current=true
    return ()=>{active.current=false;if(timer.current)clearTimeout(timer.current)}
  },[])
  const copy=async()=>{
    if(pending.current)return
    pending.current=true
    if(timer.current)clearTimeout(timer.current)
    setStatus('pending');setError(null)
    try {
      if(!navigator.clipboard?.writeText)throw new Error('当前环境不支持剪贴板，请手动选择代码复制')
      await navigator.clipboard.writeText(text)
      if(!active.current)return
      setStatus('copied')
      timer.current=setTimeout(()=>{timer.current=null;setStatus('idle')},2000)
    } catch(reason) {
      if(!active.current)return
      setStatus('idle');setError(`复制失败：${reason instanceof Error ? reason.message : String(reason)}`)
    } finally {pending.current=false}
  }
  return <>
    <Button size="sm" variant="tonal-success" disabled={status==='pending'} onClick={()=>void copy()}>
      {status==='copied'?<Check className="w-4 h-4 mr-1"/>:<Copy className="w-4 h-4 mr-1"/>}
      {status==='pending'?'正在复制':status==='copied'?'已复制':'复制'}
    </Button>
    {error && <span role="alert" className="text-xs text-red-600">{error}</span>}
  </>
}
