import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
vi.hoisted(()=>{const data=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value),removeItem:(key:string)=>data.delete(key)})})
vi.mock('@monaco-editor/react',()=>({default:()=>null,loader:{config:vi.fn(),init:vi.fn(async()=>{})}}))
vi.mock('monaco-editor',()=>({}))
vi.mock('../components/AICodeAssistant',()=>({AICodeAssistant:()=>null}))
import {startHttpStudioFixture} from './fixtures/http-studio-server'
describe.each(['memory','http'] as const)('script editor consumer over %s',mode=>{
 let Dialog:typeof import('../components/InjectJsEditorDialog')['InjectJsEditorDialog']
 let mock:typeof import('../api/mock-server')
 let server:Awaited<ReturnType<typeof startHttpStudioFixture>>|undefined
 let restore:()=>void
 let starts:Array<{requestId:string;code:string}>
 let lost:boolean
 let failedCancel:boolean
 let request:(path:string,body?:unknown)=>Promise<Response>
 const prefix='/browser/script-tests'
 const props={isOpen:true,code:'while(true){}',onClose:vi.fn(),onSave:vi.fn()}
 beforeEach(async()=>{
  vi.resetModules();starts=[];lost=false;failedCancel=false
  const data=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value),removeItem:(key:string)=>data.delete(key)})
  const {configureStudioConnection}=await import('../api/config')
  ;({InjectJsEditorDialog:Dialog}=await import('../components/InjectJsEditorDialog'))
  mock=await import('../api/mock-server')
  const handler=async(input:RequestInfo|URL,init?:RequestInit)=>{
   const url=input instanceof Request?input.url:String(input)
   const body=input instanceof Request?await input.clone().text():String(init?.body??'')
   if(url.endsWith(prefix) && body)starts.push(JSON.parse(body))
   if(url.endsWith('/cancel') && failedCancel){failedCancel=false;return Response.json({success:false,error:'模拟清理失败，资源仍占用'},{status:500})}
   return mock.mockRequest(input,init)
  }
  if(mode==='http')server=await startHttpStudioFixture(handler)
  const origin=server?.origin??'http://autoflow-studio.mock'
  restore=configureStudioConnection(origin,async(input,init)=>{
   const response=await(server?fetch(input,init):handler(input,init))
   if(String(input).endsWith(prefix) && lost){lost=false;throw new TypeError('请求已接受后响应丢失')}
   return response
  })
  request=(path,body)=>{const init=body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)};return server?fetch(`${origin}/api${path}`,init):handler(`${origin}/api${path}`,init)}
 })
 afterEach(async()=>{cleanup();await request('/browser/close',{});await server?.close();server=undefined;restore();vi.unstubAllGlobals()})
 it.each([false,true])('waits for a confirmed explicit mock result without executing source, lost=%s',async lose=>{
  lost=lose;await request('/browser/open',{url:'https://fixture.invalid'})
  mock.configureMock({scriptTest:{result:{count:3}}})
  render(<Dialog {...props}/>);fireEvent.click(screen.getByRole('button',{name:'测试运行'}))
  await waitFor(()=>expect(starts).toHaveLength(1))
  expect(screen.getByRole('button',{name:'测试运行'}).hasAttribute('disabled')).toBe(true)
  await waitFor(()=>expect(screen.getByText('模拟服务结果，未执行代码或查询网页')).toBeTruthy(),{timeout:2500})
  expect(document.querySelector('pre')?.textContent).toBe(JSON.stringify({count:3},null,2));expect(starts).toHaveLength(1)
 })
 it('reports missing browser context and leaves the code editable',async()=>{
  render(<Dialog {...props}/>);fireEvent.click(screen.getByRole('button',{name:'测试运行'}))
  await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain('打开空闲'))
  expect(starts).toHaveLength(0);expect(screen.getByRole('button',{name:'测试运行'}).hasAttribute('disabled')).toBe(false)
 })
 it('expires the old page result after navigation without submitting the source again',async()=>{
  await request('/browser/open',{});mock.configureMock({scriptTest:{hold:true}})
  render(<Dialog {...props}/>);fireEvent.click(screen.getByRole('button',{name:'测试运行'}))
  await waitFor(()=>expect(starts).toHaveLength(1));await request('/browser/navigate',{url:'https://fixture.invalid/next'})
  await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain('失效'),{timeout:2500})
  expect(document.querySelector('pre')).toBeNull();expect(starts).toHaveLength(1)
 })
 it('does not release the UI or service slot before a failed cancellation is confirmed',async()=>{
  await request('/browser/open',{});mock.configureMock({scriptTest:{hold:true}});failedCancel=true
  render(<Dialog {...props}/>);fireEvent.click(screen.getByRole('button',{name:'测试运行'}))
  await waitFor(()=>expect(starts).toHaveLength(1));fireEvent.click(screen.getByRole('button',{name:'取消测试'}))
  await waitFor(()=>expect(failedCancel).toBe(false))
  expect((await(await request(`${prefix}/context`)).json()).activeRequestId).toBe(starts[0].requestId)
  expect(screen.getByRole('button',{name:'测试运行'}).hasAttribute('disabled')).toBe(true)
  await waitFor(()=>expect(screen.queryByRole('button',{name:'取消测试'})).toBeNull(),{timeout:2500})
  expect((await(await request(`${prefix}/${starts[0].requestId}`)).json()).status).toBe('cancelled');expect(starts).toHaveLength(1)
 })
 it('cancels the old operation on code change and leaves no stale result',async()=>{
  await request('/browser/open',{});mock.configureMock({scriptTest:{hold:true}})
  const view=render(<Dialog {...props}/>);fireEvent.click(screen.getByRole('button',{name:'测试运行'}))
  await waitFor(()=>expect(starts).toHaveLength(1))
  await act(async()=>view.rerender(<Dialog {...props} code="return 9"/>))
  await waitFor(async()=>expect((await(await request(`${prefix}/${starts[0].requestId}`)).json()).status).toBe('cancelled'))
  expect(document.querySelector('pre')).toBeNull();expect(starts).toHaveLength(1)
 })
})
