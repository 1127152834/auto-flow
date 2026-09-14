import {afterEach,expect,it,vi} from 'vitest'
import {sendDebugControl} from '../api/debugControl'
import {configureStudioConnection} from '../api/config'
const context={commandId:'command',pauseId:'pause',controlRevision:1}
const receipt={...context,workflowId:'workflow',action:'step',success:true,error:null}
let restore=()=>{}
afterEach(()=>restore())
it.each(['lost','server-error','wrong-identity'] as const)('queries the original command after %s without posting again',async scenario=>{
 const requests:string[]=[]
 restore=configureStudioConnection('http://debug.fixture',async(input,init)=>{
  requests.push(`${init?.method||'GET'} ${String(input)}`)
  if(init?.method==='POST'){
   if(scenario==='lost')throw new TypeError('Failed to fetch')
   if(scenario==='server-error')return Response.json({error:'after application'},{status:500})
   return Response.json({...receipt,commandId:'foreign'})
  }
  return Response.json({...receipt,httpStatus:200})
 })
 expect(await sendDebugControl('workflow','step',context)).toMatchObject({success:true,data:receipt})
 expect(requests.filter(value=>value.startsWith('POST'))).toHaveLength(1)
 expect(requests[1]).toBe('GET http://debug.fixture/api/events/commands/command')
})
it.each(['workflow','pause','revision','missing'] as const)('keeps an unconfirmed result when lookup has a mismatched %s',async mismatch=>{
 let calls=0
 restore=configureStudioConnection('http://debug.fixture',async(_input,init)=>{
  calls++;if(init?.method==='POST')throw new TypeError('Failed to fetch')
  const body=mismatch==='missing'?{}:{...receipt,httpStatus:200,...(mismatch==='workflow'?{workflowId:'other'}:mismatch==='pause'?{pauseId:'other'}:{controlRevision:2})}
  return Response.json(body)
 })
 const result=await sendDebugControl('workflow','step',context)
 expect(result.success).toBe(false);expect(result.httpStatus).toBeUndefined();expect(calls).toBe(2)
})
it('does not query another service after the connection changed during submission',async()=>{
 let resolve!:(response:Response)=>void
 restore=configureStudioConnection('http://debug.first',()=>new Promise<Response>(r=>{resolve=r}))
 const pending=sendDebugControl('workflow','step',context)
 const replacement=vi.fn(async()=>Response.json({...receipt,httpStatus:200}))
 const restoreReplacement=configureStudioConnection('http://debug.second',replacement)
 try{
  resolve(Response.json(receipt));expect((await pending).success).toBe(false);expect(replacement).not.toHaveBeenCalled()
 }finally{restoreReplacement()}
})
it('returns a confirmed rejection without resending or clearing pause state',async()=>{
 const transport=vi.fn(async()=>Response.json({...receipt,success:false,error:'暂停已过期'},{status:409}))
 restore=configureStudioConnection('http://debug.fixture',transport)
 expect(await sendDebugControl('workflow','step',context)).toMatchObject({success:false,httpStatus:409,error:'暂停已过期'})
 expect(transport).toHaveBeenCalledOnce()
})
