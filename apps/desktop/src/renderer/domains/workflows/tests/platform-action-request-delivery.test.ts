import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
vi.hoisted(()=>{const values=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>values.set(key,value),removeItem:(key:string)=>values.delete(key)})})
import { socketService } from '../events'
import { useWorkflowStore as store } from '../editor-store'
import { configureStudioConnection } from '../api/config'
import { startHttpStudioFixture } from './fixtures/http-studio-server'

describe.each(['memory', 'http'] as const)('platform action consumer over %s', mode => {
  let mock: typeof import('../api/mock-server')
  let server: Awaited<ReturnType<typeof startHttpStudioFixture>> | undefined
  let restore: () => void
  let calls: Array<{ url: string; event?: string }>
  let lose: string | undefined
  let request: (path: string, body?: unknown) => Promise<Response>
  const runAction = vi.fn()

  beforeEach(async () => {
    const values = new Map<string, string>()
    vi.stubGlobal('localStorage', { getItem: (key:string) => values.get(key) ?? null, setItem: (key:string,value:string) => values.set(key,value), removeItem: (key:string) => values.delete(key) })
    vi.resetModules(); mock = await import('../api/mock-server')
    if (mode === 'http') server = await startHttpStudioFixture(mock.mockRequest)
    calls = []; lose = undefined; runAction.mockReset().mockResolvedValue({ ok: true, value: { value: '剪贴板原文' } })
    const transport = async (input:RequestInfo|URL, init?:RequestInit) => {
      const url=String(input),body=typeof init?.body==='string'?JSON.parse(init.body):undefined
      calls.push({url,event:body?.event})
      const response=await(server?fetch(input,init):mock.mockRequest(input,init))
      if(body?.event&&body.event===lose){lose=undefined;throw new TypeError('response lost')}
      return response
    }
    const origin=server?.origin??'http://autoflow-studio.mock'
    restore=configureStudioConnection(origin,transport)
    request=(path,body)=>transport(`${origin}/api${path}`,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    store.getState().clearWorkflow()
  })

  afterEach(async () => {
    lose=undefined
    if(mock.mockSnapshot().run)await request('/workflows/platform-delivery/stop',{})
    socketService.disconnect();mock.configureMock({disconnect:true});await server?.close();server=undefined;restore();vi.unstubAllGlobals()
  })

  it.each([undefined,'desktop_action_claim','desktop_action_result'])('executes once and confirms lost=%s',async lost=>{
    lose=lost;socketService.connect();await vi.waitFor(()=>expect(socketService.isConnected()).toBe(true))
    window.autoflow = { ...window.autoflow, runStudioPlatformAction: runAction }
    await request('/workflows',{id:'platform-delivery',nodes:[{id:'clipboard',type:'get_clipboard',data:{variableName:'copied'}}],variables:[]})
    await request('/workflows/platform-delivery/execute',{})
    await vi.waitFor(()=>expect(store.getState().executionStatus).toBe('completed'),{timeout:2500})
    expect(runAction).toHaveBeenCalledOnce();expect(runAction).toHaveBeenCalledWith({action:'clipboard_read_text'})
    expect(calls.filter(call=>call.event==='desktop_action_claim')).toHaveLength(1)
    expect(calls.filter(call=>call.event==='desktop_action_result')).toHaveLength(1)
    if(lost)expect(calls.some(call=>/\/events\/commands\//.test(call.url))).toBe(true)
  })
})
