import {act,cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {useDraftProtection} from '../hooks/useDraftProtection'
import {useStudioIntegration} from '../hooks/useStudioIntegration'
import {requestDocumentLeave, getDocumentLeaveResources} from '../lib/documentLeave'
import {RecorderPanel} from '../components/RecorderPanel'
import {useWorkflowStore as store} from '../editor-store'
import {configureStudioConnection} from '../api/config'
import {elementPickerApi,browserApi,recorderApi} from '../api'
import {mockRequest,configureMock,mockSnapshot,addMockRecordingEvent} from '../api/mock-server'
const save=vi.fn<()=>Promise<boolean>>()
let restore:()=>void
let requests:string[]
function Editor({recorder=false}:{recorder?:boolean}){
 useStudioIntegration()
 const {draftDialog}=useDraftProtection(save)
 return <>{draftDialog}{recorder&&<RecorderPanel open onClose={()=>{}}/>}</>
}
beforeEach(()=>{
 const data=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value),removeItem:(key:string)=>data.delete(key)})
 vi.useFakeTimers();store.getState().clearWorkflow();configureMock({offline:false,disconnect:false})
 store.getState().addVariable({name:'draft',type:'string',value:'keep',scope:'global'})
 requests=[]
 restore=configureStudioConnection('http://autoflow-studio.mock',async(input,init)=>{requests.push(new URL(String(input)).pathname);return mockRequest(input,init)})
 save.mockReset().mockImplementation(async()=>{requests.push('save');store.setState({hasUnsavedChanges:false});return true})
})
afterEach(async()=>{cleanup();await mockRequest('http://autoflow-studio.mock/api/browser/close',{method:'POST'});restore();vi.restoreAllMocks();vi.useRealTimers();vi.unstubAllGlobals()})
const click=async(name:string)=>act(async()=>{fireEvent.click(screen.getByRole('button',{name}))})
async function leave(){let promise!:Promise<boolean>;await act(async()=>{promise=requestDocumentLeave()});return {promise}}
it('cancels picker departure, then saves before confirmed cleanup',async()=>{
 render(<Editor/>);await act(async()=>{await elementPickerApi.start()})
 const first=await leave();await click('取消');expect(await first.promise).toBe(false);expect(mockSnapshot().picking).toBe(true)
 const second=await leave();await click('保存并结束会话');expect(await second.promise).toBe(true)
 expect(mockSnapshot().picking).toBe(false)
 expect(mockSnapshot().browser).toBe(false)
 expect(requests.indexOf('save')).toBeLessThan(requests.indexOf('/api/element-picker/stop'))
 expect(getDocumentLeaveResources()).toHaveLength(0)
})
it('picker cleanup failure retains the original document and supports retry',async()=>{
 render(<Editor/>);await act(async()=>{await elementPickerApi.start()});configureMock({failNextPickerStop:true})
 const first=await leave();await click('放弃修改并结束会话');expect(await first.promise).toBe(false)
 expect(mockSnapshot().picking).toBe(true);expect(store.getState().variables[0].value).toBe('keep')
 const second=await leave();await click('放弃修改并结束会话');expect(await second.promise).toBe(true)
})
it('save failure leaves real mock recording active with no stop request',async()=>{
 await browserApi.open();render(<Editor recorder/>);await click('开始录制')
 save.mockResolvedValueOnce(false);const first=await leave();await click('保存并结束会话')
 expect(await first.promise).toBe(false);expect(mockSnapshot().recording).toBe(true)
 expect(requests).not.toContain('/api/recorder/stop');expect(screen.getByRole('button',{name:'停止录制'})).toBeTruthy()
})
it('stops recording and reads its tail before allowing document replacement',async()=>{
 await browserApi.open();render(<Editor recorder/>);await click('开始录制')
 addMockRecordingEvent({type:'input',selector:'#name',value:'最后输入'})
 const decision=await leave();await click('保存并结束会话');expect(await decision.promise).toBe(true)
 expect(requests.indexOf('save')).toBeLessThan(requests.indexOf('/api/recorder/stop'))
 expect(mockSnapshot().recording).toBe(false);expect(screen.getByText(/共 1 步/)).toBeTruthy()
 expect(store.getState().nodes).toHaveLength(0)
 act(()=>store.getState().clearWorkflow())
 expect((screen.getByRole('button',{name:'生成节点'}) as HTMLButtonElement).disabled).toBe(true)
})
it('does not leave while a recorder startup is still awaiting acknowledgement',async()=>{
 let finish!:(value:Response)=>void
 const original=restore;original()
 restore=configureStudioConnection('http://autoflow-studio.mock',async(input,init)=>String(input).endsWith('/recorder/start')?new Promise(resolve=>{void mockRequest(input,init).then(result=>{finish=()=>resolve(result)})}):mockRequest(input,init))
 await browserApi.open();render(<Editor recorder/>);await click('开始录制')
 const decision=await leave();await click('放弃修改并结束会话');expect(await decision.promise).toBe(false)
 await act(async()=>finish(Response.json({})))
 expect(screen.getByRole('button',{name:'停止录制'})).toBeTruthy()
 const next=await leave();await click('放弃修改并结束会话');expect(await next.promise).toBe(true)
})
it('retains confirmed tail after review-save conflict and persists it before retrying departure',async()=>{
 await browserApi.open();render(<Editor recorder/>);await click('开始录制')
 const documentId=store.getState().id
 addMockRecordingEvent({type:'input',selector:'#tail',value:'审查冲突后仍保留'})
 const persist=vi.spyOn(recorderApi,'saveReview').mockResolvedValueOnce({success:false,httpStatus:409,error:'审查已修改'})
 const first=await leave();await click('保存并结束会话');expect(await first.promise).toBe(false)
 expect(mockSnapshot().recording).toBe(false)
 expect(screen.getByText(/共 1 步/)).toBeTruthy()
 expect(getDocumentLeaveResources().some(item=>item.label==='未保存录制审查')).toBe(true)
 persist.mockRestore()
 const retry=await leave();await click('结束会话后继续');expect(await retry.promise).toBe(true)
 const review=await recorderApi.readReview(documentId)
 expect(review.data?.events).toMatchObject([{selector:'#tail',value:'审查冲突后仍保留'}])
})
it('saves deletion of all previously saved review steps before leaving',async()=>{
 await browserApi.open();render(<Editor recorder/>);await click('开始录制')
 const documentId=store.getState().id
 addMockRecordingEvent({type:'click',selector:'#remove'})
 await click('停止录制');await click('保存审查')
 await act(async()=>fireEvent.click(screen.getByRole('button',{name:'删除此步'})))
 expect((screen.getByRole('button',{name:'保存审查'}) as HTMLButtonElement).disabled).toBe(false)
 const next=await leave();await click('保存并结束会话');expect(await next.promise).toBe(true)
 expect((await recorderApi.readReview(documentId)).data?.events).toEqual([])
})
