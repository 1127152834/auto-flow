import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
vi.hoisted(()=>{const data=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>data.get(key)??null,setItem:(key:string,value:string)=>data.set(key,value),removeItem:(key:string)=>data.delete(key)})})
vi.mock('@monaco-editor/react',()=>({default:({value,onChange}:{value:string;onChange:(value:string)=>void})=><textarea aria-label="脚本代码" value={value} onChange={e=>onChange(e.target.value)}/>,loader:{config:vi.fn(),init:vi.fn(async()=>{})}}))
vi.mock('monaco-editor',()=>({}))
vi.mock('../components/AICodeAssistant',()=>({AICodeAssistant:()=>null}))
vi.mock('../lib/runJsScript',()=>({runJsScript:vi.fn()}))
import {runJsScript} from '../lib/runJsScript'
import {JsEditorDialog} from '../components/JsEditorDialog'
import {useWorkflowStore} from '../editor-store'
beforeEach(()=>{vi.mocked(runJsScript).mockReset();useWorkflowStore.getState().clearWorkflow()})
afterEach(cleanup)
it('uses the same cancellable executor for test results and preserves declared values',async()=>{
 useWorkflowStore.getState().addVariable({name:'count',type:'number',scope:'global',value:1})
 useWorkflowStore.getState().ensureGlobalVariables(['unproduced_output'])
 vi.mocked(runJsScript).mockResolvedValue({success:true,result:{answer:2},variables:{count:2}})
 render(<JsEditorDialog isOpen code="function main(vars){return 2}" onClose={vi.fn()} onSave={vi.fn()}/>)
 fireEvent.click(screen.getByRole('button',{name:'测试运行'}))
 await waitFor(()=>expect(screen.getByText(/"answer": 2/)).toBeTruthy())
 expect(runJsScript).toHaveBeenCalledWith('function main(vars){return 2}',{count:1},expect.any(AbortSignal))
 expect(useWorkflowStore.getState().variables[0].value).toBe(1)
})
it.each(['edit','close','unmount'] as const)('cancels and ignores a late test result after %s',async action=>{
 let complete!:(value:{success:boolean;result:string})=>void
 vi.mocked(runJsScript).mockImplementation(()=>new Promise(resolve=>{complete=resolve}))
 const close=vi.fn();const view=render(<JsEditorDialog isOpen code="function main(){return 1}" onClose={close} onSave={vi.fn()}/>)
 fireEvent.click(screen.getByRole('button',{name:'测试运行'}));fireEvent.click(screen.getByRole('button',{name:'正在测试'}))
 expect(runJsScript).toHaveBeenCalledOnce();const signal=vi.mocked(runJsScript).mock.calls[0][2]
 if(action==='edit')fireEvent.change(screen.getByLabelText('脚本代码'),{target:{value:'function main(){return 3}'}})
 else if(action==='close')fireEvent.click(screen.getByRole('button',{name:'关闭'}))
 else view.unmount()
 expect(signal.aborted).toBe(true)
 await act(async()=>complete({success:true,result:'迟到结果'}))
 expect(screen.queryByText('"迟到结果"')).toBeNull()
 if(action==='close')expect(close).toHaveBeenCalledOnce()
})
