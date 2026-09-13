import {useState} from 'react'
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {NumberInput} from '../components/controls/number-input'
import {useWorkflowStore} from '../editor-store'
import {WaitConfig} from '../components/config-panels/BasicModuleConfigs'
afterEach(cleanup)
function Controlled({initial=5,min,max,onBlur}:{initial?:number|string;min?:number;max?:number;onBlur?:()=>void}){
 const [value,setValue]=useState<number|string>(initial)
 return <><NumberInput aria-label="测试数字" value={value} onChange={setValue} min={min} max={max} {...(onBlur ? {onBlur} : {})}/><output data-testid="stored">{JSON.stringify(value)}</output></>
}
it.each(['1abc','Infinity','NaN','1e999','-','0x10'])('preserves invalid numeric draft %s instead of coercing it',value=>{
 render(<Controlled />);const input=screen.getByRole('textbox',{name:'测试数字'})
 fireEvent.change(input,{target:{value}});fireEvent.blur(input)
 expect((input as HTMLInputElement).value).toBe(value)
 expect(screen.getByTestId('stored').textContent).toBe(JSON.stringify(value))
 expect(input.getAttribute('aria-invalid')).toBe('true')
})
it('preserves an unfinished empty value after blur',()=>{
 render(<Controlled />);const input=screen.getByRole('textbox',{name:'测试数字'})
 fireEvent.change(input,{target:{value:''}});fireEvent.blur(input)
 expect((input as HTMLInputElement).value).toBe('')
 expect(screen.getByTestId('stored').textContent).toBe('""')
})
it.each([-1,11])('reports out-of-range %s without silently clamping the document',value=>{
 render(<Controlled min={0} max={10}/>);const input=screen.getByRole('textbox',{name:'测试数字'})
 fireEvent.change(input,{target:{value:String(value)}});fireEvent.blur(input)
 expect(screen.getByTestId('stored').textContent).toBe(String(value))
 expect((input as HTMLInputElement).value).toBe(String(value))
 expect(input.getAttribute('aria-invalid')).toBe('true')
})
it('allows decimal entry without erasing its trailing decimal point mid-edit',()=>{
 render(<Controlled initial={0}/>);const input=screen.getByRole('textbox',{name:'测试数字'})
 fireEvent.change(input,{target:{value:'1.'}})
 expect((input as HTMLInputElement).value).toBe('1.')
 fireEvent.change(input,{target:{value:'1.25'}});fireEvent.blur(input)
 expect(screen.getByTestId('stored').textContent).toBe('1.25')
})
it.each(['{duration}','${duration}'])('retains variable reference %s',value=>{
 render(<Controlled />);const input=screen.getByRole('textbox',{name:'测试数字'})
 fireEvent.change(input,{target:{value}});fireEvent.blur(input)
 expect((input as HTMLInputElement).value).toBe(value)
 expect(screen.getByTestId('stored').textContent).toBe(JSON.stringify(value))
})
it('runs internal blur validation together with the caller blur callback',()=>{
 const blur=vi.fn();render(<Controlled onBlur={blur}/>);const input=screen.getByRole('textbox',{name:'测试数字'})
 fireEvent.change(input,{target:{value:'1abc'}});fireEvent.blur(input)
 expect(blur).toHaveBeenCalledOnce()
 expect(input.getAttribute('aria-invalid')).toBe('true')
})
it.each(['1abc','Infinity','1e999'])('keeps invalid wait duration %s in its document field',value=>{
 const change=vi.fn()
 render(<WaitConfig data={{moduleType:'wait',label:'等待',duration:5}} onChange={change} renderSelectorInput={()=>null}/>)
 fireEvent.change(screen.getByRole('textbox'),{target:{value}})
 expect(change).toHaveBeenLastCalledWith('duration',value)
})

it.each([['0',0],['-2',-2],['+2',2],['.5',0.5],['1e2',100],[' 2.5 ',2.5]] as const)('stores valid finite decimal %s as a number', (text,expected)=>{
 render(<Controlled initial={7}/>);const input=screen.getByRole('textbox',{name:'测试数字'})
 fireEvent.change(input,{target:{value:text}});fireEvent.blur(input)
 expect(screen.getByTestId('stored').textContent).toBe(JSON.stringify(expected))
 expect((input as HTMLInputElement).value).toBe(String(expected))
 expect(input.getAttribute('aria-invalid')).not.toBe('true')
})
it('syncs an external value change after an unfinished numeric edit',()=>{
 const change=vi.fn();const view=render(<NumberInput value={5} onChange={change} aria-label="external"/>)
 fireEvent.change(screen.getByRole('textbox'),{target:{value:'1abc'}})
 view.rerender(<NumberInput value={8} onChange={change} aria-label="external"/>)
 expect(screen.queryByDisplayValue('8')).not.toBeNull()
 expect(screen.queryByText('请输入有效的有限数字或变量引用')).toBeNull()
})
function WaitDocument(){
 const node=useWorkflowStore(state=>state.nodes[0])
 return <WaitConfig data={node.data} onChange={(key,value)=>useWorkflowStore.getState().updateNodeData(node.id,{[key]:value})} renderSelectorInput={()=>null}/>
}
it.each(['1abc','','{duration}'])('preserves wait draft %s through undo and real mock save/load',async value=>{
 const storage=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>storage.get(key)??null,setItem:(key:string,value:string)=>storage.set(key,value)})
 const {mockRequest}=await import('../api/mock-server')
 try{
  useWorkflowStore.getState().clearWorkflow();useWorkflowStore.getState().addNode('wait',{x:0,y:0},{duration:5})
  render(<WaitDocument/>);fireEvent.change(screen.getByRole('textbox'),{target:{value}});fireEvent.blur(screen.getByRole('textbox'))
  expect(useWorkflowStore.getState().nodes[0].data.duration).toBe(value)
  act(()=>useWorkflowStore.getState().undo());expect(screen.queryByDisplayValue('5')).not.toBeNull()
  act(()=>useWorkflowStore.getState().redo());expect((screen.getByRole('textbox') as HTMLInputElement).value).toBe(value)
  const content=JSON.parse(useWorkflowStore.getState().exportWorkflow())
  const saved=await mockRequest('http://autoflow-studio.mock/api/local-workflows/save-to-folder',{method:'POST',body:JSON.stringify({filename:'numeric-draft',content})})
  expect(saved.status).toBe(200)
  const loaded=await(await mockRequest('http://autoflow-studio.mock/api/local-workflows/load/numeric-draft.json')).json()
  cleanup();useWorkflowStore.getState().clearWorkflow();expect(useWorkflowStore.getState().importWorkflow(loaded.content)).toBe(true)
  render(<WaitDocument/>);expect((screen.getByRole('textbox') as HTMLInputElement).value).toBe(value)
 }finally{cleanup();useWorkflowStore.getState().clearWorkflow();vi.unstubAllGlobals()}
})
