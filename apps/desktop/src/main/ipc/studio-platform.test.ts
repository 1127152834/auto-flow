// @vitest-environment node
import { expect, it, vi } from 'vitest'
import { createStudioPlatformActionHandler } from './studio-platform'

const event={sender:{id:7,mainFrame:{}},senderFrame:{}}
event.senderFrame=event.sender.mainFrame

function setup(allowed=true){
 const writeText=vi.fn(),writeImage=vi.fn(()=>true),beep=vi.fn(),notify=vi.fn(),readText=vi.fn(()=> 'copied')
 const handler=createStudioPlatformActionHandler({allowed:()=>allowed,writeText,writeImage,beep,notify,readText})
 return {handler,writeText,writeImage,beep,notify,readText}
}

it('limits platform actions to the registered Studio main frame',async()=>{
 const {handler}=setup(false)
 await expect(handler(event,{action:'clipboard_read_text'})).resolves.toMatchObject({ok:false,error:{code:'UNAUTHORIZED_WINDOW'}})
})

it('reads and writes clipboard values through Electron-owned adapters',async()=>{
 const api=setup()
 await expect(api.handler(event,{action:'clipboard_write_text',text:'你好'})).resolves.toEqual({ok:true,value:{}})
 await expect(api.handler(event,{action:'clipboard_read_text'})).resolves.toEqual({ok:true,value:{value:'copied'}})
 await expect(api.handler(event,{action:'clipboard_write_image',path:'/tmp/image.png'})).resolves.toEqual({ok:true,value:{}})
 expect(api.writeText).toHaveBeenCalledWith('你好');expect(api.writeImage).toHaveBeenCalledWith('/tmp/image.png')
})

it('runs bounded sound and notification actions',async()=>{
 vi.useFakeTimers();const api=setup()
 const sounding=api.handler(event,{action:'beep',count:2,interval:0.1})
 await vi.runAllTimersAsync();await expect(sounding).resolves.toEqual({ok:true,value:{}});expect(api.beep).toHaveBeenCalledTimes(2)
 await expect(api.handler(event,{action:'notification',title:'标题',message:'正文',duration:3,playSound:false})).resolves.toEqual({ok:true,value:{}})
 expect(api.notify).toHaveBeenCalledOnce();vi.useRealTimers()
})

it('rejects malformed and unsupported actions before adapters run',async()=>{
 const api=setup()
 for(const request of [null,{action:'clipboard_write_text',text:''},{action:'clipboard_write_image',path:'relative.png'},{action:'beep',count:101,interval:0},{action:'notification',title:'',message:'x',duration:1,playSound:true},{action:'other'}]){
  await expect(api.handler(event,request)).resolves.toMatchObject({ok:false,error:{code:'INVALID_PLATFORM_ACTION'}})
 }
 expect(api.writeText).not.toHaveBeenCalled();expect(api.beep).not.toHaveBeenCalled()
})
