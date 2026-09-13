import {act,cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {InputPromptDialog} from '../components/InputPromptDialog'
import {socketService} from '../events'
import {useDialogRegistry} from '../hooks/stores/dialogRegistry'
type Callback=NonNullable<Parameters<typeof socketService.setInputPromptCallback>[0]>
type Prompt=NonNullable<Parameters<Callback>[0]>
let receive: Callback
beforeEach(() => {
  vi.spyOn(socketService,'setInputPromptCallback').mockImplementation(callback=>{if(callback)receive=callback})
  vi.spyOn(socketService,'sendInputResult').mockImplementation(async(_request,_value,commandId)=>({commandId:commandId!,success:true}))
  useDialogRegistry.getState().clear()
})
afterEach(()=>{cleanup();vi.restoreAllMocks()})
function open(inputMode:Prompt['inputMode'], extra:Partial<Prompt>={}) {
  render(<InputPromptDialog />)
  act(()=>receive({requestId:'prompt-1',title:'验收输入',message:'请填写',variableName:'value',defaultValue:'',inputMode,...extra}))
}
const confirm=()=>fireEvent.click(screen.getByRole('button',{name:'确定'}))
it.each(['checkbox','slider_int','slider_float'] as const)('submits an actual %s value with no hidden text default',mode=>{
  open(mode);confirm()
  expect(socketService.sendInputResult).toHaveBeenCalledWith('prompt-1',mode==='checkbox'?'false':'0',expect.any(String))
})
it.each(['select_single','select_multiple'] as const)('submits a chosen %s option with no text default',mode=>{
  open(mode,{selectOptions:['甲','乙']});fireEvent.click(screen.getByText('乙'));confirm()
  expect(socketService.sendInputResult).toHaveBeenCalledWith('prompt-1',mode==='select_single'?'乙':'["乙"]',expect.any(String))
})
it.each(['select_single','select_multiple'] as const)('permits empty optional %s selection',mode=>{
  open(mode,{selectOptions:['甲'],required:false});confirm()
  expect(socketService.sendInputResult).toHaveBeenCalledWith('prompt-1',mode==='select_single'?'':'[]',expect.any(String))
})
it('preserves zero as a slider default when the minimum is negative',()=>{
  open('slider_int',{defaultValue:'0',minValue:-10,maxValue:10});confirm()
  expect(socketService.sendInputResult).toHaveBeenCalledWith('prompt-1','0',expect.any(String))
})
it.each(['Infinity','-Infinity','1e309'])('rejects nonfinite numeric input %s',defaultValue=>{
  open('number',{defaultValue});confirm()
  expect(socketService.sendInputResult).not.toHaveBeenCalled()
})
it.each([
  ['integer',1.5,{}],['number',Infinity,{}],['number',11,{maxValue:10}],['single','long',{maxLength:2}],['select_single','不存在',{selectOptions:['甲']}],['select_multiple',['不存在'],{selectOptions:['甲']}],['checkbox','false',{}],
] as const)('validates AI submission for %s',async(mode,value,extra)=>{
  open(mode,extra as Partial<Prompt>)
  const action=useDialogRegistry.getState().getAction('input_prompt_prompt-1','submit')!
  await act(async()=>{try{await action.handler({value})}catch{/* caller receives validation failure */}})
  expect(socketService.sendInputResult).not.toHaveBeenCalled()
  expect(screen.queryByRole('dialog')).not.toBeNull()
})
it('rejects a late AI action from a previous prompt',async()=>{
  open('single')
  const old=useDialogRegistry.getState().getAction('input_prompt_prompt-1','submit')!
  act(()=>receive({requestId:'prompt-2',title:'新输入',message:'请填写',variableName:'value',defaultValue:'',inputMode:'single'}))
  await act(async()=>{try{await old.handler({value:'stale'})}catch{/* stale action rejected */}})
  expect(socketService.sendInputResult).not.toHaveBeenCalled()
  expect(screen.queryByRole('dialog',{name:'新输入'})).not.toBeNull()
})
it.each([
 ['single','你好'],['multiline','第一行\n第二行'],['list','甲\n乙'],['password','fixture-only'],['file','/tmp/input.txt'],['folder','/tmp/input'],['number','2.5'],['integer','2'],
] as const)('preserves a valid %s input result', (mode,defaultValue)=>{
 open(mode,{defaultValue});confirm();expect(socketService.sendInputResult).toHaveBeenCalledWith('prompt-1',defaultValue,expect.any(String))
})
it.each(['single','multiline','list','password','file','folder','number','integer'] as const)('rejects a missing required %s value',mode=>{
 open(mode);confirm();expect(socketService.sendInputResult).not.toHaveBeenCalled();expect(screen.queryByText('此项为必填')).not.toBeNull()
})
it('keeps edits when the same request event is delivered again',()=>{
 open('single',{defaultValue:'before'})
 fireEvent.change(screen.getByDisplayValue('before'),{target:{value:'edited'}})
 act(()=>receive({requestId:'prompt-1',title:'验收输入',message:'请填写',variableName:'value',defaultValue:'before',inputMode:'single'}))
 confirm();expect(socketService.sendInputResult).toHaveBeenCalledWith('prompt-1','edited',expect.any(String))
})
it('does not apply a repeated AI action twice',async()=>{
 open('single');const action=useDialogRegistry.getState().getAction('input_prompt_prompt-1','submit')!
 await act(async()=>action.handler({value:'once'}))
 await act(async()=>{try{await action.handler({value:'twice'})}catch{/* already consumed */}})
 expect(socketService.sendInputResult).toHaveBeenCalledTimes(1)
})
it('cancels with null and rejects a cached submit after cancellation',async()=>{
 open('single');const action=useDialogRegistry.getState().getAction('input_prompt_prompt-1','submit')!
 fireEvent.click(screen.getByRole('button',{name:'取消'}))
 await act(async()=>{try{await action.handler({value:'late'})}catch{/* cancelled */}})
 expect(socketService.sendInputResult).toHaveBeenCalledExactlyOnceWith('prompt-1',null,expect.any(String))
})
