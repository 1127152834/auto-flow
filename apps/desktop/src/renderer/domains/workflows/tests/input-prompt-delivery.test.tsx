import {act,cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {InputPromptDialog} from '../components/InputPromptDialog'
import {socketService} from '../events'
type Callback=NonNullable<Parameters<typeof socketService.setInputPromptCallback>[0]>
let receive:Callback
beforeEach(()=>{
 vi.spyOn(socketService,'setInputPromptCallback').mockImplementation(callback=>{if(callback)receive=callback})
})
afterEach(()=>{cleanup();vi.restoreAllMocks()})
function open(){render(<InputPromptDialog />);act(()=>receive({requestId:'delivery-1',title:'输入确认',message:'请输入',variableName:'answer',defaultValue:'草稿值',inputMode:'single'}))}
const confirm=()=>screen.getByRole('button',{name:'确定'})
it('keeps the prompt and disables repeated submission until command confirmation',async()=>{
 let release!:(value:Awaited<ReturnType<typeof socketService.sendInputResult>>)=>void
 vi.spyOn(socketService,'sendInputResult').mockImplementation(()=>new Promise(resolve=>{release=resolve}))
 open();fireEvent.click(confirm())
 expect(screen.queryByRole('dialog')).not.toBeNull()
 expect((confirm() as HTMLButtonElement).disabled).toBe(true)
 fireEvent.click(confirm());expect(socketService.sendInputResult).toHaveBeenCalledTimes(1)
 await act(async()=>release({commandId:vi.mocked(socketService.sendInputResult).mock.calls[0][2]!,success:true}))
 expect(screen.queryByRole('dialog')).toBeNull()
})
it('preserves a rejected input for correction instead of discarding the draft',async()=>{
 vi.spyOn(socketService,'sendInputResult').mockImplementation(async(_request,_value,commandId)=>({commandId:commandId!,success:false,error:'输入请求校验失败'}))
 open();await act(async()=>fireEvent.click(confirm()))
 expect(screen.queryByDisplayValue('草稿值')).not.toBeNull()
 expect(screen.queryByText('输入请求校验失败')).not.toBeNull()
 expect((confirm() as HTMLButtonElement).disabled).toBe(false)
})
it('queries an unconfirmed command without resubmitting the possibly applied value',async()=>{
 vi.spyOn(socketService,'sendInputResult').mockImplementation(async(_request,_value,commandId)=>({commandId:commandId!,success:false,status:'unconfirmed',error:'响应丢失'}))
 const query=vi.spyOn(socketService,'queryInputResult').mockImplementation(async commandId=>({commandId,success:true,httpStatus:200}))
 open();await act(async()=>fireEvent.click(confirm()))
 expect(screen.queryByDisplayValue('草稿值')).not.toBeNull()
 await act(async()=>fireEvent.click(screen.getByRole('button',{name:'查询提交结果'})))
 expect(query).toHaveBeenCalledWith(vi.mocked(socketService.sendInputResult).mock.calls[0][2])
 expect(socketService.sendInputResult).toHaveBeenCalledTimes(1)
 expect(screen.queryByRole('dialog')).toBeNull()
})
it('does not close a newer prompt when the old submission response arrives',async()=>{
 let release!:(value:Awaited<ReturnType<typeof socketService.sendInputResult>>)=>void
 vi.spyOn(socketService,'sendInputResult').mockImplementation(()=>new Promise(resolve=>{release=resolve}))
 open();fireEvent.click(confirm())
 act(()=>receive({requestId:'delivery-2',title:'新请求',message:'请输入',variableName:'answer',defaultValue:'新草稿',inputMode:'single'}))
 await act(async()=>release({commandId:vi.mocked(socketService.sendInputResult).mock.calls[0][2]!,success:true}))
 expect(screen.queryByRole('dialog',{name:'新请求'})).not.toBeNull()
 expect(screen.queryByDisplayValue('新草稿')).not.toBeNull()
})
it('keeps a cancelled prompt until cancellation is confirmed',async()=>{
 let release!:(value:Awaited<ReturnType<typeof socketService.sendInputResult>>)=>void
 vi.spyOn(socketService,'sendInputResult').mockImplementation(()=>new Promise(resolve=>{release=resolve}))
 open();fireEvent.click(screen.getByRole('button',{name:'取消'}))
 expect(screen.queryByRole('dialog')).not.toBeNull()
 expect(socketService.sendInputResult).toHaveBeenCalledWith('delivery-1',null,expect.any(String))
 await act(async()=>release({commandId:vi.mocked(socketService.sendInputResult).mock.calls[0][2]!,success:true}))
 expect(screen.queryByRole('dialog')).toBeNull()
})
