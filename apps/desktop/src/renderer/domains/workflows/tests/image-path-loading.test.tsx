import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
const service=vi.hoisted(()=>({list:vi.fn(),folders:vi.fn(),file:vi.fn()}))
vi.mock('../api',()=>({imageAssetApi:{list:service.list,listFolders:service.folders},systemApi:{selectFile:service.file}}))
vi.mock('../components/controls/image-asset-preview',()=>({ImageAssetPreview:()=>null}))
import {ImagePathInput} from '../components/controls/image-path-input'
import {configureStudioConnection} from '../api/config'
const asset={id:'one',name:'one.png',originalName:'测试图像',size:1,uploadedAt:'2026-09-14',folder:'',extension:'.png',path:'/fixture/one.png'}
const deferred=()=>{let resolve!:(value:unknown)=>void;const promise=new Promise(done=>{resolve=done});return{promise,resolve}}
beforeEach(()=>{service.list.mockReset().mockResolvedValue({success:true,data:[asset]});service.folders.mockReset().mockResolvedValue({success:true,data:[]});service.file.mockReset().mockResolvedValue({success:true,data:{success:false,path:null}})})
afterEach(cleanup)
const open=()=>fireEvent.click(screen.getByRole('button',{name:'选择图像资源'}))
it('shows loading separately, applies a selected path, and permits reopening an existing value',async()=>{
 const pending=deferred();service.list.mockReturnValueOnce(pending.promise)
 const change=vi.fn();render(<ImagePathInput value="existing.png" onChange={change}/>);expect(service.list).not.toHaveBeenCalled();open()
 expect(screen.getByRole('status').textContent).toContain('正在加载');expect(screen.queryByText('图像资源库为空（可选）')).toBeNull()
 await act(async()=>pending.resolve({success:true,data:[asset]}));fireEvent.click(await screen.findByRole('button',{name:'测试图像'}))
 expect(change).toHaveBeenCalledWith('/fixture/one.png');expect(screen.queryByRole('button',{name:'测试图像'})).toBeNull()
 open();await screen.findByRole('button',{name:'测试图像'});expect(service.list).toHaveBeenCalledTimes(2)
})
it.each(['assets-failed','folders-failed','malformed-assets','malformed-folders','exception'])('shows retry instead of an empty library for %s',async mode=>{
 if(mode==='assets-failed')service.list.mockResolvedValueOnce({success:false,error:'无权限'})
 if(mode==='folders-failed')service.folders.mockResolvedValueOnce({success:false,error:'无权限'})
 if(mode==='malformed-assets')service.list.mockResolvedValueOnce({success:true,data:[{}]})
 if(mode==='malformed-folders')service.folders.mockResolvedValueOnce({success:true,data:[{}]})
 if(mode==='exception')service.list.mockRejectedValueOnce(new Error('断线'))
 render(<ImagePathInput value="" onChange={vi.fn()}/>);open();await screen.findByRole('alert')
 expect(screen.queryByText('图像资源库为空（可选）')).toBeNull();expect(screen.queryByRole('button',{name:'测试图像'})).toBeNull()
 fireEvent.click(screen.getByRole('button',{name:'重试加载图像资源'}));await screen.findByRole('button',{name:'测试图像'})
})
it('reports a successful empty library as empty',async()=>{
 service.list.mockResolvedValue({success:true,data:[]});render(<ImagePathInput value="" onChange={vi.fn()}/>);open()
 await screen.findByText('图像资源库为空（可选）');expect(screen.queryByRole('alert')).toBeNull()
})
it('ignores a late list from an earlier opening',async()=>{
 const pending=deferred();service.list.mockReturnValueOnce(pending.promise)
 render(<ImagePathInput value="" onChange={vi.fn()}/>);open();open();open();await screen.findByRole('button',{name:'测试图像'})
 await act(async()=>pending.resolve({success:true,data:[{...asset,originalName:'过期图像'}]}))
 expect(screen.queryByText('过期图像')).toBeNull()
})
it('reloads on connection replacement and ignores the previous response',async()=>{
 const pending=deferred();service.list.mockReturnValueOnce(pending.promise)
 render(<ImagePathInput value="" onChange={vi.fn()}/>);open()
 let restore!:()=>void
 act(()=>{restore=configureStudioConnection('http://next.fixture',fetch)})
 try{await screen.findByRole('button',{name:'测试图像'});await act(async()=>pending.resolve({success:true,data:[{...asset,originalName:'旧服务'}]}));expect(screen.queryByText('旧服务')).toBeNull()}
 finally{cleanup();restore()}
})
it.each(['edit','unmount','connection'])('ignores a file selection after %s',async action=>{
 const pending=deferred();service.file.mockReturnValue(pending.promise);const change=vi.fn();const view=render(<ImagePathInput value="old" onChange={change}/>);
 fireEvent.click(screen.getByRole('button',{name:'从电脑选择图片'}));fireEvent.click(screen.getByRole('button',{name:'从电脑选择图片'}));expect(service.file).toHaveBeenCalledOnce()
 let restore=()=>{}
 if(action==='edit')view.rerender(<ImagePathInput value="new" onChange={change}/>);
 if(action==='unmount')view.unmount()
 if(action==='connection')act(()=>{restore=configureStudioConnection('http://next.fixture',fetch)})
 try{
  if(action!=='unmount'){fireEvent.click(screen.getByRole('button',{name:'从电脑选择图片'}));expect(service.file).toHaveBeenCalledOnce()}
  await act(async()=>pending.resolve({success:true,data:{success:true,path:'late.png'}}));expect(change).not.toHaveBeenCalled()
  if(action!=='unmount')expect((screen.getByRole('button',{name:'从电脑选择图片'}) as HTMLButtonElement).disabled).toBe(false)
 }
 finally{cleanup();restore()}
})
it('preserves cancellation and displays file selection failure without changing the field',async()=>{
 const change=vi.fn();render(<ImagePathInput value="keep.png" onChange={change}/>);
 fireEvent.click(screen.getByRole('button',{name:'从电脑选择图片'}));await waitFor(()=>expect((screen.getByRole('button',{name:'从电脑选择图片'}) as HTMLButtonElement).disabled).toBe(false));expect(change).not.toHaveBeenCalled()
 service.file.mockResolvedValue({success:false,error:'宿主不可用'});fireEvent.click(screen.getByRole('button',{name:'从电脑选择图片'}));expect((await screen.findByRole('alert')).textContent).toBe('宿主不可用');expect(change).not.toHaveBeenCalled()
})

it.each([{}, {success:true,path:''}, {success:false,error:'选择失败'}])('rejects an invalid or failed file result %#',async data=>{
 service.file.mockResolvedValue({success:true,data});const change=vi.fn();render(<ImagePathInput value="keep" onChange={change}/>);
 fireEvent.click(screen.getByRole('button',{name:'从电脑选择图片'}));await screen.findByRole('alert');expect(change).not.toHaveBeenCalled()
})
it('applies a confirmed computer selection exactly once',async()=>{
 service.file.mockResolvedValue({success:true,data:{success:true,path:'/fixture/image.png'}});const change=vi.fn();render(<ImagePathInput value="keep" onChange={change}/>);
 fireEvent.click(screen.getByRole('button',{name:'从电脑选择图片'}));await waitFor(()=>expect(change).toHaveBeenCalledExactlyOnceWith('/fixture/image.png'))
})
