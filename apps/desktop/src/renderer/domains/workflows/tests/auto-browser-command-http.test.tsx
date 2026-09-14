import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {expect,it,vi} from 'vitest'
vi.hoisted(()=>{const values=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>values.set(key,value)})})
import {AutoBrowserDialog} from '../components/AutoBrowserDialog'
import {configureStudioConnection} from '../api/config'
import {startHttpStudioFixture} from './fixtures/http-studio-server'
import {browserApi,currentBrowserSession} from '../api'

it('keeps uncertain startup occupied until status confirms the browser identity before cleanup',async()=>{
 let recovered=false
 const closeBodies:unknown[]=[]
 const server=await startHttpStudioFixture(async(input)=>{
  const url=(input as Request).url
  if(url.endsWith('/browser/open'))return Response.json({error:'启动回执丢失'},{status:503})
  if(url.endsWith('/browser/status'))return recovered?Response.json({isOpen:true,pickerActive:false,sessionId:'confirmed-browser'}):Response.json({error:'离线'},{status:503})
  if(url.endsWith('/browser/close')){closeBodies.push(await (input as Request).json());return Response.json({success:true})}
  return Response.json({error:'unexpected'},{status:404})
 })
 const restore=configureStudioConnection(server.origin,fetch)
 try{
  expect((await browserApi.open()).success).toBe(false)
  expect(currentBrowserSession()).toBeTruthy()
  expect((await browserApi.close()).success).toBe(false)
  expect(closeBodies).toEqual([])
  expect(currentBrowserSession()).toBeTruthy()
  recovered=true
  expect((await browserApi.close()).success).toBe(true)
  expect(closeBodies).toEqual([{sessionId:'confirmed-browser'}])
  expect(currentBrowserSession()).toBeNull()
 }finally{restore();await server.close()}
})
it('does not interleave close with picker startup through the real HTTP adapter',async()=>{
 vi.resetModules();const mock=await import('../api/mock-server')
 let release!:()=>void;const gate=new Promise<void>(resolve=>{release=resolve});let starts=0;let closes=0
 const server=await startHttpStudioFixture(async(input,init)=>{
  const url=(input as Request).url
  if(url.endsWith('/element-picker/start')){starts++;await gate}
  if(url.endsWith('/browser/close'))closes++
  return mock.mockRequest(input,init)
 })
 const restore=configureStudioConnection(server.origin,fetch)
 try{
  await fetch(`${server.origin}/api/browser/open`,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
  render(<AutoBrowserDialog isOpen onClose={vi.fn()} onLog={vi.fn()}/>)
  const start=await screen.findByRole('button',{name:'启动选择器'})
  fireEvent.click(start);fireEvent.click(start);fireEvent.click(screen.getByRole('button',{name:'关闭浏览器'}))
  await waitFor(()=>expect(starts).toBe(1));expect(closes).toBe(0)
  release();await screen.findByRole('button',{name:'停止选择'})
  expect(mock.mockSnapshot()).toMatchObject({browser:true,picking:true})
  fireEvent.click(screen.getByRole('button',{name:'停止选择'}))
  await screen.findByRole('button',{name:'启动选择器'});expect(mock.mockSnapshot().picking).toBe(false)
 }finally{release();cleanup();mock.configureMock({disconnect:true});await server.close();restore()}
})
