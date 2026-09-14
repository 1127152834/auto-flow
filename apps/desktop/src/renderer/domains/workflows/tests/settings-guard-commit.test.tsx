import {useLayoutEffect,useRef,useState} from 'react'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {useSettingsDraftProtection,type SettingsLeaveGuard} from '../hooks/useSettingsDraftProtection'
afterEach(cleanup)
it('uses the committed clean state for a close request before passive effects run',async()=>{
 const close=vi.fn()
 function Form({saved,register}:{saved:boolean;register:(guard:SettingsLeaveGuard|null)=>void}){
  const protection=useSettingsDraftProtection(register,'保存配置？',!saved,false,async()=>true)
  return protection.dialog
 }
 function Parent(){
  const [saved,setSaved]=useState(false)
  const guard=useRef<SettingsLeaveGuard|null>(null)
  useLayoutEffect(()=>{if(saved)void guard.current?.().then(allowed=>{if(allowed)close()})},[saved])
  return <><button onClick={()=>setSaved(true)}>保存后立即关闭</button><Form saved={saved} register={value=>{guard.current=value}}/></>
 }
 render(<Parent/>);fireEvent.click(screen.getByText('保存后立即关闭'))
 await waitFor(()=>expect(close).toHaveBeenCalledTimes(1))
 expect(screen.queryByRole('dialog',{name:'保存配置？'})).toBeNull()
})
