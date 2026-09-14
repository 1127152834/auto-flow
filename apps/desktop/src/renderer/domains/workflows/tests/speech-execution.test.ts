import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {isSpeechRequest,runSpeech} from '../lib/runSpeech'
const request={requestId:'speech',workflowId:'flow',nodeId:'voice',text:'通知',lang:'zh-CN',rate:1,pitch:1,volume:0}
class Utterance {
 onend:(()=>void)|null=null
 onerror:((event:{error:string})=>void)|null=null
 lang='';rate=1;pitch=1;volume=1
 constructor(public text:string){}
}
let spoken:Utterance[]=[]
const cancel=vi.fn()
beforeEach(()=>{spoken=[];cancel.mockReset();vi.stubGlobal('SpeechSynthesisUtterance',Utterance);vi.stubGlobal('speechSynthesis',{speak:(utterance:Utterance)=>spoken.push(utterance),cancel})})
afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals()})
it('confirms only after end and preserves zero volume',async()=>{
 const pending=runSpeech(request,new AbortController().signal)
 expect(spoken[0]).toMatchObject({text:'通知',lang:'zh-CN',rate:1,pitch:1,volume:0})
 spoken[0].onend?.();expect(await pending).toEqual({success:true,error:null});expect(spoken[0].onend).toBeNull();expect(spoken[0].onerror).toBeNull()
})
it('reports speech errors and detaches late callbacks',async()=>{
 const pending=runSpeech(request,new AbortController().signal);spoken[0].onerror?.({error:'not-allowed'})
 expect(await pending).toMatchObject({success:false,error:expect.stringContaining('not-allowed')});expect(spoken[0].onend).toBeNull()
})
it('cancels on abort and ignores late completion',async()=>{
 const controller=new AbortController();const pending=runSpeech(request,controller.signal);const reject=expect(pending).rejects.toMatchObject({name:'AbortError'});const late=spoken[0].onend
 controller.abort();late?.();await reject;expect(cancel).toHaveBeenCalledOnce();expect(spoken[0].onend).toBeNull()
})
it('expires at sixty seconds and cancels synthesis',async()=>{
 vi.useFakeTimers();const pending=runSpeech(request,new AbortController().signal);await vi.advanceTimersByTimeAsync(60000)
 expect(await pending).toMatchObject({success:false,error:expect.stringContaining('60秒')});expect(cancel).toHaveBeenCalledOnce()
})
it('does not create an utterance after prior cancellation',async()=>{
 const controller=new AbortController();controller.abort();await expect(runSpeech(request,controller.signal)).rejects.toMatchObject({name:'AbortError'});expect(spoken).toEqual([])
})
it('reports unavailable synthesis without claiming a successful notification',async()=>{
 vi.stubGlobal('speechSynthesis',undefined);expect(await runSpeech(request,new AbortController().signal)).toMatchObject({success:false,error:expect.stringContaining('不支持')})
})
it.each([null,{...request,requestId:''},{...request,text:' '},{...request,lang:''},{...request,rate:0},{...request,pitch:3},{...request,volume:-1},{...request,volume:'0'},{...request,rate:Infinity}])('rejects invalid speech request %j',value=>{expect(isSpeechRequest(value)).toBe(false);expect(spoken).toEqual([])})
