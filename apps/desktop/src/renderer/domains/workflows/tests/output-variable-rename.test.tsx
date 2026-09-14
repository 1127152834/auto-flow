import {act,cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {useWorkflowStore} from '../editor-store'
import {VariableNameInput} from '../components/controls/variable-name-input'
let source:string
let target:string
function Field(){
 const value=useWorkflowStore(s=>s.nodes.find(n=>n.id===source)?.data.variableName as string || '')
 return <VariableNameInput value={value} onChange={value=>useWorkflowStore.getState().updateNodeData(source,{variableName:value})} />
}
beforeEach(()=>{
 vi.useFakeTimers();const s=useWorkflowStore.getState();s.clearWorkflow()
 s.addNode('get_element_info',{x:0,y:0});source=useWorkflowStore.getState().nodes[0].id
 s.updateNodeData(source,{variableName:'old'})
 s.addNode('input_text',{x:0,y:0});target=useWorkflowStore.getState().nodes[1].id
 s.updateNodeData(target,{text:'{old} ${old} {older}',nested:[{value:'{old[0]}'}]})
})
afterEach(()=>{cleanup();vi.useRealTimers()})
function rename(){
 const input=screen.getByRole('textbox');fireEvent.focus(input)
 for(const value of ['n','ne','new'])fireEvent.change(input,{target:{value}})
 fireEvent.blur(input);act(()=>vi.advanceTimersByTime(150))
}
function config(id:string){return useWorkflowStore.getState().nodes.find(n=>n.id===id)!.data}
it('undoes the complete typed output name and nested reference update together',()=>{
 render(<Field/>);rename();fireEvent.click(screen.getByRole('button',{name:'全部更新'}))
 expect(config(source).variableName).toBe('new');expect(config(target).text).toBe('{new} ${new} {older}')
 act(()=>useWorkflowStore.getState().undo())
 expect(config(source).variableName).toBe('old');expect(config(target)).toMatchObject({text:'{old} ${old} {older}',nested:[{value:'{old[0]}'}]})
 act(()=>useWorkflowStore.getState().redo());expect(config(source).variableName).toBe('new');expect(config(target).text).toBe('{new} ${new} {older}')
})
it('preserves unrelated changes made while the rename confirmation is open',()=>{
 render(<Field/>);rename();act(()=>useWorkflowStore.getState().setWorkflowNameWithHistory('另一次编辑'))
 fireEvent.click(screen.getByRole('button',{name:'全部更新'}));act(()=>useWorkflowStore.getState().undo())
 expect(useWorkflowStore.getState().name).toBe('另一次编辑');expect(config(target).text).toBe('{old} ${old} {older}')
 act(()=>useWorkflowStore.getState().undo());expect(useWorkflowStore.getState().name).toBe('未命名工作流')
})
it('keeps references unchanged when choosing only this field',()=>{
 render(<Field/>);rename();fireEvent.click(screen.getByRole('button',{name:'仅改此处'}))
 expect(config(source).variableName).toBe('new');expect(config(target).text).toBe('{old} ${old} {older}')
})
it('keeps a long typed rename reversible even when typing exceeds the history limit',()=>{
 render(<Field/>);const input=screen.getByRole('textbox');fireEvent.focus(input)
 for(let length=1;length<=60;length++)fireEvent.change(input,{target:{value:'x'.repeat(length)}})
 fireEvent.blur(input);act(()=>vi.advanceTimersByTime(150));fireEvent.click(screen.getByRole('button',{name:'全部更新'}))
 act(()=>useWorkflowStore.getState().undo());expect(config(source).variableName).toBe('old');expect(config(target).text).toBe('{old} ${old} {older}')
 act(()=>useWorkflowStore.getState().redo());expect(config(source).variableName).toBe('x'.repeat(60))
})
it('does not merge an unrelated edit between individual input changes',()=>{
 render(<Field/>);const input=screen.getByRole('textbox');fireEvent.focus(input)
 fireEvent.change(input,{target:{value:'n'}})
 act(()=>useWorkflowStore.getState().updateNodeData(target,{remark:'保留这次编辑'}))
 fireEvent.change(input,{target:{value:'new'}});fireEvent.blur(input);act(()=>vi.advanceTimersByTime(150))
 fireEvent.click(screen.getByRole('button',{name:'全部更新'}));act(()=>useWorkflowStore.getState().undo())
 expect(config(target).remark).toBe('保留这次编辑');expect(config(target).text).toBe('{old} ${old} {older}')
 act(()=>useWorkflowStore.getState().undo());expect(config(target).remark).toBe('保留这次编辑');expect(config(source).variableName).toBe('n')
 act(()=>useWorkflowStore.getState().undo());expect(config(target).remark).toBeUndefined()
})
it('discards a pending confirmation when its input unmounts',()=>{
 const {unmount}=render(<Field/>);const input=screen.getByRole('textbox')
 fireEvent.change(input,{target:{value:'new'}});fireEvent.blur(input);unmount();act(()=>vi.advanceTimersByTime(150))
 expect(screen.queryByRole('button',{name:'全部更新'})).toBeNull();expect(config(target).text).toBe('{old} ${old} {older}')
})
