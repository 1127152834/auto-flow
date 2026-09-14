import {act,cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
const api=vi.hoisted(()=>({start:vi.fn(),stop:vi.fn(),events:vi.fn(),browserStatus:vi.fn()}))
vi.mock('../api',()=>({recorderApi:api,browserApi:{getStatus:api.browserStatus}}))
import {RecorderPanel} from '../components/RecorderPanel'
import {useWorkflowStore as store} from '../editor-store'
import {configureStudioConnection} from '../api/config'
let id:string
let restore:()=>void
const tail=()=>({success:true,data:{success:true,sessionId:id,nextSeq:1,data:{events:[{sequence:1,type:'input',selector:'#name',value:'原流程'}]}}})
beforeEach(()=>{
 vi.useFakeTimers();vi.resetAllMocks();store.getState().clearWorkflow()
 restore=configureStudioConnection('http://recorder-origin.test',fetch)
 api.browserStatus.mockResolvedValue({success:true,data:{isOpen:true}})
 api.start.mockImplementation(async(sessionId:string)=>{id=sessionId;return {success:true,data:{success:true,sessionId,recording:true,nextSeq:0}}})
 api.events.mockImplementation(async()=>({success:true,data:{success:true,sessionId:id,nextSeq:0,data:[]}}))
 api.stop.mockImplementation(async()=>tail())
})
afterEach(()=>{cleanup();restore();vi.useRealTimers()})
const click=async(name:string)=>act(async()=>{fireEvent.click(screen.getByRole('button',{name}))})
it('does not launch after the document changes while browser availability is pending',async()=>{
 let release!:(value:unknown)=>void
 api.browserStatus.mockImplementationOnce(()=>new Promise(resolve=>{release=resolve}))
 render(<RecorderPanel open onClose={vi.fn()}/>);await click('开始录制')
 act(()=>store.getState().clearWorkflow())
 await act(async()=>release({success:true,data:{isOpen:true}}))
 expect(api.start).not.toHaveBeenCalled()
 expect(screen.getByRole('alert').textContent).toContain('未启动录制')
})
it('keeps late-started recording attached to its original document until explicit stop',async()=>{
 let release!:(value:unknown)=>void
 api.start.mockImplementationOnce((sessionId:string)=>{id=sessionId;return new Promise(resolve=>{release=resolve})})
 render(<RecorderPanel open onClose={vi.fn()}/>);await click('开始录制')
 act(()=>store.getState().clearWorkflow())
 await act(async()=>release({success:true,data:{success:true,sessionId:id,recording:true,nextSeq:0}}))
 await act(async()=>vi.advanceTimersByTimeAsync(1400))
 expect(api.events).not.toHaveBeenCalled()
 expect(screen.getByRole('button',{name:'停止录制'})).toBeTruthy()
 await click('停止录制')
 expect((screen.getByRole('button',{name:'生成节点'}) as HTMLButtonElement).disabled).toBe(true)
 expect(store.getState().nodes).toHaveLength(0)
})
it('cannot generate old review steps into a newly opened document',async()=>{
 render(<RecorderPanel open onClose={vi.fn()}/>);await click('开始录制');await click('停止录制')
 const original=store.getState().id
 act(()=>store.getState().clearWorkflow())
 await click('生成节点')
 expect(store.getState().nodes).toHaveLength(0)
 expect(screen.getByRole('status').textContent).toContain('当前画布不可接收')
 act(()=>store.setState({id:original}))
 await click('生成节点')
 expect(store.getState().nodes.length).toBeGreaterThan(0)
 act(()=>store.getState().undo());expect(store.getState().nodes).toHaveLength(0)
})
it('does not send old polling or stop requests to a replacement connection',async()=>{
 render(<RecorderPanel open onClose={vi.fn()}/>);await click('开始录制')
 let restoreNext!:()=>void
 act(()=>{restoreNext=configureStudioConnection('http://next-recorder.test',fetch)})
 try{
  await act(async()=>vi.advanceTimersByTimeAsync(1400));await click('停止录制')
  expect(api.events).not.toHaveBeenCalled();expect(api.stop).not.toHaveBeenCalled()
  expect(screen.getByRole('alert').textContent).toContain('停止请求未发送')
 }finally{act(()=>restoreNext())}
})
it('retains cleanup responsibility after an unknown startup and recovers its confirmed tail',async()=>{
 api.start.mockImplementationOnce(async(sessionId:string)=>{id=sessionId;return {success:false,error:'未知',outcomeUnknown:true}})
 render(<RecorderPanel open onClose={vi.fn()}/>);await click('开始录制')
 expect(screen.getByRole('button',{name:'停止录制'})).toBeTruthy()
 await click('停止录制')
 expect(api.stop).toHaveBeenCalledWith(id,0)
 expect(screen.getByText(/共 1 步/)).toBeTruthy()
})

it('requires an explicit choice before discarding review steps from an old connection',async()=>{
 const close=vi.fn()
 render(<RecorderPanel open onClose={close}/>);await click('开始录制');await click('停止录制')
 let restoreNext!:()=>void
 act(()=>{restoreNext=configureStudioConnection('http://next-recorder.test',fetch)})
 try{
  await click('关闭录制器')
  expect(screen.getByText('关闭旧录制')).toBeTruthy()
  await click('取消')
  expect(close).not.toHaveBeenCalled();expect(screen.getByText(/共 1 步/)).toBeTruthy()
  await click('关闭录制器');await click('丢弃并关闭')
  expect(close).toHaveBeenCalledTimes(1)
  expect(api.stop).toHaveBeenCalledTimes(1)
 }finally{act(()=>restoreNext())}
})

it('does not start polling from an acknowledgement received after unmount',async()=>{
 let release!:(value:unknown)=>void
 api.start.mockImplementationOnce((sessionId:string)=>{id=sessionId;return new Promise(resolve=>{release=resolve})})
 const view=render(<RecorderPanel open onClose={vi.fn()}/>);await click('开始录制')
 view.unmount()
 await act(async()=>release({success:true,data:{success:true,sessionId:id,recording:true,nextSeq:0}}))
 await act(async()=>vi.advanceTimersByTimeAsync(1400))
 expect(api.events).not.toHaveBeenCalled()
})
