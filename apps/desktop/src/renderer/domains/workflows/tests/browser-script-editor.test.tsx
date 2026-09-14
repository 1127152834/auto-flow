import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
vi.hoisted(()=>{const data=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value),removeItem:(key:string)=>data.delete(key)})})
vi.mock('@monaco-editor/react',()=>({default:()=>null,loader:{config:vi.fn(),init:vi.fn(async()=>{})}}))
vi.mock('monaco-editor',()=>({}))
vi.mock('../components/AICodeAssistant',()=>({AICodeAssistant:()=>null}))
import {InjectJsEditorDialog} from '../components/InjectJsEditorDialog'
import {browserScriptTestsApi as api} from '../api/browserScriptTests'
import {configureStudioConnection} from '../api/config'
import {useWorkflowStore as store} from '../editor-store'
import type {BrowserScriptState} from '../lib/browserScriptContract'
const target={browserSessionId:'browser',pageId:'page',revision:0}
const context={...target,url:'https://fixture.invalid',activeRequestId:null}
const state=(requestId:string,status:BrowserScriptState['status']='completed'):BrowserScriptState=>({requestId,context:target,status,hasResult:status==='completed',result:status==='completed'?7:null,error:null,executionKind:'mock'})
const deferred=<T,>()=>{let resolve!:(value:T)=>void;const promise=new Promise<T>(done=>{resolve=done});return{promise,resolve}}
let restore:()=>void
beforeEach(()=>{
 restore=configureStudioConnection('http://autoflow-studio.mock',async()=>Response.json({}))
 store.getState().clearWorkflow()
 vi.spyOn(api,'getContext').mockResolvedValue({success:true,data:context})
 vi.spyOn(api,'start').mockImplementation(async request=>({success:true,data:state(request.requestId)}))
 vi.spyOn(api,'get').mockImplementation(async id=>({success:true,data:state(id)}))
 vi.spyOn(api,'cancel').mockImplementation(async id=>({success:true,data:state(id,'cancelled')}))
})
afterEach(()=>{cleanup();vi.restoreAllMocks();restore()})
const props={isOpen:true,code:'while(true){}',onClose:vi.fn(),onSave:vi.fn()}
it.each([['absent',undefined],['null',null],['large',{text:'大'.repeat(33000)}]] as const)('renders a typed service result without evaluating source: %s',async(_name,result)=>{
 vi.mocked(api.start).mockImplementation(async request=>({success:true,data:{...state(request.requestId),hasResult:result!==undefined,result:result??null}}))
 render(<InjectJsEditorDialog {...props}/>);fireEvent.click(screen.getByRole('button',{name:'测试运行'}))
 await waitFor(()=>expect(screen.getByText('模拟服务结果，未执行代码或查询网页')).toBeTruthy())
 expect(api.start).toHaveBeenCalledWith(expect.objectContaining({code:'while(true){}',context:target,variables:{}}),expect.any(AbortSignal))
 expect(document.querySelector('pre')?.textContent).toBe(result===undefined?'执行结束（无返回值）':JSON.stringify(result,null,2))
 expect(screen.getByRole('button',{name:'测试运行'}).hasAttribute('disabled')).toBe(false)
})
it('does not submit a test when context lookup fails',async()=>{
 vi.mocked(api.getContext).mockResolvedValue({success:false,error:'请先打开浏览器',httpStatus:409})
 render(<InjectJsEditorDialog {...props}/>);fireEvent.click(screen.getByRole('button',{name:'测试运行'}))
 await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain('请先打开浏览器'));expect(api.start).not.toHaveBeenCalled()
})
it('ignores a context response after closing and never submits source',async()=>{
 const contextResponse=deferred<Awaited<ReturnType<typeof api.getContext>>>()
 vi.mocked(api.getContext).mockReturnValue(contextResponse.promise)
 const view=render(<InjectJsEditorDialog {...props}/>);fireEvent.click(screen.getByRole('button',{name:'测试运行'}))
 view.rerender(<InjectJsEditorDialog {...props} isOpen={false}/>)
 await act(async()=>contextResponse.resolve({success:true,data:context}));expect(api.start).not.toHaveBeenCalled()
})
it('cancels the original pending request on code change and never displays its result',async()=>{
 const response=deferred<Awaited<ReturnType<typeof api.start>>>()
 vi.mocked(api.start).mockReturnValue(response.promise)
 const view=render(<InjectJsEditorDialog {...props}/>);fireEvent.click(screen.getByRole('button',{name:'测试运行'}))
 await waitFor(()=>expect(api.start).toHaveBeenCalledOnce());const id=vi.mocked(api.start).mock.calls[0][0].requestId
 view.rerender(<InjectJsEditorDialog {...props} code="return 2"/>)
 await act(async()=>response.resolve({success:true,data:state(id,'running')}))
 await waitFor(()=>expect(api.cancel).toHaveBeenCalledWith(id,expect.any(AbortSignal)))
 expect(screen.queryByText('模拟服务结果，未执行代码或查询网页')).toBeNull();expect(api.start).toHaveBeenCalledOnce()
})
it('queries the original request after response loss and never resubmits the source',async()=>{
 vi.mocked(api.start).mockResolvedValue({success:false,error:'响应丢失'})
 render(<InjectJsEditorDialog {...props}/>);fireEvent.click(screen.getByRole('button',{name:'测试运行'}))
 await waitFor(()=>expect(screen.getByText('模拟服务结果，未执行代码或查询网页')).toBeTruthy(),{timeout:2500})
 const id=vi.mocked(api.start).mock.calls[0][0].requestId
 expect(api.start).toHaveBeenCalledOnce();expect(api.get).toHaveBeenCalledWith(id,expect.any(AbortSignal))
})
it('keeps cancellation occupied through a transient failure and retries the same identity',async()=>{
 vi.mocked(api.start).mockImplementation(async request=>({success:true,data:state(request.requestId,'running')}))
 vi.mocked(api.get).mockImplementation(async id=>({success:true,data:state(id,'running')}))
 vi.mocked(api.cancel).mockResolvedValueOnce({success:false,error:'清理暂时失败',httpStatus:500})
 render(<InjectJsEditorDialog {...props}/>);fireEvent.click(screen.getByRole('button',{name:'测试运行'}))
 await waitFor(()=>expect(api.start).toHaveBeenCalledOnce());fireEvent.click(screen.getByRole('button',{name:'取消测试'}))
 await waitFor(()=>expect(api.cancel).toHaveBeenCalledTimes(1))
 expect(screen.getByRole('button',{name:'测试运行'}).hasAttribute('disabled')).toBe(true)
 await waitFor(()=>expect(api.cancel).toHaveBeenCalledTimes(2),{timeout:2500})
 expect(vi.mocked(api.cancel).mock.calls[0][0]).toBe(vi.mocked(api.cancel).mock.calls[1][0]);expect(api.start).toHaveBeenCalledOnce()
 await waitFor(()=>expect(screen.queryByRole('button',{name:'取消测试'})).toBeNull())
})
it('recovers an unfinished request without executing current code',async()=>{
 vi.mocked(api.getContext).mockResolvedValue({success:true,data:{...context,activeRequestId:'recovered'}})
 render(<InjectJsEditorDialog {...props}/>);fireEvent.click(screen.getByRole('button',{name:'测试运行'}))
 await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain('上次测试已结束'))
 expect(api.get).toHaveBeenCalledWith('recovered',expect.any(AbortSignal));expect(api.start).not.toHaveBeenCalled()
 expect(screen.queryByText('模拟服务结果，未执行代码或查询网页')).toBeNull()
})
it('does not submit old-page source to a replacement service connection',async()=>{
 const contextResponse=deferred<Awaited<ReturnType<typeof api.getContext>>>()
 vi.mocked(api.getContext).mockReturnValue(contextResponse.promise)
 render(<InjectJsEditorDialog {...props}/>);fireEvent.click(screen.getByRole('button',{name:'测试运行'}))
 const revert=configureStudioConnection('http://other-service.invalid',async()=>Response.json({}))
 try{await act(async()=>contextResponse.resolve({success:true,data:context}));expect(api.start).not.toHaveBeenCalled();expect(screen.getByRole('alert').textContent).toContain('服务连接已变化')}finally{revert()}
})

it('does not claim cancellation when the service completed before cancellation applied',async()=>{
 vi.mocked(api.start).mockImplementation(async request=>({success:true,data:state(request.requestId,'running')}))
 vi.mocked(api.get).mockImplementation(async id=>({success:true,data:state(id,'running')}))
 vi.mocked(api.cancel).mockImplementation(async id=>({success:true,data:state(id,'completed')}))
 render(<InjectJsEditorDialog {...props}/>);fireEvent.click(screen.getByRole('button',{name:'测试运行'}))
 await waitFor(()=>expect(api.start).toHaveBeenCalledOnce());fireEvent.click(screen.getByRole('button',{name:'取消测试'}))
 await waitFor(()=>expect(screen.getByText('测试已在取消前完成，结果未应用')).toBeTruthy())
 expect(screen.queryByText('测试已取消')).toBeNull();expect(document.querySelector('pre')).toBeNull()
})
