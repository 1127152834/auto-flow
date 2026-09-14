import {act,cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
vi.hoisted(()=>{const values=new Map<string,string>();vi.stubGlobal('localStorage',{getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>values.set(key,value),removeItem:(key:string)=>values.delete(key)});Object.defineProperty(window,'innerWidth',{configurable:true,value:1440})})
import {ConfigPanel} from '../components/ConfigPanel'
import {useWorkflowStore as store} from '../editor-store'
import {elementPickerApi,systemApi} from '../api'
let id:string
beforeEach(()=>{
 vi.useFakeTimers();store.getState().clearWorkflow();store.getState().addNode('click_element',{x:0,y:0});id=store.getState().nodes[0].id;store.getState().updateNodeData(id,{selector:'#before'})
 vi.spyOn(elementPickerApi,'start').mockResolvedValue({success:true})
 vi.spyOn(elementPickerApi,'stop').mockResolvedValue({success:true})
 vi.spyOn(elementPickerApi,'getSelected').mockResolvedValue({success:true,data:{selected:false}})
 vi.spyOn(elementPickerApi,'getSimilar').mockResolvedValue({success:true,data:{selected:false}})
 vi.spyOn(systemApi,'setClipboard').mockResolvedValue({success:true})
})
afterEach(()=>{cleanup();vi.useRealTimers();vi.restoreAllMocks()})
async function start(){render(<ConfigPanel selectedNodeId={id}/>);fireEvent.click(screen.getByTitle('可视化选择元素'));await act(async()=>fireEvent.click(screen.getByText('启动选择器')))}
it('keeps a cleanup action when startup and its recovery query cannot be confirmed',async()=>{
 vi.mocked(elementPickerApi.start).mockResolvedValueOnce({success:false,error:'连接中断',outcomeUnknown:true})
 await start()
 expect(screen.getByTitle('停止选择')).toBeTruthy()
 expect(store.getState().logs.some(log=>log.message.includes('启动状态尚未确认'))).toBe(true)
 await act(async()=>fireEvent.click(screen.getByTitle('停止选择')))
 expect(elementPickerApi.stop).toHaveBeenCalledTimes(1)
 expect(screen.getByTitle('可视化选择元素')).toBeTruthy()
})
it.each(['business','network'])('keeps retry available after a %s stop failure',async mode=>{
 if(mode==='business')vi.mocked(elementPickerApi.stop).mockResolvedValueOnce({success:false,error:'清理失败'})
 else vi.mocked(elementPickerApi.stop).mockRejectedValueOnce(new Error('清理失败'))
 await start();await act(async()=>fireEvent.click(screen.getByTitle('停止选择')))
 expect(screen.getByTitle('停止选择')).toBeTruthy()
 expect(store.getState().logs.some(log=>log.level==='error'&&log.message.includes('清理失败'))).toBe(true)
 expect(store.getState().logs.some(log=>log.message==='元素选择器已停止')).toBe(false)
 await act(async()=>fireEvent.click(screen.getByTitle('停止选择')))
 expect(screen.getByTitle('可视化选择元素')).toBeTruthy()
 expect(elementPickerApi.stop).toHaveBeenCalledTimes(2)
})
it('does not send duplicate stop requests while cleanup is pending',async()=>{
 let release!:(value:{success:boolean})=>void;vi.mocked(elementPickerApi.stop).mockImplementation(()=>new Promise(resolve=>{release=resolve}))
 await start();fireEvent.click(screen.getByTitle('停止选择'));fireEvent.click(screen.getByTitle('停止选择'))
 expect(elementPickerApi.stop).toHaveBeenCalledTimes(1)
 await act(async()=>release({success:true}));expect(screen.getByTitle('可视化选择元素')).toBeTruthy()
})
it('keeps the applied selector but exposes failed automatic cleanup for retry',async()=>{
 vi.mocked(elementPickerApi.getSelected).mockResolvedValue({success:true,data:{selected:true,element:{selector:'#picked'}}})
 vi.mocked(elementPickerApi.stop).mockResolvedValueOnce({success:false,error:'清理失败'})
 await start();await act(async()=>vi.advanceTimersByTimeAsync(500))
 expect(store.getState().nodes[0].data.selector).toBe('#picked')
 expect(screen.getByTitle('停止选择')).toBeTruthy()
 await act(async()=>fireEvent.click(screen.getByTitle('停止选择')))
 expect(screen.getByTitle('可视化选择元素')).toBeTruthy()
 expect(store.getState().nodes[0].data.selector).toBe('#picked')
})
it('preserves similar selector and index while automatic cleanup is retried',async()=>{
 vi.mocked(elementPickerApi.getSimilar).mockResolvedValue({success:true,data:{selected:true,similar:{pattern:'.item-{index}',count:4,minIndex:1,maxIndex:4}}})
 vi.mocked(elementPickerApi.stop).mockResolvedValueOnce({success:false,error:'清理失败'})
 await start();await act(async()=>vi.advanceTimersByTimeAsync(500));await act(async()=>fireEvent.click(screen.getByText('确认使用')))
 expect(store.getState().nodes[0].data.selector).toBe('.item-{index}')
 expect(store.getState().variables.find(v=>v.name==='index')?.value).toBe(1)
 expect(screen.getByTitle('停止选择')).toBeTruthy()
 await act(async()=>fireEvent.click(screen.getByTitle('停止选择')))
 expect(screen.getByTitle('可视化选择元素')).toBeTruthy()
 act(()=>store.getState().undo());expect(store.getState().nodes[0].data.selector).toBe('#before');expect(store.getState().variables).toHaveLength(0)
})
