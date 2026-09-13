import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {runJsScript} from '../lib/runJsScript'
const workers:WorkerDouble[]=[]
const latest=()=>workers.at(-1)!
class WorkerDouble {
 onmessage:((event:{data:unknown})=>void)|null=null
 onerror:((event:{message:string;preventDefault:()=>void})=>void)|null=null
 postMessage=vi.fn();terminate=vi.fn()
 constructor(){workers.push(this)}
}
beforeEach(()=>{vi.useFakeTimers();vi.stubGlobal('Worker',WorkerDouble)})
afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals()})
it('returns worker result and terminates after completion',async()=>{
 const controller=new AbortController();const result=runJsScript('main',{nested:[1]},controller.signal)
 expect(latest().postMessage).toHaveBeenCalledWith({code:'main',variables:{nested:[1]}})
 latest().onmessage?.({data:{success:true,result:2,variables:{}}})
 expect(await result).toEqual({success:true,result:2,variables:{}})
 controller.abort();expect(latest().terminate).toHaveBeenCalledOnce();expect(vi.getTimerCount()).toBe(0)
})
it('terminates on cancellation without waiting for the script timeout',async()=>{
 const controller=new AbortController();const result=runJsScript('while(true){}',{},controller.signal)
 const rejection=expect(result).rejects.toMatchObject({name:'AbortError'})
 controller.abort();await rejection
 expect(latest().terminate).toHaveBeenCalledOnce();expect(vi.getTimerCount()).toBe(0)
})
it('terminates a timed-out script and returns explicit failure',async()=>{
 const result=runJsScript('while(true){}',{},new AbortController().signal)
 await vi.advanceTimersByTimeAsync(30000)
 expect(await result).toMatchObject({success:false,error:expect.stringContaining('30 秒')})
 expect(latest().terminate).toHaveBeenCalledOnce()
})
it('cleans up worker errors and serialisation failures',async()=>{
 const result=runJsScript('main',{},new AbortController().signal)
 latest().onerror?.({message:'无法加载脚本',preventDefault:vi.fn()})
 expect(await result).toMatchObject({success:false,error:'无法加载脚本'})
 expect(latest().terminate).toHaveBeenCalledOnce()
 expect(vi.getTimerCount()).toBe(0)
})
it('does not construct a worker for an already cancelled request',async()=>{
 const controller=new AbortController();controller.abort()
 const create=vi.fn();vi.stubGlobal('Worker',create)
 await expect(runJsScript('main',{},controller.signal)).rejects.toMatchObject({name:'AbortError'})
 expect(create).not.toHaveBeenCalled()
})
