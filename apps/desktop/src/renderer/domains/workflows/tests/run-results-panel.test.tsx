import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {RunResultsPanel} from '../components/RunResultsPanel'
import {DataTable} from '../components/DataTable'
import {workflowApi} from '../api'
beforeEach(()=>{vi.stubGlobal('ResizeObserver',class{observe(){} unobserve(){} disconnect(){}})})
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals()})
const page=(runId='run-a',sequence=1)=>({runId,workflowId:'flow',items:[{sequence,nodeId:'n',executionId:`exec-${sequence}`,values:{value:'小值'},largeValues:{large:'大值摘要'}}],total:101,nextCursor:sequence===1?100:null,throughSequence:101})
it('pages a fixed run, reads complete values and exports only that snapshot',async()=>{
 const list=vi.spyOn(workflowApi,'getRunResults').mockResolvedValue({success:true,data:page()})
 const full='完整'+ '中'.repeat(70_000)
 const value=vi.spyOn(workflowApi,'getRunResultValue').mockResolvedValue({success:true,data:{runId:'run-a',sequence:1,key:'large',value:full}})
 const exportApi=vi.spyOn(workflowApi,'exportRunResults').mockResolvedValue({success:true,data:new Blob(['{"complete":true}\n'])})
 vi.spyOn(URL,'createObjectURL').mockReturnValue('blob:result');vi.spyOn(URL,'revokeObjectURL').mockImplementation(()=>{});const click=vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>{})
 render(<RunResultsPanel runId="run-a"/>);fireEvent.click(await screen.findByText('大值摘要…（点击读取完整值）'))
 await waitFor(()=>expect((screen.getByLabelText('完整结果内容') as HTMLTextAreaElement).value).toBe(JSON.stringify(full,null,2)))
 expect(value).toHaveBeenCalledWith('run-a',1,'large')
 fireEvent.click(screen.getByText('关闭结果详情'))
 fireEvent.click(screen.getByText('导出本次运行结果'));await waitFor(()=>expect(click).toHaveBeenCalledOnce())
 expect(exportApi).toHaveBeenCalledWith('run-a',101)
 list.mockResolvedValue({success:true,data:page('run-a',101)})
 fireEvent.click(screen.getByText('下一页结果'));await waitFor(()=>expect(list).toHaveBeenLastCalledWith('run-a',100,100,101))
})
it('discards delayed full values when switching run and shows export failure without fallback',async()=>{
 vi.spyOn(workflowApi,'getRunResults').mockImplementation(async id=>({success:true,data:page(id)}))
 let resolve!:(value:Awaited<ReturnType<typeof workflowApi.getRunResultValue>>)=>void
 vi.spyOn(workflowApi,'getRunResultValue').mockImplementation(()=>new Promise(done=>{resolve=done}))
 vi.spyOn(workflowApi,'exportRunResults').mockResolvedValue({success:false,error:'文件缺失'})
 const {rerender}=render(<RunResultsPanel key="a" runId="run-a"/>);fireEvent.click(await screen.findByText('大值摘要…（点击读取完整值）'))
 rerender(<RunResultsPanel key="b" runId="run-b"/>);await screen.findByText('运行 run-b · 1/101')
 await act(async()=>resolve({success:true,data:{runId:'run-a',sequence:1,key:'large',value:'旧运行秘密'}}))
 expect(screen.queryByLabelText('完整结果内容')).toBeNull()
 fireEvent.click(screen.getByText('导出本次运行结果'));await screen.findByRole('alert');expect(screen.getByRole('alert').textContent).toContain('文件缺失')
})
it('preserves source editing while readonly inspection uses original row indices after sorting',()=>{
 const inspect=vi.fn(),edit=vi.fn()
 const {rerender}=render(<DataTable data={[{value:'z'},{value:'a'}]} columns={['value']} readOnly onInspect={inspect}/>)
 fireEvent.click(screen.getByText('value'));fireEvent.click(screen.getByText('a'));expect(inspect).toHaveBeenCalledWith(1,'value')
 expect(screen.queryByDisplayValue('a')).toBeNull()
 rerender(<DataTable data={[{value:'z'},{value:'a'}]} columns={['value']} onEdit={edit}/>)
 fireEvent.click(screen.getByText('a'));fireEvent.change(screen.getByDisplayValue('a'),{target:{value:'修改'}});fireEvent.keyDown(screen.getByDisplayValue('修改'),{key:'Enter'})
 expect(edit).toHaveBeenCalledWith(1,'value','修改')
})
