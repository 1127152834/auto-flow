import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {InputPromptDialog} from '../components/InputPromptDialog'
import {socketService} from '../events'
import {configureStudioConnection} from '../api/config'
type Callback=NonNullable<Parameters<typeof socketService.setInputPromptCallback>[0]>
let receive:Callback
let release:((response:Response)=>void)|undefined
let restore:()=>void
beforeEach(()=>{
 release=undefined
 vi.spyOn(socketService,'setInputPromptCallback').mockImplementation(callback=>{if(callback)receive=callback})
 restore=configureStudioConnection('http://path-fixture.test',()=>new Promise<Response>(resolve=>{release=resolve}))
})
afterEach(()=>{cleanup();restore();vi.restoreAllMocks()})
function prompt(id:string,mode:'file'|'folder'){
 act(()=>receive({requestId:id,title:'选择路径',message:'输入路径',variableName:'path',defaultValue:`${id}-draft`,inputMode:mode}))
}
it.each(['file','folder'] as const)('does not apply late %s selection to another prompt',async mode=>{
 render(<InputPromptDialog />);prompt('old',mode)
 fireEvent.click(screen.getByRole('button',{name:'浏览'}));await waitFor(()=>expect(release).toBeTypeOf('function'));prompt('new',mode)
 await act(async()=>release!(Response.json({success:true,path:'/old/result'})))
 expect(screen.queryByDisplayValue('new-draft')).not.toBeNull()
 expect(screen.queryByDisplayValue('/old/result')).toBeNull()
})
it.each(['file','folder'] as const)('preserves manual edits during %s selection',async mode=>{
 render(<InputPromptDialog />);prompt('edit',mode)
 fireEvent.click(screen.getByRole('button',{name:'浏览'}))
 await waitFor(()=>expect(release).toBeTypeOf('function'))
 fireEvent.change(screen.getByDisplayValue('edit-draft'),{target:{value:'new-manual-value'}})
 await act(async()=>release!(Response.json({success:true,path:'/old/result'})))
 expect(screen.queryByDisplayValue('new-manual-value')).not.toBeNull()
})
it.each(['file','folder'] as const)('shows %s service failure without replacing the draft',async mode=>{
 render(<InputPromptDialog />);prompt('failure',mode)
 fireEvent.click(screen.getByRole('button',{name:'浏览'}))
 await waitFor(()=>expect(release).toBeTypeOf('function'))
 await act(async()=>release!(Response.json({success:false,error:'路径选择不可用'},{status:503})))
 expect(screen.queryByText(/路径选择不可用/)).not.toBeNull()
 expect(screen.queryByDisplayValue('failure-draft')).not.toBeNull()
})
it.each(['file','folder'] as const)('applies a valid %s selection and prevents duplicate opens',async mode=>{
 render(<InputPromptDialog />);prompt('valid',mode)
 fireEvent.click(screen.getByRole('button',{name:'浏览'}))
 await waitFor(()=>expect(release).toBeTypeOf('function'))
 expect((screen.getByRole('button',{name:'选择中…'}) as HTMLButtonElement).disabled).toBe(true)
 await act(async()=>release!(Response.json({success:true,path:'/valid/result'})))
 expect(screen.queryByDisplayValue('/valid/result')).not.toBeNull()
 expect((screen.getByRole('button',{name:'浏览'}) as HTMLButtonElement).disabled).toBe(false)
})
it.each(['file','folder'] as const)('keeps the draft when the %s chooser is cancelled',async mode=>{
 render(<InputPromptDialog />);prompt('cancelled',mode)
 fireEvent.click(screen.getByRole('button',{name:'浏览'}))
 await waitFor(()=>expect(release).toBeTypeOf('function'))
 await act(async()=>release!(Response.json({success:true,path:null})))
 expect(screen.queryByDisplayValue('cancelled-draft')).not.toBeNull()
 expect(screen.queryByText('服务返回了无效路径')).toBeNull()
})
it.each(['file','folder'] as const)('rejects a malformed %s path without changing the input',async mode=>{
 render(<InputPromptDialog />);prompt('malformed',mode)
 fireEvent.click(screen.getByRole('button',{name:'浏览'}))
 await waitFor(()=>expect(release).toBeTypeOf('function'))
 await act(async()=>release!(Response.json({success:true,path:{invalid:true}})))
 expect(screen.queryByDisplayValue('malformed-draft')).not.toBeNull()
 expect(screen.queryByText('服务返回了无效路径')).not.toBeNull()
})
it.each(['file','folder'] as const)('discards %s selection after the input is submitted',async mode=>{
 vi.spyOn(socketService,'sendInputResult').mockImplementation((_id,_value,commandId)=>Promise.resolve({commandId:commandId!,success:true}))
 render(<InputPromptDialog />);prompt('submitted',mode)
 fireEvent.click(screen.getByRole('button',{name:'浏览'}))
 await waitFor(()=>expect(release).toBeTypeOf('function'))
 fireEvent.click(screen.getByRole('button',{name:'确定'}))
 await waitFor(()=>expect(screen.queryByRole('dialog')).toBeNull())
 await act(async()=>release!(Response.json({success:true,path:'/late/result'})))
 expect(screen.queryByRole('dialog')).toBeNull()
 expect(vi.mocked(socketService.sendInputResult).mock.calls[0][1]).toBe('submitted-draft')
})

it.each(['file','folder'] as const)('recognizes the frozen WebRPA %s cancellation response',async mode=>{
 render(<InputPromptDialog />);prompt('source-cancel',mode)
 fireEvent.click(screen.getByRole('button',{name:'浏览'}))
 await waitFor(()=>expect(release).toBeTypeOf('function'))
 await act(async()=>release!(Response.json({success:false,path:null,message:'用户取消选择'})))
 expect(screen.queryByDisplayValue('source-cancel-draft')).not.toBeNull()
 expect(screen.queryByText('用户取消选择')).toBeNull()
})
it.each(['file','folder'] as const)('does not hide an actual %s service error behind a cancellation message',async mode=>{
 render(<InputPromptDialog />);prompt('source-error',mode)
 fireEvent.click(screen.getByRole('button',{name:'浏览'}))
 await waitFor(()=>expect(release).toBeTypeOf('function'))
 await act(async()=>release!(Response.json({success:false,path:null,message:'用户取消选择',error:'实际错误'})))
 expect(screen.queryByText('实际错误')).not.toBeNull()
 expect(screen.queryByDisplayValue('source-error-draft')).not.toBeNull()
})
