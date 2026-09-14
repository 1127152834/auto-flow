import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,describe,expect,it,vi} from 'vitest'
import {WebDAVSettings} from '../components/WebDAVSettings'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
describe.each(['memory','http'])('WebDAV settings over %s',mode=>{
 it('saves and reloads mock configuration while refusing to claim a remote connection',async()=>{
  const storage=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>storage.get(key)??null,setItem:(key:string,value:string)=>storage.set(key,value)})
  vi.resetModules();const {mockRequest}=await import('../api/mock-server')
  const server=mode==='http'?await startHttpStudioFixture(mockRequest):undefined
  const restore=configureStudioConnection(server?.origin || 'http://autoflow-studio.mock',server?fetch:mockRequest)
  try{
   const view=render(<WebDAVSettings/>)
   const input=await screen.findByPlaceholderText('WebDAV 地址，如 https://dav.example.com/webrpa/')
   fireEvent.change(input,{target:{value:'https://dav.fixture/'}})
   fireEvent.change(screen.getByPlaceholderText('密码'),{target:{value:'disposable-fixture-password'}})
   fireEvent.click(screen.getByRole('button',{name:'保存配置'}));await screen.findByText('已保存模拟配置，未连接远程存储')
   view.unmount();render(<WebDAVSettings/>);await screen.findByDisplayValue('https://dav.fixture/')
   expect((screen.getByPlaceholderText('密码') as HTMLInputElement).value).toBe('')
   fireEvent.click(screen.getByRole('button',{name:'测试连接'}))
   await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain('Mock 未执行 WebDAV 远程连接'))
   expect([...storage.values()].join()).not.toContain('disposable-fixture-password')
  }finally{cleanup();restore();await server?.close()}
 })
})
