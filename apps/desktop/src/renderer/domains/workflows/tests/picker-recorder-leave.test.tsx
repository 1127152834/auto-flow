import {act,cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {useDraftProtection} from '../hooks/useDraftProtection'
import {useStudioIntegration} from '../hooks/useStudioIntegration'
import {requestDocumentLeave, getDocumentLeaveResources} from '../lib/documentLeave'
import {RecorderPanel} from '../components/RecorderPanel'
import {useWorkflowStore as store} from '../editor-store'
import {configureStudioConnection} from '../api/config'
import {elementPickerApi,browserApi} from '../api'
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
 vi.useFakeTimers();store.getState().clearWorkflow();configureMock({offline:false,disconnect:false})
 store.getState().addVariable({name:'draft',type:'string',value:'keep',scope:'global'})
 requests=[]
 restore=configureStudioConnection('http://autoflow-studio.mock',async(input,init)=>{requests.push(new URL(String(input)).pathname);return mockRequest(input,init)})
 save.mockReset().mockImplementation(async()=>{requests.push('save');store.setState({hasUnsavedChanges:false});return true})
})
afterEach(async()=>{cleanup();await mockRequest('http://autoflow-studio.mock/api/browser/close',{method:'POST'});restore();vi.useRealTimers()})
const click=async(name:string)=>act(async()=>{fireEvent.click(screen.getByRole('button',{name}))})
async function leave(){let promise!:Promise<boolean>;await act(async()=>{promise=requestDocumentLeave()});return {promise}}
it('cancels picker departure, then saves before confirmed cleanup',async()=>{
 render(<Editor/>);await act(async()=>{await elementPickerApi.start()})
 const first=await leave();await click('取消');expect(await first.promise).toBe(false);expect(mockSnapshot().picking).toBe(true)
 const second=await leave();await click('保存并结束会话');expect(await second.promise).toBe(true)
 expect(mockSnapshot().picking).toBe(false)
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
