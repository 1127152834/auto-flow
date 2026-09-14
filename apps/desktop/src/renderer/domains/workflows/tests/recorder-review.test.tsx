import {act,cleanup,fireEvent,render,screen} from '@testing-library/react'
import {beforeEach,afterEach,it,expect,vi} from 'vitest'
import type {RecEvent} from '../lib/recordingGeneration'
const api=vi.hoisted(()=>({start:vi.fn(),stop:vi.fn(),events:vi.fn(),readReview:vi.fn(),saveReview:vi.fn()}))
vi.mock('../api',()=>({recorderApi:api,browserApi:{getStatus:async()=>({success:true,data:{isOpen:true}})}}))
import {RecorderPanel} from '../components/RecorderPanel'
import {useWorkflowStore as store} from '../editor-store'
import {configureStudioConnection} from '../api/config'
let events:RecEvent[],id:string,restore:()=>void
beforeEach(()=>{
 vi.useFakeTimers();vi.resetAllMocks();store.getState().clearWorkflow();restore=configureStudioConnection('http://recorder-review.test',fetch)
 events=[{sequence:1,type:'input',selector:'#name',value:'原输入'}]
 api.start.mockImplementation(async(sessionId:string)=>{id=sessionId;return {success:true,data:{success:true,recording:true,sessionId}}})
 api.events.mockImplementation(async()=>({success:true,data:{success:true,sessionId:id,nextSeq:0,data:[]}}))
 api.stop.mockImplementation(async()=>({success:true,data:{success:true,sessionId:id,nextSeq:events.length,data:{events}}}))
 api.saveReview.mockImplementation(async(documentId:string,body:{events:RecEvent[];expectedRevision:number;autoWait:boolean})=>({success:true,data:{documentId,revision:body.expectedRevision+1,events:body.events,autoWait:body.autoWait}}))
})
afterEach(()=>{cleanup();restore();vi.useRealTimers()})
const click=async(name:string)=>act(async()=>{fireEvent.click(screen.getByRole('button',{name}))})
const fill=(name:string,value:string)=>fireEvent.change(screen.getByLabelText(name),{target:{value}})
async function record(){const view=render(<RecorderPanel open onClose={()=>{}}/>);await click('开始录制');await click('停止录制');return view}
it('edits input, introduces a variable, previews without mutation, generates and undoes atomically',async()=>{
 await record();await click('编辑第1步');fill('录制输入值','新输入');fill('录制变量名','recorded_name');await click('应用步骤修改')
 await click('预览生成');expect(screen.getByRole('region',{name:'录制生成预览'}).textContent).toContain('{recorded_name}')
 expect(store.getState().nodes).toHaveLength(0);expect(store.getState().variables).toHaveLength(0)
 await click('生成节点');expect(store.getState().nodes[0].data.text).toBe('{recorded_name}');expect(store.getState().variables).toMatchObject([{name:'recorded_name',value:'新输入'}])
 act(()=>store.getState().undo());expect(store.getState().nodes).toHaveLength(0);expect(store.getState().variables).toHaveLength(0)
 act(()=>store.getState().redo());expect(store.getState().variables[0].value).toBe('新输入')
 const exported=store.getState().exportWorkflow();act(()=>{store.getState().clearWorkflow();store.getState().importWorkflow(exported)})
 expect(store.getState().nodes[0].data.text).toBe('{recorded_name}');expect(store.getState().variables[0].value).toBe('新输入')
})
it('does not retain a captured password and requires explicit review before generating',async()=>{
 events[0]={...events[0],sensitive:true,value:'do-not-keep'};await record();await click('生成节点')
 expect(store.getState().nodes).toHaveLength(0);expect(screen.getByRole('alert').textContent).toContain('待补值')
 await click('编辑第1步');expect((screen.getByLabelText('录制输入值') as HTMLTextAreaElement).value).toBe('')
 fill('录制输入值','{credential}');await click('应用步骤修改');await click('生成节点');expect(store.getState().nodes[0].data.text).toBe('{credential}')
})
it('rejects variable collisions without partially adding nodes',async()=>{
 store.getState().addVariable({name:'existing',value:'keep',type:'string',scope:'global'});await record();await click('编辑第1步');fill('录制变量名','existing');await click('应用步骤修改');await click('生成节点')
 expect(store.getState().nodes).toHaveLength(0);expect(store.getState().variables[0].value).toBe('keep');expect(screen.getByRole('alert').textContent).toContain('重复或已存在')
})
it('cancels editing and rejects invalid structured fields',async()=>{
 await record();await click('编辑第1步');fill('框架配置 JSON','{bad');await click('应用步骤修改');expect(screen.getByRole('dialog',{name:'编辑录制步骤'})).toBeTruthy()
 await click('取消步骤修改');await click('生成节点');expect(store.getState().nodes[0].data.text).toBe('原输入')
})
it('renders at most 100 review rows while retaining all steps for generation',async()=>{
 events=Array.from({length:205},(_,i)=>({sequence:i+1,type:'click',selector:`#button-${i}`}));await record()
 expect(screen.getAllByRole('listitem')).toHaveLength(100);await click('下一页步骤');expect(screen.getAllByRole('listitem')).toHaveLength(100)
 await click('下一页步骤');expect(screen.getAllByRole('listitem')).toHaveLength(5);await click('生成节点');expect(store.getState().nodes).toHaveLength(205)
})
it('saves review and restores it after remount without starting or replaying browser operations',async()=>{
 const view=await record();await click('保存审查');expect(api.saveReview).toHaveBeenCalledWith(store.getState().id,expect.objectContaining({expectedRevision:0,events,autoWait:true}))
 const saved=await api.saveReview.mock.results[0].value;view.unmount();api.readReview.mockResolvedValueOnce(saved)
 render(<RecorderPanel open onClose={()=>{}}/>);await click('读取审查');expect(screen.getByText('审查已保存')).toBeTruthy();expect(api.start).toHaveBeenCalledTimes(1)
 await click('生成节点');expect(store.getState().nodes[0].data.text).toBe('原输入')
})
it('preserves review after a save conflict and never reports it saved',async()=>{
 await record();api.saveReview.mockResolvedValueOnce({success:false,error:'409 审查冲突'});await click('保存审查')
 expect(screen.getByRole('alert').textContent).toContain('409');expect(screen.getByText('审查未保存')).toBeTruthy();await click('生成节点');expect(store.getState().nodes).toHaveLength(1)
})
it('refuses a restored review response after the source document changes',async()=>{
 let finish!:(value:unknown)=>void;api.readReview.mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve}))
 render(<RecorderPanel open onClose={()=>{}}/>);const original=store.getState().id;await click('读取审查');act(()=>store.getState().clearWorkflow())
 await act(async()=>finish({success:true,data:{documentId:original,revision:1,autoWait:true,events}}));expect(screen.getByText(/共 0 步/)).toBeTruthy()
})
it('rejects an empty edited target and keeps the original step unchanged',async()=>{
 await record();await click('编辑第1步');fill('元素选择器','');await click('应用步骤修改')
 expect(screen.getByRole('alert').textContent).toBe('元素选择器不能为空')
 await click('取消步骤修改');await click('生成节点')
 expect(store.getState().nodes[0].data.selector).toBe('#name')
})
