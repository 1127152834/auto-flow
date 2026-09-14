import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
const services=vi.hoisted(()=>({file:vi.fn(),folder:vi.fn()}))
vi.mock('../api',()=>({systemApi:{selectFile:services.file,selectFolder:services.folder}}))
vi.mock('../components/controls/variable-input',()=>({VariableInput:({value,onChange}:{value:string;onChange:(value:string)=>void})=><input value={value} onChange={event=>onChange(event.target.value)}/>}))
import {PathInput} from '../components/controls/path-input'
import {configureStudioConnection} from '../api/config'
beforeEach(()=>{services.file.mockReset();services.folder.mockReset()})
afterEach(cleanup)
const label=(mode:string)=>mode==='file'?'选择文件':'选择文件夹'
it.each(['file','folder'] as const)('%s ignores a failed reply even if it contains a path',async mode=>{
 services[mode].mockResolvedValue({success:false,path:'/should-not-apply',error:'权限不足'})
 const change=vi.fn();render(<PathInput type={mode} value="keep" onChange={change}/>);fireEvent.click(screen.getByTitle(label(mode)))
 expect((await screen.findByRole('alert')).textContent).toContain('权限不足');expect(change).not.toHaveBeenCalled()
})
it.each(['file','folder'] as const)('%s handles success, cancellation and malformed paths explicitly',async mode=>{
 const change=vi.fn();render(<PathInput type={mode} value="keep" onChange={change}/>);
 for(const data of [{success:true,path:null},{success:true,path:''},{success:false,path:null,message:'用户取消选择'}]){
  services[mode].mockResolvedValue({success:true,data});fireEvent.click(screen.getByTitle(label(mode)));await act(async()=>{});expect(change).not.toHaveBeenCalled();expect(screen.queryByRole('alert')).toBeNull()
 }
 services[mode].mockResolvedValue({success:true,data:{success:true,path:{bad:true}}});fireEvent.click(screen.getByTitle(label(mode)));await screen.findByRole('alert');expect(change).not.toHaveBeenCalled()
 services[mode].mockResolvedValue({success:true,data:{success:true,path:'/valid'}});fireEvent.click(screen.getByTitle(label(mode)));await waitFor(()=>expect(change).toHaveBeenCalledExactlyOnceWith('/valid'))
})
it.each(['edit','unmount','connection'] as const)('does not write a late path after %s and keeps both buttons locked until reply',async action=>{
 let resolve!:(value:unknown)=>void;services.file.mockImplementation(()=>new Promise(done=>{resolve=done}));const change=vi.fn();const view=render(<PathInput type="both" value="before" onChange={change}/>);
 fireEvent.click(screen.getByTitle('选择文件'));expect((screen.getByTitle('选择文件夹') as HTMLButtonElement).disabled).toBe(true)
 let restore=()=>{}
 if(action==='edit')view.rerender(<PathInput type="both" value="after" onChange={change}/>);
 if(action==='unmount')view.unmount()
 if(action==='connection')act(()=>{restore=configureStudioConnection('http://path-next.fixture',fetch)})
 try{
  if(action!=='unmount'){fireEvent.click(screen.getByTitle('选择文件夹'));expect(services.folder).not.toHaveBeenCalled()}
  await act(async()=>resolve({success:true,data:{success:true,path:'/late'}}));expect(change).not.toHaveBeenCalled()
  if(action!=='unmount')expect((screen.getByTitle('选择文件') as HTMLButtonElement).disabled).toBe(false)
 }finally{cleanup();restore()}
})
it('accepts the legacy flat success and reports a thrown service error',async()=>{
 services.file.mockResolvedValueOnce({success:true,path:'/legacy'}).mockRejectedValueOnce(new Error('连接失败'));const change=vi.fn();render(<PathInput type="file" value="" onChange={change}/>);
 fireEvent.click(screen.getByTitle('选择文件'));await waitFor(()=>expect(change).toHaveBeenCalledExactlyOnceWith('/legacy'))
 fireEvent.click(screen.getByTitle('选择文件'));expect((await screen.findByRole('alert')).textContent).toBe('连接失败');expect(change).toHaveBeenCalledOnce()
})
