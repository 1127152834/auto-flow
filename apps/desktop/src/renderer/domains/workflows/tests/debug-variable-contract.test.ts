import {describe,expect,it} from 'vitest'
import {isDebugVariablesReceipt,isDebugVariablesRequest} from '../lib/debugControlContract'

const request={commandId:'command',runId:'run',pauseId:'pause',controlRevision:1,changes:[{name:'count',value:2}]}

describe('paused variable command contract',()=>{
  it('accepts a complete request and its matching receipt',()=>{
    expect(isDebugVariablesRequest(request)).toBe(true)
    expect(isDebugVariablesReceipt({...request,workflowId:'workflow',success:true,error:null},'workflow',request)).toBe(true)
  })

  it.each([
    {...request,runId:''},
    {...request,changes:[]},
    {...request,changes:[{name:'1bad',value:1}]},
    {...request,changes:[{name:'same',value:1},{name:'same',value:2}]},
    {...request,changes:[{name:'ok',value:1,extra:true}]},
    {...request,changes:[{name:'ok',value:Number.POSITIVE_INFINITY}]},
    {...request,changes:[{name:'ok',value:undefined}]},
  ])('rejects malformed request %#',(candidate)=>expect(isDebugVariablesRequest(candidate)).toBe(false))

  it('rejects a request larger than one MiB without truncating it',()=>{
    expect(isDebugVariablesRequest({...request,changes:[{name:'large',value:'x'.repeat(1024*1024)}]})).toBe(false)
  })

  it.each([
    {workflowId:'other'},
    {runId:'other'},
    {pauseId:'other'},
    {controlRevision:2},
    {changes:[{name:'count',value:3}]},
    {success:true,error:'contradiction'},
  ])('rejects a mismatched or contradictory receipt %#',(patch)=>{
    expect(isDebugVariablesReceipt({...request,workflowId:'workflow',success:true,error:null,...patch},'workflow',request)).toBe(false)
  })
})
