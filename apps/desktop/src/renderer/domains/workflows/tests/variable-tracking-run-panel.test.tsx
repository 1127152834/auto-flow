import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
const api=vi.hoisted(()=>({listRun:vi.fn(),getRunValue:vi.fn(),clearRun:vi.fn(),exportRun:vi.fn(),list:vi.fn(),clear:vi.fn(),listRuns:vi.fn()}))
vi.mock('../api',()=>({variableTrackingApi:api,workflowApi:api}))
import type {VariableTrackingRecord} from '../api'
import {VariableTrackingPanel} from '../components/VariableTrackingPanel'
const record: VariableTrackingRecord & {sequence:number;executionId:string;largeValues:Record<string,string>}={timestamp:'2026-09-14T00:00:00Z',variable_name:'result',old_value:null,new_value:'当前值',node_id:'node',node_name:'脚本',operation:'update',value_type:'string',sequence:1,executionId:'workflow',largeValues:{}}
const page=(runId='run-a',tracking=[record],nextCursor:number|null=100)=>({success:true,data:{runId,tracking,total:201,nextCursor,throughSequence:201}})
const panel=(runId='run-a')=><VariableTrackingPanel workflowId="workflow" runId={runId} isOpen onClose={vi.fn()}/>
const originalScroll = Object.getOwnPropertyDescriptor(HTMLElement.prototype,"scrollIntoView")
beforeEach(()=>{Object.defineProperty(HTMLElement.prototype,"scrollIntoView",{configurable:true,value:vi.fn()});vi.clearAllMocks();api.listRun.mockImplementation(async(runId)=>page(runId));api.clearRun.mockResolvedValue({success:true,data:{runId:'run-a',message:'已清空'}})})
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();if(originalScroll)Object.defineProperty(HTMLElement.prototype,"scrollIntoView",originalScroll);else Reflect.deleteProperty(HTMLElement.prototype,"scrollIntoView")})
it('pages within the initial cutoff and sends filters to the service',async()=>{
 render(panel());await screen.findByText('当前值');fireEvent.click(screen.getByTitle('关闭自动刷新'))
 expect(screen.getByText('共 201 条记录，本页 1 条')).toBeTruthy()
 fireEvent.click(screen.getByText('下一页'))
 await waitFor(()=>expect(api.listRun).toHaveBeenLastCalledWith('run-a',expect.objectContaining({cursor:100,limit:100,throughSequence:201}),expect.any(AbortSignal)))
 fireEvent.change(screen.getByPlaceholderText('搜索变量名、模块名或值...'),{target:{value:'别的页'}})
 await waitFor(()=>expect(api.listRun).toHaveBeenLastCalledWith('run-a',expect.objectContaining({cursor:0,query:'别的页',throughSequence:undefined}),expect.any(AbortSignal)))
 // Service results are not filtered a second time using the local preview.
 expect(screen.getByText('当前值')).toBeTruthy()
 expect(api.list).not.toHaveBeenCalled()
})
it('exports the server blob at the confirmed cutoff and current filters',async()=>{
 const blob=new Blob(['complete-jsonl'])
 api.exportRun.mockResolvedValue({success:true,data:blob})
 const createObjectURL=vi.fn(()=> 'blob:tracking')
 vi.stubGlobal('URL',Object.assign(URL,{createObjectURL,revokeObjectURL:vi.fn()}))
 vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>{})
 render(panel());await screen.findByText('当前值');fireEvent.click(screen.getByTitle('关闭自动刷新'))
 fireEvent.click(screen.getByTitle('导出JSONL'))
 await waitFor(()=>expect(api.exportRun).toHaveBeenCalledWith('run-a',201,{},expect.any(AbortSignal)))
 expect(createObjectURL).toHaveBeenCalledWith(blob)
})
it('reads large values only on demand and ignores a late previous-run value',async()=>{
 api.listRun.mockImplementation(async(runId)=>page(runId,[{...record,new_value:null,largeValues:{new_value:'70000 字节摘要'}}]))
 let finish!:(value:unknown)=>void
 api.getRunValue.mockImplementation(()=>new Promise(resolve=>{finish=resolve}))
 const view=render(panel());await screen.findByText('70000 字节摘要');fireEvent.click(screen.getByTitle('关闭自动刷新'))
 expect(api.getRunValue).not.toHaveBeenCalled()
 fireEvent.click(screen.getByText('读取完整新值'))
 expect(api.getRunValue).toHaveBeenCalledWith('run-a',1,'new_value',expect.any(AbortSignal))
 const signal=api.getRunValue.mock.calls[0][3] as AbortSignal
 view.rerender(panel('run-b'));await screen.findByText('70000 字节摘要');expect(signal.aborted).toBe(true)
 await act(async()=>finish({success:true,data:{runId:'run-a',sequence:1,key:'new_value',value:'旧运行大值'}}))
 expect(screen.queryByText('旧运行大值')).toBeNull()
})
it('shows the complete large value and offers retry after a resource error',async()=>{
 api.listRun.mockResolvedValue(page('run-a',[{...record,new_value:null,largeValues:{new_value:'70000 字节摘要'}}]))
 api.getRunValue.mockResolvedValueOnce({success:false,error:'资源不存在'}).mockResolvedValueOnce({success:true,data:{runId:'run-a',sequence:1,key:'new_value',value:'首'+ 'x'.repeat(70000)+'尾'}})
 render(panel());await screen.findByText('70000 字节摘要');fireEvent.click(screen.getByTitle('关闭自动刷新'))
 fireEvent.click(screen.getByText('读取完整新值'));await screen.findByText('资源不存在')
 fireEvent.click(screen.getByText('读取完整新值'));await waitFor(()=>expect(screen.getByText(/^首x+尾$/).textContent?.length).toBe(70002))
 expect(screen.queryByText('资源不存在')).toBeNull()
 expect(screen.getByText(/^首x+尾$/).className).not.toContain('line-clamp')
})
it('keeps confirmed data on a failed clear and ignores an older read after successful clear',async()=>{
 let finish!:(value:unknown)=>void
 render(panel());await screen.findByText('当前值');fireEvent.click(screen.getByTitle('关闭自动刷新'))
 api.clearRun.mockResolvedValueOnce({success:false,error:'清空被拒绝'})
 fireEvent.click(screen.getByTitle('清空记录'));await screen.findByText('清空被拒绝');expect(screen.getByText('当前值')).toBeTruthy()
 api.listRun.mockImplementation(()=>new Promise(resolve=>{finish=resolve}))
 fireEvent.click(screen.getByTitle('手动刷新'));await waitFor(()=>expect(finish).toBeTypeOf('function'))
 const oldRead=finish
 fireEvent.click(screen.getByTitle('清空记录'));await waitFor(()=>expect(screen.queryByText('当前值')).toBeNull())
 await act(async()=>oldRead(page()));expect(screen.queryByText('当前值')).toBeNull()
 expect(api.clearRun).toHaveBeenCalledWith('run-a',expect.any(AbortSignal));expect(api.clear).not.toHaveBeenCalled()
})

it('selects paginated historical runs explicitly without latest-run fallback',async()=>{
 api.listRuns.mockResolvedValueOnce({success:true,data:{items:[{runId:'history-a',workflowId:'workflow',workflowName:'历史一',startedAt:'2026-09-14'}],nextCursor:50}})
  .mockResolvedValueOnce({success:true,data:{items:[{runId:'history-b',workflowId:'workflow',workflowName:'历史二',startedAt:'2026-09-13'}],nextCursor:null}})
 render(panel());await screen.findByText('当前值');fireEvent.click(screen.getByTitle('关闭自动刷新'))
 expect(api.listRuns).not.toHaveBeenCalled()
 fireEvent.click(screen.getByText('读取运行历史'));await screen.findByText('更早运行')
 expect(api.listRun).toHaveBeenLastCalledWith('run-a',expect.anything(),expect.any(AbortSignal))
 fireEvent.click(screen.getByText('更早运行'));await waitFor(()=>expect(screen.queryByText('更早运行')).toBeNull())
 expect(api.listRuns).toHaveBeenLastCalledWith(undefined,50,50)
 fireEvent.keyDown(screen.getByLabelText('追踪运行'),{key:'ArrowDown'});fireEvent.click(await screen.findByRole('option',{name:/历史二/}))
 await waitFor(()=>expect(api.listRun).toHaveBeenLastCalledWith('history-b',expect.objectContaining({cursor:0,limit:100}),expect.any(AbortSignal)))
 expect(api.list).not.toHaveBeenCalled()
})
