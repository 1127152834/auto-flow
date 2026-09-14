import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {WebDAVSettings} from '../components/WebDAVSettings'
import {configureStudioConnection} from '../api/config'
const cfg={enabled:false,url:'https://dav.fixture/',username:'fixture',password:'',remoteDir:'workflows'}
let restore=()=>{}
const transport=vi.fn<typeof fetch>()
beforeEach(()=>{transport.mockReset().mockResolvedValue(Response.json({success:true,config:cfg}));restore=configureStudioConnection('http://webdav.fixture',transport)})
afterEach(()=>{cleanup();restore()})
it.each(['http-error','business-error','invalid-config'])('blocks empty configuration overwrite after %s and permits retry',async mode=>{
 transport.mockImplementationOnce(async()=>mode==='http-error'?Response.json({success:true,config:cfg},{status:503}):mode==='business-error'?Response.json({success:false,error:'不可用'}):Response.json({success:true,config:{enabled:'yes'}}))
 render(<WebDAVSettings/>);await screen.findByRole('alert')
 expect(screen.queryByRole('button',{name:'保存配置'})).toBeNull()
 transport.mockImplementation(async()=>Response.json({success:true,config:cfg}));fireEvent.click(screen.getByRole('button',{name:'重试读取配置'}));await screen.findByDisplayValue(cfg.url)
})
it.each(['save','test'])('%s rejects HTTP failure even when the body claims success',async action=>{
 transport.mockImplementation(async(_input,init)=>init?.method==='POST'?Response.json({success:true},{status:500}):Response.json({success:true,config:cfg}))
 render(<WebDAVSettings/>);await screen.findByDisplayValue(cfg.url);fireEvent.click(screen.getByRole('button',{name:action==='save'?'保存配置':'测试连接'}));await screen.findByRole('alert')
 expect(screen.queryByText('连接成功！')).toBeNull();expect(screen.getByDisplayValue(cfg.url)).toBeTruthy()
})
it('serializes save/test and keeps the submitted configuration on failure',async()=>{
 let resolve!:(response:Response)=>void
 transport.mockImplementation(async(_input,init)=>init?.method==='POST'?new Promise<Response>(done=>{resolve=done}):Response.json({success:true,config:cfg}))
 render(<WebDAVSettings/>);await screen.findByDisplayValue(cfg.url);fireEvent.click(screen.getByRole('button',{name:'保存配置'}));
 expect((screen.getByRole('button',{name:'测试连接'}) as HTMLButtonElement).disabled).toBe(true)
 expect((screen.getByDisplayValue(cfg.url) as HTMLInputElement).disabled).toBe(true)
 fireEvent.click(screen.getByRole('button',{name:'测试连接'}));await waitFor(()=>expect(transport.mock.calls.filter(([,init])=>init?.method==='POST')).toHaveLength(1))
 await act(async()=>resolve(Response.json({success:false,error:'保存失败'})));await screen.findByRole('alert');expect(screen.getByDisplayValue(cfg.url)).toBeTruthy()
})
it('does not report mock save as an active remote connection',async()=>{
 transport.mockImplementation(async(_input,init)=>Response.json(init?.method==='POST'?{success:true,mock:true}:{success:true,config:{...cfg,enabled:true},mock:true}))
 render(<WebDAVSettings/>);await screen.findByDisplayValue(cfg.url);fireEvent.click(screen.getByRole('button',{name:'保存配置'}));await screen.findByText('已保存模拟配置，未连接远程存储')
})
it('invalidates configuration on service replacement before another submission',async()=>{
 render(<WebDAVSettings/>);await screen.findByDisplayValue(cfg.url)
 const next=vi.fn(async()=>Response.json({success:true,config:cfg}));let restoreNext!:()=>void
 act(()=>{restoreNext=configureStudioConnection('http://different.fixture',next)})
 try{await screen.findByRole('alert');expect(screen.queryByRole('button',{name:'保存配置'})).toBeNull();expect(next).not.toHaveBeenCalled()}
 finally{cleanup();restoreNext()}
})

it('rejects an invalid URL before sending a test request',async()=>{
 render(<WebDAVSettings/>);fireEvent.change(await screen.findByDisplayValue(cfg.url),{target:{value:'ftp://invalid/'}})
 fireEvent.click(screen.getByRole('button',{name:'测试连接'}));expect((await screen.findByRole('alert')).textContent).toContain('HTTP 或 HTTPS')
 expect(transport.mock.calls.filter(([,init])=>init?.method==='POST')).toHaveLength(0)
})
it('does not display a late save confirmation after changing services and reloading',async()=>{
 let resolve!:(response:Response)=>void
 transport.mockImplementation(async(_input,init)=>init?.method==='POST'?new Promise<Response>(done=>{resolve=done}):Response.json({success:true,config:cfg}))
 render(<WebDAVSettings/>);await screen.findByDisplayValue(cfg.url);fireEvent.click(screen.getByRole('button',{name:'保存配置'}));await waitFor(()=>expect(resolve).toBeTypeOf('function'))
 const next=vi.fn(async()=>Response.json({success:true,config:{...cfg,url:'https://next.fixture/'}}));let restoreNext!:()=>void
 act(()=>{restoreNext=configureStudioConnection('http://different.fixture',next)})
 try{
  fireEvent.click(await screen.findByRole('button',{name:'重试读取配置'}));await screen.findByDisplayValue('https://next.fixture/')
  await act(async()=>resolve(Response.json({success:true})))
  expect(screen.queryByRole('status')).toBeNull();expect(screen.getByDisplayValue('https://next.fixture/')).toBeTruthy();expect(next).toHaveBeenCalledOnce()
 }finally{cleanup();restoreNext()}
})
