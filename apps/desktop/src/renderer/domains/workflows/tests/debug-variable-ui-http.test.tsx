import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {DebugBar} from '../components/DebugBar'
import {socketService} from '../events'
import {useDebugStore} from '../hooks/stores/debugStore'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'

afterEach(()=>{cleanup();socketService.disconnect();useDebugStore.getState().clearPaused();vi.unstubAllGlobals()})

it.each([false,true])('edits paused variables through the HTTP fixture exactly once; lostResponse=%s',async lostResponse=>{
  vi.resetModules()
  const {mockRequest,configureMock,mockSnapshot}=await import('../api/mock-server')
  const storage=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>storage.get(key)??null,setItem:(key:string,value:string)=>storage.set(key,value)})
  let variableRequests=0,commandQueries=0
  const server=await startHttpStudioFixture(async(input,init)=>{
    const request=input as Request
    if(request.url.endsWith('/debug/variables'))variableRequests++
    if(request.method==='GET'&&request.url.includes('/events/commands/'))commandQueries++
    return mockRequest(input,init)
  })
  const restore=configureStudioConnection(server.origin,fetch)
  const post=(path:string,body:unknown)=>fetch(`${server.origin}/api${path}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
  try{
    render(<DebugBar/>);socketService.connect();await waitFor(()=>expect(socketService.isConnected()).toBe(true))
    await post('/workflows',{id:'debug-vars-http',name:'暂停变量HTTP',nodes:[{id:'first',type:'open_page',data:{label:'变量暂停'}}],variables:[{name:'count',value:1}]})
    await post('/workflows/debug-vars-http/execute',{stepMode:true,runId:'debug-vars-run'})
    await screen.findByText('@ 变量暂停')
    fireEvent.click(screen.getByRole('button',{name:/变量 1/}));fireEvent.click(screen.getByRole('button',{name:'编辑暂停变量'}))
    expect(screen.getByText('[Mock] Initial values')).toBeTruthy()
    fireEvent.change(screen.getByRole('textbox',{name:'变量 count 的 JSON 值'}),{target:{value:'2'}})
    if(lostResponse)server.dropNextResponse('/api/workflows/debug-vars-http/debug/variables')
    fireEvent.click(screen.getByRole('button',{name:/应用变量/}))
    await waitFor(()=>expect((screen.getByRole('textbox',{name:'变量 count 的 JSON 值'}) as HTMLTextAreaElement).value).toBe('2'))
    await waitFor(()=>expect(screen.getByText('[Mock] 人工调试修改')).toBeTruthy())
    expect(variableRequests).toBe(1)
    if(lostResponse)await waitFor(()=>expect(commandQueries).toBe(1))
    else expect(commandQueries).toBe(0)
    expect(await (await fetch(`${server.origin}/api/workflows/global-variables`)).json()).toMatchObject({variables:{count:2}})
  }finally{
    cleanup();socketService.disconnect()
    if(mockSnapshot().run)await post('/workflows/debug-vars-http/stop',{})
    configureMock({disconnect:true});await server.close();restore()
  }
})
